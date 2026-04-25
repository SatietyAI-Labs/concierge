# Today — 2026-04-28 (Day 7 — Bucket A continuation: backfill + ratifications + suite hygiene)

*Opens on: `SESSION-2026-04-27-01.md` (Day 6 — Option 3 Concierge-
managed venv shipped as `e7b6e75`; three DECISIONS entries committed
ahead of code as `64ec2bf` with two post-hoc Decision B corrections
caught by the Step 5 integration test; four-data-point wiring-test
meta-lesson codified in Appendix C). Authoritative plan remains
`docs/close-the-gap-plan-2026-04-23.md`. 48h shakedown clock running
clean against fixed-telemetry + fixed-wire-format since 2026-04-24
~20:30 PDT; Day 6's `core/install/` changes don't touch the
recommend / SSE / lifecycle paths the shakedown exercises.*

## Governing framing

Bucket A continuation. Day 6 shipped Task 0 (PEP-668 Option 3
end-to-end) but slid Tasks 1-3 to today per the cut-if-behind
ladder. Day 7 is "finish what Day 6 surfaced + close the
operational-discipline ratifications + return suite to a clean
baseline." No new feature work. No pre-public-push prep yet.

Sequencing rule: **operational-discipline ratifications run BEFORE
the day's substantive work.** End-of-day ratification means
disciplines drift from documentation-only to actual-practice;
better to ratify before practice than after. Task 0.5 is the
chronological first task even though numerically labelled as a
0-bridge.

## Day 7 — Bucket A continuation + ratifications + suite hygiene

**Primary goal:** Decision C+D migration backfill shipped (one-shot
commit-time tagging of pre-Option-3 `pip_user`-installed Tool rows
with `install_method_provenance` marker per the Fix Day 2 backfill
discipline); ops-protocol gains two new ratified sections (decision-
edit pattern + wiring-test discipline); narration design validated
across three task shapes (CSV stats, PDF→EPUB, trivial `wc -l`);
suite returns to a clean baseline (zero pre-existing failures, zero
flakes under full-suite ordering). 48h shakedown clock continues
ticking throughout.

## Tasks

| # | Task | Estimate | Status |
|---|---|---|---|
| 0.5 | **Ops-protocol Q2 + Q3 ratification** (single planning commit). Q2 — Decision-edit pattern: in-place edits OK for entries written in the current session/day; corrections to prior-day entries land in the next snapshot's correction-note pattern (per Day 5 Appendix D). Add to `docs/concierge-operations-protocol.md` Decision Log section. Q3 — Wiring-test discipline: promote SESSION-2026-04-27-01 Appendix C from snapshot-appendix to ops-protocol section, peer to "Live verify discipline." Codify the four-data-point evidence + the discipline statement ("if the contract is operator-observable, the wiring test must exercise it against reality, not mocks"). Single planning commit `docs(ops-protocol): ratify decision-edit pattern + wiring-test discipline`. **Runs FIRST** before any other work — operational discipline applies to today's own practice. | ~25 min combined | **FIRST (operational discipline before substantive work)** |
| 0 | **Migration backfill (Decision C+D follow-through).** Catalog row format gains an `install_method_provenance` field (Alembic schema migration). One-shot data migration tags every existing `Tool` row whose canonical install method is `pip_user` with `"pre-option-3-user-site"`. Wire `install_pip_user` to set the post-Option-3 marker on new installs (canonical value TBD at code-write time — likely `"option-3-venv"` or absence-of-marker; pick one and pin via wiring test). **Wiring test (per the just-ratified Q3 discipline) asserts every existing pre-Option-3 row gets the marker** — not just "the migration ran" but "the marker appears on every applicable row in the catalog after migration"; this is the client-observable contract. Identical pattern to Fix Day 2 lifecycle_state backfill. Separate small commit `feat(install): Decision C+D one-shot install_method_provenance backfill`. | ~1-1.5h | NEXT |
| 1 | **Live narration 3-scenario fidelity test.** Run the three scenarios from pre-ui-todo item 5 — (a) CSV stats, (b) PDF→EPUB, (c) trivial `wc -l` — in fresh Claude Code sessions per the ratified live-verify discipline (`docs/concierge-operations-protocol.md` "Live verify discipline" section). Capture transcripts as Day 7 SESSION snapshot Appendix B. Validates the narration-as-push design across multiple task shapes, not just the one csvkit shape from Day 4-6 verifies. **Most critical task for the public-release goal** — this is the design-validation evidence that the narration-as-push pattern works across the task shape space, not just one shape. | ~30-60 min | NEXT |
| 2 | **Torch / sentence-transformers env failures triage.** 13 failures in `tests/test_memory.py` + `tests/test_identity.py` rooted in `module 'torch' has no attribute 'LongTensor'`. Reproduces on `e7b6e75` (Day 6 close) and earlier; pre-existing per Day 5 verification. Either (a) fix the env (likely a torch version pin in dev venv vs runtime venv mismatch — see `SESSION-2026-04-26-01.md` §Appendix C hypothesis), or (b) properly bracket with `@pytest.mark.skipif` + documented skip-reason so the suite has a clean baseline. Decision between fix vs bracket per Lewie's preference; default lean toward fix if the env mismatch is straightforward. | ~30-60 min | NEXT |
| 3 | **`test_shim_e2e::test_notification_produces_no_response` flake triage.** Test passes alone (`pytest tests/test_shim_e2e.py::TestNotificationSemantics::test_notification_produces_no_response` — green) but fails under full-suite ordering. Same shape as torch failures — pre-existing per Day 5/6 verification. Either fix the order-dependency (likely a leaked async event loop / shim subprocess from a prior test) or properly bracket. | ~30 min | NEXT |

**Total sized load:** ~3-4h depending on Task 2 fix-vs-bracket
decision and any Task 0 schema-migration surprises. Tasks 1, 2, 3
can run conceptually in parallel (independent surfaces); Tasks 0.5
and 0 run sequentially first.

## End-of-day deliverable

- Ops-protocol ratifications committed (single planning commit)
- Decision C+D migration backfill shipped (Alembic migration + data
  migration + `install_pip_user` wiring + wiring test asserting every
  pre-Option-3 row gets the marker; small focused commit)
- Three live-narration transcripts (CSV / PDF→EPUB / wc -l) captured
  from FRESH Claude Code sessions per ratified discipline; transcripts
  in Day 7 SESSION snapshot Appendix B
- Suite returns to a clean baseline: zero failures, zero flakes under
  full-suite ordering. Either fixes or skip-marker brackets, with the
  reason documented for each skipped test
- Day 7 SESSION snapshot written (`planning/sessions/SESSION-2026-04-
  28-NN.md`)
- 48h shakedown clock continues running cleanly throughout

## Checkpoint criteria

- [ ] `docs/concierge-operations-protocol.md` has new sections: "Decision-edit pattern" + "Wiring-test discipline" — both ratified per today's Q2 / Q3 resolutions
- [ ] Single planning commit `docs(ops-protocol): ...` lands the ratifications
- [ ] Alembic migration adds `install_method_provenance` column to `Tool`
- [ ] One-shot data migration runs and tags every pre-Option-3 `pip_user` Tool row
- [ ] Wiring test asserts every applicable row gets the marker (not just "the migration ran")
- [ ] `install_pip_user` sets the post-Option-3 marker on new installs (or omits it per the chosen field shape)
- [ ] Three live-narration transcripts captured from fresh Claude Code sessions; transcripts in SESSION snapshot Appendix B
- [ ] Each scenario shows the narration phrase + concierge_recommend invocation (or documented absence with reasoning)
- [ ] Torch failures: either (a) all 13 passing post-fix, or (b) all 13 properly skipped with documented `@pytest.mark.skipif(reason=...)`
- [ ] Shim e2e flake: either (a) full-suite passes consistently, or (b) properly bracketed with documented reason
- [ ] Full suite shows zero failures (m="not live_smoke and not slow") — only passing + skipped + deselected
- [ ] Day 7 SESSION snapshot written

## Cut-if-behind ladder

**If behind schedule, cut in this order:**

1. **First cut: Task 3 (shim flake) → Day 8.** Pre-existing flake; not blocking the public-release goal. Bracket-with-rerun (`@pytest.mark.flaky(rerun=2)` or skip-marker) is acceptable as a stopgap if root-cause investigation runs long.
2. **Second cut: Task 2 (torch) → Day 8.** Same pre-existing class as Task 3. Bracket-with-skipif acceptable; the bracket itself is the load-bearing deliverable for "clean baseline."
3. **Third cut: Task 1 (narration fidelity) trims to 2 scenarios.** CSV is already validated end-to-end (Day 4 + Day 5 + Day 6 Appendix B if it lands); PDF→EPUB and wc -l are the new evidence. **Drop `wc -l` first if forced.** CSV stats + PDF→EPUB are higher-signal scenarios — they exercise narration on tasks where Concierge has real recommendations to make. `wc -l` was specifically the "does narration fire even on trivial tasks where consultation feels like overkill" probe per pre-ui-todo item 5; useful as a third data point, but the lowest-signal of the three. If only one of the two new scenarios lands, document which and why.

**Tasks 0.5 and 0 do NOT slide.** Task 0.5 is operational discipline that affects today's own practice; Task 0 is Decision C+D follow-through with a contract pinned in DECISIONS — outstanding promises shouldn't drift across a day boundary.

**Task 1 (narration fidelity) is the most critical for the public-release goal** — design-validation across shapes is what proves the narration-as-push pattern generalizes. If Task 1 itself can't run today (operator unavailable, shakedown blocker, etc.), surface that immediately rather than cutting silently.

## What Day 7 is NOT

Explicitly excluded from Day 7 scope:

- **Pre-public-push prep** — its own scheduled block, not Day 7. Includes README polish, secrets audit, demo-recording prep, repo-hygiene final pass, and any first-time-public-facing concerns
- **Loader-emit wiring** — deferred until first real backing-server registration triggers the actual emit need (Open Question 2 from `SESSION-2026-04-25-03.md`)
- **Identity content shape** — deferred until v1.1; v1 ships with the current "loaded-on-boot list" shape per Fix Day 3 design
- **Demotion-count Option B shakedown** — bonus demo (a task that recommends one of the 34-list loaded-on-boot tools to produce a sharper scanner-aggregate movement signal); optional, not load-bearing for any ship gate
- **Catalog-slug aliasing helper** — rides along with future grep work, no current consumer (Open Question 3 from `SESSION-2026-04-26-01.md`)
- **Scanner-cadence revert** — end-of-soak checklist item (`CronTrigger(hour=3, minute=0)` → `CronTrigger(day_of_week="sun", hour=3, minute=0)`); actioned only after the 48h shakedown gate clears
- **Expanding shim-script generator** beyond `install_pip_user` — Decision C+D capped Option 3 scope to Python tools; npm/npx/single_binary remain unchanged

## Session opener

Paste this verbatim into a fresh Claude Code session to kick off Day 7:

---

> Read in order, then confirm understanding before acting:
>
> 1. `CLAUDE.md` (project root — v3 content superseding prior versions)
> 2. `docs/concierge-operations-protocol.md` ← especially the "Live verify discipline" section ratified 2026-04-26 + the two new sections being ratified TODAY (decision-edit pattern + wiring-test discipline) per Task 0.5
> 3. `planning/sessions/SESSION-2026-04-27-01.md` ← Day 6 close-out covering Option 3 implementation; Appendix A (suite delta + zero-regression confirmation); Appendix C (four-data-point wiring-test meta-lesson — the discipline being ratified into ops-protocol today)
> 4. `planning/sessions/SESSION-2026-04-26-01.md` ← Day 5 close-out (still authoritative for prior context: Tasks 0 + 1, Appendix A audit, Appendix E live-verify discipline ratification)
> 5. `planning/today.md` ← this file
> 6. `planning/decisions/DECISIONS.md` — tail; especially the three Day 6 entries with Decision B's post-hoc correction note (mechanism for the wiring-test meta-lesson narrative)
>
> Today is Day 7 — Bucket A continuation + ratifications + suite hygiene. Sequencing: Task 0.5 (ops-protocol Q2 + Q3 ratification) runs FIRST per the rule "operational-discipline ratifications run before the day's substantive work." Then Task 0 (Decision C+D migration backfill), Tasks 1/2/3 in any order. 48h shakedown clock continues running.
>
> Before starting code, report: your reading of the five tasks (sequencing, parallel-vs-serial structure, your proposed ordering after Task 0.5 + Task 0); any concerns about the cut-if-behind ladder; whether you see any Day 7 NOT-scope item that's secretly in scope (e.g. is there hidden work in Task 0's migration that would qualify as "pre-public-push prep" cleanup?).
>
> Effort: xhigh throughout. Bump to max for Task 0 (Alembic schema migration is irreversible-ish — a wrong column type or constraint could require a follow-up migration to fix).
>
> Discipline carry-forward (durable constraints from Days 2-6, not just lessons):
> - **Test-fails-first** — for any new test landing on a fix, write the failing test against the pre-fix commit, confirm it fails for the right reason, then ship the fix
> - **Wiring tests assert client-observable contracts** — not "did the bytes/calls flow" but "did the consumer-visible state change as the client expects it." Four data points across Days 5-6: telemetry-commit rollback, SSE wire-format JSON-vs-Python-repr, venv `--system-site-packages=False` CLI rejection, venv atomic-rename shebang incompatibility. **Default rule, not aspiration**: if the contract is operator-observable, the wiring test must exercise it against reality, not mocks. (Ratified into ops-protocol today via Task 0.5 Q3.)
> - **Live shakedowns are fresh-session-only** for user-experience claims; build session is technical-signal-only (codified in ops-protocol)
> - **Single-block execution preferred** when the day's tasks are tight bug-fix + test cycles; surface defaults, infer authorization from absence of vetoes
> - **Surface-then-execute** for architectural decisions: surface the proposed approach (with concerns + cost estimate); user confirms or calibrates; only then execute. Day 6 surface-phase caught two corrections to Decision B before code touched
> - **Mid-stream re-surface** for forks/surprises that weren't in the surfaced plan; don't try to resolve mid-task. Day 6 Step 5 surfaced two such forks back-to-back; both resolved cleanly
> - **In-place DECISIONS edits** OK for freshly-written entries (current session/day); corrections to prior-day entries land in the next snapshot's correction-note pattern (ratified into ops-protocol today via Task 0.5 Q2)
> - **Report between steps; proceed unless intervened** — don't pause for explicit go-ahead per step. Surface for forks; report for completion; proceed otherwise
>
> Do not begin code until I confirm your reading and session plan.

---

*Note for the fresh session: Day 6 Option 3 work caught two
post-hoc Decision B corrections via the integration test, both
rooted in the same wiring-test gap shape. The discipline
carry-forward is now four data points strong (telemetry-commit,
SSE wire format, venv flag form, venv rename incompatibility) and
the ratification today promotes it from snapshot-appendix to
ops-protocol section. Treat the four-data-point wiring-test
discipline as a durable constraint on test-strategy choices, not
just a Day 5/6 lesson. Concretely: if you're writing a test today
that mocks `subprocess.run`, asserts on argv shape, and the
contract behind it touches CLI/filesystem/network/persistent-state
semantics, you're missing a wiring-test counterpart that must
exercise the contract against reality.*

*Open questions still outstanding (not blocking Day 7):*
- *Whether Fork 1 / Fork 4 deserve formal DECISIONS entries post-hoc (Fix Day 3)*
- *Install-path auto-transition vs scanner-owned state changes (Fix Day 3 Question 2)*
- *Skills-specific "used" detection signal sources (Fix Day 3 Question 3 / Fix Day 4 Fork H)*
- *Loader-emit wiring scheduling (Fix Day 4 Open Question 2 — when first real backing-server registration arrives)*
- *Catalog-slug aliasing convention (Fix Day 5 — well-known-tool-name → slug helper, e.g. `mlr` → `miller-mlr`; rides along with future grep work)*
