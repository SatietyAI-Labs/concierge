"""Tests for core/identity_migration.py — Stage 1A item 8.

The identity-notes migration reads two source surfaces (per-agent
workspace IDENTITY.md + the unified ChromaDB identity collection) and
upserts 8 entries into Concierge's own identity collection, scoped by
`agent_id` metadata under the composite key scheme `agent:<id>:<slug>`.

Test surface
------------
- Pure (no ChromaDB): codename-set exhaustiveness (D24), key scheme,
  Surface-1 IDENTITY.md collection incl. degradation paths.
- Integration: Surface-2 ChromaDB collection, end-to-end migration,
  and the load-bearing `key="default"` invariant (Finding 3) — the
  operator tool-preferences note must survive a migration untouched.

`source_store` note: this module never calls `MemoryClient.search()`
/ `list()`, so `MemoryHit.source_store` is never exercised here. Per
DECISIONS D35 it stays parked for the post-item-8 memory-filter slice.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.agent_config import AGENT_ROOTS
from core.identity_migration import (
    AGENT_CODENAMES,
    SOURCE_CHROMADB,
    SOURCE_IDENTITY_MD,
    IdentityEntry,
    _make_key,
    collect_chromadb_identity_entries,
    collect_identity_md_entries,
    migrate_identity_notes,
)
from core.memory import IDENTITY_DEFAULT_KEY, MemoryClient

# ---- Fixtures / helpers ----------------------------------------------------

# Realistic small identity blocks, one per agent codename.
_IDENTITY_MD_CONTENT: dict[str, str] = {
    "alfred": (
        "# IDENTITY.md - Who Am I?\n\n"
        "- **Name:** Alfred\n"
        "- **Vibe:** Professional but not stuffy.\n"
        "- **Emoji:** 🎩\n"
    ),
    "scout": (
        "# IDENTITY.md - Who Am I?\n"
        "- **Name:** Scout\n"
        "- **Role:** Content Prep Agent for SatietyAI\n"
        "- **Emoji:** 📝\n"
    ),
    "dispatch": "# IDENTITY.md\n- **Name:** Dispatch\n- **Emoji:** 📮\n",
    "radar": "# IDENTITY.md\n- **Name:** Radar\n- **Emoji:** 📡\n",
    "bridge": "# IDENTITY.md\n- **Name:** Bridge\n- **Emoji:** 🌉\n",
}

# Surface-2 unified-store identity content (Alfred's role/owner/rules).
_MOLTBOT_IDENTITY: dict[str, str] = {
    "role": "Alfred - Lewie's AI building partner for SatietyAI.",
    "owner": "Lewie (Lewis Sloan) - Founder of SatietyAI. Scottsdale, AZ.",
    "rules": "1) Ask before deploying. 2) Use API MCPs over browser.",
}


def _write_identity_md(root: Path, content: str) -> Path:
    """Create `<root>/workspace/IDENTITY.md` with `content`."""
    path = root / "workspace" / "IDENTITY.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_agent_roots(
    base: Path, codenames: tuple[str, ...] = AGENT_CODENAMES
) -> dict[str, Path]:
    """Build a codename→root map under `base`, each with an
    IDENTITY.md written from `_IDENTITY_MD_CONTENT`.
    """
    roots: dict[str, Path] = {}
    for codename in codenames:
        root = base / codename
        _write_identity_md(root, _IDENTITY_MD_CONTENT[codename])
        roots[codename] = root
    return roots


def _build_moltbot_store(path: Path) -> Path:
    """Build a tmp ChromaDB store with an `identity` collection
    holding the 3 Surface-2 entries. Uses `MemoryClient.identity_set`
    so the store is byte-shaped exactly like the live unified store's
    identity collection.
    """
    client = MemoryClient(memory_dir=path)
    for entry_id, document in _MOLTBOT_IDENTITY.items():
        client.identity_set(document, key=entry_id)
    return path


def _identity_count(client: MemoryClient) -> int:
    """Count rows in a client's identity collection."""
    return client._get_identity_collection().count()


def _identity_metadata(client: MemoryClient, key: str) -> dict:
    """Return the stored metadata for one identity-collection key."""
    result = client._get_identity_collection().get(
        ids=[key], include=["metadatas"]
    )
    metas = result.get("metadatas") or []
    assert metas, f"no identity entry found for key {key!r}"
    return metas[0]


# ---- Pure: codename-set exhaustiveness (D24) -------------------------------


class TestAgentCodenameSet:
    """`AGENT_CODENAMES` is a canonical set new agents must land in
    lock-step with `AGENT_ROOTS` (D24 defensive-guard pattern, per
    item 1b D56 — pin the set proactively, not after a regression).
    """

    def test_codenames_are_exactly_the_five(self):
        assert set(AGENT_CODENAMES) == {
            "alfred", "scout", "dispatch", "radar", "bridge",
        }

    def test_codenames_match_agent_roots_keys(self):
        """A codename added to one map without the other fails here —
        the migration resolves IDENTITY.md paths through AGENT_ROOTS.
        """
        assert set(AGENT_CODENAMES) == set(AGENT_ROOTS.keys())


# ---- Pure: composite key scheme (D3) ---------------------------------------


class TestKeyScheme:
    """Composite keys (`agent:<id>:<slug>`) are namespaced away from
    the operator tool-preferences note at `key="default"`.
    """

    def test_make_key_shape(self):
        assert _make_key("alfred", "role") == "agent:alfred:role"
        assert _make_key("scout", "identity") == "agent:scout:identity"

    def test_keys_namespaced_away_from_default(self):
        for agent in AGENT_CODENAMES:
            for slug in ("identity", "role", "owner", "rules"):
                key = _make_key(agent, slug)
                assert key != IDENTITY_DEFAULT_KEY
                assert key.startswith("agent:")


# ---- Pure: Surface-1 IDENTITY.md collection --------------------------------


class TestCollectIdentityMd:
    """Surface 1 — per-agent workspace IDENTITY.md. Filesystem only;
    no ChromaDB.
    """

    def test_collects_all_five_when_present(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path)
        entries, warnings = collect_identity_md_entries(roots)
        assert len(entries) == 5
        assert warnings == []
        assert {e.agent_id for e in entries} == set(AGENT_CODENAMES)

    def test_entry_fields_are_correct(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path)
        entries, _ = collect_identity_md_entries(roots)
        by_agent = {e.agent_id: e for e in entries}
        scout = by_agent["scout"]
        assert scout.key == "agent:scout:identity"
        assert scout.source == SOURCE_IDENTITY_MD
        assert scout.entry == "identity"

    def test_document_preserved_verbatim(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path)
        entries, _ = collect_identity_md_entries(roots)
        by_agent = {e.agent_id: e for e in entries}
        for codename in AGENT_CODENAMES:
            assert by_agent[codename].document == _IDENTITY_MD_CONTENT[codename]

    def test_missing_file_skips_with_warning(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path)
        # Remove Radar's IDENTITY.md — the migration must degrade, not fail.
        (roots["radar"] / "workspace" / "IDENTITY.md").unlink()
        entries, warnings = collect_identity_md_entries(roots)
        assert len(entries) == 4
        assert "radar" not in {e.agent_id for e in entries}
        assert len(warnings) == 1
        assert "radar" in warnings[0] and "not found" in warnings[0]

    def test_unreadable_file_skips_with_warning(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path)
        # Replace Bridge's IDENTITY.md with a directory — read_text
        # raises IsADirectoryError (an OSError), not FileNotFoundError.
        bridge_md = roots["bridge"] / "workspace" / "IDENTITY.md"
        bridge_md.unlink()
        bridge_md.mkdir()
        entries, warnings = collect_identity_md_entries(roots)
        assert len(entries) == 4
        assert "bridge" not in {e.agent_id for e in entries}
        assert len(warnings) == 1
        assert "bridge" in warnings[0] and "unreadable" in warnings[0]

    def test_unconfigured_root_skips_with_warning(self, tmp_path: Path):
        # A roots map missing a codename entirely — degrade, don't crash.
        roots = _make_agent_roots(tmp_path)
        del roots["dispatch"]
        entries, warnings = collect_identity_md_entries(roots)
        assert len(entries) == 4
        assert len(warnings) == 1
        assert "dispatch" in warnings[0]


# ---- Integration: Surface-2 ChromaDB collection ----------------------------


@pytest.mark.integration
class TestCollectChromadbIdentity:
    """Surface 2 — unified ChromaDB identity collection. Read-only;
    every entry is attributed to Alfred (the unified store is his).
    """

    def test_collects_three_entries(self, tmp_path: Path):
        store = _build_moltbot_store(tmp_path / "moltbot")
        entries, warnings = collect_chromadb_identity_entries(store)
        assert len(entries) == 3
        assert warnings == []
        assert all(e.agent_id == "alfred" for e in entries)
        assert all(e.source == SOURCE_CHROMADB for e in entries)

    def test_entry_fields_and_keys(self, tmp_path: Path):
        store = _build_moltbot_store(tmp_path / "moltbot")
        entries, _ = collect_chromadb_identity_entries(store)
        by_key = {e.key: e for e in entries}
        assert set(by_key) == {
            "agent:alfred:role",
            "agent:alfred:owner",
            "agent:alfred:rules",
        }
        assert by_key["agent:alfred:role"].entry == "role"
        assert by_key["agent:alfred:role"].document == _MOLTBOT_IDENTITY["role"]

    def test_missing_store_skips_with_warning(self, tmp_path: Path):
        # Path with no chroma.sqlite3 — Surface 2 contributes nothing.
        entries, warnings = collect_chromadb_identity_entries(
            tmp_path / "does-not-exist"
        )
        assert entries == []
        assert len(warnings) == 1
        assert "chroma.sqlite3" in warnings[0]

    def test_missing_collection_skips_with_warning(self, tmp_path: Path):
        # A store that exists but has no `identity` collection — a
        # MemoryClient that only ever stored memories produces one.
        store = tmp_path / "memories-only"
        MemoryClient(memory_dir=store).store("a memory", tags=["x"])
        entries, warnings = collect_chromadb_identity_entries(
            store, collection_name="identity"
        )
        assert entries == []
        assert len(warnings) == 1
        assert "absent" in warnings[0]


# ---- Integration: end-to-end migration -------------------------------------


@pytest.mark.integration
class TestMigrateEndToEnd:
    """Full migration: both surfaces → Concierge's identity
    collection, 8 entries, scoped by `agent_id`.
    """

    def test_migrates_eight_entries(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path / "agents")
        store = _build_moltbot_store(tmp_path / "moltbot")
        client = MemoryClient(memory_dir=tmp_path / "concierge")
        result = migrate_identity_notes(
            memory_client=client, agent_roots=roots, moltbot_store=store
        )
        assert result.entries_written == 8
        assert len(result.keys) == 8
        assert result.warnings == []
        assert _identity_count(client) == 8

    def test_all_keys_use_composite_scheme(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path / "agents")
        store = _build_moltbot_store(tmp_path / "moltbot")
        client = MemoryClient(memory_dir=tmp_path / "concierge")
        result = migrate_identity_notes(
            memory_client=client, agent_roots=roots, moltbot_store=store
        )
        assert set(result.keys) == {
            "agent:alfred:identity",
            "agent:alfred:role",
            "agent:alfred:owner",
            "agent:alfred:rules",
            "agent:scout:identity",
            "agent:dispatch:identity",
            "agent:radar:identity",
            "agent:bridge:identity",
        }

    def test_entries_queryable_by_agent_id(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path / "agents")
        store = _build_moltbot_store(tmp_path / "moltbot")
        client = MemoryClient(memory_dir=tmp_path / "concierge")
        migrate_identity_notes(
            memory_client=client, agent_roots=roots, moltbot_store=store
        )
        # Alfred owns four entries — aggregated, blank-line joined.
        alfred = client.identity_get_agent("alfred")
        assert "Alfred" in alfred
        assert _MOLTBOT_IDENTITY["role"] in alfred
        assert _MOLTBOT_IDENTITY["owner"] in alfred
        assert _MOLTBOT_IDENTITY["rules"] in alfred
        # Scout owns exactly one — its IDENTITY.md, verbatim.
        assert client.identity_get_agent("scout") == _IDENTITY_MD_CONTENT["scout"]

    def test_idempotent_rerun_keeps_eight(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path / "agents")
        store = _build_moltbot_store(tmp_path / "moltbot")
        client = MemoryClient(memory_dir=tmp_path / "concierge")
        migrate_identity_notes(
            memory_client=client, agent_roots=roots, moltbot_store=store
        )
        # Second run upserts the same 8 composite keys — never 16.
        result = migrate_identity_notes(
            memory_client=client, agent_roots=roots, moltbot_store=store
        )
        assert result.entries_written == 8
        assert _identity_count(client) == 8
        assert client.identity_get_agent("scout") == _IDENTITY_MD_CONTENT["scout"]

    def test_warnings_propagate_but_migration_proceeds(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path / "agents")
        (roots["radar"] / "workspace" / "IDENTITY.md").unlink()
        client = MemoryClient(memory_dir=tmp_path / "concierge")
        # No moltbot store either — Surface 2 also degrades.
        result = migrate_identity_notes(
            memory_client=client,
            agent_roots=roots,
            moltbot_store=tmp_path / "no-store",
        )
        # 4 IDENTITY.md (Radar dropped) + 0 from Surface 2 = 4.
        assert result.entries_written == 4
        assert len(result.warnings) == 2
        assert _identity_count(client) == 4

    def test_metadata_carries_agent_id_source_and_entry(self, tmp_path: Path):
        roots = _make_agent_roots(tmp_path / "agents")
        store = _build_moltbot_store(tmp_path / "moltbot")
        client = MemoryClient(memory_dir=tmp_path / "concierge")
        migrate_identity_notes(
            memory_client=client, agent_roots=roots, moltbot_store=store
        )
        md_meta = _identity_metadata(client, "agent:bridge:identity")
        assert md_meta["agent_id"] == "bridge"
        assert md_meta["source"] == SOURCE_IDENTITY_MD
        assert md_meta["entry"] == "identity"
        chroma_meta = _identity_metadata(client, "agent:alfred:rules")
        assert chroma_meta["agent_id"] == "alfred"
        assert chroma_meta["source"] == SOURCE_CHROMADB
        assert chroma_meta["entry"] == "rules"


# ---- Integration: the load-bearing key="default" invariant -----------------


@pytest.mark.integration
class TestDefaultKeyInvariant:
    """Finding 3 — the operator tool-preferences note at
    `key="default"` is load-bearing for the recommend prompt. The
    migration adds 8 entries to the SAME collection; this test pins
    that it neither overwrites nor invalidates `default`.

    This invariant test is the regression guard for the live
    behavior — worth more than the rest of the migration surface
    combined (operator instruction at item 8 plan review).
    """

    def test_default_entry_survives_and_exactly_eight_added(
        self, tmp_path: Path
    ):
        client = MemoryClient(memory_dir=tmp_path / "concierge")
        # Seed the pre-migration state: one distinctive `default` note.
        seeded = "DISTINCTIVE-TOOL-PREFS-SUMMARY: csvkit, ripgrep, fd"
        client.identity_set(seeded)
        assert _identity_count(client) == 1

        roots = _make_agent_roots(tmp_path / "agents")
        store = _build_moltbot_store(tmp_path / "moltbot")
        result = migrate_identity_notes(
            memory_client=client, agent_roots=roots, moltbot_store=store
        )

        # Exactly 8 new entries; the collection now holds default + 8.
        assert result.entries_written == 8
        assert _identity_count(client) == 9
        assert IDENTITY_DEFAULT_KEY not in result.keys

        # The default note is byte-identical and still the no-arg read.
        assert client.identity_get() == seeded
        assert client.identity_get(key=IDENTITY_DEFAULT_KEY) == seeded

    def test_agent_reads_never_surface_the_default_note(
        self, tmp_path: Path
    ):
        client = MemoryClient(memory_dir=tmp_path / "concierge")
        client.identity_set("operator tool-prefs summary")
        roots = _make_agent_roots(tmp_path / "agents")
        store = _build_moltbot_store(tmp_path / "moltbot")
        migrate_identity_notes(
            memory_client=client, agent_roots=roots, moltbot_store=store
        )
        # `default` has no agent_id metadata — no per-agent read hits it.
        for agent in AGENT_CODENAMES:
            assert "tool-prefs summary" not in client.identity_get_agent(agent)


# ---- Construction sanity ---------------------------------------------------


class TestIdentityEntry:
    """`IdentityEntry` is a frozen value object."""

    def test_is_frozen(self):
        entry = IdentityEntry(
            key="agent:alfred:role",
            agent_id="alfred",
            source=SOURCE_CHROMADB,
            entry="role",
            document="text",
        )
        with pytest.raises(AttributeError):
            entry.document = "mutated"  # type: ignore[misc]
