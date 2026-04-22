"""Lifecycle-store operations package (N7).

Operational surface for the three-folder tool-request lifecycle
(`pending/ → resolved/ → archived/`). This is the **write side** of
the lifecycle: atomic file writes, status-line in-place updates,
folder-agnostic filename lookup, DB/filesystem reconciliation, and
transition validation against the file-side status vocabulary.

Policy constants (status values, transition tables, thresholds) live
separately at `core.lifecycle_policy` per DECISIONS
`[2026-04-22 08:34]`. The policy-vs-store split is the reason the
older module was renamed from `core/lifecycle.py` — "policy" and
"store" disambiguate at import-line read; "lifecycle" and
"lifecycle_store" would read as layered versions of the same thing.

Parser + export-to-markdown primitives live at
`core.ingest.tool_requests` (shipped with N3). `lifecycle_store`
imports them rather than re-implementing; an ownership-move
(parser → `lifecycle_store/parser.py`) is a post-hackathon refactor
concern, not a Day 2 one.

Scope boundary — what N7 does NOT do
------------------------------------

N7 is **lifecycle visibility + state transitions**, not lifecycle
**action**. Approving a request updates the status line and the DB
row; it does **not** install the tool. The approve-triggers-install
wiring (via X13's Python install module) is explicitly deferred —
Day 3 at the earliest, Cut 2 deferrable. An operator reading the 48h
shakedown logs must be able to distinguish "Concierge surfaced a
state change" from "Concierge executed an installation"; N7 emits
only the former.
"""

from core.lifecycle_store.schema import (
    ListedRequest,
    LifecycleStats,
    NewRequestDraft,
    StatusChange,
)
from core.lifecycle_store.transitions import (
    InvalidTransitionError,
    assert_valid_transition,
)

__all__ = [
    "InvalidTransitionError",
    "ListedRequest",
    "LifecycleStats",
    "NewRequestDraft",
    "StatusChange",
    "assert_valid_transition",
]
