"""CLI entry point for the SQLite catalog → TOOL-MANIFEST.md export.

Stage 1B Gate 2. Inverse of `scripts/ingest_tool_manifest.py`: that
script reads the live manifest into the SQLite catalog; this one renders
the catalog back to canonical manifest markdown, for the round-trip
fidelity verification Gate 2 calls for.

Usage
-----

  python scripts/export_tool_manifest.py [OUTPUT_PATH]

Writes the rendered markdown to `OUTPUT_PATH` if given, else to stdout.
A one-line row count is written to stderr either way.

Scope
-----

Only `Tool` rows with `is_in_manifest=True` are exported — the rows that
originate from a manifest ingest. The output covers the tool-bearing
sections only (ALFRED / AD-HOC / BUILDABLE); the worker cross-reference
section and the manifest's passthrough H2s carry no DB rows and are not
reconstructed. A raw-text diff of the export against an original
manifest is therefore expected to be non-clean; round-trip fidelity is
asserted over the tool rows via `core.ingest.manifest.equivalent`. See
`core/ingest/manifest.export_manifest` for the full round-trip contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

from core.db.models import Tool
from core.db.session import get_session_factory
from core.ingest.manifest import export_manifest


def main() -> int:
    session = get_session_factory()()
    try:
        markdown = export_manifest(session)
        row_count = (
            session.query(Tool).filter_by(is_in_manifest=True).count()
        )
    finally:
        session.close()

    if len(sys.argv) > 1:
        out_path = Path(sys.argv[1]).expanduser()
        out_path.write_text(markdown, encoding="utf-8")
        print(
            f"Exported {row_count} tool rows to: {out_path}", file=sys.stderr
        )
    else:
        sys.stdout.write(markdown)
        print(f"Exported {row_count} tool rows.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
