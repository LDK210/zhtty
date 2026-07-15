"""ORM-only HR decision history with explicit business-write restrictions.

Business code must use ordinary SQLAlchemy ``Session.add`` or ``Session.add_all``.
Core insert/update and bulk ORM APIs bypass mapper events and are prohibited for
this audit model. Direct SQL is reserved for controlled migration or operations work.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, event, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship

from app.db.session import Base
from app.models.ai_analysis_version import AIAnalysisVersion


class HRDecision(Base):
    """Store an immutable human recruiting decision for one application."""

    __tablename__ = "hr_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    analysis_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ai_analysis_versions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    application = relationship("Application")
    analysis = relationship("AIAnalysisVersion")


@event.listens_for(HRDecision, "before_insert")
def validate_decision_analysis_application(
    _: Mapper[HRDecision], connection: Connection, target: HRDecision
) -> None:
    """Reject a decision that references analysis owned by another application."""
    if target.analysis_id is None:
        return
    analysis_application_id = connection.execute(
        select(AIAnalysisVersion.application_id).where(AIAnalysisVersion.id == target.analysis_id)
    ).scalar_one_or_none()
    if analysis_application_id is None:
        return
    if analysis_application_id != target.application_id:
        raise ValueError("HR decision analysis must belong to the same application.")


@event.listens_for(HRDecision, "before_update")
def prevent_hr_decision_updates(_: Mapper[HRDecision], __: Connection, ___: HRDecision) -> None:
    """Keep ORM-managed HR decision records immutable after creation."""
    raise ValueError("HR decisions are immutable.")
