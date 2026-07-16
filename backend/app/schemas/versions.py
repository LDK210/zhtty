"""Pydantic contracts for hiring criteria and AI analysis version history."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

HiringCriteriaStatus = Literal["draft", "active", "archived"]
AnalysisStage = Literal[
    "resume_screening",
    "hr_review",
    "technical_interview",
    "manager_interview",
    "final_review",
]
RecommendationPool = Literal[
    "main_recommendation",
    "exceptional_recommendation",
    "needs_review",
    "not_qualified",
]


class HiringCriteriaVersionCreate(BaseModel):
    """Accept one job-specific draft or historical criteria version."""

    job_id: int = Field(gt=0)
    version_number: int = Field(gt=0)
    status: HiringCriteriaStatus = "draft"
    source_jd_text: str = Field(min_length=1)
    criteria_json: dict
    created_by: str | None = Field(default=None, max_length=255)
    confirmed_by: str | None = Field(default=None, max_length=255)
    activated_at: datetime | None = None


class HiringCriteriaVersionUpdate(BaseModel):
    """Allow future services to amend mutable criteria metadata explicitly."""

    status: HiringCriteriaStatus | None = None
    source_jd_text: str | None = Field(default=None, min_length=1)
    criteria_json: dict | None = None
    confirmed_by: str | None = Field(default=None, max_length=255)
    activated_at: datetime | None = None


class HiringCriteriaVersionRead(HiringCriteriaVersionCreate):
    """Expose a persisted hiring criteria version with server-generated timestamps."""

    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class HiringCriteriaDraftCreate(BaseModel):
    """Accept client-controlled fields for creating a criteria draft only."""

    model_config = ConfigDict(extra="forbid")

    source_jd_text: str | None = Field(default=None, min_length=1, max_length=50_000)
    criteria_json: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = Field(default=None, max_length=255)


class HiringCriteriaDraftUpdate(BaseModel):
    """Accept one or more mutable fields of an existing criteria draft."""

    model_config = ConfigDict(extra="forbid")

    source_jd_text: str | None = Field(default=None, min_length=1, max_length=50_000)
    criteria_json: dict[str, Any] | None = None
    created_by: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def require_one_update(self) -> "HiringCriteriaDraftUpdate":
        """Reject empty PATCH bodies before opening a database transaction."""
        if not self.model_fields_set:
            raise ValueError("At least one mutable field must be provided.")
        return self


class HiringCriteriaDraftRead(BaseModel):
    """Expose the persisted current criteria draft without mutable server fields."""

    id: int
    job_id: int
    version_number: int
    status: HiringCriteriaStatus
    source_jd_text: str
    criteria_json: dict[str, Any]
    created_by: str | None
    confirmed_by: str | None
    created_at: datetime
    activated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AIAnalysisVersionCreate(BaseModel):
    """Accept a structured AI analysis snapshot without invoking an AI workflow."""

    application_id: int = Field(gt=0)
    criteria_version_id: int = Field(gt=0)
    resume_version_id: int = Field(gt=0)
    version_number: int = Field(gt=0)
    analysis_stage: AnalysisStage
    recommendation_pool: RecommendationPool
    job_match_score: float | None = Field(default=None, ge=0, le=100)
    capability_evidence_score: float | None = Field(default=None, ge=0, le=100)
    confidence_score: float | None = Field(default=None, ge=0, le=100)
    model_provider: str | None = Field(default=None, max_length=128)
    model_name: str | None = Field(default=None, max_length=128)
    model_version: str | None = Field(default=None, max_length=128)
    prompt_version: str | None = Field(default=None, max_length=128)
    analysis_schema_version: str | None = Field(default=None, max_length=128)
    analysis_json: dict


class AIAnalysisVersionRead(AIAnalysisVersionCreate):
    """Expose a persisted AI analysis version with a read-only creation timestamp."""

    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
