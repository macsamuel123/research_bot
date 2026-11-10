from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Identity, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Research(Base):
    __tablename__ = "research"
    __table_args__ = (
        CheckConstraint("schedule IN ('6h', 'daily', 'weekly')", name="schedule"),
        Index("ix_research_last_activity_at", "last_activity_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    watch_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    watch_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schedule: Mapped[str | None] = mapped_column(Text)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unread: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
