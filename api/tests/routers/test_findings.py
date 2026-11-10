from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Finding
from tests.factories import T0, make_finding, make_research

pytestmark = pytest.mark.criterion("M7-C1")

FIELDS = {"id", "title", "url", "summary", "source", "found_at"}


def test_list_returns_non_dismissed_findings_newest_first(
    owner_client: TestClient, db: Session
) -> None:
    r = make_research(db)
    other = make_research(db, "Other")
    old = make_finding(db, r, 1, found_at=T0)
    new = make_finding(db, r, 2, found_at=T0 + timedelta(days=2))
    mid = make_finding(db, r, 3, found_at=T0 + timedelta(days=1))
    make_finding(db, r, 4, found_at=T0 + timedelta(days=3), dismissed=True)
    make_finding(db, other, 5, found_at=T0 + timedelta(days=4))

    resp = owner_client.get(f"/api/researches/{r.id}/findings")
    assert resp.status_code == 200
    body = resp.json()
    assert [f["id"] for f in body] == [new.id, mid.id, old.id]
    assert all(set(f) == FIELDS for f in body)
    assert body[0] == {
        "id": new.id,
        "title": "Finding 2",
        "url": "https://example2.com/item/2",
        "summary": "Summary 2",
        "source": "example2.com",
        "found_at": "2026-11-03T08:00:00Z",
    }


def test_dismiss_is_idempotent_and_hides_the_finding(owner_client: TestClient, db: Session) -> None:
    r = make_research(db)
    keep = make_finding(db, r, 1)
    gone = make_finding(db, r, 2)

    for _ in range(2):
        resp = owner_client.post(f"/api/findings/{gone.id}/dismiss")
        assert resp.status_code == 204
        assert resp.content == b""

    ids = [f["id"] for f in owner_client.get(f"/api/researches/{r.id}/findings").json()]
    assert ids == [keep.id]
    db.expire_all()
    assert db.scalar(select(Finding.dismissed).where(Finding.id == gone.id)) is True


def test_dismiss_unknown_finding_returns_404(owner_client: TestClient) -> None:
    resp = owner_client.post("/api/findings/999999/dismiss")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Finding not found"}


def test_findings_of_unknown_research_returns_404(owner_client: TestClient) -> None:
    assert owner_client.get("/api/researches/999999/findings").status_code == 404


def test_findings_routes_require_a_session(client: TestClient, db: Session) -> None:
    r = make_research(db)
    f = make_finding(db, r, 1)
    assert client.get(f"/api/researches/{r.id}/findings").status_code == 401
    assert client.post(f"/api/findings/{f.id}/dismiss").status_code == 401
    db.expire_all()
    assert db.scalar(select(Finding.dismissed).where(Finding.id == f.id)) is False
