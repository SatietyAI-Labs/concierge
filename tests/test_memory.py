"""Tests for `core.memory` — MemoryClient / MemoryHit / graceful degradation.

Structure:

- **Fast tests** (default): import resolution, dataclass shape,
  constructor behavior, where-filter construction, id generation,
  results-parsing helpers. No ChromaDB touch, no sentence-transformers
  load.

- **Integration tests** (marked `@pytest.mark.integration`): full
  roundtrip against a temp-directory ChromaDB. Loads sentence-
  transformers on first run — slow (~10-30s), stays warm thereafter.
  Run with `pytest -m integration` or part of default `pytest`
  invocation. Skip-fast with `pytest -m "not integration"`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.memory import (
    COLLECTION_IDENTITY,
    COLLECTION_MEMORIES,
    MemoryClient,
    MemoryHit,
    MemoryUnavailableError,
    _gen_id,
    _get_results_to_hits,
    _parse_tags,
    _query_results_to_hits,
    get_memory_client,
    make_memory_client,
)


# ---- Fast tests ---------------------------------------------------------


class TestImportShape:
    """Public surface resolves; types are as expected."""

    def test_memory_hit_is_frozen_dataclass(self):
        hit = MemoryHit(
            id="mem_abc",
            text="hello",
            similarity=0.9,
            tags=("a", "b"),
            importance="normal",
            source="test",
            created_at="2026-04-21T12:00:00",
        )
        assert hit.id == "mem_abc"
        with pytest.raises((AttributeError, Exception)):
            hit.id = "mem_xyz"  # type: ignore[misc]

    def test_memory_unavailable_error_is_runtime_error(self):
        assert issubclass(MemoryUnavailableError, RuntimeError)

    def test_collection_names_match_moltbot(self):
        """These names are wire-compatible with moltbot-memory-mcp —
        if someone edits them, cross-read on a shared store breaks.
        """
        assert COLLECTION_MEMORIES == "memories"
        assert COLLECTION_IDENTITY == "identity"


class TestClientConstructionIsLazy:
    """Constructor does NOT touch ChromaDB or load sentence-
    transformers. This keeps `import core.memory` cheap and lets the
    N6 endpoint construct a client at app startup without paying for
    the memory subsystem until first use.
    """

    def test_init_with_nonexistent_dir_does_not_raise(self, tmp_path: Path):
        bogus = tmp_path / "does-not-exist-yet"
        assert not bogus.exists()
        client = MemoryClient(memory_dir=bogus)
        assert client.memory_dir == bogus
        assert not bogus.exists(), (
            "constructor must not create the directory — only lazy-init does"
        )

    def test_init_records_embedding_model_default(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path)
        assert client.embedding_model == "all-MiniLM-L6-v2"

    def test_init_accepts_custom_embedding_model(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path, embedding_model="custom-model")
        assert client.embedding_model == "custom-model"


class TestWhereFilterConstruction:
    """The ChromaDB `where` clause builder — importance-only under
    the current strategy (tag filtering is post-hoc per the
    ChromaDB 1.x metadata-filter change documented in
    `MemoryClient.search`)."""

    def test_no_filters_returns_none(self):
        assert MemoryClient._build_where_filter() is None

    def test_importance_only_returns_eq_clause(self):
        result = MemoryClient._build_where_filter(importance_filter="high")
        assert result == {"importance": "high"}

    def test_tag_filter_accepted_but_kept_for_future_use(self):
        """The helper still accepts tag_filter for call-site symmetry,
        but the returned clause is not what production callers use —
        they pass tag_filter=None and filter post-hoc."""
        result = MemoryClient._build_where_filter(tag_filter="tool-selection")
        assert result == {"tags": "tool-selection"}


class TestGenId:
    def test_id_has_mem_prefix(self):
        assert _gen_id("hello").startswith("mem_")

    def test_id_is_short_and_hex_suffix(self):
        mem_id = _gen_id("hello")
        suffix = mem_id.removeprefix("mem_")
        assert len(suffix) == 12
        int(suffix, 16)  # raises if not hex

    def test_id_varies_with_time(self):
        a = _gen_id("same text")
        b = _gen_id("same text")
        # Includes time.time() in hash — different ids even same text.
        # Occasional collision possible if within same millisecond; run
        # twice to amortize.
        c = _gen_id("same text")
        assert len({a, b, c}) >= 2, (
            "gen_id suffix should usually differ across consecutive calls"
        )


class TestTagParsing:
    """Memory metadata stores tags as JSON-encoded lists (moltbot
    convention). Parser must handle missing, empty, malformed, and
    non-list values without raising.
    """

    def test_empty_meta_returns_empty_tuple(self):
        assert _parse_tags({}) == ()

    def test_missing_tags_returns_empty_tuple(self):
        assert _parse_tags({"source": "x"}) == ()

    def test_empty_string_returns_empty_tuple(self):
        assert _parse_tags({"tags": ""}) == ()

    def test_valid_json_list_returns_tuple(self):
        assert _parse_tags({"tags": '["a", "b", "c"]'}) == ("a", "b", "c")

    def test_malformed_json_returns_empty_tuple(self):
        assert _parse_tags({"tags": "not-json"}) == ()

    def test_json_non_list_returns_empty_tuple(self):
        assert _parse_tags({"tags": '{"foo": "bar"}'}) == ()


class TestQueryResultParsing:
    """ChromaDB `query` returns nested-list shape (one list per
    query text). We always send one query text, so we read [0].
    """

    def test_empty_results_returns_empty_list(self):
        assert _query_results_to_hits({}) == []
        assert _query_results_to_hits({"ids": []}) == []
        assert _query_results_to_hits({"ids": [[]]}) == []

    def test_single_hit_parses_cleanly(self):
        results = {
            "ids": [["mem_abc"]],
            "documents": [["hello world"]],
            "metadatas": [[{"tags": '["x"]', "importance": "high", "source": "t"}]],
            "distances": [[0.1]],
        }
        hits = _query_results_to_hits(results)
        assert len(hits) == 1
        h = hits[0]
        assert h.id == "mem_abc"
        assert h.text == "hello world"
        assert h.similarity == 0.9  # 1 - 0.1
        assert h.tags == ("x",)
        assert h.importance == "high"

    def test_missing_distances_yields_none_similarity(self):
        results = {
            "ids": [["mem_a"]],
            "documents": [["t"]],
            "metadatas": [[{}]],
            "distances": None,
        }
        hits = _query_results_to_hits(results)
        assert len(hits) == 1
        assert hits[0].similarity is None


class TestGetResultParsing:
    """ChromaDB `get` returns flat-list shape (no query text,
    no distances)."""

    def test_empty_returns_empty(self):
        assert _get_results_to_hits({}) == []
        assert _get_results_to_hits({"ids": []}) == []

    def test_parses_without_similarity(self):
        results = {
            "ids": ["mem_a", "mem_b"],
            "documents": ["one", "two"],
            "metadatas": [{}, {"importance": "low"}],
        }
        hits = _get_results_to_hits(results)
        assert len(hits) == 2
        assert all(h.similarity is None for h in hits)
        assert hits[0].id == "mem_a"
        assert hits[1].importance == "low"


class TestFactoryAndDependency:
    def test_make_memory_client_uses_settings(self, tmp_path: Path):
        from core.config import Settings

        s = Settings(memory_dir=tmp_path / "custom")
        client = make_memory_client(s)
        assert client.memory_dir == tmp_path / "custom"

    def test_make_memory_client_default_read_stores_is_empty(self, tmp_path: Path):
        """Stage 1A item 2 — `memory_read_stores` defaults to []; the
        factory passes that through verbatim. Single-store behavior
        is the default; opt-in to multi-store is explicit.
        """
        from core.config import Settings

        s = Settings(memory_dir=tmp_path / "custom")
        client = make_memory_client(s)
        assert client.read_stores == []

    def test_make_memory_client_plumbs_read_stores(self, tmp_path: Path):
        """Stage 1A item 2 — non-empty `memory_read_stores` in Settings
        round-trips into `MemoryClient.read_stores`.
        """
        from core.config import Settings

        r1 = tmp_path / "read-1"
        r2 = tmp_path / "read-2"
        s = Settings(
            memory_dir=tmp_path / "primary",
            memory_read_stores=[r1, r2],
        )
        client = make_memory_client(s)
        assert client.read_stores == [r1, r2]

    def test_get_memory_client_returns_singleton(self):
        get_memory_client.cache_clear()
        a = get_memory_client()
        b = get_memory_client()
        assert a is b


# ---- Integration tests --------------------------------------------------


@pytest.mark.integration
class TestRoundtrip:
    """End-to-end against a temp-directory ChromaDB. Loads sentence-
    transformers on first run. Skip with `pytest -m "not integration"`.
    """

    def test_store_then_search_returns_hit(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        mem_id = client.store(
            "csvkit gives column-level statistics on CSV files via csvstat",
            tags=["tool-selection", "csv"],
            source="test",
        )
        assert mem_id.startswith("mem_")

        hits = client.search("analyze a CSV file", limit=5)
        assert len(hits) >= 1
        assert any(h.id == mem_id for h in hits)
        assert hits[0].similarity is not None and hits[0].similarity > 0

    def test_tag_filter_scopes_results(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.store("ripgrep replaces grep", tags=["tool-selection"])
        client.store("unrelated observation", tags=["other-tag"])

        hits_selection = client.search(
            "text search tool", tag_filter="tool-selection", limit=10
        )
        hits_other = client.search(
            "text search tool", tag_filter="other-tag", limit=10
        )
        selection_texts = [h.text for h in hits_selection]
        other_texts = [h.text for h in hits_other]
        assert any("ripgrep" in t for t in selection_texts)
        assert all("ripgrep" not in t for t in other_texts)

    def test_empty_store_returns_empty_list(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        assert client.search("anything", limit=5) == []
        assert client.list(limit=5) == []

    def test_list_sorts_by_created_at_desc(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.store("first", tags=["test"])
        client.store("second", tags=["test"])
        client.store("third", tags=["test"])
        hits = client.list(tag_filter="test", limit=10)
        assert len(hits) == 3
        assert hits[0].created_at >= hits[1].created_at >= hits[2].created_at


@pytest.mark.integration
class TestIdentityNotes:
    """End-to-end identity_get / identity_set against temp-dir ChromaDB.

    Fix Day 3 Task 7 adds identity as the compact running summary of
    operator tool preferences. Unset → "", set → round-trips exactly,
    set-twice → second write wins (upsert semantics)."""

    def test_unset_identity_returns_empty_string(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        assert client.identity_get() == ""

    def test_set_then_get_roundtrips(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        text = "Loaded-on-boot: csvkit (cli), ripgrep (cli)"
        client.identity_set(text)
        assert client.identity_get() == text

    def test_set_twice_overwrites(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.identity_set("first version")
        client.identity_set("second version")
        assert client.identity_get() == "second version"

    def test_named_key_scopes_independently(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.identity_set("default-content")
        client.identity_set("recent-installs-content", key="recent-installs")
        assert client.identity_get() == "default-content"
        assert client.identity_get(key="recent-installs") == "recent-installs-content"

    def test_identity_and_memories_collections_are_independent(
        self, tmp_path: Path
    ):
        """Storing memories must not populate identity and vice versa."""
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.store("a memory", tags=["test"])
        client.identity_set("an identity note")
        assert client.identity_get() == "an identity note"
        # Memory search doesn't surface the identity text
        hits = client.search("an identity note", limit=5)
        assert all("identity note" not in h.text for h in hits)

    def test_stats_reports_correct_counts(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        assert client.stats()["total_memories"] == 0
        client.store("one", tags=["x"])
        client.store("two", tags=["x"])
        stats = client.stats()
        assert stats["total_memories"] == 2
        assert stats["embedding_model"] == "all-MiniLM-L6-v2"
        assert stats["collection"] == "memories"

    def test_lazy_init_means_dir_not_created_until_first_op(
        self, tmp_path: Path
    ):
        target = tmp_path / "not-yet"
        MemoryClient(memory_dir=target)
        assert not target.exists()
        # Now trigger init via stats:
        client = MemoryClient(memory_dir=target)
        client.stats()
        assert target.exists()


@pytest.mark.integration
class TestIdentityPerAgent:
    """Stage 1A item 8 — `agent_id` / `extra_metadata` on
    `identity_set` and the per-agent aggregating read
    `identity_get_agent`. The default-keyed operator tool-prefs note
    must stay reachable only via no-arg `identity_get` (Finding 3).
    """

    def test_identity_set_with_agent_id_stored_in_metadata(
        self, tmp_path: Path
    ):
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.identity_set("scout note", key="agent:scout:identity",
                            agent_id="scout")
        meta = client._get_identity_collection().get(
            ids=["agent:scout:identity"], include=["metadatas"]
        )["metadatas"][0]
        assert meta["agent_id"] == "scout"

    def test_identity_set_extra_metadata_stored(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.identity_set(
            "a note", key="agent:radar:identity", agent_id="radar",
            extra_metadata={"source": "identity-md", "entry": "identity"},
        )
        meta = client._get_identity_collection().get(
            ids=["agent:radar:identity"], include=["metadatas"]
        )["metadatas"][0]
        assert meta["source"] == "identity-md"
        assert meta["entry"] == "identity"

    def test_identity_set_without_agent_id_omits_the_field(
        self, tmp_path: Path
    ):
        """Backward compat: the pre-item-8 call shape stores no
        `agent_id` metadata key at all.
        """
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.identity_set("legacy-shape note")
        meta = client._get_identity_collection().get(
            ids=["default"], include=["metadatas"]
        )["metadatas"][0]
        assert "agent_id" not in meta

    def test_identity_get_agent_empty_when_no_entries(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        assert client.identity_get_agent("alfred") == ""

    def test_identity_get_agent_aggregates_sorted_by_key(
        self, tmp_path: Path
    ):
        client = MemoryClient(memory_dir=tmp_path / "store")
        # Inserted out of key order — read must sort by document id.
        client.identity_set("rules text", key="agent:alfred:rules",
                            agent_id="alfred")
        client.identity_set("identity text", key="agent:alfred:identity",
                            agent_id="alfred")
        aggregated = client.identity_get_agent("alfred")
        # agent:alfred:identity sorts before agent:alfred:rules.
        assert aggregated == "identity text\n\nrules text"

    def test_identity_get_agent_scopes_by_agent(self, tmp_path: Path):
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.identity_set("alfred only", key="agent:alfred:identity",
                            agent_id="alfred")
        client.identity_set("bridge only", key="agent:bridge:identity",
                            agent_id="bridge")
        assert client.identity_get_agent("alfred") == "alfred only"
        assert client.identity_get_agent("bridge") == "bridge only"

    def test_identity_get_agent_excludes_default_note(self, tmp_path: Path):
        """The default tool-prefs note carries no `agent_id` — a
        per-agent read must never surface it.
        """
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.identity_set("operator tool-prefs summary")
        client.identity_set("alfred identity", key="agent:alfred:identity",
                            agent_id="alfred")
        assert client.identity_get_agent("alfred") == "alfred identity"

    def test_no_arg_identity_get_unaffected_by_agent_entries(
        self, tmp_path: Path
    ):
        """No-arg `identity_get()` keeps returning `key="default"`
        even after per-agent entries land in the same collection.
        """
        client = MemoryClient(memory_dir=tmp_path / "store")
        client.identity_set("the default note")
        client.identity_set("alfred identity", key="agent:alfred:identity",
                            agent_id="alfred")
        assert client.identity_get() == "the default note"
