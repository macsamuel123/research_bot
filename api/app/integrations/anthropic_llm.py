"""Anthropic adapter for LLMClient."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal, cast

import anthropic
import httpx2

from app.integrations.llm import LLMClient, LLMEvent, LLMRequest, LLMResponse, TextDelta, ToolUse
from app.integrations.llm import Usage as LLMUsage

#: Explicit so the SDK's ANTHROPIC_BASE_URL env lookup can never steer requests (INV-7).
ANTHROPIC_BASE_URL = "https://api.anthropic.com"

StopReason = Literal["end_turn", "tool_use", "max_tokens", "other"]


def _stop_reason(value: str | None) -> StopReason:
    if value == "end_turn":
        return "end_turn"
    if value == "tool_use":
        return "tool_use"
    if value == "max_tokens":
        return "max_tokens"
    return "other"


class AnthropicLLM:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._transport = transport
        self._client: anthropic.AsyncAnthropic | None = None

    def __repr__(self) -> str:  # never expose the key
        return f"AnthropicLLM(model={self.model!r})"

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key,
                base_url=ANTHROPIC_BASE_URL,
                http_client=httpx2.AsyncClient(transport=self._transport, timeout=120.0),
                max_retries=2,
            )
        return self._client

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": request.messages,
        }
        if request.tools:
            kwargs["tools"] = request.tools
        async with self._get_client().messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                if text:
                    yield TextDelta(text=text)
            final = await stream.get_final_message()
        texts: list[str] = []
        tool_uses: list[ToolUse] = []
        for block in final.content:
            if block.type == "text":
                texts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(
                    ToolUse(id=block.id, name=block.name, input=cast(object, block.input))
                )
        yield LLMResponse(
            text="".join(texts),
            tool_uses=tool_uses,
            usage=LLMUsage(
                input_tokens=final.usage.input_tokens, output_tokens=final.usage.output_tokens
            ),
            stop_reason=_stop_reason(final.stop_reason),
        )


_conforms: type[LLMClient] = AnthropicLLM
