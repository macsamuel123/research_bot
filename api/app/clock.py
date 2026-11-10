"""Injectable time source. Services, the engine, the worker and auth never call datetime.now()."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from fastapi import Request


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock:
    """A manually advanced clock for tests."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start if start is not None else datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
        if self._now.tzinfo is None:
            raise ValueError("FakeClock needs an aware datetime")

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta

    def set(self, value: datetime) -> None:
        self._now = value


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock
