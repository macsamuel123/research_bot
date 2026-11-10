"""LLM seam. The engine talks to Anthropic only through this protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class LLMRequest:
    system: str
    messages: list[dict[str, Any]]
    max_tokens: int
    tools: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolUse:
    id: str
    name: str
    #: Raw model-provided input. Usually a dict, but the engine validates it (never trusts it).
    input: object


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class LLMResponse:
    """Final event of a stream: the full assistant turn."""

    text: str
    tool_uses: list[ToolUse]
    usage: Usage
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "other"]


LLMEvent = TextDelta | LLMResponse


@runtime_checkable
class LLMClient(Protocol):
    def stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        """Yield TextDelta chunks, then exactly one LLMResponse."""
        ...
