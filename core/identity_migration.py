"""Identity-notes migration — Stage 1A item 8.

Reads per-agent identity content from where it actually lives and
upserts it into Concierge's own identity collection, scoped by an
`agent_id` metadata field so each agent's identity stays
distinguishable inside the shared collection. One-way migration
(master plan v1.1 §II.5 Deliverable 3 + §III.2 item 8): identity
flows from the agents into Concierge; Concierge becomes the source of
truth, the originals stay in place as defense-in-depth.

Two source surfaces (per DECISIONS [2026-05-14] D17 — 5 + 3 = 8):

  Surface 1 — per-agent workspace IDENTITY.md
      `<root>/workspace/IDENTITY.md`, one per agent (5 files). Read
      LIVE per items-8 Decision D2: a migration script's real job is
      to read identity from where it lives, not from a one-time
      Stage 0.5 disaster-recovery snapshot — D2 reflects how the
      script behaves in any real Concierge deployment. Roots resolve
      through `core.agent_config.AGENT_ROOTS` (the package's single
      codename↔functional-name registry — no second copy).

  Surface 2 — unified ChromaDB identity collection
      `~/.moltbot-memory-v2/` holds 3 identity entries (`role` /
      `owner` / `rules`), all Alfred's. Read read-only via a direct
      chromadb client, mirroring `scripts/export_agent_memory.py`'s
      read-only-on-live-stores pattern. Applying the same D2
      principle to Surface 2: read from the live store, not the
      `moltbot-memory-v2-identity.json` snapshot the plan-surface
      originally proposed.

Both surfaces are READS of live paths — identical in shape to what
the items-5+6 inspection did against `~/.openclaw-*/openclaw.json`.
No writes to any live system path: the migration's only write target
is Concierge's own identity collection.

Composite key scheme (D3): `agent:<agent_id>:<slug>` — namespaced
away from the operator tool-preferences note at `key="default"`,
which this migration never touches (Finding 3 invariant). 8 keys:
`agent:alfred:identity` + `agent:alfred:{role,owner,rules}` +
`agent:{scout,dispatch,radar,bridge}:identity`.

source_store note: this module never calls `MemoryClient.search()` /
`list()`, so `MemoryHit` — and its parked `source_store` field —
never enter item 8's code path. Per DECISIONS D35, `source_store`
stays parked for the post-item-8 memory-filter slice; item 8 does not
consume it.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from core.agent_config import AGENT_ROOTS
from core.memory import MemoryClient

logger = logging.getLogger(__name__)


# Canonical agent-codename set (CLAUDE.md §2). Pinned against
# `AGENT_ROOTS` keys by the exhaustiveness test in
# `tests/test_identity_migration.py` (D24): a codename added to one
# without the other fails the suite.
AGENT_CODENAMES: tuple[str, ...] = (
    "alfred", "scout", "dispatch", "radar", "bridge",
)

# Composite key namespace (D3). `<KEY_PREFIX>:<agent_id>:<slug>`.
KEY_PREFIX = "agent"

# `source` metadata values — which surface an entry came from.
SOURCE_IDENTITY_MD = "identity-md"
SOURCE_CHROMADB = "chromadb-identity"

# Surface-1 file location, relative to an agent's OpenClaw root.
IDENTITY_MD_RELPATH = Path("workspace") / "IDENTITY.md"

# Surface-2 unified store (Alfred's; D14). Read-only.
MOLTBOT_STORE = Path.home() / ".moltbot-memory-v2"
MOLTBOT_IDENTITY_COLLECTION = "identity"


def _make_key(agent_id: str, slug: str) -> str:
    """Build a composite identity-collection key (D3)."""
    return f"{KEY_PREFIX}:{agent_id}:{slug}"


@dataclass(frozen=True)
class IdentityEntry:
    """One identity entry queued for upsert into Concierge's identity
    collection.

    Attributes:
        key: Composite ChromaDB document id (`agent:<id>:<slug>`).
        agent_id: Owning agent codename — lands in metadata; the
            filter key for `MemoryClient.identity_get_agent`.
        source: `SOURCE_IDENTITY_MD` or `SOURCE_CHROMADB` — surface
            provenance, stored in metadata.
        entry: Slug naming the entry within the agent (`identity`,
            `role`, `owner`, `rules`); stored in metadata.
        document: The identity text, preserved verbatim.
    """

    key: str
    agent_id: str
    source: str
    entry: str
    document: str


@dataclass
class MigrationResult:
    """Outcome of a migration run.

    Attributes:
        entries_written: Number of identity entries upserted.
        keys: The composite keys written, in write order.
        warnings: Non-fatal degradation messages (missing source
            file, absent store/collection). A migration with
            warnings still succeeds for every source it could read.
    """

    entries_written: int = 0
    keys: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def collect_identity_md_entries(
    agent_roots: Mapping[str, Path],
) -> tuple[list[IdentityEntry], list[str]]:
    """Collect Surface-1 entries from per-agent workspace IDENTITY.md.

    For each codename in `AGENT_CODENAMES`, reads
    `<root>/workspace/IDENTITY.md` and produces one `IdentityEntry`.
    A missing or unreadable file is skipped with a warning rather
    than raising — graceful degradation per master plan §II.5 risk
    register row 5. Returns `(entries, warnings)`.
    """
    entries: list[IdentityEntry] = []
    warnings: list[str] = []
    for agent_id in AGENT_CODENAMES:
        root = agent_roots.get(agent_id)
        if root is None:
            warnings.append(
                f"no root path configured for agent {agent_id!r}; skipped"
            )
            continue
        path = root / IDENTITY_MD_RELPATH
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            warnings.append(
                f"IDENTITY.md not found for {agent_id!r} at {path}; skipped"
            )
            continue
        except OSError as exc:
            warnings.append(
                f"IDENTITY.md unreadable for {agent_id!r} at {path}: "
                f"{type(exc).__name__}: {exc}; skipped"
            )
            continue
        entries.append(
            IdentityEntry(
                key=_make_key(agent_id, "identity"),
                agent_id=agent_id,
                source=SOURCE_IDENTITY_MD,
                entry="identity",
                document=text,
            )
        )
    return entries, warnings


def collect_chromadb_identity_entries(
    store_path: Path,
    *,
    owner_agent_id: str = "alfred",
    collection_name: str = MOLTBOT_IDENTITY_COLLECTION,
) -> tuple[list[IdentityEntry], list[str]]:
    """Collect Surface-2 entries from the unified ChromaDB identity
    collection.

    Opens `store_path` read-only and reads every entry in its
    identity collection (`role` / `owner` / `rules` on the live
    store). Each becomes an `IdentityEntry` keyed `agent:<owner>:
    <entry-id>`. The unified store is Alfred's (D14), so
    `owner_agent_id` defaults to `alfred`.

    A missing store directory (no `chroma.sqlite3`) or absent
    collection is skipped with a warning rather than raising —
    Surface 2 simply contributes nothing. Returns
    `(entries, warnings)`.
    """
    entries: list[IdentityEntry] = []
    warnings: list[str] = []

    if not (store_path / "chroma.sqlite3").exists():
        warnings.append(
            f"unified store has no chroma.sqlite3 at {store_path}; "
            f"surface-2 skipped"
        )
        return entries, warnings

    # Imported lazily so the module (and the unit tests that exercise
    # only Surface 1 / the key scheme) don't pay the chromadb import.
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    client = chromadb.PersistentClient(
        path=str(store_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    try:
        collection = client.get_collection(name=collection_name)
    except Exception as exc:  # noqa: BLE001 — absent collection is non-fatal
        warnings.append(
            f"identity collection {collection_name!r} absent in "
            f"{store_path}: {type(exc).__name__}: {exc}; surface-2 skipped"
        )
        return entries, warnings

    # `.get()` fetches by id — no embedding function is exercised
    # (mirrors scripts/export_agent_memory.py's read-only pattern).
    raw = collection.get(include=["documents"])
    ids = raw.get("ids") or []
    docs = raw.get("documents") or [None] * len(ids)
    for index, entry_id in enumerate(ids):
        document = docs[index] if index < len(docs) else None
        if document is None:
            warnings.append(
                f"unified-store identity entry {entry_id!r} has no "
                f"document; skipped"
            )
            continue
        entries.append(
            IdentityEntry(
                key=_make_key(owner_agent_id, entry_id),
                agent_id=owner_agent_id,
                source=SOURCE_CHROMADB,
                entry=entry_id,
                document=document,
            )
        )
    return entries, warnings


def migrate_identity_notes(
    *,
    memory_client: MemoryClient,
    agent_roots: Mapping[str, Path] | None = None,
    moltbot_store: Path = MOLTBOT_STORE,
) -> MigrationResult:
    """Run the full identity-notes migration.

    Collects both surfaces, then upserts every entry into
    `memory_client`'s identity collection via
    `MemoryClient.identity_set` (D6 — all identity writes go through
    one method), stamping `agent_id` plus `source` / `entry`
    provenance metadata. The composite key scheme makes the run
    idempotent: a rerun upserts the same keys (delete-then-add), so
    the collection holds the same 8 entries afterward — never 16.

    `agent_roots` defaults to `AGENT_ROOTS` (live paths). Tests pass a
    `tmp_path`-backed map and a tmp ChromaDB store; the live Gate 4.5
    run uses the defaults.

    The operator tool-preferences note at `key="default"` is never
    read or written here — composite keys are namespaced away from it
    (D3 / Finding 3 invariant).
    """
    roots = AGENT_ROOTS if agent_roots is None else agent_roots

    md_entries, md_warnings = collect_identity_md_entries(roots)
    chroma_entries, chroma_warnings = collect_chromadb_identity_entries(
        moltbot_store
    )
    all_entries = md_entries + chroma_entries

    result = MigrationResult(warnings=md_warnings + chroma_warnings)
    for entry in all_entries:
        memory_client.identity_set(
            entry.document,
            key=entry.key,
            agent_id=entry.agent_id,
            extra_metadata={"source": entry.source, "entry": entry.entry},
        )
        result.keys.append(entry.key)
        logger.info(
            "identity_migration.upsert key=%s agent_id=%s source=%s",
            entry.key, entry.agent_id, entry.source,
        )
    result.entries_written = len(result.keys)
    logger.info(
        "identity_migration.done entries=%d warnings=%d",
        result.entries_written, len(result.warnings),
    )
    return result
