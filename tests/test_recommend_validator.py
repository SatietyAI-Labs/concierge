"""Tests for core.recommend.validator — Tier 1 drift detection.

Two concerns, separately covered:

1. **`validate_response_shape` correctness in isolation.** Given
   dicts shaped like real/drifted responses, the right drift
   categories appear in the returned list. No logging, no service
   wiring — pure function.

2. **Service wiring produces the observable drift surface.** Given
   a response shape that drifts, `service.recommend()` logs a
   `recommend.fixture_drift_detected` WARNING, bumps the
   `fixture_drift_count` counter, and returns the response
   successfully (never raises). This is the integration surface
   the soak operator depends on.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from core.memory import MemoryHit, MemoryUnavailableError
from core.recommend.client import AnthropicCall
from core.recommend.counters import RecommendCounters
from core.recommend.prompt import CatalogToolView
from core.recommend.schemas import RecommendRequest
from core.recommend.service import RecommendationService
from core.recommend.validator import validate_response_shape


# ---- Baseline valid dict ---------------------------------------------------
# Matches the moneyshot shape + fixture-spec from
# tests/test_recommend_pipeline.py. Each drift test below perturbs
# exactly one field so the drift message is attributable.


def _valid_response_dict() -> dict:
    return {
        "request_id": "33b0ae69-e1a0-4f2a-9b3c-4d5e6f7a8b9c",
        "recommendations": [
            {
                "rank": 1,
                "tool_slug": "csvstat",
                "tool_name": "csvstat",
                "rationale": "Lightweight CSV stats CLI.",
                "confidence": "high",
                "is_in_catalog": True,
                "category": "data-processing",
                "install_method": "pip-user",
                "risk_cost": "~5MB wheel; MIT",
            },
            {
                "rank": 2,
                "tool_slug": None,
                "tool_name": "miller",
                "rationale": "Streaming CSV processor; discovery.",
                "confidence": "medium",
                "is_in_catalog": False,
                "category": "data-processing",
                "install_method": "apt",
                "risk_cost": None,
            },
        ],
        "memory_available": True,
        "memory_hit_count": 1,
        "model": "claude-opus-4-7",
        "effort": "xhigh",
        "latency_ms": {"total": 9500, "memory": 4, "model": 8500, "parse": 2},
        "token_usage": {"input": 1200, "output": 280, "total": 1480},
        "reasoning": "Top-level rationale across the ranked list.",
        "stop_reason": "end_turn",
    }


# ---- Pure-function tests ---------------------------------------------------


class TestValidatorNoDrift:
    def test_valid_moneyshot_shape_produces_no_drift(self):
        drift = validate_response_shape(
            _valid_response_dict(), request_id="33b0ae69-e1a0"
        )
        assert drift == []

    def test_valid_empty_recs_also_clean(self):
        """Empty-recs is a real valid shape — the pipeline already
        handles it cleanly. Validator must not flag it.
        """
        d = _valid_response_dict()
        d["recommendations"] = []
        drift = validate_response_shape(d, request_id="r1")
        assert drift == []

    def test_none_stop_reason_ok(self):
        d = _valid_response_dict()
        d["stop_reason"] = None
        drift = validate_response_shape(d, request_id="r1")
        assert drift == []


class TestValidatorTopLevelShapeDrift:
    def test_missing_model_field_flagged(self):
        d = _valid_response_dict()
        del d["model"]
        drift = validate_response_shape(d, request_id="r1")
        assert any("top_level_field_missing:model" in m for m in drift)

    def test_wrong_type_memory_available_flagged(self):
        d = _valid_response_dict()
        d["memory_available"] = "yes"  # should be bool
        drift = validate_response_shape(d, request_id="r1")
        assert any(
            "top_level_field_wrong_type:memory_available" in m for m in drift
        )

    def test_recommendations_not_list_short_circuits(self):
        """When recommendations isn't a list, per-rec checks must
        not crash. Top-level check reports the issue and the
        function returns cleanly.
        """
        d = _valid_response_dict()
        d["recommendations"] = "oops"
        drift = validate_response_shape(d, request_id="r1")
        assert any("recommendations" in m for m in drift)
        # Must not crash and must not produce per-rec noise.
        assert not any("rank_" in m for m in drift)


class TestValidatorRankConsistency:
    def test_sparse_ranks_flagged(self):
        """Opus returns 1, 3 instead of 1, 2 — real drift signal."""
        d = _valid_response_dict()
        d["recommendations"][1]["rank"] = 3
        drift = validate_response_shape(d, request_id="r1")
        assert any("rank_not_dense_1_indexed" in m for m in drift)

    def test_zero_indexed_ranks_flagged(self):
        d = _valid_response_dict()
        d["recommendations"][0]["rank"] = 0
        drift = validate_response_shape(d, request_id="r1")
        assert any("rank_not_dense_1_indexed" in m for m in drift)

    def test_rank_wrong_type_flagged(self):
        d = _valid_response_dict()
        d["recommendations"][0]["rank"] = "1"  # str, not int
        drift = validate_response_shape(d, request_id="r1")
        assert any("rank_wrong_type" in m for m in drift)


class TestValidatorCatalogFlagConsistency:
    def test_in_catalog_with_null_slug_flagged(self):
        d = _valid_response_dict()
        d["recommendations"][0]["tool_slug"] = None
        drift = validate_response_shape(d, request_id="r1")
        assert any("in_catalog_but_null_slug:index=0" in m for m in drift)

    def test_discovery_with_non_null_slug_flagged(self):
        """Opus starts attaching a slug to discovery recommendations —
        violates JSON_OUTPUT_ENVELOPE rule, signals either model
        evolution or prompt-following degradation.
        """
        d = _valid_response_dict()
        d["recommendations"][1]["tool_slug"] = "some-slug"
        drift = validate_response_shape(d, request_id="r1")
        assert any(
            "discovery_but_non_null_slug:index=1" in m for m in drift
        )

    def test_in_catalog_empty_string_slug_flagged(self):
        """Empty string is as bad as None for rendering — the slug
        badge in render.py won't print a useful value."""
        d = _valid_response_dict()
        d["recommendations"][0]["tool_slug"] = ""
        drift = validate_response_shape(d, request_id="r1")
        assert any("in_catalog_but_null_slug:index=0" in m for m in drift)


class TestValidatorStopReasonDrift:
    def test_unknown_stop_reason_flagged(self):
        """A stop_reason Anthropic adds that we haven't seen before."""
        d = _valid_response_dict()
        d["stop_reason"] = "quantum_collapse"
        drift = validate_response_shape(d, request_id="r1")
        assert any(
            "stop_reason_outside_known_set" in m and "quantum_collapse" in m
            for m in drift
        )

    def test_refusal_is_a_known_stop_reason(self):
        """refusal was added in late 2025 and must not be flagged
        as drift — the validator's known set must include it.
        """
        d = _valid_response_dict()
        d["stop_reason"] = "refusal"
        drift = validate_response_shape(d, request_id="r1")
        assert not any("stop_reason_outside_known_set" in m for m in drift)


class TestValidatorEffortDrift:
    def test_unknown_effort_value_flagged(self):
        d = _valid_response_dict()
        d["effort"] = "extreme"
        drift = validate_response_shape(d, request_id="r1")
        assert any(
            "effort_outside_known_set" in m and "extreme" in m for m in drift
        )


class TestValidatorRichContentDrift:
    """Rich in-chat content fields (category / install_method /
    risk_cost) must be present on every recommendation. Explicit
    null is acceptable — key absence is drift.
    """

    def test_missing_category_flagged(self):
        d = _valid_response_dict()
        del d["recommendations"][0]["category"]
        drift = validate_response_shape(d, request_id="r1")
        assert any(
            "rich_content_missing:category:index=0" in m for m in drift
        )

    def test_missing_install_method_flagged(self):
        d = _valid_response_dict()
        del d["recommendations"][1]["install_method"]
        drift = validate_response_shape(d, request_id="r1")
        assert any(
            "rich_content_missing:install_method:index=1" in m for m in drift
        )

    def test_missing_risk_cost_flagged(self):
        d = _valid_response_dict()
        del d["recommendations"][0]["risk_cost"]
        drift = validate_response_shape(d, request_id="r1")
        assert any(
            "rich_content_missing:risk_cost:index=0" in m for m in drift
        )

    def test_explicit_null_values_not_flagged(self):
        """Opus saying 'I have no confident value' (null) is fine;
        only missing key is drift.
        """
        d = _valid_response_dict()
        d["recommendations"][0]["category"] = None
        d["recommendations"][0]["install_method"] = None
        d["recommendations"][0]["risk_cost"] = None
        drift = validate_response_shape(d, request_id="r1")
        assert not any("rich_content_missing" in m for m in drift)


# ---- Service-wiring integration tests --------------------------------------
# Drives the full service.recommend() flow with a FakeAnthropic that
# returns content whose parsed response dict drifts. Verifies the
# WARNING log + counter bump + no-raise contract.


@dataclass
class _FakeMemory:
    raise_on_search: bool = False

    def search(self, q, *, limit=5):
        if self.raise_on_search:
            raise MemoryUnavailableError("stub")
        return []


@dataclass
class _FakeAnthropic:
    content: str = ""
    effort: str = "xhigh"

    def call(self, *, system, user):
        return AnthropicCall(
            content=self.content,
            stop_reason="end_turn",
            tokens_in=100,
            tokens_out=50,
            model_echo="claude-opus-4-7",
            latency_ms=7,
        )


def _catalog() -> list[CatalogToolView]:
    return [
        CatalogToolView(
            slug="csvstat",
            name="csvstat",
            description="CSV stats",
            category="data",
            pack_slug="csvkit",
            is_in_manifest=True,
            is_active=True,
        )
    ]


def _service(content: str) -> tuple[RecommendationService, RecommendCounters]:
    counters = RecommendCounters()
    svc = RecommendationService(
        memory=_FakeMemory(),  # type: ignore[arg-type]
        anthropic=_FakeAnthropic(content=content),  # type: ignore[arg-type]
        fetch_catalog=_catalog,
        counters=counters,
    )
    return svc, counters


def _content_with_sparse_ranks() -> str:
    """A real-shaped Opus response where rank values are 1 and 3
    instead of 1 and 2. The parse layer accepts it (each rec is
    individually Pydantic-valid — rank >= 1); the drift check
    flags it because the list is not dense.
    """
    return json.dumps(
        {
            "reasoning": "Two tools, sparse ranks.",
            "recommendations": [
                {
                    "rank": 1,
                    "tool_slug": "csvstat",
                    "tool_name": "csvstat",
                    "rationale": "ok",
                    "confidence": "high",
                    "is_in_catalog": True,
                },
                {
                    "rank": 3,
                    "tool_slug": None,
                    "tool_name": "miller",
                    "rationale": "ok",
                    "confidence": "medium",
                    "is_in_catalog": False,
                },
            ],
        }
    )


def _content_clean() -> str:
    return json.dumps(
        {
            "reasoning": "Clean response.",
            "recommendations": [
                {
                    "rank": 1,
                    "tool_slug": "csvstat",
                    "tool_name": "csvstat",
                    "rationale": "ok",
                    "confidence": "high",
                    "is_in_catalog": True,
                }
            ],
        }
    )


class TestServiceDriftDetectionWiring:
    def test_drifted_response_logs_warning_and_bumps_counter(self, caplog):
        svc, counters = _service(_content_with_sparse_ranks())

        with caplog.at_level(logging.WARNING, logger="core.recommend.service"):
            response = svc.recommend(RecommendRequest(task="analyze CSV"))

        # Contract: the user's call still returns a well-formed response.
        assert response.recommendations is not None
        assert len(response.recommendations) == 2

        # Counter bumped exactly once per drifted call.
        assert counters.snapshot()["fixture_drift"] == 1

        # WARNING log line has the expected marker + summary text.
        drift_records = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING
            and "recommend.fixture_drift_detected" in r.getMessage()
        ]
        assert len(drift_records) == 1
        msg = drift_records[0].getMessage()
        assert "rank_not_dense_1_indexed" in msg
        assert "request_id=" in msg
        assert "drift_count=" in msg
        assert 'drift_summary="' in msg

    def test_clean_response_does_not_trigger_drift_log(self, caplog):
        svc, counters = _service(_content_clean())

        with caplog.at_level(logging.WARNING, logger="core.recommend.service"):
            svc.recommend(RecommendRequest(task="analyze CSV"))

        # Counter not bumped.
        assert counters.snapshot()["fixture_drift"] == 0

        # No drift WARNING emitted.
        drift_records = [
            r
            for r in caplog.records
            if "recommend.fixture_drift_detected" in r.getMessage()
        ]
        assert drift_records == []

    def test_drift_detection_does_not_raise_to_caller(self):
        """Contract: drift is a signal, not a failure. The user's
        recommend() call must succeed even when drift is detected.
        """
        svc, _ = _service(_content_with_sparse_ranks())
        response = svc.recommend(RecommendRequest(task="analyze CSV"))
        assert response.request_id is not None
        assert len(response.recommendations) == 2

    def test_drift_counter_accumulates_across_calls(self):
        """Two drifted calls in a row → counter reads 2. Guards
        against a once-per-process accidental latch.
        """
        svc, counters = _service(_content_with_sparse_ranks())
        svc.recommend(RecommendRequest(task="a"))
        svc.recommend(RecommendRequest(task="b"))
        assert counters.snapshot()["fixture_drift"] == 2
