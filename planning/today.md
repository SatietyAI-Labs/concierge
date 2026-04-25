# Today — 2026-04-29 (Day 8 — Pre-public-push prep block)

*Opens on: `SESSION-2026-04-28-01.md` (Day 7 — five tasks closed: Task 0.5
ops-protocol ratifications committed as `0f34999`; Task 0 Decision C+D
migration backfill committed as `daf5f42`; Task 1 narration fidelity
3-scenario validated; Task 2 torch reinstall recovered the venv per
Appendix C; Task 3 shim flake corrected attribution + fix committed as
`3aa4393`). Suite at **clean baseline** for the first time since Day 5
(783 passing, 0 failures, 1 skipped, 3 deselected). Authoritative plan
remains `planning/close-the-gap-plan-2026-04-23.md`. 48h shakedown clock
running clean against fixed-telemetry + fixed-wire-format since
2026-04-24 ~20:30 PDT; Day 7's changes touched test infrastructure +
one Alembic migration + one wiring change in `_maybe_install_on_approve`,
all unaffected by the recommend / SSE / lifecycle paths the shakedown
exercises.*

## Governing framing

Pre-public-push prep block. The durable scheduled work carried since
Day 5 finally lands. Day 7 closed Bucket A end-of-day with a clean
suite baseline; Day 8 opens the path toward repo-public-readiness.

Sequencing rule: **public-release gates run BEFORE surface-findings
work.** Tasks 0 + 1 are gates (must-fix-before-push); Task 2 is
surface-findings (informs Day 9, doesn't block Day 8 itself). Run
gates first; surface-findings third.

## Day 8 — Pre-public-push prep block

**Primary goal:** Two public-release gates closed (GitHub-hygiene audit
+ shim shebang portability fix); repository structure surface-findings
captured to inform Day 9. Suite stays at clean baseline (zero failures,
zero pre-existing flakes). 48h shakedown clock continues ticking
throughout.

## Tasks

| # | Task | Estimate | Status |
|---|---|---|---|
| 0 | **GitHub-hygiene audit.** Sweep `git log -p` for accidentally-committed secrets (API keys, tokens, credentials, OAuth refresh tokens). Audit `.env*` exclusion (verify `.gitignore` covers all variants; check `_legacy/` for any pre-existing `.env`-style files that may have leaked). Scan `planning/` and `docs/` for sensitive content that shouldn't ship publicly (operator names, machine paths, internal-only references that don't belong on a public GitHub page). Reference pre-ui-todo item 1. **Public-release gate** — does NOT slide. Surface findings + remediations together: any actual secret found gets surfaced before scrubbing (history-rewrite is a destructive operation that needs explicit auth). | ~45-60 min | **FIRST (gate before surface-findings work)** |
| 1 | **Shim wrapper shebang portability.** `scripts/concierge-shim` line 1 is hardcoded as `#!/home/satiety/.venvs/concierge-hackathon/bin/python3` — breaks for anyone cloning the repo. Replace with a portable invocation pattern (likely `#!/usr/bin/env python3` with environment-detection logic in the body, OR a wrapper-script-that-finds-the-venv pattern). Reference pre-ui-todo item 7 (added 2026-04-22 commit `e8a7e1b`). **Public-release gate** — does NOT slide. Single small commit with portability fix; smoke-test post-fix that the shim still launches correctly via stdio. | ~30-45 min | NEXT |
| 2 | **Repository structure audit.** Read the repo top-level as if you've never seen it before; flag anything that reads weird to a stranger landing on the GitHub page. Specific surfaces: (a) what's in `_legacy/` and does it ship publicly or stay archived (consider .gitignore'ing if it shouldn't ship); (b) what's in `planning/` that should be in `docs/` for public visibility, or vice versa; (c) any top-level files that are operator-internal vs. public-facing; (d) directory naming clarity for new readers; (e) inconsistencies a reviewer would flag. **Surface findings + decide together — don't fix yet.** Output lands as `planning/repo-structure-audit.md` (per Open Question 2 from `SESSION-2026-04-28-01.md`); Day 9 work consumes it as input. | ~45-60 min | NEXT (surface-findings; cut-if-behind candidate) |

**Total sized load:** ~2-2.5h depending on Task 0 secrets-found scope (if
any actual secret turns up, scope expands to include history-rewrite
authorization + execution). Tasks 0 + 1 sequential (gate ordering); Task
2 can run after either gate completes.

## End-of-day deliverable

- GitHub-hygiene audit complete; any secrets surfaced + remediation
  authorized + executed; `.env*` exclusion verified; planning-doc
  sensitivity scan documented (Day 8 SESSION snapshot Appendix)
- Shim shebang portability fix committed (single small commit); shim
  smoke-tested post-fix to confirm stdio invocation still works
- Repository structure audit findings captured as
  `planning/repo-structure-audit.md`; concrete recommendations for Day
  9 to act on (or explicit "no change needed for this surface")
- Day 8 SESSION snapshot written
  (`planning/sessions/SESSION-2026-04-29-NN.md`)
- Suite stays at clean baseline (zero failures, zero pre-existing
  flakes); any new failure that appears is treated as unambiguous
  regression signal per the new discipline carry-forward
- 48h shakedown clock continues running cleanly throughout

## Checkpoint criteria

- [ ] `git log -p` swept for secrets; result documented (none found OR list of findings + scrubbing decisions)
- [ ] `.gitignore` `.env*` exclusion verified; any `.env`-style files in `_legacy/` flagged
- [ ] `planning/` + `docs/` scanned for sensitive content; result documented
- [ ] `scripts/concierge-shim` shebang replaced with portable pattern; commit message describes the new invocation pattern
- [ ] Shim smoke-tested post-fix: a fresh subprocess invocation produces a valid initialize response over stdio (the `test_initialize_returns_capabilities_and_serverinfo` shape is sufficient)
- [ ] `planning/repo-structure-audit.md` written; covers `_legacy/` ship-vs-archive, `planning/` vs `docs/` boundary, top-level file shape, directory naming, inconsistency flags
- [ ] Full suite shows zero failures (m="not live_smoke and not slow") — clean baseline preserved
- [ ] Day 8 SESSION snapshot written

## Cut-if-behind ladder

**If behind schedule, cut in this order:**

1. **First cut: Task 2 (repo structure audit) → Day 9.** Surface-findings work that informs Day 9; not a Day 8 gate. The audit itself can land at the start of Day 9 with no quality loss; the only cost is Day 9's first task becomes "do the audit" rather than "act on the audit findings."

**Tasks 0 and 1 do NOT slide.** Both are public-release gates — Task 0 because secrets in `git log` are unrecoverable post-push; Task 1 because the shim is broken-for-everyone-but-Lewie until the shebang is portable. Pre-public-push prep that doesn't close these two gates isn't pre-public-push prep.

If Task 0 surfaces unexpected scope (multiple secrets requiring history rewrite, complex `.gitignore` edge cases, sensitive content in planning that needs case-by-case scrub decisions), surface that immediately rather than racing to compress all three tasks.

## What Day 8 is NOT

Explicitly excluded from Day 8 scope:

- **README writing** — Day 9 territory. The repo-structure-audit findings (Task 2) are inputs to README; the README itself is a separate scoped piece of work.
- **Pushing to a remote** — its own scheduled block, not Day 8. Pre-public-push prep is a prerequisite, not the push itself. The push happens after Day 8 + Day 9 are both done and Lewie has an explicit "go" moment.
- **Day 9 marketing/positioning work** — repo description, GitHub topics, social copy, project-card-on-portfolio framing, etc. All Day 9 territory.
- **Loader-emit wiring** — deferred until first real backing-server registration triggers the actual emit need (Open Question 2 from `SESSION-2026-04-25-03.md`)
- **Identity content shape** — deferred until v1.1; v1 ships with the current "loaded-on-boot list" shape
- **Demotion-count Option B shakedown** — bonus demo; optional, not load-bearing
- **Catalog-slug aliasing helper** — rides along with future grep work, no current consumer
- **Scanner-cadence revert** — end-of-soak checklist item; actioned only after the 48h shakedown gate clears
- **Untangling the hyphen/underscore install_method mismatch** — out-of-scope per Decision C+D scope discipline; the Day 7 `PROVENANCE_BY_RESULT_METHOD` translation boundary is the documented entry point for any future contributor tackling it

## Session opener

Paste this verbatim into a fresh Claude Code session to kick off Day 8:

---

> Read in order, then confirm understanding before acting:
>
> 1. `CLAUDE.md` (project root — v3 content superseding prior versions)
> 2. `planning/concierge-operations-protocol.md` ← especially the two newly-ratified sections from Day 7: "Decision-edit pattern" subsection of "The decision log" + "Wiring-test discipline" top-level section. Plus the existing "Live verify discipline" section ratified Day 5
> 3. `planning/sessions/SESSION-2026-04-28-01.md` ← Day 7 close-out covering five tasks; Appendix A (suite delta + clean-baseline confirmation); Appendix B (live narration 3-scenario transcripts); Appendix C (venv corruption event + operational discipline notes); Appendix D (shim flake corrected attribution); Appendix E (discipline carry-forward + ratifications applied prospectively)
> 4. `planning/sessions/SESSION-2026-04-27-01.md` ← Day 6 close-out (still authoritative for prior context: Option 3 implementation, Decision B post-hoc correction note, Appendix C four-data-point wiring-test narrative)
> 5. `planning/today.md` ← this file
> 6. `planning/decisions/DECISIONS.md` — tail; especially the three Day 6 entries with Decision B's post-hoc correction note. Decision C+D's scope-discipline framing informs Day 8 Task 2 (repo structure audit)
>
> Today is Day 8 — Pre-public-push prep block. Sequencing: Task 0 (GitHub hygiene) FIRST as a public-release gate, then Task 1 (shim shebang portability fix), then Task 2 (repository structure audit, surface-findings only). 48h shakedown clock continues running.
>
> Before starting code, report: your reading of the three tasks (sequencing, parallel-vs-serial structure, your proposed ordering); any concerns about the cut-if-behind ladder; whether you see anything in Task 0 that should be raised for case-by-case decision before scrubbing (e.g. specific commits flagged for secrets that need authorization).
>
> Effort: xhigh throughout. Bump to max for Task 0 if the secrets sweep surfaces non-trivial findings — history-rewrite is irreversible and warrants the deeper reasoning.
>
> Discipline carry-forward (durable constraints from Days 2-7, not just lessons):
> - **Test-fails-first** — for any new test landing on a fix, write the failing test against the pre-fix commit, confirm it fails for the right reason, then ship the fix
> - **Wiring tests assert client-observable contracts** — not "did the bytes/calls flow" but "did the consumer-visible state change as the client expects it." Default rule, not aspiration: if the contract is operator-observable, the wiring test must exercise it against reality, not mocks. (Now ratified in `planning/concierge-operations-protocol.md` "Wiring-test discipline" section.)
> - **Live shakedowns are fresh-session-only** for user-experience claims; build session is technical-signal-only (codified in ops-protocol)
> - **Single-block execution preferred** when the day's tasks are tight bug-fix + test cycles; surface defaults, infer authorization from absence of vetoes
> - **Surface-then-execute** for architectural decisions: surface the proposed approach (with concerns + cost estimate); user confirms or calibrates; only then execute. Day 7 surface-phase caught all six forks before code touched
> - **Mid-stream re-surface** for forks/surprises that weren't in the surfaced plan; don't try to resolve mid-task. Day 7 caught two such re-surfaces (Task 2 uv-sync side effect + Task 3 reframed attribution)
> - **In-place DECISIONS edits** OK for freshly-written entries (current session/day); corrections to prior-day entries land in the next snapshot's correction-note pattern (now ratified in ops-protocol "Decision-edit pattern" section)
> - **Report between steps; proceed unless intervened** — don't pause for explicit go-ahead per step. Surface for forks; report for completion; proceed otherwise
> - **Time-box discipline on ambiguous-scope investigations** — set explicit cap (e.g. 30 min for a flake-attribution investigation); if exceeded with surface-findings only, cut to defer rather than dig open-endedly. Applied to Day 7 Task 3; pattern flagged as candidate for ratification pending second data point
> - **Clean-baseline regression signal** — the suite is now at clean baseline; any regression from this point is unambiguous signal. Treat new failures with full surface-investigation discipline before assuming flakiness. The "passes alone, fails under suite" attribution shorthand from Days 5-6 is now a known wrong-cause-attribution shape; new failures get full diagnosis, not categorization
>
> Do not begin code until I confirm your reading and session plan.

---

*Note for the fresh session: Day 7 closed all five Bucket A items and
brought the suite to a clean baseline (zero failures) for the first
time since Day 5. The Day 7 ratifications (decision-edit pattern +
wiring-test discipline) are durable constraints applied prospectively
in Day 7's Task 0 wiring test (`tests/test_install_method_provenance.py`);
treat that test as the canonical wiring-test template for any future
persistent-state-contract work. The venv-corruption-events Appendix
pattern is candidate for ops-protocol ratification (per Appendix C
"Audit trail rationale") — wait for a second data point before
committing. Same for the time-box-discipline pattern (Day 7 Task 3
applied; pending second data point).*

*Open questions still outstanding (not blocking Day 8):*
- *Whether Fork 1 / Fork 4 deserve formal DECISIONS entries post-hoc (Fix Day 3)*
- *Install-path auto-transition vs scanner-owned state changes (Fix Day 3 Question 2)*
- *Skills-specific "used" detection signal sources (Fix Day 3 Question 3 / Fix Day 4 Fork H)*
- *Loader-emit wiring scheduling (Fix Day 4 Open Question 2 — when first real backing-server registration arrives)*
- *Catalog-slug aliasing convention (Fix Day 5 — well-known-tool-name → slug helper, e.g. `mlr` → `miller-mlr`; rides along with future grep work)*
- *Venv-corruption-events Appendix as ops-protocol section (Day 7 Appendix C — candidate, awaiting second data point)*
- *Time-box discipline on ambiguous-scope investigations (Day 7 Appendix E — candidate, awaiting second data point)*
- *Repo structure audit deliverable shape (Day 7 Open Question 2 — Day 8 Task 2 lands as `planning/repo-structure-audit.md`; resolved)*
