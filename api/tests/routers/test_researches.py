"""Research create/list/detail/read used by the shell and the M7 full-stack journey."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import make_research, make_run


def test_create_then_detail_and_list(owner_client: TestClient) -> None:
    resp = owner_client.post("/api/researches", json={"topic": "  EU AI Act  "})
    assert resp.status_code == 201
    created = resp.json()
    assert created["title"] == "EU AI Act"
    assert created["watch_enabled"] is False and created["schedule"] is None

    detail = owner_client.get(f"/api/researches/{created['id']}").json()
    assert detail["topic"] == "EU AI Act"
    assert [m["role"] for m in detail["messages"]] == ["user"]
    assert detail["active_run"] is None
    assert [x["id"] for x in owner_client.get("/api/researches").json()] == [created["id"]]


def test_blank_topic_is_422(owner_client: TestClient) -> None:
    assert owner_client.post("/api/researches", json={"topic": "   "}).status_code == 422


def test_long_topic_title_is_truncated(owner_client: TestClient) -> None:
    title = owner_client.post("/api/researches", json={"topic": "x" * 200}).json()["title"]
    assert len(title) == 80 and title.endswith("…")


def test_detail_exposes_active_run(owner_client: TestClient, db: Session) -> None:
    r = make_research(db)
    run = make_run(db, r, status="running")
    active = owner_client.get(f"/api/researches/{r.id}").json()["active_run"]
    assert active["id"] == run.id and active["status"] == "running"


def test_mark_read(owner_client: TestClient, db: Session) -> None:
    r = make_research(db, unread=True)
    assert owner_client.post(f"/api/researches/{r.id}/read").status_code == 204
    assert owner_client.get(f"/api/researches/{r.id}").json()["unread"] is False
    assert owner_client.post("/api/researches/999999/read").status_code == 404
