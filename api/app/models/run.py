from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Run(Base):
    """Created only by services.runs.open_run() (INV-10, from M8)."""

    __tablename__ = "run"
    __table_args__ = (
        CheckConstraint(
            "trigger IN ('chat', 'watch', 'telegram', 'api', 'digest')", name="trigger"
        ),
        CheckConstraint("status IN ('running', 'ok', 'capped', 'error')", name="status"),
        UniqueConstraint("research_id", "scheduled_for"),
        Index(
            "run_one_running_per_research",
            "research_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    research_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("research.id", ondelete="CASCADE"), nullable=False
    )
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    search_calls: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    new_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
