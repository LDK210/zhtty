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

__all__ = [
    "ApplicationCreate",
    "ApplicationRead",
    "ApplicationUpdate",
    "AIAnalysisVersionCreate",
    "AIAnalysisVersionRead",
    "HiringCriteriaVersionCreate",
    "HiringCriteriaVersionRead",
    "HiringCriteriaVersionUpdate",
    "ResumeVersionCreate",
    "ResumeVersionRead",
    "TalentCandidateCreate",
    "TalentCandidateRead",
    "TalentCandidateUpdate",
]
