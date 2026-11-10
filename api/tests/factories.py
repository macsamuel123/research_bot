"""Test-only row factories for router/read tests. They seed findings and runs directly to
set up fixed states; app code inserts them only through services.findings.save_finding and
services.runs.open_run (checked by tests/test_insert_paths.py)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.models import Finding, Message, Research, Run

T0 = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def make_research(
    db: Session, title: str = "Topic", *, at: datetime = T0, **fields: object
) -> Research:
    research = Research(title=title, topic=title, created_at=at, last_activity_at=at, **fields)
    db.add(research)
    db.commit()
    return research


def make_message(db: Session, research: Research, content: str = "hi") -> Message:
    msg = Message(research_id=research.id, role="user", content=content, created_at=T0)
    db.add(msg)
    db.commit()
    return msg


def make_finding(
    db: Session,
    research: Research,
    n: int,
    *,
    found_at: datetime = T0,
    dismissed: bool = False,
    run: Run | None = None,
) -> Finding:
    url = f"https://example{n}.com/item/{n}"
    title = f"Finding {n}"
    summary = f"Summary {n}"
    url_hash = _sha(url)
    content_hash = _sha(f"{title.lower()}\n{summary.lower()}")
    finding = Finding(
        research_id=research.id,
        run_id=run.id if run else None,
        title=title,
        url=url,
        summary=summary,
        source=urlsplit(url).hostname or "",
        found_at=found_at,
        url_hash=url_hash,
        content_hash=content_hash,
        dedupe_hash=_sha(url_hash + content_hash),
        dismissed=dismissed,
    )
    db.add(finding)
    db.commit()
    return finding


def make_run(
    db: Session,
    research: Research,
    *,
    started_at: datetime = T0,
    finished_at: datetime | None = None,
    status: str = "ok",
    trigger: str = "chat",
    cost_cents: int = 0,
    new_findings: int = 0,
) -> Run:
    run = Run(
        research_id=research.id,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        trigger=trigger,
        cost_cents=cost_cents,
        new_findings=new_findings,
    )
    db.add(run)
    db.commit()
    return run
