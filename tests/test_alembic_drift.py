"""Guard against divergence between the Alembic migration path (production)
and `Base.metadata.create_all()` (test fixtures).

Rationale — DECISIONS `[2026-04-24 Fix Day 1]` (Alembic owns schema):
`init_db()` / `Base.metadata.create_all()` survives only as a per-test fast
path. Production runs `alembic upgrade head` at startup. The two are
guaranteed to match only at baseline; from the moment a new migration lands,
drift is possible: someone could add a column to `core/db/models.py` without
emitting a revision, tests would still pass (create_all picks up the model
change), and production would ship stale schema. This test exercises the
Alembic path against a fresh SQLite, reflects the resulting schema, and
compares against `Base.metadata.create_all()`'s output.

It compares table set, per-table columns (name + normalized type), per-table
indexes (name + columns + uniqueness), and per-table FKs (constrained
columns → referred table + columns). Enum types compile to
`VARCHAR(N)` + CHECK in SQLite; both paths produce the same VARCHAR so the
normalized-type comparison stays stable. The `alembic_version` bookkeeping
table is excluded since it only exists on the migration path.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from core.config import get_settings
from core.db.base import Base
from core.db import models  # noqa: F401 — register models on Base.metadata


def _normalize_type(col_type) -> str:
    return str(col_type).upper()


def _reflect_schema(engine) -> dict[str, dict]:
    inspector = inspect(engine)
    schema: dict[str, dict] = {}
    for table_name in inspector.get_table_names():
        if table_name.startswith("alembic_"):
            continue
        columns = {
            col["name"]: _normalize_type(col["type"])
            for col in inspector.get_columns(table_name)
        }
        indexes = frozenset(
            (ix["name"], tuple(sorted(ix["column_names"])), bool(ix["unique"]))
            for ix in inspector.get_indexes(table_name)
        )
        fks = frozenset(
            (
                tuple(sorted(fk["constrained_columns"])),
                fk["referred_table"],
                tuple(sorted(fk["referred_columns"])),
            )
            for fk in inspector.get_foreign_keys(table_name)
        )
        schema[table_name] = {"columns": columns, "indexes": indexes, "fks": fks}
    return schema


def _assert_schemas_equal(
    alembic_schema: dict[str, dict], metadata_schema: dict[str, dict]
) -> None:
    alembic_tables = set(alembic_schema)
    metadata_tables = set(metadata_schema)

    only_in_alembic = alembic_tables - metadata_tables
    only_in_metadata = metadata_tables - alembic_tables
    assert not only_in_alembic, (
        f"Tables exist in Alembic path but not in models.py "
        f"(obsolete migration?): {sorted(only_in_alembic)}"
    )
    assert not only_in_metadata, (
        f"Tables exist in models.py but not in Alembic migrations "
        f"(missing revision?): {sorted(only_in_metadata)}"
    )

    for table in sorted(alembic_tables):
        a = alembic_schema[table]
        m = metadata_schema[table]

        col_diffs: list[str] = []
        for name in sorted(set(a["columns"]) | set(m["columns"])):
            a_type = a["columns"].get(name)
            m_type = m["columns"].get(name)
            if a_type is None:
                col_diffs.append(f"    {name}: missing from Alembic path")
            elif m_type is None:
                col_diffs.append(f"    {name}: missing from models.py")
            elif a_type != m_type:
                col_diffs.append(
                    f"    {name}: Alembic={a_type!r} vs models={m_type!r}"
                )
        assert not col_diffs, (
            f"Column drift on '{table}':\n" + "\n".join(col_diffs)
        )

        if a["indexes"] != m["indexes"]:
            only_a = a["indexes"] - m["indexes"]
            only_m = m["indexes"] - a["indexes"]
            raise AssertionError(
                f"Index drift on '{table}':\n"
                f"  only in Alembic path: {sorted(only_a)}\n"
                f"  only in models.py: {sorted(only_m)}"
            )

        assert a["fks"] == m["fks"], (
            f"Foreign-key drift on '{table}':\n"
            f"  Alembic: {sorted(a['fks'])}\n"
            f"  models: {sorted(m['fks'])}"
        )


def test_alembic_matches_metadata_create_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alembic_db = tmp_path / "alembic.db"
    metadata_db = tmp_path / "metadata.db"

    monkeypatch.setenv("CONCIERGE_DATABASE_PATH", str(alembic_db))
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.database_path == alembic_db

        cfg = Config(str(settings.project_root / "alembic.ini"))
        command.upgrade(cfg, "head")

        alembic_engine = create_engine(f"sqlite:///{alembic_db}")
        try:
            alembic_schema = _reflect_schema(alembic_engine)
        finally:
            alembic_engine.dispose()
    finally:
        get_settings.cache_clear()

    metadata_engine = create_engine(f"sqlite:///{metadata_db}")
    try:
        Base.metadata.create_all(metadata_engine)
        metadata_schema = _reflect_schema(metadata_engine)
    finally:
        metadata_engine.dispose()

    assert alembic_schema, "Alembic path produced zero tables — bootstrap broken?"
    assert metadata_schema, "metadata.create_all produced zero tables — Base import broken?"

    _assert_schemas_equal(alembic_schema, metadata_schema)


def test_request_escalation_target_migration_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage 1A item 5 — operator watch item: pin the migration
    upgrade → downgrade → upgrade symmetry for
    `e17b8137cade_add_request_escalation_target`.

    The migration is structurally simple (one column add + one
    index) so the downgrade is the inverse (drop index, drop
    column) and the second upgrade should land at the same schema
    as the first. Pinning the symmetry here catches any future edit
    that drifts the up/down inverse relationship — same shape as
    items-4+7's lifecycle_state migration round-trip discipline
    pinned implicitly at items-4+7 close.
    """
    db = tmp_path / "alembic_roundtrip.db"

    monkeypatch.setenv("CONCIERGE_DATABASE_PATH", str(db))
    get_settings.cache_clear()
    try:
        settings = get_settings()
        cfg = Config(str(settings.project_root / "alembic.ini"))

        # First upgrade to head — captures the post-migration schema.
        command.upgrade(cfg, "head")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_first_upgrade = _reflect_schema(engine)
        finally:
            engine.dispose()

        # Downgrade one revision (undo item 5's migration).
        command.downgrade(cfg, "-1")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_downgrade = _reflect_schema(engine)
        finally:
            engine.dispose()

        # Re-upgrade to head — should land at the same schema as the
        # first upgrade.
        command.upgrade(cfg, "head")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_second_upgrade = _reflect_schema(engine)
        finally:
            engine.dispose()
    finally:
        get_settings.cache_clear()

    # Downgrade actually removed the column.
    assert "escalation_target" in after_first_upgrade["requests"]["columns"]
    assert "escalation_target" not in after_downgrade["requests"]["columns"]
    # Downgrade also removed the index (same name, key check).
    after_downgrade_index_names = {
        idx[0] for idx in after_downgrade["requests"]["indexes"]
    }
    assert "ix_requests_escalation_target" not in after_downgrade_index_names

    # Symmetry: second upgrade matches first upgrade. The full
    # `requests` table schema (columns + indexes + fks) must round-trip
    # byte-for-byte through downgrade-then-upgrade.
    assert after_first_upgrade == after_second_upgrade, (
        "Migration round-trip drift detected. Expected the schema "
        "after downgrade-then-upgrade to match the schema after the "
        "first upgrade. Inspect e17b8137cade for asymmetric up/down."
    )


def test_alembic_drift_detector_catches_injected_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Meta-test: proves the comparator rejects drift it should reject.

    If this test ever starts passing against identical schemas, the
    comparator has been weakened and real drift could slip through.
    """
    alembic_db = tmp_path / "alembic.db"
    metadata_db = tmp_path / "metadata.db"

    monkeypatch.setenv("CONCIERGE_DATABASE_PATH", str(alembic_db))
    get_settings.cache_clear()
    try:
        settings = get_settings()
        cfg = Config(str(settings.project_root / "alembic.ini"))
        command.upgrade(cfg, "head")

        alembic_engine = create_engine(f"sqlite:///{alembic_db}")
        try:
            alembic_schema = _reflect_schema(alembic_engine)
        finally:
            alembic_engine.dispose()
    finally:
        get_settings.cache_clear()

    metadata_engine = create_engine(f"sqlite:///{metadata_db}")
    try:
        Base.metadata.create_all(metadata_engine)
        metadata_schema = _reflect_schema(metadata_engine)
    finally:
        metadata_engine.dispose()

    metadata_schema["tools"]["columns"]["phantom_drift_column"] = "TEXT"

    with pytest.raises(AssertionError, match="phantom_drift_column"):
        _assert_schemas_equal(alembic_schema, metadata_schema)
