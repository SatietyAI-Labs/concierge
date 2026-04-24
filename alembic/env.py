"""Alembic environment for Concierge.

Bootstrapped 2026-04-24 as part of Fix Day 1 (close-the-gap plan).
Alembic is the single source of truth for DB schema. The prior
`Base.metadata.create_all()` startup call is removed in favor of
`alembic upgrade head` at install time; the pre-existing dev DB was
stamped at the baseline revision so Alembic upgrades from that known
state.

- DB URL is pulled from `core.config.Settings.database_path` — the
  `sqlalchemy.url` fallback in alembic.ini is overridden here.
- `render_as_batch=True` is mandatory for SQLite to support
  ALTER COLUMN / DROP COLUMN via table recreation.
- `compare_type=True` lets autogenerate catch column type changes the
  default miss.
- The `from core.db import models` side-effect import is load-bearing:
  without it Base.metadata is empty and autogenerate proposes dropping
  every existing table.
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from core.config import get_settings
from core.db.base import Base
from core.db import models  # noqa: F401 — register models on Base.metadata

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False preserves the `concierge` logger
    # (and any other pre-existing loggers) when Alembic is invoked
    # programmatically from a running process — e.g. the drift test
    # or the FastAPI startup hook. Without this, fileConfig's default
    # disables every logger not named in alembic.ini, breaking
    # caplog-based log-assertion tests that run after Alembic has run.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

_settings = get_settings()
config.set_main_option(
    "sqlalchemy.url", f"sqlite:///{_settings.database_path}"
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL scripts without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against the live DB."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
