from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ResumeStatus(str, enum.Enum):
    uploaded = "uploaded"
    extracting = "extracting"
    parsed = "parsed"
    scored = "scored"
    completed = "completed"
    failed = "failed"


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ResumeStatus] = mapped_column(Enum(ResumeStatus), default=ResumeStatus.uploaded, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    job = relationship("Job", back_populates="resumes")
    candidate = relationship("Candidate", back_populates="resume", cascade="all, delete-orphan", uselist=False)
    logs = relationship("AgentLog", back_populates="resume")
