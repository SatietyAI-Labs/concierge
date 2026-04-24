# Today — 2026-04-25 (Fix Day 4)

*Opens on: `SESSION-2026-04-25-02.md` (Fix Day 3 — all seven tasks green;
tool-lifecycle transition validation shipped as hybrid service-method +
set-event-listener; usage-telemetry emit hooks wired with live verification
on recommend + install paths; loader unload + rich list_active; identity
notes end-to-end with integration-test-verified install cycle). Authoritative
plan remains `docs/close-the-gap-plan-2026-04-23.md`.*

## Governing framing

Ship-it-whole. Operational-first. Fix Day 4 is the narration-as-push + real-
time surface + promotion/demotion scanner + integration day. The §D schema
foundations (Fix Day 2) and validation+telemetry+identity wiring (Fix Day 3)
fed this day's work. Fix Day 4's job is to make Concierge visibly
collaborative inside a Claude Code session (narration), deliver request
notifications in real-time (SSE), automate the lifecycle scanner, and
integrate every Tier 1+2 change end-to-end.

## Fix Day 4 — Narration-as-push + real-time surface + scanner + integration

**Primary goal:** A fresh Claude Code session feels visibly collaborative
when Concierge is consulted. Real-time SSE delivers new-request events to
connected UI clients. Weekly scanner surfaces promotion/demotion candidates.
Full integration suite passes end-to-end.

## Tasks (from close-the-gap plan §Fix Day 4)

| # | Task | Estimate |
|---|---|---|
| 1 | **Narration-as-push, pattern 1:** enrich `concierge_recommend` + `concierge_request_tool` MCP tool descriptions with narration requirement ("After invoking this tool, your next user-visible message must briefly narrate the consultation"). Per DECISIONS `[2026-04-23]` — Push channel reframed as narration-as-push. | ~0.5-1h |
| 2 | **Narration-as-push, pattern 2:** MCP resources protocol implementation at `adapters/claude_code/resources.py`; expose X3/X4/X6/X7/X8 preambles + gap-preamble via `resources/list` + `resources/read`. Turns narration from per-tool instruction into session-long posture. | ~1-2h |
| 3 | **Narration-as-push, pattern 3:** piggyback observations in `RecommendResponse`. New optional `side_observations: list[str]` field on RecommendResponse schema; Opus prompt instructed to surface relevant adjacent observations when present. Agent surfaces these in narration. | ~0.5-1h |
| 4 | **C3 dual-channel real-time SSE:** add `/ui/events` SSE endpoint in FastAPI; `new_request` event fires when a request is filed via `create_request`; HTMX-friendly format. Connected UI clients receive push updates without polling. | ~1-2h |
| 5 | **C7 promotion/demotion scanner:** new `core/lifecycle_scanner.py`; APScheduler weekly job registered in FastAPI lifespan (not cron per DECISIONS `[2026-04-23]`); scans usage-log (tool_usage_events) for promotion candidates (5+ `used`/`recommended` events in 30d), demotion candidates (90+ days no events), stale pending (>7d). Auto-promotes on unambiguous signal via `transition_tool_lifecycle` with the identity hook; flags ambiguous cases for operator review. Writes summary to `/health` payload. | ~2-3h |
| 6 | **Session-id propagation across all three telemetry sites:** per Fork 2 (Fix Day 3), session_id is uniformly None today. Fix Day 4 wires real session-id across recommend (via RecommendRequest.session_id), install (via new LifecycleService param), and loader (via MCP session). Replaces the null placeholders with actual values. | ~0.5-1h |
| 7 | **Integration tests covering all Tier 1+2 changes end-to-end:** file a request → emit event → SSE delivers to subscriber → approve → install → ToolUsageEvent fires → scanner picks up → promotes → identity refreshes. Exercise the full cycle as one integration test. | ~1-2h |

**Total sized load:** ~6-12h.

## End-of-day deliverable

A fresh Claude Code session invoking `concierge_recommend` produces a
user-visible message narrating the consultation. `resources/list` returns
the five preambles; `resources/read` retrieves them. `RecommendResponse`
optionally includes `side_observations`. `GET /ui/events` streams SSE
new-request events to connected clients. Weekly scanner runs and surfaces
promotion/demotion candidates. Session-id propagates across all three
telemetry sites. Full integration suite passes end-to-end.

## Checkpoint criteria

- [ ] In a fresh Claude Code session, invoking `concierge_recommend` produces a user-visible message narrating the consultation
- [ ] `resources/list` returns the five preambles; `resources/read` retrieves them
- [ ] `RecommendResponse` optionally includes `side_observations` when Opus has relevant adjacent observations
- [ ] `GET /ui/events` streams SSE with `new_request` events when a request is filed
- [ ] Scanner run produces valid output for at least one test scenario (synthetic usage-log entries)
- [ ] `/health` payload includes scanner summary fields
- [ ] session_id populates on all three telemetry emit sites (recommend / install / loader) in a live cycle
- [ ] Integration test suite passes end-to-end
- [ ] Day 4 SESSION snapshot written

## Cut-if-behind ladder

**If behind schedule, cut:**
1. First cut: Pattern 2 (MCP resources protocol) scoped to tool-description enrichment only (Pattern 1 + 3), Pattern 2 deferred to soak. The user-facing narration is achievable via Patterns 1 and 3 alone.
2. Second cut: Scanner ships with auto-promotion only, demotion flagging deferred. Promotion is the demo-worthy signal; demotion can live as a `/health` counter initially.
3. Third cut: Task 6 (session-id propagation) slides. The null placeholders are honest per Fork 2; real propagation can ship with UI day if narration/scanner/SSE fill the day.

Tasks 1, 4, 5, 7 do NOT slide — Task 1 is narration's anchor; Task 4 is the real-time-surface deliverable; Task 5 makes lifecycle automatic; Task 7 proves integration.

## What Fix Day 4 is NOT

- Not UI tiles (UI Day after Fix Day 4)
- Not OpenClaw adapter (Phase 2)
- Not Claude Desktop adapter (Phase 2)
- Not PEP-668 install-strategy fix (still pending Lewie's ruling)
- Not true async sidecar push (Phase 3 per DECISIONS `[2026-04-23]` narration-as-push decision)

## Session opener

Paste this verbatim into a fresh Claude Code session to kick off Fix Day 4:

---

> Read in order, then confirm understanding before acting:
>
> 1. `CLAUDE.md` (project root — v3 content superseding prior versions)
> 2. `docs/concierge-operations-protocol.md`
> 3. `docs/concierge-blueprint-v2.md` (especially §Post-hackathon UI sections for Phase-2 boundary + §Failure Feedback Loop for wishlist/patterns)
> 4. `docs/close-the-gap-plan-2026-04-23.md` §Fix Day 4 section
> 5. `planning/sessions/SESSION-2026-04-25-02.md` ← Fix Day 3 close-out; hybrid transition validation, telemetry hooks, identity notes
> 6. `planning/today.md` ← this file
> 7. `planning/decisions/DECISIONS.md` — especially `[2026-04-23]` Push channel reframed as narration-as-push (authoritative for Task 1-3) and C7 scanner-in-v1 (authoritative for Task 5)
>
> Today is Fix Day 4 — narration-as-push + real-time surface + scanner + integration. Primary goal: fresh Claude Code session feels visibly collaborative when Concierge is consulted; real-time SSE; weekly scanner; full integration.
>
> Before starting code, report: your reading of the narration-as-push DECISIONS entry + C7 scanner entry, any concerns about the Fix Day 4 tasks or checkpoint criteria, and your proposed session structure (single block with surfaced defaults, same pattern as Fix Day 1/2/3).
>
> Effort: xhigh throughout. Bump to max for Task 5 (scanner design — auto-promote-vs-flag signal discrimination is subtle) and Task 2 (MCP resources protocol — session-long posture change shapes every subsequent prompt).
>
> Do not begin code until I confirm your reading and session plan.

---

*Note for the fresh session: Fix Day 3 wired three new surfaces (tool
transitions, telemetry, identity) that Fix Day 4 leverages. The scanner
(Task 5) is the primary caller of `transition_tool_lifecycle(session, tool,
state, on_transition=refresh_identity_on_loaded_on_boot_change)` — that's
the wiring point where loaded-on-boot transitions trigger identity refresh
automatically. Up until today it was manually-triggered-only.*

*Open questions still outstanding (not blocking Fix Day 4):*
- *PEP-668 install-strategy design (Fix Day 1)*
- *Whether Fork 1 / Fork 4 deserve formal DECISIONS entries post-hoc (Fix Day 3)*
- *Install-path auto-transition vs scanner-owned state changes (Fix Day 3 Question 2)*
- *Skills-specific "used" detection signal sources (Fix Day 3 Question 3 — candidate to fold into Task 5)*
