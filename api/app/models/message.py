from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Message(Base):
    __tablename__ = "message"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="role"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    research_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("research.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
