import atexit
import os
import shutil
import tempfile
from pathlib import Path

# Disable the §VIII.2 / D88 cold-start pre-warm for the test suite —
# app-construction tests that run the lifespan must not load the
# sentence-transformers model. Set before `get_settings()`'s lru_cache
# is first populated. The dedicated pre-warm tests (test_app_lifespan.py)
# opt back in explicitly by overriding `core.app.get_settings`.
os.environ.setdefault("CONCIERGE_PREWARM_ON_STARTUP", "false")

# D111 — isolate the catalog DB, lifecycle root, and memory dir off
# production for the whole suite. The app lifespan (exercised by
# `test_app_lifespan.py` and `test_scanner_endpoint.py` via
# `with TestClient(...)`) runs `alembic upgrade head` + a lifecycle
# `reconcile()` against `get_settings()` — neither flows through the
# `core.app.get_settings` monkeypatch nor `dependency_overrides[get_db]`,
# so without this a suite run mutates the live
# `~/satietyai-concierge/concierge.db`. Set here, before the first
# `get_settings()` call (its `lru_cache` reads the env once), mirroring
# the `CONCIERGE_PREWARM_ON_STARTUP` precedent above — so no
# `lru_cache.cache_clear()` is needed. `setdefault` leaves an operator
# override possible. See
# planning/audits/stage-1b-test-isolation-inspection-2026-05-17.md
# (upgrade workspace) for the inspection record.
_TEST_STATE_DIR = tempfile.mkdtemp(prefix="concierge-test-state-")
_TEST_LIFECYCLE_ROOT = Path(_TEST_STATE_DIR) / "lifecycle"
for _sub in ("pending", "resolved", "archived"):
    (_TEST_LIFECYCLE_ROOT / _sub).mkdir(parents=True, exist_ok=True)
os.environ.setdefault(
    "CONCIERGE_DATABASE_PATH", str(Path(_TEST_STATE_DIR) / "concierge-test.db")
)
os.environ.setdefault("CONCIERGE_LIFECYCLE_ROOT", str(_TEST_LIFECYCLE_ROOT))
os.environ.setdefault("CONCIERGE_MEMORY_DIR", str(Path(_TEST_STATE_DIR) / "memory"))
atexit.register(shutil.rmtree, _TEST_STATE_DIR, ignore_errors=True)

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
