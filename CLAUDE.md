# Concierge — Mission and Ground Rules (v3)

## This document supersedes all previous CLAUDE.md versions
The previous version (v2) corrected the framing about what's already built.
This v3 adds the operations protocol that governs how AI sessions, handoffs,
and decisions work across the build week.

Read these documents in this order before doing anything else:
1. This file (CLAUDE.md)
2. `docs/concierge-operations-protocol.md` — how sessions work
3. `docs/concierge-blueprint-v2.md` — what we're building and why
4. `docs/concierge-claude-code-plan-v3.md` — phases and execution plan

## Vision

Concierge is a harness-agnostic, model-agnostic tool-awareness substrate. It sits between any LLM and any harness — Claude Code, OpenClaw, Codex, Manus, future things. The harness is the runtime environment; the LLM is the model doing the thinking; Concierge is the substrate underneath that any LLM-in-any-harness can consult via MCP. Concierge runs on the operator's machine, not the LLM's. The operator is whoever runs Concierge — could be a developer on a dev machine, could be a non-dev using a no-code agent. Both personas show up; Concierge should "just work" for both.

Concierge is the third voice in the room. It isn't a passive recommender the LLM consults silently. It's an active participant in the operator-LLM dialogue. When the operator and the agent are working through a task, the agent pauses, consults Concierge, and comes back with "here's what I'd reach for, here's an alternative you might not have thought of, here's why" — and that becomes part of the conversation. The narration-as-push design landed in Days 4-5 (per `planning/sessions/SESSION-2026-04-25-03.md` and `planning/sessions/SESSION-2026-04-26-01.md`) is what makes this work in practice: the agent surfaces the consultation visibly, names alternatives, explains trade-offs. The operator hears Concierge through the agent, not as a separate UI surface they have to context-switch to.

Concierge is identity-aware substrate for multi-tier-agent fleets. In a fleet with multiple agents — workers reporting to a primary agent reporting to the operator — every agent at every tier consults Concierge as the same shared substrate. Tool requests route based on the requester's position in the hierarchy: worker requests escalate to the primary agent who has autonomous-action authority for non-money-non-sudo decisions; primary agent requests escalate to the operator. The single-agent case (one operator, one Claude Code session) is the degenerate form of the same pattern — one tier, no escalation chain, but the same identity-aware substrate underneath. Concierge is identity-aware enough to route correctly; the substrate itself is uniform.

*This Vision section is the v3-build-era authoritative framing. The blueprint at `docs/concierge-blueprint-v2.md` is the architectural specification; the Day 1-5 SESSION snapshots in `planning/sessions/` are the build narrative. An earlier reference doc at `_legacy/toolconcierge/TOOL-CONCIERGE-OVERVIEW.md` captures a narrower MCP-centric framing from before the v3 scope expansion; it remains in `_legacy/` for historical reference but is superseded by this Vision and by the v3 build artifacts.*

## What this project is
Concierge is a platform-agnostic tool awareness layer for AI agents. It gives
agents tool agency: knowing what they don't have, asking for it, preferring
lightweight options, learning which tools earn their place over time, and
managing the lifecycle from pending request to retired tool — all visible
through a real UI for the human operator.

## Optimization priorities (this matters — read carefully)

*Updated 2026-04-21 per DECISIONS `[2026-04-21 18:00]` — operational-first
pivot. Priority 3 was "demo readiness by Day 4"; now reads "operational
readiness by Day 4." The build target shifts from a recorded 3-minute
demo video to Concierge running live on Lewie's daily Claude Code
sessions for 48+ continuous hours. Demo is a subset of operational, not
the primary goal.*

The build operates under one explicit priority hierarchy:

1. **AI quality** — every decision favors the option that produces better
   thinking and cleaner output, regardless of token/credit cost
2. **Build smoothness** — handoffs, recovery, and continuity over speed
3. **Operational readiness by Day 4** — the protected operational core
   (catalog + recommendation + lifecycle + adapter + UI) runs on Lewie's
   daily Claude Code sessions by Day 4 evening, leaving Days 5-6 for a
   48+ hour live-shakedown gate. Substantive completion early so the
   shakedown has room. Demo recording, if it happens, is a byproduct of
   the shakedown — not a separately-rehearsed scripted take.
4. **Token cost / credit conservation — explicitly NOT a priority**

What this means in practice:
- Effort stays at `xhigh` or `max` throughout. No dropping to lower
  levels for "routine" work.
- Tool calls stay generous. Read what you need; verify thoroughly.
- Re-explanation is fine when it improves grounding.
- Parallel exploration of two approaches is on the table for hard
  decisions.
- Sessions can run deep into context before triggering handoff.
- Quality of grounding and reasoning is the metric.

The one practice we keep regardless: **files-in-folders for larger
reference material**, not pasted in-context. This is for clarity and single
source of truth, not for cost. Lewie will drop reference material into
`planning/scratch/` or appropriate folders and tell you the path.

## What's already built (in OpenClaw, to be extracted)
The existing OpenClaw-resident system includes a tool manifest, behavioral
recommendation protocol embedded in agent personality (SKILL.md +
SOUL-ADDITIONS.md), three-folder lifecycle with cron housekeeping
(pending → resolved → archived), discovery engine, semantic memory MCP,
identity notes, promotion/demotion criteria, multi-agent escalation,
autonomous installation logic, and a wishlist gap log.

The system overview document `_legacy/openclaw-workspace/TOOL-CONCIERGE-INTRO.md`
(or wherever Lewie placed it) is the richest reference for the existing
implementation.

## What Concierge needs to build (the hackathon work)
Three things, in priority order:

1. **Platform-agnostic core extraction** — lift catalog, request schema,
   recommendation behavior, lifecycle cron, memory integration out of
   OpenClaw-specific assumptions. Wrap as a service.
2. **Claude Code adapter** — let the same Concierge brain serve a Claude
   Code session. Genuinely new code.
3. **Operator UI** — a real, browser-accessible interface with three
   sections for v1: Tool Registry, Pending Requests Inbox, Health/Stats
   bar. Built with FastAPI + HTMX + Pico.css.

OpenClaw adapter is **out of scope** for the hackathon week. Phase 2 work.

## Existing code locations
The legacy reference material is spread across both Windows and WSL
filesystems. All accessible via `_legacy/`:

- `_legacy/toolconcierge/` → the beta tool concierge repo (Windows side)
- `_legacy/satiety-docs/` → master plan, tool catalog, scripts (WSL)
- `_legacy/satiety-pipeline/` → content pipeline; contains
  `outbox/tool-requests/` which is the actual lifecycle implementation
- `_legacy/tool-requests/` → direct symlink to the lifecycle folder
- `_legacy/openclaw-workspace/` → SOUL.md, TOOLS.md, TOOL-CONCIERGE-INTRO
- `_legacy/agent-skills/` → shared/ contains TOOL-MANIFEST.md and the
  tool-awareness SKILL.md

Treat everything under `_legacy/` as READ-ONLY. Never modify files there.
If you need to experiment with a file, copy it into `planning/scratch/`
first.

## Output locations
- `planning/` — inventory, classification, dependency maps, build plan,
  decisions log, session snapshots
- `planning/sessions/` — handoff snapshot per session (see ops protocol)
- `planning/decisions/DECISIONS.md` — append-only architectural decisions log
- `planning/scratch/` — temporary experiments and large reference material
- `planning/test-fixtures/` — consistent test data used all week
- `core/` — empty during planning. Platform-agnostic Concierge service.
- `adapters/claude-code/` — empty during planning. Claude Code adapter.
- `adapters/openclaw/` and `adapters/claude-desktop/` — Phase 2 work.
- `ui/` — empty during planning. FastAPI + HTMX UI.

## Session protocol summary

Full details in `docs/concierge-operations-protocol.md`. Critical points:

**Every session ends with a handoff snapshot** at
`planning/sessions/SESSION-YYYY-MM-DD-NN.md` following the standard template.
Non-negotiable. Write it in the last 5-10 minutes of every session.

**Every architectural decision gets logged** to
`planning/decisions/DECISIONS.md` following the standard template.

**Every session starts by reading**:
1. The most recent SESSION snapshot
2. CLAUDE.md (this file) if not already in this session's context
3. `planning/today.md` for the day's plan
4. Any specific files referenced in the previous snapshot's "Context the
   next session needs to read first" section

**Soft session limits:** 6 hours active OR 70% context. Trigger handoff.
**Hard session limits:** 8 hours active OR 85% context. Force handoff.

**Effort levels:** `xhigh` default. `max` for Phase C classification,
Phase F build plan, and any architectural decision encountered mid-build.

## Ground rules

1. Read CLAUDE.md, ops protocol, blueprint-v2, and plan-v3 in full before
   acting on the project.
2. Cite file paths for every claim about existing code.
3. `_legacy/` is read-only. Document, don't modify.
4. Stop and ask when unsure. Don't guess intent.
5. Concrete over abstract. "This file at path X does Y" beats "the system
   appears to support Y functionality."
6. Flag OpenClaw coupling explicitly when found inside what should be
   platform-agnostic logic.
7. Honor the filesystem split. Code on Windows, runtime on native WSL.
8. Working over pretty over clever. Hackathon goal is a solid demo.
9. Follow the operations protocol consistently. Mediocre adherence beats
   inconsistent perfection.

## Phase gates

Each phase has explicit pass/fail checkpoints in the operations protocol.
Either everything is checked or you're not at the next phase. No "basically
done." After completing a phase, summarize the deliverable in chat and
wait for Lewie's review before continuing.

## Personal context
- Solo self-taught builder, 13 months into AI
- WSL2 Ubuntu on Windows multi-machine setup
- Core brands: SatietyAI (primary), Sonoran Caramel Co, Bartruff brand
- Daily drivers: Claude Code CLI, Claude Desktop, Cowork tab
- Has never built a UI before — leans heavily on Claude Code scaffolding
  with prefab CSS framework defaults (Pico.css)
- Targeting: Built with Opus 4.7 hackathon, April 21-26, 2026
- Plan: substantively done by Day 4 (Friday), Days 5-6 for stabilization
  and demo polish
- Optimizes for AI quality, not token cost
