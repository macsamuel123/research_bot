from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.integrations.fakes import FakeLLM, FakeSearch, FakeTurn
from app.integrations.llm import ToolUse
from app.integrations.search import SearchResult
from app.models import Finding
from app.services.runs import RunDeps
from app.services.sinks import ListSink
from tests.factories import make_research
from tests.helpers.engine import run_once, with_fakes

pytestmark = pytest.mark.criterion("M8-C5")

URL = "https://site.example.com/a"


def _count(db: Session) -> int:
    db.expire_all()
    return int(db.scalar(select(func.count()).select_from(Finding)) or 0)


def _llm(*tool_uses: ToolUse) -> FakeLLM:
    return FakeLLM(
        [
            FakeTurn(chunks=[], tool_uses=[ToolUse("s", "web_search", {"query": "q"})]),
            FakeTurn(chunks=[], tool_uses=list(tool_uses)),
            FakeTurn(chunks=["end"]),
        ]
    )


def _tool_results(llm: FakeLLM, request_index: int = 2) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = llm.requests[request_index].messages[-1]["content"]
    return results


def _search(*urls: str) -> FakeSearch:
    return FakeSearch([SearchResult(f"t{i}", u, "c") for i, u in enumerate(urls)])


def test_save_finding_error_is_tool_error_result(db: Session, deps: RunDeps) -> None:
    r = make_research(db)
    bad = {"title": "T", "url": "https://not-searched.example.org/", "summary": "S"}
    llm = _llm(ToolUse("f", "save_finding", bad))
    sink = ListSink()
    run_id, outcome = run_once(with_fakes(deps, llm, _search(URL)), r, "chat", "Q", sink)
    [result] = _tool_results(llm)
    assert result["is_error"] is True and "web_search" in result["content"]
    assert _count(db) == 0 and outcome.new_findings == 0
    assert "finding" not in sink.names and outcome.status == "ok"


def test_valid_finding_inserted_with_source_and_run_id(db: Session, deps: RunDeps) -> None:
    r = make_research(db)
    good = {"title": "T", "url": URL + "?utm_source=feed", "summary": "S"}
    llm = _llm(ToolUse("f", "save_finding", good))
    run_id, outcome = run_once(with_fakes(deps, llm, _search(URL)), r, "chat", "Q")
    [result] = _tool_results(llm)
    assert result["is_error"] is False
    row = db.scalar(select(Finding))
    assert row is not None
    assert (row.url, row.source, row.run_id, row.research_id) == (
        URL,
        "site.example.com",
        run_id,
        r.id,
    )
    assert outcome.new_findings == 1


@pytest.mark.parametrize(
    "tool_input",
    [
        "str",
        [1],
        {},
        {"title": "T", "url": 5, "summary": "S"},
        {"title": "T", "url": URL},
        {"title": None, "url": URL, "summary": "S"},
    ],
)
def test_non_dict_or_missing_field_input_is_tool_error(
    db: Session, deps: RunDeps, tool_input: object
) -> None:
    r = make_research(db)
    llm = _llm(ToolUse("f", "save_finding", tool_input))
    run_once(with_fakes(deps, llm, _search(URL)), r, "chat", "Q")
    [result] = _tool_results(llm)
    assert result["is_error"] is True and result["tool_use_id"] == "f"
    assert _count(db) == 0


@pytest.mark.parametrize("tool_input", [{}, {"query": ""}, {"query": "   "}, {"query": 3}, "q"])
def test_web_search_bad_query_is_tool_error(db: Session, deps: RunDeps, tool_input: object) -> None:
    r = make_research(db)
    search = _search(URL)
    llm = FakeLLM(
        [FakeTurn(chunks=[], tool_uses=[ToolUse("s", "web_search", tool_input)]), FakeTurn()]
    )
    run_once(with_fakes(deps, llm, search), r, "chat", "Q")
    [result] = _tool_results(llm, 1)
    assert result["is_error"] is True
    assert search.call_count == 0


def test_unparseable_search_url_is_skipped(db: Session, deps: RunDeps) -> None:
    r = make_research(db)
    bad = "http://[::1"
    llm = _llm(
        ToolUse("f1", "save_finding", {"title": "A", "url": bad, "summary": "S"}),
        ToolUse("f2", "save_finding", {"title": "B", "url": URL, "summary": "S2"}),
    )
    run_once(with_fakes(deps, llm, _search(bad, URL)), r, "chat", "Q")
    search_result = llm.requests[1].messages[-1]["content"][0]
    assert bad not in search_result["content"] and URL in search_result["content"]
    r1, r2 = _tool_results(llm)
    assert r1["is_error"] is True and r2["is_error"] is False
    assert _count(db) == 1


def test_search_exception_is_tool_error(db: Session, deps: RunDeps) -> None:
    class Failing(FakeSearch):
        async def search(self, query: str, max_results: int) -> list[SearchResult]:
            raise RuntimeError("provider down")

    r = make_research(db)
    llm = FakeLLM(
        [FakeTurn(chunks=[], tool_uses=[ToolUse("s", "web_search", {"query": "q"})]), FakeTurn()]
    )
    _, outcome = run_once(with_fakes(deps, llm, Failing()), r, "chat", "Q")
    [result] = _tool_results(llm, 1)
    assert result["is_error"] is True and "provider down" not in result["content"]
    assert outcome.status == "ok"


def test_unknown_tool_is_tool_error(db: Session, deps: RunDeps) -> None:
    r = make_research(db)
    llm = FakeLLM([FakeTurn(chunks=[], tool_uses=[ToolUse("x", "rm_rf", {})]), FakeTurn()])
    run_once(with_fakes(deps, llm), r, "chat", "Q")
    [result] = _tool_results(llm, 1)
    assert result["is_error"] is True and "unknown tool" in result["content"]
