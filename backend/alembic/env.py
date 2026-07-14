"""Alembic environment configured from the HirePilot application settings."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db.migration_compat import prepare_legacy_database
from app.db.session import Base
from app.models import agent_log, candidate, job, resume, score  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = config.attributes.get("database_url") or get_settings().database_url
config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def should_prepare_legacy_schema() -> bool:
    """Allow compatibility stamping only while an upgrade command is running."""
    command = getattr(getattr(config, "cmd_opts", None), "cmd", None)
    if not command:
        # Programmatic upgrade calls used by isolated tests do not set cmd_opts.
        return True
    command_function = command[0] if isinstance(command, tuple) else command
    return getattr(command_function, "__name__", "") == "upgrade"


def run_migrations_offline() -> None:
    """Run migrations without creating an engine connection."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations and stamp a verified legacy schema when needed."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if should_prepare_legacy_schema():
            prepare_legacy_database(connection)
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
