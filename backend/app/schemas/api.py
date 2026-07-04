from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.job import JobStatus
from app.models.resume import ResumeStatus


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    jd_text: str = Field(min_length=1)


class ResumeRead(BaseModel):
    id: int
    original_filename: str
    status: ResumeStatus
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobRead(BaseModel):
    id: int
    title: str
    jd_text: str
    status: JobStatus
    error_message: str | None
    created_at: datetime
    resumes: list[ResumeRead] = Field(default_factory=list)
    progress: dict[str, int] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    uploaded: int
    resumes: list[ResumeRead]


class RunResponse(BaseModel):
    job_id: int
    status: JobStatus
    message: str


class ScoreRead(BaseModel):
    total_score: int
    level: str
    score_detail_json: dict
    matched_points_json: list[str]
    missing_points_json: list[str]
    interview_questions_json: list[str]
    invitation_message: str
    summary: str

    model_config = {"from_attributes": True}


class CandidateResult(BaseModel):
    id: int
    resume_id: int
    name: str
    email: str | None
    phone: str | None
    structured_json: dict
    score: ScoreRead

    model_config = {"from_attributes": True}


class AgentLogRead(BaseModel):
    id: int
    resume_id: int | None
    step: str
    message: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
