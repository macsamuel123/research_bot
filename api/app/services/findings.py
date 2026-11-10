"""Finding reads and dismissal. The insert path (save_finding) lands with the engine in M8."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.errors import NotFound
from app.models import Finding
from app.schemas.findings import FindingOut
from app.services.researches import ensure_exists


def list_findings(session: Session, research_id: int) -> list[FindingOut]:
    ensure_exists(session, research_id)
    rows = session.scalars(
        select(Finding)
        .where(Finding.research_id == research_id, Finding.dismissed.is_(False))
        .order_by(Finding.found_at.desc(), Finding.id.desc())
    )
    return [FindingOut.model_validate(f) for f in rows]


def dismiss_finding(session: Session, finding_id: int) -> None:
    """Idempotent: dismissing an already dismissed finding is still a success."""
    updated = session.scalar(
        update(Finding).where(Finding.id == finding_id).values(dismissed=True).returning(Finding.id)
    )
    if updated is None:
        raise NotFound("Finding not found")
    session.commit()
