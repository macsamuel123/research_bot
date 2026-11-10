from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.integrations.fakes import FakeLLM, FakeTurn
from app.models import Message
from app.services.runs import RunDeps
from tests.factories import make_finding, make_research
from tests.helpers.engine import run_once, search_then_save, with_fakes

pytestmark = pytest.mark.criterion("M8-C4")


def test_follow_up_sends_history_and_stored_urls(db: Session, deps: RunDeps) -> None:
    r = make_research(db, "Solid-state batteries")
    llm = FakeLLM([FakeTurn(chunks=["First answer."])])
    d = with_fakes(deps, llm)
    run_once(d, r, "chat", "Solid-state batteries")
    stored = make_finding(db, r, 7)
    dismissed = make_finding(db, r, 8, dismissed=True)

    run_once(d, r, "chat", "Any news on yields?")
    follow_up = llm.requests[-1]
    assert follow_up.messages == [
        {"role": "user", "content": "Solid-state batteries"},
        {"role": "assistant", "content": "First answer."},
        {"role": "user", "content": "Any news on yields?"},
    ]
    assert stored.url in follow_up.system and dismissed.url in follow_up.system
    assert "Solid-state batteries" in follow_up.system
    assert {t["name"] for t in follow_up.tools} == {"web_search", "save_finding"}
    assert follow_up.max_tokens == deps.settings.llm_max_tokens


def test_watch_run_appends_topic_prompt_even_after_stale_user_message(
    db: Session, deps: RunDeps
) -> None:
    r = make_research(db, "Fusion")
    db.add(
        Message(research_id=r.id, role="user", content="orphan question", created_at=r.created_at)
    )
    db.commit()
    llm = FakeLLM([FakeTurn(chunks=["x"])])
    run_once(with_fakes(deps, llm), r, "watch")
    msgs = llm.requests[0].messages
    assert msgs[0] == {"role": "user", "content": "orphan question"}
    assert msgs[-1]["role"] == "user" and "Fusion" in msgs[-1]["content"]
    assert len(msgs) == 2


def test_tool_loop_sends_tool_results_back(db: Session, deps: RunDeps) -> None:
    r = make_research(db)
    llm = search_then_save()
    run_once(with_fakes(deps, llm), r, "chat", "Q")
    second = llm.requests[1].messages
    assert second[-2]["role"] == "assistant"
    assert second[-2]["content"][1]["type"] == "tool_use"
    result = second[-1]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "s1"
    assert result["is_error"] is False and "https://example.com/article" in result["content"]
