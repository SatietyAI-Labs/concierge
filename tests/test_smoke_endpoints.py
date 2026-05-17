"""N8 — endpoint liveness across the full service surface.

This suite exists to produce the **operational baseline for soak
diagnostics**, not merely to add test coverage. During the 48h gate,
running this suite against a live Concierge is the operator's first
diagnostic move when something degrades. Every endpoint that
contributes to the operational core must surface a green check
here — otherwise soak operators can't bisect.

Scope: happy-path structural liveness only. Semantic-quality
assertions (Risk 1) live in test_smoke_live_anthropic.py behind
the live_smoke marker. Subsystem-specific edge cases live in their
respective test modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.api.recommend import get_recommendation_service
from core.app import create_app
from core.db.models import Pack, Tool
from core.recommend.schemas import (
    LatencyBreakdown,
    RecommendResponse,
    TokenUsage,
    ToolRecommendation,
)


# ---- Fixtures ------------------------------------------------------------


@dataclass
class _StubRecommendService:
    def recommend(self, req):
        return RecommendResponse(
            request_id="11111111-2222-3333-4444-555555555555",
            recommendations=[
                ToolRecommendation(
                    rank=1,
                    tool_slug="csvstat",
                    tool_name="csvstat",
                    rationale="Lightweight.",
                    confidence="high",
                    is_in_catalog=True,
                )
            ],
            memory_available=True,
            memory_hit_count=0,
            model="claude-opus-4-7",
            effort="xhigh",
            latency_ms=LatencyBreakdown(total=100, memory=10, model=85, parse=2),
            token_usage=TokenUsage(input=500, output=100, total=600),
            reasoning="Stub.",
            stop_reason="end_turn",
        )


@pytest.fixture
def seeded_client(db_session):
    """TestClient with a couple of catalog rows seeded so /health
    surfaces non-zero catalog counts.
    """
    pack = Pack(slug="csvkit", name="csvkit", status="active")
    db_session.add(pack)
    db_session.flush()
    db_session.add_all(
        [
            Tool(
                slug="csvstat",
                name="csvstat",
                pack_id=pack.id,
                is_in_manifest=True,
                lifecycle_state="loaded-on-boot",  # active
            ),
            Tool(
                slug="pandas",
                name="pandas",
                is_in_manifest=True,
                lifecycle_state="discovered",  # dormant — activation candidate
            ),
        ]
    )
    db_session.commit()

    from core.db.session import get_db

    app = create_app()
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    app.dependency_overrides[get_recommendation_service] = lambda: _StubRecommendService()
    return TestClient(app)


# ---- /health operational pulse ------------------------------------------


class TestHealthOperationalPulse:
    def test_health_returns_200(self, seeded_client):
        resp = seeded_client.get("/health")
        assert resp.status_code == 200

    def test_health_config_echo_includes_model_and_roots(self, seeded_client):
        body = seeded_client.get("/health").json()
        assert body["config"]["model"] == "claude-opus-4-7"
        assert body["config"]["effort"] == "xhigh"
        assert "memory_dir" in body["config"]
        assert "lifecycle_root" in body["config"]
        assert "database_path" in body["config"]

    def test_health_counters_present(self, seeded_client):
        body = seeded_client.get("/health").json()
        assert "recommend" in body["counters"]
        assert "lifecycle" in body["counters"]
        # Shape: zero initial state, but all expected keys present.
        for key in ("requests", "tokens_in", "tokens_out", "memory_unavailable", "parse_failed", "fixture_drift"):
            assert key in body["counters"]["recommend"]
        for key in ("created", "transitioned", "invalid_transitions", "parse_failed", "not_found"):
            assert key in body["counters"]["lifecycle"]

    def test_health_catalog_counts_reflect_db_state(self, seeded_client):
        body = seeded_client.get("/health").json()
        assert body["catalog"]["packs"] == 1
        assert body["catalog"]["tools"] == 2
        assert body["catalog"]["tools_active"] == 1
        assert body["catalog"]["tools_dormant"] == 1

    def test_health_requests_folder_counts_present(self, seeded_client):
        body = seeded_client.get("/health").json()
        for folder in ("pending", "resolved", "archived", "total"):
            assert folder in body["requests"]

    def test_health_has_no_warnings_on_happy_path(self, seeded_client):
        body = seeded_client.get("/health").json()
        # `health_warnings` only present when a subsystem read fails.
        assert "health_warnings" not in body


# ---- /health pending-count semantic (Day 11 Task 1.3 / Fork D1) -----


class TestHealthRequestsPendingCount:
    """The Health/Stats `Pending requests` tile must show the same
    number the operator sees in the inbox card list. Day 10 surfaced
    a real-world drift case (id=6 csvkit failed since 2026-04-23 +
    id=7 ocrmypdf installed after approve action — both stuck in
    folder=pending until cron reconciles) where the bar showed
    `Pending requests: 1` while the inbox showed `No pending tool
    requests`. Day 11 Fork D1: align the bar to the inbox by
    filtering on Request.status == 'pending' instead of
    folder='pending'.

    `resolved` and `archived` keys remain folder-based so that
    folder/status drift surfaces as a /health diagnostic signal —
    deliberate mixed semantic, not oversight. See DECISIONS
    `[2026-05-02 Day 11]`.
    """

    def test_pending_count_uses_status_not_folder(self, db_session):
        """Drift fixture: three rows in folder=pending, only one
        with status=pending. /health pending must return 1, not 3."""
        from core.app import create_app
        from core.db.models import Request as RequestRow
        from core.db.session import get_db

        db_session.add_all([
            RequestRow(
                filename="2026-04-26-0001-csvkit.md",
                status="pending",
                folder="pending",
                tool_name="csvkit",
                raw_markdown="# csvkit",
            ),
            RequestRow(
                filename="2026-04-26-0002-ripgrep.md",
                status="failed",  # drift: folder=pending but status=failed
                folder="pending",
                tool_name="ripgrep",
                raw_markdown="# ripgrep",
            ),
            RequestRow(
                filename="2026-04-26-0003-ocrmypdf.md",
                status="installed",  # drift: cron hasn't moved it yet
                folder="pending",
                tool_name="ocrmypdf",
                raw_markdown="# ocrmypdf",
            ),
        ])
        db_session.commit()

        app = create_app()
        app.dependency_overrides[get_db] = lambda: (yield db_session)
        client = TestClient(app)
        body = client.get("/health").json()

        assert body["requests"]["pending"] == 1, (
            "Pending count must filter by status, not folder, to match "
            "the inbox semantic. Folder-based count would return 3."
        )

    def test_pending_count_matches_inbox_query_under_both_drift_directions(
        self, db_session
    ):
        """Belt-and-suspenders: /health pending must equal the count
        list_pending_rows would return under BOTH drift directions
        — forward (folder=pending, status≠pending) and reverse
        (status=pending, folder≠pending). Locks the alignment claim
        regardless of which drift the cron-reconciliation lag exhibits.

        Filter shape mirrors list_pending_rows (folder='pending' AND
        status='pending') so the two queries are structurally identical;
        future refactors of either side that preserve this invariant
        keep the bar/inbox alignment intact."""
        from core.app import create_app
        from core.db.models import Request as RequestRow
        from core.db.session import get_db
        from core.lifecycle_store.store import list_pending_rows

        db_session.add_all([
            # Pending in both — counts in both queries
            RequestRow(
                filename="a.md", status="pending", folder="pending",
                tool_name="a", raw_markdown="# a",
            ),
            # Forward drift — folder=pending but status moved on (cron
            # reconciliation hasn't moved the file yet). Excluded from
            # both queries.
            RequestRow(
                filename="b.md", status="failed", folder="pending",
                tool_name="b", raw_markdown="# b",
            ),
            RequestRow(
                filename="c.md", status="approved", folder="pending",
                tool_name="c", raw_markdown="# c",
            ),
            # Reverse drift — status=pending but folder moved on (the
            # symmetric drift bug class; harden against it now while
            # we're touching the filter shape). Excluded from both
            # queries iff the bar's filter mirrors the inbox.
            RequestRow(
                filename="d.md", status="pending", folder="resolved",
                tool_name="d", raw_markdown="# d",
            ),
        ])
        db_session.commit()

        app = create_app()
        app.dependency_overrides[get_db] = lambda: (yield db_session)
        client = TestClient(app)

        health_pending = client.get("/health").json()["requests"]["pending"]
        inbox_count = len(list_pending_rows(db_session))
        assert health_pending == inbox_count == 1, (
            f"health.pending={health_pending} vs inbox={inbox_count}; "
            f"both should be 1 (only row 'a.md' satisfies folder=pending "
            f"AND status=pending)."
        )

    def test_resolved_and_archived_remain_folder_based(self, db_session):
        """Diagnostic signal preserved: resolved/archived counts
        reflect on-disk folder state, regardless of row status. This
        is what makes folder/status drift visible in /health."""
        from core.app import create_app
        from core.db.models import Request as RequestRow
        from core.db.session import get_db

        db_session.add_all([
            RequestRow(
                filename="r1.md", status="approved", folder="resolved",
                tool_name="r1", raw_markdown="# r1",
            ),
            RequestRow(
                filename="r2.md", status="failed", folder="resolved",
                tool_name="r2", raw_markdown="# r2",
            ),
            RequestRow(
                filename="a1.md", status="approved", folder="archived",
                tool_name="a1", raw_markdown="# a1",
            ),
        ])
        db_session.commit()

        app = create_app()
        app.dependency_overrides[get_db] = lambda: (yield db_session)
        client = TestClient(app)
        body = client.get("/health").json()

        assert body["requests"]["resolved"] == 2
        assert body["requests"]["archived"] == 1
        assert body["requests"]["total"] == 3


# ---- /tools ----------------------------------------------------------


class TestToolsEndpointLiveness:
    def test_get_tools_returns_list_envelope(self, seeded_client):
        resp = seeded_client.get("/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] == 2

    def test_get_tools_by_id_returns_200(self, seeded_client, db_session):
        tool = db_session.query(Tool).filter(Tool.slug == "csvstat").one()
        resp = seeded_client.get(f"/tools/{tool.id}")
        assert resp.status_code == 200
        assert resp.json()["slug"] == "csvstat"

    def test_get_tools_missing_id_returns_404(self, seeded_client):
        resp = seeded_client.get("/tools/999999")
        assert resp.status_code == 404


# ---- /packs ----------------------------------------------------------


class TestPacksEndpointLiveness:
    def test_get_packs_returns_list_envelope(self, seeded_client):
        resp = seeded_client.get("/packs")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert body["total"] == 1


# ---- /requests/pending ------------------------------------------------


class TestRequestsPendingLiveness:
    def test_empty_pending_returns_envelope(self, seeded_client):
        resp = seeded_client.get("/requests/pending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0


# ---- /recommend (mocked service) ------------------------------------


class TestRecommendLiveness:
    def test_post_recommend_mocked_returns_200(self, seeded_client):
        resp = seeded_client.post("/recommend", json={"task": "analyze this CSV"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["model"] == "claude-opus-4-7"
        assert body["effort"] == "xhigh"
        assert len(body["recommendations"]) == 1
