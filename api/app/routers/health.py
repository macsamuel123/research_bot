"""GET /health (R2): liveness plus a DB round-trip. Public (see PUBLIC_PATHS from M3)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text

from app.db import get_engine

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)

DbCheck = Callable[[], None]


def db_check(engine: Annotated[Engine, Depends(get_engine)]) -> DbCheck:
    def check() -> None:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    return check


@router.get("/health")
def health(check: Annotated[DbCheck, Depends(db_check)]) -> JSONResponse:
    try:
        check()
    except Exception as exc:  # noqa: BLE001 - any DB failure means degraded
        log.warning("health: db check failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "error"})
    return JSONResponse(status_code=200, content={"status": "ok", "db": "ok"})
