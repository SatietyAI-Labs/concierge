"""Prompt fragment extracted from the tool-lifecycle skill — weekly-review
section only (SELECTIVE extract).

See `core/prompts/tool_awareness.py` for the full conventions —
consumer compose model, OpenClaw coupling treatment, drift model,
Phase 2 target. This module only records the per-fragment facts
and the scoping notes unique to this source.

**First selective extract in the fragment set.** X3/X4/X6 were
whole-body verbatim extracts. X7 is a "partial hybrid" per
classification §C.5.3: promotion/demotion thresholds and the tag
schema become Python constants (see `core/lifecycle_policy.py`); *only*
the weekly-review protocol is the prompt-fragment part. Future
selective extracts cite this module as precedent.

What is NOT in this fragment (deliberately left in `_legacy/` only):
    - Memory-tagging prose: pattern naming guidance, worked
      examples, search interpretation rules, identity notes template
    - Promotion logic prose: request template, "do not promote"
      anti-criteria
    - Demotion logic prose: request template, "demotion is never
      automatic" policy

Those sections are either captured as Python constants in
`core/lifecycle_policy.py` (the structured data) or are OpenClaw-side
agent prose that Concierge does not need to consume.

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
Source bytes (whole file):
    7158
Fragment bytes (weekly-review section):
    862

Extract
-------
Extracted:
    2026-04-21 16:50 PDT (SESSION-2026-04-21-02, item X7-A)
Section extracted:
    `## Weekly review` (inclusive) through end-of-file. Located in
    source at byte offset 6296; runs 862 bytes to byte 7158. Covers
    the scan / what-to-check / review-output / WhatsApp-ping
    protocol that Opus 4.7 will reason through at weekly-review time.
Fidelity:
    VERBATIM of the sliced section. No backslash or triple-quote
    hazards in source; no Python-layer escaping applied. Drift-check
    compares against the section slice (not the whole file) via the
    `_slice_section_by_h2` helper in `tests/test_prompts.py`.

OpenClaw coupling (this fragment's specifics)
---------------------------------------------
Preserved verbatim in the constant:

- Housekeeping log path: `~/.satiety-pipeline/outbox/housekeeping.log`
- WhatsApp notification at the tail ("ping the operator on WhatsApp
  with a brief summary")
- MCP tool name: `memory__memory_search`
- Numeric thresholds appear as prose references ("5+ occurrences in
  30 days", "in 90 days", "older than 7 days"). The canonical
  value-form lives in `core/lifecycle_policy.py`; the prose-form here stays
  because it is how the LLM will naturally read the criteria.
  Drift between the two is detected by `tests/test_lifecycle_policy.py`'s
  source-cross-check (asserts the literal phrases stay in source).
"""

TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL = """\
## Weekly review

Schedule a weekly cron job to scan for lifecycle events. Log results to `~/.satiety-pipeline/outbox/housekeeping.log`.

### What to check

1. **Promotion candidates:** `memory__memory_search` for `tool-selection installed` entries with 5+ occurrences in 30 days
2. **Demotion candidates:** Boot-loaded tools with no `tool-selection` memory entries in 90 days
3. **Stale requests:** Files in `pending/` older than 7 days (already handled by cron script, but worth a nudge to the operator)
4. **Memory hygiene:** Entries with status `pending` that were actually resolved (status drift)

### Review output

Add a section to the housekeeping log:

```
2026-04-27 09:00  REVIEW  promotion-candidates=1 (csvkit: 8 uses/30d) demotion-candidates=0 stale-pending=0
```

If there are actionable items, ping the operator on WhatsApp with a brief summary.
"""
