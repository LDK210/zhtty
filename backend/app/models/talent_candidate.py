from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class TalentCandidate(Base):
    """Represent a company-level candidate independent of legacy resume analysis."""

    __tablename__ = "talent_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    current_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    resume_versions = relationship("ResumeVersion", back_populates="talent_candidate")
    applications = relationship("Application", back_populates="talent_candidate")
