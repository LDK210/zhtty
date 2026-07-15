"""Pydantic contracts for immutable HR decisions and pipeline audit events."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

HRDecisionType = Literal["advance", "hold", "reject", "talent_pool", "transfer_recommendation"]
PipelineStage = Literal[
    "new",
    "ai_screening",
    "hr_review",
    "interview_planning",
    "interviewing",
    "interview_review",
    "final_decision",
    "offer",
    "hired",
    "rejected",
    "candidate_withdrew",
    "job_closed",
    "talent_pool",
]
PipelineEventType = Literal[
    "stage_changed",
    "hr_decision_recorded",
    "application_created",
    "transfer_requested",
    "transfer_confirmed",
    "note_added",
]
PipelineActorType = Literal["hr", "hiring_manager", "interviewer", "admin", "ai", "system"]


class HRDecisionCreate(BaseModel):
    """Accept one immutable human recruiting decision."""

    application_id: int = Field(gt=0)
    analysis_id: int | None = Field(default=None, gt=0)
    decision: HRDecisionType
    reason_code: str | None = Field(default=None, max_length=128)
    comment: str | None = Field(default=None, max_length=2000)
    decided_by: str | None = Field(default=None, max_length=255)


class HRDecisionRead(HRDecisionCreate):
    """Expose a persisted HR decision with server-generated audit fields."""

    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineEventCreate(BaseModel):
    """Accept one immutable pipeline history entry without changing Application stage."""

    application_id: int = Field(gt=0)
    from_stage: PipelineStage | None = None
    to_stage: PipelineStage
    event_type: PipelineEventType
    actor_type: PipelineActorType
    actor_id: str | None = Field(default=None, max_length=255)
    reason_code: str | None = Field(default=None, max_length=128)
    comment: str | None = Field(default=None, max_length=2000)


class PipelineEventRead(PipelineEventCreate):
    """Expose a persisted pipeline event with server-generated audit fields."""

    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
