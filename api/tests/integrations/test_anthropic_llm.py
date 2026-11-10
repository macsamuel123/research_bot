from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
import respx

from app.config import Settings
from app.engine.budget import RunBudget
from app.integrations.anthropic_llm import AnthropicLLM
from app.integrations.fakes import FakeSearch
from app.integrations.llm import LLMEvent, LLMRequest, LLMResponse, TextDelta, ToolUse, Usage
from tests.helpers.httpx_bridge import RespxBridgeTransport

pytestmark = pytest.mark.criterion("M8-C10")

MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def _sse(events: list[dict[str, Any]]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _stream_body(model: str) -> bytes:
    return _sse(
        [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "model": model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 42, "output_tokens": 1},
                },
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Hello "},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "world"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "content_block_start",
                "index": 1,
                "content_block": {
                    "type": "tool_use",
                    "id": "tu_1",
                    "name": "web_search",
                    "input": {},
                },
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "input_json_delta", "partial_json": '{"query": "fus'},
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "input_json_delta", "partial_json": 'ion"}'},
            },
            {"type": "content_block_stop", "index": 1},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                "usage": {"output_tokens": 17},
            },
            {"type": "message_stop"},
        ]
    )


def test_request_uses_settings_model_and_max_tokens(settings: Settings) -> None:
    llm = AnthropicLLM(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
        transport=RespxBridgeTransport(),
    )
    budget = RunBudget(llm, FakeSearch(), settings)
    request = LLMRequest(
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=1,  # RunBudget must overwrite this with LLM_MAX_TOKENS
        tools=[{"name": "web_search", "description": "d", "input_schema": {"type": "object"}}],
    )

    async def go() -> list[LLMEvent]:
        return [event async for event in budget.stream(request)]

    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(MESSAGES_URL).mock(
            return_value=httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=_stream_body(settings.anthropic_model),
            )
        )
        events = asyncio.run(go())

    sent = route.calls.last.request
    body = json.loads(sent.content)
    assert body["model"] == settings.anthropic_model
    assert settings.anthropic_model in sent.content.decode()
    assert body["max_tokens"] == settings.llm_max_tokens
    assert body["stream"] is True
    assert body["system"] == "sys" and body["messages"] == request.messages
    assert body["tools"][0]["name"] == "web_search"
    # The configured key is sent (header name depends on the SDK version).
    key = settings.anthropic_api_key
    assert sent.headers.get("x-api-key") == key or sent.headers.get("authorization") == (
        f"Bearer {key}"
    )

    assert events[:2] == [TextDelta("Hello "), TextDelta("world")]
    final = events[-1]
    assert isinstance(final, LLMResponse)
    assert final.text == "Hello world"
    assert final.tool_uses == [ToolUse(id="tu_1", name="web_search", input={"query": "fusion"})]
    assert final.usage == Usage(input_tokens=42, output_tokens=17)
    assert final.stop_reason == "tool_use"
    assert (budget.input_tokens, budget.output_tokens) == (42, 17)


def test_anthropic_repr_hides_key(settings: Settings) -> None:
    llm = AnthropicLLM(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    assert settings.anthropic_api_key not in repr(llm)
