from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from app.schemas.common import UtcDatetime
from app.schemas.runs import ActiveRunOut

Schedule = Literal["6h", "daily", "weekly"]


class ResearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(max_length=4000)

    @field_validator("topic")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("topic must not be blank")
        return value


class ResearchWatchIn(BaseModel):
    """PATCH body. Omitted fields are left alone; explicit nulls are rejected."""

    model_config = ConfigDict(extra="forbid")

    watch_enabled: StrictBool | None = None
    schedule: Schedule | None = None

    @model_validator(mode="before")
    @classmethod
    def _no_explicit_null(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("watch_enabled", "schedule"):
                if key in data and data[key] is None:
                    raise ValueError(f"{key} must not be null")
        return data


class ResearchSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    unread: bool
    watch_enabled: bool
    schedule: Schedule | None
    last_activity_at: UtcDatetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: UtcDatetime


class ResearchDetailOut(ResearchSummaryOut):
    topic: str
    created_at: UtcDatetime
    last_run_at: UtcDatetime | None
    watch_enabled_at: UtcDatetime | None
    messages: list[MessageOut]
    active_run: ActiveRunOut | None
