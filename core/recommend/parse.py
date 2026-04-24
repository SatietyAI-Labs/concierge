"""Response parsing for POST /recommend.

The Anthropic response content is expected to be a JSON object
matching the `JSON_OUTPUT_ENVELOPE` schema (see `prompt.py`). In
practice Opus sometimes wraps JSON in ```json fences despite the
envelope instructions; the parser tolerates both fenced and bare
JSON.

Operational-first: parser failure is a **distinct** failure class
from memory-unavailability. This module raises
`RecommendationParseError` on malformed output; the service layer
logs this at ERROR and returns HTTP 502. An operator reading soak
logs can distinguish "Opus returned something we can't parse"
from "memory was down" because the two surface as different log
levels on different log.names.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from core.recommend.schemas import ToolRecommendation


class RecommendationParseError(ValueError):
    """Raised when the Anthropic response content cannot be
    parsed into a list of recommendations.
    """


# Matches a triple-backtick fence optionally tagged with a language.
# Non-greedy body capture so multi-fence input (rare) picks the
# first fence rather than swallowing everything.
_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n(?P<body>.*?)\n\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def _strip_fence(content: str) -> str:
    """Remove a wrapping ```json / ``` fence if present; otherwise
    return the content unchanged. Only matches a fence that wraps
    the entire content; inline fences inside a prose response are
    treated as malformed and will fail JSON parsing downstream.
    """
    m = _FENCE_RE.match(content)
    if m:
        return m.group("body")
    return content


def _require(payload: dict, key: str, expected_type: type) -> Any:
    if key not in payload:
        raise RecommendationParseError(f"missing required key: {key!r}")
    val = payload[key]
    if not isinstance(val, expected_type):
        raise RecommendationParseError(
            f"key {key!r} has wrong type: expected {expected_type.__name__}, "
            f"got {type(val).__name__}"
        )
    return val


def parse_recommendation_response(
    content: str,
) -> tuple[str, list[ToolRecommendation], Optional[list[str]]]:
    """Parse an Anthropic response content string into a
    (reasoning, recommendations, side_observations) tuple.

    `side_observations` is Fix Day 4 Task 3's optional field: None
    when the key is absent or explicitly null, a list of strings
    (possibly empty) when present. Malformed shapes (non-list, list
    with non-string entries) raise RecommendationParseError so the
    service layer's standard error pathway surfaces them.

    Raises:
        RecommendationParseError: if content is not valid JSON,
            not an object, missing required top-level keys, or
            contains malformed recommendation or side_observations
            entries.
    """
    stripped = _strip_fence(content).strip()
    if not stripped:
        raise RecommendationParseError("response content was empty")

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise RecommendationParseError(
            f"JSON decode failed at position {exc.pos}: {exc.msg}"
        ) from exc

    if not isinstance(payload, dict):
        raise RecommendationParseError(
            f"top-level JSON must be an object, got {type(payload).__name__}"
        )

    reasoning = _require(payload, "reasoning", str)
    raw_recs = _require(payload, "recommendations", list)

    recommendations: list[ToolRecommendation] = []
    for idx, raw in enumerate(raw_recs):
        if not isinstance(raw, dict):
            raise RecommendationParseError(
                f"recommendations[{idx}] must be an object, got {type(raw).__name__}"
            )
        try:
            rec = ToolRecommendation.model_validate(raw)
        except Exception as exc:  # Pydantic ValidationError
            raise RecommendationParseError(
                f"recommendations[{idx}] validation failed: {exc}"
            ) from exc
        recommendations.append(rec)

    side_observations = _parse_side_observations(payload)

    return reasoning, recommendations, side_observations


def _parse_side_observations(payload: dict) -> Optional[list[str]]:
    """Parse the optional `side_observations` top-level key.

    Returns None when the key is absent OR explicitly null (both
    read as "Opus did not surface observations"). Returns a list
    of strings when present as a list — empty list passes through.
    Raises RecommendationParseError on list-with-non-string entries
    or non-list-non-null values.
    """
    if "side_observations" not in payload:
        return None
    raw = payload["side_observations"]
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise RecommendationParseError(
            f"side_observations must be a list or null, got {type(raw).__name__}"
        )
    for idx, item in enumerate(raw):
        if not isinstance(item, str):
            raise RecommendationParseError(
                f"side_observations[{idx}] must be a string, got {type(item).__name__}"
            )
    return list(raw)
