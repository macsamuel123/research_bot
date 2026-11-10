"""Finding reads, dismissal and the single insert path, save_finding (INV-2, INV-3)."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.clock import Clock
from app.engine import dedupe
from app.errors import NotFound
from app.models import Finding
from app.schemas.findings import FindingIn, FindingOut
from app.services.researches import ensure_exists


@dataclass(frozen=True)
class Saved:
    finding: FindingOut


@dataclass(frozen=True)
class Duplicate:
    pass


@dataclass(frozen=True)
class Invalid:
    message: str


SaveResult = Saved | Duplicate | Invalid

NOT_FROM_SEARCH = "url was not returned by web_search in this run"


def _validation_message(exc: ValidationError) -> str:
    """Field names and messages only; never the input values."""
    parts = []
    for err in exc.errors(include_input=False, include_context=False, include_url=False):
        loc = ".".join(str(p) for p in err.get("loc", ())) or "input"
        msg = str(err.get("msg", "invalid")).removeprefix("Value error, ")
        parts.append(f"{loc}: {msg}")
    return "; ".join(parts)


def save_finding(
    session: Session,
    *,
    research_id: int,
    run_id: int,
    raw: Mapping[str, object],
    allowed_urls: Collection[str],
    clock: Clock,
) -> SaveResult:
    """Validate and insert one finding with ON CONFLICT DO NOTHING (never check-then-insert).

    `allowed_urls` are the normalized URLs web_search returned in this run.
    """
    try:
        data = FindingIn.model_validate(dict(raw))
    except ValidationError as exc:
        return Invalid(_validation_message(exc))
    if data.url not in allowed_urls:
        return Invalid(NOT_FROM_SEARCH)
    url_hash = dedupe.url_hash(data.url)
    content_hash = dedupe.content_hash(data.title, data.summary)
    stmt = (
        pg_insert(Finding)
        .values(
            research_id=research_id,
            run_id=run_id,
            title=data.title,
            url=data.url,
            summary=data.summary,
            source=urlsplit(data.url).hostname or "",
            found_at=clock.now(),
            url_hash=url_hash,
            content_hash=content_hash,
            dedupe_hash=dedupe.dedupe_hash(url_hash, content_hash),
        )
        .on_conflict_do_nothing()
        .returning(
            Finding.id,
            Finding.title,
            Finding.url,
            Finding.summary,
            Finding.source,
            Finding.found_at,
        )
    )
    row = session.execute(stmt).mappings().first()
    session.commit()
    if row is None:
        return Duplicate()
    return Saved(FindingOut.model_validate(dict(row)))


def list_findings(session: Session, research_id: int) -> list[FindingOut]:
    ensure_exists(session, research_id)
    rows = session.scalars(
        select(Finding)
        .where(Finding.research_id == research_id, Finding.dismissed.is_(False))
        .order_by(Finding.found_at.desc(), Finding.id.desc())
    )
    return [FindingOut.model_validate(f) for f in rows]


def stored_urls(session: Session, research_id: int, limit: int) -> list[str]:
    """URLs of every stored finding (dismissed included), newest first."""
    return list(
        session.scalars(
            select(Finding.url)
            .where(Finding.research_id == research_id)
            .order_by(Finding.found_at.desc(), Finding.id.desc())
            .limit(limit)
        )
    )


def dismiss_finding(session: Session, finding_id: int) -> None:
    """Idempotent: dismissing an already dismissed finding is still a success."""
    updated = session.scalar(
        update(Finding).where(Finding.id == finding_id).values(dismissed=True).returning(Finding.id)
    )
    if updated is None:
        raise NotFound("Finding not found")
    session.commit()
