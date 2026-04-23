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
                is_active=True,
            ),
            Tool(
                slug="pandas",
                name="pandas",
                is_in_manifest=True,
                is_active=False,  # dormant
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
