# Today — 2026-04-27 (Day 6 — Bucket A: blockers + suite hygiene)

*Opens on: `SESSION-2026-04-26-01.md` (Fix Day 5 — Task 0 telemetry-
commit fix shipped as `8ee0af3`; Task 1 SSE wire-format JSON
serialization fix shipped as `6f5239f`; full audit table for both;
Appendix E ratified into ops-protocol's new "Live verify discipline"
section). Authoritative plan remains `docs/close-the-gap-plan-2026-
04-23.md`. 48h shakedown clock running against fixed-telemetry +
fixed-wire-format since 2026-04-24 ~20:30 PDT.*

## Governing framing

Bucket A only. Day 6 is the blockers + suite-hygiene day before any
new feature work or pre-public-push prep. The protected operational
core (catalog + recommendation + lifecycle + adapter + the now-fixed
telemetry persistence + the now-fixed SSE wire format) is healthy;
Day 6's job is to clear the four operator-blocking / suite-hygiene
items so the 48h shakedown clock crosses cleanly and the next set of
day's work has a clean baseline to build on.

No feature work. No new surfaces. No demo polish. Each task is either
an operator-input-needed unblock (Task 0), a multi-shape validation of
work already done (Task 1), or a regression-from-clean-baseline
restoration (Tasks 2 + 3).

## Day 6 — Bucket A blockers + suite hygiene

**Primary goal:** PEP-668 install-strategy decided + implemented;
narration design validated across three task shapes (not just one);
suite returns to a clean baseline (zero pre-existing failures, zero
flakes under full-suite ordering). 48h shakedown clock continues
ticking against fixed-telemetry + fixed-wire-format throughout.

## Tasks

| # | Task | Estimate | Status |
|---|---|---|---|
| 0 | **PEP-668 install-strategy decision + implementation.** Operator (Lewie) provides the decision among options surfaced in pre-ui-todo item 1 — `pipx` / system `pip3 --break-system-packages` / venv-managed install / escalation-to-operator (i.e. install_dispatcher returns `None` and the operator handles manually). Once decided, implement in `core/install/dispatcher.py` (or wherever the canonical install_method dispatch lives) and add tests for the chosen path. Operator-blocking until the decision lands; carry from Fix Day 1 still-open + today's Open Question 1. | ~1-3h depending on choice | **WAITING ON OPERATOR DECISION** |
| 1 | **Live narration 3-scenario fidelity test.** Run the three scenarios from pre-ui-todo item 5 — (a) CSV stats, (b) PDF→EPUB, (c) trivial `wc -l` — in fresh Claude Code sessions per the now-ratified live-verify discipline (see `docs/concierge-operations-protocol.md` "Live verify discipline" section, ratified 2026-04-26 via Appendix E of `SESSION-2026-04-26-01.md`). Capture transcripts as Day 6 SESSION snapshot Appendix B. Validates the narration-as-push design across multiple task shapes, not just the one csvkit shape from Day 4 / Day 5 verifies. | ~30-60 min | NEXT ACTIVE (no blocker) |
| 2 | **Torch / sentence-transformers env failures triage.** 13 failures in `tests/test_memory.py` + `tests/test_identity.py` rooted in `module 'torch' has no attribute 'LongTensor'`. Reproduces on `8ee0af3` and earlier; not a regression from any Day 5 work. Either (a) fix the env (likely a torch version pin in dev venv vs runtime venv mismatch — see `SESSION-2026-04-26-01.md` §Appendix C hypothesis), or (b) properly bracket with `@pytest.mark.skipif` + clear skip-reason so the suite has a clean baseline (zero failures, N skipped with documented reason). Decision between fix vs bracket per Lewie's preference; default lean toward fix if the env mismatch is straightforward. | ~30-60 min | NEXT |
| 3 | **`test_shim_e2e::test_notification_produces_no_response` flake triage.** Test passes alone (`pytest tests/test_shim_e2e.py::TestNotificationSemantics::test_notification_produces_no_response` — green) but fails under full-suite ordering. Same shape as torch failures — pre-existing on `8ee0af3` per the `git stash` round-trip in `SESSION-2026-04-26-01.md` §Task 1 close-out. Either fix the order-dependency (likely a leaked async event loop / shim subprocess from a prior test) or properly bracket. | ~30 min | NEXT |

**Total sized load:** ~2.5-5h depending on Task 0 choice + Task 2
fix-vs-bracket decision. Tasks 1, 2, 3 can run in parallel
conceptually (independent surfaces); Task 0 may serialize behind the
operator decision but its implementation can land between other tasks.

## End-of-day deliverable

- PEP-668 install-strategy decided (DECISIONS entry) + implemented
  (commit) + tests landed
- Three live-narration transcripts captured in Day 6 SESSION snapshot
  Appendix B, validating narration across CSV / PDF→EPUB / wc -l task
  shapes
- Suite returns to a clean baseline: zero failures, zero flakes under
  full-suite ordering. Either fixes or skip-marker brackets, with the
  reason documented for each skipped test
- Day 6 SESSION snapshot written (`planning/sessions/SESSION-2026-04-
  27-NN.md`)
- 48h shakedown clock continues running cleanly throughout

## Checkpoint criteria

- [ ] PEP-668 install-strategy decision logged in `planning/decisions/DECISIONS.md` with rationale among the four options
- [ ] `install_dispatcher` (or canonical install path) implements the chosen strategy with tests landed
- [ ] Three live-narration transcripts (CSV / PDF→EPUB / wc -l) captured from FRESH Claude Code sessions per ratified discipline; transcripts in Day 6 SESSION snapshot Appendix B
- [ ] Each scenario shows the narration phrase + concierge_recommend invocation (or documented absence with reasoning)
- [ ] Torch failures: either (a) all 13 passing post-fix, or (b) all 13 properly skipped with documented `@pytest.mark.skipif(reason=...)`
- [ ] Shim e2e flake: either (a) full-suite passes consistently, or (b) properly bracketed with documented reason
- [ ] Full suite shows zero failures (m="not live_smoke") — only passing + skipped + deselected
- [ ] Day 6 SESSION snapshot written

## Cut-if-behind ladder

**If behind schedule, cut:**

1. **First cut: Task 1 (3-scenario narration test) trims to 2 scenarios.** CSV is already validated end-to-end (Day 4 + Day 5 Appendix B); PDF→EPUB and wc -l are the new evidence. If only one of those two lands, document which and why; the design already has one shape's worth of validation.
2. **Second cut: Task 3 (shim flake) accepts a temporary `@pytest.mark.flaky(rerun=2)` marker** if the root-cause investigation runs longer than 30 min. Bracketing as flake-with-rerun is acceptable as a stopgap; full root-cause can roll to pre-public-push prep window.
3. **Third cut: Task 2 (torch) accepts the bracket-with-skipif path** even if the fix looks straightforward but threatens the day's clean-baseline deliverable. Bracket-then-fix is acceptable; the bracket itself is the load-bearing deliverable for "clean baseline."

Task 0 does NOT slide — it's operator-blocking on a decision that's been outstanding since Fix Day 1, and unblocking it is the highest-leverage thing to ship today regardless of other tasks.

## What Day 6 is NOT

Explicitly excluded from Day 6 scope:

- **Pre-public-push prep** — its own scheduled block, not Day 6. Includes README polish, secrets audit, demo-recording prep, repo-hygiene final pass, and any first-time-public-facing concerns
- **Loader-emit wiring** — deferred until first real backing-server registration triggers the actual emit need (Open Question 2 from `SESSION-2026-04-25-03.md`)
- **Identity content shape** — deferred until v1.1; v1 ships with the current "loaded-on-boot list" shape per Fix Day 3 design
- **Demotion-count Option B shakedown** — bonus demo (a task that recommends one of the 34-list loaded-on-boot tools to produce a sharper scanner-aggregate movement signal); optional, not load-bearing for any ship gate
- **Catalog-slug aliasing helper** — rides along with future grep work, no current consumer (Open Question 3 from `SESSION-2026-04-26-01.md`)
- **Scanner-cadence revert** — end-of-soak checklist item (`CronTrigger(hour=3, minute=0)` → `CronTrigger(day_of_week="sun", hour=3, minute=0)`); actioned only after the 48h shakedown gate clears

## Session opener

Paste this verbatim into a fresh Claude Code session to kick off Day 6:

---

> Read in order, then confirm understanding before acting:
>
> 1. `CLAUDE.md` (project root — v3 content superseding prior versions)
> 2. `docs/concierge-operations-protocol.md` ← especially the new "Live verify discipline" section (ratified 2026-04-26)
> 3. `planning/sessions/SESSION-2026-04-26-01.md` ← Fix Day 5 close-out covering Tasks 0 + 1; Appendix A (audit verdict table); Appendix B (Day 5 live verify); Appendix C (suite delta + torch hypothesis); Appendix E (live-shakedown discipline ratification); Task 1 close-out section (SSE wire-format bug + meta-lesson on wiring tests asserting client-observable contracts)
> 4. `planning/today.md` ← this file
> 5. `planning/decisions/DECISIONS.md` — tail; especially Fix Day 4 entries (Forks A, B, C, D, G, I) referenced from yesterday's audit table
>
> Today is Day 6 — Bucket A blockers + suite hygiene. Primary goal: PEP-668 install-strategy decided + implemented; narration design validated across three task shapes (not just one); suite returns to a clean baseline. 48h shakedown clock continues running.
>
> Before starting code, report: your reading of the four tasks (which is operator-blocking, which can run in parallel, your proposed sequencing), any concerns about the cut-if-behind ladder, and whether you see any Day 6 NOT-scope item that's secretly in scope (e.g. is there hidden work in Task 2's torch fix that would qualify as "pre-public-push prep" cleanup?).
>
> Effort: xhigh throughout. Bump to max for Task 0 (PEP-668 decision is a multi-environment-affecting choice — pipx vs system-pip3 vs venv-managed has different soak / portability / CI implications) and Task 2 (torch env triage may surface deeper venv-management questions worth surfacing as a DECISIONS entry rather than a code patch).
>
> Discipline carry-forward from Day 5:
> - **Test-fails-first** — for any new test landing on a fix, write the failing test against the pre-fix commit, confirm it fails for the right reason, then ship the fix
> - **Wiring tests assert client-observable contracts** — not "did the bytes/calls flow" but "did the consumer-visible state change as the client expects it." See SESSION-2026-04-26-01.md Task 1 close-out for the worked pattern
> - **Live shakedowns are fresh-session-only** for user-experience claims; build session is technical-signal-only (now codified in ops-protocol)
> - **Single-block execution preferred** when the day's tasks are tight bug-fix + test cycles; surface defaults, infer authorization from absence of vetoes
>
> Do not begin code until I confirm your reading and session plan.

---

*Note for the fresh session: Day 5 shipped two consecutive bug fixes
of identical wiring-test-gap shape (telemetry-commit + SSE wire
format). The wiring-test-gap meta-lesson is the most important
discipline carry-forward — every new test on a fix should ask "does
this assert what the client actually depends on?" before the test
text is written, not after.*

*Open questions still outstanding (not blocking Day 6):*
- *Whether Fork 1 / Fork 4 deserve formal DECISIONS entries post-hoc (Fix Day 3)*
- *Install-path auto-transition vs scanner-owned state changes (Fix Day 3 Question 2)*
- *Skills-specific "used" detection signal sources (Fix Day 3 Question 3 / Fix Day 4 Fork H)*
- *Loader-emit wiring scheduling (Fix Day 4 Open Question 2 — when first real backing-server registration arrives)*
- *Catalog-slug aliasing convention (Fix Day 5 — well-known-tool-name → slug helper, e.g. `mlr` → `miller-mlr`; rides along with future grep work)*
- *Wiring-test discipline codification (Fix Day 5 Task 1 — peer to "Test fixture management" in ops-protocol; flagged in SESSION-2026-04-26-01 Task 1 close-out)*
