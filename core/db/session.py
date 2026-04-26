"""Engine + session factory + FastAPI dependency for the Concierge database."""
from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import Settings, get_settings


def make_engine(settings: Settings) -> Engine:
    database_url = f"sqlite:///{settings.database_path}"
    return create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        echo=settings.debug and settings.log_level.upper() == "DEBUG",
    )


@lru_cache
def get_engine() -> Engine:
    return make_engine(get_settings())


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=True)


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create all tables defined on Base.metadata directly. Test-only.

    Production startup uses `ensure_schema_current()` which runs
    Alembic migrations; this function bypasses Alembic for per-test
    speed in fixtures. Kept in sync with the migration chain is a
    test concern — a migration-drift integration test should exercise
    the Alembic path from empty → head.
    """
    from core.db.base import Base
    from core.db import models  # noqa: F401  — ensure models register on Base

    Base.metadata.create_all(bind=get_engine())


def ensure_schema_current() -> None:
    """Run `alembic upgrade head` at FastAPI startup.

    Alembic owns schema as of 2026-04-24 (Fix Day 1 bootstrap).
    Running it programmatically means `uvicorn core.app:create_app
    --factory` on a fresh clone produces a ready DB with no prior
    CLI step. Idempotent — no-op when already at head.
    """
    import logging

    from alembic import command
    from alembic.config import Config

    from core.config import get_settings

    logger = logging.getLogger("concierge")
    settings = get_settings()
    alembic_cfg = Config(str(settings.project_root / "alembic.ini"))
    logger.info("alembic.upgrade.start db=%s", settings.database_path)
    command.upgrade(alembic_cfg, "head")
    logger.info("alembic.upgrade.done")
