# Concierge — Phase C (Classification)

*Deliverable of Phase C per `docs/concierge-claude-code-plan-v3.md`.*
*Session:* `SESSION-2026-04-21-02` (morning alignment was Session 01).
*Generated:* 2026-04-21.
*Effort:* `xhigh` (adjusted from `max` per 2026-04-21 08:15 decision —
see DECISIONS.md).

Every existing Concierge component inventoried in Phase A receives
**exactly one** classification here, with 2-4 sentence justification,
hackathon-week effort estimate, target build day, and reversibility
rating. The three genuinely-new items (Claude Code adapter, FastAPI
core, UI) are sized in §C.3 and roll into the grand-total sanity check
in §C.4. Phase C's checkpoint is §C.9; summary-for-chat is §C.8.

---

## C.1 Classification options (restated)

Per `docs/concierge-claude-code-plan-v3.md` §C.1:

- **LIFT** — use as-is, point at it from new structure; zero
  modification to the original file
- **EXTRACT** — pull platform-agnostic core into `core/`, leave OpenClaw
  wrapping in `_legacy/`; original stays untouched
- **ADAPT** — needs modification to fit new architecture; original file
  changes in place
- **REWRITE** — too tangled or different; faster to redo; should be
  rare, and every instance must explain why it is not EXTRACT or ADAPT
- **RETIRE** — not needed in new architecture; includes scope-excluded
  components present in `_legacy/` but never in Concierge's perimeter

Phase C decision hygiene (plan-v3 §C.3):

- Every **LIFT** carries a "prove not secretly coupled" note
- Every **REWRITE** carries a "why not EXTRACT or ADAPT" note
- Every **RETIRE** scope-exclusion gets flagged as such so future
  sessions don't mistake it for "retired after use"

Effort flags per 2026-04-21 morning confirmation:

- Yellow at ≥40h total non-RETIRE effort (triggers check-in before
  committing)
- Red at ≥50h (hard-alert, propose scope cut per plan-v3 §C.3)

Duplicate-handling convention per 2026-04-21 morning confirmation:

- Canonical path receives the full classification row
- Byte-identical draft copies get "draft copy, see canonical — same
  classification" notation (§C.2.3 annex table)

Reversibility field per 2026-04-21 morning confirmation:

- **Easy** — reclassifying mid-build week costs ≤1 day of rework
- **Hard** — reclassifying costs multiple days
- **Permanent** — reclassifying is not recoverable within hackathon
  week

---

## C.2 Per-component classification

### C.2.1 Summary table

24 canonical components. Single classification each.

| # | Component | Path | Classification | Effort | Day | Reversibility |
|---|---|---|---|---|---|---|
| 1 | TOOL-MANIFEST.md | `_legacy/agent-skills/shared/TOOL-MANIFEST.md` | **EXTRACT** | 1.5h (shared ingest) | Day 1 | Easy |
| 2 | TOOL-CATALOG.md | `_legacy/satiety-docs/TOOL-CATALOG.md` | **EXTRACT** | 1.5h (shared ingest) | Day 1 | Easy |
| 3 | tool-awareness.md | `_legacy/agent-skills/shared/tool-awareness.md` | **EXTRACT** | 0.5h | Day 2 | Easy |
| 4 | tool-recommendation.md | `_legacy/agent-skills/shared/tool-recommendation.md` | **EXTRACT** | 0.5h | Day 2 | Easy |
| 5 | tool-concierge-intro.md | `_legacy/agent-skills/shared/tool-concierge-intro.md` | **LIFT** | 0h | Day 0 (reference) | Easy |
| 6 | tool-discovery SKILL.md | `_legacy/openclaw-workspace/skills/tool-discovery/SKILL.md` | **EXTRACT** | 1h | Day 2 | Easy |
| 7 | tool-lifecycle SKILL.md | `_legacy/openclaw-workspace/skills/tool-lifecycle/SKILL.md` | **EXTRACT** | 1h | Day 2 | Easy |
| 8 | SOUL.md root (delta) | `_legacy/openclaw-root/SOUL.md` | **EXTRACT** | 0.5h | Day 3 | Easy |
| 9 | SOUL.md workspace (integrated) | `_legacy/openclaw-workspace/SOUL.md` | **LIFT** | 0h | — | Easy |
| 10 | tool-requests/ layout + README.md schema | `_legacy/tool-requests/` + `_legacy/tool-requests/README.md` | **LIFT** | 0h (reuse as-is) | Day 2 (API wraps) | Easy |
| 11 | outbox-housekeeping.sh | `_legacy/satiety-docs/scripts/outbox-housekeeping.sh` | **LIFT** | 0.5h (verify + doc) | Day 2 | Easy |
| 12 | tool-functions.sh: tool-on/tool-off | `_legacy/satiety-docs/scripts/tool-functions.sh` (functions) | **RETIRE** | 0h | — | Easy |
| 13 | tool-functions.sh: tool-install-npm/pip | same file, install functions | **EXTRACT** | 1h | Day 3 | Easy |
| 14 | tool-wishlist.md | `_legacy/openclaw-root/logs/tool-wishlist.md` | **LIFT** | 0h | — | Easy |
| 15 | moltbot-memory-mcp (server + run.sh + store) | `_legacy/moltbot-memory-mcp/` + `/home/satiety/.moltbot-memory-v2/` | **LIFT** | 0h (wrapper in new-build) | Day 2 (wrapper) | Easy |
| 16 | mcporter | `/home/satiety/.npm-global/bin/mcporter` v0.7.3 | **LIFT** | 0h | Day 3 (optional invoke) | Easy |
| 17 | MCP-BRIDGE-GUIDE.md | `_legacy/openclaw-workspace/docs/MCP-BRIDGE-GUIDE.md` | **RETIRE** | 0h | — | Easy |
| 18 | ALFRED-MCP-REFERENCE.md | `_legacy/openclaw-workspace/docs/ALFRED-MCP-REFERENCE.md` | **RETIRE** | 0h | — | Easy |
| 19 | TOOL-CONCIERGE-OVERVIEW.md | `_legacy/toolconcierge/TOOL-CONCIERGE-OVERVIEW.md` | **LIFT** | 0h | — | Easy |
| 20 | worker-tool-escalation.md | `_legacy/toolconcierge/worker-tool-escalation.md` | **LIFT** | 0h | — | Easy |
| 21 | phase-2-test-scenarios.md | `_legacy/toolconcierge/phase-2-test-scenarios.md` (also `satiety-docs/test-scenarios/phase-2.md`) | **LIFT** | 0h | Day 0 (fixtures) | Easy |
| 22 | openclaw.json (active config) | `_legacy/openclaw-root/openclaw.json` | **LIFT** | 0h | Day 1 (parse) | Easy |
| 23 | OpenClaw AT-time scheduler | `_legacy/openclaw-root/cron/jobs.json` + `cron/runs/*.jsonl` | **RETIRE** (scope-excluded) | 0h | — | Easy |
| 24 | OpenClaw internal SQLite | `_legacy/openclaw-root/memory/main.sqlite` | **RETIRE** (scope-excluded) | 0h | — | Easy |

**Classification tally:** 12 LIFT, 7 EXTRACT, 0 ADAPT, 0 REWRITE, 5
RETIRE (of which 2 are scope-excluded rather than deprecated).

**Non-RETIRE effort subtotal (existing components):** 7.5h — see §C.4
for the full audit.

### C.2.2 Per-component justifications

#### 1. TOOL-MANIFEST.md — **EXTRACT** — 1.5h (shared with #2) — Day 1 — Easy

The manifest's schema (per-agent capability rows, MCP servers + tool
counts, transport types, install methods, API-key status, BUILDABLE
list) is the shape Concierge's SQLite catalog needs to represent.
Content is OpenClaw-fleet-specific (Alfred/Scout/Bridge agent IDs,
`openclaw --profile` CLI form as normative usage) but the structure
generalizes directly. The Day-1 ingest pass reads TOOL-MANIFEST.md +
TOOL-CATALOG.md + `openclaw.json` in a single operation and seeds the
SQLite store; the original markdown file is untouched and continues
serving OpenClaw. **Why not LIFT:** v2 blueprint explicitly wants a
SQLite catalog that any harness can query; a single operator markdown
file doesn't serve that requirement. **Why not ADAPT:** the original
file isn't modified — Concierge extracts its content; the file keeps
doing its OpenClaw job unchanged.

#### 2. TOOL-CATALOG.md — **EXTRACT** — 1.5h (shared with #1) — Day 1 — Easy

Same shape as #1: the catalog's CLI-tools + MCP-servers + paid-services
+ candidate-pool tables become SQLite rows. `satiety-docs/` is
canonical (Apr-14 version has promoted five tools into "Installed" per
§A.2.6); `toolconcierge/TOOL-CATALOG.md` is the day-older draft copy
and inherits this classification via the §C.2.3 annex. Ingest pass is
the same single Day-1 operation as #1 — the 1.5h is a shared estimate,
not additive. **Why not LIFT:** single-operator markdown without
schema enforcement can't feed a UI that filters by pack, state, or
transport. **Why not ADAPT:** the original isn't modified.

#### 3. tool-awareness.md — **EXTRACT** — 0.5h — Day 2 — Easy

The 5-step protocol (Task Decomposition → Manifest Check → Gap Report
→ Execute → Log to Wishlist) is the pre-execution pattern Concierge's
`POST /recommend` endpoint wants to reason through when handed task
context. Extract into the Opus-4.7 system prompt as a "how to analyze
a task" fragment. **Why not LIFT:** the file is consumed by OpenClaw
agents at skill-load time; Concierge needs its behavior as service-side
reasoning, not agent-side instruction. **Why not ADAPT:** OpenClaw
continues to use the file as-is; extraction is one-directional.

**Extraction-pattern note (applies to #3, #4, #6, #7, #8):** The
extraction physically lands as a Python string constant composed
into `POST /recommend`'s Opus 4.7 system prompt, **not** as
reimplemented Python logic. This is prompt-fragment composition, not
code lifting. The 2026-04-21 10:30 DECISIONS.md entry explains why
EXTRACT (vs. pure-Python EXTRACT or ADAPT) is the correct framing
and names the source-of-truth coupling risk + the structural
mitigations (header-comment provenance, verbose constant names,
SKILL_FRAGMENT_SYNC_LOG, Phase 2 automated-generation path). Every
row #3/#4/#6/#7/#8 inherits that DECISION entry.

#### 4. tool-recommendation.md — **EXTRACT** — 0.5h — Day 2 — Easy

Companion to #3. The 6-step "Notice → Check-before-proposing →
Continue → Write → Notify → Log" pattern governs during/after task
execution. Extract into the same Opus-4.7 system prompt used by
`POST /recommend`, specifically the "what to surface as a
recommendation result" section. **Why not LIFT:** same reasoning as
#3 — it's an agent-side skill; Concierge needs it as service-side
reasoning. **Why not ADAPT:** no modification to the original.

*Extraction-pattern note:* see row #3; same pattern.

#### 5. tool-concierge-intro.md — **LIFT** — 0h — Day 0 (reference material) — Easy

Orientation/onboarding prose (3,595 B). No behavior, no algorithm —
narrative context for agents meeting Concierge for the first time.
Referenced from Concierge docs via `_legacy/` link; continues serving
OpenClaw verbatim. **Prove LIFT isn't secretly coupled:** the file is
prose about what Concierge is and why; no OpenClaw-specific logic,
paths, or agent IDs embedded in its normative content. It would read
identically to a Claude Code user discovering Concierge for the first
time. **Why not EXTRACT:** nothing to extract — it's narrative, not
algorithm. **Why not RETIRE:** remains useful for new contributors and
for onboarding Phase 2 harnesses; drop cost is zero, retention cost is
zero.

#### 6. tool-discovery SKILL.md — **EXTRACT** — 1h — Day 2 — Easy

Per Phase B.4 resolution: this is the authoritative algorithm spec for
the Recommendation Engine's **discovery-engine subcomponent**. Content
(search patterns by domain — CLI / Python / Node / Rust / MCP / data
processing; green/yellow/red signal table for candidate filtering;
Source + Evidence fields in the discovery-request format) becomes
system-prompt text and threshold language inside `POST /recommend`
when the catalog and memory hits come up empty. **Why not LIFT:**
per B.4, the file is an algorithm spec, not a loadable skill inside
Concierge's architecture. **Why not ADAPT:** the original stays as-is
for OpenClaw; Concierge consumes it one-way.

*Extraction-pattern note:* see row #3; this is the demo-critical
instance of the pattern — the signal-table content is prompt-fragment
material, not reimplemented as a Python scoring function. 2026-04-21
10:30 DECISIONS.md entry explains why.

#### 7. tool-lifecycle SKILL.md — **EXTRACT** — 1h — Day 2 — Easy

Per Phase B.4 resolution: authoritative spec for the Lifecycle State
Machine. Content: (a) the `tool-selection` memory tag schema with
structured content string `TOOL: <name> | PATTERN: <p> | STATUS: <s>
| AGENT: <a> | DATE: <d> | NOTES: <n>` — this becomes a shared
constant between the Recommendation Engine and the Memory Service
wrapper; (b) promotion criteria (5+ uses / 30 days / recurring) and
demotion criteria (90+ days unused) — these become module-level
threshold constants; (c) weekly-review protocol — this becomes future
cron automation (Phase 2) or a manual operator action surfaced in the
UI. **Why not LIFT:** algorithm spec, not loadable skill (per B.4).
**Why not ADAPT:** original stays; extraction is one-way.

*Extraction-pattern note:* see row #3. The promotion/demotion
thresholds and the tag schema are the parts of this file that become
**Python constants** (genuine code — not prompt fragments); the
weekly-review protocol is the part that becomes prompt-fragment
guidance when operator-facing review surfaces are built. Partial-
hybrid within a single row.

#### 8. SOUL.md root (delta) — **EXTRACT** — 0.5h — Day 3 — Easy

The "Tool-Awareness Behavioral Rules — Append these to your existing
SOUL.md" delta file (3,291 B, 46 lines). Six sections: Capability
Honesty, Planning Discipline, Feedback and Learning, Requesting
Capabilities, Workaround Transparency, Tool Concierge. The Claude
Code adapter needs a SOUL-equivalent system-prompt fragment it sends
to a Claude Code session to make it Concierge-aware; this delta file
is the cleanest extraction point because it is **additions-only**
(pure behavioral rules, no OpenClaw-fleet framing). **Why not LIFT:**
Claude Code sessions aren't OpenClaw agents; the framing (which agent
to escalate to, which MCP namespace to use) needs substitution. **Why
not ADAPT:** the original delta file stays unchanged and continues
shaping OpenClaw's SOUL; the Claude Code version is a derived
fragment.

*Extraction-pattern note:* see row #3. This is the pure
prompt-fragment case — SOUL is inherently prompt content; no Python
logic is extractable from it.

#### 9. SOUL.md workspace (integrated) — **LIFT** — 0h — — — Easy

Alfred's full integrated SOUL file (9,714 B). OpenClaw-specific to the
bone (Core Truths for Alfred, Continuity section, explicit Worker
escalations). Not a useful extraction source — #8 is the cleaner
extraction point for Concierge's purposes, and this file's Tool
Concierge section is just a deployment of #8's content with OpenClaw
framing added. **Prove LIFT isn't secretly coupled:** Concierge
doesn't consume this file at all; it remains entirely within
OpenClaw's runtime. There's no coupling to prove innocent — it's
out-of-path. **Why not EXTRACT:** duplicates #8's content; extracting
twice is noise. **Why not RETIRE:** OpenClaw uses it continuously.

#### 10. tool-requests/ three-folder layout + README.md schema — **LIFT** — 0h (reuse); API endpoints are new-build — Day 2 (API wraps) — Easy

The three folders (`pending/`, `resolved/`, `archived/`) and the
schema spec (six-value status, filename convention, request template)
move into Concierge's architecture **unchanged**. Concierge's API
endpoints read from and write to the same filesystem; the existing
cron continues moving files. **Prove LIFT isn't secretly coupled:**
Phase A.2.4 explicitly verified — zero OpenClaw-specific fields in the
request template; status values (`pending | approved | denied |
installed | failed | deferred`) are platform-agnostic; only the
physical path (`~/.satiety-pipeline/...`) is Moltbot-specific and is
trivially relocatable via a config variable in the new service. The
pipeline's parent folder (`satiety-pipeline/`) houses content-pipeline
stages that are out-of-scope per 2026-04-20 decision — only the
`outbox/tool-requests/` subtree is LIFTed. **Why not EXTRACT:** the
schema and layout ARE the lifecycle implementation; there's no logic
to pull out into `core/`. **Why not ADAPT:** no modifications needed.

#### 11. outbox-housekeeping.sh — **LIFT** — 0.5h (verify crontab + document) — Day 2 — Easy

52-line bash script already running hourly via user crontab. Moves
files by status (non-pending → `resolved/`), archives resolved files
after 30 days, flags stale pending (≥7 days), writes heartbeats to
`housekeeping.log`. **Prove LIFT isn't secretly coupled:** Phase A.2.5
explicitly verified zero OpenClaw coupling — pure bash + coreutils
(`stat`, `date`, `grep -oP`, `mv`); only the `$HOME` path of the
outbox directory is configurable. 0.5h is for verifying the crontab
entry on the target machine and documenting the heartbeat-log
location in Concierge docs so the UI's Health-Stats bar knows where
to read. **Why not EXTRACT:** the script IS the implementation —
nothing to pull out. **Why not ADAPT:** no modifications needed.

#### 12. tool-functions.sh: tool-on/tool-off — **RETIRE** — 0h — — — Easy

The MCP load/unload mechanism for OpenClaw (edit `openclaw.json` with
`jq`, back up to `.bak`, `systemctl --user restart
openclaw-<profile>.service`, verify active). Fundamentally incompatible
with Claude Code sessions because a systemd service restart kills the
session's active conversational context. Per Phase A.2.11 + S8 finding:
"the whole point of the Claude Code adapter is swapping tools without
losing session context." The Claude Code adapter (new-build §C.3.1)
uses an entirely different mechanism (stdio proxy shim primary with
native `tools/list_changed` fallback). This component is retired
*from Concierge's perspective*; OpenClaw continues to use it (Phase 2
adapter work). **Why not REWRITE:** REWRITE implies Concierge needs
this specific functionality but the existing code is too tangled; here
Concierge needs a **different mechanism**, not a rewrite of the same
mechanism. **Why not ADAPT:** the same objection — no amount of
modification makes systemd-restart work for Claude Code sessions.

#### 13. tool-functions.sh: tool-install-npm/pip — **EXTRACT** — 1h — Day 3 — Easy

The autonomous-install logic: `npm install -g` to `~/.npm-global`
(no sudo) and `pip3 install --user` (no sudo). Both patterns are
platform-agnostic at their core — Claude Code's adapter needs to
trigger installs when a request is approved, and these two install
methods plus single-file-binary download cover the vast majority of
CLI and MCP server installations. Extract into a Python
`core/install.py` module exposing `install_npm_global(pkg)`,
`install_pip_user(pkg)`, `install_single_binary(url, dest)`.
**Why not LIFT:** the bash functions are entangled with tool-on/off
in the same file, and tool-on/off is RETIRE; clean separation
produces cleaner Concierge code. **Why not ADAPT:** the original bash
file continues serving OpenClaw; Python extraction is for the new
architecture.

#### 14. tool-wishlist.md — **LIFT** — 0h — — — Easy

Template-only file, zero real entries (Phase A.2.8 / S4 finding).
Concierge's backend can read the same file if agents ever write to
it; per Q5 decision (2026-04-20), the v1 UI does not render a
Wishlist section so there's no urgency on Day 1-4. **Prove LIFT
isn't secretly coupled:** the file is a markdown log with a documented
entry format (frequency + priority lines); no OpenClaw-specific
structure, no agent-specific fields. It would accept entries from
any harness in the same format. **Why not EXTRACT:** no behavior to
extract — it's a simple append log. **Why not RETIRE:** Phase 2's
Wishlist Patterns UI section needs this file to exist and be writable;
retiring it would block that future work.

#### 15. moltbot-memory-mcp (server.py + run.sh + ChromaDB store) — **LIFT** — 0h (server); wrapper is new-build — Day 2 (wrapper work) — Easy

14 KB Python FastMCP server with 8 tools (store / search / delete /
list / update + identity get/set + stats), ChromaDB backend,
`all-MiniLM-L6-v2` embeddings. Concierge imports server functions as
library calls from the FastAPI core (per Phase B.1 narrative); the
MCP server itself is unchanged and continues serving OpenClaw via
its stdio entry point. The thin wrapper that exposes memory to
non-MCP callers is new code, counted under §C.3.2 FastAPI core
service new-build. **Prove LIFT isn't secretly coupled:** Phase A.2.9
explicitly verified — zero OpenClaw-specific coupling in code; only
env var `MOLTBOT_MEMORY_DIR` is configurable; the server is generic.
Two ChromaDB collections (`memories`, `identity`) and six metadata
fields are all platform-agnostic. **Why not EXTRACT:** server is
already platform-agnostic — there's no OpenClaw wrapping to pull out.
**Why not ADAPT:** consuming via library import is not modification.

#### 16. mcporter — **LIFT** — 0h — Day 3 (optional invocation) — Easy

Third-party ad-hoc MCP caller at `/home/satiety/.npm-global/bin/mcporter`
v0.7.3. Per Phase B.2, serves as the tertiary approach in the Claude
Code adapter (per-call ephemeral spawn for low-frequency or one-off
tools from discovery). Used by invocation, not modification.
**Prove LIFT isn't secretly coupled:** third-party binary written by
someone else; zero Concierge or OpenClaw involvement in its
construction. **Why not EXTRACT:** not our code. **Why not RETIRE:**
its pattern is a legitimate tertiary adapter approach per Phase B.2.

#### 17. MCP-BRIDGE-GUIDE.md — **RETIRE** — 0h — — — Easy

Historical reference only (per Q2 decision, 2026-04-20). Describes a
TypeScript plugin at `_legacy/openclaw-root/extensions/mcp-bridge/`
that no longer exists on disk — the plugin files were removed during
the ~Apr 10 migration to native `mcp.servers`. The guide's conceptual
content (JSON-RPC 2.0 over stdio, tool discovery at startup,
`servername_toolname` routing) is re-derivable from the MCP protocol
spec itself; Concierge's stdio proxy shim in §C.3.1 reads the
protocol spec, not this guide. **Why not LIFT:** Concierge does not
consume this file in any capacity; having it in our architecture
would be architectural clutter. **Why not REWRITE:** we aren't
reimplementing the MCP Bridge plugin — Concierge's Claude Code
adapter is a different pattern (we are the MCP server, not a
plugin-inside-OpenClaw). The doc stays in `_legacy/` as historical
record; "RETIRE" here means "not part of Concierge."

#### 18. ALFRED-MCP-REFERENCE.md — **RETIRE** — 0h — — — Easy

Per-server tool reference, ~180 lines. Describes the 7 MCP servers
previously loaded for Alfred — all of which have been migrated or
dropped (per S3 / A.2.9 manifest-vs-active drift). Historical, not
authoritative. Same reasoning as #17: Concierge doesn't consume it;
active ground truth is `openclaw.json` (#22). **Why not LIFT:** not
consumed by Concierge; no value in retaining as live reference when
active config is authoritative. **Why not EXTRACT:** the relevant
information has already been superseded by `openclaw.json`'s active
state.

#### 19. TOOL-CONCIERGE-OVERVIEW.md — **LIFT** — 0h — — — Easy

10,618 B narrative document — richest single-file conceptual
description of Concierge (per CLAUDE.md v3's "richest reference"
pointer, confirmed in A.2.12). Referenced from Concierge's own docs
as the prose backbone for future contributors and for the Phase 2
roadmap. **Prove LIFT isn't secretly coupled:** the document is
prose-level description — it talks about Concierge's philosophy,
components, and design intent without hard-coding OpenClaw-specific
paths into load-bearing normative claims. A reader needs to know "we
currently run this inside OpenClaw" but doesn't need OpenClaw to
understand the concepts. **Why not EXTRACT:** narrative prose,
nothing to extract. **Why not RETIRE:** highest-value reference doc
in the inventory; drop would be a small but real loss.

#### 20. worker-tool-escalation.md — **LIFT** — 0h — — — Easy

Dual-channel pattern (real-time `sessions_send` + filesystem `worker-*`
prefix in `pending/`) for how OpenClaw worker agents escalate to
Alfred. Used by OpenClaw; not relevant to Concierge's single-session
Claude Code adapter. Stays in place for OpenClaw. **Prove LIFT isn't
secretly coupled:** the doc is documentation of OpenClaw's internal
communication pattern; Concierge reads it once for context (during
Phase 2 OpenClaw adapter work) and otherwise doesn't depend on it.
**Why not EXTRACT:** pattern is architecturally specific to
multi-worker OpenClaw; not generalizable to a single Claude Code
session. **Why not RETIRE:** OpenClaw uses it.

#### 21. phase-2-test-scenarios.md — **LIFT** — 0h — Day 0 (fixture source) — Easy

9,251 B test-scenarios document. Pre-dates v2 framing but per A.2.12
serves as demo-fixture source material for `planning/test-fixtures/`.
The fixture-creation step in Phase F (Day 0-1) cherry-picks scenarios
from this doc and normalizes them into the test-fixtures structure
specified by the ops protocol. **Prove LIFT isn't secretly coupled:**
the scenarios are task-level descriptions (e.g. "analyze a CSV");
they describe tasks, not infrastructure. No OpenClaw-specific paths
or agent IDs in the scenario descriptions themselves.
Byte-identical at two locations (`_legacy/toolconcierge/` and
`_legacy/satiety-docs/test-scenarios/phase-2.md`). **Why not
EXTRACT:** cherry-picking scenarios into fixtures is not extraction
of a platform-agnostic core — it's fixture creation, which is Phase
F work, not Phase C classification. **Why not RETIRE:** the scenarios
are the best starting point for demo fixtures we have.

#### 22. openclaw.json (active config) — **LIFT** — 0h — Day 1 (parse) — Easy

Active MCP-server and plugin configuration for OpenClaw. Concierge's
Tool Registry UI and Health-Stats bar parse this file to render the
"active" column and the manifest-vs-active delta (per Q3 decision:
surface the drift as a "consider reloading" affordance, not as a bug).
Concierge **never writes** to this file — that would break OpenClaw.
Phase 2's OpenClaw adapter may eventually do so; not in hackathon
week. **Prove LIFT isn't secretly coupled:** Concierge treats this
file as external-system state, not as its own config. The coupling
exists but is **inbound only** (we read OpenClaw's state), not
outbound (we don't write). That's a safe, bounded coupling.
**Why not EXTRACT:** not our file to own. **Why not RETIRE:** parsing
it is the concrete mechanism by which the UI's most demo-visible
stat (3-of-7 loaded) gets its data.

#### 23. OpenClaw AT-time scheduler (cron/jobs.json + runs/*.jsonl) — **RETIRE** (scope-excluded) — 0h — — — Easy

Per A.2.12 + A.2.5: one-off reminder jobs ("Client Meeting Reminder",
"Stripe key rotation reminder"). Scheduler payloads are `systemEvent`
types, unrelated to tool-request lifecycle. Listed in the inventory
for completeness and to prevent future confusion with
`outbox-housekeeping.sh` (#11) — the only actual cron job in
Concierge's scope. **RETIRE scope-exclusion flag:** this component was
never in Concierge's perimeter; it exists inside OpenClaw's runtime
and is documented here so future sessions don't mistake it for
Concierge infrastructure. **Why not LIFT:** entirely outside
Concierge's architecture. **Why not EXTRACT:** nothing to pull out
that belongs to Concierge.

#### 24. OpenClaw internal SQLite (memory/main.sqlite) — **RETIRE** (scope-excluded) — 0h — — — Easy

Per A.2.12: 610 KB internal task/session state DB for OpenClaw —
distinct from the semantic memory ChromaDB store (#15). Not the
Concierge SQLite catalog (which is new-build, clean-database). Listed
for completeness and to prevent conflation with Concierge's own
future SQLite file. **RETIRE scope-exclusion flag:** never in
Concierge's perimeter. **Why not LIFT / EXTRACT / ADAPT:** same
reasoning as #23 — this is OpenClaw's internal state storage, not
Concierge's.

### C.2.3 Duplicate / draft-copy rows (per option-ii convention)

Thirteen byte-identical or near-identical drafts inherit their
canonical row's classification. Listed here for inventory completeness
without double-counting effort.

| Draft copy path | Canonical (row #) | Inherited classification | Notes |
|---|---|---|---|
| `_legacy/toolconcierge/outbox-housekeeping.sh` | #11 | LIFT | Byte-identical; drafting snapshot of canonical at `satiety-docs/scripts/`. |
| `_legacy/toolconcierge/tool-functions.sh` | #12 + #13 | RETIRE (tool-on/off) + EXTRACT (install) | Byte-identical; splits the same way the canonical splits. |
| `_legacy/toolconcierge/TOOL-CATALOG.md` | #2 | EXTRACT | Apr-13 version; older than canonical by one audit cycle. |
| `_legacy/toolconcierge/skill-tool-concierge-intro.md` | #5 | LIFT | Byte-identical to fleet library version. |
| `_legacy/toolconcierge/skill-tool-recommendation.md` | #4 | EXTRACT | Byte-identical to fleet library version. |
| `_legacy/toolconcierge/skill-tool-discovery.md` | #6 | EXTRACT | Earlier variant (pre-workspace SKILL.md). |
| `_legacy/toolconcierge/skill-tool-lifecycle.md` | #7 | EXTRACT | Earlier variant (pre-workspace SKILL.md). |
| `_legacy/toolconcierge/SOUL-workspace.md` | #9 | LIFT | Snapshot of workspace version. |
| `_legacy/openclaw-root/skills/tool-awareness/SKILL.md` | #3 | EXTRACT | Byte-identical to fleet library; runtime-loaded copy. |
| `_legacy/openclaw-root/skills/tool-recommendation/SKILL.md` | #4 | EXTRACT | Byte-identical; runtime-loaded copy. |
| `_legacy/openclaw-root/skills/tool-concierge-intro/SKILL.md` | #5 | LIFT | Byte-identical; runtime-loaded copy. |
| `_legacy/openclaw-workspace/skills/tool-recommendation/SKILL.md` | #4 | EXTRACT | Byte-identical; workspace-loaded copy. |
| `_legacy/openclaw-workspace/skills/tool-concierge-intro/SKILL.md` | #5 | LIFT | Byte-identical; workspace-loaded copy. |

Per Q4 decision (2026-04-20), the `toolconcierge/` repo is preserved
as-is via symlink for hackathon week; post-hackathon consolidation is
Phase 2 scope. These duplicate rows do **not** add effort — they
inherit the effort estimate of the canonical row, which already
accounts for the content.

---

## C.3 New-build sizing

Three genuinely-new items per Phase B architecture-map. These are not
classifications (they weren't existing components); they are sized
estimates that roll into the §C.4 total.

### C.3.1 Claude Code adapter — ~14h — Day 3 (primary) + Day 2 afternoon pull-forward opportunity

Per Phase B.2: Approach 2 (stdio proxy shim) as primary mechanism,
with Approach 1 (native `tools/list_changed`) as fallback and
Approach 3 (mcporter-style per-call) as tertiary for low-frequency
tools. Four subcomponents (B.2) plus the proxy shim itself.

| Sub-item | Hours | Notes |
|---|---|---|
| Day-3-morning `tools/list_changed` verification spike | 0.5 | Per ops protocol carry-forward note. Determines whether Approach 1 is a viable primary (shortcut) or if we commit fully to Approach 2. |
| stdio proxy shim skeleton | 4.0 | ~300 LOC per B.2; JSON-RPC id mapping, stdio read/write pump, backing-server process management. |
| Meta-tool surface: `concierge_recommend`, `concierge_request_tool`, `concierge_list_active`, `concierge_observe` (observe deferred per B.2) | 3.0 | Three meta-tools for v1, backing on the `POST /recommend`, `POST /requests`, and `GET /tools` endpoints from §C.3.2. |
| Gap-report injection via recommendation tool-call result | 2.0 | Returned in `concierge_recommend`'s result payload. Requires SOUL-extracted Claude-Code-specific system-prompt fragment (from component #8). |
| Backing-server spawn/teardown + lifecycle management | 2.0 | Enables mid-session load/unload without session restart. |
| Integration debug + end-to-end smoke | 2.0 | Day 3 afternoon. |
| Contingency for adapter approach pivot if spike fails | 0.5 | Buffer: if Approach 1 doesn't work, Approach 2 is primary and the work budget holds; if Approach 2 runs long, Approach 1 fallback trims 4h off the shim. |

**Subtotal: 14h.** Phase F carry-forward: Day 3 budget is ~8h per
today.md; this doesn't fit cleanly in a single day. Recommend
pulling the proxy-shim skeleton (4h) into Day 2 afternoon if Day 2
morning runs on time. See §C.7 for carry-forward detail.

### C.3.2 FastAPI core service — ~14h — Day 1-2

| Sub-item | Hours | Notes |
|---|---|---|
| Project skeleton (FastAPI + pydantic + config + logging + test setup) | 1.0 | Day 1 morning. |
| SQLite schema (tools, packs, requests, memory-events) + SQLAlchemy models | 2.0 | Schema generalized to remove OpenClaw-specific columns (no `agentId`, no Alfred-only flags). Day 1. |
| Markdown-to-SQLite ingest routine (TOOL-MANIFEST.md + TOOL-CATALOG.md + openclaw.json) | 2.0 | Single one-shot ingest; seeds the store from existing markdown + active config. Day 1. |
| Catalog API endpoints (GET /tools, GET /tools/{id}, GET /packs) + markdown export | 2.0 | Day 1 afternoon — Day 1 checkpoint criterion (Lewie can curl GET /tools). |
| Memory service wrapper (in-process import of `moltbot-memory-mcp/server.py` functions) | 1.0 | Day 2 morning. |
| Recommendation endpoint (POST /recommend with Opus 4.7 call, system prompt assembled from components #3/#4/#6/#7/#8) | 3.0 | Day 2 morning-afternoon. |
| Lifecycle endpoints (GET /requests/pending, GET /requests/{id}, POST /requests, POST /requests/{id}/status) + markdown parser for tool-requests | 2.5 | Day 2 afternoon. Markdown parser is ~50 LOC per B.3. |
| Smoke tests + fixtures + heartbeat endpoint (health check) | 0.5 | Day 2 evening. |

**Subtotal: 14h.**

### C.3.3 UI (three sections) — ~12h — Day 4

Per Phase B.3 data needs and v2 blueprint §UI-in-detail. FastAPI +
Jinja2 + HTMX + Pico.css.

| Sub-item | Hours | Notes |
|---|---|---|
| Layout shell (Pico.css + Jinja2 base template + nav) | 1.0 | Day 4 morning. |
| Tool Registry section (hierarchical pack list, expand/collapse sub-tools, filter, search, manifest-vs-active dormant badge + Reload button) | 4.0 | Day 4 morning. |
| Pending Requests Inbox section (card render, HTMX approve/deny/defer buttons, optional comment field, reflects status line writes to markdown) | 3.0 | Day 4 afternoon. |
| Health/Stats bar (token-win counter, 3-of-7 MCP count, cron heartbeat, top-3 tools) | 2.0 | Day 4 afternoon. |
| Token-win instrumentation (NEW — not extraction; logs lightweight-substitute events to memory with `token-win` tag; rough heuristic: 400 tokens per MCP tool definition vs 20 tokens per CLI command) | 1.0 | Day 4 afternoon. |
| Integration + polish (empty states, titles, labels) | 1.0 | Day 4 evening. |

**Subtotal: 12h.**

### C.3.4 New-build total

**14 + 14 + 12 = 40h.**

---

## C.4 Effort audit and scope-flag assessment

### C.4.1 Existing-component non-RETIRE effort (from §C.2.1)

| Component | Effort |
|---|---|
| #1 TOOL-MANIFEST.md ingest | 1.5h (shared) |
| #2 TOOL-CATALOG.md ingest | (shared with #1, 0h additive) |
| #3 tool-awareness.md extract | 0.5h |
| #4 tool-recommendation.md extract | 0.5h |
| #5 tool-concierge-intro.md LIFT | 0h |
| #6 tool-discovery SKILL.md extract | 1.0h |
| #7 tool-lifecycle SKILL.md extract | 1.0h |
| #8 SOUL.md root extract | 0.5h |
| #9 SOUL.md workspace LIFT | 0h |
| #10 tool-requests/ layout + schema LIFT | 0h (API wrap counted in §C.3.2) |
| #11 outbox-housekeeping.sh LIFT | 0.5h (verify + doc) |
| #12 tool-on/tool-off RETIRE | 0h |
| #13 tool-install extract | 1.0h |
| #14 tool-wishlist.md LIFT | 0h |
| #15 moltbot-memory-mcp LIFT | 0h (wrapper counted in §C.3.2) |
| #16 mcporter LIFT | 0h |
| #19 TOOL-CONCIERGE-OVERVIEW.md LIFT | 0h |
| #20 worker-tool-escalation.md LIFT | 0h |
| #21 phase-2-test-scenarios.md LIFT | 0h |
| #22 openclaw.json LIFT | 0h (parse counted in §C.3.3) |

**Existing-component subtotal: 6.5h.**

### C.4.2 New-build subtotal (from §C.3.4)

**40h.**

### C.4.3 Grand total

**46.5h non-RETIRE effort for hackathon week.**

### C.4.4 Scope flag assessment

- **40h yellow threshold:** EXCEEDED (46.5h ≥ 40h). Triggers the
  check-in-before-committing conversation per 2026-04-21 morning
  confirmation.
- **50h red threshold:** NOT EXCEEDED (46.5h < 50h). No hard scope
  cut required by plan-v3 §C.3.
- **Nominal week budget:** 6 days × ~10-12h effective = ~60-72h raw,
  with diminishing returns from Day 4 onward. Per ops protocol,
  Days 5-6 are explicitly for stabilization / demo / submission, so
  the effective build-work budget is roughly Days 1-4 = ~32-48h of
  focused build-session hours, with Days 5-6 absorbing slack. 46.5h
  lands at the top of Days 1-4's realistic capacity and relies on
  the Day 5-6 buffer being available for any overflow.

**Pre-sequenced pull-out ladder (per 2026-04-21 signoff direction):**

These are **not** "if we have time" cuts. They are the pre-sequenced
ladder of trims to execute if Day 3 (or any earlier day) bleeds past
its budget. Pre-sequenced means: no improvisation under pressure.
When a day overruns, pull the next ladder item, log it in
DECISIONS.md, continue.

Ordered from lowest to highest demo impact:

- **Cut 1 — Trim Health/Stats bar to three tiles** (was §C.4.4 "c").
  Drop the top-3 most-used tools tile; keep token-win counter, active
  MCP count, and cron heartbeat. **Saves 0.5h.** Demo impact: minimal —
  the bar reads cleaner with three tiles and the top-3 tile's data
  source (memory aggregation) is the slowest to compute.
- **Cut 2 — Drop #13 tool-install-npm/pip extract** (was §C.4.4 "a").
  Approval-triggers-install step in the demo uses a manual install
  command shown in the terminal rather than an auto-triggered module.
  **Saves 1.0h.** Demo impact: low — the "watch cron pick it up"
  moment still works; the "autonomous install" claim becomes a
  narrated voiceover rather than a live action.
- **Cut 3 — Defer `concierge_list_active` meta-tool from the Claude
  Code adapter** (new; per §C.3.1 subcomponent breakdown). The adapter
  loads tools; the agent doesn't self-assess what's active before
  filing requests. **Saves 1.0h.** Demo impact: low — the agent can
  still file requests blindly; the Tool Registry UI surface handles
  the "what's active" introspection for the human operator.
- **Cut 4 — Defer markdown-export from the Day 1 SQLite ingest pass**
  (new). v2 blueprint names markdown-export as a nice-to-have for
  audit-trail preservation. Operator uses the UI for catalog
  introspection during hackathon; markdown-export lands post-demo.
  **Saves 1.0h.** Demo impact: low — audit trail is preserved by the
  SQLite store; markdown is cosmetic during demo week.

**Ladder subtotal: 3.5h saved across four pre-sequenced cuts.**

Executing the full ladder brings the estimate from 46.5h → **43h**,
still yellow-flagged (≥40h) but with meaningful buffer from the 50h
red line. Pre-sequencing means any day's overrun is absorbed by
pulling the next ladder item — no mid-week scope conversation required
for cuts 1-4.

**Beyond Cut 4 is demo-materiality territory.** Further cuts (e.g.,
trimming gap-report injection, deferring the memory wrapper, dropping
Tool Registry's filter/search UI, dropping the manifest-vs-active
dormant-badge affordance) materially affect the demo narrative and
require a Level-3 ops-protocol conversation (Claude.ai chat decision)
before being pulled. These are **not** pre-sequenced; they are escalation
triggers.

**Recommended posture:** accept 46.5h baseline; queue Cuts 1-4 as the
pre-sequenced ladder; any cut past Cut 4 escalates to chat. See §C.6
Q1.

### C.4.5 Budget distribution by build day

| Day | Activity | Hours |
|---|---|---|
| Day 1 (Tue 04-21) | §C.3.2 skeleton + catalog ingest + catalog endpoints; #1/#2 shared ingest; #22 parse prep | ~7.5h |
| Day 2 (Wed 04-22) | §C.3.2 memory wrapper + recommendation + lifecycle endpoints; #3/#4/#6/#7 extract (skill-prompt assembly); #11 verify; #10/#15 LIFT integration | ~8-9h |
| Day 3 (Thu 04-23) | §C.3.1 Claude Code adapter (verification spike → proxy shim → meta-tools → gap-report injection); #8 extract; #13 extract (install module) | ~12-14h (over single-day budget — see §C.7) |
| Day 4 (Fri 04-24) | §C.3.3 UI three sections + token-win instrumentation + integration | ~12h (two sessions per B.3) |
| Day 5 (Sat 04-25) | Stabilization, bug fixes, demo rehearsal (5 clean runs) | ops-protocol-defined |
| Day 6 (Sun 04-26) | Demo recording, README, submission | ops-protocol-defined |

**Day 3 overflow flag** — see §C.7 carry-forward to Phase F.

---

## C.5 Decision hygiene summary

Per plan-v3 §C.3 requirements:

### C.5.1 LIFT components — prove not secretly coupled

Every LIFT row in §C.2.2 includes an explicit "Prove LIFT isn't
secretly coupled" paragraph. Consolidated summary:

- **#5, #19** (prose docs): no coupling possible — content is
  narrative, not logic.
- **#9, #20** (OpenClaw-consumed docs): coupling exists but is
  out-of-path — Concierge doesn't consume these files at all; they
  stay inside OpenClaw's runtime.
- **#10** (lifecycle folder + schema): Phase A.2.4 explicitly
  verified — zero OpenClaw-specific fields; only the physical path
  is Moltbot-specific and is trivially relocatable.
- **#11** (outbox-housekeeping.sh): Phase A.2.5 explicitly verified —
  pure bash + coreutils; only `$HOME` path is configurable.
- **#14** (tool-wishlist.md): markdown log with documented format;
  would accept entries from any harness without modification.
- **#15** (moltbot-memory-mcp): Phase A.2.9 explicitly verified —
  zero OpenClaw-specific coupling in code; env-var configurable.
- **#16** (mcporter): third-party binary, not our code.
- **#21** (phase-2-test-scenarios.md): task-level descriptions with
  no infra coupling.
- **#22** (openclaw.json): coupling is inbound-only (we read, never
  write); bounded safely.

**No LIFT row is secretly coupled.** The inventory's verification
work and the Q2 / Q3 / Q4 / Q5 decisions from 2026-04-20 already
substantiated these claims; §C.2.2 cites where each was established.

### C.5.2 REWRITE components — explain why not EXTRACT or ADAPT

**No REWRITE classifications in this phase.** Every existing component
falls into LIFT, EXTRACT, or RETIRE. The genuinely-new items in §C.3
are not REWRITE (they weren't existing components to begin with).

Implicit case: **#12 (tool-on/tool-off) was a plausible REWRITE
candidate** — the v1 framing might have said "we need an MCP
load/unload mechanism, and the OpenClaw one has the wrong shape, so
rewrite it." Instead it is RETIRE because the **Claude Code adapter
is a different mechanism, not a rewrite of the same mechanism.** A
rewrite implies "same functionality, cleaner code"; the Claude Code
proxy-shim architecture is a functionally-different approach (session
preservation via proxying, not via restart-and-reload). See §C.2.2
row #12 for the full "why not REWRITE" argument.

### C.5.3 Unusual EXTRACTs worth noting

- **Prompt-fragment EXTRACTs (#3, #4, #6, #7, #8) are the headline
  unusual case.** Five of the seven EXTRACTs physically land as
  Python string constants composed into the `POST /recommend`
  Opus 4.7 system prompt, not as reimplemented Python logic. This
  jump from Phase B's "algorithm spec" framing to Phase C's
  "prompt-fragment composition" framing is the most load-bearing
  decision in Phase C and is logged at `[2026-04-21 10:30] Skill-
  extraction pattern: EXTRACT as prompt fragments (not pure Python,
  not ADAPT)` in DECISIONS.md. The decision entry covers why
  pure-Python EXTRACT (~+15h budget blow, discovery can't reasonably
  be Python) and ADAPT (implies modifying the source files —
  dilutes the vocabulary when no source file is being modified) both
  lose to the prompt-fragment framing. Structural mitigations
  (header-comment provenance, verbose constant names,
  `SKILL_FRAGMENT_SYNC_LOG.md`, Phase 2 automated-generation path)
  are specified there. Row #7 is a **partial hybrid** — promotion/
  demotion thresholds and the tag schema become genuine Python
  constants; the weekly-review protocol is the prompt-fragment part.
  Row #8 is the **pure prompt-fragment** case (SOUL is inherently
  prompt content; no Python logic is extractable).
- **#13 tool-install-npm/pip extract from the middle of a bash file**
  is unusual because it's extracting selected functions from a mixed-
  purpose file (the same file's tool-on/tool-off functions are
  RETIRE). The clean-separation argument justifies the Python
  extraction over an in-place ADAPT. This is the one "genuine code
  EXTRACT" in the inventory.

### C.5.4 Scope-excluded RETIREs

- **#23 AT-time scheduler** and **#24 OpenClaw internal SQLite** are
  RETIRE with the explicit "scope-excluded" flag per §C.2.2. They
  were never in Concierge's perimeter. This notation prevents future
  sessions from misreading them as "Concierge components retired
  after use."

---

## C.6 Questions for Lewie

**Q1 (scope-flag check-in, yellow-flag trigger):** ANSWERED
2026-04-21 per signoff feedback.

Accepted 46.5h with a **pre-sequenced 4-cut pull-out ladder** (not
"if we have time" cuts — explicit day-of triggers if any day
overruns). Ladder per §C.4.4: Cut 1 Health/Stats trim (0.5h), Cut 2
tool-install drop (1h), Cut 3 `concierge_list_active` meta-tool
deferral (1h), Cut 4 markdown-export deferral (1h). Full ladder
saves 3.5h → 43h. Beyond Cut 4 requires Level-3 chat escalation
(demo-materiality territory).

Rationale: pre-sequencing removes mid-week improvisation pressure.
When a day bleeds, pull the next ladder item, log it in
DECISIONS.md, continue. 46.5h leans on Day 5-6 buffer which is
operationally fine per ops-protocol Day-5-6 framing.

**Q2 (Day 3 overflow to Phase F):** ANSWERED 2026-04-21 —
**defer to Phase F.** Phase C flags the overflow; Phase F (capstone
build-plan document) makes the final day-allocation call with the
full Phase D dependency graph in hand. Carry-forward captured in §C.7.

**Q3 (token-win instrumentation scope):** ANSWERED 2026-04-21 —
**rough heuristic confirmed.** 1h budget holds. Demo shows the
number rising during the lightweight-substitute moment; precision
would be cosmetic.

**Q4 (any Phase C classification to re-review at max effort?):**
ANSWERED 2026-04-21 — **one re-review requested and completed at
`max` effort:** the EXTRACT-as-prompt-fragment pattern for the
skill files (#3, #4, #6, #7) and SOUL delta (#8). Three alternatives
considered (EXTRACT-as-prompt-fragment / pure-Python EXTRACT /
ADAPT). Outcome: **EXTRACT stands with structural mitigations.**
Full reasoning logged at `[2026-04-21 10:30]` in DECISIONS.md and
elevated in §C.5.3 above. No other re-reviews requested; all other
classifications stand as-written. Effort dropped back to `xhigh`
after the re-review completed.

---

## C.7 Carry-forward notes for Phase D and Phase F

**For Phase D (Dependency Graph):**

1. Skill-extracts (#3, #4, #6, #7, #8) compose into a single system
   prompt for `POST /recommend` — they have no dependencies on each
   other except via the composed prompt. Concurrency-friendly on Day 2.
2. §C.3.2 catalog ingest depends on §C.3.2 SQLite schema; both block
   catalog endpoints. Straightforward linear chain on Day 1.
3. §C.3.1 Claude Code adapter depends on §C.3.2 recommendation +
   lifecycle endpoints being up. Blocks integration testing on Day 3.
4. §C.3.3 UI depends on §C.3.2 catalog + lifecycle + memory endpoints
   being up. Can partially develop against fixtures before endpoints
   are wired, if schedule slips.
5. `openclaw.json` parsing (#22) is a dependency of the UI's
   Tool-Registry dormant-badge affordance and the Health-Stats bar's
   active-MCP-count tile.

**For Phase F (Build Plan):**

1. **Day 3 overflow flag (Q2 above):** Claude Code adapter's 14h
   budget exceeds an 8h day. Phase F decides whether to pull the
   proxy-shim skeleton into Day 2 afternoon or absorb into Day 5
   buffer.
2. **Day-3-morning verification spike (~30 min):** carry-forward from
   SESSION-2026-04-20-01. If `tools/list_changed` works in-session
   in Claude Code, Approach 1 becomes viable as primary and trims
   §C.3.1 effort by up to 4h. If not, Approach 2 is primary per
   current plan.
3. **Pre-sequenced pull-out ladder (Q1 answer, §C.4.4):** four cuts
   totaling 3.5h, day-of triggers if any day overruns. Cut 1
   Health/Stats trim → Cut 2 tool-install drop → Cut 3
   `concierge_list_active` deferral → Cut 4 markdown-export deferral.
   Phase F bakes these into the build plan as day-of pull triggers,
   not pre-cuts. Beyond Cut 4 escalates to chat.
4. **Token-win heuristic calibration (Q3 above):** 1h budget; rough
   heuristic; cosmetic precision.
5. **Ingest ordering:** on Day 1, ingest in order TOOL-MANIFEST.md →
   TOOL-CATALOG.md → openclaw.json (last-write-wins for active state).
6. **`toolconcierge/` draft-copy consolidation** is Phase 2 work per
   Q4 (2026-04-20). Do not touch during hackathon week.

---

## C.8 Summary for chat

Proposed for summary back to Lewie in chat (pre-signoff):

**Classification tally:** 12 LIFT (prose, schema, self-contained
tools), 7 EXTRACT (manifest/catalog data + four behavioral skills +
SOUL delta + install logic), 0 ADAPT, 0 REWRITE, 5 RETIRE (2
scope-excluded).

**Headline classifications, drivers:**

- **EXTRACT, not LIFT**, for the three cataloging sources
  (TOOL-MANIFEST.md, TOOL-CATALOG.md, skill markdown files): v2
  blueprint's SQLite + API requirement.
- **RETIRE, not REWRITE**, for tool-on/tool-off: the Claude Code
  adapter is a **different mechanism**, not a rewrite of the same.
- **LIFT, not EXTRACT**, for the three-folder lifecycle + schema:
  Phase A explicitly verified zero OpenClaw-specific fields.
- **LIFT, not EXTRACT**, for moltbot-memory-mcp: it's already
  platform-agnostic; in-process library import is consumption, not
  modification.
- **EXTRACT-as-prompt-fragment (not pure-Python, not ADAPT)** for
  skill files #3, #4, #6, #7, #8. Re-reviewed at `max` effort per
  Q4 answer; decision and structural mitigations logged at
  `[2026-04-21 10:30]` in DECISIONS.md; elevated in §C.5.3.

**Effort totals:**
- Existing-component non-RETIRE work: **6.5h**
- New-build (Claude Code adapter 14h + FastAPI core 14h + UI 12h):
  **40h**
- **Grand total: 46.5h — yellow flag triggered, red not triggered.**
- **Pre-sequenced pull-out ladder (Cuts 1-4):** saves up to 3.5h →
  43h if fully executed. Any single cut may be pulled day-of without
  chat escalation; beyond Cut 4 requires Level-3 escalation.

**Final posture (all four Q&As closed 2026-04-21):** accept 46.5h,
ladder queued, Day-3-overflow deferred to Phase F, rough-heuristic
for token-win, one max-effort re-review completed (prompt-fragment
pattern stands). Classification.md is finalized pending sign-off.

---

## C.9 Phase C checkpoint

Per `docs/concierge-operations-protocol.md` §Phase C and
`docs/concierge-claude-code-plan-v3.md` §Phase C checkpoint:

- [x] `planning/classification.md` exists
- [x] Every existing component has exactly one classification (24
      canonical rows + 13 draft-copy rows per §C.2.3 convention)
- [x] Effort estimates totaled and sanity-checked (§C.4.3 — 46.5h;
      ladder to 43h pre-sequenced in §C.4.4)
- [x] Scope risk flagged (yellow-flag at 46.5h ≥ 40h; red not
      triggered; pre-sequenced pull-out ladder in §C.4.4)
- [x] Max-effort re-review completed on EXTRACT-as-prompt-fragment
      pattern (rows #3/#4/#6/#7/#8) per Q4 signoff feedback; outcome
      logged at `[2026-04-21 10:30]` in DECISIONS.md
- [x] Lewie has reviewed and signed off on classifications
      (2026-04-21 — see DECISIONS.md)

Decision-hygiene items (plan-v3 §C.3):

- [x] Every LIFT carries "prove not secretly coupled" note (§C.5.1)
- [x] Every REWRITE carries "why not EXTRACT or ADAPT" note (N/A — no
      REWRITEs; implicit case for #12 handled in §C.5.2)
- [x] Unusual EXTRACTs (prompt-fragment pattern, mixed-file extract)
      called out in §C.5.3 with DECISIONS.md cross-reference
- [x] Scope-excluded RETIREs flagged (§C.5.4)

---

*Phase C deliverable complete and signed off 2026-04-21. Proceeding
to Phase D — Dependency Graph at `xhigh` effort per Lewie's
direction. Phase D deliverable: `planning/dependency-graph.md`.*
