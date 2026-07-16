"""Persistence access for hiring-criteria versions."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import HiringCriteriaVersion, Job


def get_job_by_id(session: Session, job_id: int) -> Job | None:
    """Return the job identified by ``job_id``, if it exists."""
    return session.get(Job, job_id)


def get_current_draft_for_job(session: Session, job_id: int) -> HiringCriteriaVersion | None:
    """Return the current draft criteria version for one job, if present."""
    return (
        session.query(HiringCriteriaVersion)
        .filter(
            HiringCriteriaVersion.job_id == job_id,
            HiringCriteriaVersion.status == "draft",
        )
        .order_by(HiringCriteriaVersion.version_number.desc())
        .first()
    )


def get_max_version_number_for_job(session: Session, job_id: int) -> int:
    """Return the highest persisted criteria version number for one job."""
    maximum = (
        session.query(func.max(HiringCriteriaVersion.version_number))
        .filter(HiringCriteriaVersion.job_id == job_id)
        .scalar()
    )
    return int(maximum or 0)


def create_criteria_version(session: Session, criteria_version: HiringCriteriaVersion) -> HiringCriteriaVersion:
    """Add a new criteria version to the current ORM unit of work."""
    session.add(criteria_version)
    return criteria_version


def get_criteria_version_by_id(session: Session, criteria_version_id: int) -> HiringCriteriaVersion | None:
    """Return a criteria version by primary key, if it exists."""
    return session.get(HiringCriteriaVersion, criteria_version_id)
