"""Runs: reads, open_run (the only run-creation path, INV-10) and execute.

start_background (asyncio tasks, sinks for SSE) lands in M9.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.clock import Clock
from app.config import Settings
from app.engine import cost
from app.engine.agent import TurnState, run_turn
from app.engine.budget import RunBudget
from app.errors import Conflict, NotFound
from app.integrations.llm import LLMClient
from app.integrations.search import SearchClient
from app.models import Message, Research, Run
from app.schemas.runs import RunOut, RunStatus, RunTrigger
from app.services.researches import ensure_exists
from app.services.sinks import RunSink

logger = logging.getLogger(__name__)

STOPPED_ON_ERROR = "(stopped: error)"
ERROR_EVENT_MESSAGE = "Research run failed"


@dataclass(frozen=True)
class RunDeps:
    session_factory: sessionmaker[Session]
    llm: LLMClient
    search: SearchClient
    settings: Settings
    clock: Clock


@dataclass(frozen=True)
class RunOutcome:
    run_id: int
    status: RunStatus
    cost_cents: int
    new_findings: int


def list_runs(session: Session, research_id: int) -> list[RunOut]:
    ensure_exists(session, research_id)
    rows = session.scalars(
        select(Run)
        .where(Run.research_id == research_id)
        .order_by(Run.started_at.desc(), Run.id.desc())
    )
    return [RunOut.model_validate(r) for r in rows]


def open_run(
    session: Session,
    research_id: int,
    trigger: RunTrigger,
    user_content: str | None = None,
    scheduled_for: datetime | None = None,
    *,
    clock: Clock,
) -> int:
    """Insert the `running` run row (and the user message, if any) in one transaction.

    Relies on DB uniqueness (`run_one_running_per_research`, (research_id, scheduled_for)):
    a conflict stores nothing and raises Conflict.
    """
    ensure_exists(session, research_id)
    now = clock.now()
    stmt = (
        pg_insert(Run)
        .values(
            research_id=research_id,
            trigger=trigger,
            scheduled_for=scheduled_for,
            status="running",
            started_at=now,
        )
        .on_conflict_do_nothing()
        .returning(Run.id)
    )
    try:
        run_id = session.scalar(stmt)
    except IntegrityError:
        session.rollback()
        ensure_exists(session, research_id)  # deleted since the check above → NotFound
        raise
    if run_id is None:
        session.rollback()
        raise Conflict("A run is already in progress for this research")
    if user_content is not None:
        session.add(
            Message(research_id=research_id, role="user", content=user_content, created_at=now)
        )
    session.execute(update(Research).where(Research.id == research_id).values(last_activity_at=now))
    session.commit()
    return run_id


def should_persist_assistant(has_user_message: bool, new_findings: int) -> bool:
    """Every user message gets an answer; runs without one add a message only when they found
    something (INV-3: a watch run with zero new findings adds no message)."""
    return has_user_message or new_findings > 0


def _finalize(
    deps: RunDeps,
    run_id: int,
    research_id: int,
    *,
    status: RunStatus,
    budget: RunBudget,
    new_findings: int,
    assistant_text: str | None,
) -> RunOutcome:
    now = deps.clock.now()
    cost_cents = cost.compute(
        budget.input_tokens,
        budget.output_tokens,
        budget.search_calls,
        cost.Prices.from_settings(deps.settings),
    )
    with deps.session_factory() as session:
        if assistant_text is not None:
            session.add(
                Message(
                    research_id=research_id,
                    role="assistant",
                    content=assistant_text,
                    created_at=now,
                )
            )
        session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                status=status,
                finished_at=now,
                input_tokens=budget.input_tokens,
                output_tokens=budget.output_tokens,
                search_calls=budget.search_calls,
                cost_cents=cost_cents,
                new_findings=new_findings,
            )
        )
        session.execute(
            update(Research)
            .where(Research.id == research_id)
            .values(last_run_at=now, last_activity_at=now)
        )
        session.commit()
    return RunOutcome(run_id, status, cost_cents, new_findings)


async def execute(
    run_id: int, sink: RunSink, *, deps: RunDeps, has_user_message: bool
) -> RunOutcome:
    """Run the agent turn for an opened run and finalize it (ok or error).

    `has_user_message` must say whether open_run stored a user message for this run; it is
    not inferred from the thread (a swept run can leave a trailing user message).
    """
    with deps.session_factory() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise NotFound("Run not found")
        research_id, trigger = run.research_id, run.trigger
    budget = RunBudget(deps.llm, deps.search, deps.settings)
    state = TurnState()
    try:
        await run_turn(
            research_id,
            run_id,
            trigger,
            sink,
            budget,
            deps=deps,
            state=state,
            has_user_message=has_user_message,
        )
    except BaseException as exc:
        logger.exception("run %s failed", run_id)
        text = None
        if should_persist_assistant(has_user_message, state.new_findings):
            text = f"{state.text}\n\n{STOPPED_ON_ERROR}" if state.text else STOPPED_ON_ERROR
        outcome = _finalize(
            deps,
            run_id,
            research_id,
            status="error",
            budget=budget,
            new_findings=state.new_findings,
            assistant_text=text,
        )
        sink.emit("error", {"message": ERROR_EVENT_MESSAGE})
        if not isinstance(exc, Exception):  # cancellation etc.: finalized, then propagate
            raise
        return outcome
    text = state.text if should_persist_assistant(has_user_message, state.new_findings) else None
    outcome = _finalize(
        deps,
        run_id,
        research_id,
        status="ok",
        budget=budget,
        new_findings=state.new_findings,
        assistant_text=text,
    )
    sink.emit(
        "done",
        {
            "run_id": run_id,
            "status": outcome.status,
            "cost_cents": outcome.cost_cents,
            "new_findings": outcome.new_findings,
        },
    )
    return outcome
