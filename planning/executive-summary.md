# Concierge — Executive Summary

*Built with Opus 4.7 hackathon | 2026-04-21 through 2026-04-26 | Solo builder*
*Companion to `planning/build-plan.md` — read this first.*

## What gets built

Platform-agnostic tool-awareness layer for AI agents. Three deliverables:

- **FastAPI core service** — SQLite catalog + Opus 4.7 recommendation engine
  + markdown-file-based lifecycle store + ChromaDB memory wrapper
- **Claude Code adapter** — stdio proxy shim exposing `concierge_recommend`,
  `concierge_request_tool` meta-tools mid-session without restart
- **Operator UI** — FastAPI + HTMX + Pico.css three sections: Tool Registry,
  Pending Requests Inbox, Health/Stats bar

## Scope and posture

| Metric | Value |
|---|---|
| Grand total effort | **46.5h** (yellow-flag ≥40h, red not tripped) |
| Full-ladder total | 43h (saves 3.5h across 4 pre-sequenced cuts) |
| Critical path (strict serial) | 27.5h of the 46.5h |
| Protected demo floor | 17 items / ~27h non-cuttable |
| Classification tally | 12 LIFT / 7 EXTRACT / 0 ADAPT / 0 REWRITE / 5 RETIRE |

## Day-by-day at a glance

| Day | Date | Theme | Target items | Ladder trigger |
|---|---|---|---|---|
| 1 | Tue 04-21 | Planning tail + **required** foundation sprint (health-check-gated) | Phase F + N1 + N2 (+ N3 stretch) | **Cut 4** fires at 10pm if N1+N2 not both committed-and-tested |
| 2 | Wed 04-22 | Service core + N10 pull-forward (~15.5h — Scenario A target) | N3/N4 finish + X3/X4/X6/X7/X11 + N5/N6/N7/N8 + N10 | none pre-sequenced |
| 3 | Thu 04-23 | Adapter integration (critical-path day) | N9→N14 + X8 + X13 | **Cut 3** first, then **Cut 2** |
| 4 | Fri 04-24 | UI three sections (sequential focus) | N15→N20 + N19 | **Cut 1** if N18 slips past 6 PM |
| 5 | Sat 04-25 | Stabilization + 5-consecutive-clean rehearsal | bug fixes, fragment tuning, record backup take | — |
| 6 | Sun 04-26 | Recording + submission | demo video, README, submit | — |

## Four Phase E adjustments (all embedded as day-plan items)

| Adjustment | Lands on |
|---|---|
| N8 smoke-test expansion to ~1.0-1.5h | Day 2 eve — fixture rec assertion + round-trip markdown parse |
| N10 stdio-shim pulled forward to Day 2 evening as DEFAULT | Day 2 eve block |
| N9 `tools/list_changed` spike, 0.5h hard time-box | Day 3 AM first 30 min |
| `temperature=0` on N6 Opus calls for demo runs | Day 2 PM at N6 implementation |

## Four pre-sequenced ladder cuts (day-of triggers)

| Cut | Day | Trigger | Saves | Impact |
|---|---|---|---|---|
| Cut 4 — defer markdown export from N3 ingest | Day 1 (10pm cutoff) | N1+N2 not both committed-and-tested by 10pm local Tuesday | 1.0h | Low |
| Cut 3 — defer `concierge_list_active` meta-tool | Day 3 AM | N11 slips past midday (auto-fires under Day-2 Scenario B) | 1.0h | Low |
| Cut 2 — drop X13 Python install module | Day 3 midday | Midday block overruns | 1.0h | Low (voiceover replaces live) |
| Cut 1 — trim Health/Stats bar to 3 tiles | Day 4 PM | N18 slips past 6 PM | 0.5h | Minimal |

**Beyond Cut 4 = Level-3 chat escalation** (touches demo materiality — N12
gap-report, N19 token-win, N5 memory wrapper, N16 filter/search, N18
dormant-badge).

## Top-5 risks

1. **Prompt-fragment correctness** (H/H) — Day 2 N8 fixture assertion catches
2. **Stdio shim debugging** (M-H/H) — Day 2 eve pull-forward buys debug time
3. **Day 3 serial-tail cascade** (M-H/M) — Cut 3 is first trigger
4. **Opus 4.7 recommendation variance** (M/H) — temperature=0 + Day 5 rehearsal
5. **Markdown parser surfacing late** (M/M-H) — Day 2 round-trip check catches

## Operating posture

- **Effort:** `xhigh` default; `max` for mid-build architectural decisions
- **Session protocol:** every session opens by reading most recent snapshot +
  build-plan.md day block + today.md; every session closes with a handoff
  snapshot
- **Decision logging:** any cut invoked, any architectural choice, any
  parallelism-realism override → one-liner in `planning/decisions/DECISIONS.md`
- **Soft limits:** 6h active session or 70% context → handoff trigger
- **Hard limits:** 8h active or 85% context → force handoff

## Phase-F questions — status

1. **Tuesday evening sprint framing:** RESOLVED 2026-04-21 — **required**,
   N1+N2 health-check-gated, 10pm Cut 4 trigger. See DECISIONS
   `[2026-04-21 17:30]`.
2. **Level-3 escalation destination:** Claude.ai chat (not mid-build) —
   implicitly accepted at Phase F signoff.

## Tuesday-evening safety valve

Health check at ~8pm local (post-N1, pre-N2). Criteria: can I read my own
code; ≤2 trivial mistakes last hour; tired-but-engaged (not tired-and-sloppy).
Fail any → end sprint, N2 rolls to Wednesday, Cut 4 fires at 10pm automatically.
"Required" ≠ "push through injury."

---

*Full plan: `planning/build-plan.md`. Inputs: Phases A-E deliverables in
`planning/`. Decisions log: `planning/decisions/DECISIONS.md`.*
