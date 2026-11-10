"""Run reads. open_run / execute / start_background land with the engine in M8."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Run
from app.schemas.runs import RunOut
from app.services.researches import ensure_exists


def list_runs(session: Session, research_id: int) -> list[RunOut]:
    ensure_exists(session, research_id)
    rows = session.scalars(
        select(Run)
        .where(Run.research_id == research_id)
        .order_by(Run.started_at.desc(), Run.id.desc())
    )
    return [RunOut.model_validate(r) for r in rows]
