# Concierge — Phase A (Codification) Inventory

*Deliverable of Phase A per `docs/concierge-claude-code-plan-v3.md`.*
*Session:* `SESSION-2026-04-20-01`
*Generated:* 2026-04-20

This document is grown incrementally across A.1 → A.2 → A.3 → A.4. Sections
beyond the current work-in-progress marker are placeholders until filled.

---

## A.1 Top-level survey

Seven symlinks under `_legacy/`. Total unique files at depth ≤3 (accounting
for overlaps): ~1,234. Two intentional overlaps noted:

- `_legacy/tool-requests/` is the same subtree as
  `_legacy/satiety-pipeline/outbox/tool-requests/` (direct shortcut created
  during bootstrap for ergonomic access to the lifecycle store).
- `_legacy/openclaw-workspace/` is the same subtree as
  `_legacy/openclaw-root/workspace/` (both resolve into `.openclaw/workspace/`).

### Symlink inventory

| # | Path | Target | Kind | Files ≤3 |
|---|---|---|---|---|
| 1 | `_legacy/toolconcierge/` | `/mnt/c/.../ClaudeCodeCLI/ToolConcierge` | Windows → Windows | 20 |
| 2 | `_legacy/satiety-docs/` | `/home/satiety/satiety-docs/` | Windows → WSL | 8 |
| 3 | `_legacy/satiety-pipeline/` | `/home/satiety/.satiety-pipeline/` | Windows → WSL | 35 |
| 4 | `_legacy/openclaw-workspace/` | `/home/satiety/.openclaw/workspace/` | Windows → WSL | 451 |
| 5 | `_legacy/agent-skills/` | `/home/satiety/.agent-skills/` | Windows → WSL | 16 |
| 6 | `_legacy/tool-requests/` | `/home/satiety/.satiety-pipeline/outbox/tool-requests/` | Windows → WSL | 7 |
| 7 | `_legacy/openclaw-root/` | `/home/satiety/.openclaw/` | Windows → WSL | 1,155 |

### Per-symlink one-line purpose + depth-3 structure

**1. `_legacy/toolconcierge/` — Beta tool concierge design/spec repo**
Flat directory of 20 planning and skill documents plus two shell scripts.
No subdirectories beyond `.claude/`. Appears to be the **design/spec and
skill-authoring workspace** for the tool concierge — not a runtime. Contains
`CLAUDE.md`, `TOOL-CONCIERGE-OVERVIEW.md`, `TOOL-CONCIERGE-PLAN.md`,
`TOOL-CATALOG.md`, four `skill-tool-*.md` files (discovery, lifecycle,
recommendation, intro), `tool-functions.sh`, `outbox-housekeeping.sh`
(candidate: the cron housekeeping script?), `setup-test-data.sh`,
`phase-2-test-scenarios.md`, and v1/v2 `tool-request-README` files.
Also has `paste.txt` and `paste2.txt` — likely scratch content, noted not
judged.

**2. `_legacy/satiety-docs/` — Master planning docs and scripts root**
8 files / 3 dirs. Contains `TOOL-CATALOG.md` and `TOOL-CONCIERGE-PLAN.md`
(appears duplicated from `toolconcierge/` — provenance to resolve in A.2),
`DONE.md`, plus `scripts/` and `test-scenarios/` subdirectories. One Windows
artifact present: `TOOL-CONCIERGE-PLAN.md:Zone.Identifier` (harmless).

**3. `_legacy/satiety-pipeline/` — Content/publishing pipeline**
35 files / 16 dirs. **Important reframing:** this is *not* a tool lifecycle
pipeline. It is a content/publishing pipeline with per-state folders:
`alerts/`, `approved/`, `briefings/`, `drafts/`, `engagement/`,
`linkedin-ready/`, `needs-attention/`, `outbox/`, `posted/`, `research/`,
`scheduled/`, plus `calendar.json`. The tool-concierge-specific piece is
*only* the `outbox/tool-requests/` subtree (exposed directly as symlink 6).

**4. `_legacy/openclaw-workspace/` — Alfred's operator workspace (git-tracked)**
451 files / 92 dirs. This is OpenClaw/Alfred's primary working directory
with its own `.git`. Top-level agent persona and state files:
`AGENTS.md`, `FLEET.md`, `IDENTITY.md`, `MEMORY.md`, `SOUL.md`,
`ALFRED-ACCESS.md`, `HEARTBEAT.md`, `TOOLS.md`, `USER.md`,
`TOOL-CONCIERGE-INTRO.md`. Operator subdirs: `skills/` (contains four
tool-concierge-related skill folders), `memory/` (with a `.dreams/`
subdir — noted), `automations/`, `business/`, `clients/`, `outbox/`,
`projects/`, `satiety-projects/`, `scripts/`, `state/`, plus a
`satietyai-website/` Cloudflare-hosted site project that is clearly
unrelated to Concierge.

**5. `_legacy/agent-skills/` — Fleet-wide skill library**
16 files / 6 dirs. Five skill-category folders: `content-prep/`,
`distribution/`, `engagement/`, `intelligence/`, `shared/`. Per CLAUDE.md
v3, `shared/` contains `TOOL-MANIFEST.md` and the tool-awareness
`SKILL.md` — confirmed by symlink evidence at #7 below. Smallest of the
symlinks; likely high signal-to-noise for Phase A.2.

**6. `_legacy/tool-requests/` — Three-folder lifecycle store (authoritative)**
7 files / 4 dirs. `README.md` at root plus `pending/`, `resolved/`,
`archived/`. **This is the authoritative lifecycle implementation** called
out in CLAUDE.md v3. v2 blueprint describes a six-value status field
(`pending, approved, denied, installed, failed, deferred`) over this
three-folder physical layout — to validate in A.2 by reading sample
request files.

**7. `_legacy/openclaw-root/` — Full OpenClaw runtime**
1,155 files / 99 dirs. Superset of symlink 4 plus the operational runtime
for the OpenClaw fleet. Depth-1 entries worth calling out now:
- `cron/` *(mode 700)* — **candidate: cron housekeeping location**
- `memory/` — **candidate: semantic memory MCP runtime/data**
- `agents/` *(mode 700)* — agent configurations
- `skills/` — runtime skills (distinct from symlink 5; has
  `tool-awareness/`, `tool-concierge-intro/`, `tool-recommendation/`)
- `logs/` — runtime logs (may aid Phase E risk analysis)
- `openclaw.json` — main config, with 13 (!) backup/clobber variants
  suggesting a live-debugging surface
- `TOOL-MANIFEST.md` → **symlinks into `/home/satiety/.agent-skills/shared/`**
  — authoritative manifest location confirmed
- `SOUL.md` at the root (3,291 bytes) — distinct from
  `openclaw-workspace/SOUL.md` (9,714 bytes). **Two SOUL files.** Flag for
  A.2 reconciliation.
- Other runtime subsystems: `browser/`, `browser-extension/`, `canvas/`,
  `credentials/` (whatsapp), `delivery-queue/` (mode 700), `devices/`,
  `extensions/`, `identity/`, `media/` (mode 700), `prompts/`, `qqbot/`,
  `tasks/` (mode 700), `workspace-content/`.
- `.env` at root *(mode 600)* — **will not read**. Presence noted.
- `exec-approvals.json` *(mode 600)* — will not read; noted.

### Known overlaps (deduplication map)

| Canonical location | Also accessible via |
|---|---|
| `/home/satiety/.openclaw/workspace/` | symlink 4 (`openclaw-workspace`) AND symlink 7/workspace (`openclaw-root/workspace`) |
| `/home/satiety/.satiety-pipeline/outbox/tool-requests/` | symlink 3/outbox/tool-requests AND symlink 6 (`tool-requests`) |
| `/home/satiety/.agent-skills/shared/TOOL-MANIFEST.md` | symlink 5/shared AND symlink 7/`TOOL-MANIFEST.md` (itself a symlink) |

These are expected given the shortcut symlinks created in bootstrap; no
action beyond citing the canonical path in A.2 findings.

### Immediate observations for A.2 prioritization

Three file-location questions from the v3 plan's checkpoint list are
already partly answered:
- **Cron housekeeping location:** two candidates —
  `_legacy/toolconcierge/outbox-housekeeping.sh` AND `_legacy/openclaw-root/cron/`.
  Need to read both to determine which is active and which is spec.
- **Beta tool concierge MCP load/unload code:** not yet located. No
  obvious directory named for it under `toolconcierge/` (which is all
  markdown + two shell scripts). Must search `openclaw-root/` more
  deeply — likely under `agents/` or an MCP-server path not yet visible
  at depth 3.
- **Tool manifest:** located at
  `/home/satiety/.agent-skills/shared/TOOL-MANIFEST.md`, reachable via
  `_legacy/agent-skills/shared/` or via the symlink at
  `_legacy/openclaw-root/TOOL-MANIFEST.md`.

---

## A.2 Component deep-read

Every v3-plan component has been located. Where two files exist for the
same component, the **canonical** location — the one consumed by the
running system — is named. Duplicates and near-duplicates are called out
explicitly.

### A.2.1 Tool Manifest (TOOL-MANIFEST.md)

**Canonical:** `_legacy/agent-skills/shared/TOOL-MANIFEST.md`
(13,672 B, 256 lines, last touched 2026-03-24).
**Also reachable via:** `_legacy/openclaw-root/TOOL-MANIFEST.md` (symlink
into the canonical path).

Fleet-wide capability registry read by all agents before multi-step tasks.
Documents 5 agents (Alfred + Scout, Dispatch, Radar, Bridge) with ports,
profiles, roles; claims **7 MCP servers / 153 tools for Alfred** (Firefox
DevTools 24, Browser Control 8, Semantic Memory 8, Stripe 28, ElevenLabs
24, MailerLite 36, Cloudflare 25 — *see A.2.9 drift note*); the content
pipeline directory map; skills-system structure; per-agent memory paths;
**mcporter** as the ad-hoc-MCP escape hatch; a "BUILDABLE" list of
not-yet-built capabilities; API-key status table.

**OpenClaw coupling:** Heavy (embeds `openclaw --profile <name>` CLI
form as normative usage, MailerLite IDs, Discord-bot Windows path,
`~/.satiety-pipeline/` as agent-comms substrate). Structure generalizes;
content is OpenClaw-fleet-specific.

### A.2.2 Recommendation Behavior (tool-awareness / tool-recommendation skills)

Three parallel surfaces express the same behavioral pattern:

**Fleet-wide library (markdown):**
- `_legacy/agent-skills/shared/tool-awareness.md` (9,619 B, 193 lines) —
  "Plan Before You Execute." 5-step protocol: Task Decomposition →
  Manifest Check → Gap Report → Execute → Log to Wishlist.
- `_legacy/agent-skills/shared/tool-recommendation.md` (9,571 B, 143
  lines) — "Notice, Evaluate, Propose" during/after task execution.
  6-step: Notice → Check-before-proposing (4 sources) → Continue →
  Write → Notify (WhatsApp) → Log to memory.
- `_legacy/agent-skills/shared/tool-concierge-intro.md` (3,595 B) —
  orientation overview.

**Runtime-loaded (OpenClaw SKILL.md format, byte-identical content):**
- `_legacy/openclaw-root/skills/{tool-awareness,tool-concierge-intro,tool-recommendation}/SKILL.md`
- `_legacy/openclaw-workspace/skills/{tool-concierge-intro,tool-recommendation}/SKILL.md`

**Workspace-only extended skills (not in fleet library):**
- `_legacy/openclaw-workspace/skills/tool-discovery/SKILL.md` —
  search patterns by domain (CLI / Python / Node / Rust / MCP / data
  processing), green/yellow/red signal table for candidate filtering,
  discovery-request format. **This is the authoritative discovery spec.**
- `_legacy/openclaw-workspace/skills/tool-lifecycle/SKILL.md` — memory
  tagging convention (`tool-selection` tag + structured content string),
  promotion criteria (5+ uses / 30 days / recurring), demotion criteria
  (90+ days unused), weekly review protocol. **Deeper than anything the
  v2 blueprint summarizes.**

**Active enablement:** `openclaw.json` enables exactly three via
`skills.entries` — `tool-recommendation`, `tool-concierge-intro`,
`tool-awareness`. `tool-discovery` and `tool-lifecycle` are **not**
boot-enabled; they serve as reference material the active skills
cross-link to.

**Drafts (stale copies):** `toolconcierge/skill-tool-{concierge-intro,recommendation,discovery,lifecycle}.md`
— the first two byte-identical to the fleet-library versions, the latter
two earlier variants.

**OpenClaw coupling:** Medium. Behavioral pattern is platform-agnostic;
path references (`~/.agent-skills/`, `~/.openclaw/`, `openclaw-*.service`
systemd units, `mcporter`) are OpenClaw-native. Easily retargeted.

### A.2.3 SOUL.md additions

Two SOUL files, non-conflicting:

- `_legacy/openclaw-root/SOUL.md` (3,291 B, 46 lines) — titled
  "Tool-Awareness Behavioral Rules — Append these to your existing
  SOUL.md." **ADDITIONS-ONLY delta file.** Six sections: Capability
  Honesty, Planning Discipline, Feedback and Learning, Requesting
  Capabilities, Workaround Transparency, Tool Concierge.
- `_legacy/openclaw-workspace/SOUL.md` (9,714 B, 170 lines) — FULL
  integrated file. Core Truths / Boundaries / Vibe / Continuity, plus
  `## Tool Concierge` section containing the richer deployment of the
  additions (explicit Discovery subsection, Memory/learning, Promotion
  thresholds, Worker escalations, autonomous-install allow-list: npm
  globals / pip --user / single binaries / npx MCPs).
- `_legacy/toolconcierge/SOUL-workspace.md` (9,714 B) — snapshot of the
  workspace version.

Root = patch, workspace = patched-in-place living file. Alfred reads the
full one at boot.

### A.2.4 Three-folder lifecycle (pending / resolved / archived)

**Canonical physical root:** `/home/satiety/.satiety-pipeline/outbox/tool-requests/`.
Reachable via `_legacy/tool-requests/` (shortcut) or the longer
`_legacy/satiety-pipeline/outbox/tool-requests/`.

**Spec:** `_legacy/tool-requests/README.md` (3,779 B, 107 lines).
Defines filename convention (`YYYY-MM-DD-HHMM-<slug>.md`), the
**six-value status field** (`pending | approved | denied | installed |
failed | deferred`) on the first line of every file, cron transition
rules (any non-`pending` status → `resolved/`; `resolved/` age ≥30d →
`archived/`), the full request template (Request / Recommendation /
Approval / Install / First Use / Outcome), and role rules (Alfred writes,
workers escalate to Alfred, Lewie reviews).

**Current population:**
- `pending/`: 1 file (csvkit, status `pending`, awaiting decision since
  2026-04-16).
- `resolved/`: 5 files — tree, csvkit, ripgrep, sqlite3, pandoc (all
  status `installed`, 2026-04-13 → resolved 2026-04-14). Sample tree
  request is a complete example with full Approval/Install/First Use/
  Outcome sections.
- `archived/`: 0 files (none have aged 30 days yet).

**OpenClaw coupling:** Very low. Request template has **zero OpenClaw-
specific fields**. Status values are platform-agnostic. Only the physical
path (`~/.satiety-pipeline/...`) is Moltbot-specific — trivially
relocatable.

### A.2.5 Cron housekeeping script

**Canonical (ACTIVE):** `_legacy/satiety-docs/scripts/outbox-housekeeping.sh`
(1,836 B, 52 lines). **Confirmed active via user crontab:**

```
0 * * * * /home/satiety/satiety-docs/scripts/outbox-housekeeping.sh
```

Runs hourly at minute 0. No systemd timer involvement.

**Duplicate (STALE):** `_legacy/toolconcierge/outbox-housekeeping.sh`
(1,836 B) — byte-identical to canonical. Drafting snapshot.

**Behavior:**
1. Iterate `pending/*.md`. Read first line for `status:`. If status is
   `approved|denied|installed|failed|deferred`, `mv` to `resolved/`. If
   still `pending` and file age ≥ 7 days, log a FLAG entry.
2. Iterate `resolved/*.md`. If age ≥ 30 days, `mv` to `archived/`.
3. Always write a BEAT heartbeat line to
   `$HOME/.satiety-pipeline/outbox/housekeeping.log`.

**Runtime evidence:** `housekeeping.log` exists and accumulates entries
(confirmed in A.1).

**Not to be confused with `openclaw-root/cron/jobs.json`,** which is
OpenClaw's internal AT-TIME EVENT scheduler for one-off reminders (e.g.,
"Client Meeting Reminder - Monday," "Stripe key rotation reminder").
Payloads are `systemEvent` with reminder text. Unrelated to
tool-request lifecycle.

**OpenClaw coupling:** None. Pure bash + coreutils (`stat`, `date`,
`grep -oP`, `mv`). Lifts cleanly.

### A.2.6 Tool catalog (TOOL-CATALOG.md)

**Canonical (ACTIVE):** `_legacy/satiety-docs/TOOL-CATALOG.md` (5,471 B,
last audited 2026-04-14).
**Duplicate (stale by one day):** `_legacy/toolconcierge/TOOL-CATALOG.md`
(5,679 B, audited 2026-04-13). The older version still lists tree,
ripgrep, sqlite3, csvkit, pandoc under "NOT Installed"; the newer
canonical version has promoted them into "Installed."

Single-operator markdown file with tables of: 7 MCP servers; Installed
CLI tools (Core / Runtimes / Media / Browsers / Agent Infrastructure);
"NOT Installed (Known-Good Candidates)" — fd, bat, miller, xsv, htop, eza,
imagemagick, gh, docker — the promotion candidate pool; Python stdlib;
paid services with monthly cost; Catalog Maintenance protocol.

**Cross-reference with active config:** The 7-MCP-server claim in this
catalog disagrees with `openclaw.json` — see A.2.9.

**OpenClaw coupling:** Medium (MCP servers reference tool-prefix
conventions; CLI/services rows are generic).

### A.2.7 Shell tool functions (tool-functions.sh)

**Canonical (ACTIVE):** `_legacy/satiety-docs/scripts/tool-functions.sh`
(5,508 B, 158 lines). Sourced at login via `~/.bashrc`.
**Duplicate (STALE):** `_legacy/toolconcierge/tool-functions.sh` —
byte-identical.

Five public functions + two private helpers:
- `_tool_profile_config <profile>` / `_tool_profile_service <profile>` —
  map profile name (`default|content|distribution|intelligence|engagement`)
  to config path and systemd unit.
- `tool-on <profile> <server>` — enables MCP server via `jq` edit to
  `openclaw.json`, backs up to `.bak`, **restarts systemd service**,
  verifies active.
- `tool-off <profile> <server>` — mirror of `tool-on` (sets
  `enabled:false`, backs up, restarts).
- `tool-install-npm <package>` — autonomous `npm install -g` to
  `~/.npm-global` (no sudo).
- `tool-install-pip <package>` — autonomous `pip3 install --user`
  (no sudo).
- `tool-list <profile>` — prints MCP servers with ENABLED/DISABLED.

**This is the MCP load/unload mechanism — see A.2.11.**

### A.2.8 Wishlist log (tool-wishlist.md)

**Canonical:** `_legacy/openclaw-root/logs/tool-wishlist.md` (1,128 B,
28 lines).

**Current state:** Header comment + template only. **Zero actual entries
exist.** The last line is `<!-- Entries begin below this line -->` with
nothing below it.

Design-complete; traffic-empty. The `tool-awareness.md` skill documents
logging to the wishlist as protocol Step 5, but in practice agents go
straight to `pending/` requests (5 resolved requests exist). See Q5 in
A.4 about UI implications.

### A.2.9 Semantic Memory MCP server code

**Code location (OUTSIDE `_legacy/`):** `/home/satiety/moltbot-memory-mcp/`

Contents: `server.py` (14,466 B, the MCP server), `server.py.pre-flatten`
(16,608 B, pre-refactor backup), `run.sh` (243 B, stdio entry point),
`install.sh`, `migrate.py`, `requirements.txt`, `venv/`. **Python MCP
server, ~14 KB — small.**

**Data store:** `/home/satiety/.moltbot-memory-v2/` — ChromaDB persistent
store (`chroma.sqlite3` 290,816 B + two UUID-named collection directories).
Confirms v2 blueprint's "ChromaDB-based" framing.

**Invocation:** Per `openclaw-root/openclaw.json → mcp.servers.memory`:
```json
"memory": {
  "command": "/bin/sh",
  "args": ["-c", "/home/satiety/moltbot-memory-mcp/run.sh"],
  "env": { "MOLTBOT_MEMORY_DIR": "/home/satiety/.moltbot-memory-v2" }
}
```

**Tools exposed** (per manifest): `memory_store`, `memory_search`,
`memory_delete`, `memory_list`, `memory_update`, `memory_identity_get`,
`memory_identity_set`, `memory_stats`.

**DRIFT FLAG — manifest vs. active config:**
- **TOOL-MANIFEST.md (Mar 24 2026):** Alfred has 7 MCP servers / 153
  tools including Stripe, ElevenLabs, MailerLite, Cloudflare.
- **Active `openclaw.json` (Apr 16 2026 lastTouched):** Only 3 MCP
  servers — `memory`, `firefox`, `browser-control`. No Stripe, ElevenLabs,
  MailerLite, or Cloudflare under `mcp.servers` **or** under
  `plugins.entries`.
- **Evidence of migration:** Backup file
  `openclaw.json.pre-native-mcp-migration` (Apr 10 2026). Empty
  `openclaw-root/extensions/mcp-bridge/` dir.
- **Inference:** OpenClaw migrated from the MCP-Bridge-plugin
  architecture to native `mcp.servers` ~Apr 10; migration dropped the
  four API-based servers. The manifest is ~2 weeks stale.

Matters for Phase B: the v2 blueprint's "semantic memory MCP largely
exists" is correct (still running), but "7 MCP servers loaded" is
aspirational/historical. Active config is ground truth.

### A.2.10 MCP Bridge plugin

**Docs:** `_legacy/openclaw-workspace/docs/MCP-BRIDGE-GUIDE.md` (~400
lines) and `_legacy/openclaw-workspace/docs/ALFRED-MCP-REFERENCE.md`
(~180 lines, per-server tool reference).

**Code location on disk:** `_legacy/openclaw-root/extensions/mcp-bridge/`
**is empty.** The guide describes a TypeScript plugin (`index.ts` +
`openclaw.plugin.json`) that used JSON-RPC 2.0 over stdio to manage
Firefox DevTools + Browser Control + MCPMonkey. **The plugin files no
longer exist.**

**Status:** Deprecated. Superseded by native `mcp.servers` config. The
guide is historical documentation. Conceptual content (JSON-RPC over
stdio, tool discovery at startup, `servername_toolname` routing) is
generalizable; the specific implementation is gone.

**Implication:** No MCP Bridge plugin component to LIFT or EXTRACT in
Phase C. Concierge's Claude Code loader/proxy is genuinely new — informed
by the patterns documented here but not reusing code. See Q2.

### A.2.11 Beta Tool Concierge MCP load/unload code — **FOUND**

**Canonical:** `_legacy/satiety-docs/scripts/tool-functions.sh` (full
detail in A.2.7). The `tool-on` / `tool-off` shell functions ARE the
MCP load/unload mechanism.

**Mechanism:**
1. Edit profile's `openclaw.json` with `jq` to (un)set `enabled:false`.
2. Back up prior config to `.bak`.
3. `systemctl --user restart openclaw-<profile>.service`.
4. Sleep 3s, verify `is-active`, report.

**This is NOT hot-swap.** Every load/unload forces a systemd service
restart. Acceptable for the OpenClaw fleet (workers are mostly stateless;
Alfred recovers from filesystem memory). **Fundamentally incompatible
with a Claude Code session** — a restart would kill the active
conversation's tool context. Claude Code needs a different approach:
native MCP dynamic loading / `tools/list_changed` notifications / proxy
shim that masks backing-server swaps. Validates v2 blueprint's framing
of the Claude Code loader as genuinely new work.

**No separate "beta tool concierge" daemon/process exists.** The "beta
tool concierge" referenced in CLAUDE.md v2/v3 IS the composition of
`tool-functions.sh` + `outbox-housekeeping.sh` + `tool-requests/` folder +
SOUL.md additions + `agent-skills/shared/*.md`. **No compiled server.
No Python/Node service. Bash + markdown + cron orchestration.** Material
for Phase C classification.

**OpenClaw coupling:** Very high in the script (systemd units,
openclaw.json paths, profile conventions). Design pattern (edit config
→ restart service) is portable; specific script isn't.

### A.2.12 Other discovered components

- **mcporter** (`/home/satiety/.npm-global/bin/mcporter` v0.7.3) — ad-hoc
  MCP caller. Spawns a temporary server per call, no config changes. The
  manifest calls it "the bridge to Phase 3." Relevant prior art for
  Concierge's Claude Code loader.
- **OpenClaw AT-time scheduler** (`openclaw-root/cron/jobs.json` +
  `cron/runs/*.jsonl`) — one-off reminder jobs, unrelated to tool-request
  lifecycle. Noted for scope clarity.
- **OpenClaw internal SQLite** (`openclaw-root/memory/main.sqlite`,
  610 KB) — NOT the semantic memory ChromaDB. Likely OpenClaw's
  task/session state DB. Out of scope.
- **openclaw.json backup explosion** — 13 backup variants (`.bak.*`,
  `.backup*`, `.clobbered.*`, `.pre-chrome-switch`,
  `.pre-native-mcp-migration`, `.pre-4.12-backup`, `.pre-plugins-allow`).
  Evidence of active config churn and at least one failed recovery.
  Not scope-relevant; confirms the config-edit-restart load/unload
  pattern has been stress-tested.
- **TOOL-CONCIERGE-OVERVIEW.md** (`_legacy/toolconcierge/`, 10,618 B) —
  richest single-file conceptual description of the Concierge system,
  close match to v2 blueprint prose. CLAUDE.md v3's "richest reference"
  pointer confirmed.
- **Worker escalation** (`toolconcierge/worker-tool-escalation.md`,
  1,603 B, referenced by SOUL but not deep-read). Dual-channel:
  real-time `sessions_send` + filesystem `worker-*` prefix in `pending/`.
- **phase-2-test-scenarios** — identical files at
  `toolconcierge/phase-2-test-scenarios.md` and
  `satiety-docs/test-scenarios/phase-2.md` (9,251 B each). Pre-dates v2
  framing but useful as demo-fixture source material.
- **satietyai-website** (`openclaw-workspace/satietyai-website/`) —
  Cloudflare Pages/Worker marketing site with own `.git`. Not
  Concierge-related. Confirmed by Q4 exclusion.

---

## A.3 Surprise findings

Twelve items worth Lewie's attention, beyond what the v2 blueprint or
CLAUDE.md v3 made obvious.

**S1 — "Beta tool concierge" is not a daemon.** It's a composition of
bash + markdown + cron + SOUL rules (see A.2.11). No compiled server,
no Node/Python service, no MCP server of its own. Much lighter than the
word "beta" suggested; simplifies Phase C significantly.

**S2 — The MCP Bridge plugin code is gone.** `MCP-BRIDGE-GUIDE.md`
describes a TypeScript plugin at `openclaw-root/extensions/mcp-bridge/`;
that dir is empty. Migration to native `mcp.servers` happened ~Apr 10
(confirmed by `.pre-native-mcp-migration` backup). Docs are now
historical.

**S3 — Manifest vs. active config drift is ~14 days stale.** Manifest
claims 7 MCP servers for Alfred (153 tools). Active `openclaw.json`
has 3 (memory, firefox, browser-control). Stripe, ElevenLabs, MailerLite,
Cloudflare are no longer loaded. Demo narrative needs to reconcile this.

**S4 — Wishlist is empty.** `tool-wishlist.md` has been template-only
for its entire lifetime. Skill docs treat Step 5 ("log to wishlist") as
mandatory, but in practice agents go straight to `pending/` requests.
The v2 blueprint's "Wishlist Patterns" UI section would render nothing
today.

**S5 — Canonical vs. drafts filesystem layout.** `satiety-docs/scripts/`
+ `agent-skills/shared/` are the **canonical live paths** (crontab points
at one, `~/.bashrc` sources the other, agents read the third).
`toolconcierge/` is the **design/drafting workspace** — all its scripts
and skill docs are byte-identical (or slightly newer-dated) copies of
the live ones. `toolconcierge/` is mostly reference-only content;
Phase C will largely LIFT its docs, not deploy its code.

**S6 — `satiety-docs/TOOL-CATALOG.md` is canonical, not `toolconcierge/`.**
Apr-14 version has promoted five tools into "Installed"; Apr-13
`toolconcierge/` copy still lists them as candidates.

**S7 — Three-folder lifecycle schema is genuinely portable.** Zero
OpenClaw-specific fields in the request template. Status values are
platform-agnostic. Filename convention is timestamp+slug. The whole
schema is markdown-native. Clean LIFT in Phase C — extract-worthy part
is only the *code that writes/reads these files*, not the format.

**S8 — Load/unload requires a service restart, not hot-swap.** Informed
for the OpenClaw fleet (workers don't hold conversation state).
**Incompatible with Claude Code sessions** — the whole point of the
Claude Code adapter is swapping tools without losing session context.
Validates v2 blueprint framing of the loader as "genuinely new work."

**S9 — Two skill storage models coexist.** Markdown files at
`agent-skills/shared/*.md` (fleet library) AND `SKILL.md` folders at
`openclaw-root/skills/<name>/SKILL.md` (OpenClaw skill loader). The
boot-enabled skills match the SKILL.md folders. `tool-discovery` and
`tool-lifecycle` exist only under `openclaw-workspace/skills/` and are
**not enabled** — reference material only. See Q6.

**S10 — The semantic memory MCP is a 14 KB Python file.** `server.py`
at `/home/satiety/moltbot-memory-mcp/server.py` is small; ChromaDB does
the heavy lifting. The v2 blueprint's "add API wrapper for non-agent
callers" is a small wrapping job around a small script.

**S11 — mcporter already ships "load on demand."** Binary at
`/home/satiety/.npm-global/bin/mcporter` v0.7.3 provides ad-hoc MCP
calls without config changes, via per-call temporary server spawn. The
manifest calls it "the bridge to Phase 3." Relevant prior art for the
Concierge Claude Code loader — options: build on mcporter's pattern,
call it directly, or replace with persistent-connection version.

**S12 — Skills spread across three locations, non-identically.**
Summary table:

| Skill | fleet library (`agent-skills/shared/`) | openclaw-root `skills/<n>/SKILL.md` | openclaw-workspace `skills/<n>/SKILL.md` | enabled? |
|---|---|---|---|---|
| tool-awareness | yes | yes | no | yes |
| tool-concierge-intro | yes | yes | yes | yes |
| tool-recommendation | yes | yes | yes | yes |
| tool-discovery | no | no | yes | no |
| tool-lifecycle | no | no | yes | no |

The runtime reads SKILL.md folders, not the fleet library markdown
directly — those appear to feed something else (or are documentation of
the same concepts maintained separately).

---

## A.4 Open questions for Lewie

**Q1 — Extend `_legacy/` to cover the semantic memory MCP code.**
`/home/satiety/moltbot-memory-mcp/` (code, 14 KB Python server) and
`/home/satiety/.moltbot-memory-v2/` (ChromaDB store) are outside all
current symlinks. I need the code accessible to cite file:line in Phase
B. Propose:
- 8th symlink: `_legacy/memory-mcp/` → `/home/satiety/moltbot-memory-mcp/`
- (optional 9th): `_legacy/memory-mcp-data/` → `/home/satiety/.moltbot-memory-v2/`

Confirm and I'll add. The code one is needed; the data one is
nice-to-have.

**Q2 — Is the MCP Bridge plugin architecture dead for our purposes?**
`MCP-BRIDGE-GUIDE.md` is rich but describes the pre-migration
implementation (plugin gone, config superseded). Treat as historical-only
for Concierge planning, or is there reason to mirror the bridge pattern
for the Claude Code adapter (e.g., running our own stdio-proxy over
spawned MCPs)? My instinct is historical-only — confirm.

**Q3 — How should the manifest/config drift be handled?** Manifest
claims 7 MCP servers; active config has 3. If the demo narrative leans
on "7 servers / 153 tools," the drift becomes visible. Options:
(a) out of scope for Phase A — flag in Phase B;
(b) you update manifest separately before Day 1;
(c) Concierge's UI renders active config as source of truth, making
drift irrelevant (my preference — aligns with the UI plan).

**Q4 — `toolconcierge/` repo classification intent.** All its scripts
and skill docs are byte-identical or slightly-older copies of canonical
locations. Is this a repo to preserve as a design artifact (LIFT as
`docs/legacy-toolconcierge/`) or safe to archive after Phase A? Affects
how Phase C frames its several byte-identical duplicates.

**Q5 — Wishlist: design-complete, zero traffic.** v2 blueprint includes
a "Wishlist Patterns" UI section sourced from `tool-wishlist.md`. That
file has no real entries. Options:
(a) cut to two UI sections for v1;
(b) seed the wishlist retroactively from resolved requests;
(c) keep the section, render "no patterns yet" as a legitimate empty
state (my preference — honest empty states are fine).

**Q6 — Intentionally reference-only skills.** `tool-discovery` and
`tool-lifecycle` SKILL.md live only under `openclaw-workspace/skills/`
and are NOT in `openclaw.json.skills.entries`. The three enabled skills
cross-reference them. Reference-only by design, or incomplete wiring?
For Phase B I'll treat them as reference material unless you indicate
they should be boot-loaded.

---

*Phase A deliverable complete pending your review of A.3 surprises and
A.4 open questions. Session handoff snapshot to be written after review
closes the phase.*
