"""Tests for core/tool_transitions.py — Tool.lifecycle_state transition
validation via hybrid service-method + event-listener.

Fork 1 ruling (Fix Day 3): enforcement is hybrid. Service method
is the canonical write path; SQLAlchemy `before_update` event listener
catches direct setattr writes as a belt-and-suspenders guard. Raw SQL
UPDATE (Alembic migrations + audited backfills) intentionally bypasses
both. This test surface covers all three paths plus the
retired-reinstatement discipline.
"""
from __future__ import annotations

import logging

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.db.base import Base
from core.db import models  # noqa: F401 — register on Base.metadata
from core.db.models import LIFECYCLE_STATE_VALUES, Tool
from core.tool_transitions import (
    _TRANSITIONS,
    IllegalLifecycleTransition,
    assert_legal_transition,
    is_legal_transition,
    transition_tool_lifecycle,
)


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


def _seed(session: Session, *, slug: str, lifecycle_state: str) -> Tool:
    t = Tool(slug=slug, name=slug, lifecycle_state=lifecycle_state)
    session.add(t)
    session.commit()
    return t


# ---- Pure predicate + assertion tests ------------------------------------


class TestPredicateShape:
    def test_self_transition_always_legal(self):
        for s in LIFECYCLE_STATE_VALUES:
            assert is_legal_transition(s, s)

    def test_unknown_current_returns_false(self):
        assert is_legal_transition("garbage", "discovered") is False

    def test_unknown_target_returns_false(self):
        assert is_legal_transition("discovered", "garbage") is False

    def test_every_state_reachable_from_discovered(self):
        for target in LIFECYCLE_STATE_VALUES:
            assert is_legal_transition("discovered", target), (
                f"discovered → {target} should be legal"
            )

    def test_retired_only_exits_to_discovered(self):
        for target in LIFECYCLE_STATE_VALUES:
            legal = is_legal_transition("retired", target)
            if target == "retired" or target == "discovered":
                assert legal, f"retired → {target} should be legal"
            else:
                assert not legal, (
                    f"retired → {target} should be illegal — "
                    f"retired tools must reinstate via discovered first"
                )

    def test_transitions_table_covers_every_lifecycle_state(self):
        """Defensive-D24 guard (D56): every state in
        `LIFECYCLE_STATE_VALUES` must have a `_TRANSITIONS` row.
        `assert_legal_transition` indexes `_TRANSITIONS[current]`
        directly — a state present in the Enum but missing from the
        table would `KeyError` at runtime rather than fail cleanly.
        A future eighth state lacking its `_TRANSITIONS` row trips
        this immediately (the D24 green-signal mechanic)."""
        assert set(_TRANSITIONS) == set(LIFECYCLE_STATE_VALUES), (
            "_TRANSITIONS keys must exactly match LIFECYCLE_STATE_VALUES; "
            f"only in _TRANSITIONS: {set(_TRANSITIONS) - set(LIFECYCLE_STATE_VALUES)}; "
            f"only in LIFECYCLE_STATE_VALUES: "
            f"{set(LIFECYCLE_STATE_VALUES) - set(_TRANSITIONS)}"
        )


class TestAssertLegalTransition:
    def test_accepts_legal(self):
        assert_legal_transition(
            current="pending", target="used", slug="x"
        )  # no raise

    def test_rejects_illegal(self):
        with pytest.raises(IllegalLifecycleTransition, match="retired"):
            assert_legal_transition(
                current="retired", target="used", slug="csvkit"
            )

    def test_error_message_includes_slug(self):
        with pytest.raises(IllegalLifecycleTransition) as exc_info:
            assert_legal_transition(
                current="retired", target="loaded-on-boot", slug="my-tool"
            )
        assert "my-tool" in str(exc_info.value)

    def test_error_message_lists_allowed_targets(self):
        with pytest.raises(IllegalLifecycleTransition) as exc_info:
            assert_legal_transition(
                current="retired", target="used", slug="x"
            )
        # retired's only legal exit is discovered
        assert "discovered" in str(exc_info.value)

    def test_unknown_current_raises(self):
        with pytest.raises(IllegalLifecycleTransition, match="not a recognized"):
            assert_legal_transition(
                current="zombie", target="discovered", slug="x"
            )


# ---- Service method tests ------------------------------------------------


class TestTransitionToolLifecycle:
    def test_legal_transition_applies_and_returns(self, session: Session):
        t = _seed(session, slug="csvkit", lifecycle_state="discovered")
        transition_tool_lifecycle(session, t, "pending")
        session.refresh(t)
        assert t.lifecycle_state == "pending"

    def test_illegal_transition_raises_and_preserves_prior_state(
        self, session: Session
    ):
        t = _seed(session, slug="htop", lifecycle_state="retired")
        with pytest.raises(IllegalLifecycleTransition):
            transition_tool_lifecycle(session, t, "used")
        session.refresh(t)
        assert t.lifecycle_state == "retired"

    def test_self_transition_is_noop(self, session: Session):
        t = _seed(session, slug="jq", lifecycle_state="loaded-on-boot")
        transition_tool_lifecycle(session, t, "loaded-on-boot")
        session.refresh(t)
        assert t.lifecycle_state == "loaded-on-boot"

    def test_logs_at_info_on_success(
        self, session: Session, caplog: pytest.LogCaptureFixture
    ):
        t = _seed(session, slug="ripgrep", lifecycle_state="discovered")
        with caplog.at_level(logging.INFO, logger="concierge.tool_transitions"):
            transition_tool_lifecycle(session, t, "pending")
        applied = [
            r for r in caplog.records
            if "tool_transitions.apply" in r.message
        ]
        assert len(applied) == 1
        assert "ripgrep" in applied[0].message
        assert "discovered" in applied[0].message
        assert "pending" in applied[0].message


# ---- Event listener tests (direct setattr) -------------------------------


class TestEventListener:
    """The `set` event on `Tool.lifecycle_state` fires immediately on
    setattr, BEFORE the flush. active_history=True forces SQLAlchemy to
    load the committed old value from the DB even for expired attributes
    (the common case after a commit / in a fresh session request cycle).
    Validation failures raise on the setattr itself; the new value is
    not stored on the instance."""

    def test_direct_setattr_legal_transition_succeeds(self, session: Session):
        t = _seed(session, slug="pandoc", lifecycle_state="pending")
        t.lifecycle_state = "used"
        session.flush()
        session.refresh(t)
        assert t.lifecycle_state == "used"

    def test_direct_setattr_illegal_transition_raises_on_assignment(
        self, session: Session
    ):
        t = _seed(session, slug="htop", lifecycle_state="retired")
        with pytest.raises(IllegalLifecycleTransition):
            t.lifecycle_state = "used"
        # Failed set did not store the new value; DB unchanged too.
        session.refresh(t)
        assert t.lifecycle_state == "retired"

    def test_listener_logs_warning_on_rejection(
        self, session: Session, caplog: pytest.LogCaptureFixture
    ):
        t = _seed(session, slug="csvkit", lifecycle_state="retired")
        with caplog.at_level(logging.WARNING, logger="concierge.tool_transitions"):
            with pytest.raises(IllegalLifecycleTransition):
                t.lifecycle_state = "loaded-on-boot"
        rejected = [
            r for r in caplog.records
            if "tool_transitions.rejected" in r.message
        ]
        assert len(rejected) == 1
        assert "csvkit" in rejected[0].message
        assert rejected[0].levelname == "WARNING"

    def test_listener_ignores_non_lifecycle_updates(self, session: Session):
        """The set listener is attached to `Tool.lifecycle_state`
        specifically, not to the whole Tool class. Writes to other
        columns must not invoke the validator."""
        t = _seed(session, slug="pandoc", lifecycle_state="retired")
        t.description = "updated description"
        session.flush()  # must not raise
        session.refresh(t)
        assert t.description == "updated description"
        assert t.lifecycle_state == "retired"

    def test_listener_catches_expired_attribute_after_commit(
        self, session: Session
    ):
        """Regression test for Fix Day 3 listener bug: after commit
        SQLAlchemy expires attributes; `before_update` + `get_history`
        returned `deleted=[]` and the early-exit path silently accepted
        illegal transitions. active_history=True on the `set` event
        forces the committed value to load so oldvalue is reliable."""
        t = _seed(session, slug="expired-probe", lifecycle_state="retired")
        session.commit()  # expires the attribute
        # Even with attribute expired, listener must still catch this
        with pytest.raises(IllegalLifecycleTransition):
            t.lifecycle_state = "loaded-on-boot"
        session.refresh(t)
        assert t.lifecycle_state == "retired"


# ---- Insert-vs-update invariant ------------------------------------------


class TestInsertSemantics:
    """Initial inserts are NOT validated — a row can be created in any
    lifecycle_state. Validation gates UPDATEs only. This allows ingest
    paths to land rows at `loaded-on-boot` / `retired` / etc. without
    a two-step insert-then-transition ceremony."""

    def test_insert_with_retired_is_legal(self, session: Session):
        t = Tool(slug="preretired", name="preretired", lifecycle_state="retired")
        session.add(t)
        session.commit()
        assert t.lifecycle_state == "retired"

    def test_insert_with_loaded_on_boot_is_legal(self, session: Session):
        t = Tool(
            slug="preloaded", name="preloaded", lifecycle_state="loaded-on-boot"
        )
        session.add(t)
        session.commit()
        assert t.lifecycle_state == "loaded-on-boot"


# ---- Retired reinstatement flow ------------------------------------------


class TestRetiredReinstatement:
    """The "retired → X illegal except → discovered" invariant forces
    an explicit reinstatement step before any other transition. This
    preserves the operator audit trail: a retired tool cannot silently
    become loaded-on-boot."""

    def test_retired_cannot_directly_promote(self, session: Session):
        t = _seed(session, slug="x", lifecycle_state="retired")
        for illegal_target in ("used", "loaded-on-boot", "pending"):
            with pytest.raises(IllegalLifecycleTransition):
                transition_tool_lifecycle(session, t, illegal_target)
            session.rollback()
            session.refresh(t)
            assert t.lifecycle_state == "retired"

    def test_retired_to_discovered_reinstatement_then_promote(
        self, session: Session
    ):
        t = _seed(session, slug="x", lifecycle_state="retired")
        # Step 1: reinstate
        transition_tool_lifecycle(session, t, "discovered")
        session.refresh(t)
        assert t.lifecycle_state == "discovered"
        # Step 2: now any onward transition is legal
        transition_tool_lifecycle(session, t, "used")
        session.refresh(t)
        assert t.lifecycle_state == "used"


# ---- Raw-SQL bypass precedent --------------------------------------------


class TestRawSqlBypass:
    """Alembic migrations + audited backfills use `op.execute(UPDATE...)`
    which does NOT fire the ORM event listener. This is explicit-by-design
    per the module docstring. The test below codifies the precedent by
    demonstrating that raw SQL can write any state without validation —
    exactly as the Fix Day 2 backfill migration did."""

    def test_raw_sql_update_bypasses_listener(self, session: Session):
        t = _seed(session, slug="x", lifecycle_state="retired")
        # An ORM transition would raise: retired → loaded-on-boot is illegal.
        # Raw SQL bypasses the listener intentionally.
        session.execute(
            text("UPDATE tools SET lifecycle_state = :s WHERE slug = :slug"),
            {"s": "loaded-on-boot", "slug": "x"},
        )
        session.commit()
        # Use a fresh read to confirm DB state (cached object would lag)
        row = session.execute(
            text("SELECT lifecycle_state FROM tools WHERE slug = 'x'")
        ).scalar()
        assert row == "loaded-on-boot"


# ---- pending-decision transitions (Stage 1A item 4) -----------------------


class TestPendingDecisionTransitions:
    """`pending-decision` is the sixth lifecycle state, added by Stage 1A
    item 4 for tools the operator is actively evaluating. The state's
    semantics:

    - Incoming from `discovered` (operator picks up a known-but-not-loaded
      row for active evaluation), from `pending` (a request that needs
      operator deliberation before approve/deny), or from `loaded-on-boot`
      (operator re-opens evaluation of a currently-active tool without
      unloading it — the Stripe/Cloudflare case; edge added 2026-05-15,
      Stage-0 re-scope bundle).
    - Outgoing: approve → `used` or `loaded-on-boot`; deny → `retired`;
      park the evaluation → `discovered`.

    The `retired → pending-decision` edge is intentionally illegal — the
    retired-reinstatement invariant (retired's only exit is `discovered`)
    extends to this new state: a retired tool cannot silently move to
    active evaluation without an explicit reinstatement step.
    """

    def test_discovered_to_pending_decision_legal(self, session: Session):
        t = _seed(session, slug="stripe", lifecycle_state="discovered")
        transition_tool_lifecycle(session, t, "pending-decision")
        session.refresh(t)
        assert t.lifecycle_state == "pending-decision"

    def test_pending_to_pending_decision_legal(self, session: Session):
        t = _seed(session, slug="cloudflare", lifecycle_state="pending")
        transition_tool_lifecycle(session, t, "pending-decision")
        session.refresh(t)
        assert t.lifecycle_state == "pending-decision"

    def test_loaded_on_boot_to_pending_decision_legal(self, session: Session):
        """A currently-active (`loaded-on-boot`) tool can move directly to
        `pending-decision` — the operator re-opens evaluation without
        unloading it. Edge added 2026-05-15 (Stage-0 re-scope bundle); the
        Stripe/Cloudflare "we have it but its future is uncertain" case."""
        t = _seed(session, slug="stripe", lifecycle_state="loaded-on-boot")
        transition_tool_lifecycle(session, t, "pending-decision")
        session.refresh(t)
        assert t.lifecycle_state == "pending-decision"

    def test_pending_decision_to_loaded_on_boot_legal_approval(
        self, session: Session
    ):
        t = _seed(session, slug="ghl", lifecycle_state="pending-decision")
        transition_tool_lifecycle(session, t, "loaded-on-boot")
        session.refresh(t)
        assert t.lifecycle_state == "loaded-on-boot"

    def test_pending_decision_to_used_legal_session_loaded_approval(
        self, session: Session
    ):
        t = _seed(session, slug="mailerlite", lifecycle_state="pending-decision")
        transition_tool_lifecycle(session, t, "used")
        session.refresh(t)
        assert t.lifecycle_state == "used"

    def test_pending_decision_to_retired_legal_denial(self, session: Session):
        t = _seed(session, slug="ad-hoc-tool", lifecycle_state="pending-decision")
        transition_tool_lifecycle(session, t, "retired")
        session.refresh(t)
        assert t.lifecycle_state == "retired"

    def test_pending_decision_to_discovered_legal_park(self, session: Session):
        t = _seed(
            session, slug="parked-eval", lifecycle_state="pending-decision"
        )
        transition_tool_lifecycle(session, t, "discovered")
        session.refresh(t)
        assert t.lifecycle_state == "discovered"

    def test_pending_decision_to_pending_illegal(self, session: Session):
        """`pending` is the request-in-flight state; once an evaluation
        has been picked up (pending-decision), going back to "request
        is open" is not modeled — outcomes are approve/deny/park."""
        t = _seed(session, slug="x", lifecycle_state="pending-decision")
        with pytest.raises(IllegalLifecycleTransition):
            transition_tool_lifecycle(session, t, "pending")
        session.rollback()
        session.refresh(t)
        assert t.lifecycle_state == "pending-decision"

    def test_retired_to_pending_decision_illegal(self, session: Session):
        """Retired-reinstatement invariant: retired's only exit is
        `discovered`. A retired tool cannot bypass that to land
        directly in active evaluation."""
        t = _seed(session, slug="x", lifecycle_state="retired")
        with pytest.raises(IllegalLifecycleTransition):
            transition_tool_lifecycle(session, t, "pending-decision")
        session.rollback()
        session.refresh(t)
        assert t.lifecycle_state == "retired"

    def test_pending_decision_self_transition_is_noop(self, session: Session):
        t = _seed(session, slug="x", lifecycle_state="pending-decision")
        transition_tool_lifecycle(session, t, "pending-decision")
        session.refresh(t)
        assert t.lifecycle_state == "pending-decision"

    def test_insert_with_pending_decision_is_legal(self, session: Session):
        """Inserts are not validated; ingest can land rows directly in
        `pending-decision` without a two-step ceremony (matches the
        precedent for `retired` / `loaded-on-boot` inserts)."""
        t = Tool(
            slug="fresh-eval",
            name="fresh-eval",
            lifecycle_state="pending-decision",
        )
        session.add(t)
        session.commit()
        assert t.lifecycle_state == "pending-decision"


# ---- on-demand transitions (Stage 1B reconciliation slice) ----------------


class TestOnDemandTransitions:
    """`on-demand` is the seventh lifecycle state, added by the Stage 1B
    catalog reconciliation slice for a tool deliberately kept but not
    boot-loaded — installed and usable, off the boot context budget. A
    *settled* state, peer to `loaded-on-boot`; distinct from
    `pending-decision` ("fate undecided"). The state's transition graph:

    - Incoming from `loaded-on-boot` (keep the tool, drop it off boot —
      the ElevenLabs case), `pending-decision` (an evaluation concludes
      "keep it, on-demand"), `discovered` (settle a catalogued tool as
      kept-on-demand), or `pending` (a request approved as "install,
      don't boot-load").
    - Outgoing: `loaded-on-boot` (promote to boot — without this edge
      `on-demand` is a one-way trap), `discovered` (full unload),
      `retired` (drop), `pending-decision` (re-open evaluation).

    Intentionally illegal: `used → on-demand` (`used` is kept narrow —
    mirrors the deliberate `used → pending-decision` exclusion, D82);
    `retired → on-demand` (the retired-reinstatement invariant —
    retired's only exit is `discovered`); `on-demand → pending`
    (a catalogued kept tool is not in the request pipeline) and
    `on-demand → used` (`on-demand` is already non-boot-usable; the
    demote slot points at `loaded-on-boot`).
    """

    # ---- legal incoming ----

    def test_loaded_on_boot_to_on_demand_legal(self, session: Session):
        """The ElevenLabs move — keep an active tool but drop it off the
        boot context budget."""
        t = _seed(session, slug="elevenlabs", lifecycle_state="loaded-on-boot")
        transition_tool_lifecycle(session, t, "on-demand")
        session.refresh(t)
        assert t.lifecycle_state == "on-demand"

    def test_pending_decision_to_on_demand_legal(self, session: Session):
        """An evaluation concludes "keep it, on-demand" — a legitimate
        fate for a pending-decision row."""
        t = _seed(session, slug="x", lifecycle_state="pending-decision")
        transition_tool_lifecycle(session, t, "on-demand")
        session.refresh(t)
        assert t.lifecycle_state == "on-demand"

    def test_discovered_to_on_demand_legal(self, session: Session):
        t = _seed(session, slug="x", lifecycle_state="discovered")
        transition_tool_lifecycle(session, t, "on-demand")
        session.refresh(t)
        assert t.lifecycle_state == "on-demand"

    def test_pending_to_on_demand_legal(self, session: Session):
        """A request approved as "install but do not boot-load"."""
        t = _seed(session, slug="x", lifecycle_state="pending")
        transition_tool_lifecycle(session, t, "on-demand")
        session.refresh(t)
        assert t.lifecycle_state == "on-demand"

    # ---- legal outgoing ----

    def test_on_demand_to_loaded_on_boot_legal(self, session: Session):
        """Promote a kept tool to boot. Without this edge `on-demand` is
        a one-way trap."""
        t = _seed(session, slug="x", lifecycle_state="on-demand")
        transition_tool_lifecycle(session, t, "loaded-on-boot")
        session.refresh(t)
        assert t.lifecycle_state == "loaded-on-boot"

    def test_on_demand_to_discovered_legal(self, session: Session):
        t = _seed(session, slug="x", lifecycle_state="on-demand")
        transition_tool_lifecycle(session, t, "discovered")
        session.refresh(t)
        assert t.lifecycle_state == "discovered"

    def test_on_demand_to_retired_legal(self, session: Session):
        t = _seed(session, slug="x", lifecycle_state="on-demand")
        transition_tool_lifecycle(session, t, "retired")
        session.refresh(t)
        assert t.lifecycle_state == "retired"

    def test_on_demand_to_pending_decision_legal(self, session: Session):
        """Re-open evaluation of a kept tool — mirrors the
        `loaded-on-boot → pending-decision` rationale (D82)."""
        t = _seed(session, slug="x", lifecycle_state="on-demand")
        transition_tool_lifecycle(session, t, "pending-decision")
        session.refresh(t)
        assert t.lifecycle_state == "pending-decision"

    # ---- intentionally illegal ----

    def test_used_to_on_demand_illegal(self, session: Session):
        """`used` is kept deliberately narrow — `used → on-demand` is
        not modelled (mirrors the deliberate `used → pending-decision`
        exclusion, D82). A future micro-edit adds it if a real case
        appears."""
        t = _seed(session, slug="x", lifecycle_state="used")
        with pytest.raises(IllegalLifecycleTransition):
            transition_tool_lifecycle(session, t, "on-demand")
        session.rollback()
        session.refresh(t)
        assert t.lifecycle_state == "used"

    def test_retired_to_on_demand_illegal(self, session: Session):
        """Retired-reinstatement invariant: retired's only exit is
        `discovered`. A retired tool cannot bypass that to land
        directly at `on-demand`."""
        t = _seed(session, slug="x", lifecycle_state="retired")
        with pytest.raises(IllegalLifecycleTransition):
            transition_tool_lifecycle(session, t, "on-demand")
        session.rollback()
        session.refresh(t)
        assert t.lifecycle_state == "retired"

    def test_on_demand_to_pending_illegal(self, session: Session):
        """`pending` is the request-in-flight state; a catalogued
        kept tool is not in the request pipeline."""
        t = _seed(session, slug="x", lifecycle_state="on-demand")
        with pytest.raises(IllegalLifecycleTransition):
            transition_tool_lifecycle(session, t, "pending")
        session.rollback()
        session.refresh(t)
        assert t.lifecycle_state == "on-demand"

    def test_on_demand_to_used_illegal(self, session: Session):
        """`on-demand` is already non-boot-usable; `on-demand → used`
        is not modelled — the demote slot for `on-demand` points at
        `loaded-on-boot`."""
        t = _seed(session, slug="x", lifecycle_state="on-demand")
        with pytest.raises(IllegalLifecycleTransition):
            transition_tool_lifecycle(session, t, "used")
        session.rollback()
        session.refresh(t)
        assert t.lifecycle_state == "on-demand"

    # ---- self-transition + insert ----

    def test_on_demand_self_transition_is_noop(self, session: Session):
        t = _seed(session, slug="x", lifecycle_state="on-demand")
        transition_tool_lifecycle(session, t, "on-demand")
        session.refresh(t)
        assert t.lifecycle_state == "on-demand"

    def test_insert_with_on_demand_is_legal(self, session: Session):
        """Inserts are not validated; a row can be created directly at
        `on-demand` (matches the precedent for `retired` /
        `loaded-on-boot` / `pending-decision` inserts)."""
        t = Tool(slug="fresh", name="fresh", lifecycle_state="on-demand")
        session.add(t)
        session.commit()
        assert t.lifecycle_state == "on-demand"
