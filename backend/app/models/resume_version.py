from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ResumeVersion(Base):
    """Store an immutable historical resume version for a talent candidate."""

    __tablename__ = "resume_versions"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "talent_candidate_id",
            name="uq_resume_versions_id_talent_candidate_id",
        ),
        UniqueConstraint(
            "talent_candidate_id",
            "version_number",
            name="uq_resume_versions_talent_candidate_id_version_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    talent_candidate_id: Mapped[int] = mapped_column(
        ForeignKey("talent_candidates.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    talent_candidate = relationship("TalentCandidate", back_populates="resume_versions")
    applications = relationship("Application", back_populates="resume_version", viewonly=True)
