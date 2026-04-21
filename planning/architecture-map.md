# Concierge — Phase B (Architecture Mapping)

*Deliverable of Phase B per `docs/concierge-claude-code-plan-v3.md`.*
*Session:* `SESSION-2026-04-20-01` (Phase A and Phase B rolled together).
*Generated:* 2026-04-20.
*Effort:* `xhigh`.

This document maps every component inventoried in Phase A against the v2
blueprint's architecture, specifies the gaps to hackathon target state
(especially the Claude Code adapter), and specifies the three UI sections'
data needs. It resolves Phase A's open question Q6 in §B.4.

---

## B.1 Mapping overview

### Summary table — blueprint coverage at a glance

Ratings: **FULL** = existing work largely implements the blueprint
component; **PARTIAL** = implements some of it; **SUPPORTS** = helps but
doesn't implement; **—** = no relationship; **HISTORICAL** = reference
only, not deployable.

| Blueprint component | Existing coverage | Gap size | Classification lean |
|---|---|---|---|
| **Catalog Service** | PARTIAL | Schema generalize + SQLite + markdown export | EXTRACT + ADAPT |
| **Recommendation Engine** | PARTIAL | Lift behavioral protocol into callable Opus-backed API | EXTRACT (algorithm) + NEW (API + wiring) |
| **Memory Service** | FULL (for MCP callers) | HTTP wrapper for non-agent callers | LIFT + wrap |
| **Loader/Proxy Layer (Claude Code)** | — | Fully new; load/unload without session restart | NEW BUILD |
| **Loader/Proxy Layer (OpenClaw)** | FULL (tool-on/tool-off) | Out of hackathon scope | — (Phase 2) |
| **Concierge Agent Interface** | FULL (for OpenClaw, file-based) | HTTP/MCP surface for non-file callers | ADAPT |
| **Lifecycle State Machine** | FULL (filesystem + cron + schema) | Read/write API endpoints for UI | LIFT + wrap |
| **UI / Dashboard** | — | Three sections, fully new | NEW BUILD |
| **Failure Feedback Loop** | PARTIAL (file + template, zero traffic) | Cut from v1 per Q5; phase-2 | DEFER |
| **Cross-Harness Learning** | SUPPORTS (shared memory + manifest in fleet) | Falls out of Memory + Catalog | ∅ (no separate work) |

### Map of every existing component → blueprint slot(s)

Each existing component may support multiple blueprint components; that's
noted as a list. Primary mapping listed first.

| Existing component | File path | Primary → blueprint slot | Also touches |
|---|---|---|---|
| TOOL-MANIFEST.md | `_legacy/agent-skills/shared/TOOL-MANIFEST.md` | Catalog (PARTIAL) | Agent Iface (SUPPORTS), Failure FB (SUPPORTS intent-vs-active), Cross-Harness (SUPPORTS fleet-wide view) |
| TOOL-CATALOG.md | `_legacy/satiety-docs/TOOL-CATALOG.md` | Catalog (PARTIAL) | Rec Engine (SUPPORTS candidate pool) |
| tool-awareness.md + SKILL.md | `agent-skills/shared/`, `openclaw-root/skills/tool-awareness/` | Rec Engine (PARTIAL, 5-step protocol) | Agent Iface (SUPPORTS) |
| tool-recommendation.md + SKILL.md | `agent-skills/shared/`, `openclaw-root/skills/tool-recommendation/` | Rec Engine (PARTIAL, 6-step notice/evaluate/propose) | — |
| tool-discovery SKILL.md | `openclaw-workspace/skills/tool-discovery/` | Rec Engine (PARTIAL, discovery algorithm) | — |
| tool-lifecycle SKILL.md | `openclaw-workspace/skills/tool-lifecycle/` | Lifecycle SM (FULL algorithm spec) | Memory (SUPPORTS via tagging convention) |
| tool-concierge-intro SKILL.md | various `skills/tool-concierge-intro/` | Agent Iface (SUPPORTS orientation) | — |
| SOUL.md (root, delta) | `_legacy/openclaw-root/SOUL.md` | Agent Iface (FULL mandate) | Rec Engine (SUPPORTS) |
| SOUL.md (workspace, integrated) | `_legacy/openclaw-workspace/SOUL.md` | Agent Iface (FULL integrated behavior) | Rec Engine (SUPPORTS) |
| tool-requests/ three-folder store | `_legacy/tool-requests/{pending,resolved,archived}/` | Lifecycle SM (FULL physical layout) | UI (SUPPORTS Pending Inbox data source) |
| tool-requests/README.md (schema) | `_legacy/tool-requests/README.md` | Lifecycle SM (FULL spec) | UI (SUPPORTS rendering contract) |
| outbox-housekeeping.sh | `_legacy/satiety-docs/scripts/outbox-housekeeping.sh` | Lifecycle SM (FULL automation) | UI (SUPPORTS heartbeat source) |
| tool-functions.sh (tool-on/tool-off) | `_legacy/satiety-docs/scripts/tool-functions.sh` | Loader/Proxy OpenClaw (PARTIAL) | — |
| tool-functions.sh (install-npm/pip) | same | Loader/Proxy (PARTIAL autonomous-install logic) | — |
| tool-wishlist.md | `_legacy/openclaw-root/logs/tool-wishlist.md` | Failure FB (PARTIAL template + protocol; zero traffic) | — |
| moltbot-memory-mcp/server.py | `_legacy/moltbot-memory-mcp/server.py` | Memory (FULL) | Cross-Harness (SUPPORTS substrate) |
| moltbot-memory-mcp/run.sh | same dir | Memory (FULL, stdio entry) | — |
| mcporter | `/home/satiety/.npm-global/bin/mcporter` | Loader/Proxy (SUPPORTS per-call pattern) | — |
| openclaw.json | `_legacy/openclaw-root/openclaw.json` | Catalog (SUPPORTS — active config), Loader/Proxy (SUPPORTS edit surface), Memory (SUPPORTS registration) | — |
| MCP-BRIDGE-GUIDE.md | `_legacy/openclaw-workspace/docs/MCP-BRIDGE-GUIDE.md` | Loader/Proxy (HISTORICAL) | — |
| ALFRED-MCP-REFERENCE.md | same dir | Catalog (HISTORICAL, per-server detail) | — |
| TOOL-CONCIERGE-OVERVIEW.md | `_legacy/toolconcierge/` | Documentation for all components | — |
| worker-tool-escalation.md | `_legacy/toolconcierge/` | Agent Iface (SUPPORTS dual-channel pattern) | — |
| phase-2-test-scenarios.md | `_legacy/toolconcierge/`, `_legacy/satiety-docs/test-scenarios/` | UI (SUPPORTS demo-fixture source) | — |
| openclaw cron/jobs.json | `_legacy/openclaw-root/cron/jobs.json` | — (AT-time scheduler, unrelated to Concierge) | — |

### Per-blueprint-component narrative

Detail on what exists, what's missing, and what the extraction looks like.

**Catalog Service — PARTIAL**

Two markdown files — `TOOL-MANIFEST.md` (fleet-wide, 256 lines, 7 MCP
servers with metadata) and `TOOL-CATALOG.md` (operator-facing, CLI tools
+ MCP servers + paid services) — jointly describe the catalog. The
active state is in `openclaw.json.mcp.servers` (3 servers currently
loaded). The Q3 reframing makes this tidy: `openclaw.json` = active,
`TOOL-MANIFEST.md` = intent/manifest, delta = "consider reloading"
affordance.

*What's missing for hackathon target:*
- Structured schema (SQLite table with generalized fields — no
  OpenClaw-specific columns like `agentId`, Alfred-only flags). The
  schema needs to represent MCP servers, CLI tools, HTTP APIs, and skills
  as peers, per the v2 blueprint's lightweight-first framing.
- Markdown export back to a human-readable manifest (preserve the audit
  trail the current manifest provides).
- Pack hierarchy (e.g., "MailerLite 36 tools" as a pack with sub-tools).
  The catalog today has packs *named* in its tables but not as a
  first-class data relationship.
- Ingest routine: read TOOL-CATALOG.md + TOOL-MANIFEST.md + openclaw.json
  on first run, seed the SQLite store.

*Extraction footprint:* ~200 LOC FastAPI + SQLAlchemy models + a
one-shot Markdown-to-SQLite ingester. The existing data is the seed.

**Recommendation Engine — PARTIAL**

Four skill files carry the behavioral spec (`tool-awareness.md`,
`tool-recommendation.md`, `tool-discovery/SKILL.md`,
`tool-lifecycle/SKILL.md`). Together they specify: when to fire, what
sources to check before proposing (memory → resolved requests → catalog
→ manifest → discovery research), how to write a structured request,
promotion/demotion thresholds. **The algorithm is documented in
markdown; there is no Python/Node service that executes it.** Today it
runs as Alfred's internal reasoning guided by the skill prompts.

*What's missing for hackathon target:*
- A callable API (`POST /recommend` with task context → ranked list).
- The Opus-4.7-driven reasoning layer that turns a task description +
  catalog + memory hits into a recommendation with rationale and
  confidence. This is *genuinely new* code, but the prompt for the Opus
  call is lifted directly from the four skill files.
- Lightweight-first preference policy as a system-prompt rule (per v2
  blueprint). Not present in the current skills — they emphasize
  "silence is failure" but don't bias toward CLI over MCP.
- The discovery-engine subcomponent: today the agent is told to web-search
  per `tool-discovery/SKILL.md`. For the hackathon this likely stays as a
  Claude-Opus-driven research step (not a background crawler).

*Extraction footprint:* new FastAPI endpoint + Opus wrapper, ~150 LOC.
The four skill files become the system-prompt fragments.

**Memory Service — FULL**

`moltbot-memory-mcp/server.py` is a 14,466-byte FastMCP stdio server
with 8 tools (store/search/delete/list/update + identity get/set +
stats), ChromaDB persistent backend at `$MOLTBOT_MEMORY_DIR`, and
`all-MiniLM-L6-v2` sentence-transformer embeddings on CPU. The server
has zero OpenClaw-specific coupling in its code — path config is via
`MOLTBOT_MEMORY_DIR` env var. Two ChromaDB collections: `memories`
(main) and `identity` (persistent agent-context notes). Metadata fields:
`created_at`, `updated_at`, `source`, `importance` (low/normal/high/
critical), `tags` (JSON-encoded).

*What's missing for hackathon target:*
- An HTTP wrapper so non-MCP callers (the Concierge Recommendation Engine
  API, the Operator UI) can query memory without going through the stdio
  MCP surface. `server.py` can be imported directly by the FastAPI
  app if Concierge runs in-process with ChromaDB, which is the
  recommended shape for v1.
- Per-harness separation: today memory stores are per-agent
  (`~/.agent-memory/content-prep/`, `~/.agent-memory/intelligence/`, etc.)
  via `MOLTBOT_MEMORY_DIR`. For Concierge serving Claude Code AND
  OpenClaw, decide whether Concierge has its own shared memory or
  federates across per-agent stores. *Claimed falls out of existing
  design* — just point the Concierge-side env var at a shared path.

*Extraction footprint:* thin wrapper, ~50 LOC — import `server.py`
functions as Python library calls from the FastAPI app, or run the MCP
server as a subprocess and proxy. The former is cleaner for v1.

**Loader/Proxy Layer (Claude Code) — NEW BUILD**

Nothing exists today. The OpenClaw equivalent (`tool-on`/`tool-off` in
`tool-functions.sh`) requires a systemd service restart per load/unload,
which would kill a Claude Code session's active context. See §B.2 for
the full adapter gap specification and candidate approaches.

**Loader/Proxy Layer (OpenClaw) — FULL (out of hackathon scope)**

`tool-functions.sh` fully implements the OpenClaw load/unload via
config-edit + `systemctl restart`. Autonomous-install (`tool-install-npm`
/ `tool-install-pip`) is also complete. Per CLAUDE.md v3 and Q4, OpenClaw
adapter is Phase 2 work. Noting completeness for later.

**Concierge Agent Interface — FULL (for OpenClaw) / needs adapter for Claude Code**

The OpenClaw-side interface is the combination of:
- `SOUL.md` mandate ("silence about inadequate tools is failure")
- `tool-awareness.md` protocol (how agents check manifest + gap report)
- `tool-recommendation.md` protocol (how agents file requests)
- Filesystem surface at `.satiety-pipeline/outbox/tool-requests/` (what
  agents write to)
- `sessions_send` + `worker-*` escalation for cross-agent comms

This is pull-and-push in the current architecture, but *file-based and
OpenClaw-fleet-specific*. Workers pull by reading the manifest; they push
by writing to `pending/`. There is no HTTP/MCP surface today.

*What's missing for hackathon target:*
- HTTP/MCP endpoints a Claude Code session can call:
  `POST /recommend` (pull), `POST /requests` (push new gap), `GET
  /requests/pending` (read state)
- Proactive push — Concierge injecting a message into the Claude Code
  session's context ("you're about to use MCP browser; curl+grep would
  work for this task"). See §B.2's push mechanism discussion.

*Extraction footprint:* the HTTP/MCP surface is the same 3-4 endpoints
the UI uses (§B.3), just exposed to a different client. No duplicate
work.

**Lifecycle State Machine — FULL**

Every piece exists and is currently running:
- Physical layout: `.satiety-pipeline/outbox/tool-requests/{pending,
  resolved,archived}/` (3 folders).
- Schema: `tool-requests/README.md` defines 6-value status
  (`pending|approved|denied|installed|failed|deferred`), filename
  convention (`YYYY-MM-DD-HHMM-<slug>.md`), and the request template with
  sections Request / Recommendation / Approval / Install / First Use /
  Outcome.
- Automation: `outbox-housekeeping.sh` runs hourly via user crontab
  (`0 * * * *`), moving files by status, archiving resolved files after
  30 days, flagging stale pending (≥7 days), writing heartbeats to
  `housekeeping.log`.
- Algorithm spec (promotion/demotion): `tool-lifecycle SKILL.md` defines
  promotion criteria (5+ uses in 30 days + recurring across tasks) and
  demotion criteria (90+ days unused). Today the promotion/demotion
  itself is manual — the spec exists, the operator acts on it.
- Memory tagging convention: `tool-selection` tag with structured
  content `TOOL: <name> | PATTERN: <pattern> | STATUS: <status> | AGENT:
  <agent> | DATE: <YYYY-MM-DD> | NOTES: <...>`.

*What's missing for hackathon target:*
- Read endpoints (`GET /requests/pending`, `GET /requests/resolved`,
  `GET /requests/{id}`) that parse the markdown files and return
  structured JSON for the UI.
- Write endpoint (`POST /requests/{id}/status`) that updates the status
  line in the markdown file (appending an Approval block if
  applicable), so the existing hourly cron picks it up — zero changes to
  the cron or schema.
- Promotion/demotion execution code: today the criteria are written as
  prose for the operator to act on. A `POST /requests/` that accepts a
  "promotion: X to boot set" or "demotion: X" template and files it into
  `pending/` (same machinery as any other request — just a different
  title convention) is the smallest addition.

*Extraction footprint:* read endpoints + one write endpoint, ~150 LOC
FastAPI + a small Markdown parser (the template is regular enough that a
50-line parser handles it).

**UI / Dashboard — NEW BUILD**

Nothing exists. Full specification in §B.3.

**Failure Feedback Loop — PARTIAL → DEFERRED**

`tool-wishlist.md` has a template + documented logging protocol (Step 5
of `tool-awareness.md`), but zero real entries. Per Q5, the Wishlist
UI section is cut from v1; backend still reads the file (so Phase 2 UI
work is just rendering). Nothing extra to build in Phase F for the
hackathon.

**Cross-Harness Learning — SUPPORTS → ∅ (falls out)**

The semantic memory MCP is per-agent today but the mechanism is generic
(`MOLTBOT_MEMORY_DIR` env var). Pointing Concierge at a shared memory
path — or at each harness's store by default — makes Claude Code sessions
and OpenClaw agents peers in the same memory substrate. **No separate
work is required for cross-harness learning** beyond the Memory Service
wrapper. The TOOL-MANIFEST.md is the shared catalog view today; the
generalized SQLite catalog replaces it.

---

## B.2 Claude Code adapter gap

The Loader/Proxy Layer for Claude Code is the *architecturally hardest
genuinely-new piece of the hackathon*. The blueprint assumes it and the
v2 refresh emphasized it, but didn't specify the mechanism. Phase A
surfaced the core constraint: **load/unload via systemd restart (the
OpenClaw approach) is incompatible with Claude Code sessions.**

### The core problem

A Claude Code session holds conversational state (context window, tool
call history, partially-completed tasks) across many turns. The MCP
servers attached to it define its tool surface. **The v1 demo requires
tools to be added to or removed from that surface mid-session without
dropping the conversation.**

Three mechanisms could achieve this.

### Approach 1 — Native MCP `tools/list_changed` notification

The MCP protocol defines a server-side notification
(`notifications/tools/list_changed`) that signals the client to re-fetch
the tool list. Claude Code's MCP client handles this. The approach:

1. Concierge runs as an MCP server that Claude Code connects to at
   session start.
2. Concierge's exposed tool list is *meta* — `concierge_recommend`,
   `concierge_request_tool`, `concierge_list_active`, etc. — plus the
   currently-loaded backing tools routed through Concierge.
3. When Concierge loads or unloads a backing tool, it sends
   `tools/list_changed`. Claude Code re-fetches. The session continues.

**Pro:** Uses standard protocol primitives, no custom plumbing.
**Con:** Requires Claude Code to respect `tools/list_changed` in-session
(Anthropic documented support varies by harness; verify early on Day 3).
**Verification task for Day 3 morning:** Confirm the Claude Code MCP
client actually re-fetches on `tools/list_changed` and that tool
definitions change within the same session.

### Approach 2 — stdio proxy shim (Concierge as the only MCP server)

Concierge runs a single stdio MCP server. Behind its tool surface, it
multiplexes over multiple backing MCP servers (the ones currently
loaded) plus its own meta-tools. Tool names are prefixed
(`firefox_navigate_page` routes to the firefox backing server). When
backing servers change, only Concierge's tool list changes — from
Claude Code's perspective, it's always talking to one server.

**Pro:** Full control over lifecycle; works even if
`tools/list_changed` support is flaky; backing-server crashes don't
propagate to the session. Enables the lightweight-first preference to
*intercept and substitute* (e.g., route a catalog lookup to `curl`
instead of a backing browser tool).
**Con:** More implementation work (~300 LOC stdio proxy + per-backing-
server process management). Must handle JSON-RPC id mapping, request
forwarding, and backing-server spawn/teardown.

### Approach 3 — Per-call ephemeral spawn (mcporter-style)

For low-frequency or one-off tools: spawn the backing MCP server per
call, make the call, tear down. `mcporter` (v0.7.3) already exists on
the system as prior art for this pattern.

**Pro:** Zero ongoing process state; works for ad-hoc tools from
registries.
**Con:** Slow per-call (200ms+ spawn cost); unusable for interactive
tools that need session state (browser automation, MCP servers that
maintain OAuth tokens).

### Recommended mix for v1

- **Primary: Approach 2 (stdio proxy shim).** Full control, demo-
  resilient, enables the lightweight-first-preference substitution that
  is the pitch's most compelling feature.
- **Fallback: Approach 1 (native `tools/list_changed`).** If the proxy
  shim runs long on Day 3, falling back to direct MCP-server connections
  + `tools/list_changed` notifications is a simpler implementation.
- **Tertiary: Approach 3 for infrequent tools.** Use mcporter or mirror
  its pattern for one-off discovery calls. Don't use for anything in the
  hot path.

### Subcomponents beyond the loader itself

The Claude Code adapter is more than the load/unload mechanism:

1. **Gap-report injection (push).** Concierge proactively surfaces
   "there's a better tool for this task" mid-session. Two candidate
   mechanisms:
   - **Via a push-tool call result:** Concierge's `concierge_recommend`
     returns a recommendation whenever the session calls it; the agent
     learns to call it as part of its task decomposition.
   - **Via a watcher subscription:** Claude Code session publishes its
     current task context to Concierge via a subscription tool
     (`concierge_observe`); Concierge returns relevant recommendations
     in the next tool-call result. More invasive; defer to Phase 2.
   
   v1 goes with the first — Claude Code calls `concierge_recommend` on
   its own initiative, guided by a SOUL-like system prompt rule. This
   preserves the "agent agency" pattern the current OpenClaw system
   uses.

2. **Recommendation pull.** The direct `concierge_recommend(task_context)`
   tool call. Returns ranked recommendations. Trivial given the
   recommendation-engine endpoint exists.

3. **Request filing from within a session.** `concierge_request_tool`
   writes to `pending/` following the existing markdown schema. The
   user sees it in the Pending Requests Inbox UI, approves, cron
   picks up, Concierge loads, session regains the tool.

4. **Session-aware catalog view.** `concierge_list_active` returns what's
   currently loaded for *this* session (if proxy shim) or globally (if
   direct MCP). Useful for the agent to self-assess before filing
   requests.

### Informed-by references

- `tool-functions.sh` (tool-on/tool-off pattern) — how to think about
  enable/disable semantics, even though the OpenClaw-specific script
  can't lift.
- `MCP-BRIDGE-GUIDE.md` — JSON-RPC 2.0 over stdio protocol details; tool
  registration at startup; `servername_toolname` routing convention.
  Per Q2: historical reference only, don't lift.
- `mcporter` — per-call ephemeral spawn pattern.

---

## B.3 UI gap per section

Three sections per the v2 blueprint and Q5 decision. Tech stack: FastAPI
+ Jinja2 templates + HTMX + Pico.css (per blueprint v2, §UI in detail).

### Section 1 — Tool Registry

Browsable, hierarchical view of all tools in the catalog. Hackathon v1
scope: render active state + lifecycle state + usage summary.

**Data needs (per row):**
- `name` (string)
- `pack` (string, for hierarchy — e.g. "MailerLite", "Firefox DevTools",
  "CLI core")
- `transport` (one of: `mcp-stdio | mcp-http | cli | http-api | skill`)
- `lifecycle_state` (one of: `pending | used | loaded-on-boot | retired`
  per v2 blueprint)
- `owning_agent(s)` (list — e.g. ["alfred"], ["all"])
- `last_used` (ISO timestamp or null)
- `success_rate` (float 0-1 or null)
- `active` (bool — is this currently loaded per openclaw.json?)
- `install_method` (if not yet installed: npm-global | pip-user | apt |
  binary | mcp-server | other)

**Data sources (where each field comes from):**
- `name`, `pack`, `transport`, `install_method` → SQLite catalog
  (derived from TOOL-MANIFEST.md + TOOL-CATALOG.md ingest).
- `active` → parse `openclaw.json.mcp.servers` + `plugins.entries` for
  `enabled: true`.
- `lifecycle_state` → derived: intersect catalog entries with memory
  tag `tool-selection` hits (installed → used; no hits in 90d → retired;
  in `pending/` folder → pending) and with `active` flag (active for 30d+
  with use → loaded-on-boot).
- `last_used`, `success_rate` → semantic memory MCP queries for
  `tool-selection` tagged entries filtered by tool name.
- `owning_agent(s)` → TOOL-MANIFEST.md ingest field.

**Filter UI:** by state (pending/used/loaded/retired), by pack, by
transport type.
**Search UI:** by name (simple text filter).
**Hierarchy UI:** collapsible packs with sub-tool counts. MailerLite
expands to 36 tools, etc.

**Manifest-vs-active delta affordance** (per Q3): rows for tools
claimed in the manifest but not in the active config get a visual
"dormant" badge plus a `Reload` button that files a pending request
with title "Reload: <tool> to <agent>."

### Section 2 — Pending Requests Inbox

Renders the contents of `.satiety-pipeline/outbox/tool-requests/pending/`
as a list of cards, with approve/deny/defer actions.

**Data needs (per card):**
- `filename` (for status-line editing)
- `status` (from first line — should be `pending` for anything in this
  folder)
- `tool_name` (from `# Tool Request: <n>` header)
- `task_context` (Request section, first bullet)
- `tool_suggested` (Request section, Tool suggested)
- `category` (Request section, Category)
- `install_method` (Request section, Install method)
- `discovered` (bool — Request section, Discovered true/false)
- `recommendation_why` (Recommendation section, Why this tool)
- `alternatives_considered` (Recommendation section)
- `risk_cost` (Recommendation section)
- `confidence` (high/medium/low)
- `source` + `evidence` (discovery requests only)
- `filed_at` (from filename timestamp)
- `age_days` (derived)

**Data sources:**
- Parse `pending/*.md` via a small Markdown parser (50 LOC; the template
  is regular).
- `age_days` = `now - filename_timestamp`.

**Actions (HTMX buttons):**
- **Approve** → `POST /requests/{filename}/status` with body
  `{status: "approved", conditions: "<optional>", date: "<today>"}`.
  Server rewrites the file: update status line to `approved`, fill
  Approval block. Cron moves file to `resolved/` on next run.
- **Deny** → same endpoint, `{status: "denied", reason: "<required>"}`.
- **Defer** → same endpoint, `{status: "deferred"}`.
- **Optional comment field** on each card (appended to the Approval
  block's Conditions or a Notes line).

**Operator experience note:** Replaces the "edit the markdown file by
hand" workflow. Reasonable hackathon-v1 spec.

### Section 3 — Health / Stats bar

Compact strip across the top of the dashboard. Updated on page load
(or periodic HTMX poll — 30s interval is fine for v1).

**Stats to render:**
- **Token-win counter.** Running total of estimated token savings from
  lightweight-first preference substitutions this week.
  *Data source:* NEW instrumentation. When `concierge_recommend` returns
  a lightweight substitute over an MCP option and Claude Code uses the
  substitute, log the estimated token delta (heuristic: `<MCP tool
  definition size> - <cli command length>`). v1 can use rough estimates
  (e.g., 400 tokens per MCP tool definition, 20 tokens per CLI command).
  Store in the memory MCP with tag `token-win`.
- **Active MCP servers count.** "3 of 7 loaded" (or whatever the active
  config + manifest delta shows).
  *Data source:* parse `openclaw.json.mcp.servers` for active count;
  parse TOOL-MANIFEST.md for total claimed.
- **Cron last-run timestamp + heartbeat status.** "Last cron: 14 min
  ago ✓" or "Last cron: 2h 12m ago ⚠" if stale.
  *Data source:* tail `housekeeping.log` for the most recent BEAT line.
  Parse timestamp. Compare against expected cadence (should be within
  the hour).
- **Top 3 most-used tools (this week).** Sorted by `tool-selection`
  memory entry count in the last 7 days.
  *Data source:* semantic memory MCP `memory_list` with
  `tag_filter: tool-selection`, filter client-side to last 7 days,
  aggregate by tool name.

**Rendering:** a single-row horizontal strip with four tiles. Pico.css
handles styling.

---

## B.4 Resolution of Phase A's Q6 (tool-discovery / tool-lifecycle skills)

Phase A left Q6 open pending Phase B mapping evidence.

**Resolution:** `tool-discovery/SKILL.md` and `tool-lifecycle/SKILL.md`
are **not "skills" in the Concierge architecture — they are the
authoritative algorithm specs for specific blueprint components.**

- `tool-discovery/SKILL.md` is the authoritative specification for the
  **Recommendation Engine's discovery-engine subcomponent**. Its content
  (search patterns by domain; green/yellow/red signal table for
  candidate filtering; discovery-request format with
  Source/Evidence fields) defines how Concierge researches unknown
  tools when the catalog and manifest come up empty.

- `tool-lifecycle/SKILL.md` is the authoritative specification for the
  **Lifecycle State Machine**. Its content (`tool-selection` memory
  tagging convention with structured content string; promotion criteria
  [5+ uses / 30 days / recurring]; demotion criteria [90+ days unused];
  weekly-review protocol) defines how Concierge evaluates tools for
  lifecycle transitions.

**Phase C treatment:** Both EXTRACT as algorithm-spec modules inside
Concierge core. The content becomes Python docstrings, system prompts,
or threshold constants as appropriate. Neither needs to be a loadable
SKILL.md in Concierge.

**OpenClaw boot-load status (orthogonal):** Whether OpenClaw enables
these as boot-loaded skills is independent of Concierge's extraction.
Current state (reference-only, cross-linked from active skills
`tool-awareness` and `tool-recommendation`) is fine and does not need
to change for the hackathon. Phase 2's OpenClaw adapter can reconsider.

---

## B.5 Phase B checkpoint

Per `docs/concierge-claude-code-plan-v3.md` §B checkpoint:

- [x] `planning/architecture-map.md` exists
- [x] Every existing component mapped to one or more blueprint components
  (see §B.1 table and narrative; every Phase A component appears)
- [x] Claude Code adapter gap fully specified (§B.2 — core problem,
  three candidate approaches with pros/cons, recommended mix, four
  subcomponents, references)
- [x] UI gap fully specified per section (§B.3 — three sections, each
  with data needs per field, data sources, actions, and renderer notes)
- [ ] Lewie reviewed before Phase C

Two phase-A items closed here as well:

- [x] Phase A's Q6 resolved (§B.4)
- [x] Phase A's Q3 honored (manifest/active-config drift surfaces as a
  UI feature, not hidden — §B.3 Tool Registry "dormant" badge +
  Reload button, and the Health/Stats "3 of 7 loaded" tile)

---

*Phase B deliverable complete pending your review. Session handoff
snapshot will be written after review, rolling Phase A + Phase B into
`planning/sessions/SESSION-2026-04-20-01.md`. Per your instruction: do
NOT start Phase C — that's tomorrow's session at `max` effort.*
