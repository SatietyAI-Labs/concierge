# Concierge — Mission and Ground Rules

This document is the authoritative reference for AI sessions working in this project. Read it in full before acting on the project, alongside:

1. `planning/concierge-operations-protocol.md` — operations protocol with ratified disciplines
2. `planning/concierge-blueprint-v2.md` — architectural specification with rationale and trade-offs
3. `planning/today.md` — current day's task plan and scope

## Vision

Concierge is a harness-agnostic, model-agnostic tool-awareness substrate. It sits between any LLM and any harness — Claude Code, OpenClaw, Codex, Manus, future things. The harness is the runtime environment; the LLM is the model doing the thinking; Concierge is the substrate underneath that any LLM-in-any-harness can consult via MCP. Concierge runs on the operator's machine, not the LLM's. The operator is whoever runs Concierge — could be a developer on a dev machine, could be a non-dev using a no-code agent. Both personas show up; Concierge should "just work" for both.

Concierge is the third voice in the room. It isn't a passive recommender the LLM consults silently. It's an active participant in the operator-LLM dialogue. When the operator and the agent are working through a task, the agent pauses, consults Concierge, and comes back with "here's what I'd reach for, here's an alternative you might not have thought of, here's why" — and that becomes part of the conversation. The narration-as-push design (per `planning/sessions/SESSION-2026-04-25-03.md` and `planning/sessions/SESSION-2026-04-26-01.md`) is what makes this work in practice: the agent surfaces the consultation visibly, names alternatives, explains trade-offs. The operator hears Concierge through the agent, not as a separate UI surface they have to context-switch to.

Concierge is identity-aware substrate for multi-tier-agent fleets. In a fleet with multiple agents — workers reporting to a primary agent reporting to the operator — every agent at every tier consults Concierge as the same shared substrate. Tool requests route based on the requester's position in the hierarchy: worker requests escalate to the primary agent who has autonomous-action authority for non-money-non-sudo decisions; primary agent requests escalate to the operator. The single-agent case (one operator, one Claude Code session) is the degenerate form of the same pattern — one tier, no escalation chain, but the same identity-aware substrate underneath. Concierge is identity-aware enough to route correctly; the substrate itself is uniform.

## What this project is
Concierge is a platform-agnostic tool awareness layer for AI agents. It gives
agents tool agency: knowing what they don't have, asking for it, preferring
lightweight options, learning which tools earn their place over time, and
managing the lifecycle from pending request to retired tool — all visible
through a real UI for the human operator.

## Optimization priorities

The build operates under one explicit priority hierarchy:

1. **AI quality** — every decision favors the option that produces better
   thinking and cleaner output, regardless of token/credit cost
2. **Build smoothness** — handoffs, recovery, and continuity over speed
3. **Token cost / credit conservation — explicitly NOT a priority**

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
source of truth. Lewie will drop reference material into
`planning/scratch/` or appropriate folders and tell you the path.

## Output locations
- `planning/` — inventory, classification, dependency maps, build plan,
  decisions log, session snapshots
- `planning/sessions/` — handoff snapshot per session (see ops protocol)
- `planning/decisions/DECISIONS.md` — append-only architectural decisions log
- `planning/scratch/` — temporary experiments and large reference material
- `planning/test-fixtures/` — consistent test data for tests and demo runs
- `core/` — platform-agnostic Concierge service (catalog, recommendation, lifecycle, memory, install).
- `adapters/claude_code/` — Claude Code MCP adapter (the reference adapter).
- `ui/` — operator-facing UI (in development).

## Session protocol summary

Full details in `planning/concierge-operations-protocol.md`. Critical points:

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

**Effort levels:** `xhigh` default. `max` for any architectural decision encountered mid-build.

## Ground rules

1. Read CLAUDE.md, the ops protocol, and the v2 blueprint in full before
   acting on the project.
2. Cite file paths for every claim about existing code.
3. Stop and ask when unsure. Don't guess intent.
4. Concrete over abstract. "This file at path X does Y" beats "the system
   appears to support Y functionality."
5. Working over pretty over clever.
6. Follow the operations protocol consistently. Mediocre adherence beats
   inconsistent perfection.
