"""The Claude agent loop: one research turn with the web_search and save_finding tools.

All LLM and search calls go through RunBudget (INV-9). Findings are inserted only through
services.findings.save_finding (INV-2). Every DB access uses a short session from
`deps.session_factory`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.engine import prompts
from app.engine.budget import RunBudget
from app.engine.normalize import InvalidUrl, normalize_url
from app.engine.tools import SAVE_FINDING, TOOLS, WEB_SEARCH
from app.integrations.llm import LLMRequest, LLMResponse, TextDelta, ToolUse
from app.models import Message, Research
from app.services import findings as findings_service
from app.services.sinks import RunSink

if TYPE_CHECKING:
    from app.services.runs import RunDeps

logger = logging.getLogger(__name__)

SEARCH_CONTENT_MAX_CHARS = 1500
FINDING_FIELDS = ("title", "url", "summary")


@dataclass
class TurnState:
    """Mutable turn state shared with the caller, so failures can still finalize from it."""

    text_parts: list[str] = field(default_factory=list)
    new_findings: int = 0
    allowed_urls: set[str] = field(default_factory=set)

    @property
    def text(self) -> str:
        return "".join(self.text_parts)


@dataclass(frozen=True)
class ToolResult:
    content: str
    is_error: bool = False

    def block(self, tool_use_id: str) -> dict[str, Any]:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": self.content,
            "is_error": self.is_error,
        }


def _load_context(
    deps: RunDeps, research_id: int, has_user_message: bool
) -> tuple[str, list[dict[str, Any]]]:
    with deps.session_factory() as session:
        research = session.get(Research, research_id)
        if research is None:
            raise LookupError("research disappeared")
        topic = research.topic
        rows = session.scalars(
            select(Message)
            .where(Message.research_id == research_id)
            .order_by(Message.created_at, Message.id)
        ).all()
        urls = findings_service.stored_urls(session, research_id, prompts.MAX_STORED_URLS)
    messages: list[dict[str, Any]] = [
        {"role": m.role, "content": m.content} for m in rows if m.content
    ]
    if not has_user_message or not messages or messages[-1]["role"] != "user":
        # Watch/digest runs (or a thread ending in an assistant turn) get a topic prompt,
        # so a stale user message left by a swept run is never answered by a watch run.
        messages.append({"role": "user", "content": prompts.synthetic_prompt(topic)})
    return prompts.build_system(topic, urls), messages


async def run_turn(
    research_id: int,
    run_id: int,
    trigger: str,
    sink: RunSink,
    budget: RunBudget,
    *,
    deps: RunDeps,
    state: TurnState,
    has_user_message: bool,
) -> None:
    """Run the tool loop to completion. Mutates `state`; on failure re-raises with `state`
    still holding the partial text and the findings count."""
    system, messages = _load_context(deps, research_id, has_user_message)
    for _ in range(deps.settings.run_max_llm_calls):
        request = LLMRequest(
            system=system,
            messages=list(messages),
            max_tokens=deps.settings.llm_max_tokens,
            tools=TOOLS,
        )
        final: LLMResponse | None = None
        async for event in budget.stream(request):
            if isinstance(event, TextDelta):
                if event.text:
                    state.text_parts.append(event.text)
                    sink.emit("token", {"text": event.text})
            else:
                final = event
        if final is None:
            raise RuntimeError("LLM stream ended without a final response")
        content: list[dict[str, Any]] = []
        if final.text:
            content.append({"type": "text", "text": final.text})
        for tu in final.tool_uses:
            content.append({"type": "tool_use", "id": tu.id, "name": tu.name, "input": tu.input})
        if content:
            messages.append({"role": "assistant", "content": content})
        if final.stop_reason != "tool_use" or not final.tool_uses:
            return
        results = []
        for tu in final.tool_uses:
            result = await _dispatch(tu, research_id, run_id, sink, budget, deps, state)
            results.append(result.block(tu.id))
        messages.append({"role": "user", "content": results})
    logger.warning("run %s hit the LLM call safety bound", run_id)


async def _dispatch(
    tool_use: ToolUse,
    research_id: int,
    run_id: int,
    sink: RunSink,
    budget: RunBudget,
    deps: RunDeps,
    state: TurnState,
) -> ToolResult:
    raw = tool_use.input
    if not isinstance(raw, dict):
        return ToolResult("tool input must be an object", is_error=True)
    if tool_use.name == WEB_SEARCH:
        return await _web_search(raw, budget, state)
    if tool_use.name == SAVE_FINDING:
        return _save_finding(raw, research_id, run_id, sink, deps, state)
    return ToolResult(f"unknown tool: {tool_use.name[:64]}", is_error=True)


async def _web_search(raw: dict[Any, Any], budget: RunBudget, state: TurnState) -> ToolResult:
    query = raw.get("query")
    if not isinstance(query, str) or not query.strip():
        return ToolResult("query must be a non-empty string", is_error=True)
    try:
        results = await budget.search(query.strip())
    except Exception:
        logger.exception("web_search failed")
        return ToolResult("web_search failed; try again or a different query", is_error=True)
    out = []
    for r in results:
        try:
            normalized = normalize_url(r.url)
        except InvalidUrl:
            continue
        state.allowed_urls.add(normalized)
        out.append(
            {"title": r.title, "url": r.url, "content": r.content[:SEARCH_CONTENT_MAX_CHARS]}
        )
    return ToolResult(json.dumps(out, ensure_ascii=False))


def _save_finding(
    raw: dict[Any, Any],
    research_id: int,
    run_id: int,
    sink: RunSink,
    deps: RunDeps,
    state: TurnState,
) -> ToolResult:
    for name in FINDING_FIELDS:
        if name not in raw:
            return ToolResult(f"{name} is required", is_error=True)
        if not isinstance(raw[name], str):
            return ToolResult(f"{name} must be a string", is_error=True)
    with deps.session_factory() as session:
        result = findings_service.save_finding(
            session,
            research_id=research_id,
            run_id=run_id,
            raw={name: raw[name] for name in FINDING_FIELDS},
            allowed_urls=state.allowed_urls,
            clock=deps.clock,
        )
    if isinstance(result, findings_service.Saved):
        state.new_findings += 1
        sink.emit("finding", result.finding.model_dump(mode="json"))
        return ToolResult(f"saved finding {result.finding.id}")
    if isinstance(result, findings_service.Duplicate):
        return ToolResult("already saved, skipped")
    return ToolResult(f"not saved: {result.message}", is_error=True)
