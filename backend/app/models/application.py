from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Application(Base):
    """Represent one talent candidate's application to one job."""

    __tablename__ = "applications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["resume_version_id", "talent_candidate_id"],
            ["resume_versions.id", "resume_versions.talent_candidate_id"],
            name="fk_applications_resume_version_talent_candidate",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "talent_candidate_id",
            "job_id",
            name="uq_applications_talent_candidate_id_job_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    talent_candidate_id: Mapped[int] = mapped_column(
        ForeignKey("talent_candidates.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    resume_version_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="submitted", nullable=False)
    current_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    talent_candidate = relationship("TalentCandidate", back_populates="applications")
    job = relationship("Job")
    resume_version = relationship("ResumeVersion", back_populates="applications", viewonly=True)
