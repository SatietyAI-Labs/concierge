# Close-the-Gap Plan (2026-04-23)
### The fix block that precedes UI build

---

## What this document is

This plan supersedes Day 4 onward of `concierge-claude-code-plan-v3.md`. It was produced after three verification passes (catalog multi-category gap, three-part fidelity report, comprehensive blueprint audit) surfaced a cluster of load-bearing gaps between current Concierge implementation and blueprint-v2 + TOOL-CONCIERGE-OVERVIEW promises. The scope pivot from "hackathon-MVP demo" to "ship it whole and post it for people to use" (handoff-2026-04-23-scope-pivot.md) changed the filter: anything consciously-narrowed for MVP is now a no-go, and Lewie is a day ahead of the original hackathon pacing so time-to-soak is not the binding constraint.

This document is the authoritative sequencing for the close-the-gap work. All sizing reflects consensus between strategic planning (this chat) and Claude Code's audit. Ranges are honest — the lower bound assumes clean runs, the upper bound assumes normal friction.

---

## Read order for any session picking this up

Read in order before acting on the project:

1. `docs/CLAUDE-v3.md`
2. `planning/concierge-operations-protocol.md`
3. `planning/concierge-blueprint-v2.md` — especially §Five Core Capabilities and §Platform-Agnostic Architecture
4. `planning/handoff-2026-04-23-scope-pivot.md` — context for why the verification pause happened
5. This document (`planning/close-the-gap-plan-2026-04-23.md`)
6. The most recent SESSION snapshot in `planning/sessions/`
7. `planning/audits/AUDIT-2026-04-23-blueprint-coverage.md` — the full evidentiary basis for this plan

If anything in the current-session context conflicts with this document, this document wins.

---

## Scope summary

The verification triplet identified two classes of gap: **structural foundations** where implementation doesn't yet support blueprint promises (catalog can't express HTTP/API or skill categories as peers; tool-level lifecycle state machine is an entirely missing third state machine, not a conflation), and **capability gaps** where functionality exists in OpenClaw or is promised by blueprint but isn't reached in current Concierge (approve-triggers-install wire-in, loader `unload` and rich `list_active`, narration-as-push, dual-channel real-time surface, identity notes, promotion/demotion scanner).

The close-the-gap work is structured into two tiers plus UI plus soak. Tier 1 foundations unblock Tier 2 downstream work. Tier 2 capabilities are largely parallel and sequenced by size and dependency. UI is the payoff — Day 4's original plan, now with honest data to render. Soak is the real acceptance criterion under operational-first.

**Sized totals:**
- Tier 1 structural foundations: ~18-25.5h
- Tier 2 capability gaps: ~9-13.5h
- UI build (A7 three tiles): ~4-6h
- Soak smoke + fixtures: ~4-6h
- **Combined: ~35-51h across 5 fix-days + UI day + soak day**

Substantive completion lands end of Day 8-9 under current pacing. Soak starts Day 9-10. 48-hour drift-watch completes Day 11-12. Past original hackathon end — acceptable under the operational-first framing.

---

## Decisions to append to DECISIONS.md

Six decisions emerged from this planning chat. All should be appended to `planning/decisions/DECISIONS.md` in the standard template format. They are formalized below ready to paste.

---

### [2026-04-23] — Skills as fourth catalog category with full peer status

**Context:** Blueprint-v2 §Five Core Capabilities item #1 names four categories as peers: MCP servers, CLI commands, lightweight HTTP APIs, and skills. Current catalog schema has no `tool_type` enum. Skills are not currently expressed as catalog entries — they exist in `/mnt/skills/` directories and are loaded on-demand by Claude when it judges them relevant, but have no systemic memory, lifecycle, or recommendation-engine awareness.

**Options considered:**
- Three categories only (MCP / CLI / HTTP), skills remain outside catalog — 0h but misses blueprint commitment
- Four categories with schema-ready / data-model-deferred — ~0.5h enum work, skills ingest Phase 2
- Four categories with full peer status including ingest and lifecycle — ~5-7h on top of three-category baseline

**Decision:** Four categories with full peer status. Catalog ingest walks `/mnt/skills/public`, `/mnt/skills/user`, `/mnt/skills/examples`. Each SKILL.md is parsed for its frontmatter (name, description, location), registered as a catalog entry with `tool_type=skill`. Skills participate in recommendation, lifecycle, and usage telemetry.

**Reasoning:** Blueprint is authoritative. Skills solve exactly the same myopia problem as tools — they sit in the context window unmanaged by any lifecycle, with no promotion/demotion based on real usage. Treating them as catalog peers extends Concierge's value proposition from MCP-tool-awareness to all-agent-capability-awareness. The extra 5-7h is justified under ship-it-whole scope.

**Reversibility:** Easy. Schema supports all four values from v1; populating skills can be turned off by disabling the skills-ingest path.

**Decided by:** Lewie (strategic chat, 2026-04-23).

**Affects:** `core/db/models.py` Tool schema; new `core/ingest/skills.py` module; `core/recommend/prompt.py` catalog-rendering; B1 UI Registry tile.

---

### [2026-04-23] — Wishlist collapse into requests

**Context:** Blueprint-v2 §Post-hackathon UI sections references a "Wishlist Patterns" tile, implying a surface distinct from formal tool-requests. TOOL-CONCIERGE-OVERVIEW does not name a standalone wishlist section. `core/prompts/SKILL_FRAGMENT_SYNC_LOG.md:388-389` notes "lifecycle store absorbs the wishlist log" as an architectural decision, but the collapse was not reflected in code or blueprint.

**Options considered:**
- Keep wishlist as separate less-structured gap-log surface alongside formal requests (~2-3h to build)
- Collapse: formal requests are the only gap-capture surface; Phase-2 "patterns" UI derives from requests table

**Decision:** Collapse. Wishlog is deprecated as a distinct surface. `concierge_request_tool` is the gap-capture surface. Agents who can't fully evaluate alternatives file thin requests (tool_name only) and Concierge-the-reasoner fills context during the recommendation that prompted the request. Phase-2 "Wishlist Patterns" UI view becomes "request patterns" derivable from the existing requests table.

**Reasoning:** The wishlog's reason-for-existing in OpenClaw was letting low-capability agents casually note gaps without doing full evaluation. Concierge's `concierge_request_tool` with its rich schema handles the same function without needing a separate lighter-weight surface. Three-part fidelity Q3 confirmed agents can populate requests richly when prompted. One storage model, one UI surface, one mental model.

**Reversibility:** Medium. Reversing requires building the separate wishlist table and ingest path that doesn't currently exist.

**Decided by:** Lewie (strategic chat, 2026-04-23).

**Affects:** Blueprint-v2 §Post-hackathon UI sections to be updated. A8 in audit marked as Phase-2-derivable rather than separate-surface.

---

### [2026-04-23] — A2 recommendation five-check loop collapsed into Opus reasoning

**Context:** Blueprint-v2 §Recommendation Engine describes a five-step protocol (memory → resolved requests → catalog → manifest → discovery). TOOL-CONCIERGE-OVERVIEW names the same loop. Current implementation at `core/recommend/service.py:101-122` pre-loads memory + catalog and lets Opus reason about the rest in a single call. Audit flagged this as "defensible collapse" but noted possible loss of the "previously denied → still denied" guardrail.

**Options considered:**
- Accept current collapse as v1 architecture (~0h)
- Add explicit resolved-requests query between memory and catalog (~1h)
- Fully branch into five explicit Python steps (~1-2h)

**Decision:** Accept the collapse as intentional architecture. Denial-recall is handled via memory retrieval — a prior-denied tool shows up in memory hits and Opus is instructed via X3/X4 prompt fragments to honor prior decisions. The collapse is the more-Concierge-native pattern (reasoning over branching for soft decisions).

**Verification requirement:** Empirically verify denial-recall works — pick a previously-denied tool from memory, send a task that would have triggered it, confirm Opus honors the prior denial in its recommendation. This is a ~1h test, not a fix, and is included in Fix Day 1. If verification fails, add the ~1h resolved-requests query between memory and catalog.

**Reasoning:** Branching if/else logic over soft decisions replicates what Opus does natively. The structural guardrail the overview implies can be preserved via prompt instruction without explicit branching, provided the verification confirms it.

**Reversibility:** Easy. Adding the explicit query is a localized change if verification exposes a gap.

**Decided by:** Lewie (strategic chat, 2026-04-23).

**Affects:** A2 in audit closes under this decision. Verification task added to Fix Day 1 checkpoint criteria.

---

### [2026-04-23] — Push channel reframed as narration-as-push

**Context:** Blueprint-v2 and TOOL-CONCIERGE-OVERVIEW reference a push channel where Concierge proactively injects messages into the agent's context. Claude Code is a conversational agent without an external interrupt surface — true async push would require sidecar infrastructure that doesn't exist. The underlying user need is collaborative visibility: agents acknowledging their own tool limits, surfacing Concierge's work visibly, making the user feel the partnership rather than having to dig for it.

**Options considered:**
- True async push via sidecar process (infrastructure that doesn't exist; Phase-3)
- Minimum-viable narration-as-push via prompt surface (achievable in current harness)

**Decision:** Narration-as-push. Every Concierge interaction leaves a visible trail in the agent's conversation via three combined patterns:

1. **Enriched MCP tool descriptions** for `concierge_recommend` and `concierge_request_tool` include explicit narration requirements: "After invoking this tool, your next user-visible message must briefly narrate the consultation — what you asked Concierge about, what it recommended, what you're doing with that recommendation."
2. **MCP resources protocol** exposes X3/X4/X6/X7/X8 preambles + gap-preamble as readable resources at session start. Turns narration from a per-tool instruction into a session-long posture.
3. **Piggyback observations in recommend responses** — when Concierge answers, it can optionally include "by the way, I noticed this other thing" observations. Agent surfaces these in its narration.

**Reasoning:** The user-facing goal — feeling the collaborative partnership — is achieved by making every Concierge interaction produce a visible "I just consulted Concierge, here's what it said" moment in the conversation. True async push would add infrastructure complexity that doesn't meaningfully improve the user experience because Claude Code doesn't have an interrupt surface to compare against.

**Reversibility:** Easy. Prompt-surface change, no infrastructure commitments.

**Decided by:** Lewie (strategic chat, 2026-04-23).

**Affects:** Fix Day 4 narration-as-push tasks. Async sidecar push marked as Phase-3, out of scope for ship-it-whole v1.

---

### [2026-04-23] — Identity Notes included in v1

**Context:** TOOL-CONCIERGE-OVERVIEW §Memory and Learning describes identity notes as a compact running summary of tool preferences in persistent memory. Stubs exist at `core/memory.py:40-45` marked "not implemented (scope trim)" and `core/memory.py:74-77` defining the identity collection name with no consumer. Blueprint-v2 does not name identity notes explicitly but its memory service §71-81 references similar persistent-preference patterns.

**Options considered:**
- Defer to Phase 2 (originally cut in earlier sizing)
- Include in v1

**Decision:** Include in v1. Implement `identity_get` / `identity_set` on `MemoryClient`. Recommendation engine reads current identity summary at recommend time and injects into Opus system prompt context. Identity gets updated after each install/remove via lifecycle-store post-transition hook.

**Reasoning:** Identity notes solve the "fresh session forgets my preferences" problem that otherwise requires Opus to re-derive preferences from memory search every time. One persistent summary is cheaper to read than N tool-selection memory entries. The architecture was designed with room for it; finishing the implementation is closing a known gap rather than adding scope.

**Reversibility:** Easy. Disabling the identity read in recommendation engine is localized.

**Decided by:** Lewie (strategic chat, 2026-04-23).

**Affects:** `core/memory.py` identity methods; `core/recommend/service.py` prompt composition; `core/lifecycle_store/service.py` post-transition hook.

---

### [2026-04-23] — C7 promotion/demotion scanner included in v1

**Context:** Blueprint-v2 §Post-hackathon UI sections marks promotion/demotion threshold adjustment as Phase-2 ("Settings — adjust thresholds"). But TOOL-CONCIERGE-OVERVIEW §Tool Lifecycle Management describes an active scanner with weekly-review semantics. Promotion/demotion constants already exist at `core/lifecycle_policy.py:139-160` with thresholds matching overview. Usage telemetry is a §D dependency for the audit's B1 "last used / success rate" column and B3 "top 3 tools" tile, so the underlying data infrastructure is being built anyway.

**Options considered:**
- Constants-only for v1; scanner deferred to Phase 2 (saves ~2-3h, UI tiles show blanks)
- Full scanner in v1 (auto-acts on clear signal, flags ambiguous cases for review)

**Decision:** Full scanner in v1. Weekly job implemented via APScheduler in the FastAPI lifespan (no cron). Reads usage-log from §D, emits promotion candidates (5+ uses in 30d) and demotion candidates (90+ days unused), writes summary to `/health`, surfaces in UI's Health tile. Auto-promotes on unambiguous signal, flags ambiguous cases (tools just crossing thresholds, tools with recent install date) for operator review rather than auto-acting.

**Reasoning:** Since §D work creates the usage-log table and tool-lifecycle machine regardless, the scanner is a small addition on top. Demo-worthy and operator-useful. Blueprint's Phase-2 framing was written before the scope pivot to ship-it-whole.

**Reversibility:** Easy. Scheduled job can be disabled via config flag.

**Decided by:** Lewie (strategic chat, 2026-04-23).

**Affects:** New `core/lifecycle_scanner.py` module; APScheduler addition to FastAPI lifespan in `core/app.py`; `/health` payload gets scanner fields; Fix Day 4 tasks.

---

## The fix-day plan

Each day below specifies primary goal, concrete tasks with hour estimates, end-of-day deliverable, and checkpoint criteria. Daily load targets 8-10 productive hours; the upper ranges in task estimates are padding for normal friction.

---

### Fix Day 1 — Catalog foundation + quick wins

**Primary goal:** Catalog can express MCP / CLI / HTTP categories as peers. Rich in-chat content schema in place. Approve-triggers-install works end-to-end.

**Tasks:**
- A1 schema: add `tool_type` enum (`mcp` / `cli` / `http` / `skill`) to `core/db/models.py:33-52`; Alembic migration; backfill 4 existing rows (~1h)
- A1 ingest parser for MCP / CLI / HTTP: new `core/ingest/catalog.py`; reads from existing `_legacy/toolconcierge/TOOL-CATALOG.md` and other source(s); idempotent (~2-3h)
- Rich in-chat content: add `category`, `install_method`, `risk_cost` fields to `RecommendationRecord`; update Opus system prompt to require emission; extend `validator.py` to assert presence (~1-1.5h)
- C4 X13 wire-in: `core/lifecycle_store/service.py::update_status` triggers `install_by_method` when status transitions to `approved` (~0.25h)
- C4 npx-for-MCP install method: add `install_npx_mcp(package)` to `core/install/methods.py`; update `normalize_install_method` signals (~0.75h)
- Memory denial-recall verification: pick a denied tool from memory, send a task that would have triggered it, confirm Opus honors the prior denial (~1h)

**End-of-day deliverable:** `GET /tools` returns catalog with three category values populated. `POST /recommend` response includes category / install_method / risk_cost for each rec. Approving a pending request via `POST /requests/{filename}/status` triggers the appropriate install method and writes the install section back to the file. Denial-recall verification logged (pass or fail).

**Checkpoint criteria:**
- [ ] `tool_type` enum in schema with migration applied and 4 rows backfilled
- [ ] `GET /tools` returns non-null `tool_type` for every row
- [ ] `POST /recommend` response includes three new fields on `RecommendationRecord`; validator asserts presence
- [ ] Approve transition on a pending csvkit-request triggers `pip install --user csvkit` via install_by_method
- [ ] `install_npx_mcp` handler exists and passes round-trip dry-run
- [ ] Memory denial-recall verification result recorded in SESSION snapshot
- [ ] Day 1 SESSION snapshot written

**If behind schedule, cut:** memory denial-recall verification moves to Fix Day 2 morning. Everything else is foundational and stays on Day 1.

---

### Fix Day 2 — Skills ingest + tool-lifecycle schema

**Primary goal:** Catalog ingests skills as fourth peer category. Tool-lifecycle state machine schema in place.

**Tasks:**
- A1 skills ingest path: new `core/ingest/skills.py`; walks `/mnt/skills/public`, `/mnt/skills/user`, `/mnt/skills/examples`; parses SKILL.md frontmatter (name, description, location); registers each as catalog entry with `tool_type=skill` (~2-3h)
- A1 skills-specific schema fields: add `path` (nullable for non-skill tools) and `ambient_loading` (bool, defaults true for skills) to Tool model; migration (~0.5h)
- §D schema change: add `lifecycle_state` column to Tool model (`discovered` / `pending` / `used` / `loaded-on-boot` / `retired`); migration; backfill based on current `is_in_manifest` + `is_active` mapping (~1.5h)
- §D usage-log table: new `ToolUsageEvent` model (`tool_id`, `event_type`, `timestamp`, `session_id`, `context`); migration (~1h)
- Catalog ingest enrichment for skills metadata (description, ambient-loading flag surfaces in rendered catalog) (~0.5-1h)

**End-of-day deliverable:** `GET /tools` includes skill-category rows. Tool model has `lifecycle_state` and `path` columns. `ToolUsageEvent` table exists and accepts writes via direct SQLAlchemy session.

**Checkpoint criteria:**
- [ ] Running the skills ingest populates at least 5 skill rows from `/mnt/skills/public`
- [ ] `GET /tools?tool_type=skill` returns skill rows with non-null `path` and `ambient_loading=true`
- [ ] `Tool.lifecycle_state` column backfilled for all existing rows (four existing seeded rows + skill rows)
- [ ] `ToolUsageEvent` table migrates cleanly and accepts a test write
- [ ] Day 2 SESSION snapshot written

**If behind schedule, cut:** usage-log table slides to Fix Day 3 morning. Skills ingest is the priority deliverable because it's the biggest scope-expansion item.

---

### Fix Day 3 — Tool-lifecycle transitions + loader + identity notes

**Primary goal:** Tool-lifecycle state machine is operational. Loader supports unload and rich list_active. Identity notes working end-to-end.

**Tasks:**
- §D transition validation: new `core/tool_transitions.py` mirroring `core/lifecycle_store/transitions.py` pattern; legal-transition table; validation on every state write (~1h)
- §D usage telemetry emit hooks: `concierge_recommend` emits `UsageEvent(tool_id, event_type='recommended')`; install_by_method emits `UsageEvent(tool_id, event_type='installed')`; Claude Code loader `load()` emits `UsageEvent(tool_id, event_type='loaded')` (~1-2h)
- §D derived-label migration: deprecate `_tool_state` in `core/recommend/prompt.py:125-136` in favor of stored `lifecycle_state`; keep as backward-compat mapping for transition period (~0.5-1h)
- §D skills-specific lifecycle semantics: define what "used" means for a skill (Claude viewed the SKILL.md at session start? Skill's instructions were referenced in a response?); document in `core/tool_transitions.py` docstring (~0.5-1h)
- A4 loader `unload(tool_prefix)` method in `adapters/claude_code/backing_server_registry.py` (~0.5h)
- A4 rich `list_active()` API returning pack + tool detail + lifecycle_state (~0.5-1h)
- Identity Notes: `identity_get` / `identity_set` on `MemoryClient`; integrated into `core/recommend/service.py` prompt composition; post-transition hook updates identity after install/remove (~1-2h)

**End-of-day deliverable:** Tool-lifecycle transitions validated on write. Usage events emit on recommend/install/load. `_tool_state` deprecated but still functional for backward-compat. Loader can unload individual packs and report rich list_active. Identity notes populate automatically after installs.

**Checkpoint criteria:**
- [ ] Attempting an illegal tool-lifecycle transition (e.g. retired → used) is rejected with logged reason
- [ ] A `concierge_recommend` call produces at least one `ToolUsageEvent` row
- [ ] An approved install produces a `ToolUsageEvent(event_type='installed')` row
- [ ] `BackingServerRegistry.unload('csvkit')` removes csvkit from active and frees resources
- [ ] `list_active()` returns structured pack + tool detail with lifecycle_state
- [ ] `MemoryClient.identity_get()` returns non-empty content after an install cycle
- [ ] Day 3 SESSION snapshot written

**If behind schedule, cut:** skills-specific lifecycle semantics documentation slides to Fix Day 4 (the code itself still works; it's the docstring clarity that defers). Identity notes is the lowest-dependency item and can slide to Day 4 morning if needed.

---

### Fix Day 4 — Narration-as-push + real-time surface + scanner + integration

**Primary goal:** Collaborative visibility working in Claude Code sessions. Real-time surface delivers request notifications. Promotion/demotion scanner running. All Tier 1+2 changes integrated.

**Tasks:**
- Narration-as-push, pattern 1: enrich `concierge_recommend` MCP tool description with narration requirement; same for `concierge_request_tool` (~0.5-1h combined)
- Narration-as-push, pattern 2: MCP resources protocol implementation at `adapters/claude_code/resources.py`; expose X3/X4/X6/X7/X8 preambles + gap-preamble via `resources/list` + `resources/read` (~1-2h)
- Narration-as-push, pattern 3: piggyback observations in `RecommendResponse`; new optional `side_observations` field; Opus prompt instructed to surface relevant adjacent observations when present (~0.5-1h)
- C3 dual-channel real-time SSE: add `/ui/events` SSE endpoint; `new_request` event fires when request filed; HTMX-friendly format (~1-2h)
- C7 promotion/demotion scanner: new `core/lifecycle_scanner.py`; APScheduler weekly job registered in FastAPI lifespan; scans usage-log for promotion candidates (5+ uses in 30d), demotion candidates (90+ days unused), stale pending (>7d); auto-promotes on unambiguous signal; flags ambiguous cases; writes summary to `/health` payload (~2-3h)
- Integration tests covering all Tier 1+2 changes end-to-end (~1-2h)

**End-of-day deliverable:** A fresh Claude Code session feels visibly collaborative when Concierge is consulted. Real-time SSE delivers new-request events to connected UI clients. Weekly scanner runs and surfaces promotion/demotion candidates. Full integration suite passes.

**Checkpoint criteria:**
- [ ] In a fresh Claude Code session, invoking `concierge_recommend` produces a user-visible message narrating the consultation
- [ ] `resources/list` returns the five preambles; `resources/read` retrieves them
- [ ] `RecommendResponse` optionally includes `side_observations` when Opus has relevant adjacent observations
- [ ] `GET /ui/events` streams SSE with `new_request` events when a request is filed
- [ ] Scanner run produces valid output for at least one test scenario (synthetic usage-log entries)
- [ ] `/health` payload includes scanner summary fields
- [ ] Integration test suite passes end-to-end
- [ ] Day 4 SESSION snapshot written

**If behind schedule, cut:** MCP resources protocol can be scoped to tool-description enrichment only (pattern 1 + 3), with pattern 2 deferred to soak. Scanner can ship with auto-promotion only and demotion flagging deferred if truly needed.

---

### UI Day — A7 three tiles with honest data

**Primary goal:** Operator dashboard live at `localhost:8000/ui` with Tool Registry, Pending Requests Inbox, Health/Stats Bar all rendering real data.

**Tasks:**
- A7 Tool Registry tile: hierarchical rendering (packs → tools); columns for name, `tool_type`, `lifecycle_state`, last_used (from usage-log), success_rate (from usage-log); filter by tool_type and lifecycle_state; search by name; skills rendered as category alongside MCP/CLI/HTTP (~2-2.5h)
- A7 Pending Requests Inbox tile: card per request; approve/deny/defer buttons posting to `/requests/{filename}/status`; HTMX partial update; SSE listener for new requests (~1.5-2h)
- A7 Health/Stats Bar: four sub-tiles — token-win counter (wire to existing `/health` payload), active MCP servers/total (from rich `list_active`), scanner last-run timestamp + summary, top-3 tools (from usage-log aggregation) (~1-2h)
- End-to-end smoke: session triggers `concierge_request_tool` → SSE fires → inbox shows new request → operator clicks approve → install runs → cron/scanner would move file → scanner picks up usage event for promotion tracking (~1h)

**End-of-day deliverable:** Operator can open `localhost:8000/ui`, see all three tiles populated with real data, approve a pending request, watch it install, see the install reflected in usage-log and eventually in Registry's last_used column.

**Checkpoint criteria:**
- [ ] `GET /ui` returns dashboard HTML (not 404)
- [ ] Tool Registry renders all four categories as peers
- [ ] Pending Requests Inbox approves a real request and triggers real install
- [ ] Health bar shows live data for all four sub-tiles
- [ ] SSE delivers new_request event to connected browser
- [ ] End-to-end smoke passes once
- [ ] UI Day SESSION snapshot written

**If behind schedule, cut:** search/filter on Registry can be minimum-viable. Top-3-tools tile can show placeholder if usage-log aggregation is rough. The core demo beat is the approve-triggers-install flow — protect that above polish.

---

### Soak Day 1 — Smoke, fixtures, 48h drift-watch start

**Primary goal:** Full smoke test battery passes. Fixtures codified. 48-hour drift-watch starts.

**Tasks:**
- Smoke test battery covering all seven capabilities: catalog multi-category, rich in-chat content, tool-lifecycle transitions, loader unload/list_active, narration-as-push, SSE real-time, scanner (~2-3h)
- Stress fixtures: bulk-generate 50+ request files, stress the inbox UI; bulk-generate 500+ usage events, stress the scanner aggregation queries (~1-2h)
- Start 48h drift-watch: live real Opus 4.7 calls on recurring schedule (e.g., one canonical call every 15 minutes); fixture_drift_count monitored via `/health` (~0.5h setup)
- Documentation polish: update README with ship-it-whole scope; update blueprint-v2 with wishlist-collapse ruling; ensure DECISIONS.md fully current (~1h)

**End-of-day deliverable:** Soak is running. Drift-watch active. Docs aligned with shipped scope.

**Checkpoint criteria:**
- [ ] Smoke test battery passes 5 consecutive runs
- [ ] Stress fixtures run without UI or scanner failures
- [ ] Drift-watch live call succeeds; `/health` shows fixture_drift_count
- [ ] README and blueprint-v2 reflect all six decisions from this planning chat
- [ ] Soak Day 1 SESSION snapshot written

**During 48h soak window:** any drift detected triggers immediate investigation. Declaration of "done" happens at hour 48 if no drift, else the clock resets.

---

## Opening prompt for Fix Day 1

Paste this into a fresh Claude Code session to kick off Fix Day 1:

---

> Read in order, then confirm understanding before acting:
>
> 1. `docs/CLAUDE-v3.md`
> 2. `planning/concierge-operations-protocol.md`
> 3. `planning/concierge-blueprint-v2.md` (especially §Five Core Capabilities and §Platform-Agnostic Architecture)
> 4. `planning/handoff-2026-04-23-scope-pivot.md`
> 5. `planning/close-the-gap-plan-2026-04-23.md` ← this is the authoritative plan superseding Day 4 onward of plan-v3
> 6. Most recent SESSION snapshot in `planning/sessions/`
> 7. `planning/audits/AUDIT-2026-04-23-blueprint-coverage.md`
>
> Before beginning Fix Day 1 work, append the six decisions from the close-the-gap plan's §Decisions-to-append section to `planning/decisions/DECISIONS.md`. Verify they land cleanly and cite the planning-chat timestamp.
>
> Today is Fix Day 1 — Catalog foundation + quick wins. Primary goal: catalog can express MCP / CLI / HTTP categories as peers; rich in-chat content schema in place; approve-triggers-install works end-to-end.
>
> Before starting any code, report: your reading of the six decisions, any concerns or questions about the Fix Day 1 task list or checkpoint criteria, and your proposed session structure (single block or split into two sessions).
>
> Effort: xhigh throughout. Bump to max for schema migration design and for the memory denial-recall verification logic.
>
> Do not begin code until I confirm your reading and session plan.

---

## Out-of-scope / Phase-2 reminders

These were explicitly deferred during planning and should not accidentally pull into the fix block:

- **Multi-agent hierarchy / worker escalation** — OpenClaw deployment pattern; not applicable to standalone Concierge
- **WhatsApp-specific notification channel** — dual-channel *concept* is in scope (SSE covers it); WhatsApp-as-channel is OpenClaw-deployment-specific
- **Cron-based housekeeping mechanism** — semantics are in scope (status-line-driven transitions); the *mechanism* can be APScheduler rather than system cron
- **True async sidecar push channel** — Phase 3; narration-as-push covers the user-facing need
- **Full registry-query discovery engine** (live npm / PyPI / GitHub queries) — Opus-reasoning surface works today; full registry implementation is Phase 2
- **OpenClaw adapter** — explicitly out-of-scope for hackathon week and this close-the-gap phase; Phase 2
- **Claude Desktop adapter** — Phase 2
- **Settings UI for threshold adjustment** — Phase 2; current scanner uses hardcoded thresholds from `lifecycle_policy.py`
- **Wishlist as standalone surface** — collapsed into requests per decision above
- **Lifecycle Activity Timeline / Cross-Agent Map UI tiles** — Phase 2

---

## Closing reminder

Ship-it-whole means whole-as-a-platform-agnostic-product, not whole-as-an-OpenClaw-clone. The six decisions in this document calibrate that line — skills included because they're platform-agnostic and solve the same problem; wishlist excluded because formal requests absorb its function; push channel reframed because the async-sidecar pattern is OpenClaw-architecture-specific and Claude Code needs a different implementation to achieve the same user-facing result.

The fix block is not scope creep — it's catching promises before UI work commits to rendering them. Operational-first discipline. Close the gaps, render the truth, soak the result.

Good luck with Fix Day 1.
