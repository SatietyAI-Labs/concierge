"""CLI entry point for the identity-notes migration.

Stage 1A item 8. Thin shim over
`core.identity_migration.migrate_identity_notes` — all logic lives in
`core/identity_migration.py` (mirrors `scripts/ingest_tool_manifest.py`
over `core/ingest/manifest.py`).

Usage
-----

  python scripts/migrate_identity_notes.py

Reads per-agent identity from where it lives (items-8 D2):
  - 5 workspace IDENTITY.md files via `core.agent_config.AGENT_ROOTS`
  - 3 unified ChromaDB identity entries at `~/.moltbot-memory-v2/`

and upserts 8 entries into Concierge's own identity collection,
scoped by `agent_id` metadata. Both reads are read-only; the only
write target is Concierge's identity collection.

This is the script the master plan v1.1 §III.3 Gate 4.5 step 3 runs.
In Stage 1A it ships built + tested (against `tmp_path` fixtures);
the live run against the fleet's real identity content happens at
Gate 4.5.

Idempotency
-----------

Rerun-safe — composite keys (`agent:<id>:<slug>`) make every upsert
deterministic; a second run leaves the same 8 entries, never 16. The
operator tool-preferences note at `key="default"` is never touched.
"""
from __future__ import annotations

import sys

from core.identity_migration import migrate_identity_notes
from core.memory import make_memory_client


def main() -> int:
    client = make_memory_client()
    result = migrate_identity_notes(memory_client=client)

    print(
        f"Identity-notes migration: {result.entries_written} "
        f"entry(ies) upserted into Concierge's identity collection"
    )
    for key in result.keys:
        print(f"  + {key}")

    if result.warnings:
        print(f"\n{len(result.warnings)} warning(s):", file=sys.stderr)
        for warning in result.warnings:
            print(f"  ! {warning}", file=sys.stderr)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
