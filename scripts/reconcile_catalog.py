"""CLI entry point for the one-shot catalog reconciliation.

Stage 1B reconciliation slice, Phase B. Sister to
`scripts/ingest_tool_manifest.py` — a run-once, manual operator script.

Usage
-----

  python scripts/reconcile_catalog.py [--dry-run]

Runs against the configured Concierge database (`get_settings()` —
`CONCIERGE_DATABASE_PATH`). The reconciliation policy itself lives in
`core/catalog_reconcile.py`; this is a thin CLI wrapper.

`--dry-run` applies the reconciliation in-session, prints the summary,
then ROLLS BACK — nothing is written. Use it to preview the effect
against the live catalog before the real run (the snapshot → preview →
apply discipline; CLAUDE.md §3).

Output
------

One line per operation — outcome, kind, slug, detail — then a count
summary. Exit 0 when every operation applied cleanly or was already
satisfied; exit 1 when any slug was missing or a transition errored
(in which case the run is rolled back — reconciliation is
all-or-nothing).

Idempotency
-----------

Safe to re-run. A second run reports every operation `already_satisfied`
and writes nothing — see `core/catalog_reconcile.py`.
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from core.catalog_reconcile import reconcile_catalog
from core.db.session import get_session_factory


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-shot catalog reconciliation (Stage 1B, D40/D79/D77)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apply in-session, print the summary, then roll back — "
        "no DB write.",
    )
    args = parser.parse_args(argv)

    session = get_session_factory()()
    try:
        summary = reconcile_catalog(session)

        print("Catalog reconciliation —")
        for r in summary.results:
            print(f"  [{r.outcome:17s}] {r.kind:10s} {r.slug:28s} {r.detail}")
        print(
            f"  {summary.count('applied')} applied, "
            f"{summary.count('already_satisfied')} already-satisfied, "
            f"{summary.count('skipped_missing')} missing, "
            f"{summary.count('error')} error"
        )

        if args.dry_run:
            session.rollback()
            print("DRY RUN — rolled back; no changes written.")
        elif summary.ok:
            session.commit()
            print("Committed.")
        else:
            session.rollback()
            print(
                "Errors present — rolled back; no changes written. "
                "Inspect the catalog and re-run.",
                file=sys.stderr,
            )
    finally:
        session.close()

    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
