"""Research CRUD and watch settings."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.clock import Clock
from app.errors import NotFound
from app.models import Message, Research, Run
from app.schemas.researches import (
    MessageOut,
    ResearchDetailOut,
    ResearchIn,
    ResearchSummaryOut,
    ResearchWatchIn,
)
from app.schemas.runs import ActiveRunOut

TITLE_MAX = 80
DEFAULT_SCHEDULE = "daily"


def _title(topic: str) -> str:
    return topic if len(topic) <= TITLE_MAX else topic[: TITLE_MAX - 1] + "…"


def ensure_exists(session: Session, research_id: int) -> None:
    if session.scalar(select(Research.id).where(Research.id == research_id)) is None:
        raise NotFound("Research not found")


def list_researches(session: Session) -> list[ResearchSummaryOut]:
    rows = session.scalars(
        select(Research).order_by(Research.last_activity_at.desc(), Research.id.desc())
    )
    return [ResearchSummaryOut.model_validate(r) for r in rows]


def create_research(session: Session, clock: Clock, data: ResearchIn) -> ResearchSummaryOut:
    now = clock.now()
    research = Research(
        title=_title(data.topic), topic=data.topic, created_at=now, last_activity_at=now
    )
    session.add(research)
    session.flush()
    session.add(Message(research_id=research.id, role="user", content=data.topic, created_at=now))
    session.commit()
    return ResearchSummaryOut.model_validate(research)


def get_research(session: Session, research_id: int) -> ResearchDetailOut:
    research = session.get(Research, research_id)
    if research is None:
        raise NotFound("Research not found")
    messages = session.scalars(
        select(Message)
        .where(Message.research_id == research_id)
        .order_by(Message.created_at, Message.id)
    )
    active = session.scalar(
        select(Run).where(Run.research_id == research_id, Run.status == "running")
    )
    summary = ResearchSummaryOut.model_validate(research)
    return ResearchDetailOut(
        **summary.model_dump(),
        topic=research.topic,
        created_at=research.created_at,
        last_run_at=research.last_run_at,
        watch_enabled_at=research.watch_enabled_at,
        messages=[MessageOut.model_validate(m) for m in messages],
        active_run=ActiveRunOut.model_validate(active) if active is not None else None,
    )


def mark_read(session: Session, research_id: int) -> None:
    updated = session.scalar(
        update(Research)
        .where(Research.id == research_id)
        .values(unread=False)
        .returning(Research.id)
    )
    if updated is None:
        raise NotFound("Research not found")
    session.commit()


def update_watch(
    session: Session, clock: Clock, research_id: int, patch: ResearchWatchIn
) -> ResearchSummaryOut:
    """M7-C2 rules.

    - Enabling with no schedule (given or stored) sets `daily`.
    - Enabling (false→true) or changing the schedule sets `watch_enabled_at = now`, so the
      first watch run happens in the next slot (INV-10).
    - Pausing only clears `watch_enabled`; the schedule is kept.
    """
    research = session.scalar(select(Research).where(Research.id == research_id).with_for_update())
    if research is None:
        raise NotFound("Research not found")
    now = clock.now()
    if patch.schedule is not None and patch.schedule != research.schedule:
        research.schedule = patch.schedule
        research.watch_enabled_at = now
    if patch.watch_enabled is True:
        if research.schedule is None:
            research.schedule = DEFAULT_SCHEDULE
        if not research.watch_enabled:
            research.watch_enabled_at = now
        research.watch_enabled = True
    elif patch.watch_enabled is False:
        research.watch_enabled = False
    session.commit()
    return ResearchSummaryOut.model_validate(research)


def delete_research(session: Session, research_id: int) -> None:
    """Messages, findings and runs go with it through ON DELETE CASCADE."""
    deleted = session.scalar(
        delete(Research).where(Research.id == research_id).returning(Research.id)
    )
    if deleted is None:
        raise NotFound("Research not found")
    session.commit()
