import os

# Disable the §VIII.2 / D88 cold-start pre-warm for the test suite —
# app-construction tests that run the lifespan must not load the
# sentence-transformers model. Set before `get_settings()`'s lru_cache
# is first populated. The dedicated pre-warm tests (test_app_lifespan.py)
# opt back in explicitly by overriding `core.app.get_settings`.
os.environ.setdefault("CONCIERGE_PREWARM_ON_STARTUP", "false")

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.app import create_app
from core.db.base import Base
from core.db import models  # noqa: F401 — ensure models register on Base.metadata
from core.db.session import get_db


@pytest.fixture(autouse=True)
def _restore_concierge_logger_families():
    """Snapshot and restore the `concierge` and `core` family loggers
    around every test.

    `configure_logging()` — run by the app lifespan in
    `test_app_lifespan.py` and `test_scanner_endpoint.py` — sets
    `propagate = False` on both family loggers (so they are immune to
    Alembic's `fileConfig` reconfiguring the root logger). Without this
    fixture that leaks into later `caplog`-based tests: `caplog`
    captures at the *root* logger, so a family logger left at
    `propagate = False` is no longer observed and those tests fail
    spuriously depending on collection order.
    """
    families = [logging.getLogger(n) for n in ("concierge", "core")]
    saved = [(lg, lg.level, lg.propagate, lg.handlers[:]) for lg in families]
    try:
        yield
    finally:
        for lg, level, propagate, handlers in saved:
            lg.setLevel(level)
            lg.propagate = propagate
            lg.handlers[:] = handlers


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client_with_db(db_session):
    """TestClient wired to the in-memory db_session via dependency override."""
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
