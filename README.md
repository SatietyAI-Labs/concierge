# Concierge

**Platform-agnostic tool awareness layer for AI agents.**

Concierge is a harness-agnostic, model-agnostic tool-awareness substrate for AI agents. It sits between any LLM and any harness — Claude Code, Claude Desktop, custom agents, future runtimes. The agent consults Concierge to understand what tools are available to its operator: what's installed, what's loaded right now, what's been retired, what to ask for. The harness is the runtime environment; the LLM is the model doing the thinking; Concierge is the substrate underneath that any LLM-in-any-harness can consult via MCP.

Concierge is the third voice in the room when an operator and their AI agent work through a task together. It isn't a passive recommender the LLM consults silently. When the agent hits a capability question — *"should I shell out for this?"* *"is there something faster?"* *"what does this operator already have installed?"* — it pauses, consults Concierge, and comes back with "here's what I'd reach for, here's an alternative you might not have thought of, here's why." That narration becomes part of the conversation: the operator hears Concierge through the agent, not as a separate UI surface to context-switch to.

Concierge is identity-aware substrate. In the simplest case — one operator, one Claude Code session — Concierge mediates between that single agent and the operator. In multi-tier setups where multiple agents collaborate (workers reporting to a primary agent reporting to the operator), every agent at every tier consults Concierge as the same shared substrate. Tool requests route by the requester's place in the hierarchy: worker requests escalate to the primary agent (which has autonomous-action authority for everything short of spending money or `sudo`); primary-agent requests escalate to the operator. The single-agent case is the degenerate form of the same pattern — one tier, no escalation chain, same substrate underneath.

## What Concierge does

Concierge manages four peer categories of agent capability: **CLI tools** (csvkit, ripgrep, pandoc), **MCP servers** (third-party integrations), **HTTP APIs** (direct service calls), and **skills** (agent-readable instruction documents). Treating skills as a peer category — managed with the same lifecycle, recommendation, and discovery semantics as executables — is genuinely novel; no other system does this. Across all four categories, Concierge ranks options by fit when the agent asks, names alternatives the agent might not have considered, and explains why one fits the task better than another. The recommendation surface is uniform: a CLI tool and a skill file go through the same `concierge_recommend` flow, returning the same ranked structure.

The catalog is the structured view of every capability Concierge knows about — installed, loaded-on-boot, idle, demoted, retired. Each entry carries lifecycle state, recommendation metadata, ownership, and success/failure history. The catalog is the agent's source of truth for what exists; Concierge keeps it consistent across harnesses, so the same capability that's loaded for one agent is visible to another agent asking about it.

Capabilities move through a lifecycle state machine: pending request → operator approval → install → loaded-on-boot → (if idle long enough) demoted → (after extended disuse) retired. Operator approval is mediated through structured pending-request markdown files that Concierge generates when the agent asks for something not yet in the catalog. Approving a request triggers an autonomous install; denying records the decision so the next agent that hits the same gap doesn't re-ask.

Concierge surfaces through the agent rather than as a separate UI. When the agent consults `concierge_recommend`, the rationale, ranked alternatives, and trade-offs come back as structured response data; the agent narrates them as part of its conversation with the operator. The operator never has to context-switch — the consultation is part of the dialogue, not a sidebar. The narration-as-push design keeps Concierge inside the conversation where the work is happening.

Concierge speaks MCP. Any MCP host — Claude Code, Claude Desktop, custom agents — registers Concierge as a stdio MCP server and gets `concierge_recommend`, `concierge_request_tool`, and `concierge_list_active` as native tool calls. No SDK, no HTTP client, no harness-specific glue: Concierge is just another MCP server in the agent's toolset.

## Install

Concierge runs as an MCP server. Your AI agent — Claude Code, Claude Desktop, or any other MCP host — talks to it via stdio.

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv) for environment management.

```bash
git clone <repo-url>
cd Concierge
uv sync
```

This creates `.venv/` at the repo root with Concierge installed editably and a `concierge-shim` console script at `.venv/bin/concierge-shim`.

### Register with Claude Code

```bash
claude mcp add concierge "$(pwd)/.venv/bin/concierge-shim"
```

Open a fresh Claude Code session to pick up the registration. The agent should now see `concierge_recommend`, `concierge_request_tool`, and `concierge_list_active` in its toolset.

To verify the install end-to-end, ask the agent something tool-shaped: *"How should I count lines in a CSV file?"* If the agent calls `concierge_recommend` and returns a ranked recommendation, registration is working.

### Other MCP hosts

Any MCP host that supports stdio servers can run Concierge — same `concierge-shim` console script, no host-specific build. Point your host's MCP config at the absolute path of `<repo>/.venv/bin/concierge-shim`.

For Claude Desktop, edit the config file at your platform's path:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

Add Concierge under `mcpServers`:

```json
{
  "mcpServers": {
    "concierge": {
      "command": "/REPLACE/with/absolute/path/to/Concierge/.venv/bin/concierge-shim",
      "args": []
    }
  }
}
```

Restart Claude Desktop completely (quit, don't just close the window) for the registration to take effect.

## Quick start

With Concierge registered, open a fresh Claude Code session and ask the agent something tool-shaped. Here's a real interaction:

> **You:** How should I count lines in a CSV file?
>
> **Agent:** Let me check what you have available for that.
>
> *[calls `concierge_recommend`]*
>
> For this task I'd reach for `xsv count` first — purpose-built for CSVs, handles embedded newlines in quoted fields correctly, and returns in milliseconds. It's in your catalog under data-processing.
>
> A close alternative is `wc -l`, which is faster but treats every newline as a row boundary, so it'll over-count if any cell contains an embedded newline. For well-formed CSVs, `wc -l` is fine; for arbitrary input, `xsv count` is safer.
>
> Want me to run `xsv count <file>` for you?

That's the third-voice pattern in practice: the agent surfaces Concierge's ranked recommendation with rationale, names a faster alternative with its trade-off, and offers to act. If your install is healthy, your agent's output will look structurally similar — not identical, but recognizably the same shape.

## Usage

Three scenarios that show how the recommendation pattern lands across categories.

### Recommending a CLI tool for data processing

> **You:** Compute summary statistics for the numeric columns in survey-2026-q1.csv.
>
> **Agent:** Looking at your catalog for CSV-shaped numeric processing.
>
> *[calls `concierge_recommend`]*
>
> Your catalog has four candidates. I'd reach for `miller-mlr` first — the `mlr stats1` verb is purpose-built for this exact shape (mean / median / stddev across numeric columns) and runs in one pass. `csvkit`'s `csvstat` is a close second — more interactive but slower on large files. `xsv` covers similar ground with less native stats support but faster filter / select work. `sqlite3` is the heaviest option, worth knowing about if you'd rather load the CSV into a queryable form for follow-up analysis.

### Recommending across in-catalog and discovery

> **You:** Convert my-book.pdf to EPUB so I can read it on my Kindle.
>
> **Agent:** Checking what you have for PDF-to-EPUB conversion.
>
> *[calls `concierge_recommend`]*
>
> `pandoc` is in your catalog and handles this directly — `pandoc my-book.pdf -o my-book.epub`. Quality varies based on the PDF's structure: pure-text PDFs convert cleanly, layout-heavy ones may need post-conversion editing.
>
> Two alternatives I'd flag (both out-of-catalog, surfaced from discovery): Calibre's `ebook-convert` is the heavyweight choice — better quality on layout-heavy PDFs but you'd need to install Calibre. A `pdftotext` → `pandoc` pipeline is more surgical if you want to clean up the intermediate text before converting. If `pandoc` alone gives you a passable EPUB, stick with that; if it's rough, ask me about the alternatives.

### Recommending across peer categories

> **You:** Review this PR for security issues — there's a new endpoint that takes user input and writes to the database.
>
> **Agent:** Let me check what review approaches you have available.
>
> *[calls `concierge_recommend`]*
>
> Two candidates fit here, one skill and one CLI tool. The `security-review` skill is the methodology match — a checklist document covering input validation, injection vectors, authn / authz checks, and trust boundaries, with concrete review steps for endpoint changes. `semgrep` is a static-analysis CLI in your catalog that catches a different layer — pattern-based detection of known-bad code shapes (SQL injection, hardcoded secrets, unsafe deserialization).
>
> For a database-write endpoint with user input, I'd run the `security-review` checklist first for the methodology pass, then `semgrep` for the static-analysis sweep. The skill catches what requires reasoning about the change; the CLI catches what regex-shaped patterns can find. Want me to walk through `security-review` against the diff?

The recommendation pattern is the same as the CLI examples — ranked options, alternatives with trade-offs, an offer to act — but here the ranked list mixes a skill and an executable as peers. Same lifecycle, same recommendation surface, same `concierge_recommend` call.

## Architecture

Concierge is composed of:

- **Catalog Service** — structured store of every capability Concierge knows about, with lifecycle state, recommendation metadata, and success / failure history. SQLite-backed; markdown-exportable.
- **Recommendation Engine** — ranks catalog entries by fit for a given task and surfaces alternatives. Uses Anthropic's Claude API for the reasoning step.
- **Lifecycle State Machine** — manages capability transitions (pending → installed → loaded-on-boot → demoted → retired) with operator approval mediated through structured markdown files.
- **Memory Service** — semantic-memory store (ChromaDB with sentence-transformer embeddings) that records past tool decisions and surfaces similar prior choices for new tasks.
- **Discovery Engine** — scans package registries, awesome-lists, and GitHub for capabilities not yet in the catalog when the recommendation engine doesn't have a fit.
- **Adapters** — host-specific runtimes that surface Concierge to AI agents. The Claude Code adapter is an MCP server that works for any MCP host out of the box; an OpenClaw adapter is roadmapped to bridge that fleet's non-MCP runtime.

For the architectural specification with rationale and trade-offs, see [`planning/concierge-blueprint-v2.md`](planning/concierge-blueprint-v2.md).

## Origin

Concierge was built during the Built with Opus 4.7 hackathon (April 21–26, 2026) and extended through a post-hackathon hardening phase. The recommendation behavior, lifecycle state machine, and discovery engine were lifted from the OpenClaw fleet runtime, where they had run in production beforehand. For builder background, see [ABOUT.md](ABOUT.md).

## License

Concierge is released under the MIT License — see [LICENSE](LICENSE).
