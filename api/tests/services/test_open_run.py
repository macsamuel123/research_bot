from __future__ import annotations

import threading

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clock import FakeClock
from app.errors import Conflict, NotFound
from app.models import Message, Run
from app.services.runs import RunDeps, open_run
from tests.factories import make_research

pytestmark = pytest.mark.criterion("M8-C1")


def _counts(db: Session) -> tuple[int, int]:
    db.expire_all()
    runs = db.scalar(select(func.count()).select_from(Run))
    msgs = db.scalar(select(func.count()).select_from(Message))
    return int(runs or 0), int(msgs or 0)


def test_open_run_inserts_running_run_and_user_message(db: Session, clock: FakeClock) -> None:
    r = make_research(db)
    run_id = open_run(db, r.id, "chat", "What is new?", clock=clock)
    run = db.get(Run, run_id)
    assert run is not None
    assert (run.status, run.trigger, run.research_id) == ("running", "chat", r.id)
    assert run.started_at == clock.now() and run.finished_at is None
    msgs = db.scalars(select(Message).where(Message.research_id == r.id)).all()
    assert [(m.role, m.content) for m in msgs] == [("user", "What is new?")]
    db.refresh(r)
    assert r.last_activity_at == clock.now()


def test_open_run_without_user_content(db: Session, clock: FakeClock) -> None:
    r = make_research(db)
    run_id = open_run(db, r.id, "watch", scheduled_for=clock.now(), clock=clock)
    run = db.get(Run, run_id)
    assert run is not None and run.status == "running" and run.scheduled_for == clock.now()
    assert _counts(db) == (1, 0)


def test_open_run_conflict_stores_nothing(db: Session, clock: FakeClock) -> None:
    r = make_research(db)
    open_run(db, r.id, "chat", "first", clock=clock)
    before = _counts(db)
    with pytest.raises(Conflict):
        open_run(db, r.id, "chat", "second", clock=clock)
    assert _counts(db) == before == (1, 1)


def test_open_run_unknown_research_is_not_found(db: Session, clock: FakeClock) -> None:
    with pytest.raises(NotFound):
        open_run(db, 999, "chat", "x", clock=clock)


def test_concurrent_open_run_one_conflict(deps: RunDeps, db: Session) -> None:
    r = make_research(db)
    barrier = threading.Barrier(2)
    results: list[object] = []
    lock = threading.Lock()

    def attempt(n: int) -> None:
        with deps.session_factory() as session:
            barrier.wait()
            try:
                out: object = open_run(session, r.id, "chat", f"msg {n}", clock=deps.clock)
            except Conflict as exc:
                out = exc
        with lock:
            results.append(out)

    threads = [threading.Thread(target=attempt, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(isinstance(x, int) for x in results) == 1
    assert sum(isinstance(x, Conflict) for x in results) == 1
    assert _counts(db) == (1, 1)
