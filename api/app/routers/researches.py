"""Owner research endpoints (session only, INV-4)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.deps import require_owner
from app.clock import Clock, get_clock
from app.db import get_session
from app.schemas.findings import FindingOut
from app.schemas.researches import (
    ResearchDetailOut,
    ResearchIn,
    ResearchSummaryOut,
    ResearchWatchIn,
)
from app.schemas.runs import RunOut
from app.services import findings as findings_service
from app.services import researches as service
from app.services import runs as runs_service

router = APIRouter(
    prefix="/api/researches", tags=["researches"], dependencies=[Depends(require_owner)]
)

DbSession = Annotated[Session, Depends(get_session)]
AppClock = Annotated[Clock, Depends(get_clock)]


@router.get("")
def list_researches(session: DbSession) -> list[ResearchSummaryOut]:
    return service.list_researches(session)


@router.post("", status_code=201)
def create_research(body: ResearchIn, session: DbSession, clock: AppClock) -> ResearchSummaryOut:
    return service.create_research(session, clock, body)


@router.get("/{research_id}")
def get_research(research_id: int, session: DbSession) -> ResearchDetailOut:
    return service.get_research(session, research_id)


@router.patch("/{research_id}")
def update_watch(
    research_id: int, body: ResearchWatchIn, session: DbSession, clock: AppClock
) -> ResearchSummaryOut:
    return service.update_watch(session, clock, research_id, body)


@router.delete("/{research_id}", status_code=204)
def delete_research(research_id: int, session: DbSession) -> Response:
    service.delete_research(session, research_id)
    return Response(status_code=204)


@router.post("/{research_id}/read", status_code=204)
def mark_read(research_id: int, session: DbSession) -> Response:
    service.mark_read(session, research_id)
    return Response(status_code=204)


@router.get("/{research_id}/findings")
def list_findings(research_id: int, session: DbSession) -> list[FindingOut]:
    return findings_service.list_findings(session, research_id)


@router.get("/{research_id}/runs")
def list_runs(research_id: int, session: DbSession) -> list[RunOut]:
    return runs_service.list_runs(session, research_id)
