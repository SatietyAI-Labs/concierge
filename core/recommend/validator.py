"""Self-detecting drift on real Anthropic response shape.

## Why this exists

`tests/test_recommend_pipeline.py` defines — via three fixture
scenarios modeled on the 2026-04-22 16:27 moneyshot baseline — what
a valid recommendation response shape looks like. Those tests are
CI-safe (no real API). This module runs the **same structural
invariants** against live responses in production, so the day Opus
4.7's output shape evolves past the fixture specification, we don't
have to remember to check: the operator sees a
`recommend.fixture_drift_detected` WARNING in the log and a
`fixture_drift_count` bump in `/health`.

This is on-mission for Concierge's tool-awareness layer — Concierge
knows when its own assumptions are stale, rather than relying on
humans to catch it.

## What this does NOT do

- Does NOT raise. Drift is a signal, not a failure — user calls
  still complete and return the response regardless.
- Does NOT enforce Pydantic-level schema (that's already done by
  `parse_recommendation_response` via `ToolRecommendation.model_
  validate`). This layer catches invariants one level above Pydantic:
  cross-field consistency, value-set extensions, semantic plausibility.
- Does NOT attempt to repair or reshape the response. Downstream
  renderers already defensively `.get(..., default)` on every key.

## What it catches (the drift surface)

Four categories, each mapping to a potential real-world drift mode:

1. **Top-level shape drift** — missing or unexpectedly-typed fields
   on the response dict that the render layer reads.
2. **Rank consistency drift** — `rank` values not forming a dense
   1-indexed sequence (Opus returns 1,3,5 instead of 1,2,3).
3. **Catalog-flag consistency drift** — `tool_slug` null/non-null
   inconsistent with `is_in_catalog` (the JSON_OUTPUT_ENVELOPE says
   `is_in_catalog: true` requires a non-null slug).
4. **Stop-reason drift** — `stop_reason` outside the known Anthropic
   set. Signals either a new SDK/API-level value we should handle
   or (more likely during soak) truncation we should investigate.

## Future-work hook

Tier 3 (auto-reseed: capture new shapes, regenerate fixtures,
auto-commit if tests pass) is the logical next step. Not scoped for
tonight — documented in the N14 commit's "next steps" for a
separable future slot. The detection + counter + log surface built
here is the prerequisite.
"""
from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


# Known values — drift outside these sets triggers a WARNING.
_KNOWN_CONFIDENCES = {"high", "medium", "low"}
_KNOWN_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
# Anthropic's documented stop_reason values for the messages API.
# `refusal` was added in late 2025 and is explicitly part of this
# set; a value outside this list is the drift signal.
_KNOWN_STOP_REASONS = {
    "end_turn",
    "max_tokens",
    "stop_sequence",
    "tool_use",
    "refusal",
    "pause_turn",
}


def validate_response_shape(
    response: dict[str, Any], *, request_id: str
) -> list[str]:
    """Check a recommendation response dict against the fixture-spec
    invariants. Returns a list of human-readable drift messages;
    an empty list means no drift detected.

    The caller is responsible for logging the drift messages
    (typically via the service layer's WARNING channel) and bumping
    the counter. This function is pure — no side effects, no I/O —
    so it can be unit-tested in isolation and called from any code
    path that has a `RecommendResponse.model_dump()` dict in hand.

    `request_id` is accepted to match the caller's logging pattern
    but is not embedded in the returned messages (the caller
    prepends it to the log line). Keeps the messages reusable for
    non-logging consumers (e.g., a future UI surface).
    """
    drift: list[str] = []

    # 1. Top-level shape — every field the render layer reads must
    # be the type render.py expects. The renderer uses .get(...) with
    # defaults, so a missing field won't crash, but the operator
    # wants to know the field evaporated.
    drift.extend(_check_top_level_shape(response))

    recommendations = response.get("recommendations")
    if not isinstance(recommendations, list):
        # Without a valid recommendations list we can't run the
        # per-rec checks; top-level drift already captured it.
        return drift

    # 2. Rank consistency — dense 1-indexed sequence matching list
    # index + 1. Guards against Opus returning sparse or misaligned
    # ranks; the render layer prints `rank` verbatim.
    drift.extend(_check_rank_consistency(recommendations))

    # 3. Catalog-flag consistency — JSON_OUTPUT_ENVELOPE rule:
    # is_in_catalog=True requires non-null slug; False requires null.
    drift.extend(_check_catalog_flag_consistency(recommendations))

    # 4. Stop-reason drift — tracks the Anthropic-side value space.
    drift.extend(_check_stop_reason(response))

    # 5. Effort drift — guards against the effort value being outside
    # the documented set (e.g., a new tier added upstream that our
    # config doesn't know about).
    drift.extend(_check_effort(response))

    # 6. Rich in-chat content fields. Opus is instructed to emit
    # category / install_method / risk_cost on every recommendation
    # (explicit null is fine; key missing is drift). Surfaces Fix
    # Day 1 Q2 structural gap as a drift signal so we notice when
    # Opus starts silently dropping a field.
    drift.extend(_check_rich_content_fields(recommendations))

    return drift


# ---- Individual checks ---------------------------------------------------


def _check_top_level_shape(response: dict[str, Any]) -> list[str]:
    """The render layer reads these fields. Missing or wrong-typed
    is drift. Pydantic would normally catch this at parse time, but
    if a service-side refactor changes the response dict shape
    before the renderer, we want the warning to fire at call time,
    not at fixture-refresh time.
    """
    drift: list[str] = []
    expected_types: dict[str, type | tuple[type, ...]] = {
        "request_id": str,
        "recommendations": list,
        "memory_available": bool,
        "memory_hit_count": int,
        "model": str,
        "effort": str,
        # reasoning and stop_reason are Optional[str] in the schema.
        "reasoning": (str, type(None)),
        "stop_reason": (str, type(None)),
    }
    for key, typ in expected_types.items():
        if key not in response:
            drift.append(f"top_level_field_missing:{key}")
            continue
        if not isinstance(response[key], typ):
            got = type(response[key]).__name__
            drift.append(
                f"top_level_field_wrong_type:{key} "
                f"expected={getattr(typ, '__name__', typ)} got={got}"
            )
    return drift


def _check_rank_consistency(recommendations: list[Any]) -> list[str]:
    drift: list[str] = []
    for idx, rec in enumerate(recommendations):
        if not isinstance(rec, dict):
            drift.append(f"recommendation_not_dict:index={idx}")
            continue
        rank = rec.get("rank")
        if not isinstance(rank, int):
            drift.append(
                f"rank_wrong_type:index={idx} "
                f"got={type(rank).__name__}"
            )
            continue
        if rank != idx + 1:
            drift.append(
                f"rank_not_dense_1_indexed:index={idx} "
                f"expected_rank={idx + 1} got_rank={rank}"
            )
    return drift


def _check_catalog_flag_consistency(recommendations: list[Any]) -> list[str]:
    drift: list[str] = []
    for idx, rec in enumerate(recommendations):
        if not isinstance(rec, dict):
            continue  # already reported by rank check
        is_in_catalog = rec.get("is_in_catalog")
        tool_slug = rec.get("tool_slug")
        if is_in_catalog is True and tool_slug in (None, ""):
            drift.append(
                f"in_catalog_but_null_slug:index={idx} "
                "(JSON_OUTPUT_ENVELOPE requires non-null slug when "
                "is_in_catalog=True)"
            )
        elif is_in_catalog is False and tool_slug not in (None, ""):
            drift.append(
                f"discovery_but_non_null_slug:index={idx} "
                f"slug={tool_slug!r} "
                "(JSON_OUTPUT_ENVELOPE requires null slug when "
                "is_in_catalog=False)"
            )
    return drift


def _check_stop_reason(response: dict[str, Any]) -> list[str]:
    stop_reason = response.get("stop_reason")
    if stop_reason is None:
        return []
    if stop_reason in _KNOWN_STOP_REASONS:
        return []
    return [
        f"stop_reason_outside_known_set:got={stop_reason!r} "
        f"known={sorted(_KNOWN_STOP_REASONS)}"
    ]


def _check_effort(response: dict[str, Any]) -> list[str]:
    effort = response.get("effort")
    if not isinstance(effort, str):
        return []  # top-level shape check already reports wrong-type
    if effort in _KNOWN_EFFORTS:
        return []
    return [
        f"effort_outside_known_set:got={effort!r} "
        f"known={sorted(_KNOWN_EFFORTS)}"
    ]


_RICH_CONTENT_FIELDS = ("category", "install_method", "risk_cost")


def _check_rich_content_fields(recommendations: list[Any]) -> list[str]:
    """Each recommendation should have category / install_method /
    risk_cost keys present — explicit null acceptable, key absence
    is drift. See the JSON_OUTPUT_ENVELOPE rules in prompt.py.
    """
    drift: list[str] = []
    for idx, rec in enumerate(recommendations):
        if not isinstance(rec, dict):
            continue  # rank check already reported
        for field in _RICH_CONTENT_FIELDS:
            if field not in rec:
                drift.append(f"rich_content_missing:{field}:index={idx}")
    return drift
