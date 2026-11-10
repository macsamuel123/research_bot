"""Anthropic adapter for LLMClient. Implemented in M8."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.integrations.llm import LLMClient, LLMEvent, LLMRequest


class AnthropicLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.model = model

    def __repr__(self) -> str:  # never expose the key
        return f"AnthropicLLM(model={self.model!r})"

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        raise NotImplementedError("AnthropicLLM.stream is implemented in M8")
        yield  # pragma: no cover - makes this an async generator


_conforms: type[LLMClient] = AnthropicLLM
