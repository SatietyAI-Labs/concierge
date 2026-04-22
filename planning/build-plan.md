# Concierge — Phase F (Build Plan)

*Deliverable of Phase F per `docs/concierge-claude-code-plan-v3.md` §F.*
*Session:* `SESSION-2026-04-21-01` (single live session covering
Phases C → D → E → F).
*Generated:* 2026-04-21.
*Effort:* `xhigh` with per-section `/effort max` bumps allowed.

Phase F is the capstone synthesis of Phases A-E into a six-day build
sequence running Tuesday 2026-04-21 through Sunday 2026-04-26. It is
the operating document for the remainder of the hackathon — every
build session opens by reading the relevant §F.2 day block.

Phase F makes no original architectural decisions. Its inputs are:

- **Phase A** — 24 canonical components (`planning/inventory.md`)
- **Phase B** — 10-slot architecture map + 3 Claude Code adapter
  approaches (`planning/architecture-map.md`)
- **Phase C** — 12 LIFT / 7 EXTRACT / 0 ADAPT / 0 REWRITE / 5 RETIRE
  at 46.5h grand total; pre-sequenced 4-cut ladder → 43h
  (`planning/classification.md`)
- **Phase D** — critical path 27.5h strict; 32 tracked items;
  ladder-integrity verified (`planning/dependency-graph.md`)
- **Phase E** — 7 FULL / 2 PARTIAL / 0 NEW coverage; top-5 risks;
  ten Phase F carry-forwards (`planning/gap-analysis.md`)

Decisions logged at DECISIONS.md entries 2026-04-20 18:15, 19:45, 21:00
and 2026-04-21 04:45, 05:50, 05:55, 06:10.

---

## F.1 Mission framing

*Updated 2026-04-21 per DECISIONS `[2026-04-21 18:00]` — operational-
first pivot. Original framing (recorded demo video as the end-state by
Day 6) is superseded. The reworked framing below treats operational
use as primary and demo recording as a byproduct, per Lewie's
mid-session announcement that the event is underway without a
confirmed acceptance email.*

**Primary end-state (2026-04-21 pivot):** Concierge running **live on
Lewie's daily Claude Code sessions for 48+ continuous hours** before
declaring the build "done." The operational-shakedown gate
supersedes the 5-consecutive-clean-demo-rehearsal gate.

**Day 4 deliverable (operational milestone):** the protected
operational core (§F.5) runs end-to-end against Lewie's real
workflow — Claude Code session talking to the FastAPI service,
SQLite + ChromaDB memory queried, Opus 4.7 serving recommendations
with graceful degradation when memory is unavailable, lifecycle
store + cron integration verified on real input, three-section HTMX
UI browsable. This sets up Days 5-6 for the 48h shakedown.

**Day 6 deliverable (conditional):** if the 48h operational gate has
been met, submit hackathon entry with a demo video recorded from
live usage. If the gate has not been met, either (a) submit with a
"running live, N hours of uptime, M recommendations served" footnote
or (b) slip submission in favor of operational integrity. Judgment
call at the time, not pre-committed.

**Priority hierarchy (from CLAUDE.md, updated 2026-04-21):** AI
quality → build smoothness → **operational readiness by Day 4** →
token cost explicitly not a priority.

**Protected core (§F.5):** 17 items / 26-28h non-cuttable core, now
framed as "minimum operational core" (demo-capable == operational-
capable). Operational-first adds error handling, structured logging,
graceful degradation, and X11-cron-actually-running as additional
unwritten protected surface.

**Scope posture:** 46.5h baseline, 43h with full ladder, 40h yellow
threshold triggered, 50h red threshold not triggered. Ladder cuts
are **pre-sequenced day-of triggers** — no mid-week scope
conversation needed for Cuts 1-4.

---

## F.2 Day-by-day plan

Each day block contains: morning/midday/PM/eve target items, the
day-end checkpoint, the day's named ladder triggers (if any), and
the Phase E adjustment embedments relevant to that day.

Session-level effort: `xhigh`. Bump to `max` for any mid-build
architectural decision (new `POST /recommend` behavior, adapter
approach change, schema change).

### F.2.1 Day 1 — Tuesday 2026-04-21 — "Planning tail + required foundation sprint"

**Already complete this morning (4:30-6:30am):**

- Phase C — Classify → signed off 05:55
- Phase D — Dependency Graph → signed off 06:10
- Phase E — Gap Analysis → signed off bundled with Phase F at session close

**Midday-afternoon (~2-3h):**

- Phase F — Build Plan (this document) at `xhigh`
- Phase F signoff, session snapshot staged (writes at session close)

**Evening — REQUIRED foundation sprint (~3-5h, starts post-signoff):**

The Tuesday evening sprint is required, not stretch. Per DECISIONS
`[2026-04-21 07:00]` framing change: with Day 2 carrying 15-19.5h
of work depending on Tuesday-eve completion, pre-doing N1+N2 tonight
reduces Day 2 from infeasible (~19.5h) to near-the-top-of-feasible
(~15.5h). Operator energy assessed as adequate for 4-6 more hours
post-signoff. "Required" does **not** mean "push through injury" —
see health check below.

| ID | Item | Effort | Notes |
|---|---|---|---|
| N1 | FastAPI project skeleton (pydantic, config, logging, test setup) | 1.0h | REQUIRED. Includes `core/` package layout, `ui/` stub for Day 4, `adapters/claude-code/` stub for Day 3 |
| — | **Tuesday evening health check** (see below) | — | Hard self-assessment at ~8pm local, post-N1 |
| N2 | SQLite schema + SQLAlchemy models (tools, packs, requests, memory-events) | 2.0h | REQUIRED *if health check passes*. Generalized schema — no `agentId`, no Alfred-only flags |
| N3 | Markdown-to-SQLite ingest (partial) | 1-2h | Stretch — attempt only if N1+N2 complete with buffer before 10pm cutoff |

**Tuesday evening health check (~8pm local, post-N1):**

After N1 completes and before N2 begins, pause for a hard
self-assessment. Criteria to continue:

- Can I read my own code without losing the thread?
- Have I made more than ~2 trivial mistakes in the last hour?
- Am I tired-but-engaged, or tired-and-sloppy?

If any criterion fails — **end the sprint here.** N2 rolls to
Wednesday morning. Close the terminal, write the session snapshot,
sleep. Cut 4 fires automatically at 10pm (since N2 won't be complete
by cutoff) — pre-logged in the snapshot so Wednesday opens
unambiguous.

The health check is the safety valve that preserves "required"
framing without making it reckless. Required means "default is to do
the sprint"; health-check lets fatigue override when fatigue is real.

**Cut 4 trigger (replaces old stretch-goal-based trigger):**

- **Cut 4 fires if N1+N2 aren't both committed-and-tested in the
  repo by 10pm local Tuesday.** "Committed-and-tested" = code
  committed to git, N1's `pytest` smoke passes, N2's migration
  applied and verified against the SQLite file. Partial progress
  on N2 at 10pm still triggers Cut 4 — the bright line is both
  complete or neither considered complete.

**Cutoff time justification (10pm local):**

- Phase F close-out (signoff + DECISIONS + snapshot) expected
  complete ~7pm local. Sprint starts ~7pm.
- N1 (1h) + N2 (2h) = 3h minimum. 7pm + 3h = 10pm target.
- 10pm is the natural check-in: late enough to genuinely attempt;
  early enough to preserve sleep before Wednesday's ~15.5h build
  day.
- Any slippage past 10pm signals fatigue or complexity-surprise —
  either argues for Cut 4 pre-emptive (easing Wednesday) over
  pushing through (risking Wednesday).
- Health check at ~8pm provides the earlier escape: if sprint ends
  at N1, N1+N2 won't both be complete by 10pm, so Cut 4 fires
  automatically.

**Day 1 checkpoint (Tuesday night, pre-snapshot):**

- [ ] Phase F signed off (minimum — required to close session)
- [ ] N1 complete and committed (required unless health check fails
      immediately after Phase F signoff, which would itself be an
      emergency warranting Level-3 chat — not an expected outcome)
- [ ] N2 complete and committed (required *if health check passes*;
      N2-deferred-to-Wed is allowed under health-check exception)
- [ ] N3 partial or complete (stretch only; not expected)
- [ ] Cut 4 status: either pre-emptively fired (Decision logged) or
      not-needed (both N1+N2 done by 10pm)

**Session close tonight:**

Write `planning/sessions/SESSION-2026-04-21-01.md` covering the full
Phase C → D → E → F arc. Record Tuesday-evening sprint outcome and
health-check result; note whether Cut 4 fired. Wednesday morning
opens on whatever state is committed.

### F.2.2 Day 2 — Wednesday 2026-04-22 — "Service core + N10 pull-forward"

Longest build day of the week. Sequentially executed per Phase D
parallelism-realism note (solo-builder context-switching cost makes
nominal-parallel work sequentially-faster in practice).

**Day 2 scenarios based on Tuesday evening outcome:**

| Scenario | Tuesday eve completed | Day 2 load | Feasibility |
|---|---|---|---|
| A (target) | N1 + N2 | ~15.5h | Near top of feasible — the plan below |
| B (health-check fired) | N1 only; Cut 4 fires | ~17.5h | Stressful; protect core, N10 becomes stretch |
| C (stretch success) | N1 + N2 + N3 | ~13.5h | Comfortable; N10 lands earlier in evening |

Plan below assumes **Scenario A** as default. Divergence notes at end
of section.

**Freed-hours principle:** the 3-4h absorbed by Tuesday eve does
**not** compress Wednesday's day. Those hours fund: (1) the N8
smoke expansion to 1.0-1.5h without squeezing N10; (2) round-trip
parser debug time on N8 if Risk 5 surfaces; (3) fragment-tuning
iteration on N6 if Risk 1 surfaces during smoke. Compression under
pressure is the fallback path, not the default.

**Morning block 1 — N3/N4 finish + prompt-fragment extracts (~4h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| N3 | Markdown-to-SQLite ingest (finish, or all of it if only N1+N2 done Tue eve) | 0.5-2.0h | Scenario A: finish only (if partial); Scenario B/health-check: all 2h |
| N4 | Catalog API endpoints (`GET /tools`, `GET /tools/{id}`, `GET /packs`) + markdown export (unless Cut 4 executed, which strips the export) | 1.0-2.0h | **Day 2 first-checkpoint criterion: `curl GET /tools` returns structured JSON** |
| X3 | tool-awareness.md → prompt-fragment constant | 0.5h | Per DECISIONS 2026-04-21 05:50 — header-comment provenance, verbose constant name |
| X4 | tool-recommendation.md → prompt-fragment constant | 0.5h | Same pattern |
| X11 | outbox-housekeeping.sh verify crontab + doc heartbeat path | 0.5h | Off-path; fit any gap |

**Morning block 2 — demo-critical extracts + memory wrapper (~3h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| X6 | tool-discovery SKILL.md → prompt fragment (signal table critical) | 1.0h | Demo-critical; Risk 1 mitigation #2 applies (manual Opus test-run before committing the constant) |
| X7 | tool-lifecycle SKILL.md → hybrid (Python constants + prompt protocol) | 1.0h | Threshold constants + tag schema → Python; weekly-review protocol → prompt |
| N5 | Memory service wrapper (in-process import of `moltbot-memory-mcp/server.py`) | 1.0h | Reads env var for store location |

**Afternoon — recommendation + lifecycle endpoints (~5.5h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| N6 | `POST /recommend` — Opus 4.7 call, system prompt from X3+X4+X6+X7, task + catalog + memory context, ranked output | 3.0h | **temperature=0 locked for demo runs** (per Phase E Q2). Higher values allowed only during fixture-tuning sub-work |
| N7 | Lifecycle endpoints + markdown parser (`GET /requests/pending`, `GET /requests/{id}`, `POST /requests`, `POST /requests/{id}/status`) | 2.5h | Markdown parser ~50 LOC; reads/writes X10 folder; uses X7 thresholds |

**Evening — smoke tests + N10 pull-forward (~5-5.5h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| N8 | **Smoke tests — EXPANDED to ~1.0-1.5h** per Phase E Q1 | 1.0-1.5h | Endpoint liveness + **fixture-driven recommendation assertion (`csvstat` ranks above `pandas` for "analyze a CSV")** + **round-trip markdown parse check** (write fixture → POST status → re-GET → assert). Catches Risk 1 and Risk 5 on Day 2, not Day 4. **Day 2 core-milestone** — this block completes the protected service core |
| N10 | **stdio proxy shim — PULLED FORWARD as default plan** per Phase D signoff | 4.0h | ~300 LOC; JSON-RPC 2.0 id mapping; stdio read/write pump; backing-server process mgmt. Day 3 opens with shim already built. **If Scenario B or energy runs out post-N8, N10 slides to Day 3 AM — see Day 3 adjustments** |

**Day 2 checkpoint (Wednesday night):**

- [ ] `curl POST /recommend` with fixture task returns ranked recommendations
- [ ] N8 smoke tests pass — fixture assertion + markdown round-trip
- [ ] N10 stdio proxy shim skeleton compiles and passes its own unit test (Scenario A target; conditional under B)
- [ ] Day 3 opens with zero blocker on N11 meta-tool work (Scenario A) OR with N10-finish as the opening 4h work item (Scenario B)

**Scenario B / health-check divergence notes:**

If Tuesday eve ended at N1 (health check fired), Wednesday carries
+2h for N2 and +1h for N4-without-Cut-4 (since Cut 4 already fired
Tuesday). Day 2 becomes ~17.5h. In this scenario:

- **Core through N8 is protected** — N3/N4/X3/X4/X6/X7/N5/N6/N7/N8
  all still land Wednesday. The expanded N8 still absorbs parser
  and fragment debug time.
- **N10 pull-forward becomes conditional**, not default. If energy
  permits post-N8, attempt as much of N10 as fits before hard stop.
  Whatever remains slides to Day 3 AM, which means Day 3 opens with
  (N9 spike + N10 finish + N11 meta-tools) in sequence. Cut 3 then
  becomes more likely to fire (see §F.4 ladder-integrity note).

**Named day-of triggers for Day 2:**

- No pre-sequenced Cut triggers on Day 2 itself — day is long but all
  items are on critical path or demo-critical. If Day 2 overruns 9 PM
  and N10 is still in progress, truncate N10 to
  the process-spawn skeleton only (defer full JSON-RPC routing to
  Day 3 AM). This is **not** a ladder cut; it is a within-item
  time-box. Log in DECISIONS.md if invoked.

### F.2.3 Day 3 — Thursday 2026-04-23 — "Adapter integration"

Day 3 is the critical-path high-pressure day. Phase D's 27.5h
critical path runs through this day's items. Risk 3 (serial-tail
cascade) is most active here. Ladder Cut 3 is the **first day-of
trigger** per Phase E Risk 3 mitigation #2.

**Morning — spike + meta-tools (~4h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| N9 | **`tools/list_changed` verification spike — 0.5h HARD time-box** per Phase E adjustment | 0.5h | Send a `notifications/tools/list_changed` during a live Claude Code session. If the client re-fetches `tools/list`: Approach 1 viable, N10 simplifies. If not or ambiguous: commit to Approach 2 per classification.md §C.3.1 |
| X8 | SOUL.md root delta → Claude-Code-specific prompt fragment | 0.5h | Feeds N12 gap-report injection |
| N11 | Meta-tool surface — `concierge_recommend`, `concierge_request_tool`, `concierge_list_active` (per Phase C §C.3.1) | 3.0h | **Day-of trigger if midday runs late: Cut 3 — defer `concierge_list_active`, saves 1.0h, trims N11 to 2.0h** |

**Midday — gap-report injection + optional install (~3h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| N12 | Gap-report injection via `concierge_recommend` result payload | 2.0h | Requires X8 SOUL fragment; the pitch-demo moment ("agent proactively surfaces what it's missing") |
| X13 | Python install module (`install_npm_global`, `install_pip_user`, `install_single_binary`) | 1.0h | **Day-of trigger if midday runs late: Cut 2 — drop X13 entirely.** Demo falls back to manual install command + voiceover. Saves 1.0h |

**Afternoon — backing-server lifecycle + integration smoke (~4h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| N13 | Backing-server spawn/teardown lifecycle management | 2.0h | Enables mid-session load/unload without session restart — Capability 5 |
| N14 | End-to-end integration smoke — Claude Code session → N10 shim → N11 meta-tool → N6 recommend → ranked output | 2.0h | Demo narrative rehearsal: run fixture scenario "analyze a CSV" end-to-end |

**Day 3 checkpoint (Thursday night):**

- [ ] Claude Code session loads the Concierge stdio proxy shim and
      sees `concierge_recommend` meta-tool
- [ ] `concierge_recommend` call returns ranked recommendations with
      gap-report structure
- [ ] Backing-server spawn/teardown works without session restart
- [ ] N14 integration smoke runs the fixture scenario cleanly at
      least once

**Named day-of triggers for Day 3 (in trigger order):**

1. **Cut 3 — defer `concierge_list_active` meta-tool** (saves 1.0h).
   Trigger: N11 start slips past midday. Agent can still file requests
   blind; Tool Registry UI handles active-tool introspection for
   the human operator.
2. **Cut 2 — drop X13 tool-install Python module** (saves 1.0h).
   Trigger: midday-block overruns. Approval-triggers-install becomes
   manual install command shown in terminal with voiceover ("and in
   the real thing the cron picks this up and runs install
   automatically"). X11 cron stays LIFTed and still demonstrates
   the "cron picks it up" moment.
3. **Fallback to Approach 3 (X16 mcporter) if N10 shim catastrophically
   breaks** (not a ladder cut — Risk 2 mitigation #2). Lower-fidelity
   but working. Escalate to Level-3 chat before invoking.

**Expected wall-clock:** ~11.5h even with Cuts 2+3 executed. Bleeds
into Day 4 morning are absorbed by Day 5 buffer, not by Day 4 UI
time. Day 3 over-shoot by ≤1h is acceptable; over-shoot by ≥2h
escalates to Level-3 chat.

### F.2.4 Day 4 — Friday 2026-04-24 — "UI — three sections"

Sequential focus per Phase D parallelism-realism note — one UI
section at a time rather than nominal-parallel claims. Day 4's
wall-clock is closer to the 12h serial total than the 6h parallel
ideal for solo-builder context-switching reasons.

**Morning block 1 — shell + registry (~5h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| N15 | UI layout shell — Pico.css + Jinja2 base template + nav | 1.0h | Gates all three sections |
| N16 | Tool Registry section — hierarchical pack list, expand/collapse, filter, search, manifest-vs-active dormant badge, Reload button | 4.0h | Biggest UI branch; do first while focus is freshest. Demo beat: Lewie clicks a pack, it expands, dormant badge visible per Q3 decision |

**Afternoon block 1 — inbox (~3h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| N17 | Pending Requests Inbox section — card render, HTMX approve/deny/defer buttons, optional comment field | 3.0h | Approve button POSTs to N7 `/requests/{id}/status`; cron picks up within the hour and moves the file |

**Afternoon block 2 — health + token-win (~3h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| N19 | Token-win instrumentation — rough heuristic (400 tokens per MCP tool def vs 20 tokens per CLI command); writes to N5 memory with `token-win` tag | 1.0h | Demo beat: the counter rises visibly during the lightweight-substitute moment |
| N18 | Health/Stats bar — four tiles: token-win counter, active-MCP count, cron heartbeat, top-3 tools | 2.0h | **Day-of trigger if running late: Cut 1 — trim to 3 tiles, drop top-3 tools tile.** Saves 0.5h |

**Evening — integration + polish (~1h):**

| ID | Item | Effort | Notes |
|---|---|---|---|
| N20 | UI integration + polish — empty states, titles, labels, transitions | 1.0h | Absorbs whatever rough edges remain from the three sections |

**Day 4 checkpoint (Friday night):**

- [ ] UI shell loads in browser; three sections navigate correctly
- [ ] Tool Registry renders packs + tools with dormant-badge state
- [ ] Pending Requests Inbox shows fixture requests with functional
      approve/deny buttons
- [ ] Health/Stats bar shows live token-win counter and
      active-MCP count
- [ ] Cron heartbeat tile reads the current `housekeeping.log` timestamp
- [ ] End-to-end demo scenario runs **once** cleanly (rehearsal-ready
      but not yet 5-consecutive-clean)

**Named day-of trigger for Day 4:**

- **Cut 1 — trim Health/Stats bar to 3 tiles** (saves 0.5h). Trigger:
  N18 start slips past 6 PM. Drop the top-3 tools tile (its data source
  is the slowest to compute from memory aggregation). Demo reads
  cleaner with three tiles.

### F.2.5 Day 5 — Saturday 2026-04-25 — "Operational shakedown day 1"

*Updated 2026-04-21 per DECISIONS `[2026-04-21 18:00]`. Original
framing was "stabilization + 5-consecutive-clean demo rehearsal";
replaced with the first 24 hours of the operational-shakedown gate.
Day 5 still absorbs Days 1-4 slippage, but via reactive bug-fixing
during live use rather than scripted rehearsal.*

Day 5 is the **first 24 hours of the 48+ hour operational gate**.
Concierge runs live on Lewie's real daily Claude Code sessions.
The shakedown generates bugs naturally through use — Claude Code
session → `concierge_recommend` meta-tool → N6 → memory/catalog/
lifecycle → response. Bugs get fixed reactively as they surface;
logs are the primary diagnostic surface.

**Morning — launch + residual stabilization (~3h):**

- Resolve any Day-3 overflow items that didn't make Day 4 morning
- Fix any Day-4 UI bugs surfaced during first real-use session
- Verify X11 cron is actually running against real input (not
  just installed): check `housekeeping.log` for heartbeats since
  Day-4 install; confirm pending→resolved moves happen on real
  approve/deny actions from the UI
- Capture baseline metrics: uptime start timestamp, initial memory
  store state, request-lifecycle state at shakedown t=0

**Midday-to-afternoon — live use (~6h, no scripted blocks):**

- Lewie runs real Claude Code sessions against Concierge. Not
  scripted; actual tasks from his daily workflow.
- Fix bugs reactively as they surface. Prioritize bugs that break
  operational use over bugs that only affect demo polish.
- Any Phase E Risk 1 (prompt-fragment correctness) surfacing in
  real recommendations → tune X6/X7-A fragments, re-run N8
  fixture assertion, re-verify.
- Any Risk 6 (operational regressions) surfacing → git-tag the
  last-known-good commit before attempting fix; revert-path
  available.

**Evening — checkpoint + start draft README (~2h):**

- 24h operational-gate progress: tally uptime, recommendation
  count, request count, cron heartbeat count, bugs caught and
  fixed vs. still-open
- Draft README.md from live usage learnings (not from a script —
  "here's what Concierge actually does" based on what it actually
  did today)

**Day 5 checkpoint (Saturday night, t=24h into shakedown):**

- [ ] Concierge has been running continuously for 24+ hours
- [ ] N recommendations served during live Claude Code sessions
  (document N in snapshot)
- [ ] X11 cron has executed at least 2-3 times with non-empty
  output (heartbeat discipline)
- [ ] All bugs surfaced during Day-5 live use are either fixed
  or explicitly tagged as acceptable for the 48h gate
- [ ] README draft exists

### F.2.6 Day 6 — Sunday 2026-04-26 — "Operational gate close + submission posture"

*Updated 2026-04-21 per DECISIONS `[2026-04-21 18:00]`. Original
framing was "demo recording + submission by Sunday evening."
Replaced with the 48h operational-gate close. Submission becomes
conditional on the gate; demo recording becomes a byproduct of
live usage, not a scripted take.*

**Morning — gate closure + assessment (~3h):**

- t=48h check: Concierge has been continuously operational for
  48+ hours, serving real recommendations into real Claude Code
  sessions, with cron running, logs present, no corruption of
  Alfred's production memory (isolation default held)
- Tally the shakedown: bugs found / fixed / open, uptime, memory
  store growth, recommendations served, requests moved through
  lifecycle
- Decide submission posture based on gate outcome:
  - **Gate met:** record demo as byproduct (live capture or
    curated replay of a real session), submit with confidence
  - **Gate mostly met (<48h or <N%):** submit with footnote
    ("Concierge has been running live for X hours; here's what
    we've learned")
  - **Gate failed (obvious instability):** Level-3 chat call —
    submit anyway with honest caveat, or slip submission and
    keep fixing

**Midday — submission prep (~3h):**

- README.md finalized from draft + Day-6-morning metrics
- Submission form — hackathon-specific fields; attach whatever
  demo artifact matches the submission posture
- Final repo cleanup (remove `planning/scratch/` experiments, trim
  noise, tag the submission commit)

**Afternoon — submit + reflect (~1h):**

- Submit entry (if submission posture says go)
- Write final snapshot `planning/sessions/SESSION-2026-04-26-01.md`
  capturing the gate outcome, submission decision, and what the
  shakedown taught about operational-fitness of Concierge

**Day 6 checkpoint (Sunday evening):**

- [ ] 48h operational gate met (or explicitly not-met with rationale)
- [ ] Submission decision made and executed per chosen posture
- [ ] README complete with whatever narrative matches the posture
- [ ] Final snapshot written

---

## F.3 Four Phase E adjustments — embedment locations

Cross-reference map so any reader can verify the four adjustments
are embedded as named day-plan items, not footnotes:

| Phase E adjustment | Embedded in | How it appears |
|---|---|---|
| **N8 smoke-test expansion to ~1.0-1.5h** | §F.2.2 Day 2 evening block | Named sub-items: fixture-driven recommendation assertion (`csvstat > pandas`) + round-trip markdown parse check |
| **N10 pull-forward to Day 2 evening as DEFAULT plan** | §F.2.2 Day 2 evening block | Scheduled 4.0h block; Day 3 opens with shim already built |
| **N9 spike 0.5h hard time-box on Day 3 AM** | §F.2.3 Day 3 morning block | First 30 minutes of Day 3; commit to Approach 2 if ambiguous |
| **temperature=0 on N6 Opus calls for demo runs** | §F.2.2 Day 2 afternoon, N6 row | Noted directly on the N6 line; fixture-tuning dev-only exception |

---

## F.4 Ladder-cut triggers — consolidated view

The four pre-sequenced ladder cuts from classification.md §C.4.4
appear as named day-of triggers in the day plans above. Consolidated
here for at-a-glance scan:

| Cut | Day | Trigger condition | Saves | Demo impact |
|---|---|---|---|---|
| **Cut 4** — defer markdown-export from N3 ingest | Day 1 (10pm cutoff) | **N1+N2 aren't both committed-and-tested by 10pm local Tuesday** (includes health-check-fired-after-N1 case, where N2 is deferred to Wed) | 1.0h | Low — SQLite catalog still authoritative |
| **Cut 3** — defer `concierge_list_active` meta-tool | Day 3 AM-midday | N11 start slips past midday on Day 3 (applies under both Scenario A and B) | 1.0h | Low — UI handles active-tool introspection |
| **Cut 2** — drop X13 Python install module | Day 3 midday | Midday block overruns | 1.0h | Low — demo voiceover replaces live auto-install |
| **Cut 1** — trim Health/Stats bar to 3 tiles | Day 4 PM | N18 start slips past 6 PM | 0.5h | Minimal — bar reads cleaner with 3 tiles |

**Full-ladder execution:** saves 3.5h, brings total to 43h.

**Execution protocol:** when a day's trigger condition fires, pull
the ladder cut immediately, log execution in DECISIONS.md (one-liner
with timestamp + reason), continue. No mid-week chat required.

**Beyond Cut 4:** Level-3 chat escalation per §F.7.

**Ladder integrity re-verification (post Tuesday-eve required-framing):**

Cut 3's trigger point — "N11 start slips past midday Day 3" —
remains structurally correct under both Day 2 scenarios:

- **Scenario A (N1+N2 done Tue, N10 pulled-forward to Day 2 eve):**
  Day 3 AM opens with N9 spike (0.5h) → N11 start (~9:30 AM).
  N11 slipping past midday means N11 started, then ran long.
  Cut 3 fires late-morning or midday as originally designed.
- **Scenario B (N1 only Tue, N10 slides to Day 3 AM):** Day 3 AM
  opens with N9 spike (0.5h) + N10 finish (up to 4h) + N11 start
  (~1:30 PM if N10 took full 4h). N11 already starts past midday,
  so Cut 3's trigger condition fires automatically at N11's start
  under Scenario B — this is intended. Cut 3 becomes near-
  deterministic under Scenario B, which is the correct structural
  response to the Day 3 compression.

**Conclusion:** Cut 3's trigger stays as written. Under Scenario B
it fires earlier (at N11 start, not N11-running-long), which
correctly accelerates Day 3's response to the Tuesday-eve
compression. Ladder integrity holds. No other Cut needs re-timing.

---

## F.5 Protected core — non-deferrable

*Renamed 2026-04-21 per DECISIONS `[2026-04-21 18:00]` from
"Protected demo floor." Under operational-first, the same 17 items
remain non-cuttable — but the framing is "minimum operational
core" rather than "minimum demo-scenario core." Demo-capable ==
operational-capable: anything that makes the demo work ALSO makes
daily operation work, so the 17 items are shared between both.
Operational-first additionally protects a superset of unwritten
surface (see end of section).*

Per dependency-graph.md §D.4.3, the 17 items totaling 26-28h that
cannot be cut without breaking the operational core (and therefore
also the demo scenario):

**Catalog surface (~7h):**
- N1, N2, N3, N4 — FastAPI skeleton, schema, ingest, endpoints

**Recommendation surface (~4h):**
- N5, N6 — memory wrapper, `POST /recommend`
- Plus the prompt-fragment extracts (X3, X4, X6, X7) that compose
  into N6's system prompt

**Lifecycle surface (~2.5h):**
- N7 — lifecycle endpoints + markdown parser
- X10 — three-folder layout (LIFT, 0h but demo-required)

**Adapter surface (~9h):**
- N10, N11, N12, N13, N14 — shim, meta-tools, gap-report, spawn/
  teardown, integration smoke

**UI surface (~8h):**
- N15, N16, N17 — shell, Tool Registry, Inbox
- Note: N18 Health/Stats bar is demo-valuable but Cut 1 deferrable;
  the **dormant-badge affordance** on N16 is Q3-demo-beat protected

**Cron surface (~0.5h):**
- X11 — outbox-housekeeping verify + doc (the "watch cron pick it up"
  demo moment depends on this being live)

Total protected: ~27h against 46.5h baseline or 43h with full ladder.
The remaining 16-19.5h distributes across N8 (smoke), N9 (spike),
N18 (tiles 2-4), N19 (token-win), N20 (polish), X8 (SOUL), X13
(install), and various smaller items.

**Operational-first additional protected surface (unnumbered, per
DECISIONS `[2026-04-21 18:00]`):** these are not countable items in
the 17-item demo floor because they do not appear as N-series or
X-series components — but they are required for the 48h operational
gate to be met:

- **Error-handling paths on every endpoint.** 500 responses must be
  logged with enough context that Lewie can diagnose from logs alone.
  422 responses for invalid POST bodies are structured, not generic.
- **Structured logging discipline.** N5/N6/N7 all log operations at
  DEBUG with enough context to reconstruct a failed recommendation
  from logs alone.
- **Graceful degradation.** N6 serves recommendations with
  `memory_available: false` annotation when N5 raises
  `MemoryUnavailableError`. N7 tolerates file-parse failures and
  continues through the directory.
- **X11 cron actually running.** Installation was the Day-2 task
  (0.5h); operational-first elevates to verification that cron
  fires, produces heartbeats in `housekeeping.log`, and produces
  weekly-review output reaching the operator within hour 24 of the
  shakedown.
- **Startup / restart discipline.** Ports released, DB handles
  closed, ChromaDB client disposed on shutdown. Required for a
  running instance to survive the multi-day gate across any
  restart events.

These cost maybe 1-2h of additional discipline across Days 2-3
(spread thin through N5/N6/N7/N8) rather than a dedicated block.
Elevated to the protected tier means they are not cuttable under
any of Cuts 1-4; dropping them is Level-3 chat territory.

---

## F.6 Risk register — Phase E top-5 + post-pivot additions

*Updated 2026-04-21 per DECISIONS `[2026-04-21 18:00]`. Risk 6 added
to cover the operational-shakedown window Days 5-6. Risks 3 and 4
noted as marginally easier under operational-first framing (the
long-form shakedown surfaces variance naturally, and demo-polish
time-pressure relaxes).*

Consolidated from gap-analysis.md §E.2 plus post-pivot additions.
Each risk names: probability, impact, the day its first mitigation
fires, and the specific day-plan line that implements the mitigation.

### F.6.1 Risk 1 — Prompt-fragment correctness on first integration (P:High / I:High)

**First mitigation day:** Day 2 morning (during X3/X4/X6/X7 extract
phase); confirmed Day 2 evening (N8 fixture assertion).

**Day-plan pointers:**

- X6 row in §F.2.2 morning block 2 — "Risk 1 mitigation #2 applies
  (manual Opus test-run before committing the constant)"
- N8 row in §F.2.2 evening block — "fixture-driven recommendation
  assertion (`csvstat` ranks above `pandas`)"
- Per-constant header-comment provenance per DECISIONS 2026-04-21
  05:50 structural mitigation (structural, not day-plan)

### F.6.2 Risk 2 — Stdio proxy shim debugging under time pressure (P:Medium-High / I:High)

**First mitigation day:** Day 2 evening (N10 pulled forward — more
time to debug before Day 3 time pressure).

**Day-plan pointers:**

- N10 pull-forward to Day 2 evening per §F.2.2 (default plan, not
  contingency)
- N9 spike first on Day 3 morning per §F.2.3 — if Approach 1 works,
  shim simplifies
- Fallback: Approach 3 (X16 mcporter ephemeral spawn) noted in §F.2.3
  Day 3 trigger list item 3 — Level-3 chat before invoking

### F.6.3 Risk 3 — Day 3 serial-tail cascade eating Day 4 budget (P:Medium-High / I:Medium → **I: Low-Medium post-pivot**)

**First mitigation day:** Day 3 morning (Cut 3 as first day-of
trigger).

**Post-pivot note (2026-04-21):** impact downgraded under
operational-first. If Day 3 slippage eats into Day 4, it compresses
the operational-readiness runway but does not cascade into demo-
rehearsal time (which no longer exists). Cut 2 (X13 auto-install)
becomes even more comfortable to drop since manual install in a
voiceover is demo-first vocabulary; under operational-first, manual
install is just a setup step Lewie does once per shakedown start.

**Day-plan pointers:**

- Cut 3 — `concierge_list_active` deferral — first Day 3 trigger per
  §F.2.3 trigger list item 1
- N10 pull-forward to Day 2 evening absorbs the risk structurally —
  Day 3 opens with 4h of critical-path work already complete
- Day 5 first-24h-shakedown absorbs any Day-4 overflow via reactive
  fixing rather than dedicated stabilization slot

### F.6.4 Risk 4 — Opus 4.7 recommendation quality variance (P:Medium / I:High → **I: Medium post-pivot**)

**First mitigation day:** Day 2 afternoon (temperature=0 locked on
N6 from day of implementation).

**Post-pivot note (2026-04-21):** impact downgraded under
operational-first. A 48h live shakedown surfaces Opus variance
naturally through ~dozens of real recommendations; "5 consecutive
clean runs" was a synthetic and less rigorous test. Variance that
shows up in live use is the signal that matters, and there is
time in the shakedown window to tune fragments or adjust
temperature in response. N6's graceful-degradation requirement
(serve a recommendation even when memory is unavailable) also
structurally limits variance-impact — a worst-case variant is
still an answer, not a 500.

**Day-plan pointers:**

- N6 row in §F.2.2 afternoon — "temperature=0 locked from
  implementation"
- N8 fixture-driven assertion catches variance on Day 2 evening
- Day 5-6 live shakedown surfaces variance across real tasks;
  reactive tuning in response rather than synthetic rehearsal

### F.6.5 Risk 5 — Markdown round-trip parser surfacing late (P:Medium / I:Medium-High)

**First mitigation day:** Day 2 evening (N8 round-trip check).

**Day-plan pointers:**

- N8 row in §F.2.2 evening — "round-trip markdown parse check
  (write fixture → POST status → re-GET → assert)"
- Fixture inventory per Phase E §E.5 item 8 — captures real-world
  format variants from actual `_legacy/tool-requests/` pending/ folder
  during Tuesday evening or Wednesday morning

### F.6.6 Risk 6 — Operational regressions during 48h shakedown (P: Medium / I: Medium-High)

*Added 2026-04-21 per DECISIONS `[2026-04-21 18:00]`. New risk
introduced by the operational-first pivot — Concierge running live
on Lewie's daily Claude Code sessions during Days 5-6 means
Concierge can break mid-session.*

**What this risk looks like in practice:**

- A Day-5 session hits a bug that causes `concierge_recommend` to
  return a 500, interrupting Lewie's real work
- A bug corrupts the Concierge memory store mid-session (unlikely
  given isolation default, but possible)
- The ChromaDB backing store runs out of disk or hits a lock
  contention during live use
- A cron run produces a crash loop during the shakedown window

**First mitigation day:** Day 5 opening (before live use begins).

**Day-plan pointers:**

- Git-tag the last-known-good commit at Day 5 open (and at any
  stable point during Days 5-6) so revert-path is available
- Logging discipline from Days 2-3 (Risk 6 depends on structured
  logging being sufficient for diagnose-from-logs)
- Graceful degradation paths (`MemoryUnavailableError` catchable at
  endpoint boundaries) limit blast radius of subsystem failures
- Memory-isolation default (`~/.concierge-memory/`, not shared with
  moltbot) bounds the "corrupt production state" worst case
- If shakedown surfaces a showstopper within the 48h window, the
  revert-to-tag + continue-shakedown-with-less-ambitious-scope path
  is preferred over pushing through — Level-3 chat if unclear

---

## F.7 Level-3 escalation items (cuts past Cut 4)

Per classification.md §C.4.4, cuts beyond Cut 4 require chat-level
escalation because they touch demo-materiality. Listed here for
reference; do **not** invoke without Level-3 chat conversation first.

| Candidate | Saves (est.) | Why escalation required |
|---|---|---|
| Drop N12 gap-report injection | 2.0h | Pitch-demo moment — "agent proactively surfaces what it's missing." Concierge becomes passive-query |
| Drop N19 token-win counter | 1.0h | Pitch-critical tile for lightweight-substitute win narrative |
| Defer N5 memory wrapper | 1.0h | Cascade — N6 depends on it; N19 depends on it; materially changes recommendation quality |
| Defer N16 filter/search UI | ~1-2h | Turns Tool Registry into flat list; breaks pack-hierarchy narrative (first thing demo-viewer clicks) |
| Drop N18 dormant-badge affordance | 1.0h | Removes Q3 decision surface — a planned demo beat |

---

## F.8 Questions for Lewie

**Q1 (Tuesday evening sprint framing):** ANSWERED 2026-04-21 via
operator-context reframing — **required, not stretch goal.**
Scope: N1 + N2 required (health-check-gated between them), N3
stretch. Cut 4 trigger rewritten to fire at 10pm local Tuesday if
N1+N2 aren't both committed-and-tested. Full reasoning in
DECISIONS `[2026-04-21 07:00]` entry. Day 2 rebalanced in §F.2.2
with Scenario A/B/C structure.

**Q2 (Day 3 overflow absorbing — Level-3 posture):** Day 3 is
11.5-13h of critical-path work in an 8-10h day even with the full
ladder. If Day 3 overruns by ≥2h despite Cuts 2+3, the escalation
triggers to Level-3 chat. Confirm the escalation destination is
Claude.ai chat (not mid-build Claude Code consultation) so the
decision-making surface is fully visible to both parties.

My lean: **yes, Claude.ai chat.** Mid-build Claude Code sessions are
execution mode, not decision mode. Level-3 cuts materially change
demo scope and deserve chat-level deliberation. Taking implicit
acceptance absent explicit pushback at Phase F signoff.

---

## F.9 Phase F checkpoint

Per `docs/concierge-claude-code-plan-v3.md` §Phase F checkpoint:

- [x] `planning/build-plan.md` exists
- [x] `planning/executive-summary.md` exists (written alongside this)
- [x] Six daily plans cover Tuesday 2026-04-21 through Sunday
      2026-04-26
- [x] All four Phase E adjustments embedded as named day-plan items
      (§F.3 cross-reference)
- [x] All four ladder cuts named as day-of triggers in the correct
      day (§F.4 consolidated view)
- [x] Risk register consolidates Phase E top-5 with day-of mitigation
      pointers (§F.6)
- [x] Protected demo floor explicit (§F.5 — 17 items, ~27h)
- [x] Level-3 escalation items named, not pre-sequenced (§F.7)
- [x] Lewie has reviewed and signed off on Phase F (2026-04-21 — see
      DECISIONS.md `[2026-04-21 07:00]` framing change and
      `[2026-04-21 07:05]` Phase E + Phase F bundled approval)

Additional phase-gate traceability:

- [x] Inputs from Phases A-E explicitly cited (§F.1)
- [x] Parallelism-realism carry-forward from Phase D signoff honored
      (Day 2 and Day 4 plans are sequential-focus, not nominal-parallel)
- [x] Session-close session-snapshot plan captured (§F.2.6 + today.md)
- [x] Tuesday-evening required-framing (post-summary reframe) reflected
      in §F.2.1 with health-check safety valve and 10pm Cut 4 trigger
- [x] Ladder-integrity re-verified for Cut 3 under both Day 2 scenarios
      (§F.4 ladder integrity re-verification paragraph)

---

## F.10 Summary for chat

Proposed summary for Lewie at Phase F signoff:

**Plan shape:** six days Tuesday → Sunday. Day 1 = planning tail +
**required** foundation sprint (N1+N2 required with health-check
midway; N3 stretch; 10pm Cut 4 trigger). Day 2 = service core +
N10 pull-forward (longest build day; ~15.5h Scenario A target).
Day 3 = adapter stack + integration smoke (critical-path
high-pressure; Cut 3 is first day-of trigger, fires earlier under
Scenario B). Day 4 = UI three sections sequential-focus. Day 5 =
stabilization + 5-consecutive-clean rehearsal. Day 6 = recording +
submission.

**Four Phase E adjustments embedded (§F.3):** N8 expanded to 1.0-1.5h
on Day 2 eve; N10 pulled forward to Day 2 eve as default; N9 spike
0.5h hard time-box on Day 3 AM; temperature=0 on N6 locked from
implementation.

**Four ladder cuts as named triggers (§F.4):** Cut 4 fires at 10pm
Tuesday if N1+N2 aren't both committed-and-tested; Cut 3 Day 3 AM
if N11 slips (auto-fires under Scenario B); Cut 2 Day 3 midday if
overrun; Cut 1 Day 4 PM if N18 slips. Full ladder saves 3.5h → 43h.

**Protected demo floor (§F.5):** 17 items / ~27h that cannot be cut
without demo damage.

**Top 5 risks, all with day-of mitigation pointers (§F.6):** prompt-
fragment correctness (Day 2), stdio shim debugging (Day 2 eve pull-
forward), Day 3 serial-tail (Cut 3 trigger), Opus variance
(temperature=0 + rehearsal), markdown parser (Day 2 round-trip check).

**Tuesday-evening safety valve:** health check at ~8pm local, post-N1
and pre-N2. Criteria: readable code, <=2 trivial mistakes in the
last hour, tired-but-engaged. Fail any → end sprint, N2 rolls to Wed,
Cut 4 fires at 10pm automatically. "Required" ≠ "push through injury."

**Q1 resolved; Q2 taken as implicitly accepted (§F.8).** Phase F is
synthesis not original decision-making; every call above is citable
back to Phase C/D/E + DECISIONS.md.

---

*Phase F deliverable complete pending Lewie's review. Phase F signoff
closes the planning arc. Session-close snapshot
`planning/sessions/SESSION-2026-04-21-01.md` writes tonight covering
the full Phase C → D → E → F arc.*
