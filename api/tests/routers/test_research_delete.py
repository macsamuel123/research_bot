from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Finding, Message, Research, Run
from tests.factories import make_finding, make_message, make_research, make_run

pytestmark = pytest.mark.criterion("M7-C3")


def _counts(db: Session, research_id: int) -> tuple[int, ...]:
    db.expire_all()
    return tuple(
        db.scalar(select(func.count()).select_from(model).where(col == research_id)) or 0
        for model, col in (
            (Research, Research.id),
            (Message, Message.research_id),
            (Finding, Finding.research_id),
            (Run, Run.research_id),
        )
    )


def test_delete_removes_research_and_children(owner_client: TestClient, db: Session) -> None:
    r = make_research(db)
    other = make_research(db, "Other")
    for target in (r, other):
        make_message(db, target)
        run = make_run(db, target)
        make_finding(db, target, target.id, run=run)

    rid, other_id = r.id, other.id
    resp = owner_client.delete(f"/api/researches/{rid}")
    assert resp.status_code == 204
    assert resp.content == b""
    assert _counts(db, rid) == (0, 0, 0, 0)
    assert _counts(db, other_id) == (1, 1, 1, 1)

    assert owner_client.get(f"/api/researches/{rid}").status_code == 404
    assert owner_client.delete(f"/api/researches/{rid}").status_code == 404
    assert [x["id"] for x in owner_client.get("/api/researches").json()] == [other_id]


def test_delete_unknown_research_returns_404(owner_client: TestClient) -> None:
    assert owner_client.delete("/api/researches/999999").status_code == 404


def test_delete_requires_a_session(client: TestClient, db: Session) -> None:
    r = make_research(db)
    assert client.delete(f"/api/researches/{r.id}").status_code == 401
    assert _counts(db, r.id)[0] == 1
