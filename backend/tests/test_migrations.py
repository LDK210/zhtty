"""Integration tests for Alembic schema creation and legacy SQLite onboarding."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import create_engine, inspect, text

from app.db.migration_compat import INITIAL_REVISION, VERSION_TABLE_NAME
from app.db.session import Base
from app.config import BACKEND_DIR, Settings


def _sqlite_url(database_path: Path) -> str:
    """Return an SQLite URL for a pytest-managed temporary database file."""
    return f"sqlite:///{database_path.as_posix()}"


def _alembic_config(database_url: str) -> Config:
    """Build an Alembic config that targets a pytest temporary database."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def _file_hash(path: Path) -> str:
    """Return the SHA-256 digest of a temporary SQLite database file."""
    return sha256(path.read_bytes()).hexdigest()


def test_upgrade_head_creates_complete_schema(tmp_path: Path) -> None:
    """A fresh SQLite database upgrades to the full current schema successfully."""
    database_url = _sqlite_url(tmp_path / "fresh.db")
    command.upgrade(_alembic_config(database_url), "head")
    command.upgrade(_alembic_config(database_url), "head")
    command.check(_alembic_config(database_url))

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
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
            "hr_decisions",
            "pipeline_events",
        } <= set(inspector.get_table_names())
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
                "0004_add_hr_decisions_and_pipeline_events"
            )
    finally:
        engine.dispose()


def test_compatible_legacy_schema_is_safely_stamped(tmp_path: Path) -> None:
    """A matching pre-Alembic schema gains only an Alembic version record."""
    database_url = _sqlite_url(tmp_path / "legacy-compatible.db")
    config = _alembic_config(database_url)
    command.upgrade(config, INITIAL_REVISION)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
            connection.execute(text("ALTER TABLE scores ADD COLUMN assessment_json JSON"))
            connection.execute(
                text(
                    "INSERT INTO jobs (id, title, jd_text, jd_structured_json, status, "
                    "error_message, created_at, updated_at) VALUES "
                    "(1, 'Preserved job', 'Preserved JD', NULL, 'draft', NULL, "
                    "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
                )
            )
        before_tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    verified_engine = create_engine(database_url)
    try:
        inspector = inspect(verified_engine)
        assert set(inspector.get_table_names()) == before_tables | {
            VERSION_TABLE_NAME,
            "talent_candidates",
            "resume_versions",
            "applications",
            "hiring_criteria_versions",
            "ai_analysis_versions",
            "hr_decisions",
            "pipeline_events",
        }
        assert "assessment_json" in {column["name"] for column in inspector.get_columns("scores")}
        with verified_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
                "0004_add_hr_decisions_and_pipeline_events"
            )
            assert connection.execute(text("SELECT title FROM jobs WHERE id = 1")).scalar_one() == "Preserved job"
    finally:
        verified_engine.dispose()


def test_incompatible_legacy_schema_is_not_stamped(tmp_path: Path) -> None:
    """A partial legacy schema fails safely without adding ``alembic_version``."""
    database_url = _sqlite_url(tmp_path / "legacy-incompatible.db")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE jobs (id INTEGER PRIMARY KEY)"))
    finally:
        engine.dispose()

    with pytest.raises(CommandError, match="incompatible"):
        command.upgrade(_alembic_config(database_url), "head")

    verified_engine = create_engine(database_url)
    try:
        assert not inspect(verified_engine).has_table(VERSION_TABLE_NAME)
    finally:
        verified_engine.dispose()


def test_current_does_not_stamp_a_legacy_database(tmp_path: Path) -> None:
    """Inspecting a legacy database must not create an Alembic version record."""
    database_url = _sqlite_url(tmp_path / "legacy-current.db")
    engine = create_engine(database_url)
    try:
        Base.metadata.create_all(bind=engine)
    finally:
        engine.dispose()
    database_path = tmp_path / "legacy-current.db"
    before_hash = _file_hash(database_path)
    before_tables = set(inspect(create_engine(database_url)).get_table_names())

    config = _alembic_config(database_url)
    config.cmd_opts = SimpleNamespace(cmd=(command.current, [], []))
    command.current(config)

    verified_engine = create_engine(database_url)
    try:
        assert not inspect(verified_engine).has_table(VERSION_TABLE_NAME)
        assert set(inspect(verified_engine).get_table_names()) == before_tables
    finally:
        verified_engine.dispose()
    assert _file_hash(database_path) == before_hash


def test_unknown_existing_revision_is_not_overwritten(tmp_path: Path) -> None:
    """An invalid existing version is reported instead of being automatically replaced."""
    database_url = _sqlite_url(tmp_path / "unknown-revision.db")
    engine = create_engine(database_url)
    try:
        Base.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, "
                    "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
                )
            )
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('unknown_revision')")
            )
    finally:
        engine.dispose()

    with pytest.raises(CommandError):
        command.upgrade(_alembic_config(database_url), "head")

    verified_engine = create_engine(database_url)
    try:
        with verified_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
                "unknown_revision"
            )
    finally:
        verified_engine.dispose()


def test_relative_sqlite_url_is_anchored_to_backend_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A relative SQLite URL cannot create a database in an arbitrary process CWD."""
    monkeypatch.chdir(tmp_path)
    database_name = "relative-url-test.db"
    settings = Settings(database_url=f"sqlite:///./{database_name}")

    assert settings.database_url == f"sqlite:///{(BACKEND_DIR / database_name).as_posix()}"
    assert not (tmp_path / database_name).exists()
