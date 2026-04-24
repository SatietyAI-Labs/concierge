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

## Graceful degradation

All public methods raise `MemoryUnavailableError` on backing-store
failure (ChromaDB init error, embedding-model load failure, query
error). N6 `POST /recommend` is expected to catch this narrow
exception and serve a recommendation without memory context,
annotating the response accordingly. Hard Python errors propagate;
only the "memory is unavailable for this operation" case is a
graceful-degradation surface.

## Lazy initialization

ChromaDB client and embedding function both lazy-init on first use.
Importing `core.memory` is cheap; first call to `search`/`store`/
`list`/`stats` pays the ~300MB / 5-30s sentence-transformers load.
Tests that only verify import resolution stay fast.

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
    """

    id: str
    text: str
    similarity: float | None
    tags: tuple[str, ...]
    importance: str
    source: str
    created_at: str


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
    ) -> None:
        self.memory_dir = memory_dir
        self.embedding_model = embedding_model
        self._client: Any = None
        self._memories: Any = None
        self._identity: Any = None
        self._embedding_fn: Any = None
        logger.debug(
            "MemoryClient configured: dir=%s model=%s (lazy init)",
            memory_dir,
            embedding_model,
        )

    # ---- Lazy init helpers --------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                self.memory_dir.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=str(self.memory_dir),
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                logger.info("ChromaDB client initialized at %s", self.memory_dir)
            except Exception as exc:
                raise MemoryUnavailableError(
                    f"ChromaDB init failed at {self.memory_dir}: {exc}"
                ) from exc
        return self._client

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
        """
        if self._identity is None:
            self._identity = self._get_client().get_or_create_collection(
                name=COLLECTION_IDENTITY,
                embedding_function=self._get_embedding_fn(),
                metadata={"hnsw:space": "cosine"},
            )
        return self._identity

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
            col = self._get_memories_collection()
            total = col.count()
            if total == 0:
                logger.debug("memory.search(query=%r): store empty", query)
                return []

            # Only importance_filter survives as a ChromaDB where
            # clause; tag_filter is post-hoc (see docstring).
            where_filter = self._build_where_filter(
                tag_filter=None, importance_filter=importance_filter
            )
            # Over-fetch when tag_filter is set so post-hoc filtering
            # can still reach `limit`.
            n_results = min(limit * 5 if tag_filter else limit, total)
            kwargs: dict[str, Any] = {
                "query_texts": [query],
                "n_results": n_results,
            }
            if where_filter:
                kwargs["where"] = where_filter

            results = col.query(**kwargs)
            hits = _query_results_to_hits(results)
            if tag_filter is not None:
                hits = [h for h in hits if tag_filter in h.tags]
            hits = hits[:limit]
            logger.debug(
                "memory.search(query=%r, tag=%r, n<=%d): %d hits",
                query,
                tag_filter,
                limit,
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

        `tag_filter` uses exact-tag-membership post-hoc filtering
        (see `search` docstring for the rationale). The over-fetch
        factor is 5× for the same reason.

        Returns:
            MemoryHit list with `similarity=None`, sorted by
            `created_at` descending. Empty list if the store has no
            entries or the tag filter excludes all entries.

        Raises:
            MemoryUnavailableError: on backing-store failure.
        """
        try:
            col = self._get_memories_collection()
            total = col.count()
            if total == 0:
                return []
            n_results = min(limit * 5 if tag_filter else limit, total)
            results = col.get(limit=n_results)
            hits = _get_results_to_hits(results)
            if tag_filter is not None:
                hits = [h for h in hits if tag_filter in h.tags]
            hits.sort(key=lambda h: h.created_at, reverse=True)
            return hits[:limit]
        except Exception as exc:
            raise MemoryUnavailableError(f"memory.list failed: {exc}") from exc

    def stats(self) -> dict[str, Any]:
        """Return store statistics. Raises MemoryUnavailableError on
        failure (e.g. dir unreadable).
        """
        try:
            col = self._get_memories_collection()
            return {
                "total_memories": col.count(),
                "memory_dir": str(self.memory_dir),
                "embedding_model": self.embedding_model,
                "collection": COLLECTION_MEMORIES,
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
        self, text: str, *, key: str = IDENTITY_DEFAULT_KEY
    ) -> None:
        """Upsert the identity note for `key`.

        ChromaDB does not have a native upsert — this delete-then-add
        pattern guarantees the row has the current text even across
        repeated calls. Delete-before-add is safe when the id is
        absent (ChromaDB returns silently).

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
            col.add(ids=[key], documents=[text], metadatas=[metadata])
            logger.debug(
                "memory.identity_set(key=%s, len=%d): ok", key, len(text)
            )
        except Exception as exc:
            raise MemoryUnavailableError(
                f"memory.identity_set(key={key!r}) failed: {exc}"
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


def _query_results_to_hits(results: dict[str, Any]) -> list[MemoryHit]:
    """Parse a ChromaDB `query` result shape (nested lists, one per
    query text) into MemoryHit objects. We always issue exactly one
    query text, so we read the [0] nested lists.
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
            )
        )
    return hits


def _get_results_to_hits(results: dict[str, Any]) -> list[MemoryHit]:
    """Parse a ChromaDB `get` result shape (flat lists, not nested)
    into MemoryHit objects. `similarity` is None because `get` is
    not a semantic query.
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
            )
        )
    return hits


# ---- FastAPI dependency --------------------------------------------------


def make_memory_client(settings: Settings | None = None) -> MemoryClient:
    """Construct a MemoryClient from settings (or defaults). Does
    not touch ChromaDB; lazy init on first operation.
    """
    s = settings if settings is not None else get_settings()
    return MemoryClient(
        memory_dir=s.memory_dir,
        embedding_model=s.memory_embedding_model,
    )


@lru_cache
def get_memory_client() -> MemoryClient:
    """FastAPI dependency. Process-wide singleton via `lru_cache` —
    one ChromaDB PersistentClient per process. Respects settings at
    first call; subsequent settings changes require
    `get_memory_client.cache_clear()`.
    """
    return make_memory_client()
