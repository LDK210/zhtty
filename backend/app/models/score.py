from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False, unique=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(64), nullable=False)
    score_detail_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    matched_points_json: Mapped[list] = mapped_column(JSON, nullable=False)
    missing_points_json: Mapped[list] = mapped_column(JSON, nullable=False)
    interview_questions_json: Mapped[list] = mapped_column(JSON, nullable=False)
    invitation_message: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    candidate = relationship("Candidate", back_populates="score")
    job = relationship("Job", back_populates="scores")
