# Concierge — Claude Code Execution Plan (v3)
### Codification, classification, and build-plan production with operations protocol integrated

This document is written for Claude Code to follow end-to-end. It supersedes
the v1 and v2 execution plans by integrating the operations protocol from
`planning/concierge-operations-protocol.md` at every phase boundary.

Read CLAUDE.md, the operations protocol, and the v2 blueprint in full before
starting Phase A.

---

## What changed from v2

The v2 plan had the right phase structure but didn't address the
**operational mechanics** of working across multiple sessions and days. v3
adds:

- Explicit session boundaries within each phase
- Standard handoff snapshot procedure at the end of every session
- Decision logging integrated into every phase
- Daily rhythm baked into the build week
- Phase-by-phase checkpoint criteria
- Recovery procedures referenced at appropriate breakpoints

The optimization priority is **AI quality**, not token conservation. Use
xhigh or max effort throughout. Generous tool calls, thorough grounding,
parallel exploration on hard decisions — all on the table.

---

## Mission context (read first)

Lewie has built a fully-designed, production-running tool concierge system
inside OpenClaw. The hackathon work is to **extract** the core into a
platform-agnostic service, **build** a Claude Code adapter, and **build** a
real operator UI.

OpenClaw adapter is **out of scope** for hackathon week. Phase 2 work.

The v2 blueprint document `planning/concierge-blueprint-v2.md` has the full
architecture map and the honest "what's lifted vs. what's new" table.

The operations protocol document `planning/concierge-operations-protocol.md`
governs how sessions, handoffs, and decisions work. Reference it
constantly.

---

## Ground rules (operational)

1. Every session ends with a handoff snapshot at
   `planning/sessions/SESSION-YYYY-MM-DD-NN.md`. Non-negotiable.
2. Every architectural decision gets logged to
   `planning/decisions/DECISIONS.md`.
3. Every session starts by reading the most recent snapshot, CLAUDE.md (if
   not already in context), and the day's plan in `planning/today.md`.
4. Soft session limits: 6 hours active OR 70% context. Hard limits: 8
   hours OR 85% context.
5. Effort: `xhigh` default. `max` for Phase C, Phase F, and any
   architectural decision mid-build.
6. Cite file paths for every claim about existing code.
7. `_legacy/` is read-only.
8. Ask when unsure.

---

## PHASE A — Codification

**Goal:** Produce a complete, file-path-accurate map of the existing
Concierge implementation in OpenClaw. We know what's there; this phase
confirms exactly where it lives.

**Estimated sessions:** 1-2 sessions, ~3-5 hours total.

**Effort:** `xhigh`.

### A.1 Top-level survey

Walk `_legacy/` at depth 1-3. For each directory record path,
one-sentence purpose, file count.

### A.2 Component-by-component file location

For each Concierge component, find the actual file(s) and record exact
paths:

- A.2.1 Tool Manifest (TOOL-MANIFEST.md)
- A.2.2 Recommendation Behavior (SKILL.md / tool-awareness.md)
- A.2.3 SOUL.md additions
- A.2.4 Three-folder lifecycle (pending/, resolved/, archived/)
- A.2.5 Cron housekeeping script
- A.2.6 Tool catalog data file (TOOL-CATALOG.md)
- A.2.7 Shell tool functions (tool-functions.sh)
- A.2.8 Wishlist log (tool-wishlist.md)
- A.2.9 Semantic Memory MCP server code
- A.2.10 MCP Bridge plugin
- A.2.11 Beta Tool Concierge code (the ToolConcierge repo) — pay
        special attention to MCP load/unload mechanism
- A.2.12 Anything else discovered

### A.3 Surprise findings

Document anything that diverges from the overview document or adds
capability not previously known.

### A.4 Open questions

List anything needing Lewie's input.

### A.5 Deliverable

Write `planning/inventory.md`. Stop.

### Phase A checkpoint

Before moving to Phase B, verify all items below:

- [ ] `planning/inventory.md` exists
- [ ] Every component from the v2 blueprint mapped to a file path (or
      marked "not found" with explanation)
- [ ] Cron housekeeping script located and documented
- [ ] Beta tool concierge MCP load/unload code located and documented
- [ ] Top 5 findings summarized in chat
- [ ] Open questions reviewed by Lewie

### Session handoff

Write the SESSION snapshot. Append any decisions made (including "decided
to mark X as not-found because we couldn't locate it") to DECISIONS.md.

---

## PHASE B — Architecture Mapping

**Goal:** For each existing component, identify which v2 blueprint
component(s) it maps to, and what the gap is to hackathon target state.

**Estimated sessions:** 1 session, ~2-3 hours.

**Effort:** `xhigh`.

### B.1 Mapping table

For each existing component from Phase A, identify:
- Which v2 blueprint component(s) it implements
- How completely (full / partial / supports but doesn't implement)
- What's missing for hackathon target

### B.2 Claude Code adapter gap

Specifically map:
- What's needed to load/unload MCP servers in a Claude Code session
- Which existing OpenClaw load/unload code can inform this work
- What's genuinely new vs. patterned-after-existing

### B.3 UI gap

Map:
- What data each of the three planned UI sections needs
- Which existing components that data lives in
- What new API endpoints are required to serve the UI

### B.4 Deliverable

Write `planning/architecture-map.md`. Stop.

### Phase B checkpoint

- [ ] `planning/architecture-map.md` exists
- [ ] Every existing component mapped to one or more blueprint components
- [ ] Claude Code adapter gap fully specified
- [ ] UI gap fully specified per section
- [ ] Lewie has reviewed before Phase C

### Session handoff

Write the SESSION snapshot. Append decisions to DECISIONS.md.

---

## PHASE C — Classify

**Goal:** Make hard decisions about what to do with each existing component
during hackathon week.

**Estimated sessions:** 1 dedicated session, ~3-4 hours.

**Effort:** `max`. This is the highest-stakes planning decision. Burn the
cycles.

### C.1 Classification options

- **LIFT** — use as-is, point at it from new structure
- **EXTRACT** — pull platform-agnostic core into `core/`, leave OpenClaw
  wrapping in `_legacy/`
- **ADAPT** — needs modification to fit new architecture
- **REWRITE** — too tangled or different; faster to redo (should be rare)
- **RETIRE** — not needed in new architecture

### C.2 Per-component classification

For each existing component:
- Pick exactly one classification
- Justify in 2-4 sentences
- Estimate hours of effort during hackathon week
- Note which day of the build plan it should land on

### C.3 New-build sizing

For the three genuinely new things:
- Claude Code adapter (estimated hours)
- FastAPI core service (estimated hours)
- UI with three sections (estimated hours)

Sanity check totals. If non-RETIRE classifications + new builds exceed 50
hours, flag scope risk and propose what to cut.

### C.4 Deliverable

Write `planning/classification.md`. Stop.

### Phase C checkpoint

- [ ] `planning/classification.md` exists
- [ ] Every existing component has exactly one classification
- [ ] Effort estimates totaled and sanity-checked
- [ ] Scope risk flagged if total exceeds 50 hours
- [ ] Lewie has reviewed and signed off

### Session handoff

Critical to log decisions thoroughly here. Every classification is a
decision worth preserving with full reasoning. Future-you will thank
present-you on Day 4.

---

## PHASE D — Dependency Graph

**Goal:** Determine build order for hackathon week.

**Estimated sessions:** 1 session, ~1-2 hours.

**Effort:** `xhigh`.

### D.1 Component dependencies

For every component (existing extracted + genuinely new):
- What does it depend on?
- What depends on it?

### D.2 Critical path

Identify longest dependency chain from empty repo to working demo.

### D.3 Parallel work

Identify what can be built in parallel or deferred.

### D.4 Deliverable

Write `planning/dependency-graph.md`. Stop.

### Phase D checkpoint

- [ ] `planning/dependency-graph.md` exists
- [ ] Critical path identified
- [ ] Parallel work and deferrable items called out

---

## PHASE E — Gap Analysis

**Goal:** Confirm everything the hackathon target requires has a clear
build path.

**Estimated sessions:** 1 session, ~1-2 hours.

**Effort:** `xhigh`.

### E.1 Capability checklist

For each capability the demo needs:
- Tool Registry rendering with packs
- Pending Requests Inbox with approve/deny buttons
- Health/Stats bar
- Claude Code session can call recommend endpoint
- Claude Code session can have MCP server loaded mid-session
- Lightweight-first preference applied in recommendations
- Discovery engine produces a new tool suggestion
- Approval triggers autonomous install
- Cron picks up status change

For each: existing coverage + estimated effort to complete.

### E.2 Risk surface

Top 5 things most likely to go wrong during build week. Knowing where bugs
are likely helps allocate Day 5 bug-fix time.

### E.3 Deliverable

Write `planning/gap-analysis.md`. Stop.

### Phase E checkpoint

- [ ] `planning/gap-analysis.md` exists
- [ ] Every demo capability has clear coverage status
- [ ] Top 5 risks documented

---

## PHASE F — Build Plan

**Goal:** Day-by-day plan for the hackathon week (April 21-26, 2026).

**Estimated sessions:** 1 dedicated session, ~3-4 hours.

**Effort:** `max`. Capstone planning document.

### F.1 Constraints

- Solo builder
- 6 working days, 10-12 hours/day with diminishing returns by Day 4
- Substantive completion target: end of Day 4 (Friday)
- Days 5-6 explicitly for stabilization, demo rehearsal, recording
- Lewie has never built a UI; lean on Claude Code scaffolding + prefab
  CSS defaults
- OpenClaw adapter OUT of scope
- Daily rhythm and session protocol per ops protocol

### F.2 Day-by-day skeleton

For each day produce:
- Primary goal (one sentence)
- Concrete tasks (bulleted, hours estimated)
- Session structure (how many sessions, what each one does)
- End-of-day deliverable (what working thing exists)
- Phase checkpoint criteria (the items below)
- If behind, cut: (what drops first)

### F.3 Hackathon-week skeleton (refine based on Phases A-E)

**Day 1 (Tuesday) — Core scaffold + extract catalog**
- Session 1 (morning, ~4h): FastAPI project skeleton in `core/`. SQLite
  store schema. Lift TOOL-MANIFEST.md into the SQLite store with markdown
  export preserved. Generalize schema to remove OpenClaw-specific fields.
- Session 2 (afternoon, ~4h): Catalog API endpoints (GET /tools,
  GET /tools/{id}, GET /packs). Wire to SQLite store. Smoke tests.
- End-of-day deliverable: catalog API endpoints respond with real data.
  Lewie can curl GET /tools and see the catalog.

**Day 2 (Wednesday) — Memory + recommendation + lifecycle endpoints**
- Session 1 (morning, ~4h): Memory service API wrapper around the
  existing semantic memory MCP. Endpoints to query memory by task
  context.
- Session 2 (afternoon, ~4h): Recommendation engine endpoint
  (POST /recommend) using Opus 4.7. Lifecycle API endpoints
  (GET /requests/pending, POST /requests/{id}/approve).
- End-of-day deliverable: API can return recommendations, list pending
  requests, approve a request (cron picks it up).

**Day 3 (Thursday) — Claude Code adapter**
- Session 1 (morning, ~4h): MCP load/unload mechanism for Claude Code
  sessions. Integration with existing patterns.
- Session 2 (afternoon, ~4h): Gap report injection (proactive push of
  recommendations). Recommendation pull mechanism.
- End-of-day deliverable: Claude Code session uses Concierge for at
  least one end-to-end task scenario.

**Day 4 (Friday) — UI build (substantive completion target)**
- Session 1 (morning, ~5h): FastAPI templates + Pico.css setup. Tool
  Registry section: hierarchical list with packs and sub-tools.
- Session 2 (afternoon, ~4h): Pending Requests Inbox section (HTMX
  approve/deny buttons). Health/Stats bar.
- Session 3 (evening, ~2h): Connect UI to API. End-to-end integration
  test (Claude Code triggers request → appears in UI → approval triggers
  install).
- End-of-day deliverable: UI loads in browser, all three sections
  functional, end-to-end demo passes once.

**Day 5 (Saturday) — Bug fixes + demo rehearsal**
- Session 1 (morning, ~3h): Stabilize anything flaky from Days 1-4.
- Session 2 (afternoon, ~3h): Run demo scenario start-to-finish 5+
  times. Identify and fix rough edges.
- Session 3 (evening, ~2h): Polish — titles, labels, error states, empty
  states.
- End-of-day deliverable: 5 consecutive clean demo runs.

**Day 6 (Sunday) — Demo recording, README, submit**
- Session 1 (morning, ~2h): Record 3-minute demo video, multiple takes.
- Session 2 (afternoon, ~2h): Write README, submission description, final
  cosmetic polish.
- Submit by mid-afternoon. Buffer remains for last-minute fixes.

### F.4 Demo scenario validation

Confirm v2 blueprint demo scenario is achievable. If not, propose scaled-
down alternative.

### F.5 Risk register

For each of top 5 risks from Phase E:
- Likelihood
- Impact
- Mitigation or fallback

### F.6 Daily rhythm reminder

The plan assumes the daily rhythm from ops protocol:
- Morning: read snapshots, update today.md, brief alignment session
- Build blocks: 2-3 sessions per day, 3-6 hours each
- Midday checkpoint: 15 min skim
- Evening close: write tomorrow's first action
- Hard stop: 9pm

### F.7 Deliverable

Write `planning/build-plan.md`. This is the capstone document Lewie takes
into the hackathon as his source of truth.

### Phase F checkpoint

- [ ] `planning/build-plan.md` exists
- [ ] Day-by-day plan produced with session structure
- [ ] Demo scenario validated
- [ ] Risk register complete
- [ ] All daily checkpoint criteria specified

---

## Final summary document

After Phase F, produce one last document:
`planning/executive-summary.md`

One page, readable in 3 minutes:
- What I have (existing system summary)
- What I'm building (hackathon scope)
- What's getting lifted vs. built new (short table)
- Day-by-day headlines from the build plan
- Top 3 risks
- First action Tuesday morning

This is what Lewie reads Monday night and Tuesday morning before the
hackathon starts.

---

## Build week — checkpoint criteria per day

These are referenced in F.2 above. Repeated here for explicit review at
each day's end:

### Day 1 (Tuesday)
- [ ] Catalog API `GET /tools` returns JSON from SQLite store
- [ ] Lewie can curl the endpoint
- [ ] Day 1 SESSION snapshot written

### Day 2 (Wednesday)
- [ ] `POST /recommend` returns ranked recommendations for sample task
- [ ] `GET /requests/pending` lists pending requests
- [ ] `POST /requests/{id}/approve` updates status line in markdown file
- [ ] Cron picks up status change and moves the file
- [ ] Day 2 SESSION snapshot written

### Day 3 (Thursday)
- [ ] Claude Code session can call `POST /recommend`
- [ ] Claude Code session can have MCP server loaded mid-session
- [ ] Gap report injection works
- [ ] One end-to-end task scenario demonstrated working
- [ ] Day 3 SESSION snapshot written

### Day 4 (Friday) — Substantive completion
- [ ] UI loads in browser at localhost
- [ ] Tool Registry shows packs and sub-tools, expandable
- [ ] Pending Requests Inbox renders, approve/deny buttons work
- [ ] Health/Stats bar displays live data
- [ ] End-to-end demo passes start to finish at least once
- [ ] Day 4 SESSION snapshot written

### Day 5 (Saturday)
- [ ] Demo scenario passes 5 consecutive runs
- [ ] Top 3 bugs from Day 4 fixed
- [ ] UI polish complete
- [ ] Day 5 SESSION snapshot written

### Day 6 (Sunday)
- [ ] Demo video recorded
- [ ] README written
- [ ] Submission complete

---

## Operational notes

- After each phase, summarize the deliverable in chat and ask if Lewie
  wants to continue or pause.
- Keep planning docs concise. Each deliverable should be readable in 10
  minutes or less.
- Cite file paths always.
- Don't sanitize. If existing code is messier than the overview suggests,
  say so plainly.
- Respect the read-only boundary. `_legacy/` is sacred during planning.
- Follow the operations protocol consistently.

Start with Phase A when Lewie gives the go-ahead. Begin every Phase A
session by reading CLAUDE.md, the operations protocol, the v2 blueprint,
and this v3 plan in full.
