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
indexes (name + columns + uniqueness), per-table FKs (constrained
columns → referred table + columns), and per-table CHECK constraints (name +
whitespace-normalized SQL text). Enum types compile to `VARCHAR(N)` + a CHECK
constraint in SQLite when `create_constraint=True` — the three `tools` Enum
columns, since the Stage 1B Enum CHECK-hardening slice (DECISIONS D110); both
paths produce the same VARCHAR and the same CHECK, so the comparison stays
stable. (Before D110 the Enum columns were plain `VARCHAR` with no CHECK and
this comparator ignored CHECK constraints entirely — a blind spot the D110
slice closed, since a migration that forgot a CHECK would otherwise pass.)
The `alembic_version` bookkeeping table is excluded since it only exists on
the migration path.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from core.config import get_settings
from core.db.base import Base
from core.db import models  # noqa: F401 — register models on Base.metadata


def _normalize_type(col_type) -> str:
    return str(col_type).upper()


def _normalize_check_sql(sqltext: str | None) -> str:
    """Normalize a reflected CHECK constraint's SQL text for comparison.

    SQLite renders CHECK SQL with cosmetic variation — whitespace around
    operators and after commas. Collapsing every run of whitespace makes
    the comparison robust to that rendering noise while staying sensitive
    to a real difference: a changed value list, operator, or column name
    survives normalization and is still caught.
    """
    return "".join((sqltext or "").split())


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
        checks = frozenset(
            (ck["name"], _normalize_check_sql(ck["sqltext"]))
            for ck in inspector.get_check_constraints(table_name)
        )
        schema[table_name] = {
            "columns": columns,
            "indexes": indexes,
            "fks": fks,
            "checks": checks,
        }
    return schema


def _column_ddl(engine, table: str, column: str) -> dict | None:
    """Reflected DDL shape of one column — normalized type, nullability,
    and server default. `_reflect_schema` captures only name→type; this
    is the finer-grained view needed to assert a migration restored a
    column to a specific DDL (not merely that the column is present).
    Returns None when the column is absent.
    """
    for col in inspect(engine).get_columns(table):
        if col["name"] == column:
            return {
                "type": _normalize_type(col["type"]),
                "nullable": col["nullable"],
                "server_default": col["default"],
            }
    return None


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

        if a["checks"] != m["checks"]:
            only_a = a["checks"] - m["checks"]
            only_m = m["checks"] - a["checks"]
            raise AssertionError(
                f"CHECK-constraint drift on '{table}':\n"
                f"  only in Alembic path: {sorted(only_a)}\n"
                f"  only in models.py: {sorted(only_m)}"
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

    Downgrades to `fa46ebdf05b9` (e17b8137cade's down_revision) by
    explicit name rather than the relative `-1`: once later
    migrations stack on top of e17b8137cade, `-1` from head no
    longer targets this migration. Targeting the down_revision by
    name keeps the round-trip pinned on e17b8137cade regardless of
    how many revisions follow it (the Stage 1B reconciliation slice
    added the first such follow-on, `c9d2f7a4e10b`).
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

        # Downgrade to e17b8137cade's down_revision — undoes item 5's
        # migration (and any revisions stacked above it).
        command.downgrade(cfg, "fa46ebdf05b9")
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


def test_on_demand_lifecycle_state_migration_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage 1B reconciliation slice, Phase A0 — pin the migration
    round-trip for `c9d2f7a4e10b_add_on_demand_lifecycle_state` and
    exercise its downgrade demotion guard with a real row.

    The Concierge `Enum` columns carry no DB-level CHECK constraint
    (SQLAlchemy 2.x `Enum` defaults to `create_constraint=False`;
    `lifecycle_state` is a plain `VARCHAR(16)` — see the c9d2f7a4e10b
    docstring). So the migration's `upgrade()` is a schema-level no-op
    on SQLite, and the reflected schema is identical at head and at
    the down_revision — asserted below as the round-trip invariant.

    The one observable effect is `downgrade()`'s data-hygiene UPDATE:
    a seeded `on-demand` row is demoted to `discovered` so no row
    carries a value the code-at-that-revision no longer knows. This
    test seeds such a row and confirms the demotion — the first real
    exercise of the `on-demand` downgrade guard.

    Upgrades to `c9d2f7a4e10b` explicitly (the revision under test —
    not `head`) and downgrades to `e17b8137cade` (its down_revision)
    by name. Targeting both endpoints by revision rather than `head` /
    `-1` isolates this one migration's round-trip regardless of how
    many revisions stack on top of it — Phase A's `d8a3f0b62c14`
    pin_status migration is the first such follow-on.
    """
    db = tmp_path / "alembic_on_demand_roundtrip.db"

    monkeypatch.setenv("CONCIERGE_DATABASE_PATH", str(db))
    get_settings.cache_clear()
    try:
        settings = get_settings()
        cfg = Config(str(settings.project_root / "alembic.ini"))

        # First upgrade to the revision under test — the 7-value Enum
        # model is in place.
        command.upgrade(cfg, "c9d2f7a4e10b")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_first_upgrade = _reflect_schema(engine)
            # Seed a real on-demand row so the downgrade guard has
            # something to demote.
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO tools "
                        "(slug, name, lifecycle_state, is_in_manifest, is_active) "
                        "VALUES ('od-probe', 'od-probe', 'on-demand', 1, 0)"
                    )
                )
        finally:
            engine.dispose()

        # Downgrade to this migration's down_revision by name.
        command.downgrade(cfg, "e17b8137cade")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_downgrade = _reflect_schema(engine)
            with engine.connect() as conn:
                probe_state_after_downgrade = conn.execute(
                    text(
                        "SELECT lifecycle_state FROM tools "
                        "WHERE slug = 'od-probe'"
                    )
                ).scalar()
        finally:
            engine.dispose()

        # Re-upgrade to the revision under test — should land at the
        # same schema as the first upgrade.
        command.upgrade(cfg, "c9d2f7a4e10b")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_second_upgrade = _reflect_schema(engine)
        finally:
            engine.dispose()
    finally:
        get_settings.cache_clear()

    # The downgrade's data-hygiene guard demoted the seeded `on-demand`
    # row to `discovered` — the row no longer carries a value the
    # reverted (6-value) code knows nothing about.
    assert probe_state_after_downgrade == "discovered"

    # Symmetry: second upgrade matches first upgrade — the `tools`
    # schema round-trips through downgrade-then-upgrade.
    assert after_first_upgrade == after_second_upgrade, (
        "Migration round-trip drift detected. Inspect c9d2f7a4e10b "
        "for asymmetric up/down."
    )
    # The migration is schema-invisible on SQLite (the Enum carries no
    # CHECK; `lifecycle_state` stays `VARCHAR(16)` — `pending-decision`
    # remains the longest value). The reflected schema at the
    # down_revision is therefore identical to head; pinning that here
    # documents the no-op and would catch a future edit that made the
    # migration accidentally schema-affecting.
    assert after_downgrade == after_first_upgrade


def test_pin_status_migration_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage 1B reconciliation slice, Phase A — pin the migration
    round-trip for `d8a3f0b62c14_add_tool_pin_status`.

    Unlike the `on-demand` migration (a schema-level no-op — an Enum
    value-set change with no CHECK), this one is a real schema change:
    it adds the `pin_status` column and the `ix_tools_pin_status`
    index. The downgrade is the inverse (drop index, drop column) and
    the second upgrade must land at the same schema as the first.

    Upgrades to `d8a3f0b62c14` and downgrades to `c9d2f7a4e10b` (its
    down_revision) by explicit revision name — stable regardless of
    later migrations stacking on top.
    """
    db = tmp_path / "alembic_pin_status_roundtrip.db"

    monkeypatch.setenv("CONCIERGE_DATABASE_PATH", str(db))
    get_settings.cache_clear()
    try:
        settings = get_settings()
        cfg = Config(str(settings.project_root / "alembic.ini"))

        command.upgrade(cfg, "d8a3f0b62c14")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_first_upgrade = _reflect_schema(engine)
        finally:
            engine.dispose()

        command.downgrade(cfg, "c9d2f7a4e10b")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_downgrade = _reflect_schema(engine)
        finally:
            engine.dispose()

        command.upgrade(cfg, "d8a3f0b62c14")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_second_upgrade = _reflect_schema(engine)
        finally:
            engine.dispose()
    finally:
        get_settings.cache_clear()

    # Upgrade added the column; downgrade removed it.
    assert "pin_status" in after_first_upgrade["tools"]["columns"]
    assert "pin_status" not in after_downgrade["tools"]["columns"]
    # Upgrade added the index; downgrade removed it.
    after_upgrade_index_names = {
        idx[0] for idx in after_first_upgrade["tools"]["indexes"]
    }
    after_downgrade_index_names = {
        idx[0] for idx in after_downgrade["tools"]["indexes"]
    }
    assert "ix_tools_pin_status" in after_upgrade_index_names
    assert "ix_tools_pin_status" not in after_downgrade_index_names

    # Symmetry: second upgrade matches first upgrade — the `tools`
    # table schema round-trips byte-for-byte.
    assert after_first_upgrade == after_second_upgrade, (
        "Migration round-trip drift detected. Inspect d8a3f0b62c14 "
        "for asymmetric up/down."
    )


def test_drop_is_active_migration_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage 1B `is_active`-retirement slice, Phase B — pin the migration
    round-trip for `771ddc8fcccf_drop_tools_is_active_column`.

    The inverse of the pin_status migration: upgrade DROPS the
    `is_active` column and the `ix_tools_is_active` index; downgrade
    re-adds both and backfills
    `is_active = (lifecycle_state == 'loaded-on-boot')` — the manifest.py
    derivation, the only principled one (the downgrade is documented as
    lossy: it cannot recover the original inconsistently-minted values).

    Upgrades to `771ddc8fcccf` and downgrades to `d8a3f0b62c14` (its
    down_revision) by explicit revision name — never relative -1/head —
    so the test is stable regardless of later migrations stacking on top.
    """
    db = tmp_path / "alembic_drop_is_active_roundtrip.db"

    monkeypatch.setenv("CONCIERGE_DATABASE_PATH", str(db))
    get_settings.cache_clear()
    try:
        settings = get_settings()
        cfg = Config(str(settings.project_root / "alembic.ini"))

        # Upgrade to the revision under test — is_active is gone.
        command.upgrade(cfg, "771ddc8fcccf")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_first_upgrade = _reflect_schema(engine)
            # Seed two rows carrying only `lifecycle_state` — the column
            # under test no longer exists to set — so the downgrade
            # backfill has a loaded-on-boot row and a non-boot row to
            # derive `is_active` for.
            with engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO tools "
                    "(slug, name, lifecycle_state, is_in_manifest) VALUES "
                    "('boot-probe', 'boot-probe', 'loaded-on-boot', 1), "
                    "('retired-probe', 'retired-probe', 'retired', 1)"
                ))
        finally:
            engine.dispose()

        # Downgrade to the down_revision by explicit name.
        command.downgrade(cfg, "d8a3f0b62c14")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_downgrade = _reflect_schema(engine)
            downgraded_is_active_ddl = _column_ddl(engine, "tools", "is_active")
            with engine.connect() as conn:
                backfilled = dict(conn.execute(text(
                    "SELECT slug, is_active FROM tools ORDER BY slug"
                )).all())
        finally:
            engine.dispose()

        # Re-upgrade — must land at the same schema as the first upgrade.
        command.upgrade(cfg, "771ddc8fcccf")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_second_upgrade = _reflect_schema(engine)
        finally:
            engine.dispose()
    finally:
        get_settings.cache_clear()

    # Upgrade dropped the column; downgrade restored it.
    assert "is_active" not in after_first_upgrade["tools"]["columns"]
    assert "is_active" in after_downgrade["tools"]["columns"]
    # Upgrade dropped the index; downgrade restored it.
    after_upgrade_index_names = {
        idx[0] for idx in after_first_upgrade["tools"]["indexes"]
    }
    after_downgrade_index_names = {
        idx[0] for idx in after_downgrade["tools"]["indexes"]
    }
    assert "ix_tools_is_active" not in after_upgrade_index_names
    assert "ix_tools_is_active" in after_downgrade_index_names

    # Downgrade backfill: `is_active` is re-derived from `lifecycle_state`
    # — loaded-on-boot → 1, every other state → 0 (the manifest.py rule).
    assert backfilled["boot-probe"] == 1
    assert backfilled["retired-probe"] == 0

    # Downgrade DDL-fidelity — the migration's headline claim. The
    # downgrade re-adds `is_active` via add-NULLABLE → backfill →
    # flip-NOT-NULL precisely to land the baseline (4ff5b5898f71) DDL:
    # `sa.Column("is_active", sa.Boolean(), nullable=False)` — BOOLEAN,
    # NOT NULL, no server default. This is the ONLY coverage of that
    # three-step sequence; it goes red if the downgrade leaves the
    # column NULLABLE (flip step lost) or leaves a residual
    # server_default (e.g. an add-column-with-server_default rewrite).
    assert downgraded_is_active_ddl == {
        "type": "BOOLEAN",
        "nullable": False,
        "server_default": None,
    }

    # Symmetry: second upgrade matches first upgrade — the `tools`
    # table schema round-trips byte-for-byte.
    assert after_first_upgrade == after_second_upgrade, (
        "Migration round-trip drift detected. Inspect 771ddc8fcccf "
        "for asymmetric up/down."
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


def test_enum_check_hardening_migration_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage 1B Enum CHECK-constraint hardening slice (D110) — pin the
    migration round-trip for `103a85689166_harden_tools_enum_columns_
    with_check_constraints`, exercised against a POPULATED `tools` table.

    The risk this slice exists for is a CHECK added over a populated
    table: SQLite has no `ADD CONSTRAINT`, so the batch rebuild creates a
    new `tools`, copies every row through `INSERT ... SELECT`, and the
    new CHECK is enforced on that copy. An empty-table upgrade cannot
    surface a copy-step failure — so this test seeds seven conforming
    boundary rows BEFORE the upgrade: every `lifecycle_state` value, every
    `tool_type` (including `NULL` — the CHECK is `tool_type IN (...)`,
    which `NULL` passes), and both `pin_status` values.

    Upgrades to `103a85689166` and downgrades to `771ddc8fcccf` (its
    down_revision) by explicit revision name — never relative `-1`/`head`
    — so the round-trip stays pinned regardless of later migrations.

    Asserts: the seven rows survive the rebuild intact in every
    direction; the three named CHECK constraints are present after
    upgrade and absent after downgrade, with the exact value lists; the
    `tools` schema round-trips byte-for-byte (the Phase A manual DDL
    check, now a committed assertion).
    """
    db = tmp_path / "alembic_enum_check_roundtrip.db"

    # (slug, lifecycle_state, tool_type, pin_status) — conforming rows
    # covering every boundary value. `tool_type=None` is the NULL probe.
    seed_rows = [
        ("rt-discovered", "discovered", None, "auto-managed"),
        ("rt-pending", "pending", "mcp", "auto-managed"),
        ("rt-used", "used", "cli", "auto-managed"),
        ("rt-loaded", "loaded-on-boot", "http", "always-pinned"),
        ("rt-retired", "retired", "skill", "auto-managed"),
        ("rt-pending-decision", "pending-decision", "mcp", "auto-managed"),
        ("rt-on-demand", "on-demand", "cli", "auto-managed"),
    ]
    expected_rows = {slug: (lcs, tt, ps) for slug, lcs, tt, ps in seed_rows}

    def _snapshot_rows(database: Path) -> dict:
        eng = create_engine(f"sqlite:///{database}")
        try:
            with eng.connect() as conn:
                return {
                    row[0]: (row[1], row[2], row[3])
                    for row in conn.execute(
                        text(
                            "SELECT slug, lifecycle_state, tool_type, "
                            "pin_status FROM tools ORDER BY slug"
                        )
                    ).all()
                }
        finally:
            eng.dispose()

    monkeypatch.setenv("CONCIERGE_DATABASE_PATH", str(db))
    get_settings.cache_clear()
    try:
        settings = get_settings()
        cfg = Config(str(settings.project_root / "alembic.ini"))

        # Upgrade to the down_revision — `tools` exists, no CHECKs yet —
        # then seed the boundary rows the migration's rebuild must copy.
        command.upgrade(cfg, "771ddc8fcccf")
        engine = create_engine(f"sqlite:///{db}")
        try:
            with engine.begin() as conn:
                for slug, lcs, tt, ps in seed_rows:
                    conn.execute(
                        text(
                            "INSERT INTO tools "
                            "(slug, name, is_in_manifest, lifecycle_state, "
                            "tool_type, pin_status) "
                            "VALUES (:slug, :slug, 1, :lcs, :tt, :ps)"
                        ),
                        {"slug": slug, "lcs": lcs, "tt": tt, "ps": ps},
                    )
        finally:
            engine.dispose()

        # Upgrade to the revision under test — the CHECK lands over the
        # seven populated rows via the batch rebuild's move-and-copy.
        command.upgrade(cfg, "103a85689166")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_upgrade = _reflect_schema(engine)
        finally:
            engine.dispose()
        rows_after_upgrade = _snapshot_rows(db)

        # Downgrade to the down_revision by explicit name.
        command.downgrade(cfg, "771ddc8fcccf")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_downgrade = _reflect_schema(engine)
        finally:
            engine.dispose()
        rows_after_downgrade = _snapshot_rows(db)

        # Re-upgrade — must land at the same schema as the first upgrade.
        command.upgrade(cfg, "103a85689166")
        engine = create_engine(f"sqlite:///{db}")
        try:
            after_second_upgrade = _reflect_schema(engine)
        finally:
            engine.dispose()
        rows_after_second_upgrade = _snapshot_rows(db)
    finally:
        get_settings.cache_clear()

    # The seven boundary rows survived the batch rebuild's move-and-copy
    # intact, in every direction — the populated-table risk the slice
    # exists for. The NULL `tool_type` row in particular was not rejected
    # by the `tool_type` CHECK.
    assert rows_after_upgrade == expected_rows
    assert rows_after_downgrade == expected_rows
    assert rows_after_second_upgrade == expected_rows

    # The three named CHECK constraints are present after upgrade ...
    checks_after_upgrade = dict(after_upgrade["tools"]["checks"])
    assert set(checks_after_upgrade) == {
        "tool_type",
        "lifecycle_state",
        "pin_status",
    }
    # ... with the exact value lists (the D124 "assert the headline
    # claim directly" discipline — not merely that a CHECK exists).
    assert checks_after_upgrade["tool_type"] == _normalize_check_sql(
        "tool_type IN ('mcp', 'cli', 'http', 'skill')"
    )
    assert checks_after_upgrade["lifecycle_state"] == _normalize_check_sql(
        "lifecycle_state IN ('discovered', 'pending', 'used', "
        "'loaded-on-boot', 'retired', 'pending-decision', 'on-demand')"
    )
    assert checks_after_upgrade["pin_status"] == _normalize_check_sql(
        "pin_status IN ('always-pinned', 'auto-managed')"
    )
    # ... and absent after downgrade.
    assert after_downgrade["tools"]["checks"] == frozenset()

    # Symmetry: second upgrade matches first upgrade. With _reflect_schema
    # capturing CHECK constraints, this equality covers the CHECK clauses
    # too — the Phase A byte-identical DDL check, now committed.
    assert after_upgrade == after_second_upgrade, (
        "Migration round-trip drift detected. Inspect 103a85689166 "
        "for asymmetric up/down."
    )


def test_alembic_drift_detector_catches_check_constraint_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Meta-test: proves the comparator rejects CHECK-constraint drift.

    The Enum CHECK-hardening slice (D110) made CHECK constraints
    load-bearing schema and extended `_reflect_schema` to capture them.
    Before that the comparator ignored CHECKs entirely — a migration
    that forgot one would pass the drift test. This proves the extension
    bites: drop one CHECK from a matching schema pair and the comparator
    must raise. If this test ever starts passing, the CHECK comparison
    has been weakened and a missing-CHECK migration could slip through.
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

    # Sanity: the matching pair has the three `tools` CHECKs and compares
    # equal — the comparator does not false-positive on identical schemas.
    assert {name for name, _ in alembic_schema["tools"]["checks"]} == {
        "tool_type",
        "lifecycle_state",
        "pin_status",
    }
    _assert_schemas_equal(alembic_schema, metadata_schema)

    # Drop the `lifecycle_state` CHECK from one side — the exact shape of
    # a migration that hardened the model but forgot the CHECK.
    metadata_schema["tools"]["checks"] = frozenset(
        c for c in metadata_schema["tools"]["checks"] if c[0] != "lifecycle_state"
    )
    with pytest.raises(AssertionError, match="CHECK-constraint drift"):
        _assert_schemas_equal(alembic_schema, metadata_schema)


def test_check_sql_normalization_ignores_cosmetic_rendering() -> None:
    """`_normalize_check_sql` collapses cosmetic SQLite rendering noise
    (whitespace around operators / after commas) so the same constraint
    compares equal across the Alembic and `create_all` paths — while a
    real difference (a changed value list) still survives normalization
    and is caught.
    """
    spaced = "lifecycle_state IN ('discovered', 'pending', 'used')"
    tight = "lifecycle_state IN ('discovered','pending','used')"
    extra = "lifecycle_state  IN  ( 'discovered' , 'pending' , 'used' )"
    assert (
        _normalize_check_sql(spaced)
        == _normalize_check_sql(tight)
        == _normalize_check_sql(extra)
    )

    # A genuine difference — one value dropped — is NOT normalized away.
    shorter = "lifecycle_state IN ('discovered', 'pending')"
    assert _normalize_check_sql(spaced) != _normalize_check_sql(shorter)

    # Defensive: a None sqltext normalizes without raising.
    assert _normalize_check_sql(None) == ""
