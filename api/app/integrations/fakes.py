"""Deterministic in-process fakes for tests and INTEGRATIONS_MODE=fake (INV-8)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field

from app.integrations.llm import (
    LLMClient,
    LLMEvent,
    LLMRequest,
    LLMResponse,
    TextDelta,
    ToolUse,
    Usage,
)
from app.integrations.notifier import Alert, Notifier
from app.integrations.search import SearchClient, SearchResult


@dataclass
class FakeTurn:
    """One scripted assistant turn."""

    chunks: list[str] = field(default_factory=lambda: ["Fake research reply."])
    tool_uses: list[ToolUse] = field(default_factory=list)
    usage: Usage = field(default_factory=lambda: Usage(input_tokens=100, output_tokens=20))
    #: If set, the stream waits on this event before emitting chunk `block_before_chunk`.
    block_on: asyncio.Event | None = None
    block_before_chunk: int = 0


class FakeLLM:
    """Plays scripted turns in order (the last turn repeats) and records every request."""

    def __init__(self, script: Sequence[FakeTurn] | None = None, chunk_delay_ms: int = 0) -> None:
        self.script: list[FakeTurn] = list(script) if script else [FakeTurn()]
        self.chunk_delay_ms = chunk_delay_ms
        self.requests: list[LLMRequest] = []

    def _next_turn(self) -> FakeTurn:
        index = min(len(self.requests) - 1, len(self.script) - 1)
        return self.script[index]

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        self.requests.append(request)
        turn = self._next_turn()
        for i, chunk in enumerate(turn.chunks):
            if turn.block_on is not None and i == turn.block_before_chunk:
                await turn.block_on.wait()
            if self.chunk_delay_ms:
                await asyncio.sleep(self.chunk_delay_ms / 1000)
            yield TextDelta(text=chunk)
        yield LLMResponse(
            text="".join(turn.chunks),
            tool_uses=list(turn.tool_uses),
            usage=turn.usage,
            stop_reason="tool_use" if turn.tool_uses else "end_turn",
        )


class FakeSearch:
    """Returns fixed results and counts calls."""

    def __init__(self, results: Sequence[SearchResult] | None = None) -> None:
        self.results: list[SearchResult] = (
            list(results)
            if results is not None
            else [
                SearchResult(
                    title="Example result",
                    url="https://example.com/article",
                    content="An example search result used in fake mode.",
                )
            ]
        )
        self.calls: list[tuple[str, int]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        self.calls.append((query, max_results))
        return self.results[:max_results]


class FakeNotifier:
    """Collects alerts in an outbox."""

    def __init__(self) -> None:
        self.outbox: list[Alert] = []

    async def send_alert(self, alert: Alert) -> None:
        self.outbox.append(alert)


# Static protocol conformance, checked by `mypy --strict app`.
_llm: LLMClient = FakeLLM()
_search: SearchClient = FakeSearch()
_notifier: Notifier = FakeNotifier()
