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

## [2026-04-21 08:15] — Phase C effort level adjusted from max to xhigh

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

## [2026-04-21 10:30] — Skill-extraction pattern: EXTRACT as prompt fragments (not pure Python, not ADAPT)

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

## [2026-04-21 11:15] — Phase C approved; classification.md finalized; proceeding to Phase D

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

## [2026-04-21 13:00] — Phase D approved; dependency-graph.md finalized; proceeding to Phase E

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

## [2026-04-21 17:30] — Tuesday evening sprint reframed from stretch to required (post-Phase-F)

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

## [2026-04-21 17:45] — Phase E and Phase F approved; session close sequence initiated

**Context:** Phase E (Gap Analysis) delivered earlier this session with
all checkpoint items complete but Lewie's sign-off deferred to bundle
with Phase F. Phase F (Build Plan) delivered with the post-summary
Tuesday-evening reframe (see [17:30] entry) captured. At session close,
Lewie approved both together as part of the close-out sequence.

**Decision:** Phase E is approved. `planning/gap-analysis.md` is final.
Phase F is approved. `planning/build-plan.md` and
`planning/executive-summary.md` are final. Phase F checkpoint boxes
ticked including the required-framing and ladder-integrity addenda.

Q2 from Phase F §F.8 (Level-3 escalation destination = Claude.ai chat)
taken as implicitly accepted at signoff absent pushback. Recorded here
so a later session doesn't re-litigate.

**Reasoning:** Phase E and Phase F both met all checkpoint items and the
Tuesday-evening reframe (logged separately at [17:30]) was the only
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
