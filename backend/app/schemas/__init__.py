"""Pydantic schema package."""
from app.schemas.talent import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
    ResumeVersionCreate,
    ResumeVersionRead,
    TalentCandidateCreate,
    TalentCandidateRead,
    TalentCandidateUpdate,
)
from app.schemas.versions import (
    AIAnalysisVersionCreate,
    AIAnalysisVersionRead,
    HiringCriteriaVersionCreate,
    HiringCriteriaVersionRead,
    HiringCriteriaVersionUpdate,
)
from app.schemas.audit import HRDecisionCreate, HRDecisionRead, PipelineEventCreate, PipelineEventRead

__all__ = [
    "ApplicationCreate",
    "ApplicationRead",
    "ApplicationUpdate",
    "AIAnalysisVersionCreate",
    "AIAnalysisVersionRead",
    "HiringCriteriaVersionCreate",
    "HiringCriteriaVersionRead",
    "HiringCriteriaVersionUpdate",
    "HRDecisionCreate",
    "HRDecisionRead",
    "PipelineEventCreate",
    "PipelineEventRead",
    "ResumeVersionCreate",
    "ResumeVersionRead",
    "TalentCandidateCreate",
    "TalentCandidateRead",
    "TalentCandidateUpdate",
]
