# Concierge: Platform-Agnostic Tool Awareness Layer
### A planning document and build blueprint

---

## Executive Summary

**Concierge** is a policy and memory layer that sits between any AI agent and its tool universe. It solves what we've been calling **tool myopia** — the problem that agents (Claude Code, OpenClaw, Cursor, Claude Desktop, custom harnesses) only consider the tools currently in their context, never proactively recommend tools they don't have, and have no memory of which tools actually earn their keep over time.

Concierge gives agents **tool agency**: it watches what the agent is trying to do, knows the broader catalog (MCP servers, CLI commands, lightweight HTTP APIs, skills), proactively surfaces or loads the right tool for the moment, prefers lightweight options when they fit, and runs a lifecycle that promotes tools through `pending → used → loaded-on-boot` and retires the ones that stop earning their place.

It is **agent-harness-agnostic by design**. Same Concierge runs across Moltbot (OpenClaw on WSL2), Claude Code, Claude Desktop, and anything else you bolt on later.

---

## Hackathon Context (For Reference)

**Event:** Built with Opus 4.7 — a Claude Code virtual hackathon
**Host:** Cerebral Valley + Anthropic
**Dates:** Week of April 21, 2026
**Format:** Fully virtual
**Prize pool:** $100K in Claude API credits, distributed to winning teams
**Per-participant credits:** ~$500 in API credits for accepted builders
**Application:** Submitted Sunday, April 19, 2026 — pending review

If accepted, the hackathon week is the catalyst for shipping the v1 demo. If not, the same blueprint still drives the build — the hackathon is timing, not necessity.

---

## The Core Problem: Tool Myopia

Every agent harness today suffers from some combination of these failure modes:

**Static tool surface.** Tools are configured at startup. Adding or removing them mid-session is somewhere between awkward and impossible. OpenClaw practically wants a reboot. Claude Code's mid-session MCP loading is workable but uneven. Claude Desktop's blue-switch toggle works for remote connectors but desktop extensions often need a restart.

**No proactive recommendation.** The agent never says "you should give me access to X" or "actually, a curl one-liner would beat this MCP round-trip." It just barrels ahead with what's loaded, even when a lighter tool would do the job.

**Heavy bias.** MCP servers are the loudest option in the room and tend to dominate. CLI commands and lightweight public APIs that could solve a task in three lines get ignored, even when they'd be faster, cheaper, and easier on the context window.

**No memory.** The agent has no idea which tools have actually been useful in the past. A tool that gets loaded once and never used again sits there forever, eating tokens. A tool that quietly does heavy lifting every day has the same status as one that's never been touched.

**No awareness of cost.** Tool definitions can consume 60K+ tokens before the conversation even starts (real reported numbers from heavy MCP users). The agent has no concept that loading a tool has a price.

Anthropic has already partially addressed the last point with `tool_search` (deferred loading by default in Claude Code) and the "Load tools when needed" mode in Claude Desktop's connector menu. Those are valuable primitives — but they're reactive, coarse-grained, have no learning, and don't address recommendation, lifecycle, or lightweight-first preference. **They're plumbing. Concierge is the brain.**

---

## How Claude's Existing Tool Ecosystem Actually Works

Understanding what's already shipped is critical so Concierge layers on top instead of duplicating. There are roughly four layers in play:

**Layer 1 — Connector toggle (the blue switch).** Per-chat on/off for remote connectors (Gmail, Drive, Notion, etc.) and desktop extensions. When OFF, those tool definitions are not sent to the model. Zero context cost. Toggling ON mid-chat *does* activate the tool for subsequent turns (tool definitions are sent fresh each API call), but the model doesn't know to reorient or retry — it just sees the new tools on the next turn.

**Layer 2 — "Tool access" mode in the Connectors menu.** Three modes: Auto (default), Always Available, On Demand. The lazy-load setting means a connector's tool descriptions only enter context when the model judges them relevant to the current message.

**Layer 3 — Tool Search in Claude Code.** Newer and more aggressive. Only tool *names* load at session start; the agent uses a search tool to discover full schemas when needed. Enabled by default. Cuts a 67K-token tool overhead down dramatically.

**Layer 4 — Skills.** Folders of best-practices and instructions (like the docx, pptx, pdf skills). Loaded on demand when the model decides they're relevant. A different shape from MCP tools — they're guidance, not callable APIs — but they live in the same context-budget conversation.

**Hot-swap reality across transports:**
- **Remote MCP connectors** (cloud-brokered, like Gmail/Notion) — flip cleanly mid-chat. The toggle takes effect on the next API turn.
- **Stdio MCP servers** (local processes) — workable but rougher; killing/respawning processes is doable but state can leak. This is the OpenClaw pain point.
- **Desktop extensions** — often require an app restart to pick up changes. Anthropic's own troubleshooting docs tell users to restart Desktop when toggles aren't taking effect.
- **HTTP/SSE MCP servers** — connection-based, generally more flexible than stdio.

The takeaway: **a proxy or shim layer is going to be part of Concierge whether you want it or not.** That's not a workaround — that's where the intelligence lives.

---

## The Concierge Concept

### Five core capabilities

1. **Unified tool catalog** — MCP servers, CLI commands, lightweight HTTP APIs, and skills all live in the same registry, treated as peers. Each entry has metadata: capability tags, cost (token weight, latency, dollars), reliability score, dependencies, transport type.

2. **Proactive recommendation** — Concierge watches the agent's stated intent and current task, infers what tooling would help, and surfaces or loads it *before* the agent gets stuck. This is the missing "tool agency" piece. If the user asks the agent to scrape a webpage and only an MCP browser server is loaded but a `curl + grep` chain would do, Concierge says so.

3. **Lightweight-first preference policy** — Given two tools that can solve a task, prefer the cheaper one. A 3-line bash command beats a 600-token MCP server when the bash command will actually work. This single policy alone could cut typical agent context usage in half.

4. **Lifecycle memory** — Tools move through states based on actual usage:
   - `pending` — suggested but unproven (Concierge thinks this might help; agent hasn't used it yet)
   - `used` — invoked at least once on a real task
   - `loaded-on-boot` — proven valuable enough to live in default context
   - `retired` — hasn't earned its keep; archived from active catalog
   
   The agent's tool surface evolves to fit how the user actually works, with no manual curation.

5. **Hot-swap layer** — A proxy/shim that handles the messy transport-specific reality of loading and unloading tools mid-session. Knows which transports support clean swaps and which need workarounds (your OpenClaw experience translates directly here).

---

## Platform-Agnostic Architecture

Concierge has to work across at least three very different harnesses (OpenClaw, Claude Code, Claude Desktop) plus whatever shows up next. That constraint forces good design.

### Component breakdown

**The Catalog Service** is the source of truth for all tools the user could ever use. It's a database (start with SQLite for the hackathon; PostgreSQL later when your local AI workstation comes online) holding tool entries with rich metadata. The catalog doesn't care which agent is asking — it just answers "here's what exists, here's what each one costs, here's what each one is good at."

**The Recommendation Engine** is where Opus 4.7 lives. Given the agent's current task context (last few messages, stated intent, files in scope), it reasons about which tools from the catalog would help — with explicit preference for lightweight options. Output is a ranked list of recommendations with confidence scores and rationale. Critically, this runs *async* from the agent loop so it doesn't slow the primary conversation.

**The Memory Service** tracks every tool invocation across every harness: which tool, what task, success or failure, latency, tokens consumed, agent feedback. This is the data that drives lifecycle promotions and retirements. Stored as event logs (append-only) plus a derived state table per tool. Over weeks, this becomes the most valuable asset in the system — a personalized map of which tools genuinely earn their place in *your* workflow.

**The Loader/Proxy Layer** is the harness-specific adapter. One adapter per harness (OpenClaw, Claude Code, Claude Desktop). This is the only layer that knows the messy details of how a given harness loads and unloads tools. It exposes a uniform interface upward (`load(tool_id)`, `unload(tool_id)`, `list_active()`) and translates that into whatever the harness actually needs — kill/respawn a process, send an MCP `tools/list_changed` notification, modify a config file and restart, or use the harness's own toggle API where one exists.

**The Concierge Agent Interface** is how the agent itself talks to Concierge. Two channels:
- **Pull** — agent calls Concierge as a tool: "what should I have loaded for this task?"
- **Push** — Concierge proactively injects messages into the agent's context: "Postgres tool is now available; consider re-attempting the prior request" or "you're about to use the MCP browser tool — a curl + grep would work here for ~200 tokens vs. ~2000."

### The lifecycle state machine in detail

```
                    ┌──────────────┐
                    │   DISCOVERED │  (catalog knows it exists)
                    └──────┬───────┘
                           │ Concierge surfaces it
                           ▼
                    ┌──────────────┐
                    │   PENDING    │  (recommended, unproven)
                    └──────┬───────┘
                           │ agent invokes it on real task
                           ▼
                    ┌──────────────┐
                    │     USED     │  (proven on at least one task)
                    └──────┬───────┘
                           │ used N times across M sessions
                           ▼
                    ┌──────────────┐
                    │ LOADED-ON-BOOT│ (default context citizen)
                    └──────┬───────┘
                           │ unused for X days / failure rate spikes
                           ▼
                    ┌──────────────┐
                    │   RETIRED    │  (archived, can be revived)
                    └──────────────┘
```

The thresholds (N uses, M sessions, X days unused) start as simple constants and become learned parameters once you have enough data.

---

## Additional Avenues Worth Considering

These came up implicitly in our conversation but you didn't name them directly. Worth thinking about for the longer-term roadmap:

**Failure feedback loops.** When a tool fails (returns garbage, times out, throws an error), that should affect its lifecycle standing. A tool that fails three times in a row gets demoted regardless of past performance. This is harder than it sounds because "failure" isn't always obvious from the tool response — sometimes you only know it failed because the agent had to retry with a different tool. Worth instrumenting from day one.

**Tool composition / chains.** Some tasks are best solved by *combinations* of lightweight tools (e.g., `curl | jq | grep` is a more efficient web scraper than most MCP browser servers for simple cases). Concierge could eventually recommend not just individual tools but *chains*. This is where the lightweight-first preference really shines.

**Cost-aware routing.** Your hybrid local/cloud AI inference plan (Ollama + Claude Code, four-phase rollout) means some tools should prefer local execution and some should prefer cloud. Concierge could route tool calls based on cost, latency, and current resource availability. This becomes a much bigger deal as your local hardware comes online.

**Cross-agent learning.** Moltbot's tool usage on WhatsApp and your Claude Code usage on Windows are *both* feeding the same memory layer. A tool that earns its place in one harness gets a head start in the other. This is one of the most underrated payoffs of platform-agnostic design — your agents share institutional knowledge without sharing context.

**Permission scoping per task context.** Right now Claude Connectors have global permission levels (always allow, ask first, never). A more sophisticated system would scope permissions by task type — e.g., "the Postgres tool can write during database tasks but is read-only in general code review." Concierge sits in the right place architecturally to enforce this.

**Skills as first-class catalog citizens.** You're already thinking about SKILL.md as part of Moltbot's tool-awareness architecture. Treat skills with the same lifecycle as tools — pending, used, loaded-on-boot, retired. A skill that consistently helps gets promoted; one that never gets pulled in gets archived.

**Telemetry for *you*.** Concierge will know more about your actual agent usage than any other system. A simple dashboard showing "tools used this week, tools that earned their place, tools that got retired, biggest token wins from lightweight substitutions" becomes both genuinely useful and a really compelling demo asset.

**Graceful degradation when catalog is offline.** What happens when Concierge itself is down? The agent should fall back to its native tool list and keep working. Worth designing for from the start so Concierge becomes additive, never load-bearing.

---

## Integration with Your Existing Systems

You're not building Concierge in a vacuum — it needs to slot into a constellation of things you've already built. Here's how the pieces fit:

**Moltbot (OpenClaw + WSL2 + WhatsApp)** is the production test bed. The TOOL-MANIFEST.md, SKILL.md, and SOUL.md components you've been building are already pointed in the same direction as Concierge — they're describing tool awareness from the agent side. Concierge is the *infrastructure* those manifests would consume from. Pragmatically, the OpenClaw adapter is probably the first one you should build, both because you understand OpenClaw's quirks deepest and because Moltbot gives you a real-world load to test against.

**Claude Code** is the second adapter and the one that wins the hackathon. The integration leverages tool_search (don't fight it; build on it). Concierge would register itself as an MCP server that exposes meta-tools like `recommend_tools` and `request_capability`, and the loader/proxy layer would manage actual MCP server lifecycle on the side.

**Claude Desktop / Cowork** is the third adapter and probably the messiest because of the desktop-extension restart issue. For v1 you may want to scope this down to just remote connector management, which is much cleaner.

**SatietyAI WordPress/LearnDash course content** isn't a technical integration but a strategic one. Concierge becomes a *teachable example* in your "Building With AI: From Tools to Agent Management" course — a real-world case study of how to think about tooling for autonomous systems. The restaurant/kitchen metaphor maps beautifully: Concierge is the maître d' who knows what's in the pantry, what the kitchen can prep tonight, and what the customer is in the mood for.

**Local AI workstation rollout** changes Concierge's deployment story over time. Phase 1 (NAS): Concierge runs as a service on your dev machine. Phase 2 (GPU server): Concierge runs on the server, agents from any machine connect to it. Phase 3 (full local stack): the recommendation engine itself can run on local Ollama for privacy-sensitive tasks, with Opus 4.7 as a fallback for harder reasoning. Don't optimize for this on day one, but design the boundaries cleanly so you can swap the inference layer later.

**GoHighLevel + the rest of the marketing stack** is mostly orthogonal to Concierge, but worth noting: any tools you build into your marketing automation could *also* be entries in the Concierge catalog. If you ever want Claude to help with a campaign, the GHL tool should be discoverable, not hard-coded.

---

## Build Roadmap

### Phase 0 — Pre-hackathon (this week, low effort)

- Sketch the architecture on paper. Get comfortable with the component boundaries.
- Set up a private GitHub repo, even empty, with a basic README. (The judges may glance.)
- Confirm your OpenClaw hot-swap workaround still works on your current setup. That's your fallback transport story.
- Decide on the tech stack. Suggested: Python (FastAPI) for Concierge service, SQLite for v1 storage, the official MCP SDK for the Claude Code adapter.

### Phase 1 — Hackathon week (if accepted)

The discipline here is to **show the loop closing**, not to build the whole architecture. Aim for one tight end-to-end demo:

- **Day 1-2**: Catalog service with ~10 hand-curated tools (mix of MCP servers, CLI commands, HTTP APIs). Storage layer. Basic CRUD.
- **Day 2-3**: Loader/proxy for Claude Code. Just stdio MCP servers to start. Verify you can load and unload mid-session.
- **Day 3-4**: Recommendation engine. Simple v1: Opus 4.7 takes the catalog + recent agent context, returns a ranked list. Add the lightweight-first preference as a system prompt rule.
- **Day 4-5**: Memory service. Event log + derived state. Wire up the lifecycle state machine with hardcoded thresholds.
- **Day 5-6**: The demo. Polish one specific scenario end-to-end (the "Postgres mid-session swap into curl + grep" story is solid). Record a 3-minute screen capture.
- **Day 7**: Submit. Document what's there, what's stubbed, what's next.

What gets cut if time is tight: cross-agent learning, permission scoping, the dashboard, the OpenClaw adapter (mention Moltbot in the demo without actually wiring it for the hackathon).

### Phase 2 — Post-hackathon (next 2-4 weeks)

- Add the OpenClaw adapter. Validate the platform-agnostic design by actually proving it on a second harness.
- Build the user-facing dashboard. Even simple: "tools used this week, lifecycle state of everything, biggest wins."
- Move catalog from SQLite to a more robust store as you accumulate real data.
- Open-source the recommendation engine and adapters. The catalog stays personal.

### Phase 3 — Course integration (1-3 months)

- Concierge becomes a featured case study in "Building With AI: From Tools to Agent Management."
- A simplified version of Concierge ships as a reference implementation students can fork.
- The restaurant metaphor gets a concrete embodiment.

### Phase 4 — Local AI workstation integration (timeline tied to hardware rollout)

- Concierge migrates to the GPU server.
- Recommendation engine becomes hybrid: local model for fast/cheap recommendations, Opus 4.7 for hard cases.
- Catalog grows to include local-only tools and resources.

---

## Demo Story (For The Hackathon)

A clean three-minute demo beats a sprawling ten-minute demo every time. Here's a tight script you could shoot for:

> "I start a Claude Code session with a minimal toolset — just three lightweight tools. I ask it to analyze a CSV in my project. Concierge sees the intent, recommends loading a Pandas-flavored data tool, agent picks it up mid-session, completes the task. Then I pivot: 'now scrape the latest pricing from competitor.com.' Concierge notices I have a heavy MCP browser tool available — but it also notices that `curl + grep` would work for this specific page. It surfaces both, prefers the lightweight option, agent uses it. Task done in 200 tokens instead of 2000.
>
> Now watch the memory layer. The Pandas tool got used once and is now in `used` state. By the third session this week, it'll be promoted to `loaded-on-boot` because I clearly need it. The MCP browser tool I never touched? Headed for `retired` if I don't use it in the next two weeks.
>
> Same Concierge, same catalog, same memory — also running my Moltbot WhatsApp agent in the background. When that agent learned the curl-based scraper works for that competitor's site, my Claude Code session benefited. Cross-harness learning, no manual config."

That's the story. Everything in the build serves that three minutes.

---

## Open Questions & Decisions To Make

These are real forks in the road that deserve thought before you start coding:

**Synchronous or asynchronous recommendations?** If Concierge has to make a recommendation before every agent turn, it becomes a latency tax. If it runs async and only injects when it has high confidence, it's invisible until it's useful. Lean async, but build the sync interface for cases where the agent explicitly asks.

**Per-user or shared catalog?** A personal catalog (your tools, your preferences) is the obvious starting point. But shared catalogs (your teaching audience, faith-based homeschool community, Moltbot users at scale) are an interesting future. Don't build for the second yet, but don't preclude it either.

**How aggressive should retirement be?** Too aggressive and you'll annoy yourself by losing tools you do occasionally need. Too lenient and the catalog never cleans itself. Start lenient (90 days unused → retired) and tune from telemetry.

**MCP-native or transport-agnostic?** MCP is the standard, but CLI tools and HTTP APIs aren't MCP. You can either wrap everything as MCP servers (uniform interface, more overhead) or keep them as native types in the catalog and have the loader handle the differences (more code, less overhead). Recommend the second for v1 — it keeps you honest about lightweight-first preference.

**Open-source what?** Strong opinion: open-source the engine, the adapters, and a reference catalog. Keep your personal catalog and memory data private. The asset isn't the code — it's the personalized memory layer that emerges from using it.

---

## Closing Thought

You're not building a tool. You're building the missing layer of intelligence that all of these agent systems are quietly waiting for. Anthropic shipped tool_search; that bought you the foundation. The Claude Desktop blue switch and the "load tools when needed" mode are both early steps in this same direction. The lifecycle and memory pieces — promoting tools that earn their place, retiring tools that don't, learning across harnesses — are the next step nobody has publicly built yet.

Whether or not the hackathon accepts you, this is the right thing to build. The hackathon is just helpful timing pressure to get a v1 demo shipped instead of perpetually planned.

Now go integrate this into your master plan and ship it.
