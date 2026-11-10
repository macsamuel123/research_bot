from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=1024)


class MeOut(BaseModel):
    owner: bool
