"""Test-isolation guard — D111.

These tests fail if the suite's database / lifecycle-root isolation
(`tests/conftest.py`) regresses — i.e. if a lifespan run could reach the
production `concierge.db` or `~/.concierge-lifecycle/` again.

Every test here is non-vacuous: each asserts a *positive* property of the
isolated side (a resolved path / engine URL / migrated tmp DB), so removing
the conftest `CONCIERGE_DATABASE_PATH` / `CONCIERGE_LIFECYCLE_ROOT` override
flips it red. The production-state stat checks in
`test_lifespan_migrates_the_isolated_db` are existence-guarded
defense-in-depth only — explicitly NOT load-bearing: the production
`concierge.db` is already at alembic head, so a regressed lifespan's
`alembic upgrade head` against it is a no-op that never moves its mtime
(D103 — a vacuous pass plus an inference is not a guard).

See planning/audits/stage-1b-test-isolation-inspection-2026-05-17.md
(upgrade workspace) for the inspection record.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from core.app import create_app
from core.config import PROJECT_ROOT, get_settings
from core.db.session import get_engine

PROD_DB = PROJECT_ROOT / "concierge.db"
PROD_LIFECYCLE_ROOT = Path.home() / ".concierge-lifecycle"


def test_settings_database_path_is_isolated():
    """`get_settings().database_path` must not resolve to the production
    catalog DB. Fails if conftest stops setting `CONCIERGE_DATABASE_PATH`."""
    db_path = get_settings().database_path
    assert db_path != PROD_DB
    assert db_path != Path("concierge.db")


def test_settings_lifecycle_root_is_isolated():
    """`get_settings().lifecycle_root` must not resolve to the production
    `~/.concierge-lifecycle`. Fails if conftest stops setting
    `CONCIERGE_LIFECYCLE_ROOT`."""
    assert get_settings().lifecycle_root != PROD_LIFECYCLE_ROOT


def test_engine_targets_isolated_db():
    """The real engine — what the lifespan's `get_session_factory()` and
    `ensure_schema_current()` resolve — binds to the isolated DB, not
    production."""
    assert str(PROD_DB) not in str(get_engine().url)


def test_lifespan_migrates_the_isolated_db():
    """A real lifespan run (`with TestClient(create_app())`) lands its
    `alembic upgrade head` on the *isolated* DB, not production.

    Load-bearing, non-vacuous: the post-run assertions are positive
    properties of the isolated side — the resolved `database_path` is the
    tmp path (not the production `concierge.db`), the engine binds to it,
    and the lifespan created and migrated *that* file to alembic head.
    Strip the conftest isolation and `database_path` resolves to production
    → the first assertion fails. (Contrast the rejected
    stat-the-production-DB framing: production is already at head, so a
    regressed lifespan's `alembic upgrade head` is a no-op there and never
    moves its mtime — that check could not bite. D103.)

    The production-state stat checks below are existence-guarded
    defense-in-depth only — NOT the load-bearing assertion.
    """
    import sqlite3

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    db_before = PROD_DB.stat() if PROD_DB.exists() else None
    lifecycle_before = (
        PROD_LIFECYCLE_ROOT.stat() if PROD_LIFECYCLE_ROOT.exists() else None
    )

    with TestClient(create_app()):
        pass  # lifespan startup (alembic + reconcile + scheduler) then teardown

    # --- load-bearing: the lifespan operated on the isolated DB ---
    db_path = get_settings().database_path
    assert db_path != PROD_DB, (
        "lifespan resolved database_path to the production concierge.db — "
        "conftest DB isolation has regressed"
    )
    assert str(db_path) in str(get_engine().url)
    assert db_path.exists(), "lifespan did not create the isolated DB"

    head_rev = ScriptDirectory.from_config(
        Config(str(PROJECT_ROOT / "alembic.ini"))
    ).get_current_head()
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] == head_rev, (
        "lifespan did not migrate the isolated DB to alembic head"
    )

    # --- defense-in-depth only (NOT load-bearing — see docstring) ---
    if db_before is not None:
        db_after = PROD_DB.stat()
        assert (db_after.st_mtime_ns, db_after.st_size) == (
            db_before.st_mtime_ns,
            db_before.st_size,
        )
    if lifecycle_before is not None:
        assert (
            PROD_LIFECYCLE_ROOT.stat().st_mtime_ns == lifecycle_before.st_mtime_ns
        )
