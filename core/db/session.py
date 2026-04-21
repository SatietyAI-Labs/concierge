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
    """Create all tables defined on Base.metadata. Idempotent."""
    from core.db.base import Base
    from core.db import models  # noqa: F401  — ensure models register on Base

    Base.metadata.create_all(bind=get_engine())
