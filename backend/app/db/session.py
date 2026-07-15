from __future__ import annotations

from collections.abc import Generator

from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
        """Enable SQLite foreign-key enforcement for every database connection."""
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Load ORM models used by Alembic migration metadata.

    Database schema changes are managed with Alembic. Run ``alembic upgrade
    head`` before starting the application against a new database.
    """
    from app.models import (  # noqa: F401
        agent_log,
        ai_analysis_version,
        application,
        candidate,
        job,
        hiring_criteria_version,
        hr_decision,
        pipeline_event,
        resume,
        resume_version,
        score,
        talent_candidate,
    )
