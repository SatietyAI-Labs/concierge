# Concierge — Architectural Decisions Log

Append-only log of architectural and scope decisions made during the
Concierge build. Newest entries at the bottom. See
`docs/concierge-operations-protocol.md` for the full entry template and
the when-to-log criteria.

A decision belongs here when ANY of:
- It affects more than one file
- It affects how a future session will think about something
- It would be hard to remember in 3 days
- It traded off two reasonable alternatives

Routine implementation choices do NOT go here.

---

## [2026-04-20 17:30] — Day-0 bootstrap: scaffolding, archival, naming, session numbering

**Context:** Pre-Phase-A setup. The v3 operations protocol assumes planning
scaffolding, a decisions log, and a daily plan file exist on Day 0, but they
didn't. Five pre-flight concerns surfaced in chat before Phase A could
start; Lewie confirmed all five together. One consolidated entry captures
the coordinated bootstrap rather than fragmenting into six near-trivial
entries.

**Options considered:**
- Log each of the six bootstrap actions as separate DECISIONS entries
- Log them as one consolidated entry (chosen)
- Skip logging since bootstrap is mechanical rather than architectural

**Decision:** Consolidate the following into this single entry:

1. **Symlink 6 created** — `_legacy/tool-requests/` →
   `/home/satiety/.satiety-pipeline/outbox/tool-requests/`. Direct shortcut
   to the actual three-folder lifecycle implementation
   (pending/resolved/archived) flagged in CLAUDE.md v3 as the authoritative
   lifecycle store.
2. **Symlink 7 created** — `_legacy/openclaw-root/` →
   `/home/satiety/.openclaw/`. Broader read-only view of the OpenClaw
   runtime to cover cron scripts, MCP servers, memory store, agents, and
   logs that live outside `workspace/`. Without this, Phase A's checkpoint
   requirements (locate cron housekeeping, locate beta tool concierge MCP
   load/unload) would likely have been unsatisfiable.
3. **Planning scaffolding created** — `planning/sessions/`,
   `planning/decisions/`, `planning/scratch/`, `planning/test-fixtures/`.
   Required by ops protocol as the operating substrate for the build week.
4. **Superseded docs archived** — `concierge-blueprint.md`,
   `concierge-claude-code-plan.md`, `concierge-setup-directions.md` moved
   from `docs/` to `docs/archive/` with an `ARCHIVED.md` index. Live
   `docs/` folder now unambiguously reflects the v2/v3 authoritative set
   so future sessions can't accidentally cite v1 as current.
5. **Phase-name clarification** — The v1 "Inventory / Archaeology"
   language is deprecated. The canonical phase name is "Codification"
   per v2/v3. The deliverable filename remains `planning/inventory.md`
   because "inventory" reads naturally for the *artifact* even when the
   *phase* is Codification.
6. **Session numbering** — Today's entire arc (framework re-read, pre-A
   bootstrap, and Phase A work) rolls into a single snapshot at
   `planning/sessions/SESSION-2026-04-20-01.md` written at end of session.
   No separate pre-A snapshot. This is one continuous `claude` session
   with no `/exit`, so a single snapshot preserves the linear narrative.

**Reasoning:** These are mechanical setup choices that affect every later
session (paths, filenames, canonical doc set) but aren't architecturally
contested. Consolidating preserves the Day-0 context in one place without
polluting the log. Separately-logged entries would fragment a single
coordinated bootstrap and make the log noisier than it needs to be on
Day 1.

**Reversibility:** Easy. Symlinks can be removed/recreated, archives can
be un-archived, directories can be renamed, naming can be revisited.

**Decided by:** Lewie (directive in chat after Claude Code flagged the
five concerns) + Claude Code (proposal and execution).

**Affects:** All future sessions (snapshot path, decisions log path,
today.md path); `_legacy/` layout (7 symlinks now, not 5); `docs/`
canonical set; Phase A deliverable naming.

---

## [2026-04-20 18:15] — Scope of satiety-pipeline clarified

**Context:** v1 CLAUDE.md described `satiety-pipeline/` (the folder) as the
tool lifecycle implementation. Phase A.1 top-level survey found this was
misframed: the parent `satiety-pipeline/` is a *content/publishing
pipeline* (alerts, drafts, linkedin-ready, posted, scheduled, research,
etc.), and the tool-concierge lifecycle lives *only* in the
`outbox/tool-requests/` subtree (pending/, resolved/, archived/). These
are two separate systems that happen to share a filesystem root.

**Options considered:**
- Treat `satiety-pipeline/` as the extraction surface (v1 framing)
- Treat `satiety-pipeline/outbox/tool-requests/` as the extraction surface
  (chosen)
- Migrate the tool-requests subtree out of `satiety-pipeline/` during the
  hackathon to physically separate the two systems

**Decision:** For Phases B/C/D/F, the extraction surface is
`satiety-pipeline/outbox/tool-requests/` *only*. The parent
`satiety-pipeline/` is out of scope for Concierge extraction — it is a
content-production pipeline that happens to host the tool-requests subtree
for historical/ergonomic reasons. The `_legacy/tool-requests/` symlink
already reflects this distinction and is the canonical handle for the
lifecycle store.

**Reasoning:** The lifecycle code (status transitions, archival, cron
housekeeping over pending/resolved/archived) operates on
`outbox/tool-requests/` exclusively. Lifting only that subtree keeps the
extraction clean and avoids entangling Concierge with Lewie's
content-production pipeline, which has its own lifecycle, cadence, and
operational concerns. Physical migration of the folder is deferred — the
symlink shortcut is sufficient scope signaling for the hackathon.

**Reversibility:** Easy. If a later phase finds code in the parent
pipeline that also affects tool lifecycle (e.g., a shared housekeeping
script operating on multiple outbox subtrees), we widen scope and log a
follow-up decision.

**Decided by:** Lewie (directive in chat after Claude Code surfaced the
misframing in A.1).

**Affects:** Phase B architecture-map extraction surface; Phase C LIFT vs.
EXTRACT classifications for lifecycle-related components; Phase F build
plan's reuse accounting; `_legacy/` scope guidance for all remaining
Phase A reads (ignore `satiety-pipeline/` siblings of `outbox/`).

---

## [2026-04-20 19:45] — Phase A close-out: six Q-A resolutions

**Context:** Phase A (Codification) delivered `planning/inventory.md`
with six open questions in section A.4. Lewie answered all six in chat
after reviewing the deliverable. Consolidated entry captures the
decisions and their reasoning so future sessions don't re-derive them.

**Decisions:**

1. **Q1 — 8th symlink for semantic memory MCP code.**
   DECISION: Added `_legacy/moltbot-memory-mcp/` →
   `/home/satiety/moltbot-memory-mcp/`. No symlink to the ChromaDB data
   directory (`.moltbot-memory-v2/`).
   REASONING: Phase B needs the server code accessible for file:line
   citations. Inventory scope covers code, not runtime data.

2. **Q2 — MCP Bridge plugin architecture status.**
   DECISION: Treat `MCP-BRIDGE-GUIDE.md` and `ALFRED-MCP-REFERENCE.md` as
   historical references only. Do not lift the bridge pattern.
   REASONING: Plugin code no longer exists on disk (dir is empty).
   Migration to native `mcp.servers` happened ~Apr 10. The guide's value
   is conceptual prior art, not deployable design.

3. **Q3 — Manifest vs. active-config drift in the demo.**
   DECISION: UI renders **active config** as source of truth. The manifest
   becomes the **wishlist/intent layer**. The gap between intent and
   active becomes an affordance: *"consider re-loading these dropped
   tools."* The demo explicitly calls this out rather than hiding it.
   REASONING: The drift surfaces tool myopia and recovery in a single
   scene — it is a Concierge-native feature surface, not an embarrassment
   to paper over. Phase B/F design the UI around active + (manifest -
   active) delta.

4. **Q4 — `toolconcierge/` drafting repo treatment.**
   DECISION: Keep as-is for hackathon week, read-only via symlink.
   Archive/consolidate post-hackathon.
   REASONING: Contains byte-identical copies of canonical scripts plus
   design drafts (worker-tool-escalation, phase-2-test-scenarios). Not
   worth disrupting during hackathon; worth cleanup afterward when the
   extraction is done.

5. **Q5 — Wishlist UI section for v1.**
   DECISION: Three v1 UI sections only — Tool Registry, Pending Requests
   Inbox, Health/Stats bar. Wishlist file is read by backend but not
   rendered. Phase 2 adds a Wishlist Patterns section when real traffic
   exists.
   REASONING: `tool-wishlist.md` has zero real entries. A section with
   nothing to render weakens the demo. Phase 2 addition is trivial once
   traffic accumulates.

6. **Q6 — `tool-discovery` / `tool-lifecycle` boot-load behavior.**
   DECISION: Defer to Phase B.1 mapping when the Recommendation Engine
   and Lifecycle State Machine components are reached. Revisit with the
   full mapping context.
   REASONING: Whether these skills should be boot-loaded in OpenClaw is
   orthogonal to whether their content feeds the Concierge core. The
   answer depends on the mapping, not on their current status.

**Reversibility:** All Easy except Q3 (affects UI design, but reversal is
a layout change, not a rebuild).

**Decided by:** Lewie (all six decisions in chat after reviewing Phase A
deliverable).

**Affects:** `_legacy/` layout (8 symlinks, not 7); Phase B treatment of
MCP Bridge (historical), manifest/config drift (surface as feature),
`toolconcierge/` (preserved), wishlist (deferred to Phase 2), discovery
and lifecycle skills (to be resolved in B.1); Phase F UI scope (three
sections, not four).

---

## [2026-04-20 21:00] — Schedule advance: Phase A + Phase B in a single session

**Context:** The v3 execution plan estimates Phase A at "1-2 sessions,
~3-5 hours" and Phase B at "1 session, ~2-3 hours" — a planned spread of
2-3 sessions. Both phases completed in a single continuous session on
2026-04-20, with Phase C explicitly deferred to 2026-04-21 at `max`
effort per Lewie's direction (fresh brain for the highest-stakes
classification decisions). The timing context matters for Phase F build
plan and is logged here rather than re-derived later.

**Options considered:**
- Treat as an incidental fact (not log)
- Log as a decision with scope implications for Phase F (chosen)

**Decision:** Capture the schedule advance and its scope implications so
Phase F treats them as inputs rather than rediscovering them.

**What shifted relative to the v3 plan's original assumptions:**
1. The originally-planned Phase A/B schedule assumed the v2 blueprint's
   framing — a substantial extraction across multiple significant
   components. Phase A corrected the framing: the "beta tool concierge"
   is **not a daemon** but a composition of bash + markdown + cron plus
   one 14 KB Python MCP server and one 52 LOC cron script.
2. Phase B's architecture map materially shrinks the new-build
   perimeter to three items:
   (a) FastAPI service skeleton + SQLite catalog
   (b) Claude Code loader/proxy
   (c) three-section UI
   Everything else is LIFT + thin wrap.
3. Day 1 of the hackathon week therefore starts with more capacity than
   the v3 plan's original "core scaffold + extract catalog" framing
   assumed. Phase F can either pull Day 1 goals tighter (leaving
   buffer for Days 4-6), or pull Day 3 Claude Code adapter work
   partially into Day 2.

**Reversibility:** N/A — this is a schedule/scope note, not a technical
choice. Guidance for Phase F, not a constraint.

**Decided by:** Lewie (requested the entry in chat after Phase B approval).

**Affects:** Phase F (build plan) day-by-day allocation; scope-risk
sanity checks in Phase C (non-RETIRE effort totals should be more
conservative than the v2-blueprint framing would have suggested).

---

## [2026-04-21 04:45] — Phase C effort level adjusted from max to xhigh

**Context:** The v3 execution plan (`docs/concierge-claude-code-plan-v3.md`
§Phase C and the ops protocol §Effort-level guidance) both call for `max`
effort on Phase C as "the highest-stakes planning decision." Morning
alignment session at `xhigh` reviewed the Phase A/B deliverables and the
Phase C task shape; Lewie revised the effort target downward to `xhigh`
based on observed output quality from the prior day and the actual shape
of the Phase C decision set.

**Options considered:**
- Run Phase C at `max` per the v3 plan's default — highest capability,
  deepest reasoning, but also the shape Opus 4.7 can over-think on
- Run Phase C at `xhigh` — deeper than `high`, just below `max`, matches
  the effort that produced sharp Phase B output yesterday (chosen)
- Run Phase C at `high` — lower than yesterday's Phase B effort, not
  considered (would be a quality regression)

**Decision:** Phase C runs at `xhigh`. If any specific classification
looks shallow on review, that individual classification can be bumped
to `/effort max` for a re-review pass.

**Reasoning:**
1. Phase B at `xhigh` produced excellent output yesterday — Q6
   resolution and the Claude Code adapter three-approach analysis were
   sharp. Same effort level, same caliber of output, is a reasonable
   expectation for Phase C.
2. Phase C is ~25 medium classifications rather than one large
   architectural decision. `max` shines on singular deep reasoning;
   it is the shape `max` tends to over-think on when applied to
   repetitive structured work.
3. Loop-risk with early Opus 4.7 at `max` is higher than the marginal
   quality gain justifies across a batch of classifications. Session-
   level cost of a loop in Phase C (redo-the-classification) is higher
   than the per-classification quality gain from `max`.

**Reversibility:** Easy. Any specific classification that reads shallow
on Lewie's review can be bumped to `/effort max` for a targeted
re-review pass — granular remediation, not a re-do of the whole phase.

**Decided by:** Lewie (directive in chat during morning alignment, after
Claude Code confirmed Phase C mission and questions).

**Affects:** Phase C execution (this session); ops protocol §Effort-level
guidance is a default, not a constraint — individual phase effort levels
can be adjusted case-by-case based on prior-session observed output
quality. Phase F's `max` default remains in force unless similarly
re-evaluated at the time.

---

## [2026-04-21 05:50] — Skill-extraction pattern: EXTRACT as prompt fragments (not pure Python, not ADAPT)

**Context:** Phase B (2026-04-20) established that `tool-discovery/SKILL.md`
and `tool-lifecycle/SKILL.md` are **authoritative algorithm specifications**
for the Recommendation Engine's discovery subcomponent and for the
Lifecycle State Machine, respectively (Phase B §B.4). Phase B stopped
at that framing without specifying how the extraction would physically
land in Concierge's code. Phase C §C.2 classified these two files —
plus `tool-awareness.md`, `tool-recommendation.md`, and SOUL.md root —
as **EXTRACT**, with the extraction mechanism described as "system-prompt
fragments" composed into `POST /recommend`'s Opus 4.7 call. That jump —
from "algorithm specs" to "prompt fragments" — is a load-bearing design
choice for the demo-critical Recommendation Engine and deserves an
explicit entry here so the Day 2-3 build sessions (whether run by Claude
Code or by Lewie) have the reasoning preserved and don't have to
re-derive it under time pressure.

Lewie flagged two concerns during Phase C signoff that prompted a
targeted re-review at `/effort max`:
1. **Split source of truth.** Recommendation logic lives partly in
   Python scaffolding and partly in markdown-extracted prompt strings.
   Skill-file updates post-hackathon require matching prompt-fragment
   updates, creating a drift risk.
2. **Translation subtlety.** The work of taking a markdown algorithm
   spec and composing it into an effective Opus system prompt is prompt
   engineering, not classical code extraction. The EXTRACT label might
   euphemize the subtlety and the risk.

The re-review considered three alternatives.

**Options considered:**

- **(a) EXTRACT as prompt fragments** (as originally classified in Phase
  C §C.2): skill markdown content becomes Python string constants
  composed into `POST /recommend`'s system prompt; Opus 4.7 reads the
  protocol and applies it to task + catalog + memory context.
- **(b) Pure EXTRACT (algorithm in Python)**: reimplement the 5-step
  protocol, the green/yellow/red signal table, promotion/demotion
  thresholds, and discovery search patterns as Python logic; demote
  Opus 4.7 to a "describe why" layer; ranking happens deterministically
  in code.
- **(c) ADAPT (reframe as hybrid)**: same mechanical work as (a) but
  labeled ADAPT to acknowledge the nontrivial translation from
  markdown spec to prompt fragment; honest about the transformation.

**Decision:** (a) — EXTRACT as prompt fragments — with structural
mitigations explicitly named in §C.2.2 row justifications and §C.5.3.

**Reasoning:**

*Why not (b):* three structural objections, each material.

1. **Effort blowout.** Rough estimate: 4-6h per skill × 4 skills =
   16-24h of net-new Python logic (vs. ~3h total in the EXTRACT
   classification). Grand total would jump from 46.5h to ~60h,
   crossing the red scope-cut threshold and requiring real cuts
   elsewhere.
2. **Discovery can't actually be pure Python.** `tool-discovery/SKILL.md`
   specifies behavior that is inherently LLM-ish or crawler-ish —
   "search for CLI tools that handle X domain," "filter by maintained-
   within-3-months signal." This doesn't collapse into a deterministic
   scoring function; it requires either another LLM call or a web-
   crawler subsystem. Either way, the result is still hybrid; (b)
   only eliminates the LLM for *some* of the four skills.
3. **Loses the pitch.** Concierge's demo narrative is "an AI thinking
   about your task and proposing better tools." A Python scoring-rules
   engine is fine but is not the pitch. Prompt-fragment composition is
   what makes Concierge a *thoughtful* recommender; heuristic ranking
   makes it a rule-based one. For a demo built with Opus 4.7, leaning
   into Opus-guided reasoning is the correct design.

*Why not (c):* mechanically identical to (a); rejected on vocabulary
grounds.

1. ADAPT in plan-v3 §C.1 means "the original file needs modification to
   fit new architecture." Here the original skill files are **not**
   modified — they stay in `_legacy/` untouched; a derived Python
   artifact is created.
2. Diluting the ADAPT bucket. If "nontrivial translation" pushes
   EXTRACT into ADAPT territory, the EXTRACT classification becomes
   small and arbitrary — every EXTRACT involves *some* translation
   work. The classifications lose discrimination power.
3. The honesty instinct behind (c) is correct and is absorbed into
   (a) via the structural mitigations below, not by relabeling.

*Why (a) with structural mitigations:*

1. The classification preserves plan-v3 vocabulary integrity: source
   file unchanged, derived artifact in `core/`, so it's EXTRACT.
2. The mitigations address Lewie's concerns without changing the
   classification label.
3. Effort estimate holds (~3h total across the four skills + #8),
   keeping the 46.5h total within the yellow band.
4. Phase 2's structural improvement path (build-time prompt
   generation from markdown) is named and deferred, not ignored.

**Structural mitigations (built into Day 2 build sessions):**

1. Each prompt-fragment Python constant lives in a dedicated module
   (`core/prompts/recommendation_system.py` or similar) with a per-
   constant header comment listing: (a) source skill file path within
   `_legacy/`, (b) byte range or section name drawn from, (c) date
   of last sync with the source, (d) a TODO pointing to the Phase 2
   build-time generation idea.
2. A single `SKILL_FRAGMENT_SYNC_LOG.md` inside `core/prompts/` tracks
   the sync status of each fragment against its source (manual, manual,
   manual — during hackathon week).
3. Naming convention on fragment constants encodes the source:
   `TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD`,
   `DISCOVERY_SIGNALS__FROM_TOOL_DISCOVERY_SKILL`,
   `LIFECYCLE_TAG_SCHEMA__FROM_TOOL_LIFECYCLE_SKILL`, etc. Verbose
   on purpose so drift is visible in grep.
4. If a skill file is updated post-hackathon, the sync step is
   explicit: "re-paste the updated section into the prompt-fragment
   constant, update the date-of-sync comment, note it in
   SKILL_FRAGMENT_SYNC_LOG.md." No magic.

**Phase 2 structural improvement path (named, deferred):**

A pre-commit hook or `make sync-prompts` target that reads the skill
files and generates the prompt-fragment module automatically, with
the byte-range slicing encoded in the source skill file (e.g., YAML
front-matter sections or HTML comment markers). Eliminates the drift
risk entirely. Not worth building during hackathon week; revisit
post-hackathon.

**Reversibility:** Easy. If Day 2 integration work reveals that prompt-
fragment composition underperforms for a specific skill (e.g., the
signal table doesn't translate well into prompt guidance), that
specific fragment can be promoted to Python logic with a targeted
re-review at `/effort max`. Per-fragment remediation, not a full
classification re-do.

**Decided by:** Lewie (flagged concerns in chat after Phase C summary;
requested `/effort max` re-review and explicit DECISIONS.md entry) +
Claude Code (re-review and proposal at `max`, then returning to
`xhigh` for the finalization edits).

**Affects:** Phase C classification.md rows #3, #4, #6, #7, #8 (skill
and SOUL extractions) — each gets an "Extraction-pattern note"
paragraph citing this decision; Phase C §C.5.3 "Unusual EXTRACTs"
section — elevated to reference this entry; Day 2 build sessions
(the structural mitigations above become concrete setup steps);
Phase 2 roadmap (build-time prompt generation added as a structural
improvement candidate).

---

## [2026-04-21 05:55] — Phase C approved; classification.md finalized; proceeding to Phase D

**Context:** Phase C — Classification was completed earlier in the
session (46.5h grand total, yellow-flag triggered, four Q&As answered,
max-effort re-review of the prompt-fragment EXTRACT pattern performed
with EXTRACT standing under structural mitigations). Lewie reviewed
the final deliverable and signed off. Phase-gate transition logged
here for traceability.

**Decision:** Phase C is approved. `planning/classification.md` is
final. Phase D — Dependency Graph begins next at `xhigh` effort,
producing `planning/dependency-graph.md` with the full component
dependency map, critical-path identification, and parallel-work /
deferrable callouts. Phase D halts at its checkpoint per plan-v3
for review before Phase E.

**Reasoning:** Phase C is the highest-stakes planning checkpoint per
plan-v3; explicit sign-off traceable in the decisions log satisfies
the ops-protocol requirement that phase gates be observable across
sessions. The sign-off affirms: (a) the 12 / 7 / 0 / 0 / 5 tally is
correct; (b) the prompt-fragment EXTRACT pattern holds; (c) the
pre-sequenced 4-cut ladder is the correct scope-pressure response;
(d) no further re-reviews are required.

**Reversibility:** Easy within Phase C deliverable scope (any
classification can still be bumped to `/effort max` re-review mid-
build if it reads shallow in Phase D/E/F context). The sign-off
itself is a procedural gate, not a technical commitment.

**Decided by:** Lewie (signoff message in chat) + Claude Code
(checkpoint update and this entry).

**Affects:** `planning/classification.md` §C.9 checkpoint
(Lewie-signoff box now checked); Phase D — Dependency Graph starts
this session at `xhigh` effort; ops protocol phase-gate audit trail
(Phase C → Phase D transition observable here).

---

## [2026-04-21 06:10] — Phase D approved; dependency-graph.md finalized; proceeding to Phase E

**Context:** Phase D — Dependency Graph completed mid-session.
Deliverable: `planning/dependency-graph.md` with 32 tracked build-
affecting items, topological day-by-day order, critical-path
identification (27.5h strict sequential of 46.5h total), parallel-
work analysis, four-cut ladder structural-safety verification, and
Phase E/F carry-forward notes. Lewie reviewed and signed off.
Phase-gate transition logged here for traceability, with two Phase F
carry-forward notes from the signoff message folded in.

**Decision:** Phase D is approved. `planning/dependency-graph.md`
is final. Phase E — Gap Analysis begins next at `xhigh` effort,
producing `planning/gap-analysis.md` with capability coverage,
top-5 risk surface, and build-path clarity for anything not fully
covered. Phase E halts at its checkpoint per plan-v3 for review
before Phase F.

**Phase F carry-forward notes from Phase D signoff (to be honored
in build-plan.md):**

1. **Day 3 overflow mitigation — pull N10 (stdio proxy shim, 4h)
   into Day 2 evening** if Day 2 runs fast. Dependency graph permits
   this pull-forward (D.3.2).
2. **Parallelism realism in Day 2.** The nominal "N5 memory wrapper
   parallel with X3/X4/X6/X7 prompt-fragment extracts" involves
   very different cognitive modes (Python API writing vs. markdown-
   to-constant translation). Solo-builder context-switching cost
   likely makes sequential back-to-back faster than parallel. Phase
   F's Day 2 plan should present these as sequential blocks, not
   parallel claims, even though the dependency graph permits the
   parallelism.
3. **Day 4 three-UI-branch.** Phase D already flagged as "closer
   to sequential" in solo-builder realism (§D.5 risk #5). Phase F
   should honor this framing; do not restate theoretical
   parallelism that overpromises wall-clock savings.

**Reasoning:** Phase D sign-off affirms: (a) the critical-path
shape is correct; (b) ladder-integrity check (no cut breaks the
critical path) holds; (c) protected demo floor of 17 items /
26-28h gives Phase F a concrete target to guard; (d) Day-3
allocation stays deferred to Phase F per Phase C Q2. The
parallelism-realism note captures a nuance the v3 plan's abstract
phase structure couldn't anticipate — that nominal-parallel work
in a solo-builder week is often sequentially-executed for focus
reasons.

**Reversibility:** Easy. Phase E/F may surface dependency items
Phase D missed; additions go into an updated dependency map rather
than re-signing Phase D. The sign-off itself is a procedural gate.

**Decided by:** Lewie (signoff message in chat, with the two
parallelism-realism carry-forward notes) + Claude Code (checkpoint
update, this entry, and the Phase E kickoff).

**Affects:** `planning/dependency-graph.md` §D.9 checkpoint
(Lewie-signoff box now checked); Phase F's Day 2 + Day 4 session
structure (absorb the parallelism-realism framing); Phase F's
Day 3 plan (absorb the N10 pull-forward as the default assumption
if Day 2 runs on time); ops protocol phase-gate audit trail
(Phase D → Phase E transition observable here).

---

## [2026-04-21 07:00] — Tuesday evening sprint reframed from stretch to required (post-Phase-F)

**Context:** Phase F build-plan.md was initially drafted with the Tuesday
evening sprint as a **stretch goal** (recommended-if-energy-permits; N1+N2
target with Cut 4 pre-emptive as the fallback). Phase F §F.8 Q1 surfaced
the framing question to Lewie at signoff. Lewie reframed as **required**
based on operator context that wasn't captured inside the build-plan.md
itself.

**Options considered at the reframe:**
- Keep stretch-goal framing — Tuesday evening optional, Cut 4 pre-emptive
  fallback, Wednesday absorbs ~19.5h compression
- Commit required framing — Tuesday evening N1+N2 required with health-
  check safety valve, Wednesday pre-reduced to ~15.5h baseline (chosen)
- Commit required framing without health-check — required means required,
  push through (not chosen — crosses into reckless)

**Decision:** Tuesday evening sprint is **required**, not stretch. Scope:
- **N1 (FastAPI skeleton, 1h) — required**
- **Tuesday evening health check at ~8pm local, post-N1** — hard self-
  assessment (readable code? ≤2 trivial mistakes last hour? tired-but-
  engaged vs tired-and-sloppy?). Fail any → end sprint.
- **N2 (SQLite schema, 2h) — required *if health check passes*.** N2
  rolls to Wednesday morning if health check fails.
- **N3 (ingest, 1-2h) — stretch only.** Attempt only if N1+N2 finish
  with buffer before 10pm cutoff.

Cut 4 trigger rewritten: **fires at 10pm local Tuesday if N1+N2 aren't
both committed-and-tested in the repo.** Includes the health-check-fires-
after-N1 case automatically (since N2 won't be done by 10pm → Cut 4 fires
→ pre-logged in Tuesday snapshot).

Cutoff time rationale (10pm local): Phase F close-out expected ~7pm;
N1+N2 combined = 3h; 10pm is the natural check-in. Late enough to
genuinely attempt, early enough to preserve sleep before Wednesday's
~15.5h build day. Slippage past 10pm signals fatigue or complexity-
surprise — both argue for Cut 4 pre-emptive over pushing through.

**Operator context driving the reframe:**

1. **Full day already in progress.** Lewie has been working since
   4:30am (Phase C + D + E morning arc, Phase F midday). The sprint
   isn't a cold-start ask.
2. **Energy assessed as adequate** for 4-6 more hours post-Phase-F-
   signoff. Self-reported at the reframe moment.
3. **Day 2 load pre-reduction.** Wednesday Scenario A (N1+N2 done Tue)
   ~15.5h; Scenario B (only N1 done) ~17.5h; stretch-goal fallback
   (neither done) ~19.5h. 15.5h is near the top of feasible; 19.5h is
   not feasible in one day. The scenarios-aware rebalance embeds this
   math into §F.2.2.

**Reasoning:**

1. The stretch-goal framing over-weighted the "don't force late-night
   code" concern against the Day 2 compression concern. With operator
   context (1-2 above), the late-night risk is lower than the stretch-
   goal framing assumed.
2. The required framing is not reckless because the **health check is
   named, time-boxed, and criterion-driven.** Fatigue-escape is
   explicit, not shameful. "Required" means default-is-to-do-the-
   sprint; health-check lets reality override when reality is real.
3. Cut 4's trigger condition change (from "Tuesday evening skipped" to
   "N1+N2 not both done by 10pm") makes the ladder more deterministic:
   the trigger is an observable state, not an assessment of intent.
4. Ladder integrity check re-verified (§F.4 in build-plan.md): Cut 3's
   "N11 slips past midday Day 3" trigger stays correct under both
   Scenario A (fires if N11 runs long) and Scenario B (fires near-
   deterministically because N10 slides to Day 3 AM, pushing N11 start
   past midday). No other Cut needs re-timing.

**Reversibility:** Easy. If the health check ends the sprint at N1,
Cut 4 fires automatically at 10pm cutoff and Wednesday carries the
compression as Scenario B (~17.5h, still feasible with Day 5 buffer).
If Tuesday evening goes exceptionally well, N3 lands too and Wednesday
is Scenario C (~13.5h — comfortable). No mid-week decision needed in
any of these branches.

**Decided by:** Lewie (directive in chat after Phase F signoff summary,
citing operator-context inputs) + Claude Code (capturing reframe,
rebalancing build-plan.md §F.2.1-2 + §F.4, adding health-check design).

**Affects:** `planning/build-plan.md` §F.2.1 (Day 1 plan rewritten with
required framing + health check), §F.2.2 (Day 2 Scenario A/B/C
rebalance with freed-hours-into-buffer principle), §F.4 (Cut 4 trigger
rewrite + ladder integrity re-verification paragraph), §F.8 (Q1
closed), §F.10 (summary updated); `planning/executive-summary.md`
(Day table, ladder cut table, questions section, safety valve callout);
`planning/today.md` (Tuesday evening section); forthcoming
`SESSION-2026-04-21-01.md` (reflects required framing at session close).

---

## [2026-04-21 07:05] — Phase E and Phase F approved; session close sequence initiated

**Context:** Phase E (Gap Analysis) delivered earlier this session with
all checkpoint items complete but Lewie's sign-off deferred to bundle
with Phase F. Phase F (Build Plan) delivered with the post-summary
Tuesday-evening reframe (see [07:00] entry) captured. At session close,
Lewie approved both together as part of the close-out sequence.

**Decision:** Phase E is approved. `planning/gap-analysis.md` is final.
Phase F is approved. `planning/build-plan.md` and
`planning/executive-summary.md` are final. Phase F checkpoint boxes
ticked including the required-framing and ladder-integrity addenda.

Q2 from Phase F §F.8 (Level-3 escalation destination = Claude.ai chat)
taken as implicitly accepted at signoff absent pushback. Recorded here
so a later session doesn't re-litigate.

**Reasoning:** Phase E and Phase F both met all checkpoint items and the
Tuesday-evening reframe (logged separately at [07:00]) was the only
content change between the Phase F summary and signoff. Bundled sign-off
is the ops-protocol-consistent pattern when a later phase's signoff
naturally closes an earlier phase's pending review — analogous to Phase D
signing off on Phase C's residual items implicitly via dependency-
structure validation.

**Reversibility:** Easy. Any specific deliverable section that reads
shallow in the build week can be revisited with a targeted `/effort max`
re-review and a note logged here.

**Decided by:** Lewie (signoff message in chat completing the reframe
directive) + Claude Code (checkpoint updates, this entry, and the
session-close snapshot write).

**Affects:** `planning/gap-analysis.md` §E.7 checkpoint (Lewie-signoff
box now checked); `planning/build-plan.md` §F.9 checkpoint (Lewie-
signoff box now checked); ops protocol phase-gate audit trail (Phase E
→ Phase F → session close observable in sequence via DECISIONS.md);
session transition — this is the last decision log entry before the
SESSION-2026-04-21-01.md snapshot writes.

---

## [2026-04-21 08:28] — Operating protocol refinements: timestamp discipline + pace-independent execution

**Context:** Two operating-protocol refinements surfaced during the
Day 1 morning review when false afternoon/evening timestamps in
SESSION-2026-04-21-01.md and DECISIONS.md — baked in from
plan-language rather than reality — required a backfill correction
pass. The root cause was two-fold: (1) lack of timestamp discipline
(narrative/plan-language times getting used as historical claims
without verification against `date`), and (2) conflation of
goal-sequencing with clock-locked milestones (the "Tuesday evening
sprint" naming + "10pm Cut 4 floor" wall-clock anchors were assumed
to require execution in literal evening hours, which created friction
when the planning-tail phases and the N1 scaffold all finished by
mid-morning). Lewie surfaced both issues and directed the refinements
below.

**Decisions:**

**Update 1 — Timestamp discipline.** Going forward, every timestamp
written into any project file (SESSION snapshots, DECISIONS entries,
today.md, any other planning or build doc) uses the actual output of
`date` called at the moment of writing. No interpretation of
plan-language. No pattern-matching against "plausible" times. No
extrapolation from narrative context. Call `date`, use the result,
move on. For historical events that weren't timestamped at the moment
they happened, reconstruct from file mtimes (as in the Task 1
correction pass earlier this morning, 2026-04-21) — file mtime is
observed data, not extrapolation; the correction pass itself was
protocol-consistent. Extrapolated times unsupported by either a
`date` call or an mtime anchor should be flagged as reconstructed,
not stamped as observed.

**Update 2 — Pace-independent plan execution.** The build-plan.md
day-by-day structure (Day 1 = N1+N2, Day 2 = N3/N4/N5/N6, etc.)
describes **goal sequencing**, not clock-locked milestones. Finishing
a day's goals in 3 hours instead of 14 is progress ahead of plan,
not a scheduling anomaly to reconcile. Specific practical
implications:

1. **"Tuesday evening sprint"** is a name for the N1+N2 goal
   sequence; completing it in morning hours is on-plan, not
   off-pattern. The "evening" adjective stays in the name as a
   legacy label; it is not a wall-clock constraint.
2. **"10pm Cut 4 hard floor"** was an anchor for a long evening
   session. For morning work it does not apply as a wall-clock
   trigger. Cut 4 still fires on its *content* trigger (N1+N2 not
   both committed-and-tested before moving to Day 2's sequence) —
   but the content trigger is what fires it, not the clock.
3. **Health checks trigger on sustained-work thresholds**, not
   clock times. Indicators: hours of focused work elapsed, mental
   sharpness, whether Lewie has eaten, whether rest has been taken
   since last major work block. The "~8pm local" anchor in
   build-plan.md §F.2.1 is a legacy proxy for "~3h after sprint
   start" in an evening-session framing; for a morning session the
   equivalent trigger is the same proxy (sustained-work elapsed),
   not the literal clock time.
4. **Between sequence goals, Lewie can stop at any time for any
   reason** — food, life, the hackathon acceptance email, rest.
   The plan's cadence is his, not the document's.

**Reasoning:**

*Update 1.* Plan-language timestamps (11:15, 13:00, 17:30, 17:45,
18:00) got baked into DECISIONS entries and the SESSION snapshot for
Phases C, D, E, F, the Q1 reframe, and the session close. All six
were wrong; all real work happened between 04:30 and ~07:05 today.
The failure mode is subtle: plans discuss expected times; narrative
writing absorbs those as historical claims; once baked in, they're
hard to distinguish from real observations. `date` as a hard
discipline breaks that loop by making the source of truth observable
rather than synthesized.

*Update 2.* Treating Day-N plan blocks as clock-bound creates false
pressure (late-night cutoffs, specific PM triggers) when the actual
work is sequential and pace-agnostic. Morning-pace execution is a
feature, not a bug. The build plan's named hours are
reference-anchors for energy budgeting in a long-session context,
not rules. Reframing around sustained-work thresholds preserves the
safety-valve intent (don't push through fatigue) without importing
clock-calendar friction that doesn't match the actual session shape.

**Reversibility:** N/A — these are hygiene refinements that codify
discipline we should have had from Day 0. Not overridable by later
sessions without an explicit counter-decision logged here.

**Decided by:** Lewie (both updates directed in chat after reviewing
the Task 1 correction pass + the gap audit results) + Claude Code
(logging this entry, applying Update 1's `date` discipline to the
timestamp on this entry itself).

**Affects:**
- All future DECISIONS entries, session snapshots, today.md updates,
  and any other planning/build doc writing — timestamp discipline
  applies globally
- `planning/build-plan.md` §F.2.1 "Tuesday evening" framing and
  "10pm Cut 4 trigger" — reinterpreted as goal-sequence name +
  content-trigger, not wall-clock rule (documents themselves
  unchanged; interpretation rule changes)
- Health-check criteria in build-plan.md §F.2.1 — re-anchored to
  sustained-work state, not 8pm local clock
- Cut 4 trigger interpretation — fires if N1+N2 aren't
  committed-and-tested before moving to Day 2's sequence
  (content-based), regardless of wall-clock time
- Task tracker items #6 (health check) and #9 (Cut 4) — reframed in
  the current task list following this entry to drop the clock
  anchors

---

## [2026-04-21 10:01] — Cut 4 NOT fired: N1+N2 both committed-and-tested

**Context:** Per build-plan.md §F.4 (as reinterpreted under the
pace-independent framing logged at [2026-04-21 08:28] Update 2), Cut 4
fires if N1+N2 are not both committed-and-tested before moving to
Day 2's sequence. The "10pm local Tuesday" wall-clock anchor in the
original Cut 4 trigger no longer applies under Update 2; the trigger
is content-based.

**State evaluated:**

- **N1** — FastAPI skeleton. Committed at `df9c48f`. `pytest` 3/3
  green. `uvicorn core.app:app` boots; `GET /health` returns 200 with
  `{"status":"ok","env":"dev","version":"0.1.0"}`. Lifespan logging
  fires cleanly.
- **N2** — SQLite schema + SQLAlchemy 2.x models. Committed at
  `a377c21`. `pytest` 11/11 green (3 smoke + 8 db). `init_db()`
  materializes concierge.db with all four tables (packs, tools,
  requests, memory_events), 8/11/13/7 columns respectively, and 15
  explicit indexes covering lookup columns (slug, status, filename,
  folder, event_type, occurred_at, is_active, is_in_manifest,
  pack_id, category, tool_slug, source). On-disk schema verified via
  raw `sqlite3` connection in two dedicated pytest tests.

Both content criteria satisfied. Cut 4 does **not** fire.

**Decision:** Cut 4 status: **NOT FIRED.** N3 (markdown-to-SQLite
ingest, 1-2h per build-plan §F.2.1 as stretch-only on Day 1)
therefore retains its full scope — the markdown-export portion that
Cut 4 would have deferred stays in-scope for Day 2.

**Reasoning:** Content trigger is observable: (1) both commits exist
in `git log` (`df9c48f` + `a377c21`), (2) both test suites pass, (3)
on-disk SQLite schema materialized and verified. Under Update 2's
pace-independent framing, the wall-clock "10pm" anchor is
inapplicable; the content trigger is the operative gate and it
resolves cleanly.

**Reversibility:** Cut 4 cannot "re-fire" once its content trigger
has resolved. If Day 2 surfaces schema defects requiring material
rework on N2, that's a separate scope concern and would be logged
as its own DECISIONS entry (not a re-firing of Cut 4).

**Decided by:** Claude Code (evaluation per the content trigger) —
no Lewie decision required; Cut 4's trigger is observable state,
not a judgment call. Entry logged for audit trail consistency with
ops protocol.

**Affects:** `planning/build-plan.md` §F.2.1 Day 1 checkpoint box
"Cut 4 status" — resolvable as "not-needed" (both N1+N2 done);
`planning/today.md` — Tuesday evening sprint section closeable;
Day 2 scope — N3 retains full markdown-export work per original
§F.2.2 morning block 1 table. Session close-out snapshot should
record Cut 4 NOT FIRED as the Day 1 sprint outcome.

---

## [2026-04-21 18:00] — Strategic pivot: operational-first build, demo as subset

*Correction note 2026-04-22 15:45 PDT: this entry's language about
"variance during soak must come from real input differences, not
model sampling" was load-bearing on `temperature=0.0` as a
determinism knob. Anthropic's own Opus 4.7 migration guide says
`temperature=0` never guaranteed identical outputs on prior models;
Opus 4.7 removes the parameter entirely. The **intent** of the
pivot language survives intact (recommendations should be
diagnostically meaningful, not stochastic-noise-dominated); the
**mechanism** shifts from temperature-pinning to effort-pinning
(`output_config.effort="xhigh"`). Soak diagnostics still matter;
per-call bit-identical determinism was always an approximation.
See DECISIONS [2026-04-22 15:45] for the fix + re-framing.*

**Context:** Mid-session announcement from Lewie. Two pieces of
situational information combine to motivate the pivot:

1. **No hackathon acceptance email in hand.** The Built with Opus 4.7
   event (April 21-26, 2026) is underway, but participation /
   acceptance is not confirmed. The implicit assumption baked into
   Phase F (§F.1 Mission framing) — that a recorded, polished
   3-minute demo video submitted by Day 6 is the load-bearing
   end-state — no longer holds with certainty.
2. **Self-evaluation of the operator's actual need.** Concierge, if
   it works, is useful to Lewie regardless of the hackathon's outcome.
   Building for real daily-driver use is a goal with a certain
   payoff; building for a demo video whose submission path is
   uncertain is a goal with a contingent payoff.

The natural response is to invert the hierarchy: treat operational
use as primary, the demo as a byproduct. This entry codifies the
inversion so every subsequent session reads the same priority
structure.

**Decision:** Shift the end-state gate.

- **Old end-state (per build-plan §F.1):** "Demo video recorded,
  README + submission docs complete, hackathon entry submitted"
  by Day 6 evening.
- **New end-state:** "Concierge running live on Lewie's daily Claude
  Code sessions for **48+ continuous hours** before declaring the
  build 'done'." The 48h operational-shakedown gate supersedes the
  5-consecutive-clean rehearsal gate.
- **Demo relationship:** the demo path is now a **subset** of the
  operational path. If the operational gate passes, a demo
  recording is trivially available as a byproduct (record live
  usage, edit to a 3-minute narrative). If the operational gate
  fails, the demo recording is a lie and shouldn't exist anyway.
- **Hackathon submission posture:** still aim to submit by Sunday
  2026-04-26 **if** the operational gate has been reached. If the
  gate hasn't been reached, submission either (a) happens with a
  "N hours of uptime, M recommendations served" footnote in place
  of a polished narrative, or (b) slips in favor of operational
  integrity. Judgment call at the time, not pre-committed here.

**Reasoning:**

1. **Certain vs. contingent payoff.** Operational use is a payoff
   that materializes regardless of whether the hackathon accepts
   the entry or awards a prize. Demo-first bets the entire week's
   work on an uncertain submission outcome.

2. **Operational is strictly harder than demo.** A demo that "works
   in rehearsal" can hide substantial real-use fragility (flaky
   memory writes, cron that never actually runs, error paths that
   explode on first real failure). A demo built as a byproduct of
   live operation has already survived the harder test. This
   mitigates the "demo works in the recording, fails the first
   time the founder tries it" failure mode that kills most
   solo-builder demo projects.

3. **Every engineering decision clarifies.** Under demo-first,
   "good enough for a 3-minute recording" is the quality bar; under
   operational-first, "doesn't corrupt the daily driver, logs enough
   for debugging, degrades gracefully, restarts cleanly" is the bar.
   The latter forces earlier and better architectural choices on
   exactly the surfaces where solo-builder projects typically cut
   corners.

4. **Alignment with CLAUDE.md priority hierarchy.** CLAUDE.md
   already names "AI quality → build smoothness → Day-4 substantive
   completion → token cost explicitly not a priority." Operational-
   first fits cleanly under "AI quality" at a system level: a
   system that earns its keep in daily use is demonstrably
   higher-quality than one that demos well.

**Implications:**

*Memory default — reversal of the lean proposed earlier this session:*

- Earlier in this session (~16:30 PDT, during N5 open-questions
  checkpoint), Claude Code leaned toward **shared** memory default
  (`~/.moltbot-memory-v2/`) on the reasoning that sharing Alfred's
  real tool-selection history would make the demo narrative more
  compelling. Under operational-first, this lean flips: the memory
  default must be **isolated** (`~/.concierge-memory/`).
- Reasoning for the flip:
  1. Concierge-under-development writing to Alfred's production
     memory store risks contaminating the daily driver's state.
     Alfred read-amplifies Concierge bugs into his own behavior.
  2. Alfred's live memory state mutating during Concierge's
     recommendation generation introduces non-determinism that
     makes operational debugging harder.
  3. The operational-first mandate is "Concierge runs on Lewie's
     daily Claude Code sessions" — those sessions have their own
     memory needs, separate from Alfred's fleet.
  4. Sharing is still available by explicit env-var override
     (`CONCIERGE_MEMORY_DIR=~/.moltbot-memory-v2`). Default safe,
     opt-in to risk, not the other way around.
- Net: N5 defaults to `~/.concierge-memory/`; env var
  `CONCIERGE_MEMORY_DIR` overrides.

*Priority shifts — DOWN:*

- **N19 token-win instrumentation** (Day 4 PM, 1.0h). Was a
  demo-beat; under operational-first it is a nice-to-have metric.
  Still build it if time permits, but explicitly OK to cut. First
  Level-3 escalation candidate.
- **N20 UI polish** (Day 4 evening, 1.0h). Transitions, empty
  states, labels — demo-optical concerns. Under operational-first
  the UI needs to *work* (functional empty states, clear error
  surfacing, no broken links), not to *sparkle*.
- **5-consecutive-clean demo rehearsal** (Day 5 midday, ~3h). Was
  the primary Day-5 deliverable. Replaced by "first 24h of
  operational shakedown."
- **Day 6 polished recording** (~4h). Becomes "record what's live
  IF the operational gate has been reached," not "polish takes
  until the narrative is clean."
- **Scripted demo narrative.** The per-second storyboard work that
  demo-first would require for Day 5-6 rehearsal becomes a
  secondary deliverable produced from live usage logs, not a
  pre-composed script.

*Priority shifts — UP:*

- **Error handling paths.** Every endpoint (N4, N6, N7) needs
  clear error responses, not just happy-path correctness. 500s
  must be logged with enough context that Lewie can diagnose
  from the log alone. Validation errors on POST bodies return
  structured 422 responses.
- **Structured logging.** The existing `core/logging.py` baseline
  (stream handler, level configurable) stays, but usage discipline
  increases: N5 logs init + each operation at DEBUG, failures at
  WARNING/ERROR; N6 logs each recommendation with task + candidates
  + chosen-ranking; N7 logs status transitions. Logs are the
  primary post-incident debugging surface during the 48h gate.
- **Graceful degradation.** N6 must serve a recommendation even
  when memory is unavailable (return without memory context,
  annotate response with `memory_available: false`). N7 must
  accept a request even if catalog lookup degrades. The cron
  must survive individual file-parse failures and continue with
  the rest of the directory. Explicit design choice to raise-and-
  catch at endpoint boundaries, not try-to-fix-in-place.
- **Cron lifecycle actually running on real usage.** X11 was
  flagged as "verify crontab + doc" (0.5h). Under operational-
  first, X11 is elevated — the cron must ACTUALLY run during the
  48h gate, logs must show heartbeats, weekly-review output must
  surface something useful by hour 24. Adds verification work not
  just installation work.
- **Stability under concurrent use.** The N2-era StaticPool + dep-
  override pattern handles tests. Operational use needs real
  concurrency handling — the same request file observed by cron
  mid-housekeeping, the same memory store read by Concierge and
  potentially Alfred (if sharing is enabled), the same SQLite
  accessed by the UI and the API. Not all of this needs new
  engineering; some needs explicit think-through.
- **Startup / restart discipline.** Concierge must be launchable
  and re-launchable cleanly. Ports released, DB handles closed,
  ChromaDB client disposed. Add this to the `core.app.lifespan`
  shutdown path.

*Protected-floor reframing:*

- The §F.5 "protected demo floor" (17 items / ~27h) was named as
  the uncuttable core for a working demo. Under operational-first,
  those 17 items remain protected — they *also* form the
  "minimum operational core." But the operational core is a
  **superset**: it additionally includes error-handling rigor,
  logging discipline, and X11-actually-working that weren't in
  the demo-floor definition. Rename conceptually to "Protected
  core" (demo-capable == operational-capable).

*Risk register reweighting:*

- Risk 1 (prompt-fragment correctness): **unchanged** — still H/H;
  operational use is a harder test than N8 fixture assertion.
- Risk 2 (stdio shim debugging): **unchanged** — N10 still needs
  to work; if anything, the 48h operational gate exposes more
  debugging opportunities.
- Risk 3 (Day 3 serial-tail cascade): **marginally easier** to
  ladder-cut now — Cut 2 (X13 install automation) becomes "ship
  without auto-install for shakedown period" with even less
  friction.
- Risk 4 (Opus variance): **easier** — 48h of live recommendations
  surfaces variance naturally; less need for synthetic rehearsal.
- Risk 5 (markdown parser drift): **unchanged.**
- NEW Risk 6 (operational regressions during shakedown): Medium
  probability, Medium-High impact. Concierge running live means
  Concierge breaking mid-Lewie-session. Mitigation: rollback plan
  (git tags at stable points; `systemd` / launch-script can pin
  to last-known-good commit). Add to risk register on next
  cascade.

**What does NOT change:**

- All Phase A-F planning artifacts (inventory, classification,
  dependency graph, gap analysis, build plan) remain authoritative
  for the foundation work. The pivot is a priority-weighting
  change, not a scope or architecture change.
- Extraction pattern — X3/X4/X6/X7-A/B already committed; X8 still
  scheduled.
- N1-N4 already committed; no rework.
- N5 / N6 / N7 / N8 all still required (arguably **more** required
  — they are the operational core).
- Critical path structure through N6 → N10 → N11 → N14 unchanged.
- Test discipline, commit discipline, session-snapshot discipline
  all unchanged.
- Ladder cuts (Cut 1-4) still structurally valid; trigger
  conditions unchanged.
- Effort estimates unchanged at the task level.

**Cascade edits pending (NOT executed this turn per Lewie's
instruction to log-and-proceed):**

- `planning/build-plan.md` §F.1 Mission framing — add operational-
  first framing as primary end-state; demo as byproduct.
- `planning/build-plan.md` §F.2.5 Day 5 — reshape from "rehearsal"
  to "first 24h of operational shakedown."
- `planning/build-plan.md` §F.2.6 Day 6 — reshape from "recording +
  submission" to "operational-gate check → record IF passed →
  submission posture."
- `planning/build-plan.md` §F.5 — rename "Protected demo floor" →
  "Protected core" with operational-superset note.
- `planning/build-plan.md` §F.6 — add Risk 6; reweight Risks 3/4.
- `planning/executive-summary.md` — regenerate one-page overview.
- `planning/today.md` — next daily regeneration picks up the new
  framing.
- `CLAUDE.md` §Priority hierarchy — may want an explicit addition:
  "Operational correctness > Demo polish" as a clarifying note
  under AI quality. Judgment call.

Recommended to cascade at next session start (Day 2 morning after
a sleep break) or at current session's close-out, whichever comes
first. Not blocking N5 execution — the pivot is fully readable
from this entry alone.

**Reversibility:** Easy at the planning-doc level; no code changes
reverse. If the pivot turns out wrong (e.g., real-use friction is
worse than predicted and the 48h gate becomes unachievable within
the hackathon window), revert by:

1. Re-elevating demo-first in §F.1.
2. Dropping the 48h gate in favor of 5-consecutive-clean rehearsal.
3. Restoring N19 / N20 / demo-narrative priorities.
4. No code touched — memory-default env var stays configurable.

The reverse move itself gets a DECISIONS entry citing which signal
triggered it.

**Decided by:** Lewie (strategic call, announced in session;
reasoning enumerated in his own message; no chat deliberation
required — he owns the priority hierarchy).

**Affects:** Every session from this point forward. Effective
immediately including N5 (isolated memory default). Cascade to
build-plan.md / executive-summary.md pending, not blocking.

---

## [2026-04-22 07:26] — N6 OpenClaw-coupling strategy: adapter-context preamble

**Context:** Phase C §C.2 EXTRACT classifications #3, #4, #6, #7
(tool-awareness, tool-recommendation, tool-discovery, tool-lifecycle)
preserve the source skills **verbatim** per DECISIONS
`[2026-04-21 05:50]`. The source content carries substantial
OpenClaw-specific material that was preserved intentionally:

- Fleet naming: "5 agents (Alfred, Scout, Dispatch, Radar, Bridge)"
- Pipeline paths: `~/.satiety-pipeline/`, `~/.agent-skills/shared/
  TOOL-MANIFEST.md`, `~/.openclaw/logs/tool-wishlist.md`
- Specific MCP tool IDs: MailerLite `ml_*`, ElevenLabs TTS
- Transport specifics: port 18789
- MCP-tool-call instructions (e.g. "call `memory__memory_search`")
- Worked examples naming MailerLite / Scout / Alfred by role

The X3 header (`core/prompts/tool_awareness.py` lines 40-66)
explicitly deferred the handling of this coupling to the consumer
at N6 compose time, enumerating three viable strategies without
selecting one. Phase F §F.2.2 N6 row named the fragments' use in
the system prompt but didn't pick a strategy. N6 is the first
(and in hackathon scope, only) compose site — this entry selects
the strategy so it becomes a stable architectural commitment
rather than a per-call ad-hoc choice.

Concierge's N6 call-shape differs from the OpenClaw skill-load
context in three material ways:

1. **No MCP tool surface at recommend time.** The caller is an HTTP
   client (Claude Code adapter, UI, or cURL); there is no
   `memory__memory_search` tool Opus can call mid-reasoning.
   Memory is pre-fetched server-side by `core.recommend.service`
   and rendered into the user message.
2. **No agent identity.** N6 is platform-agnostic; it is not Alfred,
   not Scout, not any named fleet member. References to specific
   agents should be read as *examples of the pattern*, not
   instructions about self-identity.
3. **No OpenClaw infrastructure paths.** `~/.satiety-pipeline/`,
   `~/.openclaw/logs/tool-wishlist.md`, port 18789, etc., are all
   OpenClaw-runtime-specific. Concierge's lifecycle store is the
   symlinked `_legacy/tool-requests/`; the wishlist is not yet
   wired; fleet transports are adapter-specific.

**Options considered (three strategies enumerated in X3 header
lines 54-63):**

- **(a) Trust Opus 4.7 to generalize** from the worked examples to
  the calling adapter's fleet/paths/transports. Zero-work
  consumer-side; relies on Opus's contextual inference.
- **(b) Pre-process at compose time** — substitute or redact
  adapter-specific strings in the fragment constants (e.g.,
  template placeholders for `{{pipeline_root}}`,
  `{{fleet_description}}`) before composition.
- **(c) Adapter-context preamble** — prepend a short
  Concierge-specific framing block that tells Opus how to
  interpret what follows (ignore agent-name references, ignore
  infrastructure paths, memory is pre-fetched, MCP tool-call
  instructions do not apply at this call site). Preamble +
  fragments + JSON-schema envelope as distinct concatenated
  blocks with clear boundaries. Fragments remain byte-identical
  to source; drift-checks unaffected.

**Decision:** (c) — adapter-context preamble.

System-prompt structure in `core.recommend.prompt.compose(...)`:

```
<Concierge adapter-context preamble>          ~5-10 lines
---
<X3 TOOL_AWARENESS_PROTOCOL__...>             verbatim
---
<X4 TOOL_RECOMMENDATION_PROTOCOL__...>        verbatim
---
<X6 TOOL_DISCOVERY_PROTOCOL__...>             verbatim
---
<X7-A TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__...>  verbatim
---
<JSON-schema envelope>                        Concierge-authored
```

Each block delimited by a clear `---` or `===` boundary so Opus
parses them as distinct framings and the preamble's scope is
unambiguous.

**Reasoning (why (c) beat (a) and (b) under operational-first):**

*Why not (a):*

1. **The OpenClaw references are load-bearing, not decorative.**
   The fragments include explicit instructions like "call
   `memory__memory_search` as MCP tool" and "route through
   `~/.satiety-pipeline/drafts/` to hand off to Alfred." If Opus
   treats these as applicable to the current call site, it may
   produce recommendations that reference a non-existent MCP tool
   surface or a non-existent pipeline path in its rationale.
   That's not "slightly off" — it's operationally wrong in a way
   an operator reading the 48h shakedown log can't distinguish
   from reasoning failure.
2. **Operational-first raises the cost of graceful fuzziness.**
   Demo-first tolerates "mostly correct recommendations with
   occasional odd wording." Operational-first means the
   recommendation shapes downstream actions (N7 pending-request
   creation, N11 meta-tool-triggered Claude Code behavior).
   Ambiguity at the prompt layer compounds into ambiguity at the
   action layer.
3. **Opus 4.7 generalizes well, but the test surface for (a) is
   unobservable.** There's no "did Opus correctly ignore the
   OpenClaw references" assertion we can write. (c) converts
   this into an observable test (preamble-text-present assertion
   in `test_recommend_prompt.py`).

*Why not (b):*

1. **Violates the EXTRACT classification structural mitigation.**
   DECISIONS `[2026-04-21 05:50]` mitigation #1 requires the
   fragment constants be byte-identical to the source skill
   files so drift-checks (`test_prompts.py`) catch source-side
   updates. Pre-processing introduces a mutated intermediate
   that breaks the drift-check contract, or requires a parallel
   "sanitized fragment" constant that doubles the maintenance
   surface.
2. **Template-placeholder scope creep.** Once `{{pipeline_root}}`
   exists, the next maintainer is tempted to also templatize
   `{{fleet_description}}`, `{{agent_name}}`, `{{default_mcp_tool_suite}}`
   — each of which is reasonable in isolation and collectively
   converts EXTRACT into a full ADAPT. Phase C rejected that
   label migration explicitly; (b) smuggles it in through the
   consumer-side door.
3. **The substitution target is not 1:1 across adapters.** For
   Concierge's Claude Code adapter, the "fleet" is a single
   Claude Code session, not a 5-agent pipeline. For a future
   OpenClaw adapter, the fleet is the OpenClaw fleet.
   Pre-processed substitutions would need adapter-specific
   templates; (c) handles this with a single preamble that says
   "interpret the following in this adapter's context" and lets
   the adapter-specific preamble vary without touching the
   fragments.

*Why (c):*

1. **Preserves the EXTRACT invariant.** Fragment constants stay
   byte-identical to source. Drift-checks in `test_prompts.py`
   continue to fire on any source-side change. No parallel
   mutated constant.
2. **Observable test surface.** `test_recommend_prompt.py` can
   assert the preamble text is present, the fragment constants
   appear verbatim after it, and the JSON envelope appears last.
   Failure modes (someone accidentally deletes the preamble,
   someone reorders blocks, someone mutates a fragment constant)
   all produce test failures rather than silent prompt drift.
3. **Adapter-swap friendly.** A future Concierge OpenClaw adapter
   can swap the preamble for an OpenClaw-runtime-appropriate one
   (e.g., "you ARE Alfred, the fleet IS the 5-agent OpenClaw
   fleet, MCP tool-call instructions apply via the bridge")
   without touching the fragments. The adapter-specific framing
   lives at the adapter boundary, which is the correct layer.
4. **Debuggability.** If a 48h shakedown surfaces a recommendation
   that cites Alfred or `~/.satiety-pipeline/` in its rationale,
   the preamble's effectiveness is observable by inspection of
   the DEBUG prompt log — we can tune the preamble without
   touching the fragments or the service code.

**Preamble content sketch (authoritative version in
`core/recommend/prompt.py`):**

```
# Concierge adapter context

You are the recommendation engine of Concierge, a platform-agnostic
tool awareness layer. The following skill protocols were extracted
verbatim from their source files. They were authored for a specific
multi-agent OpenClaw deployment. When reading them, apply these
adaptations:

- Agent names (Alfred, Scout, Dispatch, Radar, Bridge) are worked
  examples of agent roles, not instructions about your identity.
  You are Concierge; the caller is platform-agnostic.
- Infrastructure paths (`~/.satiety-pipeline/`, `~/.openclaw/logs/`,
  port 18789, etc.) are examples of an adapter's runtime layout,
  not paths you should write to or reference in your output.
- Instructions to call tools like `memory__memory_search` as MCP
  tools do not apply at this call site. Memory context, when
  relevant, has been pre-fetched and rendered into the user
  message below; treat the MCP-tool references as illustrative.
- Your output target is the JSON schema defined in the envelope
  below, not a free-form gap report or wishlist entry.

Read the protocols for their reasoning patterns (task
decomposition, signal-table discovery, lifecycle staging,
lightweight-first preference) and apply those patterns to the
task + catalog + memory in the user message.
```

(Exact wording may tune during implementation; the structural
commitment is preamble-before-fragments-before-envelope with
observable boundaries.)

**Structural mitigations:**

1. **Preamble lives in `core/recommend/prompt.py`** as a module-level
   constant `CONCIERGE_ADAPTER_PREAMBLE`. Not in `core/prompts/`
   (which is reserved for extracted fragments per DECISIONS
   `[2026-04-21 05:50]`). The directory split encodes the
   invariant: `core/prompts/` = verbatim source extracts,
   `core/recommend/prompt.py` = Concierge-authored composition.
2. **Block boundaries asserted in tests.** `test_recommend_prompt.py`
   asserts the preamble substring, each fragment substring, and
   the envelope substring all appear in the composed prompt in
   the expected order. Changing the order is observable.
3. **Drift-check integration.** `test_prompts.py`'s existing
   signal-phrase assertions on the fragment constants continue
   to fire; the preamble addition doesn't touch them.

**Reversibility:** Easy. If 48h shakedown surfaces that preamble
is insufficient (Opus still occasionally cites OpenClaw
infrastructure in its rationale), remediation options in
escalation order:

1. Strengthen preamble wording (text-only change in
   `prompt.py`, no fragment touch).
2. Promote to strategy (b) for a specific problematic fragment
   (targeted `/effort max` re-review; would be logged as its own
   DECISIONS entry per the Phase C §C.5.3 remediation path).
3. Re-classify a specific fragment as ADAPT if pre-processing
   cannot adequately handle the coupling. Would require
   DECISIONS entry and planning re-cascade.

None of these touch the fragment modules; all are contained to
the adapter layer.

**Decided by:** Lewie (selected (c) in chat with explicit
structural framing — preamble + fragments + envelope as distinct
concatenated blocks) + Claude Code (enumerated trade-offs and
proposed preamble content).

**Affects:** `core/recommend/prompt.py` — new module authoritative
for preamble and composition; `tests/test_recommend_prompt.py` —
asserts preamble presence, block ordering, envelope presence;
`core/prompts/` — unchanged (EXTRACT invariant preserved);
`core/prompts/SKILL_FRAGMENT_SYNC_LOG.md` — unchanged; future
OpenClaw adapter (Phase 2) — will define its own preamble without
touching fragments.

---

## [2026-04-22 08:34] — Rename: `core/lifecycle.py` → `core/lifecycle_policy.py`

**Context:** N7 (Day 2 afternoon, this session) introduces a new
package `core/lifecycle_store/` for the operations side of the
lifecycle surface — request-file parser, atomic writer, DB/filesystem
reconciliation, transition service, API-layer orchestration. The
existing module `core/lifecycle.py` holds the X7-B policy constants
(status vocabularies, transition rules, thresholds).

With both landing in the same codebase, `core/lifecycle.py` vs.
`core/lifecycle_store/` reads at import time as a layered pair of
the same thing ("`lifecycle_store` is the persistent store backing
`lifecycle`?"). A reader encountering both for the first time has
to trace imports to realize they are *different concerns* — policy
data vs. operational plumbing — that happen to share a domain
noun. That ambiguity compounds across future modules (a hypothetical
`lifecycle_service`, `lifecycle_scheduler`, etc. would extend it).

Lewie flagged the naming at the N7 state-check (session chat) and
directed the rename before N7 starts so nobody learns the wrong
pair first.

**Options considered:**

- **(a) Keep `core/lifecycle.py` + `core/lifecycle_store/`.** No
  change. Reader grounds the distinction via each module's header.
- **(b) Rename `core/lifecycle.py` → `core/lifecycle_policy.py`
  (chosen).** Policy vs. store reads unambiguously at the import
  line; no header-read required to resolve the pair.
- **(c) Namespace both under `core/lifecycle/` as a package:
  `core/lifecycle/policy.py` + `core/lifecycle/store/`.** Tightest
  coupling in the filesystem tree, but adds an empty `__init__.py`
  for no runtime benefit and widens the rename blast radius.

**Decision:** (b). Rename `core/lifecycle.py` →
`core/lifecycle_policy.py` and `tests/test_lifecycle.py` →
`tests/test_lifecycle_policy.py`. Use `git mv` so history follows.
Update the single `from core.lifecycle import ...` in the test file
to `from core.lifecycle_policy import ...`. Update docstring
cross-references in `core/prompts/tool_lifecycle.py`,
`core/prompts/SKILL_FRAGMENT_SYNC_LOG.md`, and `tests/test_prompts.py`.
Add a module-docstring note in `core/lifecycle_policy.py` referencing
this DECISIONS entry so the rename is self-documenting.

Historical session snapshot (`SESSION-2026-04-21-02.md`) left
unchanged — it is a frozen record of state at close of Day 1
session 02, not a live reference.

**Reasoning:**

1. **Import-line readability is the metric.** `from core.lifecycle
   import TOOL_SELECTION_STATUS_VALUES` and `from
   core.lifecycle_store.service import LifecycleService` shown on
   two adjacent lines in a reader's editor do not disambiguate
   which is policy and which is operations. `from
   core.lifecycle_policy import ...` + `from
   core.lifecycle_store.service import ...` does disambiguate,
   instantly, without requiring the reader to open the modules.

2. **Future-proofing against layered-same-thing reads.** The
   `X_store` pattern already exists in common Python idiom as "the
   persistent store for domain X" (e.g. `session_store`,
   `credential_store`). Keeping one side of the pair named `X` and
   the other `X_store` recruits exactly that idiom and therefore
   exactly that misreading.

3. **Blast radius is small and observable.** One live import
   reference (test file), four docstring cross-references, one
   sync-log table entry. `pytest -q` passing after the rename
   confirms the runtime surface is intact; grep for `core.lifecycle\b`
   and `core/lifecycle.py` confirms the text surface is clean.

4. **Timing: before N7 starts.** Renaming after N7 ships would cost
   more (more imports, more tests, more tendrils). Doing it now
   keeps the change contained to a sub-10-file edit.

**Reversibility:** Easy. `git mv` back + re-update the imports.
No content changes in the constants themselves; just the module
name and references.

**Decided by:** Lewie (directive in chat at N7 state-check) +
Claude Code (execution + this log entry).

**Affects:** `core/lifecycle_policy.py` (renamed from
`core/lifecycle.py`); `tests/test_lifecycle_policy.py` (renamed
from `tests/test_lifecycle.py`); `core/prompts/tool_lifecycle.py`
(docstring cross-refs updated); `core/prompts/SKILL_FRAGMENT_SYNC_LOG.md`
(module-home references updated across all table rows and history
entries referencing X7-B); `tests/test_prompts.py` (one docstring
cross-ref updated); forthcoming `core/lifecycle_store/` package
(N7 — will cite policy imports as `from core.lifecycle_policy
import ...`).

---

## [2026-04-22 10:35] — Promotion: N7 scope boundary — lifecycle visibility ≠ lifecycle action

**Context:** N7 (commit `7b8d790`, Day 2 afternoon) shipped `/requests`
endpoints as **lifecycle visibility + state transitions**. A POST to
`/requests/{filename}/status` with `status=approved` updates the file
status line + DB row. It does NOT execute tool installation. The
install-on-approve wiring belongs to X13 (Day 3 midday, Cut 2
deferrable).

This boundary was originally captured in the N7 commit message (first
paragraph) and in `core/lifecycle_store/__init__.py` + `service.py`
module docstrings. The Day-2 session close-out snapshot
(`SESSION-2026-04-22-01.md`) flagged it as a DECISIONS-promotion
candidate. Day-3 session open (this entry) confirms the promotion per
Lewie's directive during the architectural-pause review.

**Why promote rather than leave in commit message + docstrings:**

1. **Governs imminent branches.** X13 lands today (Day 3 midday). Cut 2
   may drop X13 entirely. UI approve-button wiring happens Day 4
   (N17-N18). All three touch the same question — "what does Approve
   actually do?" — and each needs a canonical pointer rather than
   scattered commit-message + docstring references.
2. **Cut 2 creates a naming-survival problem.** If Cut 2 fires and
   X13 is dropped, the boundary "approve still doesn't auto-install"
   must survive canonically. The N7 commit references X13 as
   forthcoming-work; if X13 never ships, a DECISIONS entry outlives
   the dropped-X13 thread in a way a commit-message reference cannot.
3. **Docstring-drift risk.** `core/lifecycle_store/service.py` will
   evolve; commit-message framing disappears from `git blame` once
   the module changes. DECISIONS entries are append-only and
   timestamped, so the pointer stays stable.
4. **Cross-cuttability.** The boundary is referenced by lifecycle
   (N7), adapter meta-tools (N11-N13), install module (X13), and UI
   (N17-N18). No single module docstring naturally owns it.

**What the boundary says:**

- The `/requests` surface (GET/POST endpoints, status transitions)
  provides lifecycle **visibility + state transitions**: read the
  inbox, read/write status flags, observe folder membership, trigger
  the atomic file write. It also provides parseability isolation
  (one bad .md surfaces as `is_parseable=False` rather than 500).
- The `/requests` surface does NOT provide lifecycle **action**: no
  tool installation, no package-manager invocation, no subprocess
  spawn on `status=approved`.
- State-change side effects are in-band with the file/DB record only.
  Out-of-band effects (install, remove, observe-usage, promote-active)
  belong to separate modules with their own surfaces.

**Scope of future work under this boundary:**

- **X13 (install module, Day 3 midday)** — when it lands, X13 may be
  invoked *by* the status transition handler (internal call inside
  `core/lifecycle_store/service.py::update_status()` when the new
  status is `approved`), but the N7 transition surface itself still
  only performs the state transition. X13's install surface is
  separate and independently testable.
- **If Cut 2 fires and X13 drops** — status transition to `approved`
  records the decision; the operator runs the install command
  manually per ladder-cut documentation; soak diagnostics still
  function. Boundary preserved: Approve remains a pure state
  transition.
- **UI approve-button (Day 4 N17-N18)** — wires to
  `POST /requests/{filename}/status` with `status=approved`. UI may
  conditionally display install-instructions-or-confirmation based
  on X13 presence, but the API contract is unchanged.
- **Adapter meta-tool `concierge_request_tool` (Day 3 N11)** — emits
  a `pending/*.md` file on call. Approving the request is still a
  separate human-operator action via UI or direct POST. No
  auto-approve path from the adapter side.

**Alternatives rejected:**

- **(a) Leave in commit message + docstrings only.** Commit-message
  framing lives where N7 readers arrive, but not where X13 / UI /
  adapter readers arrive. Docstring drift is a real risk under Day
  3-5 churn. No canonical cross-cut home.
- **(b) Fold into a broader "lifecycle actions are out-of-band"
  architectural entry later (Day 4-5).** Delays the canonical pointer
  past X13's landing. Cut 2 firing before the entry exists would
  leave the boundary homeless at the moment it is most likely to be
  tested.

**Reversibility:** The boundary is architectural but reversible. If
future work consolidates approve-triggers-install into the status
transition endpoint itself, a follow-up DECISIONS entry narrating
the consolidation supersedes this one. This entry is a
canonical-pointer, not a lock-in.

**Decided by:** Lewie (promote directive during Day 3 session-open
architectural pause) + Claude Code (this log entry).

**Affects:** `core/lifecycle_store/service.py` (current boundary
anchor — module docstring already captures the scope-boundary
phrasing); `core/lifecycle_store/__init__.py` (package-level
docstring); forthcoming install module (X13; its docstring should
cite this entry); `adapters/claude_code/` meta-tool handlers (N11,
specifically `concierge_request_tool` which writes pending/*.md
without approving); `ui/` approve-button wiring (N17-N18; POST
transition only, any install prompt is X13-presence-conditional).

---

## [2026-04-22 11:48] — N9 spike outcome: commit to Approach 2 (stdio proxy shim as primary)

**Context:** Per build-plan §F.2.3 Day 3 morning block, a 0.5h
hard-time-boxed spike opens Day 3 to answer a single protocol
question: *when the Concierge shim emits `notifications/tools/list_changed`,
does the real Claude Code MCP client respond by sending a fresh
`tools/list` request?*

If yes → Approach 1 (native MCP `tools/list_changed` as primary
mechanism per classification.md §C.3.1) is viable and could simplify
N10/N13 dynamic-tool-surface work.

If no / ambiguous / unresolvable within the time-box → commit to
Approach 2 (stdio proxy shim as primary, advertising a fixed tool
surface per session) as originally planned.

**Setup used (scratch-only, deletable post-entry):**

- Scratch shim at `planning/scratch/n9_spike/spike_shim.py` — builds
  the real Layer-2 dispatcher, registers ONE disposable tool
  (`concierge_spike_probe`), wraps `notifications/initialized` so it
  emits `notifications/tools/list_changed` immediately after the
  built-in ack. Minimum-viable-spike shape per in-session refinement:
  no async timer, no second tool, no dispatcher modification beyond
  the method re-registration.
- Launcher `run-spike-shim.sh` invoked via `claude mcp add-json
  concierge-n9-spike '{"command":"<launcher>"}'` at local (project)
  scope.
- Log-file sink at `/tmp/n9_spike.stderr` for unambiguous observation
  independent of where Claude Code routes MCP-server stderr.
- Live test run against Claude Code 2.1.117 at 2026-04-22 11:31 PDT.

**Observation:**

- Handshake completed. Client sent `protocolVersion=2025-11-25`
  vs. our pinned `2024-11-05`; non-hostile mismatch policy logged
  the delta at INFO and responded with our version; client proceeded.
  (Side-finding R1 — see separate entry below.)

  **Correction note 2026-04-22 15:10 PDT:** the original entry read
  `protocolVersion=2025-11-05` — that was a transcription typo from
  Lewie's spike-report chat message (which correctly said `2025-11-25`).
  The typo propagated into the R1 side-finding entry, the R1 closure
  config default, and several docstrings before manual verification
  at Step 5 of the wire-in checklist surfaced the real value.
  Corrected in-place here because the typo mis-stated a factual
  observation; the R1 closure commit that implemented the default
  re-pin to the typo value is corrected in a follow-up commit
  ("fix: pin protocolVersion to 2025-11-25"). Later DECISIONS
  entries incorporate the corrected value directly.
- A single `shim.recv method=tools/list` line appeared in the log
  at **the same millisecond** as the `n9_spike emit
  notifications/tools/list_changed` line (both timestamped
  11:31:47,270). On timing alone this is overwhelmingly likely
  Claude Code's own startup `tools/list` query racing with our
  emit — not a client response to our notification.
- **No second `tools/list` request appeared after that point**
  during the remainder of the session's idle time.

**Ruling on ambiguity:** The emit happens *too early* in the
handshake flow to cleanly separate "notification triggered re-fetch"
from "client would have fetched anyway." A cleaner re-run would
delay the emit by ~2s after `notifications/initialized` to let the
natural startup `tools/list` complete first, then observe whether a
*second* one arrives. We did not execute that re-run — the original
spike's time-box was expiring and the ambiguous-leaning-silence
outcome still commits to the same Day-3 path.

**Decision:** Treat observation as outcome (b) — silence. **Commit
to Approach 2** per classification.md §C.3.1 and build-plan §F.2.3.
N10 framework proceeds unchanged; N11/N13 retain their planned
shape (fixed tool surface per session, advertised at `tools/list`
time; backing-server spawn/teardown orchestrated server-side without
relying on the client to re-poll).

**Alternatives considered:**

- **(a) Re-run with delayed emit inside the time-box.** Rejected:
  expanding the spike mid-run invites further scope creep; the
  ambiguous result still points at the same Day-3 path.
- **(b) Call it re-fetch-observed on the strength of the single
  line.** Rejected: the same-millisecond timing makes causation
  unsupported; committing to Approach 1 primary on that evidence
  risks 4+ hours of rework if a cleaner test later shows silence.
- **(c) Extend the time-box.** Rejected: hard time-box is protocol,
  and Approach 2 was the default anyway.

**Implications:**

- **None for Day 3 critical path.** N10 framework + N11 meta-tool
  surface + N13 backing-server were all designed for Approach 2.
  No rework triggered.
- **A post-N14 soak-phase re-run** could cleanly answer the
  underlying question with a delayed-emit variant — Day 5 or 6,
  low priority, optional. If the re-run later shows re-fetch
  observed, that becomes a future-simplification lever, not a
  plan pivot.
- **The one-tools/list-at-startup behavior is now a documented
  datum** — the real client does query `tools/list` once shortly
  after the `notifications/initialized` notification arrives. N11
  must ensure meta-tools are registered BEFORE the dispatcher
  starts accepting stdin (i.e. registration happens inside
  `build_default_dispatcher()` or equivalent, not deferred to a
  post-handshake lifecycle hook).

**Reversibility:** Trivial. The decision is "stay with the default
plan." If a future re-run overturns it, a follow-up DECISIONS entry
+ N10/N11/N13 rework (or simplification) plans accordingly.

**Decided by:** Lewie (observation read + outcome call) + Claude
Code (spike implementation + this log entry).

**Affects:** No code changes triggered. Build-plan §F.2.3 and
classification.md §C.3.1 Approach 2 commitment reaffirmed. Scratch
dir `planning/scratch/n9_spike/` is deletable; its README captures
the re-run recipe if Day 5-6 soak revisits the question.

---

## [2026-04-22 11:49] — R1 side-finding: real Claude Code `protocolVersion` is `2025-11-25`, not pinned `2024-11-05`

*Correction note 2026-04-22 15:10 PDT: heading originally read
`2025-11-05` due to transcription typo from the N9 spike report.
Corrected in-place per the 2026-04-22 manual-verification finding.*


**Context:** The N9 spike (entry above) required a real Claude Code
MCP client to stimulate the shim. Running against Claude Code 2.1.117
surfaced an observation orthogonal to the spike's main question:

- Our shim at `adapters/claude_code/dispatcher.py:42` pins
  `PROTOCOL_VERSION = "2024-11-05"` per the N10 Day-2-evening build
  (commit `5ffe58c`).
- Real Claude Code 2.1.117 sends `protocolVersion=2025-11-25` in its
  `initialize` request — roughly 12 months newer than our pin.
- The shim's non-hostile mismatch policy (per the N10 design note
  "log at INFO and respond with our pinned version; let the client
  decide whether to proceed") **worked for the N9 spike scenario**
  — the spike's mock-subprocess harness accepted the mismatch. But
  **manual verification on 2026-04-22 showed real Claude Code's
  client REJECTS server responses with older versions** ("Server's
  protocol version is not supported"). The shim-side non-hostile
  policy is necessary but not sufficient; the default must match
  what the client sends.

**What this means:**

- The N10 non-hostile-mismatch design is vindicated as a
  compatibility policy. A hard-reject approach would have broken
  the handshake outright for every current-Claude-Code operator.
- The pinned `2024-11-05` is functional but stale. Every shim
  session against current Claude Code emits an INFO log line noting
  the mismatch — minor but real visual noise for operators during
  the Day 5-6 soak and beyond.
- The staleness will recur: any single pin drifts over time unless
  the pin policy explicitly accommodates that.

**Options under consideration:**

- **(i) Stay pinned at `2024-11-05`.** Zero-change. Mismatch log
  continues indefinitely. Operators learn to ignore it. Simplest
  but degrades log signal over time.
- **(ii) Re-pin to `2025-11-25`.** One constant change. Mismatch
  log silenced for current Claude Code. Drifts again in 6–12 months
  — kicks the same decision forward. Cheapest short-term win; no
  architectural improvement.
- **(iii) Make pin configurable via `CONCIERGE_PROTOCOL_VERSION`
  env var / `core/config.py` setting, default updated to
  `2025-11-25`.** Adds one config field. Operators hitting a future
  MCP-version issue can adjust without editing code. Default still
  drifts, but adjustment path is instant.
- **(iv) Echo-client-version policy: accept any version in a
  compatibility set (e.g. `{2024-11-05, 2025-11-25}`) and respond
  with the client's version.** Most adaptive — mismatch log
  disappears entirely for known-compatible clients. Adds a small
  version-set + conditional response logic. Highest implementation
  cost; best long-term log cleanliness.

**Tentative lean:** (iii) — config field with `2025-11-25` default.
Keeps N14 smoke quiet for current Claude Code; operators have an
escape hatch; future drift is a one-line default change, not a code
path. (iv) is appealing but adds dispatcher complexity and a
compatibility set we'd have to maintain as an ad-hoc registry.

**Decision deferred** to the moment the re-pin is cheap to land —
recommend bundling it into an X-slot on Day 3 afternoon before N14
integration smoke so N14 runs against current Claude Code with
minimal log noise. If Day 3 runs hot, defer to Day-4 morning before
the manual-verification TODO completes.

**Reversibility:** Trivial. The pin is a single constant. Any of
(i)–(iv) is reversible in < 30 lines of code.

**Decided by:** Lewie (finding flagged from live observation) +
Claude Code (this log entry — implementation decision itself
deferred to pre-N14).

**Affects:** `adapters/claude_code/dispatcher.py` (the
`PROTOCOL_VERSION` constant at line 42); potentially `core/config.py`
(new field if option iii is picked); potentially a new unit test
asserting the version-response shape if option iv is picked.

---

## [2026-04-22 14:35] — R1 closure: option iii shipped (config-driven with `2025-11-25` default)

*Correction note 2026-04-22 15:10 PDT: heading originally read
`2025-11-05` default due to transcription typo propagated from the
N9 outcome entry. Corrected in-place on the same day manual
verification surfaced the rejection. The "what landed" details
below have been updated to reflect the corrected value. A follow-up
commit ("fix: pin protocolVersion to 2025-11-25") updates the
actual config default to match this corrected narrative.*

Closing the deferred decision from the R1 side-finding entry above
(`[2026-04-22 11:49]`). Option iii chosen and shipped before N14
integration smoke so N14 runs against current Claude Code 2.1.117
with zero protocol-mismatch log noise.

**What landed:**

- `core/config.py` — new `claude_code_protocol_version: str = "2025-11-25"`
  field on the Settings class. Pydantic-settings maps this to env
  var `CONCIERGE_CLAUDE_CODE_PROTOCOL_VERSION` via the existing
  `CONCIERGE_` prefix, consistent with `CONCIERGE_MEMORY_DIR` /
  `CONCIERGE_LIFECYCLE_ROOT` / `CONCIERGE_URL`.
- `adapters/claude_code/dispatcher.py` — `PROTOCOL_VERSION` module
  constant now derives from `get_settings().claude_code_protocol_version`
  at module import time. Value is frozen for the life of the shim
  process — mid-session env changes require shim restart (matches
  the `CONCIERGE_URL` pattern at
  `adapters/claude_code/meta_tools/http_client.py`, where base URL
  is captured at first-call time).
- `tests/test_shim_e2e.py` — hardcoded `"2024-11-05"` strings
  updated to import `PROTOCOL_VERSION` from the dispatcher module
  so tests track the current default without churn on future
  re-pins. Exception: `TestProtocolVersionMismatch` still sends
  the client-side value `"2099-01-01"` — that test's point is
  mismatch behavior, not version matching.
- `tests/test_shim_e2e.py::TestProtocolVersionEnvOverride` — new
  subprocess test. Spawns the shim with `CONCIERGE_CLAUDE_CODE_PROTOCOL_VERSION=2026-06-15`
  in the child env, sends initialize, asserts the response
  `protocolVersion` matches the override. Covers the env-plumbing
  path end-to-end (parent-process test settings cache is
  irrelevant to the spawned subprocess).

**Why option iii over option ii** (direct re-pin to `2025-11-25`
without a config field): option ii kicks the same drift decision
forward 6-12 months. Option iii adds one config field and makes
the escape hatch explicit so future clients that send a different
`protocolVersion` can be accommodated without editing dispatcher
code. Marginal cost (~20 lines of code + one subprocess test);
eliminates a recurring decision.

**Why not option iv** (echo-client-version with compatibility
set): the maintenance burden of an explicit compatibility set —
adding each new MCP protocol version to it as the spec evolves —
is higher than the value of silencing the non-hostile mismatch
log. The current INFO-logged mismatch is loud-but-acceptable;
silencing it fully is a Phase-2 concern, not a hackathon priority.
Option iii gives operators the escape hatch without committing
Concierge to tracking the MCP version ecosystem.

**Operational check (post-correction):** re-running the N9 spike
setup against current Claude Code 2.1.117 with the CORRECTED
default (`2025-11-25`, after today's fix commit) should show a
clean initialize handshake with ZERO `protocol_mismatch` log
lines (the client's `2025-11-25` matches our corrected default).
The spike's primary question (tools/list_changed re-fetch) is
unaffected by this change — still outcome (b) silence, still
Approach 2 committed.

**What the manual verification caught that the N9 spike did not:**
the N9 spike was a mock-subprocess test of the shim's stdio
handshake in isolation — it verified "our shim emits a
well-formed initialize response even with a version mismatch"
but NOT "real Claude Code's MCP client accepts that response."
The client's rejection path is asymmetric: our shim's non-hostile
mismatch log accepts clients sending any version, but real Claude
Code rejects servers sending older versions. The full-chain
assertion required real Claude Code, which is what the
manual-verification step finally exercised. Adding a test that
encodes this asymmetry is part of today's fix commit.

**Tests:** 445/445 CI-safe fast green (+1 env-override subprocess
test). Zero regressions; the existing 25 shim tests all pass with
the version update.

**Decided by:** Lewie (lean confirmation during the X13 → R1
transition, "lean was pre-named, closure is turning lean-into-
decision") + Claude Code (this log entry + implementation).

**Affects:** `core/config.py` (new field); `adapters/claude_code/dispatcher.py`
(PROTOCOL_VERSION now derived); `tests/test_shim_e2e.py` (hardcoded
strings replaced with constant import + new env-override test).

---

## [2026-04-22 15:45] — Opus 4.7 temperature deprecation: remove `temperature`, use `output_config.effort="xhigh"`

**Context:** Manual verification of the concierge_recommend
round-trip (Step 7 of the wire-in checklist) surfaced a 400 error
from Anthropic's API:

    HTTP/1.1 400 Bad Request
    {'type': 'error', 'error': {'type': 'invalid_request_error',
      'message': '`temperature` is deprecated for this model.'}}

Our recommend client was sending `temperature=0.0` on every call
per the original N6 build + the operational-first-pivot language
about "variance from real input differences." Opus 4.7 has
removed the `temperature` / `top_p` / `top_k` parameters entirely.

**Research findings** (docs.anthropic.com via WebFetch-equipped
research agent):

- No direct replacement parameter. Omit `temperature` entirely.
- **Opus 4.7 is stochastic-by-default.** Anthropic's own migration
  guide explicitly notes: *"If you were using `temperature = 0`
  for determinism, note that it never guaranteed identical outputs
  on prior models."* The historic `temperature=0.0` was always a
  best-effort variance-reducer, not true determinism.
- **Replacement tuning knob:** `output_config.effort` — one of
  `"low"`, `"medium"`, `"high"`, `"xhigh"`, `"max"`. Controls
  reasoning depth, not sampling. Not a determinism knob, but the
  canonical Opus 4.7 tuning surface.
- **Other Opus 4.7 migration gotchas:** ~35% token-count inflation
  from the new tokenizer; `thinking.display` default changed from
  `"summarized"` to `"omitted"` (we don't use thinking, so no
  change); prefill still returns 400 (we don't use prefill).
- **Migration guide:** https://platform.claude.com/docs/en/about-claude/models/migration-guide

**Sources:**
- https://platform.claude.com/docs/en/about-claude/models/migration-guide
- https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7
- https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking

**Options considered:**

- **(A) Remove temperature entirely. No effort parameter.** Accept
  Opus 4.7's default sampling. Minimum change.
- **(B) Remove temperature + `output_config.effort: "high"`.** Pins
  reasoning depth; token cost up; determinism no better than (A).
- **(C) Remove temperature + `output_config.effort: "xhigh"`
  (CHOSEN).** Matches CLAUDE.md's project-wide effort principle
  ("Effort stays at `xhigh` or `max` throughout") — about human-
  operator effort but the principle transfers cleanly to the model
  effort parameter. Token cost not a priority per the project's
  optimization hierarchy. Highest reasoning quality per call. Soak-
  phase recommendation quality better even without per-call
  determinism.
- **(D) Downgrade to an older model still accepting temperature.**
  Rejected — contradicts DECISIONS `[2026-04-22 07:26]` which
  explicitly pinned `claude-opus-4-7` as the recommendation engine.

**Decision: (C).**

**What landed:**

- `core/config.py`:
  - Removed `recommend_temperature: float = 0.0` field entirely
    (schema break — operators with `CONCIERGE_RECOMMEND_TEMPERATURE`
    set will see an unknown-setting error on service start; per
    the in-chat confirmation, dead config fields that silently do
    nothing are worse than removed).
  - Bumped `recommend_max_tokens` from 2048 → 4096. Round number
    matches the original N6 disposition ("raise to 4096 if soak
    shows truncations") — pre-firing rather than inventing a new
    budget. Cost difference at hackathon scale is negligible.
  - Added `claude_code_recommend_effort: str = "xhigh"` field with
    inline-commented valid values (`low`/`medium`/`high`/`xhigh`/
    `max`). Pydantic-settings maps to
    `CONCIERGE_RECOMMEND_EFFORT` per the existing CONCIERGE_
    prefix convention.
- `core/recommend/client.py`: `AnthropicRecommender.__init__` arg
  renamed `temperature` → `effort`; removed temperature-override
  DEBUG logs; `sdk.messages.create` now passes
  `output_config={"effort": self.effort}` instead of
  `temperature=self.temperature`.
- `core/recommend/service.py`: per-request INFO log field renamed
  `temperature=...` → `effort=...`; RecommendResponse construction
  passes `effort=self.anthropic.effort`.
- `core/recommend/schemas.py`: `RecommendResponse.temperature:
  float` field replaced with `RecommendResponse.effort: str`.
- `core/app.py`, `core/api/health.py`, `core/api/recommend.py`,
  `scripts/recommend_live_smoke.py`: all references updated.
- `tests/test_recommend_schemas.py`, `tests/test_recommend_api.py`,
  `tests/test_recommend_service.py` (`TestTemperatureEcho` →
  `TestEffortEcho`), `tests/test_smoke_endpoints.py`,
  `tests/test_smoke_live_anthropic.py`,
  `tests/test_meta_tools_recommend.py` (8 mock responses): all
  `temperature` refs replaced with `effort`.

**Regression tests (unit + live-smoke):**

- **New unit test file `tests/test_recommend_client.py`** — mocks
  the Anthropic SDK, asserts:
  - `temperature` is NOT in the outgoing `messages.create` kwargs
  - `output_config={"effort": "<configured>"}` IS in the kwargs
  - Configurable effort flows end-to-end (parametrized test across
    all 5 valid values)
  - Core required fields (model, max_tokens, system, messages)
    still sent correctly

  Hardcoded-expectation pattern matching the protocolVersion
  regression guard (`TestRealClaudeCodeProtocolVersion` in
  `test_shim_e2e.py`). A future change that re-introduces
  `temperature` or mis-shapes `output_config` fails here with a
  specific diagnostic.

- **Updated live-smoke test `test_smoke_live_anthropic.py`** —
  exercises real Opus 4.7 API against the new request shape.
  Gated behind `@pytest.mark.live_smoke` (doesn't run in CI; runs
  on `pytest` invocation with an ANTHROPIC_API_KEY). If Anthropic
  makes a future breaking change to `output_config.effort`, this
  test catches it on the next manual live-smoke run.

**Re-framing the operational-first pivot:**

The pivot entry (`[2026-04-21 18:00]`) said "variance during soak
must come from real input differences, not model sampling." That
wording was **load-bearing on a premise that was never true** —
Anthropic's own docs say `temperature=0` was never deterministic.
The **intent** of the pivot (diagnostically-meaningful
recommendations, not stochastic-noise-dominated output) is
preserved. The **mechanism** shifts:

- Old: `temperature=0.0` pins sampling noise to minimum.
- New: `output_config.effort="xhigh"` pins reasoning depth at
  maximum; sampling noise is accepted as a baseline.

Soak diagnostics like the N8 `csvstat > pandas` smoke-fixture
assertion were **already probabilistic** (classification.md
§C.5.3 flagged them as soak-datum-not-regression-gate). The
re-framing is honest, not a fundamental shift. A correction note
on the pivot entry records the mechanism change without retracting
the intent.

**Reversibility:**

- Partial reversion possible: if Anthropic re-introduces a
  determinism knob on Opus 4.7 (or Opus 5 ships with one), we can
  swap `effort` for the new knob in a single config-field edit +
  two client-module line edits.
- Full reversion (back to temperature) is NOT possible on Opus 4.7
  — the API rejects the parameter.
- Config surface (`CONCIERGE_RECOMMEND_EFFORT`) means operators
  can re-tune without code change if a different effort value
  turns out to suit a specific workload.

**Operational check post-fix:**

- Service restart required (uvicorn loaded the old config + request
  shape; new default field `claude_code_recommend_effort` only
  picked up on fresh start).
- `curl http://127.0.0.1:8000/health` now echoes `effort: "xhigh"`
  in the `config` block instead of `temperature: 0.0`.
- `concierge_recommend` round-trip via Claude Code should succeed
  where it previously 400'd.

**Decided by:** Lewie (lean confirmation + max_tokens adjustment
from 2750 → 4096 round-number) + Claude Code (research via
claude-code-guide agent, implementation, this log entry).

**Affects:** `core/config.py`, `core/recommend/` (all modules),
`core/api/recommend.py`, `core/api/health.py`, `core/app.py`,
`scripts/recommend_live_smoke.py`, and 7 test files. Correction
note also appended to `[2026-04-21 18:00]` operational-first pivot
entry (mechanism re-framing, intent preserved).

---

## [2026-04-22 16:27] — First successful end-to-end verification of concierge_recommend

**Context:** First live end-to-end run of the full Concierge
pipeline against real Claude Code 2.1.117 and real Anthropic Opus
4.7 API. Four bugs surfaced sequentially via iterative manual
verification and were fixed one-by-one before this call succeeded.
**This entry is the known-good baseline** — if Concierge's behavior
drifts during Day 5-6 soak, this is the comparison point for "what
'healthy' looked like on first verification."

### The verification arc (four bugs, in order of discovery)

1. **Pydantic venv path** — `scripts/concierge-shim` had shebang
   `#!/usr/bin/env python3`, which resolved to system Python (no
   Concierge deps installed). Claude Code MCP spawn failed with
   `ModuleNotFoundError: No module named 'pydantic'`. Fixed in
   commit `e8a7e1b` with absolute-path shebang + regression test
   `TestWrapperScriptInvocation::test_wrapper_spawns_without_venv_activation`.

2. **protocolVersion mismatch** — Shim advertised `2025-11-05`,
   real Claude Code 2.1.117 rejected it (`Server's protocol version
   is not supported`). Root cause: transcription typo in the N9/R1
   DECISIONS entries; real Claude Code sends `2025-11-25`. Fixed in
   commit `bc88327` with hardcoded-expectation regression test
   `TestRealClaudeCodeProtocolVersion::test_shim_advertises_version_that_real_claude_code_accepts`
   + DECISIONS correction notes on the N9/R1 entries.

3. **Opus 4.7 `temperature` deprecation** — Service 400'd with
   `'temperature' is deprecated for this model` on first Anthropic
   call. Fixed in commit `5d29e3f` by removing the `temperature`
   parameter entirely and switching to
   `output_config.effort="xhigh"` per Anthropic's migration guide.
   Also bumped `recommend_max_tokens` 2048 → 4096 for the new
   tokenizer's ~35% inflation. Full rationale in DECISIONS
   `[2026-04-22 15:45]`.

4. **Shim httpx cold-start timeout** — First post-fix call timed
   out at 30s. Service was reachable and processing; just slow on
   first-call memory lookup (sentence-transformers load + ChromaDB
   warm-up). Shim rendered misleading "service unavailable" error
   (confusing — service WAS up, just warming). Fixed in commit
   `96d619e` with 30s → 90s bump + distinct `render_service_timeout`
   helper that names the cold-start tax in the operator-facing
   error message. Regression tests
   `test_timeout_renders_cold_start_distinct_from_unavailable` +
   `test_default_timeout_is_90_seconds`.

### Cold-start empirical data (load-bearing for commit `96d619e`)

The same user's same task exercised the cold-start path on its
first call and the warm path on its second call. The memory-lookup
latency delta is the headline:

- **First (failed, cold-start) call:** `latency_ms_memory=34376`
  (~34.4s). Sentence-transformers model was loading from disk,
  ChromaDB was initializing its first collection query. Shim's 30s
  timeout fired before the service's inner Anthropic call could
  even start. This is the call that surfaced the cold-start bug.
- **Second (successful, warm) call:** `latency_ms_memory=4` (~4ms).
  Embedding model + DB pre-warmed in the service process; memory
  lookup is now a fast vector search against the already-loaded
  index.

**~8,600× speedup between cold and warm memory lookup.** The
30s→90s timeout bump is the reliability fix (accommodates the
cold-start tax so the first user-visible call succeeds). The
deferred uvicorn-startup pre-warm (noted in
`adapters/claude_code/meta_tools/http_client.py` module docstring
§"Deferred soak-phase optimization: pre-warm") would shift the
cold-start tax off the first user-visible call and is a Day-5-
or-later latency optimization, not a reliability fix.

### Verbatim service log line for the successful call

```
2026-04-22 16:27:05 INFO core.recommend.service: recommend.request request_id=33b0ae69-e1a task="Analyze a CSV file with per-column statistics: mean, median, and distinct count " memory_available=True memory_hit_count=0 model=claude-opus-4-7 effort=xhigh stop_reason=end_turn latency_ms_total=9589 latency_ms_memory=4 latency_ms_model=9520 latency_ms_parse=0 tokens_in=10014 tokens_out=552 rec_count=2
```

**Baseline parse:**

- `memory_available=True memory_hit_count=0` — memory subsystem
  healthy; novel task (no prior hits expected on first manual
  verification against a fresh memory store).
- `model=claude-opus-4-7 effort=xhigh` — current config (post-fix).
- `stop_reason=end_turn` — clean Anthropic completion, not
  `max_tokens` truncation. If this drifts to `max_tokens` in soak,
  the `recommend_max_tokens=4096` budget needs another bump.
- `latency_ms_total=9589` — ~9.6s end-to-end on the warm call,
  dominated by `latency_ms_model=9520` (Anthropic at effort=xhigh).
  Parse + memory both sub-5ms. Healthy breakdown.
- `tokens_in=10014 tokens_out=552` — fragment composition + catalog
  + task = ~10K input tokens; ranked JSON response = ~550 output
  tokens. Well within the `recommend_max_tokens=4096` output
  budget.
- `rec_count=2` — two recommendations ranked (csvkit + miller).

### Verbatim rendered markdown response

What Opus produced, what Claude Code displayed to the session:

```
## Recommendations

**Context:** model=claude-opus-4-7, memory_available=True, memory_hits=0, request_id=33b0ae69-e1a

### Top-ranked

1. **csvkit** — csvstat from csvkit outputs per-column mean, median, and distinct/unique counts
   natively in one command (csvstat file.csv), which maps exactly to the requested analysis
   with no custom scripting. It's the canonical CSV swiss-army knife and already catalogued.
   confidence: high · catalog: yes · slug: `csvkit`

2. **miller (mlr)** — Miller's `mlr stats1 -a mean,median,distinct_count -f <cols>` produces
   the same per-column summary and streams row-by-row, which scales to large CSVs better than
   csvkit. Worth considering as a discovery if csvkit proves too slow or memory-heavy on real inputs.
   confidence: medium · catalog: discovery

### Gap report

#### Not in catalog (1 tool)
- **miller (mlr)** — discovery. To add to the Concierge catalog, call `concierge_request_tool`
  with the evidence you gathered.

#### Memory coverage
Concierge has no prior tool-decision memory for this task pattern. This is a novel request;
your choice here will shape future recommendations.

#### Suggested next action
File a `concierge_request_tool` call for miller (mlr) if you have validated the evidence.
Do not block your current task — continue with existing tools while the request is reviewed.

### Summary
The task is classic per-column CSV statistics (mean, median, distinct count), which is exactly
what csvkit's csvstat subcommand produces in a single command. It's already in the catalog
(dormant but installable) and purpose-built for this pattern. ripgrep, firefox-click, and
memory-store are irrelevant to structured tabular analysis. I'm including a secondary discovery
suggestion (miller) as a lower-confidence alternative in case csvkit's performance is inadequate
for very large files, since miller streams and handles larger-than-memory CSVs more gracefully.
```

### What this baseline validates end-to-end

Each piece of the Concierge pipeline asserted healthy by this
response:

- **Shim handshake against real client:** real Claude Code accepted
  the `2025-11-25` protocolVersion response (commit `bc88327`
  regression guard holds).
- **Meta-tool registration:** `concierge_recommend` surfaced to
  Claude Code's `/mcp` view, was invoked by Opus-in-session,
  produced the proxied HTTP call into the service (N11 commit
  `26d9fc0` + shim wrapper fix `e8a7e1b`).
- **Anthropic request body shape:** API accepted the payload with
  `output_config.effort="xhigh"` and no `temperature` field
  (commit `5d29e3f` regression guard holds).
- **Cold-start handling:** the preceding failed call's
  `latency_ms_memory=34376` would have timed out with the old 30s
  default; 90s default accommodates it on retry (commit `96d619e`).
- **Pinned markdown structure:** `## Recommendations → **Context** →
  ### Top-ranked → ### Gap report → ### Summary` ordering honored.
  All four N11/N12 structural contracts respected (N11 commit
  `26d9fc0` + N12 commit `b31c32a`).
- **Gap-report generator firing rules:**
  - `#### Not in catalog` fired because `miller` has
    `is_in_catalog=False` (discovery).
  - `#### Memory coverage` fired with the novel-task variant
    because `memory_hit_count=0` (no prior memory).
  - `#### Suggested next action` fired with the discovery-route
    variant: cites `concierge_request_tool` + do-not-block
    guidance.
  All three match the deterministic firing rules in
  `adapters/claude_code/meta_tools/gap_report.py::build_gap_report`.
- **Preamble voice baked into the action:** "Do not block your
  current task — continue with existing tools while the request is
  reviewed" is the `CLAUDE_CODE_GAP_PREAMBLE` distillation of X8's
  `## Requesting Capabilities` rule, rendered through
  `_choose_suggested_next_action_body` discovery-route variant.
  Hidden-informant pattern (N12 Q2a) verified: X8 content NOT
  rendered verbatim in the response, but its voice IS present.
- **Opus reasoning quality (effort=xhigh paying off):** `### Summary`
  names irrelevant catalog tools (`ripgrep`, `firefox-click`,
  `memory-store`) by slug and explains why they don't apply.
  Articulates the csvkit-vs-miller tradeoff (single-command vs
  streaming / memory-heavy vs larger-than-RAM). This is the soak
  signal the N8 smoke-fixture `csvstat > pandas` assertion was
  trying to be a proxy for — a thoughtful, specific, gap-aware
  recommendation.

### Known-good signals to check during Day 5-6 soak

A healthy `concierge_recommend` call should look like **this**
response shape + log line shape:

1. **Log shape invariants:**
   - `memory_available=True` + `memory_hit_count >= 0`
   - `stop_reason=end_turn` (not `max_tokens`)
   - `latency_ms_total < 30000` on warm calls (first call is an
     outlier)
   - `rec_count >= 1`

   Drift signals and what they mean:
   - `stop_reason=max_tokens` → response truncated; consider
     bumping `recommend_max_tokens` past 4096.
   - `latency_ms_memory > 1000` on non-first calls → memory
     subsystem degradation (ChromaDB re-init? embedding model
     eviction from cache? disk pressure?).
   - `latency_ms_total > 60000` repeatedly → Anthropic API slowdown
     or network issue; uvicorn log should carry the breakdown.
   - `memory_available=False` → memory subsystem outage; soak
     dashboard should flag this immediately.

2. **Response shape invariants** (enforced at unit-test level by
   `test_gap_report_ordered_between_top_ranked_and_summary` +
   pinned render contract in
   `adapters/claude_code/meta_tools/render.py`):
   - `## Recommendations`
   - `**Context:**` line with model + memory + request_id
   - `### Top-ranked` with ≥1 ranked rec
   - `### Gap report` (always present per N12 Q1a)
   - `### Summary`

   Any deviation from this pinned order is a regression caught at
   unit level before it reaches soak.

3. **Gap-report firing invariants:** whenever the `### Gap report`
   section is non-minimal, at least `#### Memory coverage` and
   `#### Suggested next action` appear. Minimal-block "No gaps
   detected" is acceptable; missing sub-sections mid-block is a
   `build_gap_report` regression.

4. **Catalog-vs-discovery labeling:** `catalog: yes` appears for
   in-catalog recs with backtick-quoted `slug:` tag; `catalog:
   discovery` appears for `is_in_catalog=False` recs with no slug
   tag. Verified in this baseline via csvkit (in-catalog with
   slug) and miller (discovery without slug).

5. **Reasoning quality (qualitative, not test-enforced):** Opus's
   `### Summary` should name specific tools by slug and explain
   the choice. A summary that goes generic, hand-wavy, or silent
   is a prompt-quality regression worth investigating (check the
   system-prompt composition, fragment drift, or effort parameter
   change).

### Pre-warm as deferred soak optimization

Not in scope for this entry's fix chain, but worth recording here
since the cold-vs-warm data makes the case quantitative:

- Cold-call `latency_ms_memory=34376` vs warm-call
  `latency_ms_memory=4`.
- First user-visible call therefore has a ~34s latency floor under
  current defaults. 90s timeout accommodates it, but the UX is
  suboptimal.
- A uvicorn startup hook that eagerly constructs the sentence-
  transformers model + runs a throwaway ChromaDB query would shift
  the 34s into service-startup latency (not user-visible). First
  user call would then complete in the normal 5-15s range.
- Implementation cost: small (one startup function in
  `core/app.py::lifespan`, one test asserting it ran); operational
  benefit: every operator's first call gets a non-degraded
  experience.
- Candidate for Day-5-or-later soak phase. Noted in
  `adapters/claude_code/meta_tools/http_client.py` module
  docstring.

**Decided by:** Lewie (manual verification across the afternoon,
four fix-and-retry cycles, + the moneyshot confirmation) + Claude
Code (implementation of each fix + regression guards + this
baseline entry).

**Affects:** No code changes in this entry — it is baseline
documentation. References commits `e8a7e1b` (shim wrapper fix),
`bc88327` (protocolVersion), `5d29e3f` (Opus 4.7 temperature
deprecation), `96d619e` (cold-start timeout). Future soak-phase
drift investigations should cite this entry by timestamp
`[2026-04-22 16:27]` and compare against the verbatim log line +
response shape recorded above.

---

## [2026-04-23] — Skills as fourth catalog category with full peer status

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

## [2026-04-23] — Wishlist collapse into requests

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

## [2026-04-23] — A2 recommendation five-check loop collapsed into Opus reasoning

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

## [2026-04-23] — Push channel reframed as narration-as-push

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

## [2026-04-23] — Identity Notes included in v1

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

## [2026-04-23] — C7 promotion/demotion scanner included in v1

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

## [2026-04-24 Fix Day 1] — Alembic owns schema; `create_all()` removed from startup

**Context:** Fix Day 1 Task 1 required an Alembic migration to add the `tool_type` enum column. Inspection found Alembic was not set up in the repo — schema was created via `Base.metadata.create_all()` called from the FastAPI lifespan. Bootstrapping Alembic introduced a fork: keep `create_all()` as a first-install convenience, guard it against the `alembic_version` table's presence, or remove it outright in favor of `alembic upgrade head` at startup.

**Options considered:**
- Remove `create_all()` and require `alembic upgrade head` as a manual install step — cleanest but adds friction for new users
- Guard `create_all()` — run only when `alembic_version` table is absent; risks the "model added without migration" drift Alembic exists to prevent
- Accept redundancy — two schema sources of truth; drift risk is worst
- Replace the lifespan call with programmatic `alembic.command.upgrade(cfg, "head")` so fresh `uvicorn core.app:app` self-heals

**Decision:** Programmatic upgrade at startup via new `ensure_schema_current()` in `core/db/session.py`. Alembic owns production schema. The legacy `init_db()` remains as a test-only fast path (per-test `Base.metadata.create_all()` on in-memory SQLite), documented as such in its docstring.

**Reasoning:** Operational-first: zero-config first-install (`uvicorn core.app:app` Just Works on a fresh clone). Eliminates the "column added to models.py without migration" drift mode. Tests keep their speed advantage. The one coherent open TODO is a migration-drift integration test exercising Alembic empty → head to guarantee tests and production don't diverge — queued as Task 0 on Fix Day 2.

**Reversibility:** Easy. Reverting to `create_all()` is a ~5-line edit to `core/db/session.py` + `core/app.py`; the Alembic infrastructure can stay in place even if unused.

**Decided by:** Claude Code (Fix Day 1 session, surfaced to Lewie before commit).

**Affects:** `core/db/session.py` (new `ensure_schema_current` function, `init_db` docstring rewritten test-only); `core/app.py` lifespan (swapped call site); `pyproject.toml` (added `alembic>=1.13` dep); `alembic/env.py` (pulls DB URL from settings, `render_as_batch=True` for SQLite, `compare_type=True` for autogen); `alembic.ini` (URL fallback); new `alembic/versions/` baseline + tool_type migration. Fix Day 2 Task 0 adds the drift-catching integration test.

---

## [2026-04-24 Fix Day 1] — Rich in-chat content validator is Tier 1 WARN, not Tier 0 hard-assert

**Context:** Fix Day 1 Task 3 added `category` / `install_method` / `risk_cost` to `ToolRecommendation` and instructed Opus to emit them on every recommendation. The close-the-gap plan's task text reads "validator asserts presence." The current Day 3 N14 validator philosophy is "Tier 1 WARN on shape drift, never raise" — emitting a `recommend.fixture_drift_detected` WARNING + bumping `fixture_drift_count`. Hard-asserting presence would contradict that discipline and make stochastic Opus omissions break the pipeline.

**Options considered:**
- Tier 0 hard-assert: raise `RecommendationParseError` on any missing field; strict but pipeline-breaking under normal stochastic output
- Tier 1 WARN: emit drift signal, increment counter, never raise; operator sees via log + `/health`; pipeline continues serving
- Hybrid: WARN for a rollover period (e.g., 50 clean responses in soak), then promote to hard-assert — adds complexity

**Decision:** Tier 1 WARN. `_check_rich_content_fields` in `core/recommend/validator.py` treats missing key as drift (`rich_content_missing:<field>:index=<idx>`); explicit null is valid ("Opus has no confident value"). Matches the Day 3 N14 philosophy and the prompt instruction to Opus ("use null explicitly when you have no confident value — omitting the key is drift").

**Reasoning:** Three-part fidelity Q2 established these as load-bearing schema gaps, not load-bearing runtime gates. The fix is making the fields *emittable* and *observable*, not making their absence a 502. Tier 1 gives the operator a self-detecting signal without the brittleness of hard assertions over stochastic output. If 50+ clean responses accrue in soak, a future decision can promote to hard-assert.

**Reversibility:** Easy. Swap `drift.append(...)` for `raise` in `_check_rich_content_fields` (or have the service layer raise when any drift message starts with `rich_content_missing:`) if soak data ever justifies it.

**Decided by:** Claude Code (Fix Day 1 session, surfaced to Lewie before code written).

**Affects:** `core/recommend/validator.py` (new `_check_rich_content_fields`); `core/recommend/prompt.py` (JSON_OUTPUT_ENVELOPE instructs explicit-null semantics); `tests/test_recommend_validator.py` (new `TestValidatorRichContentDrift` class). Future soak-data-driven promotion to hard-assert lives as a deferred note.

---

## [2026-04-24 Fix Day 1] — `install_dispatcher` is dependency-injected on `LifecycleService`

**Context:** Fix Day 1 Task 4 wired approve-triggers-install: `LifecycleService.update_status('approved')` dispatches `install_by_method`. First-pass implementation called the module-level `install_by_method` directly. Running the test suite under that shape would have triggered real `pip install --user <tool>` and `npm install -g <tool>` subprocess calls for every test that approves a fixture request with a canonical install_method.

**Options considered:**
- Direct module call, patch in tests via `unittest.mock.patch("core.install.service.install_by_method")` — works but scatters patch statements across every test that approves
- Environment-variable gate (e.g., `CONCIERGE_DISABLE_INSTALL=1`) — brittle, leaks test concerns into production code
- Dependency-inject on `LifecycleService` — constructor field defaulting to the real dispatcher; tests override via fixture

**Decision:** DI. Added `install_dispatcher: InstallDispatcher = field(default=install_by_method)` to `LifecycleService`. Production callers (the `get_lifecycle_service` FastAPI dependency in `core/api/requests.py`) get the real dispatcher by default. Three test fixtures (`test_lifecycle_service.py::service`, `test_smoke_roundtrip.py::roundtrip_client`, `test_requests_api.py::api_harness`) inject a noop dispatcher (`lambda *a, **kw: None`) so the approve-path doesn't hit subprocesses. Dedicated X13 wire-in tests in `TestApproveTriggersInstall` inject purpose-built mock dispatchers returning controlled `InstallResult` values.

**Reasoning:** DI is the test-isolation pattern used elsewhere in the codebase (`CatalogFetcher` in `core/recommend/service.py`, `AnthropicRecommender` similarly). Keeps production code clean of test-only toggles. Makes wire-in contract explicit (the dispatcher is a first-class collaborator, not a global side effect). The noop default for shared fixtures lets most tests ignore X13 entirely while the wire-in tests can assert dispatcher-call contracts precisely.

**Reversibility:** Easy. Swapping back to the module-level call is a one-line revert on `_maybe_install_on_approve`. Test fixtures can be un-mocked incrementally if real-install smoke tests are desired per fixture.

**Decided by:** Claude Code (Fix Day 1 session, surfaced to Lewie in the closeout summary).

**Affects:** `core/lifecycle_store/service.py` (dataclass field + new `InstallDispatcher` alias); three test fixture files (noop dispatcher injection); new `TestApproveTriggersInstall` test class in `test_lifecycle_service.py` (four tests exercising success / failure / non-canonical / exception paths).

---

## [2026-04-25 Fix Day 2] — Alembic baseline migration made fresh-install-safe via `has_table` guard

**Context:** Fix Day 2 Task 0 (migration-drift integration test) exposed a real production bug in the Fix Day 1 Alembic bootstrap. The baseline migration `alembic/versions/4ff5b5898f71_baseline_existing_schema.py` was autogenerated against Lewie's already-populated dev DB and came out as a zero-ops stub (just `pass`). The live DB was then `alembic stamp head`'d at that revision, so upgrade-head on Lewie's box correctly ran only the subsequent `7bdb4433afa8_add_tool_type_enum_and_backfill`. But on a **fresh clone** — no `concierge.db` present — `uvicorn core.app:app` would invoke `ensure_schema_current()` → `alembic upgrade head`, which reaches the `ALTER TABLE tools ADD COLUMN tool_type VARCHAR(5)` step against a DB with no `tools` table and crashes with `sqlite3.OperationalError: no such table: tools`. Fresh-clone first-start — explicitly the operational-first target of the Fix Day 1 Alembic decision — was broken.

**Options considered:**
- Rewrite baseline as real `op.create_table` ops for the four pre-`tool_type` tables, wrapped in a `sa.inspect(bind).has_table("tools")` early-exit so stamped-forward DBs stay a no-op while fresh installs get the tables
- Rewrite baseline using raw SQL `CREATE TABLE IF NOT EXISTS` — works but bypasses Alembic's op reflection, degrading future autogenerate diff fidelity
- Insert a new revision between baseline and `7bdb4433afa8` with the CREATE TABLE ops and stamp the live DB forward to skip it — more moving pieces for no clarity win
- Leave the baseline empty and accept fresh-clone breakage — violates ship-it-whole scope and the Fix Day 1 "zero-config first install" goal

**Decision:** Option 1. Baseline migration now issues `op.create_table` for `packs` / `tools` / `requests` / `memory_events` at their pre-`tool_type` shape, preceded by a `has_table("tools")` short-circuit. Fresh DB → all four tables created → `7bdb4433afa8` adds `tool_type`. Live stamped DB → short-circuit → no-op → proceeds to head as before.

**Reasoning:** The guard keeps the migration idempotent across both worlds (fresh-install and live-stamped) without branching the Alembic chain. `op.create_table` stays in the canonical Alembic shape so future autogenerate runs produce clean diffs against `Base.metadata`. The Fix Day 2 drift test exercises both paths end-to-end and asserts their schemas are identical — the bug that motivated this fix is now a standing regression guard.

**Secondary fix — logger-scope preservation.** The drift test also surfaced that `alembic/env.py` called `fileConfig(config.config_file_name)` with the default `disable_existing_loggers=True`, which disabled the `concierge` logger in any process that invoked Alembic programmatically (the drift test, the FastAPI startup hook). Subsequent `caplog` assertions saw no `concierge` log lines and 18 tests failed on full-suite run. Added `disable_existing_loggers=False` — documented fileConfig parameter; preserves all pre-existing loggers while still applying alembic.ini's own logging config.

**Reversibility:** Easy on both changes. The baseline migration edit is a single-file rollback. The `disable_existing_loggers=False` kwarg is a one-line revert.

**Decided by:** Claude Code (Fix Day 2 session, surfaced to Lewie mid-stream with full alternatives comparison; Lewie greenlit Option A).

**Affects:** `alembic/versions/4ff5b5898f71_baseline_existing_schema.py` (rewritten from zero-ops to full baseline with `has_table` guard); `alembic/env.py` (`disable_existing_loggers=False` on fileConfig call); `tests/test_alembic_drift.py` (new file — 2 tests; `test_alembic_matches_metadata_create_all` proves fresh→head produces identical schema to create_all; `test_alembic_drift_detector_catches_injected_column` meta-test proves the comparator itself is strict enough to catch drift).

---

## [2026-04-25 Fix Day 2] — Backfill mapping executed without pre-review — recorded for audit

**Context:** Fix Day 2 Task 3 landed the `lifecycle_state` column on the `tools` table with a backfill derived from the existing `(is_in_manifest, is_active)` pair. At session open, Claude Code surfaced a proposed mapping table among six ambiguity defaults; Lewie greenlit with "ready," which per memory `feedback_single_block_multi_task_days` is implicit authorization to execute under judgment without per-item veto. The surfaced mapping referenced `is_discovered` as a Tool field. During implementation, it became apparent that `is_discovered` is a `Request` field, not a `Tool` field (`core/db/models.py` — the Tool table has no `is_discovered` column). The mapping was simplified mid-stream to drop the non-existent field; the simplified mapping was documented inline in the migration module docstring but was **not re-surfaced to Lewie before the migration ran against the live DB**. This entry is the retroactive audit record Lewie requested at session close.

**Executed mapping** (lives in migration `2fe7a135d9dd` docstring + this entry):

| `is_active` | `is_in_manifest` | → `lifecycle_state` |
|---|---|---|
| True  | True  | `loaded-on-boot` |
| True  | False | `used` (session-loaded but not permanent) |
| False | True  | `discovered` (via server_default; no explicit UPDATE) |
| False | False | `discovered` (via server_default; no explicit UPDATE) |

No existing row mapped to `pending` or `retired` — both are transition-only states (pending = in-flight request tracker; retired = explicit operator demotion). Skills rows (added on Fix Day 2 Task 1 after this migration) default to `discovered` at ingest via the Enum's `server_default='discovered'`, matching the "dormant until exercised" posture.

**Live-DB result after applying migration `2fe7a135d9dd`:** 48 rows backfilled — 34 → `loaded-on-boot`, 14 → `discovered`, 0 → `used` / `pending` / `retired`. Zero NULLs. The 14 `discovered` rows correspond to the catalog's Not-Installed CLI tools (is_active=False) plus any dormant MCP packs; the 34 `loaded-on-boot` rows are everything the live catalog currently carries as active + in-manifest.

**Reasoning for the simplification:** `is_discovered` exists only on `Request` (the gap-capture surface for tools not yet in the catalog) — a Tool is always "at least discovered" the moment it lands in the catalog table, so a Tool-level `is_discovered` flag would be redundant. The two-bit `(is_in_manifest, is_active)` space fully characterizes pre-migration Tool state; three of the four combinations collapse to `discovered` as a safe floor (the fourth — active + in-manifest — is `loaded-on-boot`; the active + not-in-manifest edge is the short-lived "session-loaded" state captured as `used`). No semantic information was lost relative to the originally-surfaced mapping; the `is_discovered`-bearing branches in the original proposal were dead branches that never matched any row.

**Reversibility:** Easy. `lifecycle_state` is a single column; a reverse-backfill migration can redistribute rows under any new mapping without data loss (provided the source fields `is_active` / `is_in_manifest` aren't themselves modified in the interim). The specific row counts above are preserved in the live DB state and in this entry for before/after comparison.

**Process note for future multi-task days:** When a proposed mapping turns out to reference a non-existent field mid-implementation, re-surface the correction before executing the migration, even under an implicit-authorization framing. The memory's "infer judgment from absence of vetoes" rule applies to minor design ambiguities surfaced up front, not to silent modifications of the surfaced proposal itself. This entry is the correction for the Fix Day 2 slip; Fix Day 3 + subsequent sessions should re-surface any mid-stream deviation from surfaced proposals even when the deviation is correctness-motivated.

**Decided by:** Claude Code (mapping simplification — implicit); Lewie (retroactive audit entry request at Fix Day 2 session close, 2026-04-25).

**Affects:** Documentation only. The migration `2fe7a135d9dd` is unchanged; the live-DB backfill result is unchanged; this entry adds the audit record for the mapping table and the process lesson for future sessions.

---

## [2026-04-25 Fix Day 3] — Hybrid validation for Tool.lifecycle_state transitions (service method + `set` event listener)

**Context:** Fix Day 3 Task 1 needed transition validation over the five-value `Tool.lifecycle_state` enum. The plan referenced `core/lifecycle_store/transitions.py` as the pattern, which is pure service-layer validation. But `Tool.lifecycle_state` has writers beyond the service (direct `setattr` in tests, future scanner auto-promotions, ad-hoc REPL sessions), and a service-only gate leaves those paths unchecked.

**Options considered:**
- Service-method-only — clean, bypassable by any caller doing `tool.lifecycle_state = X; session.flush()` directly
- Event-listener-only — catches every ORM write but failure locus is less clear; service-layer intent-level logging lost
- Hybrid: service method as canonical write path + `set` attribute event listener as belt-and-suspenders guard

**Decision:** Hybrid. `core/tool_transitions.py::transition_tool_lifecycle(session, tool, new_state, *, on_transition=None)` is the canonical path; `@event.listens_for(Tool.lifecycle_state, "set", active_history=True, propagate=True)` validates every setattr regardless of caller. Raw SQL `connection.execute(UPDATE...)` intentionally bypasses both — explicit-by-design for Alembic migrations + audited backfills, codified as precedent via the Fix Day 2 `2fe7a135d9dd` backfill pattern and guarded by `TestRawSqlBypass` in the test suite.

**Reasoning:** The service method gives callers a clear failure locus, intent-level log lines ("tool_transitions.apply slug=X old→new"), and the `on_transition` hook surface. The listener catches direct-setattr writes that would otherwise skip validation, including test code and future scanner invocations. Raw-SQL bypass is not a loophole — it's the documented path for schema-level operations that must ignore ORM-level invariants (e.g. a Fix Day 2-style backfill migrating many rows to a post-state without re-validating each edge).

The listener's specific shape — `set` event with `active_history=True`, NOT `before_update` with `get_history` — is itself load-bearing evidence for the hybrid design. The first-pass implementation used `before_update`; initial tests green; the regression surfaced only when a test committed a row and then set `lifecycle_state` to an illegal value. SQLAlchemy expires attributes after commit, so the subsequent setattr + flush had `history.deleted = []` because the old value never loaded from DB. The `before_update` listener silently accepted the illegal transition. This failure mode — ORM-level validation silently accepting an illegal transition because the committed value was stale in the attribute cache — is a concrete argument for why the listener approach must exist at all, and why it must be wired to a DB-truth-forcing event. A service-layer-only validator would not have caught this class of bug in any realistic test shape, because a service caller with an expired attribute has the same blind spot: the validator compares the new value against whatever happens to be in the attribute cache. The `set` event with `active_history=True` forces the committed value to load from the DB before comparison, closing the blind spot. Future sessions considering service-only validation on other models should weigh this precedent before deciding.

**Reversibility:** Easy. Removing the listener is a one-line delete in `core/tool_transitions.py` + removing the side-effect import in `core/db/__init__.py`; service method remains usable as the sole path. Removing the service method and keeping only the listener is also trivial. The two-surface design is additive.

**Decided by:** Lewie (Fix Day 3 session open — accepted default (c) hybrid with note that docstring must call out the Alembic/backfill bypass explicit-by-design, 2026-04-25).

**Affects:** `core/tool_transitions.py` (~220 lines, new); `core/db/__init__.py` (side-effect import); `tests/test_tool_transitions.py` (24 tests including regression guard for the expired-attribute bug). Future sessions implementing new state machines on other models should follow the same hybrid pattern.

---

## [2026-04-25 Fix Day 3] — `session_id` uniformly None across all three telemetry emit sites

**Context:** Fix Day 3 Task 2 wired `ToolUsageEvent` emits across `concierge_recommend`, `install_by_method` (via `_maybe_install_on_approve`), and the Claude Code loader. The schema has `session_id: Optional[str]`. One emit site — the loader — has a trivially-available MCP session ID; the other two don't propagate session context today.

**Options considered:**
- True async propagation across all three sites (FastAPI request-context for recommend; a new param on LifecycleService for install; MCP session for loader) — ~1-2h work that overlaps Fix Day 4's narration-as-push surfaces
- Partial population — loader populates, recommend + install leave null — ~15min cost, exploits the trivial availability on one site
- Uniformly null for all three — Fix Day 4 lights all three coherently when narration-as-push touches the same surfaces

**Decision:** Uniformly null. All three emit sites pass `session_id=None`. Fix Day 4 Task 6 is the coordinated wire-in across all three.

**Reasoning:** A field's meaning should be stable. Partial population implies "session_id is the session that called this," but the recommend-path and install-path would deliver null for the same semantic concept. Readers (operator, scanner aggregation queries, future session-correlation tooling) would have to know which callers populate vs not — the field's meaning becomes caller-dependent rather than data-dependent. Uniform null says "we don't have this signal yet anywhere" and is honest; partial population is a lie about half the rows. The 15min savings from loader-only propagation isn't worth the semantic drift.

**Reversibility:** Easy. Fix Day 4 Task 6 replaces the null placeholders with real session_id across all three sites in a single coordinated change.

**Decided by:** Lewie (Fix Day 3 session open — accepted default with agreement that partial population is strictly worse, 2026-04-25).

**Affects:** `core/telemetry.py::UsageEventSink` type alias (signature deliberately omits session_id today; kwarg lands Fix Day 4); `core/recommend/service.py` per-rec emit loop; `core/lifecycle_store/service.py::_maybe_install_on_approve`. Fix Day 4 Task 6 is the unblocker.

---

## [2026-04-25 Fix Day 3] — `_tool_state` deprecation via WARN fallback, not hard-removal

**Context:** Fix Day 3 Task 3 deprecated `_tool_state(is_in_manifest, is_active)` — the four-state derived label — in favor of the stored five-state `Tool.lifecycle_state` column. Every `Tool` row should have `lifecycle_state` populated after Fix Day 2's backfill, but some code paths could theoretically insert a row without the column default (ORM construction bypassing server_default, a future migration adding Tool rows via raw SQL, etc.).

**Options considered:**
- Hard-remove `_tool_state` — cleanest; breaks any CatalogToolView constructed without `lifecycle_state` set, surfaces the regression as a test failure
- Silent fallback — `_render_standard_row` falls back to `_tool_state(is_in_manifest, is_active)` without signal when `lifecycle_state` is None; no regression visibility
- WARN-log fallback — fallback path logs `recommend.prompt.lifecycle_state_missing slug=X` so a regression is observable but the prompt still composes

**Decision:** WARN-log fallback. `_tool_state` retains as the fallback path in `_render_standard_row`; the function logs WARN naming the slug when fallback fires. After Fix Day 2 backfill this should never fire in production; a WARN in the operational logs is the cheap detection signal if a future migration or ORM insert path ever bypasses the column default.

**Reasoning:** Hard-remove breaks tests that construct `CatalogToolView` fixtures without lifecycle_state (there are several — they predate Task 3). Silent fallback loses the regression signal; the fallback could fire in production for months without anyone noticing that a migration silently introduced NULL lifecycle_state rows. WARN-log preserves the regression signal at cheap cost: one grep in 48h shakedown logs surfaces the class of bugs this deprecation was defending against. The 4-state vocabulary the fallback emits intentionally differs from the 5-state canonical output (`[active]` vs `[loaded-on-boot]`, etc.) — the mismatch is part of the signal, not a bug.

**Reversibility:** Easy. Future session can hard-remove `_tool_state` + delete the fallback branch when soak data shows zero WARN fires across N weeks; the inline docstring names this as the cleanup trigger.

**Decided by:** Lewie (Fix Day 3 session open — accepted default with note that WARN log must name the slug for actionability, 2026-04-25).

**Affects:** `core/recommend/prompt.py` (`_tool_state` deprecation docstring + `_render_standard_row` branch logic + new logger); `core/recommend/prompt.py::CatalogToolView` (new `lifecycle_state: Optional[str]` field); `core/api/recommend.py::_catalog_view` (passes `lifecycle_state` through); `tests/test_recommend_prompt.py::TestLifecycleStateRendering` (4 tests including both canonical + fallback paths).

---

## [2026-04-25 Fix Day 3] — Identity block position between adapter preamble and X3 fragment

**Context:** Fix Day 3 Task 7 injects operator-identity text into the composed system prompt. The existing composition is a deterministic 6-block sequence: preamble → X3 → X4 → X6 → X7-A → JSON envelope. Identity needs a position; the `TestSystemPromptStructure` tests assert block order, so adding a block is a schema change.

**Options considered:**
- Before preamble — identity comes before role-setting; risks identity contradicting "you are Concierge" framing
- Between preamble and X3 — right after role-setting, before behavioral protocols begin
- Right before the JSON envelope — last thing Opus sees; maximal recency weight but disconnected from role + protocols
- Absorbed into the user message rather than system — breaks the system-only-for-stable-context convention

**Decision:** Between preamble and X3. `compose_recommendation_prompt` accepts optional `identity` kwarg; when non-empty, renders as `# Operator identity\n\n{text}` in position 2 of the block sequence. Empty/None/whitespace-only collapses the block entirely — byte-identical to pre-Task-7 composition (regression-guarded by `test_empty_identity_prompt_byte_identical_to_pre_identity_composition`).

**Reasoning:** Identity is "context about who you're serving," semantically adjacent to the preamble's "who you are" framing. Placing it between them flows "here's your role → here's whose preferences shape this task → here's how you reason" in that order. Before-preamble risks Opus reading identity as definitional about itself rather than about the operator. At-envelope is too late — by that point Opus has already traversed X3/X4/X6/X7-A and chosen its reasoning posture without operator context. User-message absorption loses the prompt-caching benefit (system block is cacheable across calls; user block changes per call).

**Reversibility:** Easy. Block position is a single change in `compose_recommendation_prompt`; the identity block is optional and collapses cleanly when absent. Moving it would require updating `TestIdentityBlockPosition` assertions but nothing downstream.

**Decided by:** Lewie (Fix Day 3 session open — accepted default as proposed, 2026-04-25).

**Affects:** `core/recommend/prompt.py::compose_recommendation_prompt` + new `_render_identity_block`; `core/recommend/service.py` (reads identity via `self.memory.identity_get()` at recommend time); `tests/test_recommend_prompt.py::TestIdentityBlockPosition` (5 tests including byte-identity regression guard). Fix Day 4's narration-as-push MCP resources protocol will likely expose the X3/X4/X6/X7/X8 preambles via `resources/list`; identity is NOT in that set — it's dynamic per-call, not a session-long preamble.

---

## [2026-04-25 Fix Day 3] — Identity refresh triggers on loaded-on-boot boundary crossings only (both directions)

**Context:** Fix Day 3 Task 7 wires a post-transition hook that updates the identity note. The hook needs a trigger rule — which `Tool.lifecycle_state` transitions warrant an identity refresh?

**Options considered:**
- Every `approved → installed` transition — noisy; every install fires identity refresh even when the tool is just session-scope-used and doesn't earn a permanent slot
- Heuristic "new capability" detection — install of a previously unknown tool triggers refresh; requires maintaining a sidecar "previously known" set
- Boundary crossings of `loaded-on-boot` in either direction — refresh fires iff `old == 'loaded-on-boot'` OR `new == 'loaded-on-boot'`

**Decision:** Boundary crossings of `loaded-on-boot`, both directions explicitly. Refresh fires on: `* → loaded-on-boot` (gaining a permanent tool) and `loaded-on-boot → *` (losing a permanent tool, including `loaded-on-boot → retired`). Non-boundary transitions (e.g. `discovered → used`) are no-ops for identity.

**Reasoning:** `loaded-on-boot` is the state that meaningfully changes "what's in my toolbelt." Other transitions represent lifecycle movement without changing the operator's permanently-available capability set — a `discovered → used` transition means "this tool just got used once," which is exercise-telemetry but not identity-signal. The loaded-on-boot → retired direction is explicitly in-scope per operator intent: losing a tool from the toolbelt is identity-relevant signal in the same way as gaining one (future sessions need to know the tool was available AND was revoked, not just that it was available). Every-install-transition would flood identity with churn; heuristic "new-capability" would require sidecar state that duplicates what `lifecycle_state` already encodes (`discovered` → "not yet exercised"; transitioning out means the tool just got exercised enough to move).

**Reversibility:** Easy. `refresh_identity_on_loaded_on_boot_change` is one function; changing the trigger condition is a one-line edit to the `crossed_boundary` check.

**Decided by:** Lewie (Fix Day 3 session open — accepted default with note that the `loaded-on-boot → retired` direction must be explicitly in-scope in the hook code, 2026-04-25).

**Affects:** `core/identity.py::refresh_identity_on_loaded_on_boot_change`; `core/tool_transitions.py::transition_tool_lifecycle` (on_transition kwarg surface); `tests/test_identity.py::TestRefreshHookCrossings` (6 tests enforcing each boundary direction). Future session extending the hook's trigger surface (e.g. "should used→discovered also refresh?") must re-evaluate this principle: change the identity note only when the loaded-on-boot set changes.

---

## [2026-04-25 Fix Day 4] — MCP resources URI scheme: `concierge://prompts/{name}.md` (audit-discovered reversal)

**Context:** Fix Day 4 Task 2 exposes Concierge's prompt fragments via the MCP `resources/list` + `resources/read` protocol so sessions have persistent posture context beyond per-tool instructions (narration-as-push pattern 2 per DECISIONS `[2026-04-23]`). The URI scheme fork surfaced at session open with a proposed default; open-phase audit discovered an existing precedent in the codebase that argued for a different shape.

**Options considered:**
- Original proposal `concierge://preamble/{name}` — matches the "these are preamble resources" semantic framing used in the DECISIONS narration-as-push entry
- Audit-discovered `concierge://prompts/{name}.md` — matches the existing docstring at `adapters/claude_code/meta_tools/gap_preamble.py:55-56` which anticipates a "future X-slot" advertising X8 under exactly this URI
- A third `mcp://concierge/preamble/{name}` — RFC-style nested scheme; rejected as unnecessarily verbose

**Decision:** `concierge://prompts/{name}.md`. Explicit reversal from the originally-proposed default after the open-phase audit found the in-repo precedent that predates Fix Day 4 and explicitly anticipates this slot. The URI convention is now: `concierge://prompts/{kebab-case-source-filename}.md`.

**Reasoning:** A future reader grepping for `concierge://` finds one convention, not two. The existing `gap_preamble.py` docstring transitions cleanly from "Deferred per N12 proposal Q4 answer" to "Implemented in Fix Day 4 Task 2 under this same URI." Matching pre-existing documented intent is more load-bearing than my originally-proposed scheme.

Bonus finding worth recording: Fix Day 4 Task 2 closes a **documented deferral** (originally cut in the N12 proposal Q4 answer) rather than introducing a new surface. This matters for scope discipline — the "Task 2 is session-long posture" framing in the narration-as-push DECISIONS entry is actually finishing known work, not opening a new design space.

**Reversibility:** Easy. URI scheme is advertised in `resources/list` output; clients read URIs back from that list. Changing the scheme is one line in `core/adapters/claude_code/resources.py::CONCIERGE_RESOURCES` + the corresponding gap_preamble.py docstring update. No wire-protocol migration needed — clients always see the current scheme.

**Decided by:** Lewie (Fix Day 4 session open — accepted my reversal explicitly after audit surfaced the precedent, 2026-04-25). Process note: Lewie flagged this as "exactly the Fix Day 2 discipline applied" — surface default → audit → propose reversal with citation → greenlight before proceeding.

**Affects:** `adapters/claude_code/resources.py::CONCIERGE_RESOURCES` (6 URIs under the scheme); `adapters/claude_code/meta_tools/gap_preamble.py` docstring transition from Deferred → Implemented; `tests/test_mcp_resources.py::EXPECTED_URIS_IN_ORDER` + parametrized byte-identity regression guards. Future MCP-resources additions (e.g. new prompt fragments) follow this URI convention unconditionally.

---

## [2026-04-25 Fix Day 4] — MCP resources inventory: six resources (X3/X4/X6/X7-A/X8 + gap-preamble)

**Context:** Fork B at Fix Day 4 session open: "what exactly belongs in the resources set?" The DECISIONS narration-as-push entry named "X3/X4/X6/X7/X8 + gap-preamble" but today's `compose_recommendation_prompt` composes only four fragments (X3/X4/X6/X7-A) plus an adapter preamble and the JSON envelope. Audit against `core/prompts/SKILL_FRAGMENT_SYNC_LOG.md` + `core/prompts/soul_delta.py`'s closure note resolved the ambiguity.

**Options considered:**
- Expose only the four fragments currently in `compose_recommendation_prompt` (X3/X4/X6/X7-A) + gap-preamble = 5 resources — matches the runtime composition but omits X8 which exists as a constant but isn't composed into the recommend prompt
- Expose the full five-member Class-1 prompt-fragment set (X3/X4/X6/X7-A/X8) + adapter-authored gap-preamble = 6 resources — matches the DECISIONS enumeration
- Expose every prompt-fragment-ish thing in the codebase (also include the adapter preamble from `core/recommend/prompt.py`) = 7 resources

**Decision:** Six resources — the full Class-1 prompt-fragment set (X3 tool-awareness, X4 tool-recommendation, X6 tool-discovery, X7-A tool-lifecycle-weekly-review, X8 behavioral-rules) plus the adapter-authored `CLAUDE_CODE_GAP_PREAMBLE`. Matches the DECISIONS enumeration exactly. The `CONCIERGE_ADAPTER_PREAMBLE` in `core/recommend/prompt.py` is explicitly NOT exposed — it's Concierge's server-side Opus framing, not a session-posture resource. Ordering in `CONCIERGE_RESOURCES` is the order a session-long posture reader would want: three reasoning protocols first, lifecycle review fourth, behavioral rules fifth, condensed gap-preamble last.

**Reasoning:** The five Class-1 fragments are canonical-verbatim (governed by DECISIONS `[2026-04-21 05:50]` EXTRACT invariant). Exposing them byte-for-byte preserves the same "authored by skill source files, agent reads them as posture" semantic the skill protocols had in the OpenClaw consumer. X8 specifically — the SOUL-delta behavioral rules — closes a Fix Day 3-era deferral: `adapters/claude_code/meta_tools/gap_preamble.py:55-56` anticipated "Future X-slot may advertise X8 via MCP resources/list + resources/read." Fix Day 4 Task 2 IS that X-slot.

The adapter-authored gap-preamble coexists with X8 (which is verbatim OpenClaw-framed) deliberately — the gap-preamble is the Claude-Code-single-agent-framed condensed mirror. Sessions reading resources see both and get the multi-perspective view the author intended.

**Reversibility:** Easy. `CONCIERGE_RESOURCES` is a static list in one module. Adding/removing a resource is a one-line edit + updating the test's `EXPECTED_URIS_IN_ORDER`. Verbatim-identity tests are parametrized so adding a resource auto-covers under the same pattern.

**Decided by:** Lewie (Fix Day 4 session open — accepted default as proposed, post-audit, 2026-04-25). Audit found the precedent in the fragment closure docstring; Lewie greenlit immediately.

**Affects:** `adapters/claude_code/resources.py::CONCIERGE_RESOURCES` (the authoritative list); `tests/test_mcp_resources.py::URI_TO_SOURCE` (byte-identity contract); `core/prompts/SKILL_FRAGMENT_SYNC_LOG.md` is the upstream source tracker — future re-sync of any Class-1 fragment automatically propagates into `resources/read` output without code change.

---

## [2026-04-25 Fix Day 4] — side_observations trigger categories: retired-tool overlap + idle loaded-on-boot (two, not four)

**Context:** Fix Day 4 Task 3 added an optional `side_observations` field to the Opus recommendation response — pattern 3 of narration-as-push. My initial default proposed four trigger categories: (a) retired-tool overlap with the task, (b) adjacent-to-installed-pack-member, (c) idle loaded-on-boot tool whose category matches the task's domain, (d) catalog-gap-for-request. Lewie trimmed to two at session open.

**Options considered:**
- Four categories as originally proposed (a, b, c, d)
- Two strong-signal categories (a, c) — retired-tool overlap + idle loaded-on-boot
- Open-ended ("observe anything interesting") — rejected: Opus reliably over- or under-generates on open-ended list fields

**Decision:** Two categories — (a) retired-tool overlap and (c) idle loaded-on-boot. Documented with concrete example phrasing in `core/recommend/prompt.py::JSON_OUTPUT_ENVELOPE`'s §side_observations section. Cap at two observations. Prompt explicitly permits silence ("omit the key or return []", "silence is correct when the patterns don't fire").

**Reasoning:** Lewie's reasoning at greenlight: "(a) and (c) are high-signal patterns a generic agent would miss — retirement memory and idle-capital detection. (b) 'adjacent' needs a definition and the action is unclear. (d) risks Opus repeating its own recommendation in the observations channel. Two strong categories beat four mixed-signal ones, and adding more later is easier than cutting."

The two chosen categories target distinct operator concerns: (a) surfaces knowledge the operator may have forgotten they had (retired tools that could be reinstated); (c) surfaces idle capital (permanently-loaded tools that haven't been applied to the domain they were acquired for). Both are patterns a generic-LLM-without-Concierge-context cannot easily produce because they depend on catalog state + recency signal that only the system knows.

**Reversibility:** Easy. Category list lives in one prompt constant. Adding (b) or (d) back later is a docstring edit + test addition. The JSON schema and parser accept up to 2 string entries — expansion to 3+ requires validator update and prompt cap change.

**Decided by:** Lewie (Fix Day 4 session open — trimmed from my four-category default, 2026-04-25).

**Affects:** `core/recommend/prompt.py::JSON_OUTPUT_ENVELOPE` §side_observations (prompt text with the two category blocks); `core/recommend/schemas.py::RecommendResponse.side_observations` (Optional[list[str]]); `core/recommend/parse.py::_parse_side_observations` (shape validation); `core/recommend/validator.py::_check_side_observations` (>2 cap as drift signal); `adapters/claude_code/meta_tools/render.py::render_recommend_result` (conditional `### Observations` section between Gap report and Summary). Soak data on which of the two categories Opus actually triggers on may inform a future decision about expanding / contracting the set.

---

## [2026-04-25 Fix Day 4] — SSE new-request emit site: service-layer, not endpoint-layer

**Context:** Fix Day 4 Task 4 adds a real-time SSE surface (`GET /ui/events`) emitting `new_request` events when a pending request is filed. Fork D at session open: where does the publish happen — inside `LifecycleService.create_request` (service layer) or inside `POST /requests` (endpoint layer)?

**Options considered:**
- Endpoint-layer emit — simpler DI, but couples SSE to the HTTP entry point; future non-HTTP filing paths (future MCP-originated create_request, future scheduled imports) would need to repeat the publish logic
- Service-layer emit — broker is a constructor field on `LifecycleService`, `create_request` publishes directly. Any caller (HTTP, MCP, scheduler, CLI) that creates a request feeds the same broker without a second wiring step

**Decision:** Service-layer. `LifecycleService.event_broker: Optional[EventBroker] = None`; `create_request` publishes the `new_request` event after the DB commit. Optional field — tests / non-SSE-aware callers construct without a broker and the publish becomes a no-op.

**Reasoning:** SSE is a cross-cutting concern, not an HTTP concern. Any path that files a pending request should feed the notification surface; service-layer is the natural choke point. The "publish after commit" ordering is load-bearing — subscribers never see an event for a row that rolled back, which matters for UI consistency guarantees. Optional-broker keeps legacy tests / non-HTTP callers working unchanged.

**Reversibility:** Easy. Moving the publish to the endpoint layer is a one-line relocation. The EventBroker itself doesn't care about the call site.

**Decided by:** Lewie (Fix Day 4 session open — accepted default, 2026-04-25).

**Affects:** `core/lifecycle_store/service.py::LifecycleService` (new event_broker field + publish call after commit); `core/api/requests.py::get_lifecycle_service` (wires broker from `app.state` via FastAPI DI); `core/app.py` lifespan (constructs the per-app broker singleton); `core/api/requests.py::get_event_broker` (defensive fallback to None for legacy TestClient fixtures that skip lifespan). Future non-HTTP create_request callers inherit SSE fan-out for free.

---

## [2026-04-25 Fix Day 4] — Scanner auto-promotion install-age threshold: 30 days

**Context:** Fix Day 4 Task 5 — §C7 promotion scanner — auto-promotes tools meeting the 5-events-in-30-days threshold, but only when install age is "old enough" that the burst-of-initial-recommendations signal isn't mistaken for sustained usage. Fork G at session open proposed 14 days as the default; Lewie pushed to 30 days.

**Options considered:**
- 14 days (original proposal) — earlier auto-promotion; tools start contributing to the toolbelt faster
- 30 days — delayed auto-promotion; requires genuine sustained use across a full month
- No threshold — promote on events alone, ignore install age — rejected: newly-installed tools often get a burst of exploratory recommendations that aren't sustained signal

**Decision:** 30 days. `AUTO_PROMOTE_MIN_INSTALL_AGE_DAYS = 30` in `core/lifecycle_scanner.py`. Tools with install age < 30 days that meet the event threshold are flagged as ambiguous candidates (classification reason `install_age_below_threshold`) rather than auto-promoted; operator reviews and manually transitions if appropriate.

**Reasoning:** Lewie's reasoning: "Trigger-happy promotion is the worse failure mode; demotion-by-missed-signal is recoverable via re-use patterns, but false-promotion requires explicit retirement to undo. 30d gives sustained-usage signal cleanly." The asymmetric-recoverability argument is the key: a tool that SHOULD be loaded-on-boot but isn't will accumulate more events over time and eventually cross the 30-day threshold; a tool that was WRONGLY promoted to loaded-on-boot churns the operator's identity (via the refresh hook), changes Opus's context framing, and requires explicit operator intervention to undo.

Install age is proxied by `Tool.created_at` — a per-tool 'installed' event timestamp would be more authoritative but that table is still sparse today (Fix Day 3 wired installs via approve, but operator-bootstrapped tools have no install event). `created_at` defaults to `server_default=func.now()` so it tracks catalog-insert time reliably.

**Reversibility:** Easy. Threshold is a single constant `AUTO_PROMOTE_MIN_INSTALL_AGE_DAYS` in `core/lifecycle_scanner.py`. Lowering to 14 or raising to 60 is a one-line edit. If a future scanner wants per-tool-type thresholds (e.g. CLI vs MCP have different "settling time"), the constant grows into a dispatch function.

**Decided by:** Lewie (Fix Day 4 session open — chose 30 over 14 with explicit asymmetric-recoverability reasoning, 2026-04-25).

**Affects:** `core/lifecycle_scanner.py::AUTO_PROMOTE_MIN_INSTALL_AGE_DAYS`; `_classify_promotion` branching; `tests/test_lifecycle_scanner.py::TestPromotionClassification` (parametric tests at and around the threshold, including the "just-below-threshold" ambiguous-classification guard). Future "tighten to 14" or "relax to 60" debates should cite this entry's reasoning.

---

## [2026-04-25 Fix Day 4] — session_id semantic rule: MCP-originated → SHIM_SESSION_ID; non-MCP → null

**Context:** Fix Day 4 Task 6 wired `session_id` propagation across the recommend and install telemetry emit sites (per Fix Day 3 Fork 2's plan for Day 4). Fork I at session open: what value does session_id carry, and what value does it take when the caller has no MCP session context (e.g. UI-originated approval)?

**Options considered:**
- Populate session_id on every emit (generate a new UUID per request for non-MCP callers) — creates N "sessions" per browser tab, none of which correspond to an actual session
- MCP-originated emits → shim process UUID; non-MCP emits → null — honest signal, partial population but caller-context-aligned
- Cookie-based web-session id for browser callers + MCP session id for MCP callers — real session semantics on both paths but requires cookie infra that isn't built yet

**Decision:** MCP-originated emits carry `SHIM_SESSION_ID` (UUID4 minted at shim process import time); non-MCP emits (FastAPI calls from UI, direct HTTP clients) leave `session_id=null`. Captured in `adapters/claude_code/session.py::SHIM_SESSION_ID` + threaded through the `RecommendRequest.session_id` and `StatusChange.session_id` schema fields.

**Reasoning:** A field's meaning should be caller-context-aligned, not data-context-aligned. "session_id = the session that originated this event" has a well-defined meaning only when the caller has a session — for MCP that's the shim process lifetime (one UUID per shim start), for non-MCP there is no session to identify. Null is the honest shape for non-MCP.

The alternative — synthesizing a UUID per HTTP request for non-MCP — would inflate scanner aggregation queries with noise ("this tool was used in 47 different sessions this week" when it was really just 47 distinct HTTP calls from one browser tab). Cookie-based real web-session identification is the right long-term design but requires infrastructure (session store, expiration, middleware) that isn't built and isn't on the Fix Day 4 scope.

Shim-process-lifetime UUID is the right grain: one session = one continuous MCP connection. Long-running shim processes accumulate events under one session_id; short-lived ones produce more distinct ids. Scanner queries by tool + window care about the aggregate, not the session count.

**Reversibility:** Easy. The `session_id` column is already nullable (Fix Day 3 provision). Extending to cookie-based web sessions is additive — the MCP path unchanged, non-MCP callers start populating session_id from a middleware-set context var instead of null.

**Decided by:** Lewie (Fix Day 4 session open — accepted default, 2026-04-25). Documented in `adapters/claude_code/session.py` module docstring for future readers.

**Affects:** `adapters/claude_code/session.py::SHIM_SESSION_ID`; `adapters/claude_code/meta_tools/recommend.py::_build_request_body` (reads at call time, monkeypatchable); `core/telemetry.py::UsageEventSink` 4-arg signature; `core/recommend/schemas.py::RecommendRequest.session_id`; `core/recommend/service.py` (threads through to emit sink); `core/lifecycle_store/schema.py::StatusChange.session_id`; `core/lifecycle_store/service.py::update_status` + `_maybe_install_on_approve` (pass-through). Loader emit site remains deferred (BackingServerRegistry.register() doesn't emit today); when it lands it will read SHIM_SESSION_ID trivially.

---
