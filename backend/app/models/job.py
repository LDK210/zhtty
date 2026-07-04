from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class JobStatus(str, enum.Enum):
    draft = "draft"
    ready = "ready"
    running = "running"
    completed = "completed"
    failed = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    jd_structured_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.draft, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    resumes = relationship("Resume", back_populates="job", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="job", cascade="all, delete-orphan")
    logs = relationship("AgentLog", back_populates="job", cascade="all, delete-orphan")
