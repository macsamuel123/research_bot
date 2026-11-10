from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.cost import Prices, compute
from app.integrations.fakes import FakeLLM, FakeSearch, FakeTurn
from app.integrations.llm import LLMRequest, ToolUse
from app.integrations.search import SearchResult
from app.models import Finding, Message, Research, Run
from app.schemas.runs import RunTrigger
from app.services.runs import RunDeps, should_persist_assistant
from app.services.sinks import ListSink
from tests.factories import make_research
from tests.helpers.engine import run_once, search_then_save, with_fakes

URL = "https://site1.example.com/a/1"
FINDING = {"title": "Result one", "url": URL, "summary": "A thing happened."}


def _search() -> FakeSearch:
    return FakeSearch([SearchResult("Result one", URL, "content")])


def _messages(db: Session, research_id: int) -> list[tuple[str, str]]:
    db.expire_all()
    rows = db.scalars(
        select(Message)
        .where(Message.research_id == research_id)
        .order_by(Message.created_at, Message.id)
    )
    return [(m.role, m.content) for m in rows]


def _run(db: Session, run_id: int) -> Run:
    db.expire_all()
    run = db.get(Run, run_id)
    assert run is not None
    return run


def _fresh_research(db: Session) -> Research:
    """A research with no messages (so assertions see only what the run adds)."""
    return make_research(db)


@pytest.mark.criterion("M8-C2")
def test_execute_emits_token_finding_done_in_order(db: Session, deps: RunDeps) -> None:
    r = _fresh_research(db)
    llm = search_then_save(FINDING, final_chunks=["All ", "done."])
    sink = ListSink()
    run_id, outcome = run_once(with_fakes(deps, llm, _search()), r, "chat", "Find it", sink)
    assert sink.names == ["token", "token", "finding", "token", "token", "done"]
    assert [d["text"] for n, d in sink.events if n == "token"] == [
        "Searching. ",
        "Saving. ",
        "All ",
        "done.",
    ]
    finding = sink.events[2][1]
    assert set(finding) == {"id", "title", "url", "summary", "source", "found_at"}
    assert finding["url"] == URL and finding["source"] == "site1.example.com"
    assert finding["found_at"].endswith("Z")
    assert sink.events[-1] == (
        "done",
        {"run_id": run_id, "status": "ok", "cost_cents": outcome.cost_cents, "new_findings": 1},
    )


@pytest.mark.criterion("M8-C2")
def test_user_message_committed_before_llm_call(db: Session, deps: RunDeps) -> None:
    r = _fresh_research(db)
    seen: list[list[tuple[str, str]]] = []

    def check_db(_req: LLMRequest) -> None:
        with Session(db.get_bind()) as fresh:
            rows = fresh.scalars(select(Message).where(Message.research_id == r.id))
            seen.append([(m.role, m.content) for m in rows])

    llm = FakeLLM([FakeTurn(chunks=["ok"])], on_request=check_db)
    run_once(with_fakes(deps, llm), r, "chat", "Hello there")
    assert seen == [[("user", "Hello there")]]


@pytest.mark.criterion("M8-C2")
def test_assistant_message_persisted_before_done(db: Session, deps: RunDeps) -> None:
    r = _fresh_research(db)
    at_done: list[list[tuple[str, str]]] = []

    def on_event(name: str, _data: dict[str, Any]) -> None:
        if name == "done":
            with Session(db.get_bind()) as fresh:
                at_done.append(_messages(fresh, r.id))

    llm = FakeLLM([FakeTurn(chunks=["Full ", "answer."])])
    run_once(with_fakes(deps, llm), r, "chat", "Q", ListSink(on_event))
    assert at_done == [[("user", "Q"), ("assistant", "Full answer.")]]


@pytest.mark.criterion("M8-C2")
def test_multi_iteration_text_concatenated(db: Session, deps: RunDeps) -> None:
    r = _fresh_research(db)
    sink = ListSink()
    run_once(
        with_fakes(deps, search_then_save(FINDING, final_chunks=["x", "y"]), _search()),
        r,
        "chat",
        "Q",
        sink,
    )
    tokens = "".join(d["text"] for n, d in sink.events if n == "token")
    assert _messages(db, r.id)[-1] == ("assistant", tokens)
    assert tokens == "Searching. Saving. xy"


@pytest.mark.criterion("M8-C3")
def test_llm_error_marks_run_error_and_keeps_partial_text(
    db: Session, deps: RunDeps, caplog: pytest.LogCaptureFixture
) -> None:
    r = _fresh_research(db)
    secret_text = "boom-internal-detail-XYZ"
    llm = FakeLLM(
        [
            FakeTurn(
                chunks=[],
                tool_uses=[ToolUse(id="s", name="web_search", input={"query": "q"})],
            ),
            FakeTurn(
                chunks=[],
                tool_uses=[ToolUse(id="f", name="save_finding", input=dict(FINDING))],
            ),
            FakeTurn(chunks=["partial"], raise_after_chunks=RuntimeError(secret_text)),
        ]
    )
    sink = ListSink()
    run_id, outcome = run_once(with_fakes(deps, llm, _search()), r, "chat", "Q", sink)
    assert "done" not in sink.names
    assert sink.names[-1] == "error"
    assert sink.events[-1][1] == {"message": "Research run failed"}
    assert secret_text not in repr(sink.events)
    run = _run(db, run_id)
    assert run.status == "error" and run.finished_at == deps.clock.now()
    assert run.new_findings == 1 == outcome.new_findings
    assert run.search_calls == 1
    assert _messages(db, r.id) == [("user", "Q"), ("assistant", "partial\n\n(stopped: error)")]
    assert db.scalar(select(Finding.url).where(Finding.run_id == run_id)) == URL


@pytest.mark.criterion("M8-C3")
def test_llm_error_without_text_persists_stopped_marker(db: Session, deps: RunDeps) -> None:
    r = _fresh_research(db)
    llm = FakeLLM([FakeTurn(chunks=[], raise_after_chunks=RuntimeError("x"))])
    run_id, _ = run_once(with_fakes(deps, llm), r, "chat", "Q")
    assert _messages(db, r.id) == [("user", "Q"), ("assistant", "(stopped: error)")]
    assert _run(db, run_id).status == "error"


@pytest.mark.criterion("M8-C8")
def test_chat_run_finalized_ok_with_usage_and_cost(db: Session, deps: RunDeps) -> None:
    r = _fresh_research(db)
    search = _search()
    run_id, outcome = run_once(with_fakes(deps, search_then_save(FINDING), search), r, "chat", "Q")
    run = _run(db, run_id)
    assert run.status == "ok" and outcome.status == "ok"
    assert (run.input_tokens, run.output_tokens) == (100 + 200 + 300, 10 + 30 + 40)
    assert run.search_calls == search.call_count == 1
    expected = compute(600, 80, 1, Prices.from_settings(deps.settings))
    assert run.cost_cents == expected == outcome.cost_cents
    assert run.finished_at == deps.clock.now()
    db.refresh(r)
    assert r.last_run_at == deps.clock.now() and r.last_activity_at == deps.clock.now()


@pytest.mark.criterion("M8-C8")
@pytest.mark.parametrize("unread", [True, False])
def test_unread_unchanged(db: Session, deps: RunDeps, unread: bool) -> None:
    r = make_research(db, unread=unread)
    run_once(deps, r, "chat", "Q")
    db.refresh(r)
    assert r.unread is unread


# --- assistant-message rule (INV-3) -------------------------------------------------------


@pytest.mark.criterion("M8-C7")
def test_watch_run_zero_findings_adds_no_message(db: Session, deps: RunDeps) -> None:
    r = _fresh_research(db)
    sink = ListSink()
    run_id, outcome = run_once(with_fakes(deps, search_then_save()), r, "watch", None, sink)
    assert outcome.new_findings == 0 and _run(db, run_id).status == "ok"
    assert _messages(db, r.id) == []
    assert sink.names[-1] == "done"


@pytest.mark.criterion("M8-C7")
def test_watch_run_with_findings_adds_message(db: Session, deps: RunDeps) -> None:
    r = _fresh_research(db)
    run_once(with_fakes(deps, search_then_save(FINDING), _search()), r, "watch")
    assert _messages(db, r.id) == [("assistant", "Searching. Saving. Done.")]


@pytest.mark.criterion("M8-C7")
def test_watch_run_error_zero_findings_adds_no_message(db: Session, deps: RunDeps) -> None:
    r = _fresh_research(db)
    llm = FakeLLM([FakeTurn(chunks=["p"], raise_after_chunks=RuntimeError("x"))])
    run_id, _ = run_once(with_fakes(deps, llm), r, "watch")
    assert _messages(db, r.id) == []
    assert _run(db, run_id).status == "error"


@pytest.mark.criterion("M8-C2")
@pytest.mark.parametrize("trigger", ["telegram", "api"])
def test_telegram_and_api_run_with_user_message_zero_findings_gets_reply(
    db: Session, deps: RunDeps, trigger: RunTrigger
) -> None:
    r = _fresh_research(db)
    run_once(with_fakes(deps, search_then_save()), r, trigger, "Anything?")
    assert _messages(db, r.id) == [
        ("user", "Anything?"),
        ("assistant", "Searching. Done."),
    ]


@pytest.mark.criterion("M8-C3")
def test_api_run_with_user_message_error_gets_stopped_message(db: Session, deps: RunDeps) -> None:
    r = _fresh_research(db)
    llm = FakeLLM([FakeTurn(chunks=[], raise_after_chunks=RuntimeError("x"))])
    run_once(with_fakes(deps, llm), r, "api", "Q")
    assert _messages(db, r.id) == [("user", "Q"), ("assistant", "(stopped: error)")]


@pytest.mark.criterion("M8-C7")
@pytest.mark.parametrize(
    ("has_user", "found", "expected"),
    [(False, 0, False), (False, 1, True), (True, 0, True), (True, 1, True)],
)
def test_should_persist_assistant_table(has_user: bool, found: int, expected: bool) -> None:
    assert should_persist_assistant(has_user, found) is expected
