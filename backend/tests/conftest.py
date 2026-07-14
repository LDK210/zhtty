from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

_test_root = Path(tempfile.mkdtemp(prefix="hirepilot-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_test_root / 'hirepilot-test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = (_test_root / "uploads").as_posix()
os.environ.pop("OPENAI_API_KEY", None)
os.environ["LOG_LEVEL"] = "WARNING"

from app.config import get_settings

get_settings.cache_clear()

from app.db.session import Base, engine
from app.main import app


def alembic_config(database_url: str) -> Config:
    """Build an Alembic configuration that targets an isolated test database."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


@pytest.fixture(autouse=True)
def reset_test_environment() -> Generator[None, None, None]:
    """Recreate the isolated test database and upload directory for each test."""
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    command.upgrade(alembic_config(str(engine.url)), "head")
    upload_dir = _test_root / "uploads"
    shutil.rmtree(upload_dir, ignore_errors=True)
    upload_dir.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture
def client(reset_test_environment: None) -> Generator[TestClient, None, None]:
    """Provide a client whose startup uses the isolated test settings."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Dispose test-only connections and remove the temporary test workspace."""
    engine.dispose()
    shutil.rmtree(_test_root, ignore_errors=True)
