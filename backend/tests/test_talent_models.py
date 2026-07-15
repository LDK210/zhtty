"""Database and schema tests for the company talent and application domain."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models import Application, Job, JobStatus, ResumeVersion, TalentCandidate
from app.schemas.talent import ApplicationCreate, ResumeVersionRead


def _alembic_config(database_url: str) -> Config:
    """Build an Alembic configuration for a pytest-managed database file."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def _create_job(title: str) -> Job:
    """Build a minimally valid legacy job for an application relationship test."""
    return Job(title=title, jd_text="A valid job description.", status=JobStatus.draft)


def _create_resume_version(talent_candidate_id: int, version_number: int) -> ResumeVersion:
    """Build a minimally valid resume version for a known talent candidate."""
    return ResumeVersion(
        talent_candidate_id=talent_candidate_id,
        version_number=version_number,
        original_filename=f"resume-v{version_number}.pdf",
        stored_filename=f"resume-v{version_number}-stored.pdf",
        file_path=f"/private/uploads/resume-v{version_number}.pdf",
        file_hash=f"hash-{version_number}",
        source_type="upload",
    )


def test_talent_candidate_resume_versions_and_application_constraints() -> None:
    """Persist independent candidates, versioned resumes, and unique job applications."""
    db = SessionLocal()
    try:
        candidate = TalentCandidate(name="Ada Lovelace", primary_email="ada@example.test")
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        first_resume = _create_resume_version(candidate.id, 1)
        second_resume = _create_resume_version(candidate.id, 2)
        db.add_all((first_resume, second_resume))
        db.commit()

        db.add(_create_resume_version(candidate.id, 2))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        first_job = _create_job("Backend Engineer")
        second_job = _create_job("Platform Engineer")
        db.add_all((first_job, second_job))
        db.commit()

        db.add_all(
            (
                Application(
                    talent_candidate_id=candidate.id,
                    job_id=first_job.id,
                    resume_version_id=first_resume.id,
                    source_type="career_site",
                    status="submitted",
                ),
                Application(
                    talent_candidate_id=candidate.id,
                    job_id=second_job.id,
                    resume_version_id=second_resume.id,
                    source_type="referral",
                    status="in_review",
                ),
            )
        )
        db.commit()
        assert db.query(Application).filter(Application.talent_candidate_id == candidate.id).count() == 2

        db.add(
            Application(
                talent_candidate_id=candidate.id,
                job_id=first_job.id,
                resume_version_id=first_resume.id,
                source_type="career_site",
                status="submitted",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_application_rejects_a_resume_version_owned_by_another_candidate() -> None:
    """Enforce candidate ownership through the composite resume version foreign key."""
    db = SessionLocal()
    try:
        applicant = TalentCandidate(name="Applicant")
        other_candidate = TalentCandidate(name="Other Candidate")
        job = _create_job("Data Engineer")
        db.add_all((applicant, other_candidate, job))
        db.commit()

        other_resume = _create_resume_version(other_candidate.id, 1)
        db.add(other_resume)
        db.commit()

        assert db.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        db.add(
            Application(
                talent_candidate_id=applicant.id,
                job_id=job.id,
                resume_version_id=other_resume.id,
                source_type="career_site",
                status="submitted",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.query(Application).count() == 0
    finally:
        db.close()


def test_deleting_job_is_restricted_and_preserves_talent_candidate() -> None:
    """Prevent a job deletion from cascading into company talent data."""
    db = SessionLocal()
    try:
        candidate = TalentCandidate(name="Grace Hopper")
        job = _create_job("Compiler Engineer")
        db.add_all((candidate, job))
        db.commit()
        resume_version = _create_resume_version(candidate.id, 1)
        db.add(resume_version)
        db.commit()
        db.add(
            Application(
                talent_candidate_id=candidate.id,
                job_id=job.id,
                resume_version_id=resume_version.id,
                source_type="career_site",
                status="submitted",
            )
        )
        db.commit()

        db.delete(job)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        assert db.get(TalentCandidate, candidate.id) is not None
        assert db.get(Job, job.id) is not None
    finally:
        db.close()


def test_resume_version_read_omits_internal_file_path_and_status_is_validated() -> None:
    """Keep storage paths internal and constrain application status at the schema boundary."""
    resume = ResumeVersion(
        id=1,
        talent_candidate_id=2,
        version_number=1,
        original_filename="resume.pdf",
        stored_filename="stored.pdf",
        file_path="/private/uploads/stored.pdf",
        file_hash=None,
        raw_text=None,
        parsed_profile_json=None,
        source_type="upload",
        created_at=datetime(2026, 7, 15),
    )

    assert "file_path" not in ResumeVersionRead.model_validate(resume).model_dump()
    with pytest.raises(ValueError):
        ApplicationCreate(
            talent_candidate_id=1,
            job_id=1,
            resume_version_id=1,
            source_type="upload",
            status="unknown",
        )


def test_downgrade_preserves_legacy_tables_and_data(tmp_path: Path) -> None:
    """Downgrade only the new tables while retaining the original schema and records."""
    database_url = f"sqlite:///{(tmp_path / 'downgrade.db').as_posix()}"
    config = _alembic_config(database_url)
    command.upgrade(config, "0001_initial_schema")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO jobs (title, jd_text, jd_structured_json, status, "
                    "error_message, created_at, updated_at) VALUES "
                    "('Preserved job', 'Preserved JD', NULL, 'draft', NULL, "
                    "'2026-07-15 00:00:00', '2026-07-15 00:00:00')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    command.downgrade(config, "0001_initial_schema")

    verified_engine = create_engine(database_url)
    try:
        table_names = set(inspect(verified_engine).get_table_names())
        assert {"jobs", "resumes", "candidates", "scores", "agent_logs"} <= table_names
        assert not {"talent_candidates", "resume_versions", "applications"} & table_names
        with verified_engine.connect() as connection:
            assert connection.execute(text("SELECT title FROM jobs")).scalar_one() == "Preserved job"
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
                "0001_initial_schema"
            )
    finally:
        verified_engine.dispose()
