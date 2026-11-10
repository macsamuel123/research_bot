"""Event sinks for runs. Events: token, finding, done, error (see CLAUDE.md "SSE events")."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class RunSink(Protocol):
    def emit(self, event: str, data: dict[str, Any]) -> None: ...


class NullSink:
    """Discards every event (runs nobody is watching)."""

    def emit(self, event: str, data: dict[str, Any]) -> None:
        return None


class ListSink:
    """Collects events in order; `on_event` (if set) runs synchronously after each append."""

    def __init__(self, on_event: Callable[[str, dict[str, Any]], None] | None = None) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.on_event = on_event

    def emit(self, event: str, data: dict[str, Any]) -> None:
        self.events.append((event, data))
        if self.on_event is not None:
            self.on_event(event, data)

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.events]


_null: RunSink = NullSink()
_list: RunSink = ListSink()
