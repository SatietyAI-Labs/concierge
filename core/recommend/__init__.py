"""Recommendation engine (N6) — `POST /recommend` service core.

Composes prompt-fragments (X3/X4/X6/X7-A) with a Concierge
adapter-context preamble + task + catalog + memory into an Opus
4.7 system prompt, calls Anthropic with pinned model + effort,
parses the ranked JSON response, and returns a structured result.

Architecture:

- `schemas.py` — Pydantic request/response models
- `prompt.py` — `compose_recommendation_prompt(...)` (deterministic)
  + `CONCIERGE_ADAPTER_PREAMBLE` + `JSON_OUTPUT_ENVELOPE`
- `parse.py` — `parse_recommendation_response(...)` + exceptions
- `client.py` — `AnthropicRecommender` thin wrapper (model/effort
  pinned, token extraction)
- `counters.py` — in-process request + token counters for the 48h
  operational shakedown; summary log at shutdown
- `service.py` — `RecommendationService` orchestrator (memory →
  prompt → Anthropic → parse → log → return)

Governing decisions:

- DECISIONS [2026-04-21 05:50] — prompt-fragment EXTRACT pattern
- DECISIONS [2026-04-21 18:00] — operational-first pivot; memory
  graceful degradation is load-bearing (correction note
  2026-04-22 15:45 — temperature-pinning mechanism replaced with
  effort-pinning on Opus 4.7)
- DECISIONS [2026-04-22 07:26] — adapter-context preamble strategy
  (c); preamble lives in `core/recommend/prompt.py` per the
  `core/prompts/` = verbatim-only invariant
- DECISIONS [2026-04-22 15:45] — Opus 4.7 temperature deprecation
  fix: remove `temperature`, use `output_config.effort="xhigh"`
"""

from core.recommend.schemas import (
    LatencyBreakdown,
    RecommendRequest,
    RecommendResponse,
    TokenUsage,
    ToolRecommendation,
)

__all__ = [
    "LatencyBreakdown",
    "RecommendRequest",
    "RecommendResponse",
    "TokenUsage",
    "ToolRecommendation",
]
