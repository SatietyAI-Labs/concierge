# Concierge Blueprint (v2)
### Platform-agnostic tool awareness layer — extraction, generalization, and UI build

---

## What changed from v1

The v1 blueprint described Concierge as a system to design and build. After
reviewing the actual existing OpenClaw codebase and the system overview
document, that framing was substantially wrong. The truth:

**Concierge already exists, fully designed and running in production inside
OpenClaw.** Tool Manifest, recommendation behavior (SKILL.md +
SOUL-ADDITIONS.md), three-folder lifecycle with cron housekeeping,
discovery engine, semantic memory integration, promotion/demotion criteria,
multi-agent escalation, autonomous installation — all of it exists, all of
it works.

The hackathon week is therefore not a build-from-scratch project. It is an
**extraction, generalization, and adapter-build project** with a real UI
added on top. This is significantly more achievable than the v1 framing
suggested.

---

## The mission, restated

Lift the working Concierge logic out of OpenClaw-specific assumptions, wrap
it as a platform-agnostic service with a clean API, build a Claude Code
adapter so the same system can serve Claude Code sessions the way it
currently serves the OpenClaw fleet, and add a real operator UI that makes
the whole thing visible and manageable from a browser.

The OpenClaw system keeps running independently. The OpenClaw adapter is
explicitly Phase 2 work — not part of the hackathon week. The demo points
at the production OpenClaw system as proof the approach works without
requiring it to be wired into the new architecture.

---

## Architecture (revised)

The component vocabulary stays the same as v1, but the build status of each
component changes dramatically. Here is the honest map.

### Catalog Service
**Status: largely exists.** TOOL-MANIFEST.md is the working catalog,
maintained by Lewie, read by all agents. It tracks active capabilities,
ownership per agent, MCP server status, transport types, costs and
limitations.

**What's needed:** Generalize the schema so a tool entry doesn't assume
OpenClaw-specific concepts (Alfred/Scout/Bridge agent IDs, openclaw.json
paths, SatietyAI pipeline references). Move from a single markdown file to
a structured store the UI and adapters can both query (likely SQLite for
hackathon, with markdown-export so the human-readable form is preserved).

### Recommendation Engine
**Status: largely exists as agent behavior.** The 5-step protocol
(decompose → manifest check → gap report → execute → log) is encoded in
SKILL.md and reinforced by SOUL.md additions. Agents already do this when
they hit a capability gap.

**What's needed:** Lift the protocol out of agent personality files and
into a callable service. The behavior becomes an API endpoint
(`POST /recommend` with task context returns ranked recommendations) that
any harness — including a Claude Code session — can call. The discovery
engine logic (package registries, awesome-lists, GitHub stars filter)
becomes part of the same service.

### Memory Service
**Status: exists.** The semantic memory MCP (ChromaDB-based, per-agent
isolation, all-MiniLM-L6-v2 embeddings) already stores tool decisions tagged
`tool-selection`. Identity notes already maintain compact persistent
preferences.

**What's needed:** Make the memory service queryable from the new Concierge
core (not just from agents). Define the API for "given this task context,
find similar past decisions" so the recommendation engine can use it
without going through OpenClaw plumbing. The actual ChromaDB store and the
existing memory MCP keep running as-is — the new code just talks to them.

### Loader/Proxy Layer
**Status: this is where the real new work concentrates.** The existing
system has autonomous installation logic (npm-global, pip-user, single-file
binaries, MCP via npx) but the live MCP load/unload mechanism is the
component most likely to need fresh work for Claude Code.

**What's needed:** A Claude Code-specific adapter that knows how to
load/unload MCP servers in a Claude Code session. Lewie's existing
load/unload work for OpenClaw provides design patterns; the Claude Code
implementation is genuinely new code. The OpenClaw adapter (Phase 2) will
mirror this shape using the existing OpenClaw mechanisms.

### Concierge Agent Interface
**Status: exists in OpenClaw as a behavioral pattern.** Agents read the
manifest, write requests to the pipeline, log to the wishlist. This is the
"how the agent talks to Concierge" surface, currently file-based.

**What's needed:** Define the same surface as a callable API so any
agent — Claude Code session, Claude Desktop session, future harnesses —
can interact with Concierge through HTTP or MCP, not just by reading and
writing files. The file-based interface stays valid and continues to work
for OpenClaw; it just stops being the only option.

### Lifecycle State Machine
**Status: exists, working, and is more sophisticated than v1 envisioned.**
The three-folder pipeline (`pending → resolved → archived`) with a
six-value status field (`pending, approved, denied, installed, failed,
deferred`), structured markdown request schema, role separation, 30-day
archival, and hourly cron promotion is already running.

**What's needed:** Wrap the existing folder structure with an API the UI
can call (read pending requests, render them, post approval/denial,
trigger install). The cron job continues to do what it does. Promotion
criteria for tools (5+ uses in 30 days) and demotion criteria (90+ days
unused) are codified — the hackathon work is making those criteria visible
in the UI and exposing the operator action via buttons.

### UI / Dashboard
**Status: does not exist.** This is genuinely new work and a centerpiece of
the hackathon demo.

**What's needed:** See the UI section below.

### Failure Feedback Loop
**Status: exists as the wishlist log.** Agents already log capability gaps
with frequency and priority. The pattern recognition (3+ occurrences →
candidate for permanent install) is documented but currently manual.

**What's needed:** Surface wishlist patterns in the UI. Promote
high-frequency wishlist items to pending requests with one click. Hackathon
scope: read-only view. Post-hackathon: the click-to-promote button.

### Cross-Agent / Cross-Harness Learning
**Status: exists within the OpenClaw fleet.** Multi-agent routing already
works — workers escalate to Alfred, Alfred coordinates. Tool decisions
made by one agent become memory entries other agents can find.

**What's needed:** Generalize "agent" to mean "any client of Concierge"
rather than "an OpenClaw-fleet agent." A Claude Code session and an
OpenClaw worker both become equal citizens of the Concierge memory and
catalog. This falls out naturally from the API generalization above; not
much extra work.

---

## The UI in detail

This is the piece with no prior implementation, so it warrants its own
section. Designed to be built fast with prefab styling and minimal
frontend complexity.

### Tech stack

- **Backend:** FastAPI (same service that exposes the Concierge API to
  agents)
- **Templates:** Jinja2 server-rendered HTML
- **Interactivity:** HTMX for dynamic updates without a SPA framework
- **Styling:** Pico.css (semantic HTML gets clean styling automatically)
  or Tailwind via CDN if more control is needed
- **No build step.** No npm, no webpack, no Vue/React. Edit a template,
  refresh, see the change. This is the whole point.

### Why this stack

- Lewie has never built a UI. Every tool added to the stack is a thing he
  has to learn while also building. Pico.css means classes like
  `<table>` and `<button>` look polished without writing CSS.
- HTMX keeps interactivity declarative (`hx-post`, `hx-target`, no
  JavaScript event handlers).
- FastAPI is what the Concierge service backbone needs anyway — the UI
  is essentially "free" since it shares the API.
- Demo-friendly: judges open a browser, see a clean dashboard, no install
  required.
- Future-friendly: this UI is what runs on the GPU server later in the
  hardware rollout. Same code, different host.

### Hackathon-week scope (three sections)

**1. Tool Registry**
Browsable list of every tool in the catalog. Hierarchical:
- Top level: packs (MailerLite suite, Stripe, Firefox DevTools, etc.)
- Expandable to sub-tools within each pack
- Each row shows: name, lifecycle state, transport type, owning agent(s),
  last used, success rate
- Filter by state (pending/used/loaded/retired) and search by name

**2. Pending Requests Inbox**
Renders the contents of `outbox/tool-requests/pending/`:
- One card per request with the structured markdown nicely formatted
- Approve / Deny / Defer buttons (these update the status line in the
  markdown file, which the existing cron picks up)
- Optional comment field for approval conditions
- Replaces the "edit the markdown file by hand" workflow for the operator

**3. Health / Stats Bar**
A compact strip across the top of the dashboard:
- Token win counter (lightweight-first preference savings this week)
- Active MCP servers / total MCP servers
- Cron last-run timestamp + heartbeat status
- Top 3 most-used tools

### Post-hackathon UI sections (Phase 2)

- **Lifecycle Activity / Timeline** — chronological event stream
- **Wishlist Patterns** — aggregated gap log with auto-flagging
- **Cross-Agent Map** — visual of which agent has what
- **Settings** — adjust promotion/demotion thresholds, auto-approve rules

These aren't built during hackathon week. They get sketched as templates
for later but are not part of the demo.

---

## What's genuinely new vs. what gets lifted

Here is the honest accounting. This is the most important table in this
document because it sets the realistic scope for the build week.

| Component | Status | Hackathon work |
|---|---|---|
| Tool Manifest (catalog data) | Exists | Schema generalize + SQLite store |
| Recommendation behavior | Exists in SKILL.md | Lift to callable API endpoint |
| Discovery engine | Exists | Generalize to harness-agnostic |
| Semantic memory | Exists | Add API wrapper for non-agent callers |
| Three-folder lifecycle | Exists | Add UI-facing API endpoints |
| Cron housekeeping | Exists | Leave alone, document it |
| Promotion/demotion criteria | Exists in docs | Codify in API + UI |
| Wishlist log | Exists | Add read-only UI view |
| Multi-agent escalation | Exists | Generalize "agent" concept |
| Autonomous install | Exists | Lift logic out of OpenClaw paths |
| MCP load/unload (Claude Code) | New | Build the adapter |
| Claude Code adapter (overall) | New | Build it |
| FastAPI core service | New | Build it |
| UI (3 sections) | New | Build it |
| Demo scenario + recording | New | Build it |

Read the right column. That's the hackathon week. Everything in the middle
column either gets a thin extraction layer or a generalized wrapper, but
the hard architectural and behavioral work is already done.

---

## Demo scenario (refined)

A clean three-minute demo that tells the right story:

> "I open the Concierge dashboard. You see the Tool Registry — every tool
> across my system, organized into packs. MailerLite suite, 36 tools,
> currently loaded-on-boot because I use it constantly. Firefox DevTools,
> 24 tools, also loaded. Stripe, 28 tools, loaded but I'd flag it for
> review.
>
> Now I switch to a Claude Code session running in another window. I ask
> it to analyze a CSV. Concierge sees the intent. Watch the dashboard —
> a new entry appears in the Pending Requests Inbox: 'csvkit suggested for
> CSV processing tasks. Confidence: high. Source: discovery.' I click
> Approve. The cron picks it up within a minute, the install runs
> autonomously, and now Claude Code has csvkit available.
>
> Same task again. Now Concierge prefers the lightweight option: csvkit's
> `csvstat` over a 200-line pandas script. Watch the token counter at the
> top of the dashboard — that's the running savings from lightweight-first
> preference. Across the week so far it's saved roughly 40K tokens.
>
> The same Concierge brain, the same catalog, the same memory — it's also
> serving my OpenClaw fleet running in production right now. When my
> production agents hit a gap, requests show up in the same inbox. I
> approve them once, and every harness benefits.
>
> Cross-harness learning, lightweight-first preference, lifecycle
> automation, and a real interface — Concierge."

That is the demo. Everything in the build serves those three minutes.

---

## Open decisions deferred to Phase A

A few things genuinely worth deciding once Claude Code has done the
inventory and we know the actual file layout:

- **Where does the Claude Code MCP load/unload code live?** Is it a wrapper
  process, a direct call to the Claude Code MCP API, or does it require a
  proxy?
- **Does the existing OpenClaw load/unload code lift cleanly into the
  Claude Code adapter, or is it OpenClaw-specific enough that the Claude
  Code version is a fresh implementation guided by the existing patterns?**
- **Where does the cron housekeeping script actually live?** It's mentioned
  in the overview doc but not yet found at a specific path.
- **Should the catalog SQLite store also export markdown for human
  readability?** Probably yes (preserves the audit trail value of the
  current manifest), but worth confirming.

These are architecture decisions, not blockers. We make them after Phase A
inventory, before Phase F build plan.

---

## Build week plan (revised target: substantive completion by Day 4)

Detailed day-by-day plan lives in the v2 execution plan document. Summary
here:

- **Day 1 (Tuesday):** Core service skeleton, schema generalization, lift
  catalog into SQLite store. Set up FastAPI scaffold.
- **Day 2 (Wednesday):** Memory service API wrapper. Recommendation engine
  endpoint. Lifecycle API endpoints (read pending, post approval).
- **Day 3 (Thursday):** Claude Code adapter — MCP load/unload, gap report
  injection, recommendation pull/push.
- **Day 4 (Friday):** UI — Tool Registry section, Pending Requests Inbox
  section, Health/Stats bar. End-to-end integration test.
- **Day 5 (Saturday):** Bug fixes, demo scenario rehearsal, polish.
- **Day 6 (Sunday):** Demo recording, README, project description,
  submission. Buffer day.

The Day 4 substantive-completion target gives genuine cushion for the
demo. If Days 1-3 run long, Day 5 absorbs the slack. If Days 1-3 run on
time, Days 5-6 become genuine polish time, which is rare in hackathons and
shows in the final result.

---

## Phase 2 (post-hackathon) roadmap

These get explicitly set aside during the hackathon and revisited the
following week:

- **OpenClaw adapter** — wire the new Concierge core back into the OpenClaw
  fleet, replacing the file-only interface with the API where useful.
- **Additional UI sections** — Lifecycle Timeline, Wishlist Patterns,
  Cross-Agent Map, Settings.
- **Claude Desktop adapter** — third harness.
- **Telemetry dashboard expansion** — more detailed stats, export
  functionality.
- **Course integration** — Concierge becomes a featured case study in
  "Building With AI: From Tools to Agent Management."
- **Local AI workstation deployment** — Concierge service migrates from
  laptop to GPU server when the hardware rollout reaches that phase.

---

## One thing worth keeping in mind

Almost every hackathon submission is "we got it working an hour before
the deadline." Yours is going to be "we built this on top of a system that
has been running in production for months." That's a fundamentally
different posture and the demo should reflect it. Confidence comes from
having actually used the thing. Don't fake it; lean into it.
