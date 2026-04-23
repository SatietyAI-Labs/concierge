# Today — 2026-04-25 (Saturday, Fix Day 2)

*Opens on: `SESSION-2026-04-24-01.md` (Fix Day 1 — all six tasks green, Alembic
bootstrapped, denial-recall PASS, live install verification surfaced PEP-668
open question). Authoritative plan remains `docs/close-the-gap-plan-2026-04-23.md`.*

## Governing framing

Ship-it-whole per Lewie's 2026-04-23 mid-Day-4 commitment. Operational-first
discipline holds. Fix Day 1 cleared the foundation block (catalog peer
categories, rich in-chat content, approve-triggers-install, denial-recall).
Fix Day 2 closes the scope-expansion items the plan calls the biggest
scope-expansion of the fix block: skills as the fourth peer catalog citizen,
and the tool-level lifecycle state machine (the third state machine per audit
§D — absent prior to this day).

## Fix Day 2 — Skills ingest + tool-lifecycle schema

**Primary goal:** Catalog ingests skills as fourth peer category. Tool-lifecycle
state machine schema in place. Usage-log table accepting writes so §C7 Fix Day 4
scanner has data to aggregate.

## Tasks

| # | Task | Estimate |
|---|---|---|
| 0 | **Alembic migration-drift integration test:** new `tests/test_alembic_drift.py`; spins up a fresh empty SQLite, runs `alembic upgrade head` from baseline, verifies the resulting schema is identical to `Base.metadata.create_all()` output. Catches "column added to models.py without a migration" before it lands in production. Cheap insurance per the Fix Day 1 `init_db()` test-only docstring note. | ~30-45min |
| 1 | **A1 skills ingest path:** new `core/ingest/skills.py`; walks `/mnt/skills/public`, `/mnt/skills/user`, `/mnt/skills/examples`; parses SKILL.md frontmatter (name, description, location); registers each as catalog entry with `tool_type=skill`. Idempotent upsert-by-slug, same pattern as `core/ingest/catalog.py`. | ~2-3h |
| 2 | **A1 skills-specific schema fields:** add `path` (nullable for non-skill tools) and `ambient_loading` (bool, defaults true for skills) to Tool model; migration. Pack surface unchanged (skills are pack-less). | ~0.5h |
| 3 | **§D schema change:** add `lifecycle_state` column to Tool model with the blueprint's five values (`discovered` / `pending` / `used` / `loaded-on-boot` / `retired`); migration; backfill based on current `is_in_manifest` + `is_active` mapping (active+in-manifest → `loaded-on-boot`; dormant → `discovered`; etc.). | ~1.5h |
| 4 | **§D usage-log table:** new `ToolUsageEvent` SQLAlchemy model with columns `tool_id` (FK), `event_type` (recommended / installed / loaded / used / removed), `timestamp`, `session_id` (nullable), `context` (JSON, nullable); migration; no consumer yet (emit hooks land Fix Day 3). | ~1h |
| 5 | **Catalog ingest enrichment for skills metadata:** `_render_catalog` surfaces `ambient_loading` flag + `path` for skills so Opus can reason about ambient-loaded skills without trying to "install" them; skills-as-tool_type=skill gets an explicit rendering branch. | ~0.5-1h |

**Total sized load:** ~5.5-7.5h (Task 0 is separate budget as a pre-flight).

## End-of-day deliverable

`GET /tools?tool_type=skill` returns non-empty with `path` and `ambient_loading`
populated. `Tool.lifecycle_state` column populated on all existing + newly-
ingested rows. `ToolUsageEvent` table migrates cleanly and accepts a test write
via direct SQLAlchemy session. Migration-drift integration test green. Day 2
SESSION snapshot written.

## Checkpoint criteria

- [ ] Task 0 migration-drift test: passes against current HEAD schema; would fail
      if a models.py column were added without a corresponding migration
- [ ] Running the skills ingest populates ≥5 skill rows from `/mnt/skills/public`
- [ ] `GET /tools?tool_type=skill` returns skill rows with non-null `path` and
      `ambient_loading=true`
- [ ] `Tool.lifecycle_state` column backfilled for all existing rows (the Fix
      Day 1 four seeded + 44 ingested rows + new skill rows)
- [ ] `ToolUsageEvent` table migrates cleanly and accepts a test write
- [ ] Day 2 SESSION snapshot written

## Cut-if-behind ladder

**If behind schedule, cut:**
1. First cut: usage-log table (Task 4) slides to Fix Day 3 morning. Skills
   ingest is the priority deliverable because it's the biggest
   scope-expansion item and the blueprint commitment.
2. Second cut: catalog ingest enrichment (Task 5) slides to Fix Day 3. The
   rendering change is minor; the schema + data-layer work is foundational.
3. Third cut (only if foundational blockers surface): `lifecycle_state`
   backfill becomes a forward-only migration — new rows get the column
   populated at insert time; existing rows stay NULL until a one-time
   reconciliation pass in soak. Still honors the schema commitment.

Task 0 does NOT slide — it is cheap insurance that pays forward for every
migration on Days 2-3-4.

## What Fix Day 2 is NOT

- Not tool-lifecycle transition validation (that's Fix Day 3 per close-the-gap plan)
- Not usage-telemetry emit hooks (Fix Day 3 — schema lands today, emit code follows)
- Not loader `unload` / rich `list_active` (Fix Day 3)
- Not identity notes (Fix Day 3)
- Not narration-as-push / SSE / scanner (Fix Day 4)
- Not UI tiles (UI Day after Fix Day 4)
- Not PEP-668 install-strategy fix (open question from Fix Day 1; defer until
  Lewie weighs in on pipx vs system-pip3 vs escalation)

## Session opener

Paste this verbatim into a fresh Claude Code session to kick off Fix Day 2:

---

> Read in order, then confirm understanding before acting:
>
> 1. `CLAUDE.md` (project root — v3 content superseding prior versions)
> 2. `docs/concierge-operations-protocol.md`
> 3. `docs/concierge-blueprint-v2.md` (especially §Five Core Capabilities item #1 on skills as fourth peer, and §Architecture on tool-level lifecycle)
> 4. `docs/close-the-gap-plan-2026-04-23.md` §Fix Day 2 section
> 5. `planning/sessions/SESSION-2026-04-24-01.md` ← Fix Day 1 close-out; includes denial-recall PASS transcript, live-install verification, three new DECISIONS
> 6. `planning/today.md` ← this file
> 7. `planning/decisions/DECISIONS.md` tail — three new `[2026-04-24 Fix Day 1]` entries (Alembic-owns-schema, rich-content-validator-WARN, install_dispatcher-DI)
>
> Today is Fix Day 2 — Skills ingest + tool-lifecycle schema. Primary goal: catalog ingests skills as fourth peer category, tool-lifecycle state machine schema in place, usage-log table accepting writes.
>
> Before Task 1, run Task 0: write `tests/test_alembic_drift.py` — spin up a fresh empty SQLite, run `alembic upgrade head` from the baseline, verify the resulting schema matches `Base.metadata.create_all()` output. Cheap insurance that catches "column added without migration" drift. Under 30-45 minutes.
>
> Before starting code, report: your reading of the Fix Day 1 three decisions, any concerns about Task 0 or the Fix Day 2 tasks or checkpoint criteria, and your proposed session structure.
>
> Effort: xhigh throughout. Bump to max for the tool-lifecycle schema backfill design (mapping `is_in_manifest` + `is_active` + `is_discovered` onto the five-state enum is non-trivial — audit §D flagged it as design-level, not patch-level) and for the migration-drift integration test design in Task 0.
>
> Do not begin code until I confirm your reading and session plan.

---

*Note for the fresh session: The Fix Day 1 three DECISIONS entries at the tail
of `DECISIONS.md` cover the mid-session architectural calls (Alembic owning
schema, rich-content-validator as Tier 1 WARN, install_dispatcher DI). Read
them for context on why the Alembic path looks the way it does — especially
relevant when Task 2 and Task 3 generate migrations via `alembic revision
--autogenerate`. Task 0's migration-drift test guards against drift between
the Alembic path (production) and the `Base.metadata.create_all()` path (test
fixtures) diverging — which is exactly the failure mode the Fix Day 1
DECISIONS `create_all` section explicitly deferred to Fix Day 2.*

*Open question still outstanding from Fix Day 1 (not blocking Fix Day 2):
PEP-668 install-strategy design (pipx vs system-pip3 vs escalation). Do not
touch the install methods today unless Lewie has weighed in; the current
behavior (honest failure surfacing) is operational-first-correct until the
strategy is chosen.*
