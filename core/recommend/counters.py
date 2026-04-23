"""In-process counters for the 48h operational shakedown.

Per DECISIONS [2026-04-21 18:00] and the N6 framing: request-count
+ token-usage logging from the start so cost-per-day is observable
by Day 4 evening. Counters live in-process (single process for
hackathon scope); a shutdown-time summary log emits the aggregate.

The GIL is sufficient thread-safety for small integer bumps; if a
future async path or multi-worker deployment is introduced, this
becomes an `asyncio.Lock` or is pushed to the database.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class RecommendCounters:
    """Running counters over the lifetime of one Concierge process.

    Counters are cumulative; reset only when the process restarts.
    Individual log lines per request carry deltas (see
    `service.py`); this struct carries aggregates.
    """

    request_count: int = 0
    tokens_in_total: int = 0
    tokens_out_total: int = 0
    memory_unavailable_count: int = 0
    parse_failed_count: int = 0
    # Fixture-drift counter (Tier 2 / N14). Bumped once per call
    # whose response shape drifts from the fixture specification
    # enforced by `core.recommend.validator.validate_response_shape`.
    # Surfaced in /health so the operator sees the magnitude of
    # API-shape evolution over the 48h shakedown window.
    fixture_drift_count: int = 0

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_request(self, *, tokens_in: int, tokens_out: int) -> None:
        with self._lock:
            self.request_count += 1
            self.tokens_in_total += tokens_in
            self.tokens_out_total += tokens_out

    def record_memory_unavailable(self) -> None:
        with self._lock:
            self.memory_unavailable_count += 1

    def record_parse_failed(self) -> None:
        with self._lock:
            self.parse_failed_count += 1

    def record_fixture_drift(self) -> None:
        with self._lock:
            self.fixture_drift_count += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "requests": self.request_count,
                "tokens_in": self.tokens_in_total,
                "tokens_out": self.tokens_out_total,
                "memory_unavailable": self.memory_unavailable_count,
                "parse_failed": self.parse_failed_count,
                "fixture_drift": self.fixture_drift_count,
            }


_counters: RecommendCounters | None = None
_module_lock = threading.Lock()


def get_counters() -> RecommendCounters:
    """Module-level singleton. Safe for concurrent initialization."""
    global _counters
    if _counters is None:
        with _module_lock:
            if _counters is None:
                _counters = RecommendCounters()
    return _counters


def reset_counters_for_tests() -> None:
    """Test helper — reset the singleton between tests so counter
    assertions don't leak across tests. Do not call from app code.
    """
    global _counters
    with _module_lock:
        _counters = RecommendCounters()


def log_shutdown_summary() -> None:
    """Emit a single INFO log line summarizing the session's
    recommendation activity. Called from FastAPI's lifespan
    shutdown hook; a log miss here is non-fatal.
    """
    snap = get_counters().snapshot()
    logger.info(
        "recommend.session_summary requests=%d tokens_in=%d tokens_out=%d "
        "memory_unavailable=%d parse_failed=%d fixture_drift=%d",
        snap["requests"],
        snap["tokens_in"],
        snap["tokens_out"],
        snap["memory_unavailable"],
        snap["parse_failed"],
        snap["fixture_drift"],
    )
