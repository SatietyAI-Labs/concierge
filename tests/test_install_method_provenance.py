"""Wiring tests for Decision C+D install_method_provenance backfill.

Per ratified wiring-test discipline (`planning/concierge-operations-protocol.md`
"Wiring-test discipline" section), four coverage points:

  1. Multiple `pip-user` rows in seed catalog tagged
     `pre-option-3-user-site`.
  2. Non-`pip-user` rows tagged with their respective method
     (`npm-global` / `npx-mcp` / `single-binary`); `NULL` /
     non-canonical install_method rows (`mcp-server`, `apt`, etc.)
     keep `NULL` provenance. Strict assertion: future contributor
     adding a fifth Option-3-relevant method without updating the
     migration's coverage trips this test.
  3. Idempotency — re-running the data migration is a no-op (rowcount
     0 on second run; post-Option-3 rows already transitioned to
     `option-3-venv` are not clobbered back to `pre-option-3-user-site`).
  4. Post-Option-3 install through `_maybe_install_on_approve` writes
     `install_method_provenance` to the corresponding Tool row.
     Coverage 4 reads provenance from a FRESH sessionmaker against the
     same engine post-install — not from the session the install
     used. Reading from the same session would let autoflush mask a
     missing commit (the failure mode that broke Day 5's telemetry
     path; see `tests/test_recommend_endpoint_persistence.py`).

The data-migration logic is extracted to `core.install.provenance` so
both the Alembic upgrade and these tests call the same code without
either side reaching into the migration file's module namespace.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.db.base import Base
from core.db import models  # noqa: F401 — register models on Base.metadata
from core.db.models import Tool
from core.install.provenance import (
    PROVENANCE_BY_RESULT_METHOD,
    apply_install_method_provenance_backfill,
)
from core.install.schemas import InstallResult
from core.lifecycle_store.schema import NewRequestDraft, StatusChange
from core.lifecycle_store.service import LifecycleService


# ---- Fixtures ------------------------------------------------------------


@pytest.fixture
def shared_engine() -> Iterator[Engine]:
    """In-memory SQLite shared across sessions. StaticPool keeps the
    one connection alive so multiple sessions see the same DB.
    Same pattern as `tests/test_recommend_endpoint_persistence.py`.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture
def session_factory(shared_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=shared_engine, autocommit=False, autoflush=True)


@pytest.fixture
def seeded_pre_migration(session_factory: sessionmaker[Session]) -> None:
    """Seed the catalog with rows representing state BEFORE Decision
    C+D backfill. Mix of canonical install_method values + NULL +
    non-canonical (mcp-server, apt) so the wiring test can assert
    strictly which rows get tagged and which don't.

    All rows have `install_method_provenance=None` initially — the
    column's nullable default. Backfill is what populates it.
    """
    rows = [
        # Two pip-user rows (coverage 1).
        Tool(slug="pyflakes", name="pyflakes", install_method="pip-user",
             lifecycle_state="discovered"),
        Tool(slug="black", name="black", install_method="pip-user",
             lifecycle_state="loaded-on-boot"),
        # One npm-global row (coverage 2).
        Tool(slug="prettier", name="prettier", install_method="npm-global",
             lifecycle_state="discovered"),
        # One npx-mcp row (coverage 2).
        Tool(slug="some-mcp", name="some-mcp", install_method="npx-mcp",
             lifecycle_state="discovered"),
        # One binary row (coverage 2).
        Tool(slug="xsv", name="xsv", install_method="binary",
             lifecycle_state="discovered"),
        # NULL install_method (coverage 2 strict assertion).
        Tool(slug="declared-no-method", name="declared-no-method",
             install_method=None, lifecycle_state="discovered"),
        # mcp-server install_method — legitimate ingest value outside
        # Option 3 scope (coverage 2 strict assertion).
        Tool(slug="some-mcp-server", name="some-mcp-server",
             install_method="mcp-server", lifecycle_state="discovered"),
        # apt install_method — legitimate ingest value outside Option 3
        # scope (coverage 2 strict assertion).
        Tool(slug="apt-installed", name="apt-installed",
             install_method="apt", lifecycle_state="discovered"),
    ]
    with session_factory() as seed:
        for row in rows:
            seed.add(row)
        seed.commit()


# ---- Coverage 1 + 2: legacy backfill --------------------------------------


class TestBackfillCoversCanonicalMethodsOnly:
    """Coverage 1 + 2: pip-user / npm-global / npx-mcp / binary rows
    get tagged with their explicit provenance value; NULL /
    mcp-server / apt rows keep NULL provenance.
    """

    def test_pip_user_rows_tagged_pre_option_3_user_site(
        self, shared_engine, session_factory, seeded_pre_migration
    ):
        with shared_engine.begin() as conn:
            apply_install_method_provenance_backfill(conn)

        with session_factory() as fresh:
            pyflakes = fresh.query(Tool).filter_by(slug="pyflakes").one()
            black = fresh.query(Tool).filter_by(slug="black").one()

        assert pyflakes.install_method_provenance == "pre-option-3-user-site"
        assert black.install_method_provenance == "pre-option-3-user-site"

    def test_non_pip_user_rows_tagged_with_their_method(
        self, shared_engine, session_factory, seeded_pre_migration
    ):
        with shared_engine.begin() as conn:
            apply_install_method_provenance_backfill(conn)

        with session_factory() as fresh:
            prettier = fresh.query(Tool).filter_by(slug="prettier").one()
            some_mcp = fresh.query(Tool).filter_by(slug="some-mcp").one()
            xsv = fresh.query(Tool).filter_by(slug="xsv").one()

        assert prettier.install_method_provenance == "npm-global"
        assert some_mcp.install_method_provenance == "npx-mcp"
        assert xsv.install_method_provenance == "single-binary"

    def test_null_and_non_canonical_install_method_keep_null_provenance(
        self, shared_engine, session_factory, seeded_pre_migration
    ):
        """Strict assertion: rows with NULL / mcp-server / apt
        install_method MUST keep NULL provenance after backfill.
        A future contributor adding a fifth Option-3-relevant method
        without updating apply_install_method_provenance_backfill
        trips this test.
        """
        with shared_engine.begin() as conn:
            apply_install_method_provenance_backfill(conn)

        with session_factory() as fresh:
            declared_no_method = (
                fresh.query(Tool).filter_by(slug="declared-no-method").one()
            )
            mcp_server = fresh.query(Tool).filter_by(slug="some-mcp-server").one()
            apt = fresh.query(Tool).filter_by(slug="apt-installed").one()

        assert declared_no_method.install_method_provenance is None
        assert mcp_server.install_method_provenance is None
        assert apt.install_method_provenance is None


# ---- Coverage 3: idempotency ---------------------------------------------


class TestBackfillIsIdempotent:
    """Coverage 3: re-running the data migration is a no-op. The
    explicit `WHERE install_method_provenance IS NULL` guard in
    `apply_install_method_provenance_backfill` enforces this at the
    SQL level — defense-in-depth beyond Alembic's "completed
    migrations don't re-run" bookkeeping.
    """

    def test_second_run_does_not_change_any_rows(
        self, shared_engine, session_factory, seeded_pre_migration
    ):
        with shared_engine.begin() as conn:
            apply_install_method_provenance_backfill(conn)

        with session_factory() as fresh:
            first_state = {
                t.slug: t.install_method_provenance
                for t in fresh.query(Tool).all()
            }

        with shared_engine.begin() as conn:
            apply_install_method_provenance_backfill(conn)

        with session_factory() as fresh:
            second_state = {
                t.slug: t.install_method_provenance
                for t in fresh.query(Tool).all()
            }

        assert first_state == second_state

    def test_post_option_3_rows_not_clobbered_on_rerun(
        self, shared_engine, session_factory, seeded_pre_migration
    ):
        """If a pip-user row has already transitioned to
        `option-3-venv` (post-Option-3 install), a re-run of the
        backfill MUST NOT clobber it back to `pre-option-3-user-site`.
        The explicit `WHERE install_method_provenance IS NULL` guard
        enforces this.
        """
        with shared_engine.begin() as conn:
            apply_install_method_provenance_backfill(conn)

        with session_factory() as s:
            pyflakes = s.query(Tool).filter_by(slug="pyflakes").one()
            pyflakes.install_method_provenance = "option-3-venv"
            s.commit()

        with shared_engine.begin() as conn:
            apply_install_method_provenance_backfill(conn)

        with session_factory() as fresh:
            pyflakes = fresh.query(Tool).filter_by(slug="pyflakes").one()

        assert pyflakes.install_method_provenance == "option-3-venv", (
            "Post-Option-3 row was clobbered by re-run. The "
            "`AND install_method_provenance IS NULL` guard in "
            "apply_install_method_provenance_backfill is missing or broken."
        )


# ---- Coverage 4: install wiring closes the loop ---------------------------


def _stub_install_dispatcher(*, method: str, success: bool = True):
    """Build an install-dispatcher stub returning a synthetic
    InstallResult for the given method. Same shape as
    `tests/test_integration_full_cycle.py::_stub_install_dispatcher`.
    Mocks only the subprocess layer — the actual subprocess execution
    is already covered by Day 6's TestRealVenvBootstrap; this test
    pins the *persistent-state contract* (success result → DB write
    on the corresponding Tool row).
    """
    def dispatcher(install_method, *, tool_name, **kwargs):
        return InstallResult(
            method=method,
            command=f"<stub install for {tool_name} via {method}>",
            success=success,
            returncode=0 if success else 1,
            stdout="stubbed",
            stderr="",
            elapsed_ms=10,
        )
    return dispatcher


@pytest.fixture
def lifecycle_root(tmp_path: Path) -> Path:
    for folder in ("pending", "resolved", "archived"):
        (tmp_path / folder).mkdir()
    return tmp_path


class TestInstallWiringSetsPostOption3Provenance:
    """Coverage 4: post-Option-3 install through
    `_maybe_install_on_approve` writes `install_method_provenance` to
    the corresponding Tool row.

    Provenance read from a FRESH sessionmaker against the same engine
    post-install (per Day 5 telemetry-commit fix pattern in
    `tests/test_recommend_endpoint_persistence.py`). Reading from the
    same session would let autoflush mask a missing commit.

    Two subtests:
      a) pip-user install → 'option-3-venv' provenance
      b) npm-global install → 'npm-global' provenance

    Subtest (b) guards against the failure mode "wiring change covers
    pip-user only and silently drops the other three methods" — if
    PROVENANCE_BY_RESULT_METHOD ever loses an entry, this trips.
    """

    def _approve_request_through_lifecycle(
        self,
        *,
        session: Session,
        lifecycle_root: Path,
        tool_name: str,
        install_method: str,
        result_method: str,
    ) -> None:
        """Drive a request from create → approve → install via
        LifecycleService with a stub dispatcher. Mirrors the create →
        approve flow in `tests/test_integration_full_cycle.py`.
        """
        svc = LifecycleService(
            session=session,
            lifecycle_root=lifecycle_root,
            install_dispatcher=_stub_install_dispatcher(
                method=result_method, success=True
            ),
        )
        draft = NewRequestDraft(
            tool_name=tool_name,
            install_method=install_method,
            task_context="provenance wiring test",
            confidence="high",
        )
        detail = svc.create_request(draft)
        approve_result = svc.update_status(
            filename=detail.filename,
            change=StatusChange(status="approved"),
        )
        assert approve_result.status == "installed", (
            f"expected install-on-approve to transition to 'installed', "
            f"got {approve_result.status!r}"
        )

    def test_pip_user_install_sets_option_3_venv_provenance(
        self, shared_engine, session_factory, lifecycle_root
    ):
        # Seed the Tool row the install will target. Pre-existing
        # catalog state with no provenance set yet.
        with session_factory() as seed:
            seed.add(
                Tool(
                    slug="pyflakes",
                    name="pyflakes",
                    install_method="pip-user",
                    lifecycle_state="discovered",
                )
            )
            seed.commit()

        # Drive the install via a session that LifecycleService owns.
        with session_factory() as install_session:
            self._approve_request_through_lifecycle(
                session=install_session,
                lifecycle_root=lifecycle_root,
                tool_name="pyflakes",
                install_method="pip-user",
                result_method="pip_user",  # dispatcher canonical (underscore)
            )

        # Fresh session reads only committed state — the load-bearing
        # detail (Day 5 pattern). If LifecycleService forgot to commit
        # the provenance write, this returns None and the assertion
        # below catches the regression.
        with session_factory() as fresh:
            pyflakes = fresh.query(Tool).filter_by(slug="pyflakes").one()

        assert pyflakes.install_method_provenance == "option-3-venv", (
            f"expected 'option-3-venv', got "
            f"{pyflakes.install_method_provenance!r}. The "
            f"_maybe_install_on_approve wiring change for "
            f"install_method_provenance is missing or broken."
        )

    def test_npm_global_install_sets_npm_global_provenance(
        self, shared_engine, session_factory, lifecycle_root
    ):
        """Guard against the failure mode 'wiring change covers
        pip-user only and silently drops the other three methods.'
        """
        with session_factory() as seed:
            seed.add(
                Tool(
                    slug="prettier",
                    name="prettier",
                    install_method="npm-global",
                    lifecycle_state="discovered",
                )
            )
            seed.commit()

        with session_factory() as install_session:
            self._approve_request_through_lifecycle(
                session=install_session,
                lifecycle_root=lifecycle_root,
                tool_name="prettier",
                install_method="npm-global",
                result_method="npm_global",  # dispatcher canonical (underscore)
            )

        with session_factory() as fresh:
            prettier = fresh.query(Tool).filter_by(slug="prettier").one()

        assert prettier.install_method_provenance == "npm-global", (
            f"expected 'npm-global', got "
            f"{prettier.install_method_provenance!r}. Check "
            f"PROVENANCE_BY_RESULT_METHOD covers all five canonical "
            f"InstallResult.method values."
        )


# ---- Map-coverage sanity check -------------------------------------------


class TestProvenanceMapCoversAllFiveMethods:
    """Sanity: PROVENANCE_BY_RESULT_METHOD must cover all five
    InstallResult.method canonical values. A regression dropping a
    method from the map would silently leave that method's installs
    unprovenance'd.
    """

    def test_map_keys_match_install_method_constants(self):
        from core.install.methods import (
            METHOD_NPM_GLOBAL,
            METHOD_NPX_MCP,
            METHOD_PIP_USER,
            METHOD_PIPX,
            METHOD_SINGLE_BINARY,
        )

        assert set(PROVENANCE_BY_RESULT_METHOD.keys()) == {
            METHOD_PIP_USER,
            METHOD_NPM_GLOBAL,
            METHOD_NPX_MCP,
            METHOD_SINGLE_BINARY,
            METHOD_PIPX,
        }

    def test_pip_user_uniquely_maps_to_post_option_3_marker(self):
        """The pip-user row's provenance value distinguishes
        post-Option-3 ('option-3-venv') from pre-Option-3
        ('pre-option-3-user-site' set by backfill). The other four
        methods' provenance values are method-name-equivalent because
        Option 3 doesn't affect them — pipx in particular has its own
        per-package venv mechanism, distinct from Option 3.
        """
        assert PROVENANCE_BY_RESULT_METHOD["pip_user"] == "option-3-venv"
        assert PROVENANCE_BY_RESULT_METHOD["npm_global"] == "npm-global"
        assert PROVENANCE_BY_RESULT_METHOD["npx_mcp"] == "npx-mcp"
        assert PROVENANCE_BY_RESULT_METHOD["single_binary"] == "single-binary"
        assert PROVENANCE_BY_RESULT_METHOD["pipx"] == "pipx"
