"""Tests for core/identity.py — identity summary composition + the
loaded-on-boot refresh hook.

Fork 5 ruling (Fix Day 3): the refresh hook fires on ANY transition
INTO or OUT of loaded-on-boot, explicitly including
loaded-on-boot → retired. Losing a tool from the toolbelt is identity-
relevant signal in the same way as gaining one.
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.db.base import Base
from core.db import models  # noqa: F401 — register on Base.metadata
from core.db.models import Tool
from core.identity import (
    compose_identity_summary,
    refresh_identity_on_loaded_on_boot_change,
)
from core.tool_transitions import transition_tool_lifecycle


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    s = factory()
    try:
        yield s
    finally:
        s.close()


def _tool(
    slug: str, *, tool_type: str = "cli", state: str = "discovered"
) -> Tool:
    return Tool(slug=slug, name=slug, tool_type=tool_type, lifecycle_state=state)


# ---- compose_identity_summary --------------------------------------------


class TestComposeIdentitySummary:
    def test_empty_db_returns_default_sentinel(self, session: Session):
        assert compose_identity_summary(session) == (
            "No tools currently loaded on boot."
        )

    def test_only_non_loaded_rows_returns_default_sentinel(
        self, session: Session
    ):
        session.add_all(
            [
                _tool("a", state="discovered"),
                _tool("b", state="used"),
                _tool("c", state="retired"),
            ]
        )
        session.commit()
        assert compose_identity_summary(session) == (
            "No tools currently loaded on boot."
        )

    def test_loaded_tools_grouped_by_type(self, session: Session):
        session.add_all(
            [
                _tool("csvkit", tool_type="cli", state="loaded-on-boot"),
                _tool("ripgrep", tool_type="cli", state="loaded-on-boot"),
                _tool(
                    "firefox-mcp",
                    tool_type="mcp",
                    state="loaded-on-boot",
                ),
                _tool("unused", tool_type="cli", state="discovered"),
            ]
        )
        session.commit()
        summary = compose_identity_summary(session)
        assert "3 total" in summary
        # CLI group: alphabetical by slug
        assert "cli: csvkit, ripgrep" in summary
        assert "mcp: firefox-mcp" in summary
        # Non-loaded row not referenced
        assert "unused" not in summary

    def test_deterministic_output_across_calls(self, session: Session):
        session.add_all(
            [
                _tool("b", tool_type="cli", state="loaded-on-boot"),
                _tool("a", tool_type="cli", state="loaded-on-boot"),
            ]
        )
        session.commit()
        first = compose_identity_summary(session)
        second = compose_identity_summary(session)
        assert first == second


# ---- refresh_identity_on_loaded_on_boot_change ---------------------------


class TestRefreshHookCrossings:
    """Fork 5: hook fires on ANY transition crossing the loaded-on-boot
    boundary, explicitly including loaded-on-boot → retired."""

    def _probe(self, session: Session, old: str, new: str):
        t = _tool("probe", state=old)  # construction-only; not saved
        memory = MagicMock()
        refresh_identity_on_loaded_on_boot_change(
            t, old, new, session=session, memory=memory
        )
        return memory

    def test_into_loaded_on_boot_fires(self, session: Session):
        memory = self._probe(session, "pending", "loaded-on-boot")
        assert memory.identity_set.call_count == 1

    def test_out_of_loaded_on_boot_to_used_fires(self, session: Session):
        memory = self._probe(session, "loaded-on-boot", "used")
        assert memory.identity_set.call_count == 1

    def test_out_of_loaded_on_boot_to_retired_fires(self, session: Session):
        """The loaded-on-boot → retired direction is explicitly in
        scope per Fork 5 — losing a tool from the toolbelt is
        identity-relevant in the same way as gaining one."""
        memory = self._probe(session, "loaded-on-boot", "retired")
        assert memory.identity_set.call_count == 1

    def test_out_of_loaded_on_boot_to_discovered_fires(self, session: Session):
        memory = self._probe(session, "loaded-on-boot", "discovered")
        assert memory.identity_set.call_count == 1

    def test_non_boundary_transition_does_not_fire(self, session: Session):
        # discovered → used doesn't touch loaded-on-boot
        memory = self._probe(session, "discovered", "used")
        assert memory.identity_set.call_count == 0
        memory2 = self._probe(session, "used", "retired")
        assert memory2.identity_set.call_count == 0
        memory3 = self._probe(session, "pending", "used")
        assert memory3.identity_set.call_count == 0

    def test_memory_failure_logged_but_not_raised(
        self, session: Session, caplog: pytest.LogCaptureFixture
    ):
        from core.memory import MemoryUnavailableError

        memory = MagicMock()
        memory.identity_set.side_effect = MemoryUnavailableError(
            "chromadb down"
        )
        t = _tool("probe", state="pending")
        with caplog.at_level(logging.WARNING, logger="concierge.identity"):
            # Must not raise
            refresh_identity_on_loaded_on_boot_change(
                t, "pending", "loaded-on-boot",
                session=session, memory=memory,
            )
        assert any(
            "refresh_failed" in r.message for r in caplog.records
        )


# ---- End-to-end via transition_tool_lifecycle ----------------------------


class TestTransitionHookWiring:
    """Confirm the on_transition kwarg on transition_tool_lifecycle
    actually propagates to the hook. Uses real DB transition +
    spy-style hook to exercise the full path."""

    def test_hook_called_after_successful_transition(self, session: Session):
        t = _tool("csvkit", state="discovered")
        session.add(t)
        session.commit()

        calls: list[tuple[str, str, str]] = []

        def hook(tool, old, new):
            calls.append((tool.slug, old, new))

        transition_tool_lifecycle(
            session, t, "loaded-on-boot", on_transition=hook
        )
        assert calls == [("csvkit", "discovered", "loaded-on-boot")]

    def test_hook_not_called_on_self_transition(self, session: Session):
        t = _tool("csvkit", state="loaded-on-boot")
        session.add(t)
        session.commit()

        calls: list = []

        def hook(tool, old, new):
            calls.append((tool.slug, old, new))

        transition_tool_lifecycle(
            session, t, "loaded-on-boot", on_transition=hook
        )
        assert calls == []  # self-transition short-circuits before hook

    def test_hook_failure_logged_but_transition_succeeds(
        self, session: Session, caplog: pytest.LogCaptureFixture
    ):
        t = _tool("csvkit", state="discovered")
        session.add(t)
        session.commit()

        def broken_hook(tool, old, new):
            raise RuntimeError("hook exploded")

        with caplog.at_level(
            logging.WARNING, logger="concierge.tool_transitions"
        ):
            transition_tool_lifecycle(
                session, t, "loaded-on-boot", on_transition=broken_hook
            )
        # State transition succeeded despite hook failure
        session.refresh(t)
        assert t.lifecycle_state == "loaded-on-boot"
        assert any("hook_failed" in r.message for r in caplog.records)


# ---- End-to-end cycle via real MemoryClient -----------------------------


@pytest.mark.integration
class TestIdentityInstallCycle:
    """Satisfies the Fix Day 3 checkpoint criterion:
    `MemoryClient.identity_get()` returns non-empty content after an
    install cycle ends with promotion to loaded-on-boot. Exercises
    the full path: real ChromaDB-backed MemoryClient + Tool DB +
    transition hook + compose_identity_summary."""

    def test_promoting_to_loaded_on_boot_populates_identity(
        self, session: Session, tmp_path
    ):
        from functools import partial

        from core.memory import MemoryClient

        memory = MemoryClient(memory_dir=tmp_path / "identity-store")

        # Before any transition — unset identity returns "".
        assert memory.identity_get() == ""

        # Operator approves + installs csvkit. Install cycle ends with
        # an explicit lifecycle promotion to loaded-on-boot.
        t = _tool("csvkit", tool_type="cli", state="used")
        session.add(t)
        session.commit()

        hook = partial(
            refresh_identity_on_loaded_on_boot_change,
            session=session,
            memory=memory,
        )
        transition_tool_lifecycle(
            session, t, "loaded-on-boot", on_transition=hook
        )

        identity = memory.identity_get()
        assert identity != ""
        assert "csvkit" in identity
        assert "loaded-on-boot" in identity.lower() or "cli: csvkit" in identity

    def test_retiring_from_loaded_on_boot_updates_identity(
        self, session: Session, tmp_path
    ):
        """The loaded-on-boot → retired direction is explicitly in
        scope per Fork 5."""
        from functools import partial

        from core.memory import MemoryClient

        memory = MemoryClient(memory_dir=tmp_path / "identity-store")

        # Seed two loaded-on-boot tools
        csvkit = _tool("csvkit", tool_type="cli", state="loaded-on-boot")
        ripgrep = _tool("ripgrep", tool_type="cli", state="loaded-on-boot")
        session.add_all([csvkit, ripgrep])
        session.commit()

        hook = partial(
            refresh_identity_on_loaded_on_boot_change,
            session=session,
            memory=memory,
        )

        # Initial refresh captures both
        transition_tool_lifecycle(
            session, csvkit, "loaded-on-boot", on_transition=hook
        )  # self-transition: no-op, no hook fired
        # So explicitly seed identity via a real crossing
        csvkit.lifecycle_state = "used"  # without hook
        session.flush()
        transition_tool_lifecycle(
            session, csvkit, "loaded-on-boot", on_transition=hook
        )
        before = memory.identity_get()
        assert "csvkit" in before
        assert "ripgrep" in before

        # Now retire csvkit from loaded-on-boot
        transition_tool_lifecycle(
            session, csvkit, "retired", on_transition=hook
        )
        after = memory.identity_get()
        assert "csvkit" not in after
        assert "ripgrep" in after
