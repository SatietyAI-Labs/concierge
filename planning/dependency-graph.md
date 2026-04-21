# Concierge — Phase D (Dependency Graph)

*Deliverable of Phase D per `docs/concierge-claude-code-plan-v3.md`.*
*Session:* `SESSION-2026-04-21-02` (continuation from Phase C).
*Generated:* 2026-04-21.
*Effort:* `xhigh`.

Phase D follows Phase C sign-off. Input is the 24-row classification
table (§C.2.1) and the three new-build work packages (§C.3.1-3). This
phase produces the full dependency map, identifies the critical path
from empty repo to working demo, and calls out parallel-work and
deferrable items so Phase F's build plan has a dependency-aware
day allocation.

Convention: component IDs prefix with `X` for existing-extracted
(maps to classification.md row #), `N` for new-build sub-items (maps
to §C.3 tables). Non-effort items (LIFT with 0h) and scope-excluded
RETIREs are omitted from the dependency map; they have no build-order
implications.

---

## D.1 Component dependency inventory

### D.1.1 Build-affecting components

Twenty-two items carry non-zero effort or are themselves dependencies
of other items. Organized below as two tables for readability.

**Existing-extracted + integration items (from classification.md §C.2):**

| ID | Component | Effort | Day | Notes |
|---|---|---|---|---|
| X1 | TOOL-MANIFEST.md (shared ingest with X2) | 1.5h | Day 1 | Read-in for N3 ingest |
| X2 | TOOL-CATALOG.md (shared with X1) | (shared) | Day 1 | Read-in for N3 ingest |
| X3 | tool-awareness.md → prompt fragment | 0.5h | Day 2 | Prompt-fragment extract (see DECISIONS 2026-04-21 05:50) |
| X4 | tool-recommendation.md → prompt fragment | 0.5h | Day 2 | Prompt-fragment extract |
| X6 | tool-discovery SKILL.md → prompt fragment | 1.0h | Day 2 | Prompt-fragment extract; demo-critical instance |
| X7 | tool-lifecycle SKILL.md → hybrid | 1.0h | Day 2 | Thresholds/tag-schema to Python constants; review protocol to prompt fragment |
| X8 | SOUL.md root → Claude-Code-specific prompt fragment | 0.5h | Day 3 | Feeds N12 gap-report injection |
| X10 | tool-requests/ three-folder layout (LIFT) | 0h | Day 2 | N7 wraps its read/write semantics |
| X11 | outbox-housekeeping.sh verify + doc | 0.5h | Day 2 | Confirm crontab; document heartbeat path for N18 |
| X13 | tool-install-npm/pip → Python install module | 1.0h | Day 3 | Supports N7 approve-action; deferred in Cut 2 of ladder |
| X15 | moltbot-memory-mcp (LIFT + library import) | 0h | Day 2 | Imported by N5 wrapper |
| X22 | openclaw.json parse | 0h (counted in N16/N18) | Day 1 | Read-in for UI's active-MCP count and dormant-badge |

**New-build sub-items (from classification.md §C.3):**

| ID | Sub-item | Effort | Day | Source |
|---|---|---|---|---|
| N1 | FastAPI project skeleton | 1.0h | Day 1 AM | §C.3.2 |
| N2 | SQLite schema + SQLAlchemy models | 2.0h | Day 1 | §C.3.2 |
| N3 | Markdown-to-SQLite ingest (reads X1 + X2 + X22) | 2.0h | Day 1 | §C.3.2 |
| N4 | Catalog API endpoints + markdown export | 2.0h | Day 1 PM | §C.3.2 (markdown export is Cut 4 of ladder) |
| N5 | Memory service wrapper (imports X15) | 1.0h | Day 2 AM | §C.3.2 |
| N6 | Recommendation endpoint (POST /recommend) | 3.0h | Day 2 | §C.3.2; system prompt composed from X3 + X4 + X6 + X7 |
| N7 | Lifecycle API endpoints + markdown parser | 2.5h | Day 2 PM | §C.3.2; reads/writes X10 folder |
| N8 | Smoke tests + fixtures + heartbeat endpoint | 0.5h | Day 2 eve | §C.3.2 |
| N9 | `tools/list_changed` verification spike | 0.5h | Day 3 AM | §C.3.1 |
| N10 | stdio proxy shim skeleton | 4.0h | Day 3 | §C.3.1; branch depends on N9 outcome |
| N11 | Meta-tool surface: `concierge_recommend`, `concierge_request_tool`, `concierge_list_active` | 3.0h | Day 3 | §C.3.1; `list_active` is Cut 3 of ladder |
| N12 | Gap-report injection via `concierge_recommend` result | 2.0h | Day 3 | §C.3.1; requires X8 prompt fragment |
| N13 | Backing-server spawn/teardown lifecycle mgmt | 2.0h | Day 3 | §C.3.1 |
| N14 | Integration debug + end-to-end smoke | 2.0h | Day 3 PM | §C.3.1 |
| N15 | UI layout shell (Pico.css + Jinja2 base) | 1.0h | Day 4 AM | §C.3.3 |
| N16 | Tool Registry section | 4.0h | Day 4 AM | §C.3.3; reads N4 + X22 |
| N17 | Pending Requests Inbox section | 3.0h | Day 4 PM | §C.3.3; reads/writes N7 |
| N18 | Health/Stats bar | 2.0h | Day 4 PM | §C.3.3; reads N4, N19, X11 heartbeat |
| N19 | Token-win instrumentation | 1.0h | Day 4 PM | §C.3.3; writes to N5 memory |
| N20 | UI integration + polish | 1.0h | Day 4 eve | §C.3.3 |

**Total build-affecting items:** 12 existing-extracted (X-series) +
20 new-build (N-series) = **32 tracked items** in the dependency graph.

### D.1.2 Per-component dependency edges

Notation: `A → B` means "A depends on B" (B must exist/complete before
A can start). Upstream direction; read bottom-up to identify starting
points. Items not listed have no upstream dependency beyond the
hackathon repo existing.

**Day 1 items (foundation chain):**

| Item | Depends on | Depends by |
|---|---|---|
| N1 (FastAPI skeleton) | — | N2, N4, N5, N6, N7, N15 |
| N2 (SQLite schema) | N1 | N3, N4, N5, N6, N7 |
| N3 (ingest routine) | N2; reads X1, X2, X22 (on disk, always-present) | N4 |
| N4 (catalog endpoints) | N2, N3 | N16, N18 |
| X22 (openclaw.json parse) | — (file present on disk) | N3 (ingest pass), N16 (dormant-badge), N18 (active-MCP count) |

**Day 2 items (service core):**

| Item | Depends on | Depends by |
|---|---|---|
| X3 (tool-awareness prompt fragment) | — (markdown file on disk) | N6 |
| X4 (tool-recommendation prompt fragment) | — | N6 |
| X6 (tool-discovery prompt fragment) | — | N6 |
| X7 (tool-lifecycle hybrid constants + protocol fragment) | — | N6 (the review-protocol part feeds Lifecycle State Machine surface); N7 (thresholds/schema constants) |
| N5 (memory wrapper) | N1, N2; imports X15 | N6, N19 |
| N6 (recommendation endpoint) | N1, N2, N5, X3, X4, X6, X7 (partial) | N11 (indirectly via `concierge_recommend`), N12 (gap-report result payload), UI integration via N18 if tokenwin touches it |
| N7 (lifecycle endpoints) | N1, N2; reads/writes X10; uses X7 thresholds | N11 (`concierge_request_tool`), N17 |
| N8 (smoke tests + heartbeat) | N4, N6, N7 | downstream consumers that check liveness |
| X11 (outbox-housekeeping verify + doc) | X10 exists (trivially) | N18 (heartbeat path for the tile) |

**Day 3 items (Claude Code adapter):**

| Item | Depends on | Depends by |
|---|---|---|
| N9 (verification spike) | — | N10 approach decision |
| X13 (tool-install Python extract) | N1 (imports from `core/install.py`) | N7 approve-action wiring (optional, deferrable via Cut 2) |
| N10 (stdio proxy shim) | N9 outcome; uses X16 (mcporter) as tertiary fallback path only | N11, N13 |
| X8 (SOUL root → Claude-Code prompt fragment) | — | N12 |
| N11 (meta-tools) | N10, N4, N6, N7 | N12 |
| N12 (gap-report injection) | N11, X8 | N14 |
| N13 (backing-server spawn/teardown) | N10 | N14 |
| N14 (integration smoke) | N11, N12, N13, N6, N7 | Day 3 checkpoint |

**Day 4 items (UI):**

| Item | Depends on | Depends by |
|---|---|---|
| N15 (UI layout shell) | N1 | N16, N17, N18, N20 |
| N16 (Tool Registry) | N15, N4, X22 | N20 |
| N17 (Pending Requests Inbox) | N15, N7 | N20 |
| N18 (Health/Stats bar) | N15, N4, N19, X11 (heartbeat path) | N20 |
| N19 (Token-win instrumentation) | N5 | N18 (the token-win tile), N20 |
| N20 (UI integration + polish) | N15, N16, N17, N18, N19 | Day 4 checkpoint |

### D.1.3 Topological read

Legal build-day topological sort respecting upstream edges:

1. **Day 1 AM:** N1 → N2 → N3 (with X1/X2/X22 files as input)
2. **Day 1 PM:** N4 (requires N2+N3)
3. **Day 2 AM:** in parallel — N5 (requires N1+N2+X15); X3, X4, X6, X7
   prompt-fragment extracts (each independent of every other item
   except N6)
4. **Day 2 midday:** N6 (requires N5 + X3 + X4 + X6 + X7 review
   material merged into system prompt)
5. **Day 2 PM:** N7 (requires N2 + X10 + X7 thresholds); N8 smoke
   tests (requires N4 + N6 + N7)
6. **Day 2 anytime:** X11 outbox-housekeeping verify + doc
   (standalone; no upstream)
7. **Day 3 AM:** N9 spike first; then N10 shim with the branch-aware
   design chosen by spike outcome; X8 SOUL extract can happen in
   parallel with N10
8. **Day 3 midday:** N11 meta-tools (requires N10 + N4 + N6 + N7);
   X13 Python install module can happen in parallel with N11 (or
   get cut via Cut 2)
9. **Day 3 PM:** N12 gap-report injection (requires N11 + X8); N13
   spawn/teardown (requires N10)
10. **Day 3 eve:** N14 integration smoke
11. **Day 4 AM:** N15 layout shell; then N16 Tool Registry (requires
    N15 + N4 + X22)
12. **Day 4 PM:** in parallel — N17 Inbox (requires N15 + N7); N19
    token-win (requires N5); N18 Health/Stats (requires N19 + N15 +
    N4 + X11)
13. **Day 4 eve:** N20 integration + polish

---

## D.2 Critical path

### D.2.1 Longest chain from empty repo to working demo

The strict critical path — every edge in the chain is a hard upstream
dependency, no work can begin on the downstream item until the
upstream completes:

```
N1 (1.0h)
 → N2 (2.0h)
 → N3 (2.0h)
 → N4 (2.0h)                            [Day 1 foundation — 7.0h]
 → N5 (1.0h)
 → N6 (3.0h)                            [Day 2 service core — 4.0h]
 → N11 (3.0h) via N10 (4.0h) via N9 (0.5h)
                                        [Day 3 adapter chain — 7.5h]
 → N12 (2.0h)
 → N14 (2.0h)                           [Day 3 integration — 4.0h]
 → N15 (1.0h)
 → N17 (3.0h)                           [Day 4 UI primary — 4.0h]
 → N20 (1.0h)                           [Day 4 polish — 1.0h]
```

**Strict critical-path length: 27.5h.**

That's the longest serial chain that cannot be parallelized away by
adding more resources. Solo builder: serial execution is the reality
anyway, but the critical-path number tells us how much of the 46.5h
grand total is unparallelizable versus where branch-and-merge
structure buys us schedule flexibility.

### D.2.2 Why N17 is the tail, not N20's broader UI dependencies

N20 depends on N15 + N16 + N17 + N18 + N19. The longest *tail* into
N20 is N17 → N15 (Pending Requests Inbox depending on lifecycle
endpoints depending on Day 2 foundation). N16, N18, N19 can start
earlier in Day 4 afternoon and land before or alongside N17's 3h
budget.

If N18 were on the critical path instead of N17, the numbers would
be identical (both are Day 4 PM items on the tail). But N17's
dependency on N7 is a serial back-link to Day 2's final deliverable;
if Day 2 overruns, N17 slips first.

### D.2.3 Slack analysis

Items **on** the critical path have zero slack — any delay propagates.
Items **off** the critical path carry slack equal to the critical
path length minus their own chain length. Short slack summary:

| Item | On critical path? | Approx. slack if off-path |
|---|---|---|
| X3, X4, X6, X7 prompt fragments | Yes (via N6) | 0h |
| X8 SOUL extract | Near-path (via N12) | ~1h — can slip into Day 3 midday without cascading |
| X11 outbox-housekeeping verify | Off-path | ~4h — can fit any Day 2 gap |
| X13 install module | Off-path (supports N7 approve but approve can use manual install) | ~3h — can slip or be cut (Cut 2 of ladder) |
| N13 spawn/teardown | Off-path (parallel with N12) | ~1-2h |
| N16 Tool Registry | Off-path but long (4h) | ~1h — arrives before N17's tail closes |
| N18 Health/Stats | Off-path | ~1-2h |
| N19 Token-win | Off-path | ~2h |

**Highest-slack deferrables** (items that can slip the most without
affecting demo-day delivery): X13, N19, X11, N18. Three of these
overlap with ladder cuts from §C.4.4, which confirms the ladder's
sequencing aligns with off-path / low-impact structure.

---

## D.3 Parallel work opportunities

Phase D.3 identifies where two or more items can proceed concurrently
without a dependency conflict — i.e. where a faster ghost-worker (or
a willing Lewie across multiple terminal sessions) could compress
wall-clock time even though the total effort doesn't change.

### D.3.1 Within-day parallelism

**Day 1:** linear chain (N1 → N2 → N3 → N4). No within-day
parallelism — each step gates the next. Total ~7h.

**Day 2:** two branches that merge.

```
Branch A:  N5 (1h)                   ↘
Branch B:  X3,X4,X6,X7 extracts (3h) → N6 (3h) → N8 (0.5h smoke)
                                        ↗ N7 (2.5h)
```

Branch A and Branch B can proceed concurrently. X11 verify/doc
(0.5h) is off-branch and can fit any gap. Net critical branch: 3h +
3h + 2.5h + 0.5h = ~9h if strictly serial; ~6-7h with parallel
branch execution on Branch A's 1h.

**Day 3:** two branches after N10 completes.

```
After N10 (4h):
  Branch A: N11 (3h) → N12 (2h)       ↘
  Branch B: N13 (2h)                  → N14 (2h)
  Side-branch: X13 Python install (1h; off-path, optional)
  Side-branch: X8 SOUL extract (0.5h; can be earlier, Day 2 eve)
```

N11 and N13 can proceed in parallel after N10 lands. N14 waits for
both. With perfect parallelism the Day 3 wall-clock is 0.5 (spike) +
4 (shim) + 3 (N11 longer branch) + 2 (N14) = 9.5h. Still over
single-day budget; Phase F decides how to handle the overflow (per
§C.7 carry-forward).

**Day 4:** four branches after N15 completes.

```
After N15 (1h):
  Branch A: N16 (4h)               ↘
  Branch B: N17 (3h)               → N20 (1h)
  Branch C: N19 (1h) → N18 (2h)   ↗
```

Branches A, B, C all parallel. N19 gates N18. N20 waits for all.
With perfect parallelism: 1h + 4h + 1h = 6h wall-clock; strictly
serial: 12h. Solo builder splits the difference depending on
focus-switching tolerance.

### D.3.2 Cross-day pull-forward candidates

Items whose dependencies land earlier than their assigned day, and
where the dependency graph would permit pulling them forward:

- **N10 stdio proxy shim (4h)** — can start end of Day 2 if Day 2
  runs fast (Day 2 ends with N8 smoke tests at ~8-9h; proxy shim
  only depends on N9 spike which is independent of Day 2 work). This
  is exactly the Q2 carry-forward from §C.7 — Phase F decides.
- **X8 SOUL prompt fragment (0.5h)** — can land Day 2 evening even
  though it's for Day 3's N12. Its upstream dependency (the SOUL
  markdown file on disk) is always present. Pulling forward frees
  Day 3 midday.
- **X11 outbox-housekeeping verify + doc (0.5h)** — can land Day 1
  afternoon between N3 and N4 if Day 1 runs fast. Zero upstream.
- **N19 token-win instrumentation (1h)** — depends only on N5
  memory wrapper; can be pulled to Day 3 if Day 3 runs fast.
- **X13 tool-install Python module (1h)** — can be pulled to Day 2
  if not dropped (Cut 2 ladder candidate).

### D.3.3 Items that **must** remain serial

These have true upstream dependencies and cannot pull forward.

- **N3 ingest** must follow N2 schema (writes to the tables the
  schema defines).
- **N6 recommendation** must follow the prompt-fragment extracts
  (system prompt composition requires the fragment constants to
  exist in code).
- **N11 meta-tools** must follow N10 proxy shim (meta-tools register
  through the shim's MCP surface).
- **N12 gap-report injection** must follow N11 (hooks `concierge_
  recommend`'s result payload).
- **N14 integration smoke** must follow N11 + N12 + N13 (tests all
  three).
- **N16, N17, N18** all must follow N15 layout shell (templates
  extend the base).
- **N20 UI polish** must follow N15-N19 (integration happens last).

---

## D.4 Deferrable items

Per classification.md §C.4.4 pre-sequenced pull-out ladder, four
items can be cut with day-of trigger if any day overruns. Mapped
onto the dependency graph:

### D.4.1 Ladder-aligned deferrables

| Cut | Item (in D.1 ID terms) | Upstream commitment preserved? | Downstream impact if cut |
|---|---|---|---|
| Cut 1 | N18 reduced to 3 tiles (drop top-3-tools tile) | Yes — the tile itself is a subcomponent of N18, not its own node | None; N18 ships with 3 tiles |
| Cut 2 | X13 tool-install Python module | Yes — X13 is off-path per D.2.3 | N7 approve-action uses a manual install command shown in terminal for demo; voiceover replaces live action |
| Cut 3 | `concierge_list_active` sub-surface of N11 | Yes — it's one of three meta-tools inside N11's budget | Agent files requests blind; Tool Registry UI handles active-tool introspection for human operator |
| Cut 4 | Markdown export from N3 ingest | Yes — it's a side-effect of N3, not a separate node | SQLite catalog still authoritative; markdown-export lands post-demo |

**All four ladder cuts target off-path or sub-node items.** That is
the structural safety property of the ladder — executing cuts 1-4
does not slip any critical-path item.

### D.4.2 Escalation-tier deferrables (Level-3 chat)

Per §C.4.4, cuts beyond Cut 4 require chat-level escalation because
they touch demo-materiality. Mapped to graph structure:

- **Drop N12 gap-report injection entirely.** High critical-path
  impact — this is the pitch-demo moment ("the agent proactively
  surfaces what it's missing"). Dropping it turns Concierge into a
  passive-query system.
- **Drop N19 token-win counter.** Off-path but pitch-critical for
  the "lightweight-substitute win" narrative.
- **Defer N5 memory wrapper.** Cascade — N6 recommendation depends
  on it; N19 depends on it. Cutting this would require N6 to be
  memory-less, which materially changes the recommendation quality.
- **Defer N16 Tool Registry filter/search UI.** Off-path visually
  but is the first thing Lewie clicks in the demo; turning it into
  a flat list breaks the "pack hierarchy" narrative.
- **Drop N18 dormant-badge affordance** (manifest-vs-active delta).
  Removes the Q3 decision surface from 2026-04-20 — a planned demo
  beat. Worth preserving.

These are intentionally **not** pre-sequenced. Pulling any of them
is a Level-3 chat decision.

### D.4.3 Non-deferrable (demo-blocking)

Items whose removal breaks the demo scenario itself. These are
protected; cannot be cut even under schedule pressure:

- N1, N2, N3, N4 — the catalog surface; without it nothing downstream
  has data.
- N5, N6 — the recommendation surface; without it "Concierge
  recommends tools" is not demonstrable.
- N7 — the lifecycle surface; without it the approve/deny path
  doesn't exist.
- N10, N11 — the adapter shim and meta-tools; without them Claude
  Code has no way to talk to Concierge.
- N15, N16, N17 — the UI shell and two of three sections; Health/
  Stats is optional (Cut 1 territory) but not these.

The protected core: **17 items totaling roughly 26-28h** of the
46.5h grand total. Everything else carries at least some slack or
cut optionality.

---

## D.5 Risks surfaced by the dependency structure

Phase E will do full risk analysis; Phase D notes dependency-shaped
risks that Phase E should absorb.

1. **Day 2 prompt-fragment composition is the first integration
   load-bearing moment.** X3 + X4 + X6 + X7 compose into N6's system
   prompt. If any fragment is wrong (signal table mis-transcribed,
   protocol steps out of order), N6 produces bad recommendations
   and the demo narrative tarnishes. Mitigation: pair the paste
   with a manual Opus test run before committing.
2. **N9 spike outcome branches N10's architecture.** If
   `tools/list_changed` works in-session, Approach 1 shortens N10
   by ~4h. If it doesn't, Approach 2 proceeds as-planned. Either is
   fine; the risk is ambiguity — we could get a "partly works" spike
   result. Mitigation: time-box the spike at 0.5h, commit to
   Approach 2 if the result is ambiguous.
3. **N11 → N12 → N14 tail is the longest serial chain on Day 3.**
   Any slip in N11 cascades through N12 and N14. If Day 3 morning
   runs late, N14 could land Day 4 morning and compete with N15-
   N16 for time budget. Mitigation: pull N10 to Day 2 evening if
   Day 2 runs fast (§C.7 carry-forward).
4. **N17 depends on N7; N7 depends on X10 filesystem layout being
   trusted.** If we discover a bug in the lifecycle markdown parser
   on Day 4, it surfaces in the UI (Inbox shows wrong data) not in
   the API (which has passed smoke tests). Mitigation: N8 smoke
   tests on Day 2 should include a round-trip markdown-file write/
   parse check, not just endpoint liveness.
5. **Day 4 three-branch parallel structure is solo-builder-hostile.**
   N16, N17, N18 parallelism is only real with context-switching;
   in practice one gets 100% focus, others get partial attention.
   Likely wall-clock on Day 4 is closer to the 12h serial total
   than the 6h parallel ideal. Mitigation: N16 first (biggest,
   longest), then N17, then N18 last; N20 integration absorbs
   whatever rough edges remain.

---

## D.6 Questions for Lewie

No Phase-C-style material questions — the dependency structure
follows from the classification and architecture-map decisions
already made. One small confirmation:

**Q1 (Day 3 carry-forward confirmation):** D.2.3 slack analysis
shows N10 (stdio proxy shim) has zero slack on Day 3's critical
path, and Day 3 has 12-14h of work for an 8-10h day. Phase D
flags this; the actual day-allocation decision stays deferred
to Phase F (per Q2 answer on Phase C). Confirm the deferral
remains correct and nothing in Phase D changes that posture?

My lean: **Phase F still decides.** Phase D surfaces the dependency
structure (which is what it's for); Phase F makes the
call with full gap analysis in hand from Phase E.

---

## D.7 Carry-forward notes for Phase E and Phase F

**For Phase E (Gap Analysis):**

1. **Prompt-fragment correctness check** (D.5 risk #1) should be a
   Phase E capability-checklist item: "recommendation endpoint
   produces recommendations consistent with the discovery-signals
   protocol." Passing this check depends on the fragment extracts
   being correct, not just the endpoint being live.
2. **N9 spike outcome** branches N10 effort by up to 4h; Phase E
   should list the binary-branch and its downstream impact as a
   known conditional.
3. **Markdown round-trip check** (D.5 risk #4) belongs in Phase E's
   coverage analysis for the lifecycle capability.
4. **Token-win rough-heuristic calibration** (already confirmed in
   §C.6 Q3) is one of the capabilities in the checklist; Phase E
   just confirms scope.

**For Phase F (Build Plan):**

1. **Pull-forward candidate N10 to Day 2 evening** (§C.7 already
   notes this; D.3.2 confirms the dependency graph permits it if
   N9 lands Day 2 evening too).
2. **Ladder-cut sequencing** in §C.4.4 aligns with dependency
   slack structure per D.4.1. Phase F encodes cut triggers as
   day-of checkpoint failures.
3. **Day 4 parallel-branch structure** (D.3.1) should be reflected
   in Phase F's day-4 session breakdown. One session per UI branch
   (N16, N17, N18+N19) plus N15 setup plus N20 polish = ~4-5
   focused mini-sessions on Day 4, matching the blueprint's
   three-session day.
4. **Protected core** (D.4.3) defines the demo floor. Phase F's
   risk register should confirm none of these items can slip
   below Day 4 without demo-scenario damage.
5. **Cross-day pull-forward candidates** (D.3.2) become Phase F
   day-of options: if a day runs fast, here are the items whose
   dependencies are already satisfied and can absorb the surplus.

---

## D.8 Summary for chat

Proposed summary for Lewie (pre-checkpoint):

**Graph shape:** 32 tracked build-affecting items (12 existing-
extracted + 20 new-build sub-items). Day-by-day topology: Day 1
linear foundation → Day 2 two-branch merge (memory + prompt fragments
→ recommendation + lifecycle) → Day 3 adapter chain with one branch
at the top (spike decides approach) → Day 4 four-branch UI
parallelism merging at polish.

**Critical path:** N1 → N2 → N3 → N4 → N5 → N6 → (N9 → N10) → N11
→ N12 → N14 → N15 → N17 → N20. **Strict length: 27.5h** of the 46.5h
total — the remaining ~19h is parallelizable branch-and-merge work
or off-path extras.

**Highest-leverage pull-forward:** N10 stdio proxy shim (4h) into
Day 2 evening if Day 2 runs fast — already flagged in §C.7 Phase F
carry-forward.

**Ladder integrity:** all four pre-sequenced ladder cuts from §C.4.4
target off-path or sub-node items. Executing cuts 1-4 does not slip
any critical-path item. Structural safety property confirmed.

**Day 3 overflow reconfirmed.** 12-14h of adapter work for an
8-10h day even with the optimal parallel structure; Phase F makes
the allocation call.

**Day 4 solo-builder realism:** three-branch parallel structure
(N16, N17, N18/N19) has theoretical wall-clock of ~6h but practical
wall-clock closer to ~10-12h due to context-switching costs.
Phase F's Day 4 session breakdown should lean toward sequential-
focus rather than nominal parallel.

**No new decisions required.** One small confirmation question on
Phase F deferral (Q1 in §D.6) that I expect to close in chat.

---

## D.9 Phase D checkpoint

Per plan-v3 §Phase D checkpoint:

- [x] `planning/dependency-graph.md` exists
- [x] Critical path identified (§D.2.1 — 27.5h strict)
- [x] Parallel work and deferrable items called out (§D.3, §D.4)

Additional items surfaced for phase-gate traceability:

- [x] Topological legal-order per day documented (§D.1.3)
- [x] Slack analysis per item (§D.2.3)
- [x] Ladder-cut alignment with dependency structure verified (§D.4.1)
- [x] Dependency-shaped risks surfaced for Phase E consumption (§D.5)
- [x] Phase E / Phase F carry-forward notes (§D.7)
- [x] Lewie has reviewed and signed off on Phase D (2026-04-21 —
      see DECISIONS.md)

---

*Phase D deliverable complete and signed off 2026-04-21. Phase E —
Gap Analysis begins at `xhigh` effort per plan-v3.*
