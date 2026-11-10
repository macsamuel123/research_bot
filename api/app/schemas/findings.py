from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UtcDatetime


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: str
    summary: str
    source: str
    found_at: UtcDatetime
