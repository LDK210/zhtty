"""ORM-only pipeline audit history with explicit business-write restrictions.

Business code must use ordinary SQLAlchemy ``Session.add`` or ``Session.add_all``.
Core insert/update and bulk ORM APIs bypass mapper events and are prohibited for
this audit model. Direct SQL is reserved for controlled migration or operations work.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship

from app.db.session import Base


class PipelineEvent(Base):
    """Store one immutable, append-only recruiting pipeline event."""

    __tablename__ = "pipeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    from_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    application = relationship("Application")


@event.listens_for(PipelineEvent, "before_update")
def prevent_pipeline_event_updates(_: Mapper[PipelineEvent], __: Connection, ___: PipelineEvent) -> None:
    """Keep ORM-managed pipeline event records immutable after creation."""
    raise ValueError("Pipeline events are immutable.")
