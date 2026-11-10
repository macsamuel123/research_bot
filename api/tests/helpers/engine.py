"""Engine test helpers: a `deps` fixture (FakeLLM, FakeSearch, FakeClock, real Postgres)
and `run_once`, which opens a run and executes it to completion."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.clock import FakeClock
from app.config import Settings
from app.integrations.fakes import FakeLLM, FakeSearch, FakeTurn
from app.integrations.llm import ToolUse, Usage
from app.integrations.search import SearchResult
from app.models import Research
from app.schemas.runs import RunTrigger
from app.services.runs import RunDeps, RunOutcome, execute, open_run
from app.services.sinks import ListSink, RunSink


@pytest.fixture
def deps(settings: Settings, db_engine: Engine, clock: FakeClock) -> RunDeps:
    return RunDeps(
        session_factory=sessionmaker(bind=db_engine, expire_on_commit=False),
        llm=FakeLLM(),
        search=FakeSearch(),
        settings=settings,
        clock=clock,
    )


def with_fakes(
    deps: RunDeps, llm: FakeLLM | None = None, search: FakeSearch | None = None
) -> RunDeps:
    return RunDeps(
        session_factory=deps.session_factory,
        llm=llm if llm is not None else deps.llm,
        search=search if search is not None else deps.search,
        settings=deps.settings,
        clock=deps.clock,
    )


def run_once(
    deps: RunDeps,
    research: Research,
    trigger: RunTrigger = "chat",
    content: str | None = None,
    sink: RunSink | None = None,
) -> tuple[int, RunOutcome]:
    with deps.session_factory() as session:
        run_id = open_run(session, research.id, trigger, content, clock=deps.clock)
    outcome = asyncio.run(
        execute(
            run_id,
            sink if sink is not None else ListSink(),
            deps=deps,
            has_user_message=content is not None,
        )
    )
    return run_id, outcome


def search_result(n: int) -> SearchResult:
    return SearchResult(title=f"Result {n}", url=f"https://site{n}.example.com/a/{n}", content="c")


def search_then_save(
    *saves: dict[str, object], final_chunks: list[str] | None = None, query: str = "q"
) -> FakeLLM:
    """A FakeLLM that searches, then saves each finding (one per tool call), then answers."""
    turns = [
        FakeTurn(
            chunks=["Searching. "],
            tool_uses=[ToolUse(id="s1", name="web_search", input={"query": query})],
            usage=Usage(100, 10),
        )
    ]
    if saves:
        turns.append(
            FakeTurn(
                chunks=["Saving. "],
                tool_uses=[
                    ToolUse(id=f"f{i}", name="save_finding", input=dict(s))
                    for i, s in enumerate(saves)
                ],
                usage=Usage(200, 30),
            )
        )
    turns.append(FakeTurn(chunks=final_chunks or ["Done."], usage=Usage(300, 40)))
    return FakeLLM(turns)


def session_of(deps: RunDeps) -> Session:
    return deps.session_factory()
