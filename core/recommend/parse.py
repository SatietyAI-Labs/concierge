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
from typing import Any

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
) -> tuple[str, list[ToolRecommendation]]:
    """Parse an Anthropic response content string into a
    (reasoning, recommendations) tuple.

    Raises:
        RecommendationParseError: if content is not valid JSON,
            not an object, missing required top-level keys, or
            contains malformed recommendation entries.
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

    return reasoning, recommendations
