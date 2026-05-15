"""Memory service wrapper for Concierge.

Re-implements moltbot-memory-mcp's backing-store operations as a
Python-natural client — not via MCP protocol, not via tool-decorated
async functions. Uses the same ChromaDB collection names
(`memories`, `identity`), the same default embedding model
(`all-MiniLM-L6-v2`), and the same tag-serialization convention
(JSON-encoded list in metadata with `$contains` filter) so that a
Concierge client pointed at a shared store can co-mingle
reads/writes with moltbot-written memories.

## Isolation default

Per DECISIONS `[2026-04-21 18:00]` (operational-first pivot), the
default `memory_dir` is `~/.concierge-memory/` — **isolated** from
moltbot's `~/.moltbot-memory-v2/`. Explicit opt-in to the shared
store via `CONCIERGE_MEMORY_DIR=~/.moltbot-memory-v2`. Rationale:
Concierge-under-development must not contaminate Alfred's
production memory, and Alfred's memory mutations must not introduce
non-determinism into Concierge sessions during operational
shakedown.

## Multi-store read (Stage 1A item 2; upgrade-project v1.1 §III.2)

Per upgrade-project DECISIONS [2026-05-13] D14, the live fleet
configures per-worker `MOLTBOT_MEMORY_DIR` per-agent at the OpenClaw
layer. Concierge can read from additional ChromaDB stores via the
`read_stores: list[Path]` constructor parameter — `search`, `list`,
and `stats` aggregate across primary + read stores. **Writes
(`store`, `identity_set`) always scope to primary `memory_dir`.**
Per-read-store init failure WARNs once-per-store-per-process and
skips that store; primary-store failure still raises
`MemoryUnavailableError` (unchanged contract for the
no-recommendation path in `RecommendationService._lookup_memory`).

All configured stores must share the same embedding model
(default `all-MiniLM-L6-v2`) for cosine similarities to be
comparable across stores. A read store built with a different model
surfaces at collection-open time as an init failure → WARN-skip.
Gate 4.5 is where this assumption gets exercised against the four
real configured stores for the first time; operator should watch
for unexpected per-store WARN entries at that point.

## Graceful degradation

All public methods raise `MemoryUnavailableError` on **primary**
backing-store failure (ChromaDB init error, embedding-model load
failure, query error). N6 `POST /recommend` is expected to catch
this narrow exception and serve a recommendation without memory
context, annotating the response accordingly. Hard Python errors
propagate; only the "memory is unavailable for this operation"
case is a graceful-degradation surface. Per-read-store failure
degrades to "this store contributed zero hits" (logged WARN).

## Lazy initialization

ChromaDB clients (primary + per read store) and the shared
embedding function all lazy-init on first use. Importing
`core.memory` is cheap; first call to `search`/`store`/`list`/
`stats` pays the ~300MB / 5-30s sentence-transformers load.
Subsequent first-touch of an unvisited read store pays only the
ChromaDB-client init (~ms on warm filesystem) since the embedding
function is shared. Tests that only verify import resolution stay
fast.

## Not implemented (scope trim for operational-first N5 budget)

- `delete`, `update`, `identity_get`, `identity_set` — available in
  moltbot's tool surface; no consumer in Concierge yet. Add when
  N7 lifecycle scanner, N19 token-win, or a future
  identity-inspection feature materializes a call site.
- Async method variants — ChromaDB operations are sync under the
  hood; FastAPI wraps sync dependencies in its threadpool
  automatically. No async surface needed until a real async
  caller appears.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.config import Settings, get_settings


logger = logging.getLogger(__name__)

COLLECTION_MEMORIES = "memories"
"""ChromaDB collection name. Must match moltbot-memory-mcp for
cross-read compatibility on a shared store.
"""

COLLECTION_IDENTITY = "identity"
"""Identity-notes collection name.

Per DECISIONS `[2026-04-23]` (Identity Notes included in v1), the
identity collection holds a compact running summary of operator tool
preferences. `MemoryClient.identity_get` / `identity_set` (Fix Day 3
Task 7) are the read/write surfaces; the recommend prompt composer
injects the note between the adapter preamble and X3 so Opus has
persistent operator context without re-deriving from memory search
on every call.
"""

IDENTITY_DEFAULT_KEY = "default"
"""Default identity-note key. Identity notes are keyed so multiple
facets (preferences, recent installs, etc.) could coexist — v1 uses
a single default key. The key doubles as the ChromaDB document id.
"""


class MemoryUnavailableError(RuntimeError):
    """Raised when a memory operation cannot complete due to
    backing-store failure (init error, embedding-model failure,
    query-time exception). Callers that want graceful degradation
    catch this narrowly and proceed without memory context.
    """


@dataclass(frozen=True)
class MemoryHit:
    """One result from a memory search or list operation.

    Attributes:
        id: Memory's unique id (e.g. `mem_abc123def456`).
        text: Full stored text (not truncated — consumer truncates
            at display time if needed).
        similarity: Cosine similarity in [0.0, 1.0] for semantic
            search hits; None for list/get results that did not go
            through `query`.
        tags: Tuple of tag strings. Always a tuple (immutable),
            even if originally stored as a list.
        importance: One of moltbot's importance levels ("low",
            "normal", "high", "critical"); defaults to "normal".
        source: Provenance string from the memory's metadata.
        created_at: ISO-8601 UTC timestamp string.
        source_store: Path of the ChromaDB store this hit came from
            (Stage 1A item 2 — multi-store read). `None` for hits
            constructed without a store binding (e.g. test fixtures
            or pre-multi-store call sites). Unblocks item 3's
            `agent_id` filtering by giving each hit per-store
            provenance.
    """

    id: str
    text: str
    similarity: float | None
    tags: tuple[str, ...]
    importance: str
    source: str
    created_at: str
    source_store: Path | None = None


class MemoryClient:
    """Synchronous client for the ChromaDB-backed semantic memory.

    Construction is cheap — no ChromaDB touch, no embedding model
    load. First call to a public method (search/store/list/stats)
    triggers lazy init. `MemoryUnavailableError` is raised at the
    boundary on any init or operation failure.
    """

    def __init__(
        self,
        memory_dir: Path,
        embedding_model: str = "all-MiniLM-L6-v2",
        read_stores: list[Path] | None = None,
    ) -> None:
        self.memory_dir = memory_dir
        self.embedding_model = embedding_model
        # De-dupe and drop any accidental match with primary so the
        # primary store isn't queried twice (which would double-count
        # hits in the aggregated result).
        self.read_stores: list[Path] = _dedupe_read_stores(
            primary=memory_dir, read_stores=read_stores or []
        )
        self._client: Any = None
        self._memories: Any = None
        self._identity: Any = None
        self._embedding_fn: Any = None
        # Per-read-store lazy state — populated on first successful
        # init for each path. Failed inits are NOT cached here (they
        # could become valid mid-process if the operator fixes the
        # store); they are tracked in `_warned_unavailable_stores`
        # below for log-once-per-process WARN behavior.
        self._read_clients: dict[Path, Any] = {}
        self._read_memories: dict[Path, Any] = {}
        # Tracks read stores that have already WARN-logged this
        # process so a persistently-corrupt store doesn't flood logs
        # on every search call. Subsequent failures from a tracked
        # store debug-log only.
        self._warned_unavailable_stores: set[Path] = set()
        logger.debug(
            "MemoryClient configured: dir=%s model=%s read_stores=%d (lazy init)",
            memory_dir,
            embedding_model,
            len(self.read_stores),
        )

    # ---- Lazy init helpers --------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                self._client = self._build_persistent_client(self.memory_dir)
                logger.info("ChromaDB client initialized at %s", self.memory_dir)
            except Exception as exc:
                raise MemoryUnavailableError(
                    f"ChromaDB init failed at {self.memory_dir}: {exc}"
                ) from exc
        return self._client

    @staticmethod
    def _build_persistent_client(path: Path) -> Any:
        """Construct a ChromaDB `PersistentClient` for `path`. Creates
        the directory if absent (matches the prior single-store
        behavior). Caller wraps in try/except to map to either
        `MemoryUnavailableError` (primary) or per-store WARN-skip
        (read stores).
        """
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        path.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _get_embedding_fn(self) -> Any:
        if self._embedding_fn is None:
            try:
                from chromadb.utils.embedding_functions import (
                    SentenceTransformerEmbeddingFunction,
                )

                self._embedding_fn = SentenceTransformerEmbeddingFunction(
                    model_name=self.embedding_model,
                    device="cpu",
                )
                logger.info("Embedding model loaded: %s", self.embedding_model)
            except Exception as exc:
                raise MemoryUnavailableError(
                    f"Embedding model '{self.embedding_model}' init failed: {exc}"
                ) from exc
        return self._embedding_fn

    def _get_memories_collection(self) -> Any:
        if self._memories is None:
            self._memories = self._get_client().get_or_create_collection(
                name=COLLECTION_MEMORIES,
                embedding_function=self._get_embedding_fn(),
                metadata={"hnsw:space": "cosine"},
            )
        return self._memories

    def _get_identity_collection(self) -> Any:
        """Lazy init for the identity-notes collection.

        Identity notes are stored without an embedding function at the
        cosine-space level — they're fetched by id, not by similarity.
        But ChromaDB collections need an embedding function regardless
        (it gates `add` calls); reusing the memories collection's fn
        keeps the client footprint minimal.

        Per Stage 1A item 2 Q1-A: identity collection is primary-only.
        Per-agent identity-notes migration (item 8 + Gate 4.5) lands
        all agents' notes (tagged with `agent_id`) into this primary
        identity collection. Read stores are not consulted by
        `identity_get`; they don't have their own identity collections
        opened.
        """
        if self._identity is None:
            self._identity = self._get_client().get_or_create_collection(
                name=COLLECTION_IDENTITY,
                embedding_function=self._get_embedding_fn(),
                metadata={"hnsw:space": "cosine"},
            )
        return self._identity

    def _get_read_memories_collection(self, store_path: Path) -> Any | None:
        """Lazy-open the memories collection on a read store.

        Returns the collection on success, or `None` on failure (with
        WARN-once-per-store-per-process logging). The shared embedding
        function is reused across all stores so cosine similarities
        are comparable in the aggregated result set.

        Per Q2-A: read-store failure is non-fatal — it contributes
        zero hits and is skipped. The caller composes the aggregated
        result from whatever stores succeeded.
        """
        existing = self._read_memories.get(store_path)
        if existing is not None:
            return existing
        try:
            client = self._read_clients.get(store_path)
            if client is None:
                client = self._build_persistent_client(store_path)
                self._read_clients[store_path] = client
            col = client.get_or_create_collection(
                name=COLLECTION_MEMORIES,
                embedding_function=self._get_embedding_fn(),
                metadata={"hnsw:space": "cosine"},
            )
            self._read_memories[store_path] = col
            logger.info(
                "memory.read_store_initialized path=%s", store_path
            )
            return col
        except Exception as exc:
            # WARN once per store per process; debug-log subsequent
            # failures so persistent corruption doesn't flood logs.
            if store_path not in self._warned_unavailable_stores:
                self._warned_unavailable_stores.add(store_path)
                logger.warning(
                    "memory.read_store_unavailable path=%s error=%s: %s "
                    "— skipping this store; aggregated result may be partial",
                    store_path,
                    type(exc).__name__,
                    exc,
                )
            else:
                logger.debug(
                    "memory.read_store_still_unavailable path=%s error=%s: %s",
                    store_path,
                    type(exc).__name__,
                    exc,
                )
            return None

    # ---- Public API ---------------------------------------------------

    def search(
        self,
        query: str,
        *,
        tag_filter: str | None = None,
        importance_filter: str | None = None,
        limit: int = 10,
    ) -> list[MemoryHit]:
        """Semantic search by meaning. Returns ranked hits.

        Args:
            query: Natural-language query.
            tag_filter: If set, only return hits whose `tags` tuple
                contains this exact tag. Post-hoc Python filter (see
                "Tag-filter semantics" note below).
            importance_filter: Only match memories with this exact
                importance level. Applied as a ChromaDB metadata
                filter at query time.
            limit: Max hits to return.

        Returns:
            List of MemoryHit, best-similarity first. Empty list if
            the store has no entries or if the tag filter excludes
            all hits.

        Raises:
            MemoryUnavailableError: on backing-store failure.

        **Tag-filter semantics (divergence from moltbot):** moltbot
        used ChromaDB's `$contains` metadata operator to match tags
        by substring over the JSON-encoded list (`'["tool-selection"]'`).
        ChromaDB 1.x removed `$contains` for metadata (it is now a
        document-content operator only), so N5 fetches a candidate
        set without tag filtering and applies exact-tag-membership
        filtering in Python. Two consequences:

        1. Storage stays wire-compatible with moltbot — tags are
           still JSON-encoded lists in the `tags` metadata field.
        2. Filter semantics are stricter: `tag_filter="tool"` will
           NOT match a memory tagged `["tool-selection"]` the way
           moltbot's substring match would have. Exact membership
           only. This is intentional — substring matches were a
           latent source of false positives in moltbot's behavior.

        To offset the post-hoc filter's cost at larger scales, the
        candidate set is sized at `limit * 5` so the filtered
        result can still usually reach `limit`. Over-fetch factor
        may need tuning if tag-filtered queries regularly come back
        short.
        """
        try:
            # Only importance_filter survives as a ChromaDB where
            # clause; tag_filter is post-hoc (see docstring).
            where_filter = self._build_where_filter(
                tag_filter=None, importance_filter=importance_filter
            )
            # Over-fetch factor for tag-filtered queries — applied
            # per-store so each store contributes enough candidates
            # for the post-hoc filter to still hit `limit` after merge.
            overfetch = limit * 5 if tag_filter else limit

            aggregated: list[MemoryHit] = []

            # Primary store — failure raises MemoryUnavailableError
            # (preserves the no-recommendation contract in
            # RecommendationService._lookup_memory).
            primary_col = self._get_memories_collection()
            primary_total = primary_col.count()
            if primary_total > 0:
                aggregated.extend(
                    _query_store(
                        col=primary_col,
                        store_path=self.memory_dir,
                        query=query,
                        n_results=min(overfetch, primary_total),
                        where_filter=where_filter,
                    )
                )

            # Read stores — each WARN-skips on failure (per Q2-A).
            for store_path in self.read_stores:
                col = self._get_read_memories_collection(store_path)
                if col is None:
                    continue
                try:
                    store_total = col.count()
                    if store_total == 0:
                        continue
                    aggregated.extend(
                        _query_store(
                            col=col,
                            store_path=store_path,
                            query=query,
                            n_results=min(overfetch, store_total),
                            where_filter=where_filter,
                        )
                    )
                except Exception as exc:
                    if store_path not in self._warned_unavailable_stores:
                        self._warned_unavailable_stores.add(store_path)
                        logger.warning(
                            "memory.read_store_query_failed path=%s error=%s: %s "
                            "— skipping this store; aggregated result may be partial",
                            store_path,
                            type(exc).__name__,
                            exc,
                        )
                    else:
                        logger.debug(
                            "memory.read_store_query_still_failing path=%s error=%s: %s",
                            store_path,
                            type(exc).__name__,
                            exc,
                        )

            # Aggregate post-processing: post-hoc tag filter, sort by
            # similarity desc (None last), trim to `limit`. Sorting
            # by similarity across stores is meaningful because all
            # stores share the embedding model (load-bearing
            # assumption documented in the module docstring; verified
            # against the live `~/.moltbot-memory-v2/` audit and
            # inherited by Gate 4.5 for the four configured stores).
            if tag_filter is not None:
                aggregated = [h for h in aggregated if tag_filter in h.tags]
            aggregated.sort(
                key=lambda h: (
                    h.similarity is None,
                    -(h.similarity or 0.0),
                )
            )
            hits = aggregated[:limit]
            logger.debug(
                "memory.search(query=%r, tag=%r, n<=%d, stores=%d): %d hits",
                query,
                tag_filter,
                limit,
                1 + len(self.read_stores),
                len(hits),
            )
            return hits
        except MemoryUnavailableError:
            raise
        except Exception as exc:
            raise MemoryUnavailableError(f"memory.search failed: {exc}") from exc

    def store(
        self,
        text: str,
        *,
        tags: list[str] | None = None,
        source: str | None = None,
        importance: str = "normal",
    ) -> str:
        """Store a memory. Returns the generated memory id.

        Tag serialization matches moltbot: stored as a JSON-encoded
        list in the `tags` metadata field so that ChromaDB's
        `$contains` filter can match by tag substring.

        **Primary-store only** per Stage 1A item 2 Q2-A: writes never
        touch the configured read stores. Each read store continues
        to receive writes exclusively from its own owning agent at
        the OpenClaw layer (per [2026-05-13] D14).

        Raises:
            MemoryUnavailableError: on backing-store failure.
        """
        try:
            col = self._get_memories_collection()
            mem_id = _gen_id(text)
            metadata: dict[str, Any] = {
                # Match moltbot's naive-UTC ISO format for wire-compat
                # on a shared store. The modern timezone-aware call
                # produces the same prefix; stripping tzinfo keeps the
                # trailing `+00:00` off so string comparisons match
                # moltbot-written entries.
                "created_at": datetime.now(timezone.utc)
                .replace(tzinfo=None)
                .isoformat(),
                "source": source or "unknown",
                "importance": importance,
            }
            if tags:
                metadata["tags"] = json.dumps(tags)
            col.add(ids=[mem_id], documents=[text], metadatas=[metadata])
            logger.debug(
                "memory.store(id=%s, tags=%r, importance=%s): ok",
                mem_id,
                tags,
                importance,
            )
            return mem_id
        except Exception as exc:
            raise MemoryUnavailableError(f"memory.store failed: {exc}") from exc

    def list(
        self,
        *,
        tag_filter: str | None = None,
        limit: int = 20,
    ) -> list[MemoryHit]:
        """List recent memories (not a semantic search).

        Aggregates across primary + configured read stores per
        Stage 1A item 2. `tag_filter` uses exact-tag-membership
        post-hoc filtering (see `search` docstring for the rationale).
        The over-fetch factor is 5× applied per-store for the same
        reason.

        **`created_at` cross-store comparability:** Concierge writes
        `datetime.now(UTC).replace(tzinfo=None).isoformat()` (matches
        moltbot's naive-UTC ISO format for wire-compat per the
        `store()` docstring). Sorting the merged list lexically by
        `created_at` reproduces chronological order as long as every
        contributing store uses the same naive-UTC ISO format.
        Entries with an `"unknown"` `created_at` (no metadata at
        write time) sort to the end because `"u"` > any digit prefix
        — acceptable degradation.

        Returns:
            MemoryHit list with `similarity=None`, sorted by
            `created_at` descending. Empty list if no store has
            entries or the tag filter excludes all entries.

        Raises:
            MemoryUnavailableError: on primary backing-store failure.
            Per-read-store failure WARN-skips (Q2-A).
        """
        try:
            overfetch = limit * 5 if tag_filter else limit
            aggregated: list[MemoryHit] = []

            # Primary store — failure raises.
            primary_col = self._get_memories_collection()
            primary_total = primary_col.count()
            if primary_total > 0:
                results = primary_col.get(limit=min(overfetch, primary_total))
                aggregated.extend(
                    _get_results_to_hits(results, source_store=self.memory_dir)
                )

            # Read stores — failure WARN-skips.
            for store_path in self.read_stores:
                col = self._get_read_memories_collection(store_path)
                if col is None:
                    continue
                try:
                    store_total = col.count()
                    if store_total == 0:
                        continue
                    results = col.get(limit=min(overfetch, store_total))
                    aggregated.extend(
                        _get_results_to_hits(results, source_store=store_path)
                    )
                except Exception as exc:
                    if store_path not in self._warned_unavailable_stores:
                        self._warned_unavailable_stores.add(store_path)
                        logger.warning(
                            "memory.list.read_store_failed path=%s error=%s: %s "
                            "— skipping",
                            store_path,
                            type(exc).__name__,
                            exc,
                        )
                    else:
                        logger.debug(
                            "memory.list.read_store_still_failing path=%s error=%s: %s",
                            store_path,
                            type(exc).__name__,
                            exc,
                        )

            if tag_filter is not None:
                aggregated = [h for h in aggregated if tag_filter in h.tags]
            aggregated.sort(key=lambda h: h.created_at, reverse=True)
            return aggregated[:limit]
        except MemoryUnavailableError:
            raise
        except Exception as exc:
            raise MemoryUnavailableError(f"memory.list failed: {exc}") from exc

    def stats(self) -> dict[str, Any]:
        """Return store statistics. Raises MemoryUnavailableError on
        primary-store failure (e.g. dir unreadable).

        Per Stage 1A item 2 Q5-A: also reports per-read-store
        `{path, total_memories}` entries so Gate 4.5 health checks
        can confirm the four configured stores are reachable. A read
        store that fails init or count contributes an `error` entry
        in place of `total_memories` (and WARN-logs once per process
        per Q2-A); the overall `stats()` call still succeeds.
        """
        try:
            col = self._get_memories_collection()
            read_store_stats: list[dict[str, Any]] = []
            for store_path in self.read_stores:
                rcol = self._get_read_memories_collection(store_path)
                entry: dict[str, Any] = {"path": str(store_path)}
                if rcol is None:
                    entry["error"] = "init_failed"
                else:
                    try:
                        entry["total_memories"] = rcol.count()
                    except Exception as exc:
                        entry["error"] = f"count_failed: {type(exc).__name__}"
                read_store_stats.append(entry)
            return {
                "total_memories": col.count(),
                "memory_dir": str(self.memory_dir),
                "embedding_model": self.embedding_model,
                "collection": COLLECTION_MEMORIES,
                "read_stores": read_store_stats,
            }
        except Exception as exc:
            raise MemoryUnavailableError(f"memory.stats failed: {exc}") from exc

    # ---- Identity notes (Fix Day 3 Task 7) ----------------------------

    def identity_get(self, *, key: str = IDENTITY_DEFAULT_KEY) -> str:
        """Return the stored identity note for `key`, or "" if none.

        Identity notes are a compact running summary of operator tool
        preferences — injected into the recommend prompt between the
        adapter preamble and X3 (DECISIONS [2026-04-23] + Fix Day 3
        Fork 4). Empty string on first call before `identity_set`
        lets callers fold an unset identity into an empty-block render
        without a distinct "no identity" sentinel.

        Raises:
            MemoryUnavailableError: on backing-store failure.
        """
        try:
            col = self._get_identity_collection()
            result = col.get(ids=[key])
            docs = result.get("documents") or []
            if not docs:
                return ""
            return docs[0] or ""
        except Exception as exc:
            raise MemoryUnavailableError(
                f"memory.identity_get(key={key!r}) failed: {exc}"
            ) from exc

    def identity_set(
        self,
        text: str,
        *,
        key: str = IDENTITY_DEFAULT_KEY,
        agent_id: str | None = None,
        extra_metadata: dict[str, str] | None = None,
    ) -> None:
        """Upsert the identity note for `key`.

        ChromaDB does not have a native upsert — this delete-then-add
        pattern guarantees the row has the current text even across
        repeated calls. Delete-before-add is safe when the id is
        absent (ChromaDB returns silently).

        `agent_id` (Stage 1A item 8 / D6): when given, stamped onto the
        row's metadata so per-agent identity entries are filterable by
        `identity_get_agent`. The default-keyed operator tool-prefs
        note (`core/identity.py`) passes no `agent_id` — it stays
        unscoped, exactly as before. `extra_metadata` (item 8) carries
        the migration's `source` / `entry` provenance fields; any
        small string→string map is accepted. Both params default to
        the pre-item-8 behavior (no extra metadata), so existing
        callers are unaffected.

        Raises:
            MemoryUnavailableError: on backing-store failure.
        """
        try:
            col = self._get_identity_collection()
            # ChromaDB's delete is idempotent on missing ids; no
            # exists-check needed.
            col.delete(ids=[key])
            metadata: dict[str, Any] = {
                "created_at": datetime.now(timezone.utc)
                .replace(tzinfo=None)
                .isoformat(),
                "key": key,
            }
            if agent_id is not None:
                metadata["agent_id"] = agent_id
            if extra_metadata:
                metadata.update(extra_metadata)
            col.add(ids=[key], documents=[text], metadatas=[metadata])
            logger.debug(
                "memory.identity_set(key=%s, agent_id=%s, len=%d): ok",
                key, agent_id, len(text),
            )
        except Exception as exc:
            raise MemoryUnavailableError(
                f"memory.identity_set(key={key!r}) failed: {exc}"
            ) from exc

    def identity_get_agent(self, agent_id: str) -> str:
        """Return the aggregated identity note(s) for `agent_id`, or "".

        Reads every identity-collection entry whose `agent_id`
        metadata matches, sorts by document id for a deterministic
        ordering, and joins the documents with a blank line. Per-agent
        identity entries are populated by the Stage 1A item 8
        migration (`scripts/migrate_identity_notes.py`) — an agent may
        own several (Alfred has four: workspace IDENTITY.md plus the
        `role` / `owner` / `rules` notes), so aggregation rather than
        a single keyed `get` is the right read shape (D4).

        This does NOT consult `key="default"`: the default-keyed
        operator tool-preferences summary carries no `agent_id`
        metadata, so it never matches the filter. No-arg
        `identity_get()` remains the surface for that note and is
        unaffected by item 8 (Finding 3 invariant).

        Raises:
            MemoryUnavailableError: on backing-store failure.
        """
        try:
            col = self._get_identity_collection()
            result = col.get(where={"agent_id": agent_id})
            ids = result.get("ids") or []
            docs = result.get("documents") or []
            if not ids:
                return ""
            paired = sorted(zip(ids, docs), key=lambda pair: pair[0])
            return "\n\n".join(doc or "" for _, doc in paired)
        except Exception as exc:
            raise MemoryUnavailableError(
                f"memory.identity_get_agent(agent_id={agent_id!r}) failed: {exc}"
            ) from exc

    # ---- Internal helpers ---------------------------------------------

    @staticmethod
    def _build_where_filter(
        *, tag_filter: str | None = None, importance_filter: str | None = None
    ) -> dict[str, Any] | None:
        """Build a ChromaDB `where` clause for metadata filtering.

        Only `importance_filter` is supported as a native ChromaDB
        filter; `tag_filter` parameter is accepted for call-site
        symmetry but always applied post-hoc (see `search` docstring
        for the modern-ChromaDB rationale). Callers pass
        `tag_filter=None` here and handle tag filtering in Python.
        """
        conditions: list[dict[str, Any]] = []
        if tag_filter is not None:
            # Preserved for future reactivation if a custom filter
            # strategy becomes viable. Current path: callers filter
            # tags post-hoc.
            conditions.append({"tags": tag_filter})
        if importance_filter is not None:
            conditions.append({"importance": importance_filter})
        if len(conditions) == 0:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}


# ---- Module-level helpers -------------------------------------------------


def _gen_id(text: str) -> str:
    """Short deterministic-ish ID; `mem_` prefix matches moltbot for
    cross-read compatibility when the store is shared.
    """
    digest = hashlib.md5(f"{text}{time.time()}".encode()).hexdigest()[:12]
    return f"mem_{digest}"


def _parse_tags(meta: dict[str, Any]) -> tuple[str, ...]:
    raw = meta.get("tags")
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(str(t) for t in parsed)


def _dedupe_read_stores(
    *, primary: Path, read_stores: list[Path]
) -> list[Path]:
    """Drop duplicates and any path equal to the primary memory_dir.

    Both deductions matter because aggregation otherwise double-counts:
    a read store equal to primary would surface every primary hit twice,
    and two duplicate read-store entries would query the same store
    twice. Order of remaining entries preserved from the input.

    Comparison uses `Path` equality which compares the raw string form;
    callers that want filesystem-level identity (resolved symlinks,
    case-insensitive filesystems) should `.resolve()` upstream. The
    Gate 4.5 config supplies absolute, distinct paths so the simple
    comparison is sufficient.
    """
    seen: set[Path] = {primary}
    deduped: list[Path] = []
    for p in read_stores:
        if p in seen:
            continue
        seen.add(p)
        deduped.append(p)
    return deduped


def _query_store(
    *,
    col: Any,
    store_path: Path,
    query: str,
    n_results: int,
    where_filter: dict[str, Any] | None,
) -> list[MemoryHit]:
    """Issue one ChromaDB `query` against `col` and parse the result
    into `MemoryHit`s tagged with `source_store=store_path`. The
    caller-side per-store try/except wraps this so a store-level
    failure WARN-skips without aborting the whole `search` call.
    """
    kwargs: dict[str, Any] = {
        "query_texts": [query],
        "n_results": n_results,
    }
    if where_filter:
        kwargs["where"] = where_filter
    results = col.query(**kwargs)
    return _query_results_to_hits(results, source_store=store_path)


def _query_results_to_hits(
    results: dict[str, Any], *, source_store: Path | None = None
) -> list[MemoryHit]:
    """Parse a ChromaDB `query` result shape (nested lists, one per
    query text) into MemoryHit objects. We always issue exactly one
    query text, so we read the [0] nested lists.

    `source_store` (Stage 1A item 2) is stamped onto every produced
    hit so downstream code (item 3's agent_id filtering, Gate 4.5
    debug surfaces) can tell which store a hit originated from.
    Defaults to `None` to preserve the prior call signature for any
    consumer that constructs results without a store binding.
    """
    hits: list[MemoryHit] = []
    ids = (results or {}).get("ids") or []
    if not ids or not ids[0]:
        return hits
    id_row = ids[0]
    docs = (results.get("documents") or [[]])[0]
    metas = (results.get("metadatas") or [[]])[0]
    dists = (results.get("distances") or [[]])[0]
    for i, mem_id in enumerate(id_row):
        doc = docs[i] if i < len(docs) else ""
        meta = metas[i] if i < len(metas) else {}
        dist = dists[i] if i < len(dists) else None
        similarity = round(1 - dist, 3) if dist is not None else None
        hits.append(
            MemoryHit(
                id=mem_id,
                text=doc,
                similarity=similarity,
                tags=_parse_tags(meta),
                importance=meta.get("importance", "normal"),
                source=meta.get("source", "unknown"),
                created_at=meta.get("created_at", "unknown"),
                source_store=source_store,
            )
        )
    return hits


def _get_results_to_hits(
    results: dict[str, Any], *, source_store: Path | None = None
) -> list[MemoryHit]:
    """Parse a ChromaDB `get` result shape (flat lists, not nested)
    into MemoryHit objects. `similarity` is None because `get` is
    not a semantic query.

    `source_store` (Stage 1A item 2) stamps per-hit provenance; see
    `_query_results_to_hits` for the rationale.
    """
    hits: list[MemoryHit] = []
    ids = (results or {}).get("ids") or []
    if not ids:
        return hits
    docs = results.get("documents") or []
    metas = results.get("metadatas") or []
    for i, mem_id in enumerate(ids):
        doc = docs[i] if i < len(docs) else ""
        meta = metas[i] if i < len(metas) else {}
        hits.append(
            MemoryHit(
                id=mem_id,
                text=doc,
                similarity=None,
                tags=_parse_tags(meta),
                importance=meta.get("importance", "normal"),
                source=meta.get("source", "unknown"),
                created_at=meta.get("created_at", "unknown"),
                source_store=source_store,
            )
        )
    return hits


# ---- FastAPI dependency --------------------------------------------------


def make_memory_client(settings: Settings | None = None) -> MemoryClient:
    """Construct a MemoryClient from settings (or defaults). Does
    not touch ChromaDB; lazy init on first operation.

    `memory_read_stores` plumbs through to multi-store read
    aggregation per Stage 1A item 2 / Gate 4.5. Default is an empty
    list (single-store behavior preserved).
    """
    s = settings if settings is not None else get_settings()
    return MemoryClient(
        memory_dir=s.memory_dir,
        embedding_model=s.memory_embedding_model,
        read_stores=list(s.memory_read_stores),
    )


@lru_cache
def get_memory_client() -> MemoryClient:
    """FastAPI dependency. Process-wide singleton via `lru_cache` —
    one ChromaDB PersistentClient per process. Respects settings at
    first call; subsequent settings changes require
    `get_memory_client.cache_clear()`.
    """
    return make_memory_client()
