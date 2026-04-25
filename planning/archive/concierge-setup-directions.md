# Concierge Planning Day — Setup Directions

### The two-project architecture

You're setting up **two parallel workspaces** that talk to each other:

1. **Claude.ai Project (this chat interface)** — the planning brain. Holds reference documents, the blueprint, the pitch, key decisions. This is where you come to think, ask questions, get second opinions, and generate new planning docs.

2. **Claude Code Project (in WSL)** — the code archaeologist and builder. Has direct file-system access to all your existing code. Reads what's there, maps it to the blueprint, classifies it, produces inventory and build plans.

Each workspace has a distinct job. Don't mix them. The chat side is strategic; the Claude Code side is mechanical. They hand off to each other through files.

---

## Part 1: Claude.ai Project Setup (Chat)

### 1.1 Create the Project

In the Claude.ai web app or desktop:
1. Click **Projects** in the left sidebar
2. Click **Create Project** (or the `+` icon)
3. Name it: **"Concierge Build"**
4. Optional description: *"Platform-agnostic tool concierge — hackathon build and beyond"*

### 1.2 Files to add to the Project

Upload these files into the Project's Knowledge section (drag-and-drop or use the upload button):

1. **`concierge-blueprint.md`** — the full architecture/build blueprint (the first artifact I made today)
2. **`concierge-setup-directions.md`** — this document
3. **`concierge-claude-code-plan.md`** — the execution plan for Claude Code (the second artifact I'm making now)
4. **Your hackathon application pitch** — copy the pitch we drafted into a text file called `application-pitch.md` and upload it. Useful reference for "what did I actually promise."

Optional but useful:
5. **`moltbot-context.md`** — a short file (you write, 5 minutes) describing your Moltbot setup at a high level: what it does, what it runs on, what tools it uses most. Saves you explaining it from scratch every new chat.
6. **Any existing architecture notes or READMEs** from your current tool concierge or semantic memory MCP projects.

### 1.3 Project Instructions

In the Project's **Custom Instructions** field, paste something like:

> This project is for building Concierge — a platform-agnostic tool awareness layer for AI agents. I'm building this during and after Anthropic's Built with Opus 4.7 hackathon (April 21-26, 2026). I'm a solo self-taught builder, 13 months into AI development, working across Claude Code (WSL2 Ubuntu), Claude Desktop, and Claude Code CLI on Windows. My existing systems include Moltbot (OpenClaw-based WhatsApp agent on WSL2), a semantic memory MCP, and a beta tool concierge built for OpenClaw. Reference the blueprint and planning documents in the Knowledge section for architecture. I prefer concrete, actionable guidance over abstract advice. Don't pad with disclaimers. When I ask a question, assume context from prior conversations in this project.

### 1.4 When to use the Claude.ai Project

Use the chat side for:
- "Should I make decision X or Y?" conversations
- Reviewing output from Claude Code and deciding what to do with it
- Drafting new planning docs, UI copy, course material, demo scripts
- Working through unexpected issues during the hackathon week
- Post-hackathon retrospective and next-phase planning

Don't use chat for:
- Reading existing code files (that's Claude Code's job)
- Running or testing anything
- Making actual code changes

---

## Part 2: Claude Code Project Setup (WSL)

### 2.1 The physical folder structure

You mentioned your existing OpenClaw-related work is already consolidated into one openclaw project folder. Good — that simplifies things. But we don't want Claude Code modifying that during assessment. It's sacred source material.

**Create a new folder** alongside it, specifically for Concierge planning and build:

```
~/projects/concierge/
├── _legacy/              # read-only reference to existing work
│   └── openclaw/         # symlink or copy of your existing folder
├── planning/             # outputs from the assessment phase
│   ├── inventory.md
│   ├── classification.md
│   ├── dependency-graph.md
│   ├── gap-analysis.md
│   └── build-plan.md
├── docs/                 # reference material
│   ├── concierge-blueprint.md
│   └── concierge-claude-code-plan.md
├── core/                 # (empty for now) the new platform-agnostic core
├── adapters/             # (empty for now) harness-specific glue
│   ├── openclaw/
│   ├── claude-code/
│   └── claude-desktop/
├── ui/                   # (empty for now) the dashboard
├── CLAUDE.md             # Claude Code's instruction file
└── README.md
```

**Create the folder:**

```bash
mkdir -p ~/projects/concierge/{_legacy,planning,docs,core,adapters/openclaw,adapters/claude-code,adapters/claude-desktop,ui}
cd ~/projects/concierge
```

**Link in your existing work as read-only reference:**

If your openclaw folder is at, say, `~/openclaw/`:

```bash
ln -s ~/openclaw _legacy/openclaw
```

(A symlink is better than a copy — Claude Code can read through it, and it won't accidentally drift out of sync with your real work.)

**Copy in the reference docs:**

Download `concierge-blueprint.md` and `concierge-claude-code-plan.md` from this chat and put them in `~/projects/concierge/docs/`.

### 2.2 The CLAUDE.md file

This is the most important file in the whole setup. It's what Claude Code reads on every session to know what it's doing. Create `~/projects/concierge/CLAUDE.md` with this content:

```markdown
# Concierge — Mission and Ground Rules

## What this project is
I'm building Concierge, a platform-agnostic tool awareness layer for AI agents.
It gives agents "tool agency": knowing what they don't have, asking for it,
preferring lightweight options, and learning which tools earn their place
over time.

## What this project is NOT (yet)
Until the assessment phase is complete, you are NOT writing new code.
You are an archaeologist and planner. Read existing code, map it to the
blueprint, classify it, report findings.

## The authoritative reference documents
- `docs/concierge-blueprint.md` — the full architecture and build blueprint
- `docs/concierge-claude-code-plan.md` — your step-by-step execution plan
  for the assessment and planning phases

Read both of these in full before doing anything else.

## Existing code location
- `_legacy/openclaw/` — all prior work lives here, read-only
  - Includes: beta tool concierge, MCP load/unload work, semantic memory
    MCP integration, OpenClaw itself
- Treat `_legacy/` as read-only. Never modify files there during this
  planning phase. If you need to try something destructive, copy the file
  into a planning/ subfolder first.

## Output location
- `planning/` — all your inventory, classification, dependency maps, and
  build-plan documents go here
- `core/`, `adapters/`, `ui/` — leave empty during planning phase. These
  get populated during the build phase.

## Ground rules
1. Before writing any file, confirm you've read the blueprint and the
   execution plan.
2. Every assertion about existing code should cite the file path.
3. When unsure, stop and ask. Don't guess the user's intent.
4. No refactoring existing code in this phase. Document it, don't fix it.
5. Prefer concrete over abstract. "This file at path X does Y" beats
   "the system appears to support Y functionality."
6. Hidden coupling is the enemy. When you spot OpenClaw-specific assumptions
   inside what should be reusable logic, flag it explicitly.

## Personal context
- Solo self-taught builder, 13 months into AI
- Running WSL2 Ubuntu on Windows multi-machine setup
- Core brands: SatietyAI (primary), Sonoran Caramel Co, Bartruff brand
- Daily drivers: Claude Code CLI, Claude Desktop, Cowork tab
- Targeting: Built with Opus 4.7 hackathon, April 21-26, 2026
```

### 2.3 Starting a fresh Claude Code session

**Don't** reuse the session that built the beta tool concierge. That session has baggage — it's primed for building OpenClaw-specific features, not for architectural assessment. A fresh session reading the new CLAUDE.md will behave correctly.

From WSL:

```bash
cd ~/projects/concierge
claude
```

Or from the Claude Code desktop UI, open `~/projects/concierge/` as a new project.

First prompt in that session (just paste this verbatim):

> Read CLAUDE.md and both files in docs/ in full. Confirm you understand the mission. Then tell me what questions you have before starting Phase A of the execution plan. Do not begin any inventory work yet.

This forces Claude Code to actually ingest the plan before acting. You'll get a few clarifying questions back, answer them, *then* give it permission to begin Phase A.

### 2.4 Permissions / safety

Because the assessment phase should be read-only against `_legacy/`, you can be conservative with permissions during this phase. Use Claude Code's standard permission prompts — don't enable any "always allow" modes for file writes until you're into the build phase.

---

## Part 3: The handoff pattern

Here's how the two workspaces talk to each other:

**Claude Code → Claude.ai Project:**
When Claude Code produces a planning document (e.g., `planning/inventory.md`), you'll want to:
1. Open the file, skim it, see what it found
2. If you want strategic input, upload or paste the document into a chat in the Claude.ai Project and say "thoughts on this?"
3. Take any decisions back to Claude Code as explicit instructions

**Claude.ai Project → Claude Code:**
When you make a decision in chat (e.g., "we're going to rewrite the semantic memory adapter rather than extract"), you:
1. Summarize the decision in one paragraph
2. Paste it into Claude Code as instructions for the next phase
3. Optionally have Claude Code append the decision to a `planning/decisions.md` log

This prevents the chat side from drifting from the code side. Files are the single source of truth.

---

## Part 4: Today's order of operations

You've got one day. Here's the sequence:

**Morning (~2-3 hours):**
1. Set up the Claude.ai Project with files (30 min)
2. Set up the WSL folder structure and CLAUDE.md (30 min)
3. Start the fresh Claude Code session, have it read the docs, answer its clarifying questions (30-60 min)
4. Kick off Phase A (Inventory) — let it run (1 hour+)

**Midday (~2 hours):**
5. Review the inventory output in chat side. Make strategic calls on anything ambiguous.
6. Kick off Phase B (Map to Architecture) and Phase C (Classify) in Claude Code.

**Afternoon (~2-3 hours):**
7. Review classification. This is where you'll make the most important decisions of the day (lift vs. extract vs. rewrite per component). Spend real time here.
8. Run Phase D (Dependency Graph) and Phase E (Gap Analysis).
9. Run Phase F (Build Plan). This produces your hackathon-week roadmap.

**Evening:**
10. Read the final build plan end-to-end. Identify any gaps.
11. If accepted to the hackathon: you start tomorrow with a plan in hand.
12. If not accepted: same plan, different timeline. Ship it anyway.

---

## Pre-flight checklist

Before you start the Claude Code assessment session, verify:

- [ ] Claude.ai Project created with blueprint, plan docs, and pitch uploaded
- [ ] WSL folder `~/projects/concierge/` created with full subfolder structure
- [ ] `_legacy/openclaw/` symlink or copy in place and readable
- [ ] `docs/concierge-blueprint.md` present
- [ ] `docs/concierge-claude-code-plan.md` present
- [ ] `CLAUDE.md` at project root with mission + ground rules
- [ ] Fresh Claude Code session started (not the beta-build session)
- [ ] Confirmed Claude Code can read through the symlink into `_legacy/`

Once all of those are checked, you're ready. Hand Claude Code the kickoff prompt and let it start Phase A.
