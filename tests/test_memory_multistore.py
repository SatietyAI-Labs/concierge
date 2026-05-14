"""Tests for Stage 1A item 2 — multi-store read on `core.memory`.

Structure mirrors `tests/test_memory.py`:

- **Fast tests:** constructor shape, Settings field plumbing,
  `MemoryHit.source_store` field, dedupe helper. No ChromaDB touch,
  no sentence-transformers load.

- **Integration tests** (`@pytest.mark.integration`): aggregation
  across multiple real tmp-dir ChromaDB stores, primary-write
  isolation, per-store graceful degradation, stats per-store
  reporting. Loads sentence-transformers on first run. Skip with
  `pytest -m "not integration"`.

Master plan §III.2 item 2 + DECISIONS [2026-05-14] item-2 entry —
see those docs for the open-decision matrix (Q1–Q5 → all Option A).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.memory import (
    MemoryClient,
    MemoryHit,
    MemoryUnavailableError,
    _dedupe_read_stores,
)


# ---- Fast tests ---------------------------------------------------------


class TestReadStoresConstructorShape:
    """Constructor accepts `read_stores: list[Path] | None`, stores
    a normalized list, and does NOT touch ChromaDB at construction
    time (parity with the prior single-store lazy-init contract).
    """

    def test_default_read_stores_is_empty_list(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "primary")
        assert client.read_stores == []

    def test_none_read_stores_normalizes_to_empty(self, tmp_path: Path):
        client = MemoryClient(
            memory_dir=tmp_path / "primary", read_stores=None
        )
        assert client.read_stores == []

    def test_read_stores_preserves_order(self, tmp_path: Path):
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        r3 = tmp_path / "r3"
        client = MemoryClient(
            memory_dir=tmp_path / "primary", read_stores=[r1, r2, r3]
        )
        assert client.read_stores == [r1, r2, r3]

    def test_read_stores_drops_primary_collision(self, tmp_path: Path):
        """A read store equal to primary would double-count on
        aggregation. Dedupe drops it; primary remains the only
        contributor for its path."""
        primary = tmp_path / "primary"
        other = tmp_path / "other"
        client = MemoryClient(
            memory_dir=primary, read_stores=[primary, other]
        )
        assert client.read_stores == [other]

    def test_read_stores_drops_duplicates(self, tmp_path: Path):
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        client = MemoryClient(
            memory_dir=tmp_path / "primary",
            read_stores=[r1, r2, r1, r2, r1],
        )
        assert client.read_stores == [r1, r2]

    def test_construction_does_not_create_read_store_dirs(self, tmp_path: Path):
        """Read-store directories are not created at construction —
        only on first successful lazy-init at query time. Parity with
        the existing `test_init_with_nonexistent_dir_does_not_raise`
        contract on primary."""
        r1 = tmp_path / "absent-r1"
        assert not r1.exists()
        MemoryClient(
            memory_dir=tmp_path / "primary", read_stores=[r1]
        )
        assert not r1.exists()


class TestDedupeReadStores:
    """Direct coverage for the module-level helper. Constructor
    delegates to this; broken helper would silently double-count
    hits in production."""

    def test_empty_list_returns_empty(self):
        assert _dedupe_read_stores(primary=Path("/a"), read_stores=[]) == []

    def test_no_collisions_passes_through(self):
        result = _dedupe_read_stores(
            primary=Path("/a"),
            read_stores=[Path("/b"), Path("/c"), Path("/d")],
        )
        assert result == [Path("/b"), Path("/c"), Path("/d")]

    def test_primary_collision_dropped(self):
        result = _dedupe_read_stores(
            primary=Path("/a"),
            read_stores=[Path("/a"), Path("/b")],
        )
        assert result == [Path("/b")]

    def test_consecutive_duplicates_dropped(self):
        result = _dedupe_read_stores(
            primary=Path("/a"),
            read_stores=[Path("/b"), Path("/b"), Path("/c")],
        )
        assert result == [Path("/b"), Path("/c")]

    def test_non_adjacent_duplicates_dropped(self):
        result = _dedupe_read_stores(
            primary=Path("/a"),
            read_stores=[Path("/b"), Path("/c"), Path("/b"), Path("/c")],
        )
        assert result == [Path("/b"), Path("/c")]


class TestMemoryHitSourceStore:
    """`MemoryHit.source_store: Path | None = None` is a new kwarg
    with a backward-compatible default. Frozen dataclass invariant
    is preserved.
    """

    def test_default_is_none(self):
        hit = MemoryHit(
            id="mem_x",
            text="t",
            similarity=0.5,
            tags=(),
            importance="normal",
            source="t",
            created_at="2026-05-14T00:00:00",
        )
        assert hit.source_store is None

    def test_set_to_path_round_trips(self):
        p = Path("/some/store")
        hit = MemoryHit(
            id="mem_x",
            text="t",
            similarity=0.5,
            tags=(),
            importance="normal",
            source="t",
            created_at="2026-05-14T00:00:00",
            source_store=p,
        )
        assert hit.source_store == p

    def test_remains_frozen(self):
        hit = MemoryHit(
            id="mem_x",
            text="t",
            similarity=0.5,
            tags=(),
            importance="normal",
            source="t",
            created_at="2026-05-14T00:00:00",
            source_store=Path("/x"),
        )
        with pytest.raises((AttributeError, Exception)):
            hit.source_store = Path("/y")  # type: ignore[misc]


class TestSettingsField:
    """`Settings.memory_read_stores: list[Path]` parses from JSON env
    var and runs each entry through `.expanduser()`."""

    def test_default_is_empty_list(self):
        from core.config import Settings

        s = Settings()
        assert s.memory_read_stores == []

    def test_direct_assignment_round_trips(self, tmp_path: Path):
        from core.config import Settings

        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        s = Settings(memory_read_stores=[r1, r2])
        assert s.memory_read_stores == [r1, r2]

    def test_tilde_expanded_on_validation(self):
        from core.config import Settings

        s = Settings(memory_read_stores=[Path("~/some-store")])
        assert s.memory_read_stores == [Path.home() / "some-store"]

    def test_json_env_var_parses(self, monkeypatch):
        """JSON list env var → list[Path] with tilde expansion. This is
        the Gate 4.5 operator-edit path; if it breaks, Gate 4.5
        configuration breaks."""
        from core.config import Settings

        monkeypatch.setenv(
            "CONCIERGE_MEMORY_READ_STORES",
            '["~/store-a", "~/store-b"]',
        )
        s = Settings()
        assert s.memory_read_stores == [
            Path.home() / "store-a",
            Path.home() / "store-b",
        ]


# ---- Integration tests --------------------------------------------------


@pytest.mark.integration
class TestFourReadStoreConfiguration:
    """End-to-end: primary + 4 distinct read stores; each pre-populated
    with a distinguishable entry. Mirrors the Gate 4.5 configuration
    shape (1 primary + 4 read stores) on temp-dir ChromaDB.
    """

    def _seed(self, path: Path, text: str) -> str:
        """Pre-populate `path` with a single memory by constructing a
        write-capable client pointed at it as its own primary. Returns
        the new memory id.
        """
        seed_client = MemoryClient(memory_dir=path)
        return seed_client.store(text, tags=["test-fixture"], source="seed")

    def test_search_aggregates_across_all_five_stores(self, tmp_path: Path):
        primary = tmp_path / "primary"
        r1 = tmp_path / "moltbot-v2"
        r2 = tmp_path / "agent-memory-content"
        r3 = tmp_path / "agent-memory-intel"
        r4 = tmp_path / "agent-memory-engagement"

        self._seed(primary, "primary store holds Concierge-written memories")
        self._seed(r1, "alfred unified store mentions LinkedIn campaign cadence")
        self._seed(r2, "scout content-prep store discusses copy editing rules")
        self._seed(r3, "radar intelligence store covers competitor analysis")
        self._seed(r4, "bridge engagement store tracks outreach DM patterns")

        client = MemoryClient(
            memory_dir=primary, read_stores=[r1, r2, r3, r4]
        )
        hits = client.search("memory entries from agent stores", limit=20)
        assert len(hits) == 5, f"expected 5 hits across stores, got {len(hits)}"

        # Each hit must carry its originating store as source_store.
        source_paths = {h.source_store for h in hits}
        assert source_paths == {primary, r1, r2, r3, r4}

        # Similarities are populated (semantic search path) and sorted desc.
        assert all(h.similarity is not None for h in hits)
        sims = [h.similarity for h in hits]
        assert sims == sorted(sims, reverse=True), (
            f"results not sorted by similarity desc: {sims}"
        )

    def test_search_with_only_empty_read_stores_returns_primary_hits(
        self, tmp_path: Path
    ):
        """Worker stores at Gate 4.5 are configured-but-empty pending
        bring-up. The aggregation must not regress primary's hits in
        that state."""
        primary = tmp_path / "primary"
        empty_r1 = tmp_path / "empty-r1"
        empty_r2 = tmp_path / "empty-r2"

        self._seed(primary, "csvkit gives column-level statistics on CSV files")
        # No seeding of empty_r1 / empty_r2 — they will lazy-init as
        # empty ChromaDB stores on first query.

        client = MemoryClient(
            memory_dir=primary, read_stores=[empty_r1, empty_r2]
        )
        hits = client.search("CSV analysis tool", limit=5)
        assert len(hits) == 1
        assert hits[0].source_store == primary


@pytest.mark.integration
class TestPrimaryWriteOnly:
    """Writes never touch read stores. Per Q2-A this invariant
    guarantees worker stores stay write-protected from Concierge
    (they receive writes only from their owning agents at the
    OpenClaw layer)."""

    def test_store_writes_only_to_primary(self, tmp_path: Path):
        primary = tmp_path / "primary"
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"

        # Pre-seed read stores so they have non-zero baselines we can
        # compare against post-write.
        MemoryClient(memory_dir=r1).store("r1 seed", tags=["seed"])
        MemoryClient(memory_dir=r2).store("r2 seed", tags=["seed"])

        client = MemoryClient(
            memory_dir=primary, read_stores=[r1, r2]
        )

        baseline_primary = client.stats()["total_memories"]
        client.store("brand-new concierge entry", tags=["new"])
        post_primary = client.stats()["total_memories"]

        assert post_primary == baseline_primary + 1, (
            "primary should gain exactly one entry"
        )

        # Read stores must be unchanged — query each directly to
        # confirm their counts didn't move.
        r1_check = MemoryClient(memory_dir=r1)
        r2_check = MemoryClient(memory_dir=r2)
        assert r1_check.stats()["total_memories"] == 1, (
            "r1 must still hold only its seed entry"
        )
        assert r2_check.stats()["total_memories"] == 1, (
            "r2 must still hold only its seed entry"
        )

    def test_identity_set_writes_only_to_primary(self, tmp_path: Path):
        primary = tmp_path / "primary"
        r1 = tmp_path / "r1"

        # Pre-create r1 as a real store with its own identity already set.
        MemoryClient(memory_dir=r1).identity_set("r1's own identity note")

        client = MemoryClient(memory_dir=primary, read_stores=[r1])
        client.identity_set("concierge primary identity note")

        # Primary holds the new note.
        assert client.identity_get() == "concierge primary identity note"

        # r1's note is untouched — confirmed by reading r1 directly.
        assert (
            MemoryClient(memory_dir=r1).identity_get()
            == "r1's own identity note"
        )


@pytest.mark.integration
class TestIdentityGetPrimaryOnly:
    """Per Q1-A: identity_get reads from primary only. Read stores'
    identity collections are ignored. The item-8 migration is the
    bridge that consolidates all agents' identity notes into the
    primary identity collection (tagged with agent_id)."""

    def test_identity_get_does_not_consult_read_stores(self, tmp_path: Path):
        primary = tmp_path / "primary"
        r1 = tmp_path / "r1"

        # Read store has an identity note; primary does not.
        MemoryClient(memory_dir=r1).identity_set("read-store identity content")

        client = MemoryClient(memory_dir=primary, read_stores=[r1])

        # Primary is unset → empty string (preserves existing behavior).
        # Aggregating from r1 would return "read-store identity content";
        # primary-only behavior returns "" exactly.
        assert client.identity_get() == ""


@pytest.mark.integration
class TestListAggregatesAcrossStores:
    """`list()` interleaves entries across stores by created_at desc.
    Per the multi-store docstring, cross-store created_at comparability
    holds because every store uses the same naive-UTC ISO format that
    Concierge's `store()` writes (matching moltbot convention)."""

    def test_list_returns_entries_from_all_stores(self, tmp_path: Path):
        primary = tmp_path / "primary"
        r1 = tmp_path / "r1"

        MemoryClient(memory_dir=primary).store("primary-A", tags=["t"])
        MemoryClient(memory_dir=r1).store("r1-A", tags=["t"])
        MemoryClient(memory_dir=primary).store("primary-B", tags=["t"])

        client = MemoryClient(memory_dir=primary, read_stores=[r1])
        hits = client.list(tag_filter="t", limit=10)

        texts = [h.text for h in hits]
        assert "primary-A" in texts
        assert "primary-B" in texts
        assert "r1-A" in texts
        assert len(hits) == 3

    def test_list_sort_desc_by_created_at_across_stores(self, tmp_path: Path):
        primary = tmp_path / "primary"
        r1 = tmp_path / "r1"

        # Three entries across two stores. The desc sort makes
        # later-written entries come first regardless of which store
        # they live in.
        import time

        MemoryClient(memory_dir=primary).store("first", tags=["t"])
        time.sleep(0.01)
        MemoryClient(memory_dir=r1).store("middle", tags=["t"])
        time.sleep(0.01)
        MemoryClient(memory_dir=primary).store("last", tags=["t"])

        client = MemoryClient(memory_dir=primary, read_stores=[r1])
        hits = client.list(tag_filter="t", limit=10)
        texts = [h.text for h in hits]
        assert texts == ["last", "middle", "first"], (
            f"created_at desc ordering failed across stores: {texts}"
        )

    def test_list_carries_source_store_per_hit(self, tmp_path: Path):
        primary = tmp_path / "primary"
        r1 = tmp_path / "r1"

        MemoryClient(memory_dir=primary).store("primary entry", tags=["t"])
        MemoryClient(memory_dir=r1).store("r1 entry", tags=["t"])

        client = MemoryClient(memory_dir=primary, read_stores=[r1])
        hits = client.list(tag_filter="t", limit=10)
        by_source = {h.source_store: h.text for h in hits}
        assert by_source[primary] == "primary entry"
        assert by_source[r1] == "r1 entry"


@pytest.mark.integration
class TestPerStoreGracefulDegradation:
    """Per Q2-A: per-read-store failure logs WARN once-per-store and
    contributes zero hits; the search/list call still returns hits
    from healthy stores. Primary failure preserves the hard-raise
    contract that `RecommendationService._lookup_memory` depends on.
    """

    def test_corrupt_read_store_skipped_with_warn_log(
        self, tmp_path: Path, caplog
    ):
        primary = tmp_path / "primary"
        healthy = tmp_path / "healthy"
        corrupt = tmp_path / "corrupt"

        MemoryClient(memory_dir=primary).store(
            "primary-content", tags=["t"]
        )
        MemoryClient(memory_dir=healthy).store(
            "healthy-read-content", tags=["t"]
        )

        # Force ChromaDB init failure on `corrupt` by writing a file
        # at the path where ChromaDB expects a directory. mkdir below
        # will raise (FileExistsError → init failure).
        corrupt.write_text("not a directory — break ChromaDB init")

        client = MemoryClient(
            memory_dir=primary, read_stores=[healthy, corrupt]
        )

        import logging
        with caplog.at_level(logging.WARNING, logger="core.memory"):
            hits = client.search("content", limit=20)

        texts = [h.text for h in hits]
        assert "primary-content" in texts
        assert "healthy-read-content" in texts
        # corrupt store contributed no hits, but the call succeeded.

        warn_messages = [
            r.message for r in caplog.records if r.levelname == "WARNING"
        ]
        assert any("read_store" in m and str(corrupt) in m for m in warn_messages), (
            f"expected WARN log for corrupt store; got: {warn_messages}"
        )

    def test_corrupt_store_warns_only_once_per_process(
        self, tmp_path: Path, caplog
    ):
        """Multiple search calls against the same corrupt store should
        WARN only on the first call; subsequent calls debug-log to
        avoid log flooding (per build note 2 from operator)."""
        primary = tmp_path / "primary"
        corrupt = tmp_path / "corrupt"

        MemoryClient(memory_dir=primary).store("p", tags=["t"])
        corrupt.write_text("not a directory")

        client = MemoryClient(memory_dir=primary, read_stores=[corrupt])

        import logging
        with caplog.at_level(logging.WARNING, logger="core.memory"):
            client.search("anything", limit=5)
            client.search("anything", limit=5)
            client.search("anything", limit=5)

        warn_count = sum(
            1
            for r in caplog.records
            if r.levelname == "WARNING" and str(corrupt) in r.message
        )
        assert warn_count == 1, (
            f"expected exactly one WARN for the corrupt store across "
            f"three calls; got {warn_count}"
        )

    def test_query_time_failure_after_successful_init_search(
        self, tmp_path: Path, caplog
    ):
        """Search-path coverage for the inner per-store try/except.

        Init-time failure paths are exercised above via the
        file-where-directory trick, but those return None from
        `_get_read_memories_collection` and never reach the inner
        try/except in `search()`. The realistic Gate 4.5 failure mode
        is different: a store that opens fine and fails mid-query
        (HNSW corruption, schema mismatch surfacing at query time,
        mid-write read). Simulate by warming up the lazy-init cache
        with a real ChromaDB collection, then swapping in a stub that
        raises on `.count()` / `.query()`. The healthy store's hits
        must still be returned; the failing store must WARN-skip;
        the exception must NOT propagate.

        Bundled into one test: also verify WARN-once-per-process holds
        on the query-time path (the inner try/except uses the same
        `_warned_unavailable_stores` set as `_get_read_memories_collection`).
        """
        primary = tmp_path / "primary"
        healthy = tmp_path / "healthy"
        post_init_failing = tmp_path / "post-init-failing"

        # Seed real data in primary, healthy, and post-init-failing.
        # The third store is initially a working ChromaDB; we swap its
        # cached collection after warmup.
        MemoryClient(memory_dir=primary).store(
            "primary content marker", tags=["t"]
        )
        MemoryClient(memory_dir=healthy).store(
            "healthy-read content marker", tags=["t"]
        )
        MemoryClient(memory_dir=post_init_failing).store(
            "real seed; will be hidden behind failing stub", tags=["t"]
        )

        client = MemoryClient(
            memory_dir=primary, read_stores=[healthy, post_init_failing]
        )

        # Warmup: this initializes `_read_memories[post_init_failing]`
        # via `_get_read_memories_collection`'s success path.
        warmup_hits = client.search("warmup", limit=20)
        warmup_texts = {h.text for h in warmup_hits}
        assert "real seed; will be hidden behind failing stub" in warmup_texts, (
            "warmup must verify the third store was reachable before we corrupt it"
        )
        assert post_init_failing in client._read_memories, (
            "warmup must have populated the cache for the third store"
        )

        # Swap in a stub that raises on every operation. ChromaDB
        # collection objects expose .count(), .query(), .get(); the
        # inner try/except in search() calls .count() then .query()
        # via _query_store. Either one raising hits the same except.
        class FailingCollection:
            def count(self):
                raise RuntimeError("simulated mid-query HNSW corruption")

            def query(self, **kwargs):
                raise RuntimeError("simulated query failure")

            def get(self, **kwargs):
                raise RuntimeError("simulated get failure")

        client._read_memories[post_init_failing] = FailingCollection()

        import logging

        with caplog.at_level(logging.WARNING, logger="core.memory"):
            hits = client.search("content marker", limit=20)

        # Failure did not propagate — search returned.
        texts = {h.text for h in hits}
        assert "primary content marker" in texts
        assert "healthy-read content marker" in texts
        # The failing store contributed zero hits.
        assert all(
            h.source_store != post_init_failing for h in hits
        ), "failing store must contribute zero hits to the aggregated result"

        # WARN log emitted with the query-time message + store path.
        warn_msgs = [
            r.message for r in caplog.records if r.levelname == "WARNING"
        ]
        assert any(
            "memory.read_store_query_failed" in m
            and str(post_init_failing) in m
            for m in warn_msgs
        ), (
            f"expected WARN naming query-time failure for the failing store; "
            f"got: {warn_msgs}"
        )

        # WARN-once-per-process: subsequent calls debug-log only.
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="core.memory"):
            client.search("content marker", limit=20)
            client.search("content marker", limit=20)

        repeat_warns = [
            r
            for r in caplog.records
            if r.levelname == "WARNING" and str(post_init_failing) in r.message
        ]
        assert repeat_warns == [], (
            f"WARN-once discipline broken on query-time path; got "
            f"{len(repeat_warns)} additional WARN(s) across 2 repeat calls"
        )

    def test_query_time_failure_after_successful_init_list(
        self, tmp_path: Path, caplog
    ):
        """List-path equivalent of the query-time-degradation test
        above. Inner block at `core/memory.py:584-612` is what we're
        covering — same WARN-once guard, slightly different log
        message (`memory.list.read_store_failed`)."""
        primary = tmp_path / "primary"
        healthy = tmp_path / "healthy"
        post_init_failing = tmp_path / "post-init-failing"

        MemoryClient(memory_dir=primary).store("primary-A", tags=["t"])
        MemoryClient(memory_dir=healthy).store("healthy-A", tags=["t"])
        MemoryClient(memory_dir=post_init_failing).store(
            "third-A — will be hidden behind failing stub", tags=["t"]
        )

        client = MemoryClient(
            memory_dir=primary, read_stores=[healthy, post_init_failing]
        )

        # Warmup via list() so the third store's collection caches.
        warmup_hits = client.list(tag_filter="t", limit=20)
        assert any(
            "third-A" in h.text for h in warmup_hits
        ), "warmup must verify the third store was reachable"
        assert post_init_failing in client._read_memories

        class FailingCollection:
            def count(self):
                raise RuntimeError("simulated list-side failure")

            def query(self, **kwargs):
                raise RuntimeError("simulated query failure")

            def get(self, **kwargs):
                raise RuntimeError("simulated get failure")

        client._read_memories[post_init_failing] = FailingCollection()

        import logging

        with caplog.at_level(logging.WARNING, logger="core.memory"):
            hits = client.list(tag_filter="t", limit=20)

        texts = {h.text for h in hits}
        assert "primary-A" in texts
        assert "healthy-A" in texts
        assert all(h.source_store != post_init_failing for h in hits)

        warn_msgs = [
            r.message for r in caplog.records if r.levelname == "WARNING"
        ]
        assert any(
            "memory.list.read_store_failed" in m
            and str(post_init_failing) in m
            for m in warn_msgs
        ), (
            f"expected WARN naming list-side query-time failure; got: {warn_msgs}"
        )

    def test_primary_failure_still_raises(self, tmp_path: Path):
        """Even with healthy read stores configured, primary failure
        is hard-fatal — preserves the no-recommendation contract in
        RecommendationService._lookup_memory."""
        primary = tmp_path / "primary"
        healthy = tmp_path / "healthy"

        MemoryClient(memory_dir=healthy).store("readable", tags=["t"])

        # Block primary init by making `primary` itself a regular file
        # (not a directory). `path.mkdir(parents=True, exist_ok=True)`
        # only suppresses errors when the existing path is a directory;
        # an existing non-directory at the same path raises
        # FileExistsError → mapped to MemoryUnavailableError. Same
        # trick used in the corrupt-read-store tests above.
        primary.write_text("not a directory — break ChromaDB init")

        client = MemoryClient(
            memory_dir=primary, read_stores=[healthy]
        )
        with pytest.raises(MemoryUnavailableError):
            client.search("anything", limit=5)


@pytest.mark.integration
class TestStatsReportsReadStores:
    """Per Q5-A: stats() includes per-read-store entries.
    Operator-debugging aid for Gate 4.5 health checks."""

    def test_stats_includes_read_stores_entries(self, tmp_path: Path):
        primary = tmp_path / "primary"
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"

        MemoryClient(memory_dir=primary).store("p1", tags=["t"])
        MemoryClient(memory_dir=primary).store("p2", tags=["t"])
        MemoryClient(memory_dir=r1).store("r1-only", tags=["t"])
        # r2 stays empty — initialized as an empty store on stats().

        client = MemoryClient(memory_dir=primary, read_stores=[r1, r2])
        stats = client.stats()

        assert stats["total_memories"] == 2
        assert stats["memory_dir"] == str(primary)
        assert "read_stores" in stats
        entries = {e["path"]: e for e in stats["read_stores"]}
        assert entries[str(r1)]["total_memories"] == 1
        assert entries[str(r2)]["total_memories"] == 0

    def test_stats_reports_error_for_unreachable_read_store(
        self, tmp_path: Path
    ):
        primary = tmp_path / "primary"
        corrupt = tmp_path / "corrupt"

        MemoryClient(memory_dir=primary).store("p", tags=["t"])
        corrupt.write_text("not a directory")

        client = MemoryClient(memory_dir=primary, read_stores=[corrupt])
        stats = client.stats()

        # Primary is healthy — total_memories still reports.
        assert stats["total_memories"] == 1
        entries = {e["path"]: e for e in stats["read_stores"]}
        assert "error" in entries[str(corrupt)]
        assert entries[str(corrupt)].get("total_memories") is None
