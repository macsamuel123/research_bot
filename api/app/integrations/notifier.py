"""Notification seam (Telegram in production)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class AlertFinding:
    title: str
    url: str


@dataclass(frozen=True)
class Alert:
    research_id: int
    research_title: str
    run_id: int
    new_findings: int
    findings: list[AlertFinding] = field(default_factory=list)


@runtime_checkable
class Notifier(Protocol):
    async def send_alert(self, alert: Alert) -> None: ...
