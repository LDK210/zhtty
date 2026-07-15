"""ORM-only AI analysis history with explicit business-write restrictions.

Business code must use ordinary SQLAlchemy ``Session.add`` or ``Session.add_all``
and commit through the ORM. Core insert/update and bulk ORM APIs bypass mapper
events and are prohibited for this model. Future services must centralize its
creation validation; direct SQL is limited to controlled migration or operations work.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, event, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship

from app.db.session import Base
from app.models.application import Application
from app.models.hiring_criteria_version import HiringCriteriaVersion


class AIAnalysisVersion(Base):
    """Store an immutable, versioned AI analysis for one application.

    Database foreign keys protect parent existence. Cross-table job and resume
    equality is enforced by the mapper event below until a future service layer
    centralizes the same rule.
    """

    __tablename__ = "ai_analysis_versions"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "version_number",
            name="uq_ai_analysis_versions_application_id_version_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    criteria_version_id: Mapped[int] = mapped_column(
        ForeignKey("hiring_criteria_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    resume_version_id: Mapped[int] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    recommendation_pool: Mapped[str] = mapped_column(String(64), nullable=False)
    job_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capability_evidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    model_provider: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    analysis_schema_version: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    analysis_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    application = relationship("Application")
    criteria_version = relationship("HiringCriteriaVersion")
    resume_version = relationship("ResumeVersion")


@event.listens_for(AIAnalysisVersion, "before_insert")
def validate_analysis_relationship_consistency(
    _: Mapper[AIAnalysisVersion], connection: Connection, target: AIAnalysisVersion
) -> None:
    """Reject analysis rows whose criteria or resume does not match the application."""
    application = connection.execute(
        select(Application.job_id, Application.resume_version_id).where(Application.id == target.application_id)
    ).one_or_none()
    criteria_job_id = connection.execute(
        select(HiringCriteriaVersion.job_id).where(HiringCriteriaVersion.id == target.criteria_version_id)
    ).scalar_one_or_none()

    if application is None or criteria_job_id is None:
        return
    if application.job_id != criteria_job_id:
        raise ValueError("AI analysis criteria version must belong to the application job.")
    if application.resume_version_id != target.resume_version_id:
        raise ValueError("AI analysis resume version must match the application resume version.")


@event.listens_for(AIAnalysisVersion, "before_update")
def prevent_ai_analysis_version_updates(
    _: Mapper[AIAnalysisVersion], __: Connection, ___: AIAnalysisVersion
) -> None:
    """Keep ORM-managed AI analysis versions immutable after creation."""
    raise ValueError("AI analysis versions are immutable.")
