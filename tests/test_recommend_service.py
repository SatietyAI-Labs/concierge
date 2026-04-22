"""Tests for core.recommend.service — orchestration + adversarial
memory-outage + reasoning-failure.

Per the N6 framing, the memory-unavailable test is adversarial:
it injects the failure **inside** the N6 flow, not in isolation,
and asserts that:

  (a) the response still returns 200-shape with memory_available=False
  (b) the prompt composed contains the "(memory unavailable)" sentinel
      (verified by inspecting the captured Anthropic call)
  (c) caplog contains a WARNING marker distinguishable from the
      INFO request line
  (d) the recommendations list is non-empty (the fallback is
      meaningfully good, not an empty shell)
  (e) the INFO request line shows memory_available=False so a log
      reader visually distinguishes it from a healthy call
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import pytest

from core.memory import MemoryHit, MemoryUnavailableError
from core.recommend.client import AnthropicCall, AnthropicClientError
from core.recommend.counters import RecommendCounters
from core.recommend.parse import RecommendationParseError
from core.recommend.prompt import CatalogToolView
from core.recommend.schemas import RecommendRequest
from core.recommend.service import RecommendationService


# ---- Test doubles --------------------------------------------------------


@dataclass
class FakeMemory:
    """Stand-in for `MemoryClient` — configurable hits or forced outage."""

    hits: list[MemoryHit] = field(default_factory=list)
    raise_on_search: bool = False
    error_msg: str = "chromadb init failed: disk is on fire"
    search_calls: int = 0

    def search(self, query: str, *, limit: int = 5):
        self.search_calls += 1
        if self.raise_on_search:
            raise MemoryUnavailableError(self.error_msg)
        return list(self.hits)


@dataclass
class FakeAnthropic:
    """Stand-in for `AnthropicRecommender` — captures each call and
    returns a preset payload. Mirrors the fields the service reads.
    """

    content: str = ""
    stop_reason: str = "end_turn"
    tokens_in: int = 100
    tokens_out: int = 50
    model_echo: str = "claude-opus-4-7"
    effort: str = "xhigh"  # service reads this for response echo (replaced temperature on Opus 4.7)
    raise_exc: Optional[Exception] = None
    last_system: Optional[str] = None
    last_user: Optional[str] = None
    call_count: int = 0

    def call(self, *, system: str, user: str) -> AnthropicCall:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        if self.raise_exc is not None:
            raise self.raise_exc
        return AnthropicCall(
            content=self.content,
            stop_reason=self.stop_reason,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            model_echo=self.model_echo,
            latency_ms=7,
        )


def _sample_catalog() -> list[CatalogToolView]:
    return [
        CatalogToolView(
            slug="csvstat",
            name="csvstat",
            description="Summary stats for CSV",
            category="data",
            pack_slug="csvkit",
            is_in_manifest=True,
            is_active=True,
        ),
        CatalogToolView(
            slug="pandas",
            name="pandas",
            description="Data analysis library",
            category="data",
            pack_slug=None,
            is_in_manifest=True,
            is_active=False,  # dormant
        ),
    ]


def _good_response_json(*, rec_count: int = 2) -> str:
    recs = []
    for i in range(rec_count):
        recs.append(
            {
                "rank": i + 1,
                "tool_slug": "csvstat" if i == 0 else None,
                "tool_name": "csvstat" if i == 0 else "discovery-suggestion",
                "rationale": "Lightweight CLI for CSV tasks.",
                "confidence": "high" if i == 0 else "medium",
                "is_in_catalog": i == 0,
            }
        )
    return json.dumps({"reasoning": "Prefer lightweight tools.", "recommendations": recs})


def _service(
    memory: FakeMemory, anthropic: FakeAnthropic, counters: RecommendCounters | None = None
) -> RecommendationService:
    return RecommendationService(
        memory=memory,  # type: ignore[arg-type]
        anthropic=anthropic,  # type: ignore[arg-type]
        fetch_catalog=_sample_catalog,
        memory_search_limit=5,
        counters=counters if counters is not None else RecommendCounters(),
    )


# ---- Happy path ----------------------------------------------------------


class TestHappyPath:
    def test_basic_call_returns_structured_response(self, caplog):
        memory = FakeMemory(
            hits=[
                MemoryHit(
                    id="mem_1",
                    text="user prefers lightweight CLIs",
                    similarity=0.88,
                    tags=("tool-selection",),
                    importance="normal",
                    source="test",
                    created_at="2026-04-20",
                )
            ]
        )
        anthropic = FakeAnthropic(content=_good_response_json(rec_count=2))
        svc = _service(memory, anthropic)

        with caplog.at_level(logging.DEBUG, logger="core.recommend.service"):
            resp = svc.recommend(RecommendRequest(task="analyze this CSV"))

        assert resp.memory_available is True
        assert resp.memory_hit_count == 1
        assert resp.model == "claude-opus-4-7"
        assert resp.effort == "xhigh"
        assert resp.stop_reason == "end_turn"
        assert len(resp.recommendations) == 2
        assert resp.token_usage.input == 100
        assert resp.token_usage.output == 50
        assert resp.token_usage.total == 150

    def test_request_id_is_full_uuid(self):
        svc = _service(FakeMemory(), FakeAnthropic(content=_good_response_json()))
        resp = svc.recommend(RecommendRequest(task="t"))
        # 8-4-4-4-12 UUID with hyphens.
        parts = resp.request_id.split("-")
        assert len(parts) == 5
        assert [len(p) for p in parts] == [8, 4, 4, 4, 12]

    def test_log_shows_12_char_request_id_prefix(self, caplog):
        svc = _service(FakeMemory(), FakeAnthropic(content=_good_response_json()))
        with caplog.at_level(logging.INFO, logger="core.recommend.service"):
            resp = svc.recommend(RecommendRequest(task="t"))
        prefix = resp.request_id[:12]
        info_lines = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        assert any(f"request_id={prefix}" in m for m in info_lines)
        # And the FULL uuid should NOT leak into the INFO line.
        assert not any(resp.request_id in m for m in info_lines)

    def test_unique_request_ids_across_calls(self):
        svc = _service(FakeMemory(), FakeAnthropic(content=_good_response_json()))
        r1 = svc.recommend(RecommendRequest(task="a"))
        r2 = svc.recommend(RecommendRequest(task="b"))
        assert r1.request_id != r2.request_id

    def test_counters_bump_on_success(self):
        counters = RecommendCounters()
        svc = _service(FakeMemory(), FakeAnthropic(content=_good_response_json()), counters)
        svc.recommend(RecommendRequest(task="t"))
        snap = counters.snapshot()
        assert snap["requests"] == 1
        assert snap["tokens_in"] == 100
        assert snap["tokens_out"] == 50
        assert snap["memory_unavailable"] == 0
        assert snap["parse_failed"] == 0

    def test_stop_reason_appears_at_info_level(self, caplog):
        """Per the reordering discussion, stop_reason is promoted to
        INFO so truncation during soak is visible without DEBUG."""
        anthropic = FakeAnthropic(
            content=_good_response_json(), stop_reason="max_tokens"
        )
        svc = _service(FakeMemory(), anthropic)
        with caplog.at_level(logging.INFO, logger="core.recommend.service"):
            svc.recommend(RecommendRequest(task="t"))
        info_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        assert any("stop_reason=max_tokens" in m for m in info_msgs)

    def test_prompt_contains_no_memory_unavailable_sentinel_on_happy(self):
        anthropic = FakeAnthropic(content=_good_response_json())
        svc = _service(FakeMemory(hits=[]), anthropic)
        svc.recommend(RecommendRequest(task="t"))
        assert "(no relevant memory)" in anthropic.last_user
        assert "(memory unavailable)" not in anthropic.last_user


# ---- Adversarial: memory unavailable ------------------------------------


class TestMemoryUnavailableAdversarial:
    """Injects MemoryUnavailableError mid-flow and asserts the full
    fallback surface. This is the load-bearing operational-first
    test per DECISIONS [2026-04-21 18:00].
    """

    def test_memory_outage_returns_meaningfully_good_response(self, caplog):
        memory = FakeMemory(raise_on_search=True, error_msg="disk is on fire")
        anthropic = FakeAnthropic(content=_good_response_json(rec_count=2))
        counters = RecommendCounters()
        svc = _service(memory, anthropic, counters)

        with caplog.at_level(logging.DEBUG, logger="core.recommend.service"):
            resp = svc.recommend(RecommendRequest(task="analyze this CSV"))

        # (a) response is well-shaped
        assert resp.memory_available is False
        assert resp.memory_hit_count == 0
        assert len(resp.recommendations) == 2  # fallback is not an empty shell
        assert resp.model == "claude-opus-4-7"

        # (b) prompt rendered the outage sentinel
        assert anthropic.last_user is not None
        assert "(memory unavailable)" in anthropic.last_user
        assert "(no relevant memory)" not in anthropic.last_user

        # (c) exactly one WARNING log line, distinguishable marker
        warn_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        matching = [
            r
            for r in warn_records
            if "recommend.memory_unavailable" in r.getMessage()
        ]
        assert len(matching) == 1
        assert "MemoryUnavailableError" in matching[0].getMessage()
        assert "disk is on fire" in matching[0].getMessage()

        # (d) INFO request summary shows memory_available=False so a
        # log reader visually distinguishes this from a healthy call
        info_matches = [
            r for r in caplog.records if r.levelno == logging.INFO and
            "recommend.request" in r.getMessage()
        ]
        assert len(info_matches) == 1
        assert "memory_available=False" in info_matches[0].getMessage()

        # Counters: memory_unavailable bumped; request count also
        # bumped because the request DID serve successfully (it was
        # served WITHOUT memory, not skipped). parse_failed untouched.
        snap = counters.snapshot()
        assert snap["memory_unavailable"] == 1
        assert snap["requests"] == 1
        assert snap["parse_failed"] == 0

    def test_memory_outage_does_not_raise(self):
        memory = FakeMemory(raise_on_search=True)
        anthropic = FakeAnthropic(content=_good_response_json())
        svc = _service(memory, anthropic)
        # Must not propagate — this is the graceful-degradation
        # contract.
        resp = svc.recommend(RecommendRequest(task="t"))
        assert resp.memory_available is False

    def test_warning_and_info_lines_are_distinguishable(self, caplog):
        """Log consumers (grep or a future JSON extractor) must be
        able to tell outage WARNING from normal INFO by level alone.
        """
        memory = FakeMemory(raise_on_search=True)
        anthropic = FakeAnthropic(content=_good_response_json())
        svc = _service(memory, anthropic)

        with caplog.at_level(logging.DEBUG, logger="core.recommend.service"):
            svc.recommend(RecommendRequest(task="t"))

        warns = [r for r in caplog.records if r.levelno == logging.WARNING]
        infos = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(warns) == 1
        assert len(infos) >= 1
        # Levels differ, logger names match (both from service.py).
        assert warns[0].name == "core.recommend.service"
        assert all(i.name == "core.recommend.service" for i in infos)


# ---- Reasoning failure (parse error) ------------------------------------


class TestReasoningFailure:
    def test_parse_failure_raises_with_error_log(self, caplog):
        memory = FakeMemory()
        anthropic = FakeAnthropic(content="this is not json at all")
        counters = RecommendCounters()
        svc = _service(memory, anthropic, counters)

        with caplog.at_level(logging.DEBUG, logger="core.recommend.service"):
            with pytest.raises(RecommendationParseError):
                svc.recommend(RecommendRequest(task="t"))

        err_records = [
            r
            for r in caplog.records
            if r.levelno == logging.ERROR and "recommend.parse_failed" in r.getMessage()
        ]
        assert len(err_records) == 1
        # Parse-failure counter bumped; request count NOT bumped
        # (request did not serve successfully).
        snap = counters.snapshot()
        assert snap["parse_failed"] == 1
        assert snap["requests"] == 0
        assert snap["memory_unavailable"] == 0

    def test_parse_failure_is_distinct_from_memory_outage(self, caplog):
        """A parse failure must NOT look the same as a memory outage:
        ERROR level + recommend.parse_failed logger message, not
        WARNING + recommend.memory_unavailable.
        """
        memory = FakeMemory()
        anthropic = FakeAnthropic(content="garbage")
        svc = _service(memory, anthropic)

        with caplog.at_level(logging.DEBUG, logger="core.recommend.service"):
            with pytest.raises(RecommendationParseError):
                svc.recommend(RecommendRequest(task="t"))

        warns = [r for r in caplog.records if r.levelno == logging.WARNING]
        errs = [r for r in caplog.records if r.levelno == logging.ERROR]
        # No WARNING — parse failure is NOT a memory concern.
        assert not any("memory_unavailable" in w.getMessage() for w in warns)
        # Exactly one ERROR with parse_failed marker.
        assert sum("parse_failed" in e.getMessage() for e in errs) == 1


# ---- Anthropic client failure (propagates) ------------------------------


class TestAnthropicClientFailure:
    def test_anthropic_error_propagates_with_error_log(self, caplog):
        memory = FakeMemory()
        anthropic = FakeAnthropic(
            raise_exc=AnthropicClientError("upstream 503")
        )
        counters = RecommendCounters()
        svc = _service(memory, anthropic, counters)

        with caplog.at_level(logging.ERROR, logger="core.recommend.service"):
            with pytest.raises(AnthropicClientError):
                svc.recommend(RecommendRequest(task="t"))

        errs = [
            r
            for r in caplog.records
            if r.levelno == logging.ERROR
            and "recommend.anthropic_failed" in r.getMessage()
        ]
        assert len(errs) == 1
        # Neither request-count nor parse-failed bumps; memory
        # lookup DID succeed (or was skipped by fake), so
        # memory_unavailable also untouched.
        snap = counters.snapshot()
        assert snap["requests"] == 0
        assert snap["parse_failed"] == 0


# ---- Temperature override surfaces in response --------------------------


class TestEffortEcho:
    def test_effort_echo_from_anthropic_client(self):
        """Response.effort echoes what the client was configured
        with — the operator sees exactly what was used, not what was
        requested in settings.

        Replaced `test_temperature_echo_from_anthropic_client` after
        Opus 4.7 deprecated temperature (DECISIONS [2026-04-22 15:45]).
        """
        memory = FakeMemory()
        anthropic = FakeAnthropic(content=_good_response_json(), effort="high")
        svc = _service(memory, anthropic)
        resp = svc.recommend(RecommendRequest(task="t"))
        assert resp.effort == "high"


# ---- Prompt context propagation -----------------------------------------


class TestContextPropagation:
    def test_cwd_and_task_hint_reach_prompt(self):
        memory = FakeMemory(hits=[])
        anthropic = FakeAnthropic(content=_good_response_json())
        svc = _service(memory, anthropic)
        svc.recommend(
            RecommendRequest(
                task="t", cwd="/home/lewie", task_hint="data-analysis"
            )
        )
        assert "/home/lewie" in anthropic.last_user
        assert "data-analysis" in anthropic.last_user

    def test_active_tools_reach_prompt(self):
        memory = FakeMemory(hits=[])
        anthropic = FakeAnthropic(content=_good_response_json())
        svc = _service(memory, anthropic)
        svc.recommend(
            RecommendRequest(task="t", active_tools=["pandas", "csvstat"])
        )
        assert "pandas" in anthropic.last_user
        assert "csvstat" in anthropic.last_user
