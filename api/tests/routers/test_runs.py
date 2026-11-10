from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import T0, make_research, make_run

pytestmark = pytest.mark.criterion("M7-C4")

FIELDS = {"id", "started_at", "finished_at", "status", "trigger", "cost_cents", "new_findings"}


def test_runs_listed_newest_first_with_exact_fields(owner_client: TestClient, db: Session) -> None:
    r = make_research(db)
    other = make_research(db, "Other")
    first = make_run(db, r, started_at=T0, finished_at=T0 + timedelta(minutes=1), cost_cents=5)
    capped = make_run(
        db,
        r,
        started_at=T0 + timedelta(days=1),
        finished_at=T0 + timedelta(days=1, minutes=2),
        status="capped",
        trigger="watch",
        cost_cents=50,
        new_findings=2,
    )
    running = make_run(db, r, started_at=T0 + timedelta(days=2), status="running", trigger="api")
    make_run(db, other, started_at=T0 + timedelta(days=3))

    resp = owner_client.get(f"/api/researches/{r.id}/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert [x["id"] for x in body] == [running.id, capped.id, first.id]
    assert all(set(x) == FIELDS for x in body)
    assert body[0]["finished_at"] is None
    assert body[0]["status"] == "running"
    assert body[1] == {
        "id": capped.id,
        "started_at": "2026-11-02T08:00:00Z",
        "finished_at": "2026-11-02T08:02:00Z",
        "status": "capped",
        "trigger": "watch",
        "cost_cents": 50,
        "new_findings": 2,
    }
    assert all(type(x["cost_cents"]) is int for x in body)


def test_runs_of_unknown_research_returns_404(owner_client: TestClient) -> None:
    assert owner_client.get("/api/researches/999999/runs").status_code == 404


def test_runs_require_a_session(client: TestClient, db: Session) -> None:
    r = make_research(db)
    assert client.get(f"/api/researches/{r.id}/runs").status_code == 401
