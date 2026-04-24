"""Recommendation orchestrator for POST /recommend.

Flow per request:

  1. Assign a UUID4 request_id (full UUID in response, 12-char
     prefix in logs).
  2. Query memory with the task as the search term. Catch
     `MemoryUnavailableError` narrowly → set `memory_available=False`,
     log WARNING with the outage reason, pass `memory_hits=None` to
     the prompt composer so the "(memory unavailable)" sentinel
     renders.
  3. Fetch the catalog snapshot from SQLite (all tools with their
     state annotation; Opus reasons across the full picture per
     the operational-first framing).
  4. Compose the system + user prompts via
     `compose_recommendation_prompt`.
  5. Call Anthropic (`AnthropicRecommender.call(...)`).
  6. Parse the response content
     (`parse_recommendation_response(...)`).
  7. Emit INFO (per-request summary, stop_reason included) + DEBUG
     (full prompt hash/body, full response hash/body, parsed recs)
     + WARNING (memory outage) + ERROR (parse failure) logs
     deterministically.
  8. Bump counters; return `RecommendResponse`.

Logging discipline is load-bearing per DECISIONS [2026-04-21 18:00]
— an operator reading the 48h shakedown log must be able to
distinguish healthy calls from memory-outage calls from parse
failures without re-running the call.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from core.memory import MemoryClient, MemoryHit, MemoryUnavailableError
from core.recommend.client import AnthropicClientError, AnthropicRecommender
from core.recommend.counters import RecommendCounters, get_counters
from core.recommend.parse import (
    RecommendationParseError,
    parse_recommendation_response,
)
from core.recommend.prompt import (
    CatalogToolView,
    compose_recommendation_prompt,
)
from core.recommend.schemas import (
    LatencyBreakdown,
    RecommendRequest,
    RecommendResponse,
    TokenUsage,
)
from core.recommend.validator import validate_response_shape
from core.telemetry import UsageEventSink, noop_sink


logger = logging.getLogger(__name__)


# Type alias for the catalog-fetch dependency; service is indifferent
# to whether catalog comes from SQLAlchemy, a cache, or a fixture.
CatalogFetcher = Callable[[], Iterable[CatalogToolView]]


def _short_id(request_id: str) -> str:
    return request_id[:12]


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


@dataclass
class RecommendationService:
    """Orchestrator — constructed with its three dependencies so
    tests can inject mocks without patching module globals.

    - `memory` — a `MemoryClient` instance (or a stand-in with the
      same `.search(...)` contract)
    - `anthropic` — an `AnthropicRecommender` (or stand-in with the
      same `.call(system, user)` contract)
    - `fetch_catalog` — a callable returning an iterable of
      `CatalogToolView`; abstracts the DB layer
    """

    memory: MemoryClient
    anthropic: AnthropicRecommender
    fetch_catalog: CatalogFetcher
    memory_search_limit: int = 5
    counters: RecommendCounters = None  # type: ignore[assignment]
    # Usage-event sink (§D telemetry). Defaults to noop so unit tests
    # that don't care about telemetry stay clean; production wiring
    # in `core/api/recommend.py` injects a DB-backed sink via
    # `core.telemetry.make_db_sink(db)`. Per Fix Day 3 Fork 2,
    # session_id is uniformly None until Fix Day 4 lights all three
    # emit sites with real session propagation.
    emit_usage: UsageEventSink = noop_sink

    def __post_init__(self) -> None:
        if self.counters is None:
            self.counters = get_counters()

    # ---- Orchestration ------------------------------------------------

    def recommend(self, req: RecommendRequest) -> RecommendResponse:
        request_id = str(uuid.uuid4())
        short = _short_id(request_id)
        start = time.monotonic()

        # 1. Memory lookup (graceful-degradation surface)
        memory_hits, memory_available, memory_ms = self._lookup_memory(
            req.task, request_id=request_id, short=short
        )

        # 1b. Operator identity — Fix Day 3 Fork 4. Same graceful-
        # degradation posture as memory_hits: on outage we pass None
        # (block collapses); on healthy empty we pass "" (also
        # collapses); on populated we inject between preamble and X3.
        identity: Optional[str] = None
        try:
            identity = self.memory.identity_get()
        except MemoryUnavailableError as exc:
            logger.warning(
                "recommend.identity_unavailable request_id=%s reason=%s: %s "
                "— serving without identity block",
                short, type(exc).__name__, exc,
            )

        # 2. Catalog snapshot
        catalog = list(self.fetch_catalog())

        # 3. Prompt composition
        composed = compose_recommendation_prompt(
            task=req.task,
            catalog=catalog,
            memory_hits=memory_hits,
            cwd=req.cwd,
            task_hint=req.task_hint,
            active_tools=req.active_tools,
            identity=identity,
        )
        system_hash = _hash(composed.system)
        user_hash = _hash(composed.user)
        logger.debug(
            "recommend.prompt request_id=%s system_hash=%s system_len=%d "
            "user_hash=%s user_len=%d",
            short,
            system_hash,
            len(composed.system),
            user_hash,
            len(composed.user),
        )
        logger.debug(
            "recommend.prompt_body request_id=%s system=<<<\n%s\n>>> user=<<<\n%s\n>>>",
            short,
            composed.system,
            composed.user,
        )

        # 4. Anthropic call
        try:
            call = self.anthropic.call(system=composed.system, user=composed.user)
        except AnthropicClientError as exc:
            logger.error(
                "recommend.anthropic_failed request_id=%s error=%s: %s",
                short,
                type(exc).__name__,
                exc,
            )
            raise

        content_hash = _hash(call.content)
        logger.debug(
            "recommend.response request_id=%s content_hash=%s content_len=%d "
            "tokens_in=%d tokens_out=%d latency_ms_model=%d",
            short,
            content_hash,
            len(call.content),
            call.tokens_in,
            call.tokens_out,
            call.latency_ms,
        )
        logger.debug(
            "recommend.response_body request_id=%s content=<<<\n%s\n>>>",
            short,
            call.content,
        )

        # 5. Parse
        parse_start = time.monotonic()
        try:
            reasoning, recommendations, side_observations = parse_recommendation_response(
                call.content
            )
        except RecommendationParseError as exc:
            self.counters.record_parse_failed()
            logger.error(
                "recommend.parse_failed request_id=%s raw_len=%d error=%s: %s",
                short,
                len(call.content),
                type(exc).__name__,
                exc,
            )
            raise
        parse_ms = int((time.monotonic() - parse_start) * 1000)

        logger.debug(
            "recommend.parsed request_id=%s rec_count=%d reasoning_len=%d",
            short,
            len(recommendations),
            len(reasoning),
        )

        # 6a. §D usage telemetry: emit one `recommended` event per
        # in-catalog recommendation so the §C7 promotion/demotion
        # scanner has per-tool recency data. Discovery recs
        # (tool_slug is None) are skipped — there's no catalog row
        # yet to attach the event to. Any emit failure is logged by
        # the sink and swallowed so telemetry problems never fail
        # the recommend call.
        for rank, rec in enumerate(recommendations, start=1):
            if rec.tool_slug is None:
                continue
            try:
                self.emit_usage(
                    rec.tool_slug,
                    "recommended",
                    {
                        "rank": rank,
                        "request_id": short,
                        "task_hint": req.task_hint,
                    },
                    req.session_id,
                )
            except Exception as exc:
                logger.warning(
                    "recommend.telemetry_emit_failed request_id=%s "
                    "tool_slug=%s rank=%d error=%s: %s",
                    short, rec.tool_slug, rank, type(exc).__name__, exc,
                )

        # 6. Counters + INFO summary
        self.counters.record_request(
            tokens_in=call.tokens_in, tokens_out=call.tokens_out
        )
        total_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            'recommend.request request_id=%s task="%s" memory_available=%s '
            "memory_hit_count=%d model=%s effort=%s stop_reason=%s "
            "latency_ms_total=%d latency_ms_memory=%d latency_ms_model=%d "
            "latency_ms_parse=%d tokens_in=%d tokens_out=%d rec_count=%d",
            short,
            req.task[:80].replace('"', "'"),
            memory_available,
            len(memory_hits) if memory_hits is not None else 0,
            call.model_echo,
            self.anthropic.effort,
            call.stop_reason,
            total_ms,
            memory_ms,
            call.latency_ms,
            parse_ms,
            call.tokens_in,
            call.tokens_out,
            len(recommendations),
        )

        # 7. Response
        response = RecommendResponse(
            request_id=request_id,
            recommendations=recommendations,
            memory_available=memory_available,
            memory_hit_count=len(memory_hits) if memory_hits is not None else 0,
            model=call.model_echo,
            effort=self.anthropic.effort,
            latency_ms=LatencyBreakdown(
                total=total_ms,
                memory=memory_ms,
                model=call.latency_ms,
                parse=parse_ms,
            ),
            token_usage=TokenUsage(
                input=call.tokens_in,
                output=call.tokens_out,
                total=call.tokens_in + call.tokens_out,
            ),
            reasoning=reasoning,
            stop_reason=call.stop_reason,
            side_observations=side_observations,
        )

        # 8. Tier 1 drift detection — fixture-spec structural check
        # against the real response. Never raises; logs WARNING per
        # drift message and bumps the fixture_drift_count counter
        # once per drifted call (Tier 2 surface in /health). The
        # user's call still returns the response regardless.
        drift_messages = validate_response_shape(
            response.model_dump(), request_id=request_id
        )
        if drift_messages:
            self.counters.record_fixture_drift()
            drift_summary = "; ".join(drift_messages)
            logger.warning(
                "recommend.fixture_drift_detected request_id=%s "
                'drift_count=%d drift_summary="%s"',
                short,
                len(drift_messages),
                drift_summary,
            )

        return response

    # ---- Helpers ------------------------------------------------------

    def _lookup_memory(
        self, task: str, *, request_id: str, short: str
    ) -> tuple[Optional[list[MemoryHit]], bool, int]:
        """Try memory.search(task). Returns:

        - (hits_list, True, elapsed_ms) on success (hits_list may be [])
        - (None, False, elapsed_ms) on MemoryUnavailableError

        `None` for the hits is the adversarial sentinel that the
        prompt composer maps to "(memory unavailable)" — distinct
        from an empty list (healthy + no matches).
        """
        start = time.monotonic()
        try:
            hits = self.memory.search(task, limit=self.memory_search_limit)
            elapsed = int((time.monotonic() - start) * 1000)
            return hits, True, elapsed
        except MemoryUnavailableError as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            self.counters.record_memory_unavailable()
            logger.warning(
                "recommend.memory_unavailable request_id=%s reason=%s: %s "
                "— serving with (memory unavailable) sentinel",
                short,
                type(exc).__name__,
                exc,
            )
            return None, False, elapsed
