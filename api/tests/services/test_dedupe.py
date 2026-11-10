from __future__ import annotations

import threading

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.integrations.fakes import FakeSearch
from app.integrations.search import SearchResult
from app.models import Finding, Run
from app.services.findings import Duplicate, Saved, SaveResult, save_finding
from app.services.runs import RunDeps, open_run
from app.services.sinks import ListSink
from tests.factories import make_research
from tests.helpers.engine import run_once, search_then_save, with_fakes

pytestmark = pytest.mark.criterion("M8-C7")

U1 = "https://a.example.com/one"
U2 = "https://b.example.com/two"


def _count(db: Session) -> int:
    db.expire_all()
    return int(db.scalar(select(func.count()).select_from(Finding)) or 0)


def _save(db: Session, deps: RunDeps, rid: int, run_id: int, **raw: object) -> SaveResult:
    return save_finding(
        db, research_id=rid, run_id=run_id, raw=raw, allowed_urls={U1, U2}, clock=deps.clock
    )


def test_same_url_different_title_skipped(db: Session, deps: RunDeps) -> None:
    r = make_research(db)
    run_id = open_run(db, r.id, "chat", clock=deps.clock)
    assert isinstance(_save(db, deps, r.id, run_id, title="A", url=U1, summary="s"), Saved)
    dup = _save(db, deps, r.id, run_id, title="B", url=U1 + "?utm_source=x#f", summary="t")
    assert isinstance(dup, Duplicate)
    assert _count(db) == 1


def test_same_content_different_url_skipped(db: Session, deps: RunDeps) -> None:
    r = make_research(db)
    run_id = open_run(db, r.id, "chat", clock=deps.clock)
    assert isinstance(_save(db, deps, r.id, run_id, title="Same", url=U1, summary="Body"), Saved)
    dup = _save(db, deps, r.id, run_id, title="  SAME ", url=U2, summary="body\n")
    assert isinstance(dup, Duplicate)
    assert _count(db) == 1


def test_dedupe_is_per_research(db: Session, deps: RunDeps) -> None:
    r1, r2 = make_research(db, "one"), make_research(db, "two")
    run1 = open_run(db, r1.id, "chat", clock=deps.clock)
    run2 = open_run(db, r2.id, "chat", clock=deps.clock)
    assert isinstance(_save(db, deps, r1.id, run1, title="A", url=U1, summary="s"), Saved)
    assert isinstance(_save(db, deps, r2.id, run2, title="A", url=U1, summary="s"), Saved)


def test_concurrent_insert_one_row(db: Session, deps: RunDeps) -> None:
    r = make_research(db)
    run_id = open_run(db, r.id, "chat", clock=deps.clock)
    barrier = threading.Barrier(2)
    results: list[SaveResult] = []
    lock = threading.Lock()

    def attempt() -> None:
        with deps.session_factory() as session:
            barrier.wait()
            res = _save(session, deps, r.id, run_id, title="A", url=U1, summary="s")
        with lock:
            results.append(res)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(type(x).__name__ for x in results) == ["Duplicate", "Saved"]
    assert _count(db) == 1


def test_new_findings_counts_only_inserted(db: Session, deps: RunDeps) -> None:
    r = make_research(db)
    search = FakeSearch([SearchResult("1", U1, "c"), SearchResult("2", U2, "c")])
    llm = search_then_save(
        {"title": "One", "url": U1, "summary": "first"},
        {"title": "One again", "url": U1, "summary": "dup by url"},
        {"title": "Two", "url": U2, "summary": "second"},
    )
    sink = ListSink()
    run_id, outcome = run_once(with_fakes(deps, llm, search), r, "chat", "go", sink)
    assert outcome.new_findings == 2
    assert sink.names.count("finding") == 2
    assert sink.events[-1] == (
        "done",
        {"run_id": run_id, "status": "ok", "cost_cents": outcome.cost_cents, "new_findings": 2},
    )
    db.expire_all()
    run = db.get(Run, run_id)
    assert run is not None and run.new_findings == 2
    assert _count(db) == 2
