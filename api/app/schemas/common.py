from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import PlainSerializer


def _utc_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


#: Timestamps are always serialized as UTC ISO-8601 with a trailing Z.
UtcDatetime = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str)]
