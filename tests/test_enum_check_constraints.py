"""Stage 1B Enum CHECK-constraint hardening slice (DECISIONS D110) — the
non-vacuous proof that the three `tools` Enum CHECK constraints actually
reject an off-list write.

The slice's writer enumeration (inspection rev 2) found no writer — ORM or
raw-SQL — that can emit an out-of-enum value: the CHECK formalizes an
invariant every writer already holds. The consequence is that **this module
is the only thing in the suite that exercises the constraint**. If these
tests were vacuous, the slice would ship with zero proof the CHECK does
anything — so the non-vacuity is load-bearing, not a nicety.

Non-vacuity demonstration (per the support-chat framing, recorded in the
Phase B close): removing `create_constraint=True` from the model turns the
`create_all`-path reject-tests red; removing it from migration
`103a85689166` turns the Alembic-path reject-tests red. The paired in-enum
INSERT in each test stays green either way — it is the contrast proving the
test is not simply "every INSERT fails".

Two schema-construction paths are covered (OD-2):
  - the Alembic path (`alembic upgrade head`) — production schema;
  - the `Base.metadata.create_all` path — the per-test fast path, which
    `test_alembic_drift.py` separately proves equivalent to the Alembic path.
Each is asserted directly so neither path's CHECK can silently regress.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from core.config import get_settings
from core.db.base import Base
from core.db import models  # noqa: F401 — register models on Base.metadata


# (column, in-enum value, out-of-enum value) for each hardened column.
_REJECT_CASES = [
    ("lifecycle_state", "loaded-on-boot", "not-a-real-state"),
    ("tool_type", "http", "not-a-real-type"),
    ("pin_status", "always-pinned", "not-a-real-pin"),
]


@pytest.fixture
def alembic_head_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A SQLite DB built by `alembic upgrade head` — the production
    schema path, carrying the CHECKs added by `103a85689166`."""
    db = tmp_path / "enum_check_alembic.db"
    monkeypatch.setenv("CONCIERGE_DATABASE_PATH", str(db))
    get_settings.cache_clear()
    try:
        settings = get_settings()
        cfg = Config(str(settings.project_root / "alembic.ini"))
        command.upgrade(cfg, "head")
    finally:
        get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{db}")
    yield engine
    engine.dispose()


@pytest.fixture
def create_all_engine():
    """An in-memory SQLite DB built by `Base.metadata.create_all` — the
    per-test fast path, carrying the CHECKs from the model's
    `Enum(..., create_constraint=True)` declarations. `StaticPool` so
    every connection shares the one in-memory database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _insert_tool(engine, slug: str, column: str, value) -> None:
    """Insert one `tools` row setting `column` to `value` (raw SQL — the
    CHECK fires regardless of ORM-side Enum validation). Each call runs
    in its own transaction so a rejected INSERT does not poison a later
    one."""
    with engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO tools (slug, name, is_in_manifest, {column}) "
                f"VALUES (:slug, :slug, 1, :value)"
            ),
            {"slug": slug, "value": value},
        )


# ---- Alembic path --------------------------------------------------------


@pytest.mark.parametrize("column,good,bad", _REJECT_CASES)
def test_check_rejects_out_of_enum_value_alembic_path(
    alembic_head_engine, column: str, good: str, bad: str
) -> None:
    """On the production (Alembic) schema: an in-enum write to each
    hardened column succeeds; the paired out-of-enum write is rejected
    by the CHECK with `IntegrityError`."""
    # Paired in-enum write — succeeds. The contrast that proves the test
    # is not vacuously "every INSERT fails".
    _insert_tool(alembic_head_engine, f"ok-{column}", column, good)
    with alembic_head_engine.connect() as conn:
        stored = conn.execute(
            text(f"SELECT {column} FROM tools WHERE slug = :s"),
            {"s": f"ok-{column}"},
        ).scalar()
    assert stored == good

    # Out-of-enum write — rejected at the door by the CHECK.
    with pytest.raises(IntegrityError):
        _insert_tool(alembic_head_engine, f"bad-{column}", column, bad)


def test_check_allows_null_tool_type_alembic_path(alembic_head_engine) -> None:
    """`tool_type` is nullable; the CHECK is `tool_type IN (...)`, which
    `NULL` passes (`NULL IN (...)` → `NULL`, and a CHECK only rejects on
    `FALSE`). The 3 live NULL `tool_type` rows depend on this."""
    _insert_tool(alembic_head_engine, "null-tt", "tool_type", None)
    with alembic_head_engine.connect() as conn:
        stored = conn.execute(
            text("SELECT tool_type FROM tools WHERE slug = 'null-tt'")
        ).scalar()
    assert stored is None


# ---- create_all path -----------------------------------------------------


@pytest.mark.parametrize("column,good,bad", _REJECT_CASES)
def test_check_rejects_out_of_enum_value_create_all_path(
    create_all_engine, column: str, good: str, bad: str
) -> None:
    """Same proof on the `Base.metadata.create_all` schema — pins the
    model's `Enum(..., create_constraint=True)` declarations directly,
    independently of the Alembic path (OD-2)."""
    _insert_tool(create_all_engine, f"ok-{column}", column, good)
    with create_all_engine.connect() as conn:
        stored = conn.execute(
            text(f"SELECT {column} FROM tools WHERE slug = :s"),
            {"s": f"ok-{column}"},
        ).scalar()
    assert stored == good

    with pytest.raises(IntegrityError):
        _insert_tool(create_all_engine, f"bad-{column}", column, bad)


def test_check_allows_null_tool_type_create_all_path(create_all_engine) -> None:
    """`NULL` `tool_type` passes the CHECK on the `create_all` schema."""
    _insert_tool(create_all_engine, "null-tt", "tool_type", None)
    with create_all_engine.connect() as conn:
        stored = conn.execute(
            text("SELECT tool_type FROM tools WHERE slug = 'null-tt'")
        ).scalar()
    assert stored is None
