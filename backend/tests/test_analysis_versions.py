"""Database and schema tests for criteria and AI analysis version history."""

from __future__ import annotations

from pathlib import Path

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
    Job,
    JobStatus,
    ResumeVersion,
    TalentCandidate,
)
from app.schemas.versions import AIAnalysisVersionCreate, HiringCriteriaVersionCreate


def _alembic_config(database_url: str) -> Config:
    """Build an Alembic configuration that targets a temporary SQLite database."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def _create_job(title: str) -> Job:
    """Build a minimally valid Job for historical version tests."""
    return Job(title=title, jd_text="A valid job description.", status=JobStatus.draft)


def _create_resume_version(candidate_id: int, version_number: int) -> ResumeVersion:
    """Build a minimally valid ResumeVersion for one persisted candidate."""
    return ResumeVersion(
        talent_candidate_id=candidate_id,
        version_number=version_number,
        original_filename=f"resume-{version_number}.pdf",
        stored_filename=f"stored-{version_number}.pdf",
        file_path=f"/private/resume-{version_number}.pdf",
        source_type="upload",
    )


def _create_analysis(
    application_id: int,
    criteria_version_id: int,
    resume_version_id: int,
    version_number: int,
) -> AIAnalysisVersion:
    """Build a valid structured AI analysis snapshot without running an LLM."""
    return AIAnalysisVersion(
        application_id=application_id,
        criteria_version_id=criteria_version_id,
        resume_version_id=resume_version_id,
        version_number=version_number,
        analysis_stage="resume_screening",
        recommendation_pool="main_recommendation",
        job_match_score=88.0,
        capability_evidence_score=90.0,
        confidence_score=85.0,
        analysis_json={"summary": "Deterministic test analysis."},
    )


def _create_analysis_context(
    db: Session,
) -> tuple[Application, HiringCriteriaVersion, HiringCriteriaVersion, ResumeVersion, ResumeVersion]:
    """Persist an application plus matching and mismatching analysis dependencies."""
    candidate = TalentCandidate(name="Test Candidate")
    first_job = _create_job("First Job")
    second_job = _create_job("Second Job")
    db.add_all((candidate, first_job, second_job))
    db.commit()

    first_resume = _create_resume_version(candidate.id, 1)
    second_resume = _create_resume_version(candidate.id, 2)
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

    application = Application(
        talent_candidate_id=candidate.id,
        job_id=first_job.id,
        resume_version_id=first_resume.id,
        source_type="career_site",
        status="submitted",
    )
    db.add(application)
    db.commit()
    return application, first_criteria, second_criteria, first_resume, second_resume


def test_criteria_versions_are_unique_per_job_and_schema_rejects_invalid_status() -> None:
    """Allow historical criteria versions while rejecting duplicate numbers and invalid status."""
    db = SessionLocal()
    try:
        job = _create_job("Backend Engineer")
        db.add(job)
        db.commit()
        db.add_all(
            (
                HiringCriteriaVersion(
                    job_id=job.id,
                    version_number=1,
                    status="draft",
                    source_jd_text=job.jd_text,
                    criteria_json={"skills": ["Python"]},
                ),
                HiringCriteriaVersion(
                    job_id=job.id,
                    version_number=2,
                    status="active",
                    source_jd_text=job.jd_text,
                    criteria_json={"skills": ["Python", "FastAPI"]},
                ),
            )
        )
        db.commit()
        assert db.query(HiringCriteriaVersion).filter(HiringCriteriaVersion.job_id == job.id).count() == 2

        db.add(
            HiringCriteriaVersion(
                job_id=job.id,
                version_number=2,
                status="draft",
                source_jd_text=job.jd_text,
                criteria_json={},
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()

    with pytest.raises(ValueError):
        HiringCriteriaVersionCreate(
            job_id=1,
            version_number=1,
            status="invalid",
            source_jd_text="JD",
            criteria_json={},
        )


def test_analysis_versions_are_unique_and_schema_validates_input_domains() -> None:
    """Persist multiple analysis versions and validate schema literals and score ranges."""
    db = SessionLocal()
    try:
        candidate = TalentCandidate(name="Ada")
        job = _create_job("Backend Engineer")
        db.add_all((candidate, job))
        db.commit()
        resume = _create_resume_version(candidate.id, 1)
        criteria = HiringCriteriaVersion(
            job_id=job.id,
            version_number=1,
            status="draft",
            source_jd_text=job.jd_text,
            criteria_json={},
        )
        db.add_all((resume, criteria))
        db.commit()
        application = Application(
            talent_candidate_id=candidate.id,
            job_id=job.id,
            resume_version_id=resume.id,
            source_type="career_site",
            status="submitted",
        )
        db.add(application)
        db.commit()

        db.add_all(
            (
                _create_analysis(application.id, criteria.id, resume.id, 1),
                _create_analysis(application.id, criteria.id, resume.id, 2),
            )
        )
        db.commit()
        assert db.query(AIAnalysisVersion).filter(AIAnalysisVersion.application_id == application.id).count() == 2

        db.add(_create_analysis(application.id, criteria.id, resume.id, 2))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()

    base_payload = {
        "application_id": 1,
        "criteria_version_id": 1,
        "resume_version_id": 1,
        "version_number": 1,
        "analysis_stage": "resume_screening",
        "recommendation_pool": "main_recommendation",
        "analysis_json": {},
    }
    for field_name, invalid_value in (
        ("job_match_score", -0.1),
        ("capability_evidence_score", 100.1),
        ("recommendation_pool", "invalid"),
        ("analysis_stage", "invalid"),
    ):
        payload = dict(base_payload)
        payload[field_name] = invalid_value
        with pytest.raises(ValueError):
            AIAnalysisVersionCreate(**payload)


def test_analysis_rejects_cross_job_criteria_and_cross_application_resume() -> None:
    """Validate analysis references against the persisted application relationship."""
    db = SessionLocal()
    try:
        candidate = TalentCandidate(name="Grace")
        first_job = _create_job("First Job")
        second_job = _create_job("Second Job")
        db.add_all((candidate, first_job, second_job))
        db.commit()
        first_resume = _create_resume_version(candidate.id, 1)
        second_resume = _create_resume_version(candidate.id, 2)
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
        application = Application(
            talent_candidate_id=candidate.id,
            job_id=first_job.id,
            resume_version_id=first_resume.id,
            source_type="career_site",
            status="submitted",
        )
        db.add(application)
        db.commit()

        db.add(_create_analysis(application.id, second_criteria.id, first_resume.id, 1))
        with pytest.raises(ValueError, match="criteria version"):
            db.commit()
        db.rollback()

        db.add(_create_analysis(application.id, first_criteria.id, second_resume.id, 1))
        with pytest.raises(ValueError, match="resume version"):
            db.commit()
        db.rollback()
        assert db.query(AIAnalysisVersion).count() == 0
    finally:
        db.close()


def test_pending_analysis_uses_final_values_and_leaves_no_record() -> None:
    """Validate the final pending state rather than values present when ``add`` ran."""
    db = SessionLocal()
    try:
        application, criteria, other_criteria, resume, _ = _create_analysis_context(db)
        analysis = _create_analysis(application.id, criteria.id, resume.id, 1)
        db.add(analysis)
        analysis.criteria_version_id = other_criteria.id

        with pytest.raises(ValueError, match="criteria version"):
            db.commit()
        db.rollback()
        assert db.query(AIAnalysisVersion).count() == 0
    finally:
        db.close()


def test_session_is_reusable_after_failed_analysis_validation() -> None:
    """Persist a valid analysis through the same Session after rolling back a failure."""
    db = SessionLocal()
    try:
        application, criteria, other_criteria, resume, _ = _create_analysis_context(db)
        db.add(_create_analysis(application.id, other_criteria.id, resume.id, 1))
        with pytest.raises(ValueError, match="criteria version"):
            db.commit()
        db.rollback()

        valid_analysis = _create_analysis(application.id, criteria.id, resume.id, 1)
        db.add(valid_analysis)
        db.commit()
        assert db.get(AIAnalysisVersion, valid_analysis.id) is not None
    finally:
        db.close()


def test_persisted_analysis_rejects_every_orm_field_update() -> None:
    """Reject all tracked analysis field updates and retain their persisted values."""
    db = SessionLocal()
    try:
        application, criteria, other_criteria, resume, other_resume = _create_analysis_context(db)
        analysis = _create_analysis(application.id, criteria.id, resume.id, 1)
        db.add(analysis)
        db.commit()
        analysis_id = analysis.id
        expected_values = {
            "analysis_json": {"summary": "Deterministic test analysis."},
            "job_match_score": 88.0,
            "capability_evidence_score": 90.0,
            "confidence_score": 85.0,
            "recommendation_pool": "main_recommendation",
            "analysis_stage": "resume_screening",
            "application_id": application.id,
            "criteria_version_id": criteria.id,
            "resume_version_id": resume.id,
            "version_number": 1,
        }
        replacements = {
            "analysis_json": {"summary": "changed"},
            "job_match_score": 70.0,
            "capability_evidence_score": 70.0,
            "confidence_score": 70.0,
            "recommendation_pool": "needs_review",
            "analysis_stage": "hr_review",
            "application_id": 999999,
            "criteria_version_id": other_criteria.id,
            "resume_version_id": other_resume.id,
            "version_number": 2,
        }

        for field_name, replacement in replacements.items():
            persisted = db.get(AIAnalysisVersion, analysis_id)
            setattr(persisted, field_name, replacement)
            with pytest.raises(ValueError, match="immutable"):
                db.commit()
            db.rollback()
            persisted = db.get(AIAnalysisVersion, analysis_id)
            assert getattr(persisted, field_name) == expected_values[field_name]
    finally:
        db.close()


def test_add_and_add_all_are_atomic_for_analysis_validation() -> None:
    """Apply mapper validation to both normal add paths without partial commits."""
    db = SessionLocal()
    try:
        application, criteria, other_criteria, resume, _ = _create_analysis_context(db)
        first_analysis = _create_analysis(application.id, criteria.id, resume.id, 1)
        db.add(first_analysis)
        db.commit()
        assert db.query(AIAnalysisVersion).count() == 1

        db.add_all(
            (
                _create_analysis(application.id, criteria.id, resume.id, 2),
                _create_analysis(application.id, other_criteria.id, resume.id, 3),
            )
        )
        with pytest.raises(ValueError, match="criteria version"):
            db.commit()
        db.rollback()
        assert db.query(AIAnalysisVersion).count() == 1
    finally:
        db.close()


def test_analysis_model_has_no_relationship_append_write_entry() -> None:
    """Document that a reverse collection must gain dedicated flush-validation tests if added."""
    assert not hasattr(Application, "ai_analysis_versions")


def test_in_place_analysis_json_mutation_is_not_persisted() -> None:
    """Keep plain JSON immutable unless callers explicitly assign a replacement value."""
    db = SessionLocal()
    try:
        application, criteria, _, resume, _ = _create_analysis_context(db)
        analysis = _create_analysis(application.id, criteria.id, resume.id, 1)
        db.add(analysis)
        db.commit()
        analysis_id = analysis.id

        analysis.analysis_json["summary"] = "in-place mutation"
        assert not db.is_modified(analysis, include_collections=True)
        db.commit()

        db.expire(analysis, ["analysis_json"])
        assert db.get(AIAnalysisVersion, analysis_id).analysis_json == {
            "summary": "Deterministic test analysis."
        }
    finally:
        db.close()


def test_analysis_history_restricts_application_and_resume_deletion() -> None:
    """Prevent ORM deletes from silently cascading through historical analysis rows."""
    db = SessionLocal()
    try:
        candidate = TalentCandidate(name="Linus")
        job = _create_job("Systems Engineer")
        db.add_all((candidate, job))
        db.commit()
        resume = _create_resume_version(candidate.id, 1)
        criteria = HiringCriteriaVersion(
            job_id=job.id,
            version_number=1,
            status="active",
            source_jd_text=job.jd_text,
            criteria_json={},
        )
        db.add_all((resume, criteria))
        db.commit()
        application = Application(
            talent_candidate_id=candidate.id,
            job_id=job.id,
            resume_version_id=resume.id,
            source_type="referral",
            status="submitted",
        )
        db.add(application)
        db.commit()
        analysis = _create_analysis(application.id, criteria.id, resume.id, 1)
        db.add(analysis)
        db.commit()

        db.delete(job)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.delete(application)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.delete(resume)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        assert db.get(AIAnalysisVersion, analysis.id) is not None
    finally:
        db.close()


def test_downgrade_to_0002_preserves_existing_tables_and_data(tmp_path: Path) -> None:
    """Drop only V2-3A-2 tables when downgrading from head to revision 0002."""
    database_url = f"sqlite:///{(tmp_path / 'downgrade-0003.db').as_posix()}"
    config = _alembic_config(database_url)
    command.upgrade(config, "0002_add_talent_candidates_applications")
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
    command.downgrade(config, "0002_add_talent_candidates_applications")

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
        } <= table_names
        assert not {"hiring_criteria_versions", "ai_analysis_versions"} & table_names
        with verified_engine.connect() as connection:
            assert connection.execute(text("SELECT title FROM jobs")).scalar_one() == "Preserved job"
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
                "0002_add_talent_candidates_applications"
            )
    finally:
        verified_engine.dispose()
