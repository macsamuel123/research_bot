"""POST /api/findings/{id}/dismiss (session only, INV-4)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.deps import require_owner
from app.db import get_session
from app.services import findings as service

router = APIRouter(prefix="/api/findings", tags=["findings"], dependencies=[Depends(require_owner)])


@router.post("/{finding_id}/dismiss", status_code=204)
def dismiss_finding(finding_id: int, session: Annotated[Session, Depends(get_session)]) -> Response:
    service.dismiss_finding(session, finding_id)
    return Response(status_code=204)
