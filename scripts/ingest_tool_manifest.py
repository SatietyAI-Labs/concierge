"""CLI entry point for the TOOL-MANIFEST.md → SQLite ingest.

Stage 1A item 7. Sister to:
  - `python -m core.ingest.catalog` (TOOL-CATALOG.md, table format)
  - `python -m core.ingest.skills`  (SKILL.md frontmatter walk)

Usage
-----

  python scripts/ingest_tool_manifest.py [SOURCE_PATH]

`SOURCE_PATH` defaults to `~/.agent-skills/shared/TOOL-MANIFEST.md`
(the live manifest under the fleet's agent-skills tree). Pass a
different path to ingest against a fixture or a copy.

Output
------

Per-run stats: rows created / updated, sections parsed vs skipped,
worker cross-references resolved vs skipped (worker-only references
with no Alfred H3 — see `core/ingest/manifest.py` for the decision
rationale), and any errors.

Idempotency
-----------

Re-running against the same source is safe. Descriptive fields refresh
from source; operator-managed lifecycle fields (lifecycle_state once
moved away from `discovered`; `succeeded_by` always) are preserved.
"""
from __future__ import annotations

import sys
from pathlib import Path

from core.config import get_settings
from core.db.session import get_session_factory
from core.ingest.manifest import ingest_manifest


def main() -> int:
    settings = get_settings()
    if len(sys.argv) > 1:
        source = Path(sys.argv[1]).expanduser()
    else:
        # Default to the live manifest under the fleet's agent-skills tree.
        source = Path("~/.agent-skills/shared/TOOL-MANIFEST.md").expanduser()

    if not source.exists():
        print(f"ERROR: source file not found: {source}", file=sys.stderr)
        return 2

    session = get_session_factory()()
    try:
        stats = ingest_manifest(source, session)
    finally:
        session.close()

    print(f"Ingested manifest from: {source}")
    print(
        f"  Sections: {stats.sections_parsed} parsed / "
        f"{stats.sections_skipped} skipped (passthrough)"
    )
    print(
        f"  Tools: +{stats.tools_created} created, "
        f"~{stats.tools_updated} updated"
    )
    print(
        f"  Worker cross-refs: {stats.cross_references_resolved} resolved / "
        f"{stats.cross_references_skipped} skipped (worker-only — operator "
        f"should add an Alfred H3)"
    )
    if stats.errors:
        print(f"  Errors ({len(stats.errors)}):", file=sys.stderr)
        for source_ref, err in stats.errors:
            print(f"    {source_ref}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
