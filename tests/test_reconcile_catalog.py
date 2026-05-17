"""Tests for core.catalog_reconcile — the Stage 1B one-shot catalog
reconciliation (Phase B).

Covers:
- the full reconciliation end-state (the five D40 transitions + the
  D77 pin) against a live-shaped catalog;
- the GHL row's field set;
- the D79 contract — the MailerLite → GHL `succeeded_by` write paired
  with the `retired` transition;
- idempotency — a second run is all `already_satisfied`, writes
  nothing, creates no duplicate GHL row;
- a missing target slug is reported (`skipped_missing`), not crashed;
- an illegal pre-state is reported (`error`) via the validated
  `transition_tool_lifecycle` path, not silently mis-written;
- rows outside the reconciliation spec are left untouched.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from core.catalog_reconcile import GHL_ROW, reconcile_catalog
from core.db.models import Tool


def _seed(
    db: Session,
    slug: str,
    *,
    lifecycle_state: str = "loaded-on-boot",
    tool_type: str = "mcp",
    pin_status: str = "auto-managed",
) -> Tool:
    t = Tool(
        slug=slug,
        name=slug,
        tool_type=tool_type,
        lifecycle_state=lifecycle_state,
        pin_status=pin_status,
        is_in_manifest=True,
    )
    db.add(t)
    db.flush()
    return t


def _seed_live_shaped_catalog(db: Session) -> None:
    """The catalog rows the reconciliation touches, plus two it must
    leave untouched — mirrors the post-Gate-2 catalog shape."""
    for slug in (
        "mailerlite",
        "stripe",
        "cloudflare",
        "elevenlabs",
        "semantic-memory-chromadb",
        "firefox-devtools",  # untouched control — stays loaded-on-boot
    ):
        _seed(db, slug)
    # An untouched buildable control — stays pending-decision.
    _seed(
        db, "cron-scheduling-for-worker-agents",
        lifecycle_state="pending-decision", tool_type="cli",
    )
    db.flush()


def _state(db: Session, slug: str) -> Tool | None:
    return db.query(Tool).filter_by(slug=slug).one_or_none()


# ---- Full reconciliation end-state --------------------------------------


class TestFullReconciliation:

    def test_end_state_of_all_six_operations(self, db_session: Session):
        _seed_live_shaped_catalog(db_session)
        summary = reconcile_catalog(db_session)

        assert summary.ok
        # The four lifecycle transitions.
        assert _state(db_session, "mailerlite").lifecycle_state == "retired"
        assert _state(db_session, "stripe").lifecycle_state == "pending-decision"
        assert _state(db_session, "cloudflare").lifecycle_state == "pending-decision"
        assert _state(db_session, "elevenlabs").lifecycle_state == "on-demand"
        # The D77 pin.
        assert (
            _state(db_session, "semantic-memory-chromadb").pin_status
            == "always-pinned"
        )
        # The GHL row was created.
        assert _state(db_session, "ghl") is not None

    def test_rows_outside_the_spec_are_untouched(self, db_session: Session):
        _seed_live_shaped_catalog(db_session)
        reconcile_catalog(db_session)
        # firefox-devtools: still loaded-on-boot, still auto-managed.
        ff = _state(db_session, "firefox-devtools")
        assert ff.lifecycle_state == "loaded-on-boot"
        assert ff.pin_status == "auto-managed"
        # the buildable: still pending-decision.
        assert (
            _state(db_session, "cron-scheduling-for-worker-agents")
            .lifecycle_state == "pending-decision"
        )

    def test_summary_reports_six_applied_operations(self, db_session: Session):
        _seed_live_shaped_catalog(db_session)
        summary = reconcile_catalog(db_session)
        # GHL insert + 4 transitions + 1 pin = 6 operations, all applied
        # on a first run against an unreconciled catalog.
        assert len(summary.results) == 6
        assert summary.count("applied") == 6
        assert summary.count("already_satisfied") == 0


# ---- The GHL row --------------------------------------------------------


class TestGhlRow:

    def test_ghl_row_field_set(self, db_session: Session):
        _seed_live_shaped_catalog(db_session)
        reconcile_catalog(db_session)
        ghl = _state(db_session, "ghl")
        assert ghl is not None
        assert ghl.slug == "ghl"
        assert ghl.tool_type == "mcp"
        # Created at loaded-on-boot (D40: GHL "active").
        assert ghl.lifecycle_state == "loaded-on-boot"
        assert ghl.is_active is True
        # Absent from TOOL-MANIFEST.md — a manifest-update to add it is
        # a separate operator step (D40).
        assert ghl.is_in_manifest is False
        # Concierge-managed — the canonical auto-managed successor (D77).
        assert ghl.pin_status == "auto-managed"

    def test_ghl_slug_matches_succeeded_by_target(self, db_session: Session):
        """The GHL row's slug must equal the `succeeded_by` value the
        MailerLite transition writes — the retirement lineage only
        resolves if they match."""
        assert GHL_ROW["slug"] == "ghl"


# ---- D79 — succeeded_by paired with retired -----------------------------


class TestSucceededByContract:

    def test_mailerlite_retired_and_succeeded_by_ghl_together(
        self, db_session: Session
    ):
        """D79 — the reconciliation slice's own coverage for the
        MailerLite → GHL `succeeded_by` write paired with the `retired`
        transition. Both land in the one reconciliation pass."""
        _seed_live_shaped_catalog(db_session)
        reconcile_catalog(db_session)
        mailerlite = _state(db_session, "mailerlite")
        assert mailerlite.lifecycle_state == "retired"
        assert mailerlite.succeeded_by == "ghl"

    def test_succeeded_by_only_set_on_mailerlite(self, db_session: Session):
        """The other transitioned rows carry no `succeeded_by` — only
        MailerLite has a retirement successor."""
        _seed_live_shaped_catalog(db_session)
        reconcile_catalog(db_session)
        for slug in ("stripe", "cloudflare", "elevenlabs"):
            assert _state(db_session, slug).succeeded_by is None


# ---- Idempotency --------------------------------------------------------


class TestIdempotency:

    def test_second_run_is_all_already_satisfied(self, db_session: Session):
        _seed_live_shaped_catalog(db_session)
        reconcile_catalog(db_session)
        second = reconcile_catalog(db_session)
        assert second.ok
        assert second.count("already_satisfied") == 6
        assert second.count("applied") == 0

    def test_rerun_creates_no_duplicate_ghl_row(self, db_session: Session):
        _seed_live_shaped_catalog(db_session)
        reconcile_catalog(db_session)
        reconcile_catalog(db_session)
        assert db_session.query(Tool).filter_by(slug="ghl").count() == 1

    def test_rerun_end_state_identical(self, db_session: Session):
        _seed_live_shaped_catalog(db_session)
        reconcile_catalog(db_session)
        reconcile_catalog(db_session)
        # End-state after a second run matches the first-run end-state.
        assert _state(db_session, "mailerlite").lifecycle_state == "retired"
        assert _state(db_session, "mailerlite").succeeded_by == "ghl"
        assert _state(db_session, "elevenlabs").lifecycle_state == "on-demand"
        assert (
            _state(db_session, "semantic-memory-chromadb").pin_status
            == "always-pinned"
        )


# ---- Missing slug / illegal pre-state -----------------------------------


class TestDegradedCatalog:

    def test_missing_target_slug_reported_not_crashed(
        self, db_session: Session
    ):
        """A reconciliation target absent from the catalog is reported
        as `skipped_missing`; the present targets still reconcile."""
        # Seed everything except stripe + cloudflare.
        for slug in ("mailerlite", "elevenlabs", "semantic-memory-chromadb"):
            _seed(db_session, slug)
        db_session.flush()

        summary = reconcile_catalog(db_session)

        assert not summary.ok
        assert summary.count("skipped_missing") == 2
        missing = {r.slug for r in summary.results
                   if r.outcome == "skipped_missing"}
        assert missing == {"stripe", "cloudflare"}
        # The present targets still reconciled.
        assert _state(db_session, "mailerlite").lifecycle_state == "retired"
        assert _state(db_session, "elevenlabs").lifecycle_state == "on-demand"

    def test_illegal_pre_state_reported_as_error(self, db_session: Session):
        """A target in an unexpected pre-state (here `stripe` already
        `retired`, whose only legal exit is `discovered`) surfaces as a
        reported `error` via the validated `transition_tool_lifecycle`
        path — not a silent mis-write."""
        _seed(db_session, "mailerlite")
        _seed(db_session, "stripe", lifecycle_state="retired")
        _seed(db_session, "cloudflare")
        _seed(db_session, "elevenlabs")
        _seed(db_session, "semantic-memory-chromadb")
        db_session.flush()

        summary = reconcile_catalog(db_session)

        assert not summary.ok
        stripe_result = next(
            r for r in summary.results if r.slug == "stripe"
        )
        assert stripe_result.outcome == "error"
        assert "illegal transition" in stripe_result.detail
        # stripe was not mutated by the failed transition.
        assert _state(db_session, "stripe").lifecycle_state == "retired"
        # the legal targets still reconciled.
        assert _state(db_session, "elevenlabs").lifecycle_state == "on-demand"
