from __future__ import annotations

from pydantic import BaseModel, Field


class EducationItem(BaseModel):
    school: str = ""
    major: str = ""
    degree: str = ""
    start_year: str = ""
    end_year: str = ""


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)


class StructuredJD(BaseModel):
    position: str
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    experience_requirements: str = ""
    education_requirement: str = ""
    responsibilities: list[str] = Field(default_factory=list)


class StructuredCandidate(BaseModel):
    name: str = "Unknown Candidate"
    phone: str | None = None
    email: str | None = None
    education: list[EducationItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    work_experience: list[str] = Field(default_factory=list)
    summary: str = ""


class ScoreResult(BaseModel):
    skill_score: int = 0
    project_score: int = 0
    experience_score: int = 0
    education_score: int = 0
    bonus_score: int = 0
    risk_score: int = 0
    matched_points: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    interview_questions: list[str] = Field(default_factory=list)
    invitation_message: str = ""
    summary: str = ""
