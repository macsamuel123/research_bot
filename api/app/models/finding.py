from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Finding(Base):
    """Inserted only by services.findings.save_finding() (INV-2, from M8)."""

    __tablename__ = "finding"
    __table_args__ = (
        CheckConstraint("url ~ '^https?://'", name="url_http"),
        UniqueConstraint("research_id", "dedupe_hash"),
        UniqueConstraint("research_id", "url_hash"),
        UniqueConstraint("research_id", "content_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    research_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("research.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("run.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    found_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    url_hash: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_hash: Mapped[str] = mapped_column(Text, nullable=False)
    dismissed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
