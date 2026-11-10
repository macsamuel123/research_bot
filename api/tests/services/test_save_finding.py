from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clock import FakeClock
from app.models import Finding
from app.services.findings import Invalid, Saved, save_finding
from app.services.runs import open_run
from tests.factories import make_research

pytestmark = pytest.mark.criterion("M8-C5")

OK_URL = "https://news.example.com/story?id=1"
LONG = "https://e.com/" + "a" * 2050


def _count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(Finding)) or 0)


@pytest.mark.parametrize(
    "raw",
    [
        {"title": "T", "summary": "S"},  # missing url
        {"title": "T", "url": "", "summary": "S"},
        {"title": "T", "url": "   ", "summary": "S"},
        {"title": "T", "url": "ftp://e.com/file", "summary": "S"},
        {"title": "T", "url": "javascript:alert(1)", "summary": "S"},
        {"title": "T", "url": "https:///path", "summary": "S"},
        {"title": "T", "url": "http://[::1", "summary": "S"},
        {"title": "T", "url": "http://a.com:99999/", "summary": "S"},
        {"title": "T", "url": LONG, "summary": "S"},
        {"title": "T", "url": "https://elsewhere.example.org/", "summary": "S"},  # not searched
        {"title": "   ", "url": OK_URL, "summary": "S"},  # empty title
        {"title": "T", "url": 5, "summary": "S"},
    ],
)
def test_invalid_urls_rejected(db: Session, clock: FakeClock, raw: dict[str, object]) -> None:
    r = make_research(db)
    run_id = open_run(db, r.id, "chat", clock=clock)
    allowed = {OK_URL, "ftp://e.com/file", "javascript:alert(1)", "https:///path", LONG}
    result = save_finding(
        db, research_id=r.id, run_id=run_id, raw=raw, allowed_urls=allowed, clock=clock
    )
    assert isinstance(result, Invalid)
    assert "alert" not in result.message and "elsewhere" not in result.message
    assert _count(db) == 0


def test_valid_finding_stored_normalized(db: Session, clock: FakeClock) -> None:
    r = make_research(db)
    run_id = open_run(db, r.id, "chat", clock=clock)
    raw = {
        "title": " Big news ",
        "url": "HTTPS://News.Example.com/story?utm_source=x&id=1#c",
        "summary": "It happened.",
    }
    result = save_finding(
        db, research_id=r.id, run_id=run_id, raw=raw, allowed_urls={OK_URL}, clock=clock
    )
    assert isinstance(result, Saved)
    row = db.get(Finding, result.finding.id)
    assert row is not None
    assert (row.url, row.source, row.run_id, row.title) == (
        OK_URL,
        "news.example.com",
        run_id,
        "Big news",
    )
    assert row.found_at == clock.now()
    assert result.finding.url == OK_URL
