"""Pydantic contracts for the talent candidate and application domain."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ApplicationStatus = Literal[
    "submitted",
    "in_review",
    "interviewing",
    "offered",
    "hired",
    "rejected",
    "withdrawn",
]


class TalentCandidateCreate(BaseModel):
    """Accept optional profile fields when creating a company-level candidate."""

    name: str | None = Field(default=None, max_length=255)
    primary_email: str | None = Field(default=None, max_length=255)
    primary_phone: str | None = Field(default=None, max_length=64)
    current_company: str | None = Field(default=None, max_length=255)
    current_title: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    profile_json: dict | None = None


class TalentCandidateUpdate(TalentCandidateCreate):
    """Provide mutable company-level candidate profile fields."""


class TalentCandidateRead(TalentCandidateCreate):
    """Expose a company-level candidate without legacy analysis fields."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeVersionCreate(BaseModel):
    """Accept the immutable metadata and extracted content for one resume version."""

    talent_candidate_id: int = Field(gt=0)
    version_number: int = Field(gt=0)
    original_filename: str = Field(min_length=1, max_length=255)
    stored_filename: str = Field(min_length=1, max_length=255)
    file_path: str = Field(min_length=1, max_length=500)
    file_hash: str | None = Field(default=None, max_length=128)
    raw_text: str | None = None
    parsed_profile_json: dict | None = None
    source_type: str = Field(min_length=1, max_length=64)


class ResumeVersionRead(BaseModel):
    """Expose resume metadata and parsed content without the internal storage path."""

    id: int
    talent_candidate_id: int
    version_number: int
    original_filename: str
    stored_filename: str
    file_hash: str | None
    raw_text: str | None
    parsed_profile_json: dict | None
    source_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationCreate(BaseModel):
    """Accept one candidate-to-job application relationship."""

    talent_candidate_id: int = Field(gt=0)
    job_id: int = Field(gt=0)
    resume_version_id: int = Field(gt=0)
    source_type: str = Field(min_length=1, max_length=64)
    source_detail: str | None = None
    status: ApplicationStatus = "submitted"
    current_stage: str | None = Field(default=None, max_length=64)


class ApplicationUpdate(BaseModel):
    """Allow controlled updates to the mutable application state fields."""

    source_detail: str | None = None
    status: ApplicationStatus | None = None
    current_stage: str | None = Field(default=None, max_length=64)


class ApplicationRead(ApplicationCreate):
    """Expose the persisted application relationship and current state."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
