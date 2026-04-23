"""Tests for core.recommend.counters — in-process counters for the
48h operational shakedown."""
from __future__ import annotations

import logging

from core.recommend.counters import (
    RecommendCounters,
    get_counters,
    log_shutdown_summary,
    reset_counters_for_tests,
)


class TestRecommendCounters:
    def test_singleton_across_calls(self):
        reset_counters_for_tests()
        a = get_counters()
        b = get_counters()
        assert a is b

    def test_record_request_increments_aggregates(self):
        reset_counters_for_tests()
        c = get_counters()
        c.record_request(tokens_in=100, tokens_out=20)
        c.record_request(tokens_in=250, tokens_out=30)
        snap = c.snapshot()
        assert snap["requests"] == 2
        assert snap["tokens_in"] == 350
        assert snap["tokens_out"] == 50

    def test_failure_counters_independent(self):
        reset_counters_for_tests()
        c = get_counters()
        c.record_memory_unavailable()
        c.record_memory_unavailable()
        c.record_parse_failed()
        snap = c.snapshot()
        assert snap["memory_unavailable"] == 2
        assert snap["parse_failed"] == 1
        # Request count should NOT auto-bump on failures — failures
        # are tagged separately from successful request tallies.
        assert snap["requests"] == 0

    def test_fixture_drift_counter_is_independent(self):
        """Tier-2 counter (N14) — tracks how many recommend calls
        had their response shape drift from the fixture specification.
        Bumped by service.recommend() when validate_response_shape
        returns non-empty drift messages. Does not auto-bump request
        count; a drifted call still served successfully from the
        user's point of view.
        """
        reset_counters_for_tests()
        c = get_counters()
        c.record_fixture_drift()
        c.record_fixture_drift()
        c.record_fixture_drift()
        snap = c.snapshot()
        assert snap["fixture_drift"] == 3
        assert snap["requests"] == 0
        assert snap["memory_unavailable"] == 0
        assert snap["parse_failed"] == 0

    def test_snapshot_is_a_copy(self):
        reset_counters_for_tests()
        c = get_counters()
        c.record_request(tokens_in=10, tokens_out=5)
        snap = c.snapshot()
        snap["requests"] = 999
        # Mutating the snapshot must not affect the counter.
        assert c.snapshot()["requests"] == 1

    def test_reset_clears_singleton(self):
        reset_counters_for_tests()
        c1 = get_counters()
        c1.record_request(tokens_in=1, tokens_out=1)
        reset_counters_for_tests()
        c2 = get_counters()
        # A fresh singleton with zeroed state.
        assert c2.snapshot()["requests"] == 0
        # Old reference still works but is disconnected.
        assert c1 is not c2


class TestShutdownSummaryLog:
    def test_shutdown_summary_emits_info_line(self, caplog):
        reset_counters_for_tests()
        c = get_counters()
        c.record_request(tokens_in=123, tokens_out=45)
        c.record_memory_unavailable()
        c.record_parse_failed()
        c.record_parse_failed()

        with caplog.at_level(logging.INFO, logger="core.recommend.counters"):
            log_shutdown_summary()

        matching = [
            r for r in caplog.records if "recommend.session_summary" in r.getMessage()
        ]
        assert len(matching) == 1
        msg = matching[0].getMessage()
        assert "requests=1" in msg
        assert "tokens_in=123" in msg
        assert "tokens_out=45" in msg
        assert "memory_unavailable=1" in msg
        assert "parse_failed=2" in msg
        # fixture_drift was not bumped in this setup → 0 in the line.
        assert "fixture_drift=0" in msg

    def test_shutdown_summary_with_zero_activity(self, caplog):
        reset_counters_for_tests()
        with caplog.at_level(logging.INFO, logger="core.recommend.counters"):
            log_shutdown_summary()
        msg = caplog.records[-1].getMessage()
        assert "requests=0" in msg
        assert "tokens_in=0" in msg
