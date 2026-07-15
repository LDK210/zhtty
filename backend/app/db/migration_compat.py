"""Safe onboarding checks for databases created before Alembic was introduced."""

from __future__ import annotations

from collections.abc import Iterable
import logging

from alembic.util.exc import CommandError
from sqlalchemy import Connection, inspect, text
from sqlalchemy.sql.sqltypes import DateTime, Enum, Integer, JSON, String, Text

from app.db.session import Base

INITIAL_REVISION = "0001_initial_schema"
VERSION_TABLE_NAME = "alembic_version"
INITIAL_TABLE_NAMES = frozenset({"agent_logs", "candidates", "jobs", "resumes", "scores"})
logger = logging.getLogger(__name__)


def _load_model_metadata() -> None:
    """Import all ORM modules so ``Base.metadata`` contains every table."""
    from app.models import (  # noqa: F401
        agent_log,
        application,
        candidate,
        job,
        resume,
        resume_version,
        score,
        talent_candidate,
    )


def _type_matches(actual_type: object, expected_type: object) -> bool:
    """Return whether a reflected SQL type is compatible with an ORM column."""
    actual_name = str(actual_type).lower()

    if isinstance(expected_type, Integer):
        return "int" in actual_name
    if isinstance(expected_type, Text):
        return "text" in actual_name
    if isinstance(expected_type, Enum):
        if "char" not in actual_name and "varchar" not in actual_name:
            return False
        expected_length = getattr(expected_type, "length", None)
        actual_length = getattr(actual_type, "length", None)
        return expected_length is None or actual_length in (None, expected_length)
    if isinstance(expected_type, String):
        if "char" not in actual_name and "varchar" not in actual_name:
            return False
        expected_length = getattr(expected_type, "length", None)
        actual_length = getattr(actual_type, "length", None)
        return expected_length is None or actual_length in (None, expected_length)
    if isinstance(expected_type, JSON):
        return "json" in actual_name
    if isinstance(expected_type, DateTime):
        return "date" in actual_name or "time" in actual_name
    return actual_name == str(expected_type).lower()


def _format_values(values: Iterable[str]) -> str:
    """Format schema item names for concise, non-sensitive diagnostics."""
    return ", ".join(sorted(values))


def validate_legacy_schema(connection: Connection) -> list[str]:
    """Validate critical legacy structure against the current ORM metadata.

    This only inspects schema metadata. It never reads applicant or other
    business records, so diagnostics cannot expose sensitive application data.
    """
    _load_model_metadata()
    inspector = inspect(connection)
    expected_tables = INITIAL_TABLE_NAMES
    actual_tables = set(inspector.get_table_names()) - {VERSION_TABLE_NAME}
    errors: list[str] = []

    missing_tables = expected_tables - actual_tables
    unexpected_tables = actual_tables - expected_tables
    if missing_tables:
        errors.append(f"missing tables: {_format_values(missing_tables)}")
    if unexpected_tables:
        errors.append(f"unexpected tables: {_format_values(unexpected_tables)}")

    for table_name in sorted(expected_tables & actual_tables):
        expected_table = Base.metadata.tables[table_name]
        reflected_columns = {
            column["name"]: column for column in inspector.get_columns(table_name)
        }
        expected_columns = {column.name: column for column in expected_table.columns}

        missing_columns = set(expected_columns) - set(reflected_columns)
        unexpected_columns = set(reflected_columns) - set(expected_columns)
        if missing_columns:
            errors.append(
                f"{table_name} missing columns: {_format_values(missing_columns)}"
            )
        unsafe_extra_columns = {
            column_name
            for column_name in unexpected_columns
            if not reflected_columns[column_name]["nullable"]
            and reflected_columns[column_name].get("default") is None
        }
        if unsafe_extra_columns:
            errors.append(
                f"{table_name} has required extra columns: "
                f"{_format_values(unsafe_extra_columns)}"
            )
        safe_extra_columns = unexpected_columns - unsafe_extra_columns
        if safe_extra_columns:
            logger.warning(
                "Retaining optional legacy columns while stamping Alembic",
                extra={"table": table_name, "columns": sorted(safe_extra_columns)},
            )

        expected_primary_key = [column.name for column in expected_table.primary_key.columns]
        actual_primary_key = inspector.get_pk_constraint(table_name).get("constrained_columns") or []
        if actual_primary_key != expected_primary_key:
            errors.append(f"{table_name} has an incompatible primary key")

        for column_name in sorted(set(expected_columns) & set(reflected_columns)):
            expected_column = expected_columns[column_name]
            reflected_column = reflected_columns[column_name]
            if not _type_matches(reflected_column["type"], expected_column.type):
                errors.append(f"{table_name}.{column_name} has an incompatible type")
            if (
                not expected_column.primary_key
                and bool(reflected_column["nullable"]) != expected_column.nullable
            ):
                errors.append(f"{table_name}.{column_name} has incompatible nullability")
            expected_server_default = expected_column.server_default
            actual_default = reflected_column.get("default")
            if expected_server_default is not None or actual_default is not None:
                expected_default_value = (
                    str(expected_server_default.arg) if expected_server_default is not None else None
                )
                if actual_default != expected_default_value:
                    errors.append(f"{table_name}.{column_name} has an incompatible server default")

        expected_foreign_keys = {
            (
                foreign_key.parent.name,
                foreign_key.column.table.name,
                foreign_key.column.name,
                foreign_key.ondelete,
            )
            for foreign_key in expected_table.foreign_keys
        }
        actual_foreign_keys = {
            (
                foreign_key["constrained_columns"][0],
                foreign_key["referred_table"],
                foreign_key["referred_columns"][0],
                foreign_key.get("options", {}).get("ondelete"),
            )
            for foreign_key in inspector.get_foreign_keys(table_name)
            if len(foreign_key["constrained_columns"]) == 1
            and len(foreign_key["referred_columns"]) == 1
        }
        if expected_foreign_keys != actual_foreign_keys:
            errors.append(f"{table_name} has incompatible foreign keys")

        reflected_indexes = {
            index["name"]: index for index in inspector.get_indexes(table_name)
        }
        for expected_index in expected_table.indexes:
            reflected_index = reflected_indexes.get(expected_index.name)
            expected_column_names = [column.name for column in expected_index.columns]
            if reflected_index is None:
                errors.append(f"{table_name} missing index: {expected_index.name}")
                continue
            if reflected_index["column_names"] != expected_column_names:
                errors.append(f"{table_name}.{expected_index.name} has incompatible columns")
            if bool(reflected_index.get("unique")) != expected_index.unique:
                errors.append(f"{table_name}.{expected_index.name} has incompatible uniqueness")

    return errors


def prepare_legacy_database(connection: Connection) -> bool:
    """Stamp a validated pre-Alembic schema at the initial revision.

    Returns ``True`` when a legacy schema was stamped. An incompatible database
    raises ``CommandError`` before any schema or data is changed.
    """
    if connection.dialect.name != "sqlite":
        inspector = inspect(connection)
        if not inspector.has_table(VERSION_TABLE_NAME) and inspector.get_table_names():
            raise CommandError(
                "An existing non-SQLite database without alembic_version cannot be "
                "automatically stamped. Verify it and create an explicit migration plan."
            )
        connection.commit()
        return False

    # SQLite uses a write lock to serialize two simultaneous first-start attempts.
    connection.exec_driver_sql("BEGIN IMMEDIATE")
    try:
        inspector = inspect(connection)
        if inspector.has_table(VERSION_TABLE_NAME):
            connection.commit()
            return False

        if not inspector.get_table_names():
            connection.commit()
            return False

        errors = validate_legacy_schema(connection)
        if errors:
            details = "; ".join(errors)
            raise CommandError(
                "Existing database schema is incompatible with HirePilot's initial "
                f"migration; no Alembic version was written. Details: {details}"
            )

        connection.execute(
            text(
                "CREATE TABLE alembic_version ("
                "version_num VARCHAR(32) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
                ")"
            )
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": INITIAL_REVISION},
        )
        connection.commit()
        return True
    except Exception:
        if connection.in_transaction():
            connection.rollback()
        raise
