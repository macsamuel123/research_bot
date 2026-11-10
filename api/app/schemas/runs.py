from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UtcDatetime

RunStatus = Literal["running", "ok", "capped", "error"]
RunTrigger = Literal["chat", "watch", "telegram", "api", "digest"]


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: UtcDatetime
    finished_at: UtcDatetime | None
    status: RunStatus
    trigger: RunTrigger
    cost_cents: int
    new_findings: int


class ActiveRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Literal["running"]
    trigger: RunTrigger
    started_at: UtcDatetime
