"""Tests for core.recommend.parse — JSON parsing + fence tolerance
+ malformed-input error surface.

Parse failures must be observably distinct from memory outages:
this test suite asserts the exception type + preserves ordering +
handles the fence variants Opus has been seen to produce.
"""
from __future__ import annotations

import json

import pytest

from core.recommend.parse import (
    RecommendationParseError,
    parse_recommendation_response,
)


# ---- Happy paths ---------------------------------------------------------


class TestValidJSON:
    def _payload(self, recs: list[dict]) -> str:
        return json.dumps({"reasoning": "Lightweight first.", "recommendations": recs})

    def test_bare_json_parses(self):
        content = self._payload(
            [
                {
                    "rank": 1,
                    "tool_slug": "csvstat",
                    "tool_name": "csvstat",
                    "rationale": "Lightweight.",
                    "confidence": "high",
                    "is_in_catalog": True,
                }
            ]
        )
        reasoning, recs, _side = parse_recommendation_response(content)
        assert reasoning == "Lightweight first."
        assert len(recs) == 1
        assert recs[0].tool_slug == "csvstat"

    def test_json_fence_parses(self):
        inner = self._payload(
            [
                {
                    "rank": 1,
                    "tool_slug": "csvstat",
                    "tool_name": "csvstat",
                    "rationale": "Lightweight.",
                    "confidence": "high",
                    "is_in_catalog": True,
                }
            ]
        )
        content = f"```json\n{inner}\n```"
        reasoning, recs, _side = parse_recommendation_response(content)
        assert recs[0].tool_slug == "csvstat"

    def test_bare_triple_backtick_fence_parses(self):
        inner = self._payload(
            [
                {
                    "rank": 1,
                    "tool_slug": "csvstat",
                    "tool_name": "csvstat",
                    "rationale": "Lightweight.",
                    "confidence": "high",
                    "is_in_catalog": True,
                }
            ]
        )
        content = f"```\n{inner}\n```"
        reasoning, recs, _side = parse_recommendation_response(content)
        assert recs[0].tool_slug == "csvstat"

    def test_preserves_ordering(self):
        content = self._payload(
            [
                {
                    "rank": 1,
                    "tool_slug": "a",
                    "tool_name": "a",
                    "rationale": "r",
                    "confidence": "high",
                    "is_in_catalog": True,
                },
                {
                    "rank": 2,
                    "tool_slug": "b",
                    "tool_name": "b",
                    "rationale": "r",
                    "confidence": "medium",
                    "is_in_catalog": True,
                },
                {
                    "rank": 3,
                    "tool_slug": None,
                    "tool_name": "discovery-tool",
                    "rationale": "r",
                    "confidence": "low",
                    "is_in_catalog": False,
                },
            ]
        )
        _reasoning, recs, _side = parse_recommendation_response(content)
        assert [r.tool_name for r in recs] == ["a", "b", "discovery-tool"]
        assert recs[2].is_in_catalog is False
        assert recs[2].tool_slug is None

    def test_empty_recommendations_list_valid(self):
        """A response with an empty recommendations list is
        parse-valid; callers decide whether to 502 or return as-is.
        """
        content = json.dumps({"reasoning": "Nothing matches.", "recommendations": []})
        reasoning, recs, _side = parse_recommendation_response(content)
        assert reasoning == "Nothing matches."
        assert recs == []


# ---- Error surface (must raise RecommendationParseError) ----------------


class TestParseErrors:
    def test_empty_content_raises(self):
        with pytest.raises(RecommendationParseError, match="empty"):
            parse_recommendation_response("")

    def test_whitespace_only_raises(self):
        with pytest.raises(RecommendationParseError):
            parse_recommendation_response("   \n  \n")

    def test_malformed_json_raises(self):
        with pytest.raises(RecommendationParseError, match="JSON decode"):
            parse_recommendation_response("{not json")

    def test_top_level_must_be_object(self):
        with pytest.raises(RecommendationParseError, match="must be an object"):
            parse_recommendation_response('["a", "b"]')

    def test_missing_reasoning_raises(self):
        with pytest.raises(RecommendationParseError, match="reasoning"):
            parse_recommendation_response(json.dumps({"recommendations": []}))

    def test_missing_recommendations_raises(self):
        with pytest.raises(RecommendationParseError, match="recommendations"):
            parse_recommendation_response(json.dumps({"reasoning": "r"}))

    def test_reasoning_wrong_type_raises(self):
        with pytest.raises(RecommendationParseError, match="reasoning"):
            parse_recommendation_response(
                json.dumps({"reasoning": 123, "recommendations": []})
            )

    def test_recommendation_entry_missing_field(self):
        content = json.dumps(
            {
                "reasoning": "r",
                "recommendations": [
                    {
                        "rank": 1,
                        "tool_slug": "x",
                        # missing tool_name
                        "rationale": "r",
                        "confidence": "high",
                        "is_in_catalog": True,
                    }
                ],
            }
        )
        with pytest.raises(RecommendationParseError, match=r"recommendations\[0\]"):
            parse_recommendation_response(content)

    def test_recommendation_entry_bad_confidence(self):
        content = json.dumps(
            {
                "reasoning": "r",
                "recommendations": [
                    {
                        "rank": 1,
                        "tool_slug": "x",
                        "tool_name": "x",
                        "rationale": "r",
                        "confidence": "maximal",
                        "is_in_catalog": True,
                    }
                ],
            }
        )
        with pytest.raises(RecommendationParseError, match=r"recommendations\[0\]"):
            parse_recommendation_response(content)

    def test_recommendation_entry_not_dict(self):
        content = json.dumps(
            {"reasoning": "r", "recommendations": ["not-an-object"]}
        )
        with pytest.raises(RecommendationParseError, match="must be an object"):
            parse_recommendation_response(content)


# ---- Error class identity (distinct from memory-unavailable) ------------


class TestErrorClassDistinct:
    def test_parse_error_is_valueerror_not_runtimeerror(self):
        """Sanity: RecommendationParseError is a ValueError subclass;
        MemoryUnavailableError is a RuntimeError subclass. A broad
        `except RuntimeError` in the service must NOT accidentally
        catch parse errors — ensuring the two failure classes stay
        visibly distinct in logs.
        """
        try:
            parse_recommendation_response("{not json")
        except RecommendationParseError as exc:
            assert isinstance(exc, ValueError)
            assert not isinstance(exc, RuntimeError)


# ---- side_observations (Fix Day 4 Task 3 narration pattern 3) -----------


class TestSideObservations:
    """Optional top-level field. Absent or null → None. Present → list
    of strings (possibly empty). Malformed → RecommendationParseError.
    """

    _BASIC_RECS = [
        {
            "rank": 1,
            "tool_slug": "csvstat",
            "tool_name": "csvstat",
            "rationale": "Lightweight.",
            "confidence": "high",
            "is_in_catalog": True,
        }
    ]

    def _payload(self, extras: dict) -> str:
        base = {"reasoning": "r", "recommendations": self._BASIC_RECS}
        base.update(extras)
        return json.dumps(base)

    def test_absent_key_returns_none(self):
        """Omitting the key entirely reads as 'Opus surfaced no
        observations' — the None return signals absence.
        """
        _r, _recs, side = parse_recommendation_response(self._payload({}))
        assert side is None

    def test_explicit_null_returns_none(self):
        """Explicit `"side_observations": null` is also absence."""
        _r, _recs, side = parse_recommendation_response(
            self._payload({"side_observations": None})
        )
        assert side is None

    def test_empty_list_returns_empty_list(self):
        """`[]` is a distinct signal from None — Opus explicitly
        returned an empty list (the prompt allows it). The renderer
        collapses both the same way, but the parser preserves the
        distinction for any future consumer that cares.
        """
        _r, _recs, side = parse_recommendation_response(
            self._payload({"side_observations": []})
        )
        assert side == []

    def test_populated_list_round_trips(self):
        observations = [
            "`jq-old` is retired but would fit this task.",
            "`duckdb` is loaded-on-boot but hasn't been applied to CSV tasks recently.",
        ]
        _r, _recs, side = parse_recommendation_response(
            self._payload({"side_observations": observations})
        )
        assert side == observations

    def test_non_list_raises(self):
        with pytest.raises(
            RecommendationParseError, match="side_observations must be a list"
        ):
            parse_recommendation_response(
                self._payload({"side_observations": "not a list"})
            )

    def test_list_with_non_string_entry_raises(self):
        with pytest.raises(
            RecommendationParseError, match=r"side_observations\[1\]"
        ):
            parse_recommendation_response(
                self._payload({"side_observations": ["ok", 123]})
            )
