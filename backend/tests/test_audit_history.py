"""Database and schema tests for immutable HR and pipeline audit history."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    AIAnalysisVersion,
    Application,
    HiringCriteriaVersion,
    HRDecision,
    Job,
    JobStatus,
    PipelineEvent,
    ResumeVersion,
    TalentCandidate,
)
from app.schemas.audit import HRDecisionCreate, PipelineEventCreate


def _alembic_config(database_url: str) -> Config:
    """Build an Alembic configuration for a pytest-managed SQLite database."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def _create_job(title: str) -> Job:
    """Build a minimally valid Job for audit history tests."""
    return Job(title=title, jd_text="A valid job description.", status=JobStatus.draft)


def _create_resume(candidate_id: int, version_number: int) -> ResumeVersion:
    """Build a minimally valid ResumeVersion for one candidate."""
    return ResumeVersion(
        talent_candidate_id=candidate_id,
        version_number=version_number,
        original_filename=f"resume-{version_number}.pdf",
        stored_filename=f"stored-{version_number}.pdf",
        file_path=f"/private/resume-{version_number}.pdf",
        source_type="upload",
    )


def _create_analysis(
    application_id: int, criteria_id: int, resume_id: int, version_number: int
) -> AIAnalysisVersion:
    """Build a valid analysis record without invoking a model provider."""
    return AIAnalysisVersion(
        application_id=application_id,
        criteria_version_id=criteria_id,
        resume_version_id=resume_id,
        version_number=version_number,
        analysis_stage="resume_screening",
        recommendation_pool="main_recommendation",
        analysis_json={},
    )


def _create_audit_context(
    db: Session,
) -> Tuple[Application, Application, AIAnalysisVersion, AIAnalysisVersion]:
    """Persist two applications and their application-owned analysis records."""
    candidate = TalentCandidate(name="Audit Candidate")
    first_job = _create_job("First Job")
    second_job = _create_job("Second Job")
    db.add_all((candidate, first_job, second_job))
    db.commit()

    first_resume = _create_resume(candidate.id, 1)
    second_resume = _create_resume(candidate.id, 2)
    first_criteria = HiringCriteriaVersion(
        job_id=first_job.id,
        version_number=1,
        status="draft",
        source_jd_text=first_job.jd_text,
        criteria_json={},
    )
    second_criteria = HiringCriteriaVersion(
        job_id=second_job.id,
        version_number=1,
        status="draft",
        source_jd_text=second_job.jd_text,
        criteria_json={},
    )
    db.add_all((first_resume, second_resume, first_criteria, second_criteria))
    db.commit()

    first_application = Application(
        talent_candidate_id=candidate.id,
        job_id=first_job.id,
        resume_version_id=first_resume.id,
        source_type="career_site",
        status="submitted",
    )
    second_application = Application(
        talent_candidate_id=candidate.id,
        job_id=second_job.id,
        resume_version_id=second_resume.id,
        source_type="referral",
        status="submitted",
    )
    db.add_all((first_application, second_application))
    db.commit()

    first_analysis = _create_analysis(
        first_application.id, first_criteria.id, first_resume.id, version_number=1
    )
    second_analysis = _create_analysis(
        second_application.id, second_criteria.id, second_resume.id, version_number=1
    )
    db.add_all((first_analysis, second_analysis))
    db.commit()
    return first_application, second_application, first_analysis, second_analysis


def _create_pipeline_event(application_id: int, from_stage: str | None = None) -> PipelineEvent:
    """Build one valid pipeline event without changing Application.current_stage."""
    return PipelineEvent(
        application_id=application_id,
        from_stage=from_stage,
        to_stage="hr_review",
        event_type="stage_changed",
        actor_type="hr",
        actor_id="hr-1",
        reason_code="normal_progression",
        comment="Moved to review.",
    )


def test_hr_decisions_accept_multiple_and_matching_optional_analysis() -> None:
    """Allow multiple decisions per application with and without its own analysis."""
    db = SessionLocal()
    try:
        application, _, analysis, _ = _create_audit_context(db)
        db.add_all(
            (
                HRDecision(application_id=application.id, analysis_id=None, decision="hold"),
                HRDecision(application_id=application.id, analysis_id=analysis.id, decision="advance"),
            )
        )
        db.commit()
        assert db.query(HRDecision).filter(HRDecision.application_id == application.id).count() == 2
    finally:
        db.close()


def test_hr_decision_rejects_other_application_analysis_and_session_recovers() -> None:
    """Reject cross-application analysis and reuse the same Session after rollback."""
    db = SessionLocal()
    try:
        application, _, analysis, other_analysis = _create_audit_context(db)
        db.add(HRDecision(application_id=application.id, analysis_id=other_analysis.id, decision="reject"))
        with pytest.raises(ValueError, match="same application"):
            db.commit()
        db.rollback()
        assert db.query(HRDecision).count() == 0

        db.add(HRDecision(application_id=application.id, analysis_id=analysis.id, decision="advance"))
        db.commit()
        assert db.query(HRDecision).count() == 1
    finally:
        db.close()


def test_hr_decision_schema_and_orm_immutability() -> None:
    """Reject invalid decisions and every persisted HR decision business-field update."""
    with pytest.raises(ValueError):
        HRDecisionCreate(application_id=1, decision="invalid")

    db = SessionLocal()
    try:
        application, other_application, analysis, other_analysis = _create_audit_context(db)
        decision = HRDecision(
            application_id=application.id,
            analysis_id=analysis.id,
            decision="advance",
            reason_code="strong_match",
            comment="Advance the candidate.",
            decided_by="hr-1",
        )
        db.add(decision)
        db.commit()
        decision_id = decision.id
        expected_values = {
            "application_id": application.id,
            "analysis_id": analysis.id,
            "decision": "advance",
            "reason_code": "strong_match",
            "comment": "Advance the candidate.",
            "decided_by": "hr-1",
        }
        replacements = {
            "application_id": other_application.id,
            "analysis_id": other_analysis.id,
            "decision": "reject",
            "reason_code": "changed",
            "comment": "Changed.",
            "decided_by": "hr-2",
        }
        for field_name, replacement in replacements.items():
            persisted = db.get(HRDecision, decision_id)
            setattr(persisted, field_name, replacement)
            with pytest.raises(ValueError, match="immutable"):
                db.commit()
            db.rollback()
            assert getattr(db.get(HRDecision, decision_id), field_name) == expected_values[field_name]
    finally:
        db.close()


def test_hr_decision_add_all_is_atomic_when_any_analysis_is_invalid() -> None:
    """Prevent partial HR decision writes when add_all includes a mismatched analysis."""
    db = SessionLocal()
    try:
        application, _, analysis, other_analysis = _create_audit_context(db)
        db.add_all(
            (
                HRDecision(application_id=application.id, analysis_id=analysis.id, decision="advance"),
                HRDecision(application_id=application.id, analysis_id=other_analysis.id, decision="reject"),
            )
        )
        with pytest.raises(ValueError, match="same application"):
            db.commit()
        db.rollback()
        assert db.query(HRDecision).count() == 0
    finally:
        db.close()


def test_pipeline_events_append_and_schema_validation() -> None:
    """Allow initial and later pipeline events while validating every literal contract."""
    db = SessionLocal()
    try:
        application, _, _, _ = _create_audit_context(db)
        db.add_all(
            (
                _create_pipeline_event(application.id, from_stage=None),
                _create_pipeline_event(application.id, from_stage="ai_screening"),
            )
        )
        db.commit()
        assert db.query(PipelineEvent).filter(PipelineEvent.application_id == application.id).count() == 2
    finally:
        db.close()

    payload = {
        "application_id": 1,
        "to_stage": "hr_review",
        "event_type": "stage_changed",
        "actor_type": "hr",
    }
    for field_name, invalid_value in (
        ("to_stage", "invalid"),
        ("event_type", "invalid"),
        ("actor_type", "invalid"),
    ):
        invalid_payload = dict(payload)
        invalid_payload[field_name] = invalid_value
        with pytest.raises(ValueError):
            PipelineEventCreate(**invalid_payload)


def test_pipeline_event_orm_immutability() -> None:
    """Reject every persisted pipeline event business-field update."""
    db = SessionLocal()
    try:
        application, other_application, _, _ = _create_audit_context(db)
        event = _create_pipeline_event(application.id, from_stage="ai_screening")
        db.add(event)
        db.commit()
        event_id = event.id
        expected_values = {
            "application_id": application.id,
            "from_stage": "ai_screening",
            "to_stage": "hr_review",
            "event_type": "stage_changed",
            "actor_type": "hr",
            "actor_id": "hr-1",
            "reason_code": "normal_progression",
            "comment": "Moved to review.",
        }
        replacements = {
            "application_id": other_application.id,
            "from_stage": None,
            "to_stage": "final_decision",
            "event_type": "note_added",
            "actor_type": "admin",
            "actor_id": "admin-1",
            "reason_code": "changed",
            "comment": "Changed.",
        }
        for field_name, replacement in replacements.items():
            persisted = db.get(PipelineEvent, event_id)
            setattr(persisted, field_name, replacement)
            with pytest.raises(ValueError, match="immutable"):
                db.commit()
            db.rollback()
            assert getattr(db.get(PipelineEvent, event_id), field_name) == expected_values[field_name]
    finally:
        db.close()


def test_application_deletion_is_restricted_by_audit_history() -> None:
    """Prevent deleting an application while decision and pipeline history exists."""
    db = SessionLocal()
    try:
        application, _, analysis, _ = _create_audit_context(db)
        db.add_all(
            (
                HRDecision(application_id=application.id, analysis_id=analysis.id, decision="advance"),
                _create_pipeline_event(application.id),
            )
        )
        db.commit()
        db.delete(application)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.query(HRDecision).count() == 1
        assert db.query(PipelineEvent).count() == 1
    finally:
        db.close()


def test_downgrade_to_0003_preserves_existing_tables_and_data(tmp_path: Path) -> None:
    """Drop only V2-3A-3 tables while retaining revision 0003 schema and data."""
    database_url = f"sqlite:///{(tmp_path / 'downgrade-0004.db').as_posix()}"
    config = _alembic_config(database_url)
    command.upgrade(config, "0003_add_criteria_and_ai_analysis_versions")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO jobs (title, jd_text, jd_structured_json, status, "
                    "error_message, created_at, updated_at) VALUES "
                    "('Preserved job', 'Preserved JD', NULL, 'draft', NULL, "
                    "'2026-07-16 00:00:00', '2026-07-16 00:00:00')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    command.downgrade(config, "0003_add_criteria_and_ai_analysis_versions")

    verified_engine = create_engine(database_url)
    try:
        table_names = set(inspect(verified_engine).get_table_names())
        assert {
            "jobs",
            "resumes",
            "candidates",
            "scores",
            "agent_logs",
            "talent_candidates",
            "resume_versions",
            "applications",
            "hiring_criteria_versions",
            "ai_analysis_versions",
        } <= table_names
        assert not {"hr_decisions", "pipeline_events"} & table_names
        with verified_engine.connect() as connection:
            assert connection.execute(text("SELECT title FROM jobs")).scalar_one() == "Preserved job"
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
                "0003_add_criteria_and_ai_analysis_versions"
            )
    finally:
        verified_engine.dispose()
