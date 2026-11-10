from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.clock import FakeClock
from app.models import Research
from tests.factories import T0, make_research

pytestmark = pytest.mark.criterion("M7-C2")


def _reload(db: Session, research: Research) -> Research:
    db.expire_all()
    fresh = db.get(Research, research.id)
    assert fresh is not None
    return fresh


@pytest.mark.parametrize(
    "body",
    [
        {"schedule": "hourly"},
        {"schedule": ""},
        {"schedule": "DAILY"},
        {"schedule": 5},
        {"schedule": None},
        {"watch_enabled": True, "schedule": "monthly"},
        {"watch_enabled": "yes"},
        {"watch_enabled": None},
        {"title": "x"},
    ],
)
def test_invalid_patch_returns_422_and_changes_nothing(
    owner_client: TestClient, db: Session, body: dict[str, Any]
) -> None:
    r = make_research(db)
    resp = owner_client.patch(f"/api/researches/{r.id}", json=body)
    assert resp.status_code == 422
    fresh = _reload(db, r)
    assert (fresh.watch_enabled, fresh.schedule, fresh.watch_enabled_at) == (False, None, None)


@pytest.mark.parametrize("schedule", ["6h", "daily", "weekly"])
def test_each_preset_is_accepted(owner_client: TestClient, db: Session, schedule: str) -> None:
    r = make_research(db)
    resp = owner_client.patch(
        f"/api/researches/{r.id}", json={"watch_enabled": True, "schedule": schedule}
    )
    assert resp.status_code == 200
    assert resp.json()["schedule"] == schedule
    assert resp.json()["watch_enabled"] is True


def test_enable_without_schedule_sets_daily_and_watch_enabled_at(
    owner_client: TestClient, db: Session, clock: FakeClock
) -> None:
    r = make_research(db)
    resp = owner_client.patch(f"/api/researches/{r.id}", json={"watch_enabled": True})
    assert resp.status_code == 200
    assert resp.json() == {
        "id": r.id,
        "title": "Topic",
        "unread": False,
        "watch_enabled": True,
        "schedule": "daily",
        "last_activity_at": "2026-11-01T08:00:00Z",
    }
    fresh = _reload(db, r)
    assert fresh.watch_enabled_at == clock.now()


def test_enable_keeps_a_stored_schedule(
    owner_client: TestClient, db: Session, clock: FakeClock
) -> None:
    r = make_research(db, schedule="weekly", watch_enabled_at=T0)
    resp = owner_client.patch(f"/api/researches/{r.id}", json={"watch_enabled": True})
    assert resp.json()["schedule"] == "weekly"
    assert _reload(db, r).watch_enabled_at == clock.now()


def test_changing_schedule_moves_watch_enabled_at(
    owner_client: TestClient, db: Session, clock: FakeClock
) -> None:
    r = make_research(db)
    owner_client.patch(f"/api/researches/{r.id}", json={"watch_enabled": True})
    enabled_at = clock.now()

    clock.advance(timedelta(hours=3))
    resp = owner_client.patch(f"/api/researches/{r.id}", json={"schedule": "weekly"})
    assert resp.status_code == 200
    assert resp.json()["schedule"] == "weekly"
    fresh = _reload(db, r)
    assert fresh.watch_enabled_at == clock.now() != enabled_at
    assert fresh.watch_enabled is True


def test_resending_the_same_schedule_does_not_move_watch_enabled_at(
    owner_client: TestClient, db: Session, clock: FakeClock
) -> None:
    r = make_research(db)
    owner_client.patch(f"/api/researches/{r.id}", json={"watch_enabled": True, "schedule": "6h"})
    enabled_at = clock.now()
    clock.advance(timedelta(hours=1))
    owner_client.patch(f"/api/researches/{r.id}", json={"watch_enabled": True, "schedule": "6h"})
    assert _reload(db, r).watch_enabled_at == enabled_at


def test_pause_keeps_schedule_and_watch_enabled_at(
    owner_client: TestClient, db: Session, clock: FakeClock
) -> None:
    r = make_research(db)
    owner_client.patch(f"/api/researches/{r.id}", json={"watch_enabled": True, "schedule": "6h"})
    enabled_at = clock.now()
    clock.advance(timedelta(hours=1))

    resp = owner_client.patch(f"/api/researches/{r.id}", json={"watch_enabled": False})
    assert resp.status_code == 200
    assert resp.json()["watch_enabled"] is False
    assert resp.json()["schedule"] == "6h"
    fresh = _reload(db, r)
    assert fresh.watch_enabled_at == enabled_at

    # Re-enabling after a pause starts a fresh slot window.
    clock.advance(timedelta(hours=1))
    resp = owner_client.patch(f"/api/researches/{r.id}", json={"watch_enabled": True})
    assert resp.json()["schedule"] == "6h"
    assert _reload(db, r).watch_enabled_at == clock.now()


def test_list_reflects_the_watch_change(owner_client: TestClient, db: Session) -> None:
    r = make_research(db)
    owner_client.patch(f"/api/researches/{r.id}", json={"watch_enabled": True})
    [item] = owner_client.get("/api/researches").json()
    assert item["watch_enabled"] is True
    assert item["schedule"] == "daily"


def test_patch_unknown_research_returns_404(owner_client: TestClient) -> None:
    resp = owner_client.patch("/api/researches/999999", json={"watch_enabled": True})
    assert resp.status_code == 404


def test_patch_requires_a_session_before_validation(client: TestClient, db: Session) -> None:
    r = make_research(db)
    assert client.patch(f"/api/researches/{r.id}", json={"schedule": "bad"}).status_code == 401
    assert client.patch("/api/researches/999999", json={"watch_enabled": True}).status_code == 401
