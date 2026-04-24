"""Pydantic models for POST /recommend.

Operational-first per DECISIONS [2026-04-21 18:00]:

- `memory_available` is a first-class response field so an operator
  reading the 48h shakedown log can distinguish a healthy call
  from a memory-outage call without re-running the request.
- `model` and `effort` are echoed back so the operator sees
  exactly what was used (guards against the "floating alias
  quietly changed under us" failure mode). `effort` replaced
  `temperature` after Opus 4.7 deprecated the latter — see
  DECISIONS [2026-04-22 15:45].
- `latency_ms` is a breakdown, not just total, so slow calls can
  be attributed to memory vs. model vs. parse without
  instrumenting the client.
- `token_usage` is surfaced per response so cost-per-day is
  derivable from response logs by Day 4 evening.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]


class RecommendRequest(BaseModel):
    """Incoming recommendation request.

    `task` is the only required field. `cwd`, `task_hint`, and
    `active_tools` let the caller narrow context; all three feed
    the user-message context block in the Opus call.
    """

    task: str = Field(..., min_length=1, description="Natural-language task description.")
    cwd: Optional[str] = Field(None, description="Caller's working directory.")
    task_hint: Optional[str] = Field(
        None,
        description=(
            "Optional caller-provided category hint "
            "(e.g. 'data-analysis', 'content-drafting')."
        ),
    )
    active_tools: Optional[list[str]] = Field(
        None,
        description=(
            "Tool slugs the caller already has loaded; lets Opus "
            "prefer recommendations that leverage what's already active."
        ),
    )
    session_id: Optional[str] = Field(
        None,
        description=(
            "Caller-provided session identifier for telemetry "
            "correlation (Fix Day 4 Task 6 — session_id propagation). "
            "MCP-originated calls send the shim-lifetime UUID4 from "
            "`adapters/claude_code/session.SHIM_SESSION_ID`; non-MCP "
            "callers may omit. The value flows into the `recommended` "
            "ToolUsageEvent rows emitted for each in-catalog "
            "recommendation so the scanner + /health can aggregate by "
            "session."
        ),
    )


class ToolRecommendation(BaseModel):
    """One ranked tool recommendation."""

    rank: int = Field(..., ge=1, description="1-indexed rank in the result list.")
    tool_slug: Optional[str] = Field(
        None,
        description=(
            "Matching catalog slug when `is_in_catalog=True`; "
            "null for discovery recommendations."
        ),
    )
    tool_name: str = Field(..., description="Display name for the recommended tool.")
    rationale: str = Field(..., description="Why Opus chose this tool.")
    confidence: Confidence = Field(
        ..., description="Opus's confidence in this recommendation."
    )
    is_in_catalog: bool = Field(
        ...,
        description=(
            "True when the recommended tool matches a catalog entry. "
            "False signals a discovery case — caller is expected to "
            "route via `POST /requests` (N7) if a pending request "
            "should be created. N6 itself does not route."
        ),
    )
    category: Optional[str] = Field(
        None,
        description=(
            "Free-text semantic domain for the tool "
            "(e.g. 'search', 'data-processing', 'web'). Copied from "
            "the catalog entry when is_in_catalog=True; inferred by "
            "Opus when False. Null signals Opus had no confident "
            "category — distinct from the key being absent, which is "
            "Tier 1 drift."
        ),
    )
    install_method: Optional[str] = Field(
        None,
        description=(
            "Normalized install method (e.g. 'apt', 'pip-user', "
            "'npx-mcp', 'npm-global', 'binary'). Enables the in-chat "
            "surface to render 'how Concierge would install this' "
            "without the caller re-deriving it. Null when unknown."
        ),
    )
    risk_cost: Optional[str] = Field(
        None,
        description=(
            "One-phrase summary of install weight, runtime cost, "
            "license concerns, or credential requirements "
            "(e.g. '~5MB, no deps', '$0.03/call via Anthropic'). "
            "Null when Opus has no material risk/cost signal."
        ),
    )


class LatencyBreakdown(BaseModel):
    """Latency decomposition per request.

    All values in milliseconds. `total` is wall-clock from service
    entry to response return; sub-phases sum close to but do not
    exactly equal `total` (overhead in orchestration, logging, and
    Pydantic serialization is not attributed).
    """

    total: int
    memory: int
    model: int
    parse: int


class TokenUsage(BaseModel):
    """Anthropic token accounting for one call.

    `input` and `output` map to Anthropic's `usage.input_tokens`
    and `usage.output_tokens`. `total` = input + output. Cache
    metrics (if the SDK returns them) are summed into `input` —
    the soak-gate cares about the aggregate cost, not the cache
    hit rate, which is a Day-4-or-later optimization concern.
    """

    input: int = 0
    output: int = 0
    total: int = 0


class RecommendResponse(BaseModel):
    """Outgoing recommendation response."""

    request_id: str = Field(..., description="Full UUID4 correlation id.")
    recommendations: list[ToolRecommendation]
    memory_available: bool = Field(
        ...,
        description=(
            "False when memory lookup raised MemoryUnavailableError "
            "during this request. Distinct from empty-memory (True, "
            "memory_hit_count=0)."
        ),
    )
    memory_hit_count: int = Field(..., ge=0)
    model: str = Field(..., description="Anthropic model id that served this call.")
    effort: str = Field(
        ...,
        description=(
            "Opus 4.7 `output_config.effort` value used for this call — "
            "one of 'low', 'medium', 'high', 'xhigh', 'max'. Replaced "
            "`temperature` in the response shape after the Opus 4.7 "
            "temperature deprecation (DECISIONS [2026-04-22 15:45])."
        ),
    )
    latency_ms: LatencyBreakdown
    token_usage: TokenUsage
    reasoning: Optional[str] = Field(
        None,
        description="Opus's top-level rationale across the ranked list.",
    )
    stop_reason: Optional[str] = Field(
        None,
        description=(
            "Anthropic stop_reason (`end_turn`, `max_tokens`, etc.). "
            "Promoted to INFO log per the operational-first pivot so "
            "truncation during soak is visible in the primary log "
            "stream, not buried in DEBUG."
        ),
    )
    side_observations: Optional[list[str]] = Field(
        None,
        description=(
            "Fix Day 4 Task 3 — narration-as-push pattern 3. Optional "
            "array of at most two short observations Opus surfaces "
            "alongside the ranked list. Trigger categories per Fork C: "
            "(a) retired-tool overlap with the task, (b) idle loaded-"
            "on-boot tool whose category matches the task's domain. "
            "The agent caller surfaces these in its narration to the "
            "operator. Null when absent; `[]` when Opus produced an "
            "empty list. The renderer collapses an empty/absent list "
            "to a no-op — no `### Observations` section rendered."
        ),
    )
