# Handoff — Concierge scope pivot and verification arc
### Produced: 2026-04-23 (mid-Day 4) — for the fresh planning chat picking up next

---

## What this document is

You (the fresh planning chat) are inheriting an in-progress build. The project Knowledge folder contains multiple versioned reference documents. Read them in this order before acting:

1. **`CLAUDE-v3.md`** — mission, ground rules, operations protocol awareness (supersedes all prior CLAUDE.md versions)
2. **`concierge-operations-protocol.md`** — session model, handoffs, decisions, daily rhythm
3. **`concierge-blueprint-v2.md`** — architecture (supersedes v1; v2 has the lifted-vs-new table)
4. **`concierge-claude-code-plan-v3.md`** — phases and execution plan (supersedes v1)
5. **`TOOL-CONCIERGE-OVERVIEW.md`** — the richest reference for what the first-draft personal tool concierge actually does
6. **This handoff document**
7. **`build_record_progress_4-21-26.txt`** (notepad) — verbatim Claude Code log, large; read on demand when specific questions surface

The older v1 blueprint, v1 plan, hackathon pitch, and original setup directions are still in Knowledge for history but have been superseded. If they conflict with v2/v3, v2/v3 wins.

This handoff captures **what changed since those versioned documents were written** and **what the immediate scope question is**. It does not re-state architecture you already have access to.

---

## Who Lewie is and how he works

- Solo self-taught builder, 13 months into AI
- WSL2 Ubuntu on Windows multi-machine setup, primary project dir `/mnt/c/Users/satie/Projects/ClaudeCodeCLI/Concierge/`
- Daily drivers: Claude Code CLI, Claude Desktop, Cowork tab
- Core brands: SatietyAI (primary), Sonoran Caramel Co, Bartruff brand
- Communication preference: open prose questions only (no multiple-choice or `ask_user_input_v0` calls), concrete over abstract, push back honestly when you disagree, files stored in folders rather than pasted inline in chat
- Your role: strategic, planning, review. Claude Code executes. Lewie steers. You help him see scope clearly, pressure-test Claude Code's proposals, and keep the build on-mission.
- Optimizes for AI quality, not token cost. Effort stays at `xhigh` or `max` throughout.

---

## What's already built (Days 1-3, ending Day 4 morning)

### Commits as of this handoff

28+ commits across 3 days. 518 tests passing. Working tree clean at last check.

### Architectural components that exist and work

- **FastAPI service** (`core/`) with `/health`, `/tools`, `/packs`, `/recommend`, `/requests`, `/requests/{filename}/status` endpoints, all working
- **SQLite catalog** (`concierge.db`) with 4 hand-seeded tools (ripgrep, csvkit, firefox-click, memory-store) and 2 packs
- **Semantic memory** via ChromaDB + sentence-transformers, with cold-start-tax behavior documented
- **Five extracted prompt fragments** (Class-1 closed): X3 tool-awareness, X4 tool-recommendation, X6 tool-discovery, X7-A tool-lifecycle-weekly-review, X8 SOUL-delta
- **X7-B lifecycle Python constants** (Class-2)
- **Lifecycle_policy module** (renamed from lifecycle to disambiguate) — policy/thresholds/status values
- **Lifecycle_store module** — visibility + state transitions for pending requests, round-trip parse verification on every write
- **Recommendation engine** (`core/recommend/`) — calls real Opus 4.7 with `effort="xhigh"`, `max_tokens=4096`, no `temperature` (deprecated in Opus 4.7)
- **Three-tier fixture drift detection** (shipped Day 3 evening):
  - Tier 0: CI-safe composition-pipeline test (`tests/test_recommend_pipeline.py`)
  - Tier 1: Live response-shape validator (`core/recommend/validator.py`) — fires `recommend.fixture_drift_detected` WARNING on shape mismatch, never raises
  - Tier 2: `fixture_drift_count` counter surfaced in `/health`
- **Claude Code adapter** (`adapters/claude_code/`) — stdio MCP shim, three meta-tools registered (`concierge_recommend`, `concierge_request_tool`, `concierge_list_active`), backing-server registry framework
- **Shim wrapper** (`scripts/concierge-shim`) — hardcoded venv Python path (portability flagged as TODO)
- **X13 install module** — covers `install_npm_global`, `install_pip_user`, `install_single_binary`

### Four production bugs caught and regression-guarded during Day 3 manual verification

1. **Pydantic import via venv path** (commit `e8a7e1b`) — shim wrapper needed absolute venv Python path
2. **protocolVersion mismatch** (commit `bc88327`) — real Claude Code 2.1.117 sends/expects `2025-11-25`, pinned older version was rejected
3. **Opus 4.7 temperature deprecation** (commit `5d29e3f`) — `temperature=0.0` returns 400 invalid_request_error; replaced with `output_config.effort="xhigh"`, bumped `max_tokens` to 4096
4. **Shim cold-start timeout** (commit `96d619e`) — first call paid 34-50s sentence-transformers warmup tax; httpx timeout bumped 30s → 90s, error message improved

Each has a hardcoded-expectation regression test preventing recurrence.

### Verified manual-verification baselines

Two known-good real-Opus call request_ids preserved for soak-phase comparison:
- `33b0ae69-e1a` — the "moneyshot" (csvkit high-confidence + miller discovery + gap-report with "do not block" framing)
- `38e2562f-744` — restart-baseline after Day 3 N14 shipped, validator-validated on first try

---

## The pivots that happened mid-build

### Pivot 1 — Operational-first

**[DECISION 2026-04-21 18:00]** End-state shifted from "3-min demo recording" to "Concierge running live on real Claude Code sessions 48+ hours before declaring done." Demo is subset of operational; if hackathon acceptance comes, both paths work; if not, operational is what matters.

### Pivot 2 — Ship it whole

**[DECISION 2026-04-23 mid-Day-4]** Lewie explicitly committed to building for public release, not hackathon-MVP. His exact framing: *"I want to build it whole and post it for people to use."* He is a full day ahead of hackathon-build-plan pacing; time is not the constraint. This changes the scope evaluation lens — anything consciously-narrowed-for-MVP becomes a no-go.

### Consequence: Day 4 morning scope-verification pause

Before starting UI work (N17/N18 tiles per §F.2.4 of plan-v3), Lewie paused to verify current-Concierge-implementation against what blueprint-v2 promised. Two verification passes happened today.

**Verification 1: Catalog multi-category gap report**

Question: Does Concierge's catalog include MCP servers, CLI commands, and HTTP/APIs as peers per blueprint item #1?

Result: **Partial — MCP and CLI present (2 rows each), HTTP/API structurally absent.** No `tool_type` enum exists in schema. `install_method` field conflates install mechanism with runtime delivery. No catalog-ingest code path exists at all — 4 DB rows were hand-seeded Day 1-2. Legacy ground-truth catalog (`_legacy/toolconcierge/TOOL-CATALOG.md`) has explicit three-category structure; extraction to current Concierge did not carry the category-peer structure across.

Sizing:
- Layer A (schema): 0.75-1h
- Layer B (catalog ingest): 2-3h
- Layer C (prompts + engine HTTP awareness): 1-2h
- Minimal-subset (Layer A + hand-seed HTTP entries from legacy source): 1.5-2h

Full report in notepad under "Catalog-foundation gap report (Day 4 UI pause)" section.

**Verification 2: Behavioral fidelity three-part report**

**Q1 — Proactive invocation:** **Architecturally broken.** The behavioral instructions exist (X3/X4/X6/X7-A/X8/CLAUDE_CODE_GAP_PREAMBLE) but are wired to the wrong surface. They govern how Opus reasons *inside* `concierge_recommend` once called; they do NOT govern *when Claude Code decides to call it*. What Claude Code actually sees at session start is two sentences of terse tool description per meta-tool, reactive in grammar ("use when you notice"). The planning-discipline + signal-enumeration content is invisible to the caller.

**Q2 — Rich recommendation content at in-chat surface:** **3 of 8 dimensions structurally absent from `RecommendationRecord`.** Category, install_method, and risk_cost have no schema field — they cannot be emitted. "Alternatives considered" is implicit via multiple ranked recs and occasionally surfaces in Summary prose but has no structured field. Four request_ids of empirical evidence confirm this is structural, not stochastic.

**Q3 — Pending-file fidelity:** **Write path is solid.** All 8 OpenClaw dimensions are expressible through `NewRequestDraft`'s 11 parameters, render in correct sections, round-trip-parse cleanly. Two Concierge-specific additions (`Discovered` flag, optional `Source`/`Evidence`) are enrichments. **Real risk is caller sloppiness** — if agent calls with only `tool_name`, resulting file has 9 empty fields the operator has to mentally reconstruct.

Sizing:
- Proactive invocation (tool description enrichment): 0.5-1h
- Proactive invocation (full MCP resources protocol): 1-2h
- Add category/install_method/risk_cost to `RecommendationRecord` + validator: 1-1.5h
- Thin-file soak metric in `/health`: 0.5h

Full report in notepad under "Three-part fidelity report" section.

---

## What's in blueprint-v2 + TOOL-CONCIERGE-OVERVIEW that isn't yet verified

The two verification passes above were scoped to specific questions Lewie asked. Reading `concierge-blueprint-v2.md` + `TOOL-CONCIERGE-OVERVIEW.md` against current-Concierge-implementation surfaces additional items that are load-bearing for "ship it whole" and should be verified before fix work begins.

**Gaps likely present (to be verified systematically):**

1. **Skills as first-class catalog citizens** (blueprint §Five Core Capabilities item #1 names FOUR categories including skills, not three). Verification 1 addressed three; skills as peers not checked.

2. **Push channel / proactive injection** (blueprint §Concierge Agent Interface). Current Concierge has only Pull channel (meta-tools the agent calls). Push channel — Concierge proactively injecting messages into agent context — not implemented.

3. **Lightweight-first preference as enforced policy.** Named in blueprint but not verified whether X4's prompt actually instructs Opus to prefer lightweight options, or whether it just lists signals and lets Opus decide.

4. **Tool-level lifecycle state machine.** Blueprint specifies five states: `discovered → pending → used → loaded-on-boot → retired`. Current `lifecycle_store` implements `pending / resolved / archived` which is the REQUEST lifecycle, not the TOOL lifecycle. Both should exist per blueprint; tool-level lifecycle likely missing entirely.

5. **Hot-swap layer interface.** Blueprint specifies `load(tool_id)`, `unload(tool_id)`, `list_active()`. N13 backing-server-registry covers part; completeness across all three methods not verified end-to-end.

6. **Five-check recommendation loop** (TOOL-CONCIERGE-OVERVIEW "The Recommendation Loop"). First-draft performs: memory → resolved requests → tool catalog → tool manifest → discovery, in that order. Current Concierge's recommendation engine likely does not replicate this full sequence. Needs verification.

7. **Autonomous installation policy distinction** (TOOL-CONCIERGE-OVERVIEW "Autonomous Installation"). First-draft has clear rules: npm/pip-user/single-binary/npx-MCP autonomous; sudo/money/new-accounts escalated. X13 has the install functions but the autonomous-vs-escalated decision boundary may not be built in.

8. **Identity Notes** (TOOL-CONCIERGE-OVERVIEW "Identity Notes"). First-draft maintains a running summary of tool preferences in persistent identity memory. Not present in current Concierge.

9. **Discovery evaluation filter** (TOOL-CONCIERGE-OVERVIEW "Discovery Engine" table). Maintenance / adoption / license / install-weight / fit signals. Current Concierge has `is_discovered` flag but enforced evaluation filter in prompts not verified.

10. **Promotion/demotion thresholds**. TOOL-CONCIERGE-OVERVIEW specifies 5+ uses in 30 days for promotion, 90+ days unused for demotion. X7-B has constants — worth verifying they match.

11. **Notification system dual-channel** (TOOL-CONCIERGE-OVERVIEW "The Notification System"). First-draft has WhatsApp + filesystem. Current Concierge has filesystem; no notification surface to operator. Real-time pings when a request is filed likely missing.

12. **Multi-agent hierarchy / worker escalation** (TOOL-CONCIERGE-OVERVIEW "Multi-Agent Architecture"). First-draft models Alfred-as-primary with worker escalation via dual-channel (sessions_send + filesystem). Likely out of scope for platform-agnostic v1 but worth flagging whether current Concierge can accommodate this pattern via its existing interface or would need extension.

13. **Cross-harness learning** (blueprint §Additional Avenues line 152) — same memory layer across OpenClaw + Claude Code. Architectural claim; likely requires explicit design decision to honor.

14. **Graceful degradation when catalog offline** (blueprint line 160) — Concierge down should not load-bear on agent. Not verified.

15. **Failure feedback loops** (blueprint line 146) — tool fails 3x → demotion regardless of past performance. Not verified.

**Platform-Agnostic Architecture (blueprint §Architecture) — component status:**
- Catalog Service ✓ (SQLite + FastAPI)
- Recommendation Engine ✓ (Opus 4.7) — but five-check loop likely not fully replicated
- Memory Service ✓ (ChromaDB) — identity notes likely missing
- Loader/Proxy Layer — partial (backing_server_registry exists); uniform interface completeness not verified
- Concierge Agent Interface — Pull partial (Verification 2 Q1 gap); Push not implemented

---

## Proposed first action for the fresh chat

**Before any fix work, run one more verification pass against the full blueprint-v2 + TOOL-CONCIERGE-OVERVIEW scope.**

This is not scope creep — it's reading the reference documents Lewie already wrote and checking current-Concierge against every promise before declaring "ready to close gaps." The two verifications already run were scoped to specific questions. The fresh chat's first verification should be broad and systematic.

Suggested prompt shape for the first Claude Code session:

> Read `handoff-2026-04-23-scope-pivot.md` first (in project Knowledge or `docs/`), then `concierge-blueprint-v2.md`, then `TOOL-CONCIERGE-OVERVIEW.md`. Then produce a **comprehensive blueprint-vs-current-implementation audit** systematically covering every item in blueprint-v2's §Five Core Capabilities and §Platform-Agnostic Architecture, plus every subsystem in TOOL-CONCIERGE-OVERVIEW (Recommendation Loop / Request Pipeline / Notification System / Autonomous Installation / Discovery Engine / Memory and Learning / Tool Lifecycle Management / Multi-Agent Architecture).
>
> Output shape: same structured format as the prior two verification reports (cited in the notepad). For each blueprint/overview item: what's promised, what's built, what's missing, sized fix estimate, whether current Concierge is load-bearing on it or orthogonal to the public-release goal. No fixes proposed in this pass — inventory and surface only.
>
> Pay special attention to the gaps enumerated in the handoff document's "What's in blueprint-v2 + TOOL-CONCIERGE-OVERVIEW that isn't yet verified" section — those are priority items for the audit but not an exhaustive list.

Once that report lands, combine with the two prior verification reports and plan the combined close-the-gap build. That's the Day 4/5 work.

---

## Operational notes

### Infrastructure state when handoff was written

- Terminal A: uvicorn running on `127.0.0.1:8000`, warm at last check
- This chat's Claude Code CLI session: running on Max plan (confirmed via `/login`)
- API key (`ANTHROPIC_API_KEY`) in `~/.bashrc` — required for Concierge shim subprocess spawn

### Auth trap to avoid

Setting `ANTHROPIC_API_KEY` in shell env causes Claude Code CLI to detect it and prefer API-key auth over Max plan by default. `/status` shows both auth sources ambiguously. **`/login` is the authoritative diagnostic** — it shows current authenticated identity. If you see a fresh login prompt rather than "already logged in as [email]," the session is on API-key billing. `/logout` then `/login` forces claude.ai as preferred auth.

### Patterns that have worked all week

- **Architectural-pause-before-every-commit.** Claude Code proposes shape before executing. Holds without exception across 28+ commits.
- **Regression-test-for-every-caught-bug.** Every production bug gets a hardcoded-expectation test preventing recurrence.
- **Shape vs content distinction** (shipped Day 3 epilogue). Validator tests structural invariants only. Output content (which specific tool recommended, ranking order, slugs) is stochastic by design. Never assert content in CI.
- **Manual-recurring-maintenance is the anti-pattern.** When a pattern shows up that depends on remembering to check something periodically, the right fix is self-detecting infrastructure, not a TODO reminder. Tier 1+2 drift detection is the canonical example.
- **Fresh Claude Code sessions at session boundaries.** Old sessions carry context bloat; fresh sessions read the latest snapshot and continue clean. Session protocol in `concierge-operations-protocol.md`.

### File structure in repo

- `planning/sessions/SESSION-2026-04-*.md` — session-close snapshots (read the latest first)
- `planning/decisions/DECISIONS.md` — append-only decision log
- `planning/today.md` — current-day plan, regenerated each morning
- `planning/build-plan.md` — full six-day build plan (reference for §F.2.X day-scoped items)
- `docs/concierge-blueprint-v2.md` — architecture (same as project Knowledge version)
- `docs/concierge-claude-code-plan-v3.md` — plan (same as project Knowledge version)
- `docs/concierge-operations-protocol.md` — session protocol
- `core/` — FastAPI service + recommendation engine + validator + prompts + memory
- `adapters/claude_code/` — MCP shim + meta-tools + backing-server framework
- `ui/` — empty, awaiting verification-informed work
- `tests/` — 518 tests at last count
- `scripts/concierge-shim` — MCP wrapper invoked by Claude Code
- `_legacy/` — read-only symlinks, multiple reference locations:
  - `_legacy/toolconcierge/` (Windows, beta spec)
  - `_legacy/satiety-docs/`, `_legacy/satiety-pipeline/`, `_legacy/tool-requests/`
  - `_legacy/openclaw-workspace/`, `_legacy/openclaw-root/`
  - `_legacy/agent-skills/`
  - `_legacy/moltbot-memory-mcp/`

### Manual-test TODO list (9 items)

Outside the repo, maintained in chat. Covers soak-phase verifications, optimizations, and deferred cleanups. Not blocking current work but worth surfacing when you start soak planning.

---

## Closing reminder

Lewie's stated goal: *"I want to build it whole and post it for people to use."* That sentence is the north star. Any scope decision should pass through that filter:

- Does this close a real gap against blueprint-v2 or TOOL-CONCIERGE-OVERVIEW that a public user would notice?
- Does this preserve operational-first discipline (self-detecting infrastructure, no manual-recurring-maintenance anti-patterns)?
- Does this respect Lewie's stated optimization hierarchy (AI quality > build smoothness > demo readiness > token cost)?

If a fix is cheap and closes a real promised-capability gap, do it. If a fix is expensive and closes a gap Lewie never promised publicly, push back and flag the scope question. If you're unsure, surface the tradeoff in prose and let Lewie decide.

The scope verification is a feature, not a bug — catching these gaps before UI work was exactly the right operational-first move.

Good luck.
