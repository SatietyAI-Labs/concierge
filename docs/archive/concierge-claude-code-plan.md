# Concierge — Claude Code Execution Plan
### The assessment-through-build-plan protocol

This document is written **for Claude Code** to follow end-to-end. Lewie will hand it to you and you'll work through the phases in order, producing a specific set of deliverable files in the `planning/` folder.

**You are not writing production code during this plan.** You are inventorying, classifying, mapping, and planning. The output of this protocol is a complete build plan Lewie can execute during the hackathon week starting April 21, 2026.

If you skip ahead to code, you've failed the mission. The archaeology is the point.

---

## Mission Context (read first)

Lewie is building **Concierge**: a platform-agnostic tool awareness layer for AI agents. He has existing, working code in `_legacy/openclaw/` that partially implements what Concierge needs, but it's entangled with OpenClaw-specific assumptions. Your job is to figure out exactly what he has, map it against the target architecture in `docs/concierge-blueprint.md`, and produce a build plan that maximally reuses existing work while reaching the platform-agnostic goal.

The components he has built and running, in rough order of how much effort they represent:

1. **Semantic Memory MCP** — based on Claude's own semantic memory MCP, forked and modified to always-load at boot and integrate across his OpenClaw system. Used by both OpenClaw generally and his tool concierge specifically.
2. **Beta Tool Concierge** — built for OpenClaw. Unknown exact scope; likely includes some version of tool recommendation and possibly lifecycle tracking.
3. **MCP Load/Unload Mechanism** — his workaround for OpenClaw's "reboot to unload" problem. Hot-swap capability for MCP servers mid-session.
4. **OpenClaw itself** — the agent harness Moltbot runs on. Not something you'll refactor, but understanding its tool-loading conventions is necessary context.
5. **Moltbot architecture** — TOOL-MANIFEST.md, SKILL.md, SOUL.md components for agent tool-awareness.

You'll discover more as you go. Don't assume this list is complete.

---

## Ground rules

1. **Read-only against `_legacy/`.** Do not modify any file inside `_legacy/openclaw/`. If you need to experiment with a file, copy it into `planning/scratch/` first.
2. **Cite file paths for every claim.** "The semantic memory MCP stores events in SQLite" is not acceptable. "The semantic memory MCP stores events in SQLite — see `_legacy/openclaw/semantic-memory/src/store.py:47`" is acceptable.
3. **Honesty beats optimism.** If a component is messier or more coupled than Lewie remembers, say so. If you're not sure what a file does, say "unclear" and move on — don't invent a description.
4. **Flag coupling explicitly.** When you find OpenClaw-specific imports, paths, env vars, or assumptions inside what should be platform-agnostic logic, note the exact location.
5. **One phase at a time.** Complete each phase's deliverable before starting the next. After finishing a phase, stop and summarize what you found. Lewie may want to discuss before you continue.
6. **Ask before assuming.** If the user's intent is ambiguous, stop and ask rather than guessing.

---

## Phase A — Inventory (Archaeology)

**Goal:** Produce a complete, accurate map of what exists in `_legacy/openclaw/`.

**Do not classify, refactor, or judge in this phase.** Just describe what's there.

### A.1 Top-level survey

Walk the tree of `_legacy/openclaw/`. For each subdirectory at depth 1-3:

- Record the path
- One-sentence purpose (read the README if there is one; otherwise infer from code)
- Language / framework
- Rough size (file count, LOC approximation)
- Last modified date of the most recent file

### A.2 Component deep-read

For each of these components (confirmed or discovered), actually read the code and produce a detailed description:

**A.2.1 — Semantic Memory MCP**
- Entry point file
- Storage backend (SQLite? Vector DB? Flat files?)
- What it stores (events? derived state? embeddings?)
- How it's invoked (stdio MCP server? HTTP? Always-running daemon?)
- What OpenClaw-specific assumptions exist (config paths, env vars, metadata fields)
- What interface it exposes (list all exposed tools/methods with signatures)

**A.2.2 — Beta Tool Concierge**
- Entry point file
- What does it actually do today? (Trace a typical invocation start-to-finish.)
- Does it have a tool catalog? Where is it stored?
- Does it do recommendation? How?
- Does it have lifecycle tracking? What states?
- Does it use the semantic memory MCP? How?
- What OpenClaw-specific assumptions exist?

**A.2.3 — MCP Load/Unload Mechanism**
- Entry point file(s)
- How does it actually load an MCP server? (Spawn process? Modify config? Send notification?)
- How does it unload? (Signal? Kill? Graceful shutdown?)
- What state does it track (active servers, pids, ports)?
- Where does it break or degrade? (Known limitations from code comments or structure.)
- What's the OpenClaw-specific part vs. what could be generic?

**A.2.4 — Moltbot tool-awareness (TOOL-MANIFEST / SKILL / SOUL)**
- Location of each file
- Format (markdown? YAML? code?)
- What they actually contain
- Who reads them (OpenClaw? Tool concierge? Semantic memory?)
- How they get updated (manual? automated?)

**A.2.5 — Anything else you find**
If you discover components not on this list, add an A.2.X section for each one.

### A.3 Deliverable

Write `planning/inventory.md` with:
- Tree of `_legacy/openclaw/` at depth 2 with one-line purposes
- Full deep-read of each component from A.2
- A "Surprises" section at the end: things you found that Lewie probably doesn't remember or didn't mention
- A "Questions" section: things you need Lewie to clarify before moving on

**Stop after writing this file and summarize your top 5 findings in chat.** Wait for Lewie to review before starting Phase B.

---

## Phase B — Map to Architecture

**Goal:** For each existing component, identify which Concierge blueprint component it maps to.

The blueprint architecture (from `docs/concierge-blueprint.md`) has these core components:
- **Catalog Service** — source of truth for all tools
- **Recommendation Engine** — Opus 4.7-driven tool-surfacing
- **Memory Service** — event log + derived state for lifecycle
- **Loader/Proxy Layer** — harness-specific tool load/unload
- **Concierge Agent Interface** — how agents talk to Concierge (pull + push)
- **Lifecycle State Machine** — pending/used/loaded-on-boot/retired
- **UI/Dashboard** — optional v1, valuable long-term

### B.1 Mapping table

Build a table: one row per existing component (from Phase A), one column per blueprint component. Mark cells:
- **FULL** — this existing piece largely implements this blueprint component
- **PARTIAL** — this existing piece implements some of this blueprint component
- **ASSIST** — this existing piece could support this blueprint component but doesn't implement it
- **—** — no relationship

### B.2 Narrative mapping

For each existing component, write a paragraph explaining:
- Which blueprint component(s) it maps to
- What's already there vs. what would be missing for a full implementation
- Whether the mapping is clean or coupled (is this piece mostly platform-agnostic logic with some OpenClaw wrapping, or is it deeply OpenClaw-flavored?)

### B.3 Deliverable

Write `planning/architecture-map.md` containing the table from B.1 and the narrative from B.2. Stop and summarize in chat.

---

## Phase C — Classify

**Goal:** For each existing component, make a hard decision about what to do with it.

### C.1 Classification options

Each component must be classified as exactly one of:

- **LIFT** — use as-is, just point it at the new project structure. Minimal changes.
- **EXTRACT** — pull the core platform-agnostic logic out, leave the OpenClaw wrapping behind. The extracted code goes into `core/`; the OpenClaw-specific wrapping becomes part of `adapters/openclaw/`.
- **ADAPT** — needs meaningful modification to fit the new architecture. Rewrite interfaces, possibly restructure internals, but keep the core algorithm.
- **REWRITE** — too tangled or too different from blueprint; faster to redo from scratch. Existing code becomes reference, not source.
- **RETIRE** — not needed in the new architecture. Document what it did and move on.

### C.2 Decision justification

For each classification, give 2-4 sentences of justification:
- What makes this the right call (not the others)?
- What's the main risk of this choice?
- Estimated effort in hours (roughly) to execute the chosen path during hackathon week.

### C.3 Decision hygiene

- If you classify something as REWRITE, explicitly say why EXTRACT or ADAPT won't work.
- If you classify something as LIFT, prove it isn't secretly coupled (cite specific files you checked).
- If total estimated effort across all non-RETIRE components exceeds 40 hours, flag it. That's too much for a week; something needs to be scoped down.

### C.4 Deliverable

Write `planning/classification.md` containing:
- A one-page summary table: component → classification → effort estimate
- Full justifications per component
- A "Scope risk" section if totals are too high
- A "Questions for Lewie" section for any classifications you're uncertain about

Stop and summarize in chat. **This is the highest-stakes phase — do not rush it.** Lewie should review this carefully before you continue.

---

## Phase D — Dependency Graph

**Goal:** Determine build order for the hackathon week.

### D.1 Draw the graph

For every component in the new architecture (blueprint components, plus any adapter or UI work), identify:
- What does it depend on? (What must exist before this can work?)
- What depends on it? (What breaks if this isn't ready?)

Produce either:
- A mermaid diagram in markdown, OR
- A structured list showing dependencies

### D.2 Identify the critical path

The critical path is the longest chain of dependencies from empty repo to a working demo. Identify it explicitly. This is what drives your day-by-day plan in Phase F.

### D.3 Identify parallel work

Anything not on the critical path can be built in parallel or deferred. Call these out explicitly so Lewie knows what to cut first if time runs short.

### D.4 Deliverable

Write `planning/dependency-graph.md` with the graph, critical path, and parallel-work list. Stop and summarize.

---

## Phase E — Gap Analysis

**Goal:** Identify everything the blueprint requires that doesn't exist yet in any form.

### E.1 The gap list

For every blueprint component not fully covered by existing code (anything not marked FULL in Phase B), list:
- What specifically is missing
- Whether it's a small addition or a major build
- Whether it's on the critical path (from Phase D)
- Rough effort estimate

### E.2 "New features" vs. "reused features"

The hackathon pitch emphasized several capabilities. For each, determine whether existing code supports it or whether it's genuinely new work:

- Proactive tool recommendation (pulling Claude into the agent's context before it gets stuck)
- Lightweight-first preference (CLI and HTTP APIs as peers to MCP servers in the catalog)
- Lifecycle state machine (pending → used → loaded-on-boot → retired) with actual promotion/retirement logic
- Cross-harness memory (same Concierge brain serving OpenClaw and Claude Code)
- UI/dashboard

For each, mark existing coverage (none / partial / full) and effort to complete.

### E.3 Deliverable

Write `planning/gap-analysis.md`. Stop and summarize.

---

## Phase F — Build Plan

**Goal:** A concrete, day-by-day plan for the hackathon week (April 21-26, 2026) that Lewie can execute.

### F.1 Constraints

- Solo builder
- 6 working days: Tuesday April 21 through Sunday April 26
- Real sleep required. Plan for 8-10 productive hours per day, not 16.
- Must produce a demo-able system by the end of Day 6, not a theoretically-complete one.
- One clean demo scenario > ten half-working features.
- Existing code must be reused wherever possible (per classifications in Phase C).

### F.2 Structure

For each day, produce:
- **Primary goal** (one sentence)
- **Concrete tasks** (bulleted, each task estimated in hours)
- **Deliverable at end of day** (what working thing exists)
- **If behind schedule, cut:** (what drops first)

### F.3 Hackathon-week plan skeleton

Use this structure but adjust based on what you learned in Phases A-E:

**Day 1 (Tuesday April 21) — Foundation and Lift/Extract**
- Set up core/ repo scaffolding with interfaces from blueprint
- Execute all LIFT classifications (move code into new structure)
- Begin EXTRACT work on semantic memory MCP (or whatever's highest on critical path)
- End-of-day deliverable: core structure in place, lifted components wired in

**Day 2 (Wednesday April 22) — Extract and Adapt core components**
- Complete extractions started Day 1
- Execute ADAPT classifications for catalog and memory services
- Deliverable: catalog service and memory service functional in new core

**Day 3 (Thursday April 23) — Recommendation Engine**
- Build the new Opus 4.7-driven recommendation layer
- Wire in lightweight-first preference policy
- Deliverable: given a catalog and an agent task, Concierge returns ranked recommendations

**Day 4 (Friday April 24) — Claude Code Adapter**
- Build the Claude Code harness adapter
- Wire up load/unload against real MCP servers
- Deliverable: Claude Code session can hot-swap tools driven by Concierge

**Day 5 (Saturday April 25) — Lifecycle + Integration**
- Implement lifecycle state machine promotion/retirement logic
- End-to-end integration test: real task, real tools, real state transitions
- Begin UI/dashboard (if on track)
- Deliverable: one full end-to-end demo scenario works reliably

**Day 6 (Sunday April 26) — Polish, Record, Submit**
- UI polish (if applicable)
- Record 3-minute demo video
- README, project description, submission materials
- Deliverable: submitted hackathon project

Adjust this skeleton based on what you actually found. If a classified EXTRACT is bigger than expected, front-load it. If the MCP load/unload code is cleaner than expected and lifts directly, pull Day 4 tasks earlier.

### F.4 Demo scenario

The blueprint already proposes a demo scenario (Postgres mid-session swap + curl+grep lightweight win + cross-session lifecycle). Validate it's achievable given the classifications. If not, propose a scaled-down alternative.

### F.5 Risk register

Identify the top 3-5 risks that could blow up the week. For each:
- What the risk is
- Likelihood (low/med/high)
- Impact if it happens
- Mitigation or fallback plan

### F.6 Deliverable

Write `planning/build-plan.md` containing the full week plan, demo scenario validation, and risk register. This is the capstone document — Lewie takes this into the hackathon as his source of truth.

---

## Final Summary

After completing Phase F, produce one last document: `planning/executive-summary.md`

It should be one page, readable in 3 minutes, containing:
- **What I have** — 2-3 sentence summary of existing assets
- **What I'm building** — 2-3 sentence description of Concierge v1
- **How I'll reuse vs. build new** — short table
- **Day-by-day headlines** — one line per day from the build plan
- **Top risks** — 3 bullets from the risk register
- **First action tomorrow morning** — one concrete task Lewie does first when the hackathon opens

This is the document Lewie reads Monday night before bed and Tuesday morning before starting.

---

## Operational notes for Claude Code

- **Preserve momentum.** After each phase, briefly summarize what you produced and ask if Lewie wants to continue or pause. Don't wait indefinitely if he's not actively responding — move forward with reasonable defaults and flag assumptions.
- **Keep planning docs concise.** Each deliverable should be readable in 10 minutes or less. Detail belongs in appendices.
- **When you're unsure, ask.** Lewie explicitly prefers concrete over abstract; if a phase requires a judgment call he should be making, surface it as a question rather than guessing.
- **Cite file paths always.** Every specific claim about existing code should include a path.
- **Don't sanitize.** If existing code is messy or coupled, say so plainly. Lewie needs to hear the truth, not the polite version.
- **Respect the read-only boundary.** `_legacy/` is sacred during assessment. No writes, no modifications, no "just cleaning up this one thing."

Start with Phase A when Lewie gives you the go-ahead.
