"""Tool-lifecycle policy constants extracted from the tool-lifecycle skill.

**First extract in the `python-constants` class.** Sibling extract to
X7-A in `core/prompts/tool_lifecycle.py`. Where prompt-fragment
extracts (X3/X4/X6/X7-A) capture prose that Opus 4.7 reads directly
at compose time, a python-constants extract captures the structured
data the source prose describes — for consumption by Python code
(lifecycle scanners, promotion/demotion endpoints, weekly-review
cron integration), not by Opus.

This module holds **policy constants** (thresholds, status vocabularies,
transition rules). The write-side of the lifecycle store — file/DB
operations, request parsing, status transitions — lives under
`core/lifecycle_store/` (N7). The rename from `core/lifecycle.py` to
`core/lifecycle_policy.py` was made per DECISIONS [2026-04-22 08:34]
to disambiguate policy-from-operations at import-read time.

Distinctions from the prompt-fragment class:

| Dimension | prompt-fragment (X3/X4/X6/X7-A) | python-constants (X7-B) |
|---|---|---|
| Scope | whole-body (X3/X4/X6) or selective (X7-A) | selective by definition |
| Naming | verbose `_PROTOCOL__FROM_*` for grep-drift | plain semantic names |
| Fidelity | verbatim markdown body/section | values re-authored from prose |
| Drift check | byte-for-byte vs source slice | source-cross-check: assert source prose still contains the literal numeric phrases / value lists the constants re-author |
| Consumer | Opus 4.7 system prompt | Python code (lifecycle scanner, endpoints, cron) |
| Module home | `core/prompts/` | application module (`core/lifecycle_policy.py` for this one) |

Future python-constants extracts cite this module as precedent —
examples expected include X11 cron thresholds (if not ultimately
handled by config), memory-tag schemas for other agents, etc.

Governing decision: DECISIONS `[2026-04-21 05:50]` §"Affects" line,
where row #7 is flagged as a partial hybrid; classification §C.5.3
elaborates.

Source
------
Path (repo-relative, via symlink):
    _legacy/openclaw-workspace/skills/tool-lifecycle/SKILL.md
Absolute source at extract time:
    /home/satiety/.openclaw/workspace/skills/tool-lifecycle/SKILL.md
Source SHA-256:
    79128223564dcb63bc4c50763eefc6545e6151c7ccfb56a34d6a5adf895299d4
Source mtime:
    2026-04-13 21:09:25 -0700
Source bytes:
    7158

Extract
-------
Extracted:
    2026-04-21 16:50 PDT (SESSION-2026-04-21-02, item X7-B)
Sections extracted (non-contiguous, each re-authored as a Python
value):
    - `## Memory tagging convention` / "Storing a tool-selection
      memory" — tag literal, content field list, status values list
    - `## Memory tagging convention` / "Updating memory entries" —
      four explicit status transitions
    - `## Promotion logic` / "Promotion criteria" — two numeric
      thresholds
    - `## Demotion logic` / "Demotion criteria" — one numeric
      threshold
    - `## Weekly review` / "What to check" — one numeric threshold
      (stale-pending)

Drift model
-----------
Manual re-author per DECISIONS `[2026-04-21 05:50]` mitigation #4.
The source-cross-check test (`tests/test_lifecycle.py`) asserts that
specific literal phrases still appear in the source file — e.g.,
"Used 5+ times in the last 30 days", "Not used in 90+ days", "older
than 7 days", each of the six status-value names. If the source prose
is updated to change any threshold or rename a status value, the
cross-check fails and forces a joint re-sync of both this module and
the prompt fragment (X7-A `core/prompts/tool_lifecycle.py`) — since
the prose-form thresholds there reference the same numbers.

See `core/prompts/SKILL_FRAGMENT_SYNC_LOG.md` for the companion
extract record and sync history.
"""

TOOL_SELECTION_MEMORY_TAG: str = "tool-selection"
"""The memory-entry tag under which tool-selection decisions are
stored (and later searched). Source: "Every tool decision gets a
memory entry..." — `## Memory tagging convention` / "Storing a
tool-selection memory".
"""

TOOL_SELECTION_STATUS_VALUES: frozenset[str] = frozenset(
    {"pending", "approved", "installed", "denied", "failed", "removed"}
)
"""The six allowed STATUS values inside a tool-selection memory
entry's content field. Source: `## Memory tagging convention` /
"Status values". Order-free; order of enumeration in source is
informational, not semantic.
"""

TOOL_SELECTION_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"approved", "denied"}),
    "approved": frozenset({"installed"}),
    "installed": frozenset({"removed"}),
}
"""Valid status transitions. Source lists exactly four transitions
under `## Memory tagging convention` / "Updating memory entries":

    pending -> approved     (Request approved)
    approved -> installed   (Tool installed)
    pending -> denied       (Tool denied)
    installed -> removed    (Tool removed)

Status values `failed` and `denied` have no outgoing transitions in
the source; they (plus `removed`) are effectively terminal under the
explicitly-listed rules. The source does NOT specify how an entry
reaches `failed`; callers that need to record install/verify failure
will need to re-read the source and either extend this dict (with a
re-sync note) or handle `failed` as a settable terminal state
bypassing the transition table.
"""

TOOL_SELECTION_CONTENT_FIELDS: tuple[str, ...] = (
    "TOOL",
    "PATTERN",
    "STATUS",
    "AGENT",
    "DATE",
    "NOTES",
)
"""Ordered field names inside a tool-selection memory entry's
content string. Source: `## Memory tagging convention` / "Storing a
tool-selection memory" content template:

    TOOL: <name> | PATTERN: <pattern> | STATUS: <status> | AGENT: <who> | DATE: <YYYY-MM-DD> | NOTES: <brief>

Order matters here: it is the reading order of the pipe-delimited
content and the expected serialization order for new entries.
"""

PROMOTION_MIN_USES: int = 5
"""Minimum use count within the promotion window for a tool to be
promotion-eligible. Source: `## Promotion logic` / "Promotion
criteria" — "Used 5+ times in the last 30 days".
"""

PROMOTION_WINDOW_DAYS: int = 30
"""Promotion measurement window in days. Source: same line as
`PROMOTION_MIN_USES` — "...in the last 30 days".
"""

DEMOTION_INACTIVITY_DAYS: int = 90
"""Minimum inactivity window in days for a tool to be
demotion-eligible. Source: `## Demotion logic` / "Demotion criteria"
— "Not used in 90+ days".
"""

STALE_PENDING_DAYS: int = 7
"""Threshold in days for a pending request to count as stale for
weekly-review flagging. Source: `## Weekly review` / "What to check"
item 3 — "Files in `pending/` older than 7 days".
"""
