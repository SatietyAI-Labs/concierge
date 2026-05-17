"""Tests for core.lifecycle_scanner — promotion/demotion/stale.

Fix Day 4 Task 5. Coverage areas:

- Promotion pass: event-count threshold, install-age discrimination
  (Fork G — 30d), already-loaded-on-boot skip, retired skip,
  auto-promote fires transition + identity refresh hook when memory
  is wired
- Demotion pass: loaded-on-boot tools with stale / zero events flagged;
  active loaded-on-boot tools not flagged
- Stale pending: request rows in pending/ older than 7d flagged
- ScannerSummary.to_health_dict shape pinned
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from core.db.models import Request, Tool, ToolUsageEvent
from core.lifecycle_policy import (
    DEMOTION_INACTIVITY_DAYS,
    PROMOTION_MIN_USES,
    PROMOTION_WINDOW_DAYS,
    STALE_PENDING_DAYS,
)
from core.lifecycle_scanner import (
    AUTO_PROMOTE_MIN_INSTALL_AGE_DAYS,
    PROMOTION_SIGNAL_EVENT_TYPES,
    ScannerSummary,
    run_once,
)


NOW = datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc)


def _seed_tool(
    db: Session,
    *,
    slug: str,
    lifecycle_state: str = "discovered",
    created_days_ago: int = 60,
    pin_status: str = "auto-managed",
) -> Tool:
    created_at = NOW - timedelta(days=created_days_ago)
    t = Tool(
        slug=slug,
        name=slug,
        tool_type="cli",
        lifecycle_state=lifecycle_state,
        pin_status=pin_status,
        created_at=created_at,
    )
    db.add(t)
    db.flush()
    return t


def _seed_usage_events(
    db: Session,
    *,
    tool: Tool,
    event_type: str = "recommended",
    count: int,
    days_ago: int = 5,
) -> None:
    timestamp = NOW - timedelta(days=days_ago)
    for _ in range(count):
        db.add(
            ToolUsageEvent(
                tool_id=tool.id,
                event_type=event_type,
                timestamp=timestamp,
            )
        )
    db.flush()


# ---- Promotion pass -----------------------------------------------------


class TestPromotionThresholds:
    def test_tool_below_event_threshold_not_a_candidate(self, db_session):
        tool = _seed_tool(db_session, slug="under-used", created_days_ago=60)
        _seed_usage_events(
            db_session,
            tool=tool,
            count=PROMOTION_MIN_USES - 1,
            days_ago=5,
        )
        summary = run_once(db_session, now=NOW)
        assert summary.promotion_candidates == []
        assert summary.auto_promoted == []

    def test_tool_at_threshold_is_candidate(self, db_session):
        tool = _seed_tool(db_session, slug="at-threshold", created_days_ago=60)
        _seed_usage_events(
            db_session,
            tool=tool,
            count=PROMOTION_MIN_USES,
            days_ago=5,
        )
        summary = run_once(db_session, now=NOW)
        assert len(summary.promotion_candidates) == 1
        assert summary.promotion_candidates[0].slug == "at-threshold"

    def test_events_outside_window_do_not_count(self, db_session):
        """Events older than PROMOTION_WINDOW_DAYS must not contribute.
        Guards against aggregation bugs that would promote tools on
        ancient activity.
        """
        tool = _seed_tool(db_session, slug="ancient-activity", created_days_ago=200)
        _seed_usage_events(
            db_session,
            tool=tool,
            count=PROMOTION_MIN_USES + 3,
            days_ago=PROMOTION_WINDOW_DAYS + 10,  # stale events
        )
        summary = run_once(db_session, now=NOW)
        assert summary.promotion_candidates == []

    def test_admin_events_do_not_count_as_promotion_signal(self, db_session):
        """`installed` and `removed` are admin events, not usage.
        Only `recommended` / `loaded` / `used` contribute to the
        promotion count.
        """
        tool = _seed_tool(db_session, slug="admin-only", created_days_ago=60)
        _seed_usage_events(
            db_session, tool=tool, event_type="installed",
            count=PROMOTION_MIN_USES + 2, days_ago=5,
        )
        summary = run_once(db_session, now=NOW)
        assert summary.promotion_candidates == []

    @pytest.mark.parametrize("event_type", PROMOTION_SIGNAL_EVENT_TYPES)
    def test_each_promotion_signal_event_type_counts(self, db_session, event_type):
        tool = _seed_tool(
            db_session, slug=f"signal-{event_type}", created_days_ago=60
        )
        _seed_usage_events(
            db_session, tool=tool, event_type=event_type,
            count=PROMOTION_MIN_USES, days_ago=5,
        )
        summary = run_once(db_session, now=NOW)
        assert len(summary.promotion_candidates) == 1


class TestPromotionClassification:
    """Fork G — install-age discrimination. Tools with fresh install
    age (< 30d) flag as ambiguous; tools with install age ≥ 30d and
    meeting the event threshold auto-promote.
    """

    def test_auto_promote_when_install_age_above_threshold(self, db_session):
        tool = _seed_tool(
            db_session, slug="ripe", created_days_ago=60,
            lifecycle_state="used",
        )
        _seed_usage_events(
            db_session, tool=tool, count=PROMOTION_MIN_USES, days_ago=3,
        )
        summary = run_once(db_session, now=NOW)
        assert len(summary.promotion_candidates) == 1
        assert summary.promotion_candidates[0].reason == "auto_promoted"
        assert summary.auto_promoted == ["ripe"]
        # State actually transitioned.
        db_session.refresh(tool)
        assert tool.lifecycle_state == "loaded-on-boot"

    def test_flag_as_ambiguous_when_install_age_below_threshold(self, db_session):
        """30d cutoff — install age < 30 keeps the tool out of auto-
        promote and lands it as ambiguous.
        """
        tool = _seed_tool(
            db_session,
            slug="too-fresh",
            created_days_ago=AUTO_PROMOTE_MIN_INSTALL_AGE_DAYS - 1,
            lifecycle_state="used",
        )
        _seed_usage_events(
            db_session, tool=tool, count=PROMOTION_MIN_USES, days_ago=3,
        )
        summary = run_once(db_session, now=NOW)
        assert len(summary.promotion_candidates) == 1
        assert summary.promotion_candidates[0].reason == "install_age_below_threshold"
        assert summary.auto_promoted == []
        db_session.refresh(tool)
        # State unchanged.
        assert tool.lifecycle_state == "used"

    def test_already_loaded_on_boot_does_not_transition(self, db_session):
        """Idempotence: a loaded-on-boot tool with a burst of events
        still appears in the candidate list (for transparency) but
        is not re-transitioned.
        """
        tool = _seed_tool(
            db_session, slug="already-loaded", created_days_ago=120,
            lifecycle_state="loaded-on-boot",
        )
        _seed_usage_events(
            db_session, tool=tool, count=PROMOTION_MIN_USES, days_ago=3,
        )
        summary = run_once(db_session, now=NOW)
        assert len(summary.promotion_candidates) == 1
        assert summary.promotion_candidates[0].reason == "already_loaded_on_boot"
        assert summary.auto_promoted == []

    def test_retired_tools_cannot_auto_promote(self, db_session):
        """Lifecycle table: retired exits only to discovered. Any
        retired tool with event signal is flagged but not promoted.
        """
        tool = _seed_tool(
            db_session, slug="zombie", created_days_ago=120,
            lifecycle_state="retired",
        )
        _seed_usage_events(
            db_session, tool=tool, count=PROMOTION_MIN_USES, days_ago=3,
        )
        summary = run_once(db_session, now=NOW)
        assert len(summary.promotion_candidates) == 1
        assert summary.promotion_candidates[0].reason == "retired_cannot_promote"
        assert summary.auto_promoted == []
        db_session.refresh(tool)
        assert tool.lifecycle_state == "retired"

    def test_discovered_with_enough_events_auto_promotes(self, db_session):
        """Discovered → loaded-on-boot is a legal transition; this is
        the fresh-out-of-catalog-insert path when a discovery rec
        accumulates signal.
        """
        tool = _seed_tool(
            db_session, slug="freshman", created_days_ago=60,
            lifecycle_state="discovered",
        )
        _seed_usage_events(
            db_session, tool=tool, count=PROMOTION_MIN_USES, days_ago=3,
        )
        summary = run_once(db_session, now=NOW)
        assert summary.auto_promoted == ["freshman"]
        db_session.refresh(tool)
        assert tool.lifecycle_state == "loaded-on-boot"


class TestOnDemandPromotionSkip:
    """SD-1 — `on-demand` is a settled "keep it, but not at boot"
    operator decision; the autonomous scanner must never promote it
    back to `loaded-on-boot` (promotion auto-fires — unlike demotion
    it is not flag-only — so without the skip the decision would be
    silently undone).

    The two tests below are a deliberate *non-vacuous* pair: the
    `on-demand` tool and the contrast `used` tool carry an identical
    promotion profile (same install age, same event count, same event
    recency) — the only difference is `lifecycle_state`. A bare
    "on-demand tool not promoted" assertion would pass even if the
    tool were never promotion-eligible to begin with; the contrast
    proves the different outcome is the `_classify_promotion` skip at
    work, not an ineligible profile.
    """

    def test_on_demand_tool_otherwise_eligible_is_not_auto_promoted(
        self, db_session
    ):
        tool = _seed_tool(
            db_session, slug="kept-off-boot", created_days_ago=60,
            lifecycle_state="on-demand",
        )
        _seed_usage_events(
            db_session, tool=tool, count=PROMOTION_MIN_USES, days_ago=3,
        )
        summary = run_once(db_session, now=NOW)
        # Meets the event threshold, so it IS surfaced as a candidate
        # (the operator can still manually promote) ...
        assert len(summary.promotion_candidates) == 1
        assert summary.promotion_candidates[0].slug == "kept-off-boot"
        assert summary.promotion_candidates[0].reason == "on_demand_settled"
        # ... but is NOT auto-promoted, and its state is untouched.
        assert summary.auto_promoted == []
        db_session.refresh(tool)
        assert tool.lifecycle_state == "on-demand"

    def test_identical_profile_used_tool_is_auto_promoted(self, db_session):
        """The contrast — identical install age / event count / event
        recency, only `lifecycle_state` differs. A `used` tool with
        this exact profile auto-promotes, proving the `on-demand`
        outcome above is the skip, not an ineligible profile.
        """
        tool = _seed_tool(
            db_session, slug="ripe-used", created_days_ago=60,
            lifecycle_state="used",
        )
        _seed_usage_events(
            db_session, tool=tool, count=PROMOTION_MIN_USES, days_ago=3,
        )
        summary = run_once(db_session, now=NOW)
        assert summary.auto_promoted == ["ripe-used"]
        assert summary.promotion_candidates[0].reason == "auto_promoted"
        db_session.refresh(tool)
        assert tool.lifecycle_state == "loaded-on-boot"


# ---- Demotion pass ------------------------------------------------------


class TestDemotionFlagging:
    def test_loaded_on_boot_with_recent_events_not_flagged(self, db_session):
        tool = _seed_tool(
            db_session, slug="active", lifecycle_state="loaded-on-boot",
            created_days_ago=120,
        )
        _seed_usage_events(db_session, tool=tool, count=1, days_ago=10)
        summary = run_once(db_session, now=NOW)
        assert summary.demotion_candidates == []

    def test_loaded_on_boot_with_stale_events_flagged(self, db_session):
        tool = _seed_tool(
            db_session, slug="gone-quiet", lifecycle_state="loaded-on-boot",
            created_days_ago=180,
        )
        _seed_usage_events(
            db_session, tool=tool, count=1,
            days_ago=DEMOTION_INACTIVITY_DAYS + 5,
        )
        summary = run_once(db_session, now=NOW)
        assert len(summary.demotion_candidates) == 1
        candidate = summary.demotion_candidates[0]
        assert candidate.slug == "gone-quiet"
        assert candidate.inactivity_days >= DEMOTION_INACTIVITY_DAYS

    def test_loaded_on_boot_with_no_events_flagged_with_sentinel(
        self, db_session
    ):
        """Never-exercised loaded-on-boot tools flag with
        inactivity_days=-1 to distinguish from went-quiet tools.
        """
        _seed_tool(
            db_session, slug="never-used", lifecycle_state="loaded-on-boot",
            created_days_ago=120,
        )
        summary = run_once(db_session, now=NOW)
        assert len(summary.demotion_candidates) == 1
        assert summary.demotion_candidates[0].slug == "never-used"
        assert summary.demotion_candidates[0].inactivity_days == -1
        assert summary.demotion_candidates[0].last_event_at is None

    def test_non_loaded_on_boot_tools_not_flagged_for_demotion(self, db_session):
        """Demotion signal only fires for loaded-on-boot. Other
        states aren't "on the toolbelt" to begin with.
        """
        _seed_tool(
            db_session, slug="discovered-quiet",
            lifecycle_state="discovered", created_days_ago=120,
        )
        summary = run_once(db_session, now=NOW)
        assert summary.demotion_candidates == []


class TestAlwaysPinnedDemotionExemption:
    """OD-5 / D77 — an `always-pinned` `loaded-on-boot` tool is exempt
    from autonomous demotion: the scanner never flags it as a demotion
    candidate, regardless of usage telemetry.

    A deliberate *non-vacuous* pair: the pinned tool and the contrast
    `auto-managed` tool carry an identical demotion profile —
    `loaded-on-boot`, zero usage events ever (the strongest demotion
    signal, sentinel inactivity). The only difference is `pin_status`.
    A bare "pinned tool not flagged" assertion would pass even if the
    tool were not demotion-eligible to begin with; the contrast proves
    the different outcome is the `pin_status` exemption filter.
    """

    def test_always_pinned_tool_is_exempt_from_demotion_flagging(
        self, db_session
    ):
        _seed_tool(
            db_session, slug="semantic-memory-chromadb",
            lifecycle_state="loaded-on-boot", pin_status="always-pinned",
        )
        summary = run_once(db_session, now=NOW)
        flagged = [c.slug for c in summary.demotion_candidates]
        assert "semantic-memory-chromadb" not in flagged

    def test_identical_auto_managed_tool_is_flagged_for_demotion(
        self, db_session
    ):
        """The contrast — same `loaded-on-boot` state, same (zero)
        usage; only `pin_status` differs. The `auto-managed` tool IS
        flagged, proving the exemption above is the pin filter at work,
        not a non-demotable profile."""
        _seed_tool(
            db_session, slug="auto-managed-boot-tool",
            lifecycle_state="loaded-on-boot", pin_status="auto-managed",
        )
        summary = run_once(db_session, now=NOW)
        flagged = [c.slug for c in summary.demotion_candidates]
        assert "auto-managed-boot-tool" in flagged


# ---- Stale pending ------------------------------------------------------


class TestStalePending:
    def test_fresh_pending_request_not_flagged(self, db_session):
        db_session.add(
            Request(
                filename="fresh.md",
                folder="pending",
                tool_name="fresh",
                raw_markdown="---\n---\n",
                parsed_data={},
                created_at=NOW - timedelta(days=STALE_PENDING_DAYS - 1),
            )
        )
        db_session.flush()
        summary = run_once(db_session, now=NOW)
        assert summary.stale_pending == []

    def test_old_pending_request_flagged(self, db_session):
        db_session.add(
            Request(
                filename="old.md",
                folder="pending",
                tool_name="old",
                raw_markdown="---\n---\n",
                parsed_data={},
                created_at=NOW - timedelta(days=STALE_PENDING_DAYS + 5),
            )
        )
        db_session.flush()
        summary = run_once(db_session, now=NOW)
        assert len(summary.stale_pending) == 1
        assert summary.stale_pending[0].filename == "old.md"
        assert summary.stale_pending[0].age_days >= STALE_PENDING_DAYS

    def test_resolved_old_requests_not_flagged(self, db_session):
        """Only `folder=pending` counts as stale-pending. Resolved /
        archived rows, even ancient ones, don't drain the inbox.
        """
        db_session.add(
            Request(
                filename="ancient-resolved.md",
                folder="resolved",
                tool_name="ancient",
                raw_markdown="---\n---\n",
                parsed_data={},
                created_at=NOW - timedelta(days=60),
            )
        )
        db_session.flush()
        summary = run_once(db_session, now=NOW)
        assert summary.stale_pending == []


# ---- to_health_dict shape ----------------------------------------------


class TestHealthShape:
    def test_empty_summary_shape(self):
        summary = ScannerSummary(ran_at=NOW)
        h = summary.to_health_dict()
        expected_keys = {
            "last_ran_at",
            "auto_promoted_count",
            "auto_promoted_slugs",
            "promotion_candidates_count",
            "promotion_candidates_slugs",
            "demotion_candidates_count",
            "demotion_candidates_slugs",
            "stale_pending_count",
            "stale_pending_filenames",
            "errors",
        }
        assert set(h.keys()) == expected_keys
        assert h["auto_promoted_count"] == 0
        assert h["last_ran_at"] == NOW.isoformat()

    def test_populated_summary_reports_counts(self, db_session):
        tool = _seed_tool(
            db_session, slug="promote-me", lifecycle_state="used",
            created_days_ago=60,
        )
        _seed_usage_events(
            db_session, tool=tool, count=PROMOTION_MIN_USES, days_ago=3,
        )
        summary = run_once(db_session, now=NOW)
        h = summary.to_health_dict()
        assert h["auto_promoted_count"] == 1
        assert "promote-me" in h["auto_promoted_slugs"]
        assert h["promotion_candidates_count"] == 1
