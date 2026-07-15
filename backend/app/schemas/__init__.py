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

__all__ = [
    "ApplicationCreate",
    "ApplicationRead",
    "ApplicationUpdate",
    "ResumeVersionCreate",
    "ResumeVersionRead",
    "TalentCandidateCreate",
    "TalentCandidateRead",
    "TalentCandidateUpdate",
]
