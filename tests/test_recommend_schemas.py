"""Tests for core.recommend.schemas — Pydantic request/response shape.

These are plumbing tests per the N6 framing: request validation,
response field invariants, discriminated-state fields (confidence
Literal, memory_available bool). No semantic assertions.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.recommend.schemas import (
    LatencyBreakdown,
    RecommendRequest,
    RecommendResponse,
    TokenUsage,
    ToolRecommendation,
)


class TestRecommendRequest:
    def test_minimal_request(self):
        req = RecommendRequest(task="analyze this CSV")
        assert req.task == "analyze this CSV"
        assert req.cwd is None
        assert req.task_hint is None
        assert req.active_tools is None

    def test_full_request(self):
        req = RecommendRequest(
            task="analyze this CSV",
            cwd="/home/lewie/work",
            task_hint="data-analysis",
            active_tools=["pandas", "matplotlib"],
            agent_id="scout",
        )
        assert req.cwd == "/home/lewie/work"
        assert req.task_hint == "data-analysis"
        assert req.active_tools == ["pandas", "matplotlib"]
        assert req.agent_id == "scout"

    def test_empty_task_rejected(self):
        with pytest.raises(ValidationError):
            RecommendRequest(task="")

    def test_task_required(self):
        with pytest.raises(ValidationError):
            RecommendRequest()  # type: ignore[call-arg]

    def test_agent_id_optional(self):
        """Stage 1A item 3 — `agent_id` defaults to None when omitted.

        Minimal `RecommendRequest(task=...)` construction must keep
        working unchanged; this is the contract the 30+ existing
        kwarg-only test fixture sites depend on.
        """
        req = RecommendRequest(task="t")
        assert req.agent_id is None

    def test_agent_id_str_accepted(self):
        """Stage 1A item 3 — free-text `agent_id` per the platform-
        agnostic schema contract. No enum constraint; the adapter
        layer maps native agent identity onto this field.
        """
        req = RecommendRequest(task="t", agent_id="scout")
        assert req.agent_id == "scout"

        # Round-trip through JSON serialization (FastAPI does this on
        # the wire); ensures pydantic doesn't drop the field at the
        # serialization boundary.
        round_trip = RecommendRequest.model_validate_json(req.model_dump_json())
        assert round_trip.agent_id == "scout"


class TestToolRecommendation:
    def test_in_catalog_recommendation(self):
        rec = ToolRecommendation(
            rank=1,
            tool_slug="csvstat",
            tool_name="csvstat",
            rationale="Lightweight CLI; outputs summary stats.",
            confidence="high",
            is_in_catalog=True,
        )
        assert rec.rank == 1
        assert rec.is_in_catalog is True

    def test_discovery_recommendation_with_null_slug(self):
        rec = ToolRecommendation(
            rank=2,
            tool_slug=None,
            tool_name="csvkit",
            rationale="Suite of CSV utilities not yet in catalog.",
            confidence="medium",
            is_in_catalog=False,
        )
        assert rec.tool_slug is None
        assert rec.is_in_catalog is False

    def test_rank_must_be_positive(self):
        with pytest.raises(ValidationError):
            ToolRecommendation(
                rank=0,
                tool_slug="x",
                tool_name="x",
                rationale="r",
                confidence="high",
                is_in_catalog=True,
            )

    def test_confidence_literal_enforced(self):
        with pytest.raises(ValidationError):
            ToolRecommendation(
                rank=1,
                tool_slug="x",
                tool_name="x",
                rationale="r",
                confidence="unknown",  # type: ignore[arg-type]
                is_in_catalog=True,
            )


class TestRecommendResponse:
    def _valid_payload(self) -> dict:
        return {
            "request_id": "11111111-2222-3333-4444-555555555555",
            "recommendations": [
                {
                    "rank": 1,
                    "tool_slug": "csvstat",
                    "tool_name": "csvstat",
                    "rationale": "Lightweight.",
                    "confidence": "high",
                    "is_in_catalog": True,
                }
            ],
            "memory_available": True,
            "memory_hit_count": 3,
            "model": "claude-opus-4-7",
            "effort": "xhigh",
            "latency_ms": {"total": 1500, "memory": 100, "model": 1300, "parse": 5},
            "token_usage": {"input": 2500, "output": 400, "total": 2900},
            "reasoning": "Prefer lightweight CLI tools.",
            "stop_reason": "end_turn",
        }

    def test_happy_response(self):
        resp = RecommendResponse.model_validate(self._valid_payload())
        assert resp.request_id == "11111111-2222-3333-4444-555555555555"
        assert resp.memory_available is True
        assert resp.memory_hit_count == 3
        assert resp.model == "claude-opus-4-7"
        assert resp.effort == "xhigh"
        assert resp.stop_reason == "end_turn"
        assert len(resp.recommendations) == 1

    def test_memory_unavailable_response_shape(self):
        payload = self._valid_payload()
        payload["memory_available"] = False
        payload["memory_hit_count"] = 0
        resp = RecommendResponse.model_validate(payload)
        assert resp.memory_available is False
        assert resp.memory_hit_count == 0

    def test_empty_memory_vs_unavailable_are_distinct(self):
        """memory_hit_count=0 with memory_available=True is a valid
        healthy-call-with-no-relevant-memory state; distinct from
        outage.
        """
        payload = self._valid_payload()
        payload["memory_available"] = True
        payload["memory_hit_count"] = 0
        resp = RecommendResponse.model_validate(payload)
        assert resp.memory_available is True
        assert resp.memory_hit_count == 0

    def test_memory_hit_count_nonneg(self):
        payload = self._valid_payload()
        payload["memory_hit_count"] = -1
        with pytest.raises(ValidationError):
            RecommendResponse.model_validate(payload)

    def test_latency_breakdown_all_phases_present(self):
        lb = LatencyBreakdown(total=100, memory=10, model=80, parse=5)
        assert lb.total == 100
        assert lb.memory == 10
        assert lb.model == 80
        assert lb.parse == 5

    def test_token_usage_defaults_zero(self):
        tu = TokenUsage()
        assert tu.input == 0
        assert tu.output == 0
        assert tu.total == 0
