# Today — 2026-04-25 (Saturday, Fix Day 3)

*Opens on: `SESSION-2026-04-25-01.md` (Fix Day 2 — all six tasks green plus one
architectural fix for the Fix Day 1 baseline-migration bug caught by Task 0;
skills ingest verified live with 6 rows; `tool_usage_events` table ready for
Fix Day 3 emit hooks). Authoritative plan remains
`docs/close-the-gap-plan-2026-04-23.md`.*

## Governing framing

Ship-it-whole per Lewie's 2026-04-23 commitment. Operational-first discipline
holds. Fix Day 2 closed the scope-expansion block: skills as the fourth peer
catalog citizen are ingested + rendered + surfaced via the API; the third
state machine (tool-level `lifecycle_state`) has its schema + backfill; the
§D usage-log table exists and accepts writes. Fix Day 3 wires the behavior
on top of that schema: transition validation, telemetry emit hooks, loader
richness, and identity notes.

## Fix Day 3 — Tool-lifecycle transitions + loader + identity notes

**Primary goal:** Tool-lifecycle state machine is operational (illegal
transitions rejected with logged reason). Loader supports `unload` and a
rich `list_active` API. Identity notes populate automatically after
install/remove cycles.

## Tasks

| # | Task | Estimate |
|---|---|---|
| 1 | **§D transition validation:** new `core/tool_transitions.py` mirroring `core/lifecycle_store/transitions.py` pattern; legal-transition table over the five `LIFECYCLE_STATE_VALUES`; validation runs on every `Tool.lifecycle_state` write (via SQLAlchemy event listener or explicit service method). Unit tests covering every legal edge + representative illegals. | ~1h |
| 2 | **§D usage telemetry emit hooks:** `concierge_recommend` → `ToolUsageEvent(tool_id, event_type='recommended', session_id, context={'rank': N, 'task_hint': ...})` per recommendation. `install_by_method` → `ToolUsageEvent(event_type='installed')` on successful install. Claude Code loader `load()` → `ToolUsageEvent(event_type='loaded')`. Session-id propagation if available; else null. | ~1-2h |
| 3 | **§D derived-label migration:** deprecate `_tool_state(is_in_manifest, is_active)` in `core/recommend/prompt.py:134-145` in favor of the stored `lifecycle_state` column; keep `_tool_state` as a fall-back mapping for rows that somehow don't have `lifecycle_state` set (shouldn't happen after Fix Day 2, but defensive). | ~0.5-1h |
| 4 | **§D skills-specific lifecycle semantics:** define what "used" means for a skill (SKILL.md viewed at session start? Skill instructions referenced in a response?); document in `core/tool_transitions.py` docstring + a brief note in `core/ingest/skills.py`. No runtime code change expected — just pinning the semantic contract. | ~0.5-1h |
| 5 | **A4 loader `unload(tool_prefix)` method** in `adapters/claude_code/backing_server_registry.py`; symmetric with existing `load`. Unit test + one manual-verification write-up in session snapshot. | ~0.5h |
| 6 | **A4 rich `list_active()` API** returning pack + per-tool detail + `lifecycle_state` from the shared Tool model. Replaces / extends whatever the current `list_active` returns. | ~0.5-1h |
| 7 | **Identity Notes:** `identity_get` / `identity_set` on `MemoryClient` in `core/memory.py` (stubs exist at lines 40-45 + 74-77 per DECISIONS `[2026-04-23]`). Integrate into `core/recommend/service.py` prompt composition — identity summary joins the system-prompt context. Post-transition hook in `core/lifecycle_store/service.py` updates identity after install/remove. | ~1-2h |

**Total sized load:** ~5-9h.

## End-of-day deliverable

Illegal tool-lifecycle transitions rejected with logged reason. A
`concierge_recommend` call produces ≥1 `ToolUsageEvent` row. An approved
install produces a `ToolUsageEvent(event_type='installed')` row.
`BackingServerRegistry.unload('csvkit')` removes csvkit from active and
frees resources. `list_active()` returns structured pack + tool detail
with `lifecycle_state`. `MemoryClient.identity_get()` returns non-empty
content after an install cycle. Day 3 SESSION snapshot written.

## Checkpoint criteria

- [ ] Attempting an illegal `lifecycle_state` transition (e.g. `retired → used`) is rejected with logged reason
- [ ] A `concierge_recommend` call produces at least one `ToolUsageEvent` row (verified via direct SQL after a live call)
- [ ] An approved install produces a `ToolUsageEvent(event_type='installed')` row
- [ ] `BackingServerRegistry.unload('csvkit')` removes csvkit from active and frees resources
- [ ] `list_active()` returns structured pack + tool detail with `lifecycle_state`
- [ ] `MemoryClient.identity_get()` returns non-empty content after an install cycle
- [ ] Day 3 SESSION snapshot written

## Cut-if-behind ladder

**If behind schedule, cut:**
1. First cut: Task 4 (skills lifecycle semantics docstring) slides to Fix Day 4. The code itself works with the existing state machine — Task 4 is docstring-clarity only.
2. Second cut: Task 7 (identity notes) slides to Fix Day 4 morning. Lowest dependency of the remaining tasks; Fix Day 4 is narration-as-push + SSE + scanner, none of which depend on identity notes.
3. Third cut (only if foundational blockers surface): Task 3 (derived-label migration) slides — `_tool_state` can keep its current shape; rendering stays on `(is_in_manifest, is_active)` for another day. Validation + emit hooks are the priority deliverables.

Tasks 1, 2, 5, 6 do NOT slide — Task 1 unblocks transition-related code in 2/5/6; Task 2 populates the telemetry scanner will need on Fix Day 4; Tasks 5/6 are loader richness that the UI day needs to render.

## What Fix Day 3 is NOT

- Not narration-as-push or SSE or scanner (Fix Day 4)
- Not UI tiles (UI Day)
- Not PEP-668 install-strategy fix (still pending Lewie's ruling on pipx vs system-pip3 vs escalation)
- Not promotion/demotion scanner (Fix Day 4 Task C7)

## Session opener

Paste this verbatim into a fresh Claude Code session to kick off Fix Day 3:

---

> Read in order, then confirm understanding before acting:
>
> 1. `CLAUDE.md` (project root — v3 content superseding prior versions)
> 2. `docs/concierge-operations-protocol.md`
> 3. `docs/concierge-blueprint-v2.md` (especially §D tool-level lifecycle in the audit, §Memory Service for identity notes)
> 4. `docs/close-the-gap-plan-2026-04-23.md` §Fix Day 3 section
> 5. `planning/sessions/SESSION-2026-04-25-01.md` ← Fix Day 2 close-out; skills ingest + schema foundations landed
> 6. `planning/today.md` ← this file
> 7. `planning/decisions/DECISIONS.md` tail — `[2026-04-25 Fix Day 2]` entry (Alembic baseline fix) + the six `[2026-04-23]` strategic decisions still authoritative for Fix Day 3
>
> Today is Fix Day 3 — Tool-lifecycle transitions + loader + identity notes. Primary goal: transition validation operational, usage telemetry emit hooks in place, loader unload + rich list_active, identity notes populating end-to-end.
>
> Before starting code, report: your reading of the Fix Day 2 DECISIONS entry + the six strategic `[2026-04-23]` entries relevant today, any concerns about the Fix Day 3 tasks or checkpoint criteria, and your proposed session structure (single block or split).
>
> Effort: xhigh throughout. Bump to max for the transition validation (illegal-transition table design is the highest-stakes architectural call of the day) and for the identity-notes prompt-integration (touches the system-prompt composition which Fix Day 4 also extends).
>
> Do not begin code until I confirm your reading and session plan.

---

*Note for the fresh session: the `[2026-04-25 Fix Day 2]` DECISIONS entry
covers the Alembic baseline-migration fix; the `disable_existing_loggers=False`
change on `alembic/env.py` is mentioned there too. Relevant today because
Fix Day 3 migrations (if any — Task 1 might not need a migration) autogenerate
against the now-consistent Alembic chain.*

*`Settings.skills_root` defaults to `/mnt/skills`. Not load-bearing for Fix
Day 3 tasks, but remember it when reasoning about skill rows in identity
notes / usage telemetry — skill rows may not exist on fresh clones, so any
code that depends on at least one skill row should degrade gracefully.*

*Open questions still outstanding (not blocking Fix Day 3):*
- *PEP-668 install-strategy design (Fix Day 1)*
- *Skills-recommender narration in the JSON envelope (Fix Day 2) — converges into Fix Day 4's narration-as-push work; don't front-run*
