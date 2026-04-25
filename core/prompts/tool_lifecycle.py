"""Prompt fragment for tool-lifecycle weekly-review (X7-A).

Originally extracted verbatim from the `## Weekly review` section
of an OpenClaw skill source
(`_legacy/openclaw-workspace/skills/tool-lifecycle/SKILL.md`) on
2026-04-21 during the v3 build period; sanitized for public release
per DECISIONS `[2026-04-29 Day 8]` (EXTRACT invariant retired). The
constant below is Concierge-canonical, not byte-identical to any
external source. See `core/prompts/SKILL_FRAGMENT_SYNC_LOG.md` for
historical context.

**Selective extract** — X7 in the v3 build classification was a
"partial hybrid" per classification §C.5.3: promotion/demotion
thresholds + tag schema went to Python constants in
`core/lifecycle_policy.py`; this fragment captured only the prose
weekly-review protocol that Opus 4.7 reads at weekly-review compose
time.

Consumer
--------
Composed into POST /recommend's Opus 4.7 system prompt by
`core.recommend.prompt::compose_recommendation_prompt`, as the X7-A
fragment in the X3→X4→X6→X7→X8 chain.

Worked content preserves Class-2 operator paths
(`~/.satiety-pipeline/outbox/housekeeping.log`) and the
`memory__memory_search` MCP tool name; numeric thresholds stay as
prose ("5+ occurrences in 30 days", etc.) — the canonical numeric
value-form lives in `core/lifecycle_policy.py`, with
`tests/test_lifecycle_policy.py`'s source-cross-check asserting the
literal phrases stay aligned across both files.
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

If there are actionable items, ping the operator with a brief summary.
"""
