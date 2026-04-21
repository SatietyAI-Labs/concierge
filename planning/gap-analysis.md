# Concierge — Phase E (Gap Analysis)

*Deliverable of Phase E per `docs/concierge-claude-code-plan-v3.md`.*
*Session:* `SESSION-2026-04-21-02` (continuation from Phase D).
*Generated:* 2026-04-21.
*Effort:* `xhigh`.

Phase E confirms every capability the demo scenario requires has a
clear build path, with existing coverage itemized and net-new effort
quantified. Top five risks are surfaced for Phase F's risk register.
Inputs: classification.md §C.2-3, dependency-graph.md §D.1-5,
blueprint-v2 §Demo scenario, SESSION-2026-04-20-01 bugs/issues
section.

Component IDs carry forward from dependency-graph.md (`X` for
existing-extracted, `N` for new-build sub-items).

---

## E.1 Capability checklist

Nine demo-facing capabilities per plan-v3 §E.1. Each row itemizes
existing coverage, net-new effort, coverage status, and build-path
clarity.

Coverage-status vocabulary:

- **FULL** — all dependencies mapped and classified; no open
  technical questions
- **PARTIAL** — mapped but carries an open-question or
  verification-required flag
- **NEW** — zero existing coverage; net-new construction required

### E.1.1 Capability table

| # | Capability | Existing coverage | Net-new effort | Status |
|---|---|---|---|---|
| 1 | Tool Registry with packs | X1 + X2 + X22 | N2 schema + N3 ingest + N4 endpoints + N15 shell + N16 Registry = ~11h | FULL |
| 2 | Pending Requests Inbox with approve/deny | X10 + X11 | N7 lifecycle endpoints + N15 shell + N17 Inbox = ~6.5h | FULL |
| 3 | Health/Stats bar | X11 + X22 | N18 bar + N19 token-win + partial N4 aggregation = ~3h | PARTIAL (token-win) |
| 4 | Claude Code calls `POST /recommend` | X3 + X4 + X6 + X7 + X15 | N5 + N6 + N10 + N11 `concierge_recommend` = ~11h | FULL |
| 5 | Claude Code loads MCP server mid-session | (none — X12 RETIRE) | N9 spike + N10 shim + N13 spawn/teardown = ~6.5h | PARTIAL (spike) |
| 6 | Lightweight-first preference in recs | embedded in X3 + X7 | absorbed in N6 = 0 additional | FULL (verify in fixtures) |
| 7 | Discovery produces tool suggestion | X6 tool-discovery SKILL | absorbed in N6 = 0 additional | FULL (verify with fixtures) |
| 8 | Approval triggers autonomous install | X13 install functions | X13 Python extract + N7 approve-action wiring = ~1h | FULL (Cut 2 deferrable) |
| 9 | Cron picks up status change | X11 outbox-housekeeping.sh | X11 verify + doc only = 0.5h | FULL |

**Capability tally:** 7 FULL, 2 PARTIAL, 0 NEW.

The "0 NEW" count is notable: **every demo capability has at least
some existing coverage.** The two PARTIAL markers flag verification-
required edges, not missing foundations.

### E.1.2 Per-capability build path and verification

#### Capability 1 — Tool Registry rendering with packs

**Data source chain:** X1 (TOOL-MANIFEST.md) + X2 (TOOL-CATALOG.md)
land in the SQLite store via N3 ingest; N4 `GET /tools` and
`GET /packs` serve the hierarchical response; N16 renders expandable
pack rows with per-tool rows underneath. X22 openclaw.json is read
into the active-state column, producing the manifest-vs-active
dormant-badge affordance (Q3 decision, 2026-04-20).

**Net-new effort:** 11h (distributed across Days 1 and 4).
**Verification:** fixtures created Day 0-1 include at least two
packs with multiple sub-tools; Day 4 `curl GET /tools` returns a
structured pack+tool JSON; UI render visually distinguishes
loaded/dormant/pending states.

**Build-path notes:** pack relation needs explicit modeling in N2
schema (one-to-many: packs → tools). This is a standard SQLAlchemy
pattern; no open question. The dormant-badge depends on X22 parse
being wired into N16's template — already in the dependency graph.

#### Capability 2 — Pending Requests Inbox with approve/deny

**Data source chain:** N7 lifecycle endpoints wrap X10 three-folder
layout. `GET /requests/pending` scans `pending/`, parses the
markdown per the X10 schema (§C.2.2 row 10), returns structured
JSON. `POST /requests/{id}/status` updates the status line in the
markdown file; the next cron cycle (X11) moves the file. N17
renders one card per request with HTMX approve/deny/defer buttons
hitting the status endpoint.

**Net-new effort:** 6.5h.
**Verification:** smoke test writes a fixture request, `GET`s it,
`POST`s status, confirms cron moves the file within the next
hourly cycle (or verify with a faster cron interval during
development).

**Build-path notes:** the markdown parser (~50 LOC per B.3) is the
piece that most often breaks in ways Day 4 UI will surface late.
Phase D risk #4 is addressed by moving a round-trip write/parse
check into Day 2 N8 smoke tests — call this out for Phase F's
Day 2 checkpoint criteria.

#### Capability 3 — Health/Stats bar — PARTIAL

**Data source chain:** N18 renders four tiles (or three after
Cut 1):

- Token-win counter ← N19 new instrumentation ← N5 memory events
  tagged `token-win`
- Active-MCP-count ← N4 catalog `GET /tools?state=active` + X22
  openclaw.json parse for current-load counts
- Cron heartbeat ← X11 `housekeeping.log` heartbeat line
- Top-3 most-used tools ← N5 memory aggregation (Cut 1 candidate)

**Net-new effort:** 3h.
**PARTIAL flag reason:** token-win instrumentation (N19) is net-new
per SESSION-2026-04-20-01 — no existing component emits token-win
events. The ~1h heuristic-precision budget per Q3 (confirmed
2026-04-21) is the entirety of the design: log
`{tool: <name>, baseline_tokens: N, used_tokens: M, delta: N-M}`
per recommendation execution; the bar aggregates `SUM(delta)` for
the week.

**Build-path notes:** rough heuristic uses constants (400 tokens
per MCP tool definition, 20 tokens per CLI command) rather than
real measurement. Demo shows the counter rising during the
lightweight-substitute moment; precision is cosmetic. If N19 cuts
via scope pressure, the Health/Stats bar loses a pitch-critical
tile — this is Level-3 escalation territory, not ladder-deferrable.

#### Capability 4 — Claude Code calls `POST /recommend`

**Data source chain:** Claude Code session talks to N10 stdio proxy
shim; shim exposes N11 `concierge_recommend` meta-tool; meta-tool
forwards task context to N6 `POST /recommend`; N6 composes a
system prompt from X3 + X4 + X6 + X7 (prompt-fragment extracts per
DECISIONS 2026-04-21 05:50), calls Opus 4.7 with task + catalog
(from N4) + memory (from N5), returns ranked recommendations;
shim passes the result back to Claude Code as the meta-tool's
output.

**Net-new effort:** 11h.
**Verification:** Day 3 eve N14 integration smoke runs a fixture
task ("analyze a CSV") end-to-end through the stack; expected
output ranks csvkit + csvstat above pandas.

**Build-path notes:** the 27.5h critical path runs through this
capability's chain (D.2.1). Any slip here cascades to Day 4.

#### Capability 5 — Claude Code loads MCP server mid-session — PARTIAL

**Data source chain:** the stdio proxy shim (N10) sits between
Claude Code and the backing MCP servers; when the approve-action
marks a tool `installed`, N13 spawn/teardown spawns a new backing
process and re-advertises its tools through the shim's
`tools/list_changed` notification (or re-registers via whichever
mechanism the N9 spike confirms).

**Net-new effort:** 6.5h.
**PARTIAL flag reason:** the N9 spike outcome branches the
architecture. If `tools/list_changed` works in-session in Claude
Code, Approach 1 is viable as primary and trims N10 by up to 4h.
If not, Approach 2 is primary per current plan, and N10 ships
~4h as budgeted. Either path has clear coverage; the
**unknown-at-Phase-C** aspect is the spike outcome itself.

**Build-path notes:** the spike is time-boxed at 0.5h per
classification.md §C.3.1 row. Phase F must open Day 3 with the
spike and commit to one approach before the 4h shim work begins.
Fallback tertiary is X16 mcporter ephemeral-spawn for one-off or
low-frequency tools.

#### Capability 6 — Lightweight-first preference in recommendations

**Data source chain:** X3 tool-awareness.md contains the
lightweight-first guidance language; X7 tool-lifecycle.md codifies
the promotion/demotion pattern that operationalizes "lightweight
earns its place." Both fragments compose into N6's system prompt;
Opus 4.7 applies the preference when ranking.

**Net-new effort:** 0 additional beyond what N6 already counts.
**Verification:** fixture scenario "process a CSV" with both
pandas and csvstat present — expected output puts csvstat higher.

**Build-path notes:** this is pure prompt-fragment behavior. The
D.5 risk #1 (prompt-fragment correctness) applies directly — first-
attempt fragment translation may not produce the expected ranking.
Mitigation: Day 2 N8 smoke tests include a fixture-driven
recommendation that asserts csvstat > pandas, and the test failure
becomes the feedback signal for fragment tuning.

#### Capability 7 — Discovery produces a tool suggestion

**Data source chain:** X6 tool-discovery SKILL.md contains the
search-patterns-by-domain + green/yellow/red signal table; these
compose into N6's system prompt under a "when nothing in catalog
matches, propose from discovery" directive. Opus 4.7 applies the
signal table to candidate packages (from its own knowledge of the
npm / pip / GitHub ecosystem) and emits a recommendation with
`source: discovery` in the result payload. The recommendation flows
into `outbox/tool-requests/pending/` via `concierge_request_tool`
(N11 meta-tool, path 2 in the demo narrative — not the approved-
auto-install path).

**Net-new effort:** 0 additional beyond N6.
**Verification:** fixture scenario "analyze a CSV" with csvkit
**absent** from the catalog — expected output proposes csvkit
from discovery, writes a pending request that the UI renders on
Day 4.

**Build-path notes:** discovery relies on Opus 4.7's knowledge of
the tool ecosystem; we're explicitly not crawling registries on
demo day. This is demo-scoped heuristic, not a long-running
discovery crawler — per DECISIONS 2026-04-21 05:50 reasoning
(pure-Python EXTRACT would have required a crawler subsystem,
rejected). The risk is Opus 4.7 proposing something odd for the
fixture scenario; mitigation is scenario tuning in Phase F.

#### Capability 8 — Approval triggers autonomous install

**Data source chain:** N7 `POST /requests/{id}/status` with
`status: approved` writes the status line; a helper hook (inside
N7 or a small post-approve handler) invokes
`core.install.install_npm_global(name)` or `install_pip_user(name)`
or `install_single_binary(url, dest)` based on the request's
`install_method` field. On success the status moves to `installed`;
failure moves to `failed` with stderr captured.

**Net-new effort:** 1h (X13 Python extract) — deferrable as Cut 2.
**Verification:** fixture request with `install_method: npm-global`
triggers an actual `npm install -g csvkit` call in a controlled
environment.

**Build-path notes:** Cut 2 in the §C.4.4 ladder defers this to a
manual install command shown in terminal during the demo, with
voiceover ("and in the real thing the cron picks this up and runs
the install automatically"). The demo narrative absorbs the Cut
cleanly — the "watch cron pick it up" moment still works because
X11 cron is LIFTed untouched.

#### Capability 9 — Cron picks up status change

**Data source chain:** X11 outbox-housekeeping.sh (LIFT, 52 LOC,
already running hourly) reads every file in `pending/`, reads
its status-line field, moves non-pending files to `resolved/`,
archives resolved files after 30 days, and writes heartbeat lines
to `housekeeping.log`. Zero modifications needed.

**Net-new effort:** 0.5h (X11 verify crontab + doc heartbeat
path for N18).
**Verification:** write a fixture with `status: approved`, wait
one cron cycle (or trigger manually with `bash
outbox-housekeeping.sh`), confirm file moves to `resolved/`.

**Build-path notes:** most LIFTable capability in the demo. Zero
risk beyond "is the crontab entry actually installed on the demo
machine" — X11's 0.5h estimate covers verifying and documenting.

---

## E.2 Top 5 risks for build week

Risks are ordered by expected loss (probability × impact), not by
likelihood alone. Each carries a mitigation aligned to Phase F's
build plan.

### E.2.1 Risk 1 — Prompt-fragment correctness on first integration

**What could go wrong:** X3 + X4 + X6 + X7 fragment extracts compose
into N6's system prompt on Day 2. First-attempt transcription from
markdown to Python string constants may drop formatting that Opus
4.7 reads as load-bearing (numbered lists, table separators,
signal-table columns), producing recommendations that miss the
lightweight-first preference or rank poorly against fixtures.

**Probability:** High. First-attempt prompt extractions are rarely
correct out of the gate; the signal-table markdown in X6 tool-
discovery is especially format-sensitive.

**Impact:** High. This is the first integration load-bearing
moment (D.5 risk #1) and affects capabilities 4, 6, 7 — more than
half the demo story.

**Mitigation:**

1. Day 2 N8 smoke tests include **fixture-driven recommendation
   assertions**, not just endpoint liveness. Sample fixture
   ("analyze a CSV" with csvkit + pandas in catalog) asserts
   `csvstat` ranks above `pandas.read_csv`. Test failure is the
   feedback signal for fragment tuning.
2. First fragment paste is followed by a manual Opus 4.7 test-run
   before committing the constant — confirm the model reads the
   prompt the way the markdown intends.
3. The per-constant header-comment provenance (DECISIONS
   2026-04-21 05:50 structural mitigation) preserves the source
   byte-range for rapid re-transcription if the first paste is
   wrong.

### E.2.2 Risk 2 — Stdio proxy shim debugging under time pressure

**What could go wrong:** N10 stdio proxy shim is ~300 LOC of
net-new code implementing JSON-RPC 2.0 message routing, stdio
read/write pumping, backing-process lifecycle, and the
`tools/list_changed` or re-registration branch from N9's spike.
MCP protocol nuances (request-id collisions between multi-backing-
server responses, stdin/stdout buffer flushing, process-death
cleanup) bite first-time implementers.

**Probability:** Medium-high. Lewie has not built a proxy shim
before; no reference implementation in `_legacy/` that matches
the shape (mcporter is per-call ephemeral, not a persistent multi-
backing proxy).

**Impact:** High. Capability 5 is gated entirely on N10 — without
it, Claude Code has no way to hot-swap tools and the demo's "watch
csvkit become available" moment dies.

**Mitigation:**

1. N9 verification spike first on Day 3 morning. If
   `tools/list_changed` works, Approach 1 shortcuts the shim.
2. Fallback path: Approach 3 (mcporter ephemeral spawn) can demo
   the "tool appears" narrative at lower fidelity without the
   shim. Not the pitch version, but a working version.
3. Day 3 afternoon N14 integration smoke is the latest-possible
   moment to discover shim bugs; if they surface there, Day 5-6
   buffer absorbs rework (loses polish time, preserves demo).

### E.2.3 Risk 3 — Day 3 serial-tail cascade eating Day 4 budget

**What could go wrong:** Day 3's N9 → N10 → N11 → N12 → N14 chain
is 11.5h of critical-path work in an 8-10h day. Even with the N10
pull-forward into Day 2 evening (Phase F carry-forward from
Phase D signoff), the N11 → N12 → N14 tail is ~7h of serial work
that cannot start until N10 lands. A Day 2 that runs on time but
doesn't finish evening pull-forward leaves Day 3 tight.

**Probability:** Medium-high. Day 3 is already flagged in
classification.md §C.4.5 and dependency-graph.md §D.5 as
over-budget. Under observed hackathon conditions (solo builder,
first-time adapter work, debugging surfaces late), 11.5h of
critical path in one day is aggressive.

**Impact:** Medium. Slippage into Day 4 morning directly competes
with N15/N16 Tool Registry build; Day 4 three-branch structure
gets squeezed. Demo is still deliverable because Day 5-6 buffer
exists, but polish time erodes.

**Mitigation:**

1. Phase F builds the Day 2 evening pull-forward of N10 as the
   **default plan**, not a contingency. Day 2 finishes ~5 PM,
   N10 starts ~6 PM, completes ~10 PM, Day 3 morning opens with
   shim already-built and focus goes directly to N11.
2. Ladder Cut 3 (`concierge_list_active` meta-tool deferral,
   ~1h saved from N11) is the first day-of trigger if Day 3 runs
   long.
3. Day 5 buffer is reserved for demo-scenario rehearsal per ops
   protocol — slipping bug-fix work from Day 4 → Day 5 is the
   intended graceful-degradation path.

### E.2.4 Risk 4 — Opus 4.7 recommendation quality variance

**What could go wrong:** The demo narrative depends on Opus 4.7
producing consistent-enough recommendations across demo runs:
csvstat ranks above pandas, csvkit is proposed from discovery
when absent, token-win delta shows the lightweight preference.
Model sampling variance could produce occasional misranks in
live-demo conditions (judges watching, network latency included).

**Probability:** Medium. Opus 4.7 is capable and prompt-steerable,
but any LLM on any given call can emit a weird output. Five
consecutive clean demo runs per Day 5's checkpoint criteria is
the right bar but not trivially achievable.

**Impact:** High. The demo scenario is written around specific
rankings (§Demo scenario in blueprint-v2); a misrank live on
recording breaks the narrative.

**Mitigation:**

1. **Temperature control** on N6's Opus call — set `temperature:
   0` for demo runs to eliminate sampling variance at the cost
   of output fluidity.
2. **Fixture-driven recommendation assertions** in N8 smoke tests
   (shared mitigation with Risk 1) catch variance during
   development, not on recording day.
3. **Demo-scenario rehearsal** per Day 5's checkpoint (5
   consecutive clean runs) is calibrated around this risk — any
   misrank in rehearsal triggers prompt-fragment tuning or
   prompt-level directive strengthening before recording.
4. Demo recording has multiple takes per Day 6 §F.3 skeleton —
   fastest recovery if a live run diverges.

### E.2.5 Risk 5 — Markdown round-trip parser correctness surfacing late

**What could go wrong:** N7's markdown parser for
`outbox/tool-requests/` reads the structured request template,
updates the status line, writes back. Format edge cases (trailing
whitespace after status value, YAML-ish metadata blocks if present,
line-ending differences between Linux/WSL/Windows file sources)
could produce parser failures that surface first in Day 4 UI —
Inbox renders empty or wrong — rather than in Day 2 smoke tests.

**Probability:** Medium. The schema is simple (per X10
classification); parser failures on simple schemas are usually
edge-case-driven rather than core-design-driven.

**Impact:** Medium-high. Capability 2 (Pending Requests Inbox)
gates on it; discovery of a parser bug in the Day 4 Inbox
session eats 1-2h of UI time for what is a Day 2 issue.

**Mitigation:**

1. Day 2 N8 smoke tests include a **round-trip write/parse
   check**, not just `GET /requests/pending` liveness. Write a
   fixture request, POST a status update, re-GET, confirm status
   field reflects the update. This catches parser bugs on Day 2,
   well before UI.
2. Fixtures cover the request-template variants seen in
   `_legacy/tool-requests/` (inspect actual pending/ folder state
   during Day 0-1 fixture creation to capture real-world format).
3. Parser failures are expected to be localized fixes (usually
   one-line regex or strip-whitespace adjustments) rather than
   architectural rework.

### E.2.6 Risks considered but not top 5

Candidates that didn't make the cut, briefly:

- **N9 spike ambiguity** — flagged in dependency-graph.md §D.5 #2,
  but the 0.5h time-box and commit-to-Approach-2-if-ambiguous
  fallback bound the impact. Rolls into Risk 2.
- **Day 4 three-branch solo-builder context-switching** — flagged
  in §D.5 #5 and addressed by Phase D signoff's
  parallelism-realism carry-forward to Phase F. Not a top-5 risk
  because Phase F's sequential Day 4 session structure absorbs it.
- **Manifest vs active-config drift surprising us** — Q3 decision
  (2026-04-20) reframes this as a UI feature, not a risk.
- **Hackathon-week clock slip from generic underestimate** — rolls
  into Risk 3; the yellow-flag 46.5h with 4-cut ladder already
  addresses.
- **Cron not running on demo machine** — bounded by X11 verify
  step; would be caught by Day 2 fixture smoke test.
- **Claude Code CLI version incompatibility with MCP surface** —
  real risk but mitigated by mcporter ephemeral-spawn fallback
  (Capability 5 mitigation #3) and generally not observed in
  recent Claude Code builds.

---

## E.3 Demo-capability coverage summary

Condensing E.1 into the format plan-v3 §E.3 specifies:

**7 FULL / 2 PARTIAL / 0 NEW (uncovered).**

The two PARTIAL capabilities (token-win instrumentation in #3;
N9 spike outcome in #5) are **verification-required**, not
**missing-foundation**. Every demo capability has at least some
existing coverage; the hackathon work is extraction + integration
+ UI-facing wrap, not net-new invention.

This aligns with the blueprint-v2 framing: "This is significantly
more achievable than the v1 framing suggested." Phase E confirms
it empirically.

---

## E.4 Questions for Lewie

No material blockers surfaced. Two procedural confirmations:

**Q1 (verification assertions in N8 smoke tests):** Risk 1 and
Risk 5 mitigations both route through expanding N8 smoke tests
beyond endpoint-liveness checks to include fixture-driven
recommendation assertions (Risk 1) and round-trip markdown parse
checks (Risk 5). This expands N8's 0.5h budget in §C.3.2 to
roughly 1.0-1.5h. Accept the expansion, or keep N8 at 0.5h and
carry the assertions as a Day 5 stabilization item?

My lean: **expand to ~1.0-1.5h on Day 2 evening.** Catching
fragment-correctness and parser bugs on Day 2 rather than Day 4-5
is high-leverage; the extra 0.5-1.0h on Day 2 buys significantly
more than that elsewhere in the week.

**Q2 (temperature=0 for recommendation calls):** Risk 4 mitigation
is setting N6's Opus 4.7 call to `temperature: 0` for demo runs.
Confirm this is acceptable — output fluidity drops slightly
(recommendations read more mechanically) in exchange for
recording-safe consistency.

My lean: **yes, temperature=0 for demo runs.** Use a higher
temperature during development/fixture-tuning if it helps Opus
4.7 find better-phrased recommendations, but lock at 0 for
demo-recording day.

---

## E.5 Carry-forward notes for Phase F

**For Phase F (Build Plan):**

1. **Day 2 N8 smoke-test expansion** (Q1 answer): bump ~0.5h
   additional on Day 2 evening; fixture-driven recommendation
   assertion (csvstat > pandas) + round-trip markdown parse check.
2. **Day 2 evening N10 pull-forward** remains the default plan,
   not a contingency (already logged in DECISIONS 2026-04-21
   06:10).
3. **Day 3 morning starts with N9 spike** (0.5h time-box, commit
   to Approach 2 if ambiguous).
4. **Day 5 rehearsal — 5 clean runs** per ops protocol is calibrated
   around Risk 4. Any misrank in rehearsal triggers prompt-fragment
   tuning before recording.
5. **Day 6 multiple takes** for demo recording — Risk 4 mitigation
   #4.
6. **temperature=0** on N6's Opus call for demo runs (Q2 answer).
7. **Ladder Cut 3 is the first day-of trigger if Day 3 runs long**
   (Risk 3 mitigation #2).
8. **Fixture inventory** for Day 0-1 should cover: csvkit-absent
   discovery scenario; csvstat-vs-pandas ranking scenario; request
   template format variants observed in actual `_legacy/tool-
   requests/` pending/ folder.
9. **Day 2 parallelism realism** — Phase D signoff carry-forward
   already logged; Day 2 N5 memory wrapper and prompt-fragment
   extracts should appear as **sequential blocks** in the Phase F
   day plan, not nominally-parallel claims.
10. **Day 4 three-branch realism** — same principle; sequential
    focus on N16 → N17 → N18/N19 rather than parallel claims.

---

## E.6 Summary for chat

Proposed summary for Lewie (pre-checkpoint):

**Coverage:** 7 FULL + 2 PARTIAL + 0 NEW across nine demo
capabilities. Every capability has existing coverage; the two
PARTIALs (token-win instrumentation, N9 spike outcome) are
verification-required rather than missing-foundation. This
empirically confirms blueprint-v2's "more achievable than v1
framed" posture.

**Top 5 risks, ranked by expected loss:**

1. Prompt-fragment correctness on first integration (P:high /
   I:high) — demo-critical, affects capabilities 4, 6, 7
2. Stdio proxy shim debugging (P:medium-high / I:high) — never
   done before, gates capability 5
3. Day 3 serial-tail cascade eating Day 4 (P:medium-high /
   I:medium) — schedule risk, ladder absorbs
4. Opus 4.7 recommendation quality variance (P:medium / I:high) —
   demo-recording risk, temperature=0 + rehearsal absorb
5. Markdown round-trip parser surfacing late (P:medium / I:
   medium-high) — Day 2 smoke-test expansion catches early

**Key mitigations converge on four Phase F adjustments:**

- Day 2 N8 smoke tests expanded from 0.5h to ~1.0-1.5h
  (fixture-driven recommendation + round-trip parse checks) —
  catches Risks 1 and 5 early
- Day 2 evening N10 pull-forward as default (already carried
  forward)
- Day 3 opens with N9 spike (already planned)
- temperature=0 + Day 5 rehearsal + Day 6 multiple takes — absorb
  Risk 4

**Two procedural confirmations in §E.4** — N8 smoke-test expansion
(Q1) and temperature=0 for demo runs (Q2). My lean on both is yes.

---

## E.7 Phase E checkpoint

Per plan-v3 §Phase E checkpoint:

- [x] `planning/gap-analysis.md` exists
- [x] Every demo capability has clear coverage status (§E.1.1 —
      7 FULL + 2 PARTIAL + 0 NEW)
- [x] Top 5 risks documented (§E.2 with P/I ratings and mitigations)

Additional items for phase-gate traceability:

- [x] Per-capability build path and verification steps (§E.1.2)
- [x] Mitigation → Phase F build-plan carry-forward (§E.5)
- [x] Phase F capstone inputs captured (ten items in §E.5)
- [ ] Lewie has reviewed and signed off on Phase E

---

*Phase E deliverable complete pending Lewie's review. Phase F —
Build Plan is the capstone document and per plan-v3 §F runs at
`max` effort; recommended to run Phase F as its own fresh session
rather than continuing today.*
