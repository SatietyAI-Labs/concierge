"""Tests for POST /recommend HTTP endpoint.

Router-level contract:

  - Happy path → 200 with RecommendResponse-shape body
  - Empty body / missing task → 422
  - MemoryUnavailableError → STILL 200 (graceful-degradation
    surfaces at the response field, not at the HTTP status)
  - RecommendationParseError → 502 with structured error body
  - AnthropicClientError → 502 with structured error body (distinct
    error code from parse failure)

Service-level behavior has already been asserted in
`test_recommend_service.py`; this suite exercises only the HTTP
boundary, with the service mocked via dependency override.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from core.api.recommend import get_recommendation_service
from core.app import create_app
from core.memory import MemoryUnavailableError
from core.recommend.client import AnthropicClientError
from core.recommend.parse import RecommendationParseError
from core.recommend.schemas import (
    LatencyBreakdown,
    RecommendRequest,
    RecommendResponse,
    TokenUsage,
    ToolRecommendation,
)


# ---- Service stand-ins ---------------------------------------------------


@dataclass
class _StubService:
    """Stand-in that mimics `RecommendationService.recommend(...)`."""

    response: RecommendResponse | None = None
    raise_exc: Exception | None = None

    def recommend(self, req: RecommendRequest) -> RecommendResponse:
        if self.raise_exc is not None:
            raise self.raise_exc
        assert self.response is not None
        return self.response


def _happy_response(*, memory_available: bool = True) -> RecommendResponse:
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
        memory_available=memory_available,
        memory_hit_count=2 if memory_available else 0,
        model="claude-opus-4-7",
        temperature=0.0,
        latency_ms=LatencyBreakdown(total=1200, memory=50, model=1100, parse=5),
        token_usage=TokenUsage(input=1500, output=200, total=1700),
        reasoning="Prefer lightweight CLIs.",
        stop_reason="end_turn",
    )


def _client_with_service(service: _StubService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_recommendation_service] = lambda: service
    return TestClient(app)


# ---- Happy path ----------------------------------------------------------


class TestHappyPath:
    def test_happy_post_returns_200_with_body(self):
        client = _client_with_service(_StubService(response=_happy_response()))
        resp = client.post("/recommend", json={"task": "analyze this CSV"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["request_id"] == "11111111-2222-3333-4444-555555555555"
        assert body["memory_available"] is True
        assert body["memory_hit_count"] == 2
        assert body["model"] == "claude-opus-4-7"
        assert body["temperature"] == 0.0
        assert body["stop_reason"] == "end_turn"
        assert len(body["recommendations"]) == 1

    def test_full_request_accepted(self):
        client = _client_with_service(_StubService(response=_happy_response()))
        resp = client.post(
            "/recommend",
            json={
                "task": "analyze this CSV",
                "cwd": "/home/lewie/work",
                "task_hint": "data-analysis",
                "active_tools": ["pandas"],
            },
        )
        assert resp.status_code == 200


# ---- Validation errors ---------------------------------------------------


class TestValidation:
    def test_empty_body_returns_422(self):
        client = _client_with_service(_StubService(response=_happy_response()))
        resp = client.post("/recommend", json={})
        assert resp.status_code == 422

    def test_empty_task_returns_422(self):
        client = _client_with_service(_StubService(response=_happy_response()))
        resp = client.post("/recommend", json={"task": ""})
        assert resp.status_code == 422

    def test_missing_task_returns_422(self):
        client = _client_with_service(_StubService(response=_happy_response()))
        resp = client.post(
            "/recommend", json={"cwd": "/home/lewie"}  # no `task`
        )
        assert resp.status_code == 422


# ---- Graceful-degradation: memory unavailable surfaces as 200 ----------


class TestMemoryUnavailableIsNot502:
    """The adversarial HTTP-layer assertion: MemoryUnavailableError
    is a SERVICE-SIDE concern that the service handles internally
    (sets `memory_available=False`, serves a recommendation anyway).
    At the HTTP layer this must land as a 200, not a 502 — the
    caller's code path MUST be able to distinguish "memory was down"
    from "Opus was broken."
    """

    def test_memory_unavailable_path_returns_200_with_flag(self):
        client = _client_with_service(
            _StubService(response=_happy_response(memory_available=False))
        )
        resp = client.post("/recommend", json={"task": "t"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["memory_available"] is False
        assert body["memory_hit_count"] == 0
        # Recommendations still served — fallback is not an empty shell.
        assert len(body["recommendations"]) >= 1

    def test_service_raising_memory_error_directly_would_500(self):
        """Defense-in-depth sanity: if something in future refactor
        accidentally lets `MemoryUnavailableError` bubble past the
        service, the HTTP boundary does NOT silently translate it to
        a 200. (The correct handling is service-side per the
        operational-first design; we verify that the router does not
        catch it.) This test pins the contract.
        """
        client = _client_with_service(
            _StubService(raise_exc=MemoryUnavailableError("oops"))
        )
        # FastAPI default handler for an un-handled RuntimeError
        # returns 500 via Starlette — this is the right behavior:
        # we DO NOT want silent 200s on an unhandled memory error.
        with pytest.raises(MemoryUnavailableError):
            client.post("/recommend", json={"task": "t"})


# ---- 502 paths -----------------------------------------------------------


class TestParseFailure502:
    def test_parse_failure_returns_502_with_structured_body(self):
        client = _client_with_service(
            _StubService(raise_exc=RecommendationParseError("bad json"))
        )
        resp = client.post("/recommend", json={"task": "t"})
        assert resp.status_code == 502
        body = resp.json()
        assert body["detail"]["error"] == "recommendation_parse_failed"
        assert "bad json" in body["detail"]["message"]


class TestAnthropicFailure502:
    def test_anthropic_failure_returns_502_with_distinct_error_code(self):
        client = _client_with_service(
            _StubService(raise_exc=AnthropicClientError("upstream 503"))
        )
        resp = client.post("/recommend", json={"task": "t"})
        assert resp.status_code == 502
        body = resp.json()
        # Distinct from parse failure — operational logs need to
        # tell these apart.
        assert body["detail"]["error"] == "anthropic_client_failed"
        assert "upstream 503" in body["detail"]["message"]

    def test_parse_and_anthropic_error_codes_are_distinct(self):
        """Pins the invariant that the two 502 paths surface
        distinct `error` codes in their bodies.
        """
        parse_client = _client_with_service(
            _StubService(raise_exc=RecommendationParseError("x"))
        )
        anth_client = _client_with_service(
            _StubService(raise_exc=AnthropicClientError("y"))
        )
        parse_body = parse_client.post("/recommend", json={"task": "t"}).json()
        anth_body = anth_client.post("/recommend", json={"task": "t"}).json()
        assert (
            parse_body["detail"]["error"] != anth_body["detail"]["error"]
        )
