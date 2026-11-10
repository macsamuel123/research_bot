from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, field_validator

from app.engine.normalize import InvalidUrl, normalize_url
from app.schemas.common import UtcDatetime

URL_MAX_CHARS = 2048


class FindingIn(BaseModel):
    """Validated finding input (INV-2). `url` holds the normalized URL after validation."""

    model_config = ConfigDict(str_strip_whitespace=True, strict=True)

    title: str
    url: str
    summary: str

    @field_validator("title")
    @classmethod
    def _title_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("title must not be empty")
        return value

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        if not value:
            raise ValueError("url must not be empty")
        if len(value) > URL_MAX_CHARS:
            raise ValueError(f"url must be at most {URL_MAX_CHARS} characters")
        try:
            normalized = normalize_url(value)
            parts = urlsplit(normalized)
            host = parts.hostname
        except (InvalidUrl, ValueError):
            raise ValueError("url could not be parsed") from None
        if parts.scheme not in ("http", "https"):
            raise ValueError("url must use http or https")
        if not host:
            raise ValueError("url must have a host")
        return normalized


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: str
    summary: str
    source: str
    found_at: UtcDatetime
