"""Business rules for editable hiring-criteria drafts."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import AppError
from app.models import HiringCriteriaVersion
from app.repositories import criteria_repository
from app.schemas.versions import HiringCriteriaDraftCreate, HiringCriteriaDraftUpdate


def create_draft(
    job_id: int, payload: HiringCriteriaDraftCreate, session: Session
) -> HiringCriteriaVersion:
    """Create the sole editable criteria draft for a job in one transaction."""
    try:
        with session.begin():
            job = criteria_repository.get_job_by_id(session, job_id)
            if job is None:
                raise AppError(code="job_not_found", message="Job not found.", status_code=404)
            if criteria_repository.get_current_draft_for_job(session, job_id) is not None:
                raise AppError(
                    code="criteria_draft_already_exists",
                    message="A criteria draft already exists for this job.",
                    status_code=409,
                )

            criteria_version = HiringCriteriaVersion(
                job_id=job.id,
                version_number=criteria_repository.get_max_version_number_for_job(session, job.id) + 1,
                status="draft",
                source_jd_text=payload.source_jd_text if payload.source_jd_text is not None else job.jd_text,
                criteria_json=payload.criteria_json,
                created_by=payload.created_by,
            )
            criteria_repository.create_criteria_version(session, criteria_version)
            session.flush()
            session.refresh(criteria_version)
            return criteria_version
    except IntegrityError as exc:
        # The schema has no portable partial unique constraint for one draft per job.
        # A concurrent draft creation can collide on the version-number constraint.
        raise AppError(
            code="criteria_draft_already_exists",
            message="A criteria draft already exists for this job.",
            status_code=409,
        ) from exc


def get_draft(job_id: int, session: Session) -> HiringCriteriaVersion:
    """Return the current draft for a job without exposing historical versions."""
    if criteria_repository.get_job_by_id(session, job_id) is None:
        raise AppError(code="job_not_found", message="Job not found.", status_code=404)
    criteria_version = criteria_repository.get_current_draft_for_job(session, job_id)
    if criteria_version is None:
        raise AppError(
            code="criteria_draft_not_found",
            message="Criteria draft not found.",
            status_code=404,
        )
    return criteria_version


def update_draft(
    job_id: int,
    criteria_version_id: int,
    payload: HiringCriteriaDraftUpdate,
    session: Session,
) -> HiringCriteriaVersion:
    """Atomically update mutable values on a draft owned by the requested job."""
    with session.begin():
        if criteria_repository.get_job_by_id(session, job_id) is None:
            raise AppError(code="job_not_found", message="Job not found.", status_code=404)
        criteria_version = criteria_repository.get_criteria_version_by_id(session, criteria_version_id)
        if criteria_version is None or criteria_version.job_id != job_id:
            raise AppError(
                code="criteria_version_not_found",
                message="Criteria version not found for this job.",
                status_code=404,
            )
        if criteria_version.status != "draft":
            raise AppError(
                code="criteria_version_not_draft",
                message="Only draft criteria versions can be updated.",
                status_code=409,
            )

        for field_name, value in payload.model_dump(exclude_unset=True).items():
            setattr(criteria_version, field_name, value)
        session.flush()
        session.refresh(criteria_version)
        return criteria_version
