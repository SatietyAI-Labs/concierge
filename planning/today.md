# Today — 2026-04-30 (Day 9 — README day)

*Opens on: `SESSION-2026-04-29-01.md` (Day 8 — three tasks closed:
Task 0 GitHub-hygiene audit, Task 1 shim shebang portability via
`[project.scripts]` console-script, Task 2 repository structure
audit; end-of-day remediation phase landed three coherent commits
including DECISIONS `[2026-04-29 Day 8] EXTRACT invariant retired
pre-public-push`). Suite at **763/0/1/3** — clean baseline preserved
in the rebased sense; the −20 delta from Day 7 baseline (783) is the
intentional `tests/test_prompts.py` deletion (byte-identity drift-
checks no longer load-bearing). Live MCP runs cleanly out of
`.venv/bin/concierge-shim`; `concierge-hackathon` venv retired
permanently. 48h shakedown clock continues running clean since
2026-04-24 ~20:30 PDT against fixed-telemetry + fixed-wire-format;
Day 8's changes touched test infrastructure + prompt-fragment
content + `_legacy/` index entries + `docs/`/`planning/` reorg
(none affecting recommend / SSE / lifecycle paths the shakedown
exercises).*

## Governing framing

README day. Day 8 closed the structural-cleanup phase; Day 9 closes
the public-presentation phase. The repo's substantive content is now
in shape (prompts sanitized, `_legacy/` removed from index,
`docs/`/`planning/` reorg landed, audit-doc captured); the public
face is still a 3-line stub. Day 9 fixes that.

Sequencing rule: README rewrite is the load-bearing primary
deliverable; LICENSE is a small fast-win that lands alongside;
CLAUDE.md prune + ABOUT.md/bio creation is high-priority cleanup
that informs the README's framing of where personal context lives.
Run README first (Task 1) so its scope shape informs the prune
work; LICENSE second (Task 2) as the quick mechanical add; CLAUDE.md
prune + ABOUT.md third (Task 3).

## Day 9 — README day

**Primary goal:** Substantive `README.md` replacing the 3-line stub
with Vision-section-derived public-facing content; `LICENSE` (MIT)
added; `CLAUDE.md` pruned of operator-specific content and
hackathon-framing-from-lede; new `ABOUT.md` (or equivalent) absorbs
the relocated personal context. Suite stays at clean baseline. 48h
shakedown clock continues ticking throughout.

## Tasks

| # | Task | Estimate | Status |
|---|---|---|---|
| 1 | **README rewrite (substantive).** Replace the 3-line stub at `README.md` with substantive public-facing content. **Lede draws heavily from CLAUDE.md's Vision section** — its three paragraphs (harness-agnostic substrate / third voice / multi-tier-agent escalation) are the strongest articulation of what Concierge IS that exists anywhere in the docs; Day 9 shouldn't reinvent it. Sections to cover: vision/what-is-Concierge (lede), what-it-does (concrete behavior, drawing from `planning/concierge-blueprint-v2.md` + worked examples), install instructions (per the Task 1 commit body's operator-action guidance: clone → `uv sync --extra dev` → register `<repo>/.venv/bin/concierge-shim` with Claude Code MCP config), basic usage (point at `concierge_recommend` flow with sample task fixtures), origin section (hackathon-week framing relocated here, near the bottom — context for "why this exists" without dominating the lede). Reference the Days 9-12 arc only insofar as it shapes "what's coming next." Internal references should point at `planning/concierge-operations-protocol.md` etc. (post-Day-8-reorg paths; not legacy `docs/` paths). Harmonize with `pyproject.toml` description ("Platform-agnostic tool awareness layer for AI agents"). | ~75-90 min | **FIRST (load-bearing public-facing)** |
| 2 | **LICENSE = MIT.** Add `LICENSE` at top-level with standard MIT text. Year 2026, copyright holder Lewie / SatietyAI per Lewie's brand-publicity calibration. New DECISIONS entry `[2026-04-30 Day 9] LICENSE = MIT` (Context / Decision / Reasoning / Reversibility / Decided by / Affects per standard template). Update `pyproject.toml` to add `license = { text = "MIT" }` (or `license-files = ["LICENSE"]` per modern PEP 639 — pick the cleaner expression). Reference in README's footer. | ~15-30 min | NEXT (small fast-win) |
| 3 | **CLAUDE.md prune + ABOUT.md creation.** Pull operator-specific content out of `CLAUDE.md`: the "Personal context" section (brands, daily drivers, build-week timeline, "13 months into AI", "never built a UI"), the operator-environment ground rule ("Honor the filesystem split. Code on Windows, runtime on native WSL."), the stale "empty during planning" statements for `core/` and `adapters/claude_code/`, the stale "April 21-26, 2026" hackathon target dates. Land the relocated personal context in `ABOUT.md` (or `docs/ABOUT.md` if Lewie prefers a docs-folder anchor; this is also where Day 9 first populates the now-empty `docs/`). Drop hackathon framing from CLAUDE.md's lede; if any hackathon-origin context remains, it lives in an "Origin" section near the bottom (mirroring README's structure). Trim the "Existing code locations" section since `_legacy/` is now gitignored — keep only the historical-context narrative, drop the navigation references. Update "Output locations" section (already partially Day-8-stale: `docs/` is empty until repopulated; `_legacy/` is gone from public). | ~60-75 min | NEXT (case-by-case editorial; high-priority) |

**Total sized load:** ~2.5-3.5h depending on Task 1's depth (most
of the variance is in README scope — how much install-and-usage
content lands today vs slips to a follow-up). Tasks 1 → 2 → 3
sequential per the ordering rationale; Task 2 (LICENSE) could run
in parallel with Task 1 if Lewie wants, but the small-fast-win
shape suggests linear sequencing.

## End-of-day deliverable

- `README.md` substantive rewrite committed; lede from Vision
  section; install + basic usage covered; hackathon-origin in
  "Origin" section near bottom
- `LICENSE` (MIT) added; DECISIONS entry written;
  `pyproject.toml` license field updated
- `CLAUDE.md` pruned; operator-specific content relocated to
  `ABOUT.md` (or equivalent); hackathon framing dropped from lede;
  stale build-week-only text removed
- `pyproject.toml` description and `README.md` framing harmonized
- Day 9 SESSION snapshot written
  (`planning/sessions/SESSION-2026-04-30-NN.md`)
- Suite stays at clean baseline (or, if Day 8's flake rate
  reproduces, characterized again with N≥5 sampling per the
  Appendix D evolution)
- 48h shakedown clock continues running cleanly

## Checkpoint criteria

- [ ] `README.md` carries Vision-section-derived lede; install
      instructions present and accurate; basic usage section
      points at `concierge_recommend` flow; hackathon framing
      lives in lower section (not lede)
- [ ] `LICENSE` exists at top-level with MIT text; year 2026;
      copyright holder per Lewie's calibration
- [ ] DECISIONS entry `[2026-04-30 Day 9] LICENSE = MIT` written
      following standard template
- [ ] `pyproject.toml` license metadata field updated
- [ ] `CLAUDE.md` lede carries no hackathon framing or
      operator-environment-specific content
- [ ] `ABOUT.md` (or chosen equivalent) absorbs relocated personal
      context; CLAUDE.md cross-references the new location
- [ ] Stale CLAUDE.md statements removed: "empty during planning"
      for `core/` and `adapters/claude_code/`; "April 21-26, 2026"
      target dates; "Existing code locations" navigation refs to
      `_legacy/` (gitignored as of Day 8)
- [ ] Internal cross-references in README + CLAUDE.md + ABOUT.md
      point at post-Day-8-reorg paths (`planning/concierge-*` not
      `docs/concierge-*`)
- [ ] Full suite shows zero failures (m="not live_smoke and not
      slow") OR flake-rate characterization runs N≥5 if first run
      shows failures (per Day 8 Appendix D)
- [ ] Day 9 SESSION snapshot written

## Cut-if-behind ladder

**If behind schedule, cut in this order:**

1. **First cut: Task 3 (CLAUDE.md prune + ABOUT.md) → Day 10
   morning.** README + LICENSE are the load-bearing public-facing
   work; CLAUDE.md prune is internal cleanup that doesn't block
   public readiness. The personal context stays in CLAUDE.md
   temporarily — fine while internal-to-build; not ideal in public,
   but recoverable on Day 10.

2. **Second cut: trim Task 1 README scope to lede + install +
   minimal-usage (drop comprehensive usage section).** A thin
   README is far better than no README; comprehensive usage docs
   can land Day 11 (during launch-artifacts work) if Day 9 runs out.

**Tasks 1 + 2 do NOT both slide.** README must land (it's the public
face); LICENSE must land (legal default without one is "all rights
reserved"). If both Task 1 trimming AND Task 3 cut still leave Day 9
in trouble, surface to Lewie immediately rather than racing.

## What Day 9 is NOT

Explicitly excluded from Day 9 scope:

- **UI work** — Day 10 territory per Days 9-12 arc. The agent-as-
  substrate is the primary product surface; UI is administrative
  observability that complements it. Day 10 alignment session
  decides UI shape.
- **CHANGELOG.md / CONTRIBUTING.md / `.github/ISSUE_TEMPLATE/`** —
  Day 11 launch artifacts.
- **Demo recording (60-90s screen recording of Day 7 narration
  scenarios)** — Day 11.
- **Blog post / launch thread draft** — Day 11.
- **Pushing to GitHub remote** — Day 12.
- **`~/.satiety-pipeline/` generic-equivalent question** — Day 8
  forward-pointer flagged today; consider during README review
  (does the example "save to `~/.satiety-pipeline/drafts/`" feel
  weird-specific to a stranger?) but don't necessarily action.
  Touching the just-sanitized prompts is sensitive scope; surface
  before any change.
- **Flake-rate P2 investigation** (Day 8 Appendix B) — only if
  Day 9 has substantial headroom. Default: defer to Day 10
  alignment.
- **Loader-emit wiring** — deferred until first real backing-server
  registration triggers the actual emit need (Open Question 2 from
  `SESSION-2026-04-25-03.md`)
- **Identity content shape** — deferred until v1.1
- **Demotion-count Option B shakedown** — bonus demo; optional
- **Catalog-slug aliasing helper** — rides along with future grep
  work
- **Scanner-cadence revert** — end-of-soak checklist; actioned
  only after the 48h shakedown gate clears
- **Untangling the hyphen/underscore install_method mismatch** —
  out-of-scope per Decision C+D scope discipline; documented
  translation boundary in `PROVENANCE_BY_RESULT_METHOD`

## Session opener

Paste this verbatim into a fresh Claude Code session to kick off Day 9:

---

> Read in order, then confirm understanding before acting:
>
> 1. `CLAUDE.md` (project root — v3 content; note: Day 9 task 3 prunes operator-specific content from this file, so read for current ground rules and flag any that should already be relocated)
> 2. `planning/concierge-operations-protocol.md` ← three ratified disciplines: "Decision-edit pattern", "Wiring-test discipline", and "Live verify discipline". (Note: this file moved from `docs/` to `planning/` in Day 8 commit `102ef2f`.)
> 3. `planning/sessions/SESSION-2026-04-29-01.md` ← Day 8 close-out covering three tasks + end-of-day three-commit remediation phase; Appendix A (suite delta + clean-baseline confirmation in the rebased sense), Appendix B (flake-rate characterization N=5; 1/5 = 20%; P2 priority), Appendix C (venv consolidation event + single-venv discipline candidate), Appendix D (clean-baseline-flake-rate refinement candidate), Appendix E (discipline carry-forward + ratifications applied prospectively); Days 9-12 forward arc
> 4. `planning/sessions/SESSION-2026-04-28-01.md` ← Day 7 close-out (still authoritative for prior context: clean-baseline-regression-signal ratification, decision-edit pattern + wiring-test discipline ratification + Day 7 Appendices)
> 5. `planning/today.md` ← this file
> 6. `planning/decisions/DECISIONS.md` — tail; especially the new `[2026-04-29 Day 8] EXTRACT invariant retired pre-public-push` entry. Day 9 README work needs to know what's authoritative post-retirement (prompt-fragment constants are Concierge-canonical; OpenClaw lineage documented in docstrings + retired SKILL_FRAGMENT_SYNC_LOG; constant naming preserved as historical)
>
> Today is Day 9 — README day. Sequencing: Task 1 (README rewrite, substantive) FIRST as the load-bearing public-facing deliverable, then Task 2 (LICENSE = MIT) as the small fast-win, then Task 3 (CLAUDE.md prune + ABOUT.md creation) as the case-by-case editorial work. 48h shakedown clock continues running.
>
> Before starting code, report: your reading of the three tasks (sequencing, scope, your proposed approach for Task 1's lede draw from Vision section); any concerns about the cut-if-behind ladder; whether you see anything in Task 1 that should be raised for case-by-case decision before drafting (e.g. specific framing choices for the README's lede; whether install instructions should reference the `<repo>/.venv/bin/concierge-shim` path explicitly or use a generic placeholder; whether the README references the post-Day-8 prompt-sanitization narrative anywhere or stays scope-tight on what-Concierge-is).
>
> Effort: xhigh throughout. Bump to max for Task 1 if the README lede needs deeper reasoning to harmonize Vision-section + blueprint-v2 + pyproject description into a coherent public-facing voice.
>
> Discipline carry-forward (durable constraints from Days 2-8, not just lessons):
> - **Test-fails-first** — for any new test landing on a fix, write the failing test against the pre-fix commit, confirm it fails for the right reason, then ship the fix
> - **Wiring tests assert client-observable contracts** — default rule, not aspiration: if the contract is operator-observable, the wiring test must exercise it against reality, not mocks. (Ratified in `planning/concierge-operations-protocol.md` "Wiring-test discipline" section.)
> - **Live shakedowns are fresh-session-only** for user-experience claims; build session is technical-signal-only (codified in ops-protocol)
> - **Single-block execution preferred** when the day's tasks are tight bug-fix + test cycles; surface defaults, infer authorization from absence of vetoes
> - **Surface-then-execute** for architectural decisions: surface the proposed approach (with concerns + cost estimate); user confirms or calibrates; only then execute. Day 8 surface-phases caught all forks before code touched
> - **Mid-stream re-surface** for forks/surprises that weren't in the surfaced plan; don't try to resolve mid-task. Day 8 caught the parallel-venv discovery (Task 1) and the substantive Class-3 finding's reframe (Task 0 close-out) via mid-stream re-surface
> - **In-place DECISIONS edits** OK for freshly-written entries (current session/day); corrections to prior-day entries land in the next snapshot's correction-note pattern (ratified in ops-protocol "Decision-edit pattern" section). Day 8 applied this to the cross-reference grep-and-update during commit 3 (skipped historical-record files; touched only current-day live docs)
> - **Report between steps; proceed unless intervened** — don't pause for explicit go-ahead per step. Surface for forks; report for completion; proceed otherwise
> - **Time-box discipline on ambiguous-scope investigations** — set explicit cap (e.g. 30 min for an investigation); if exceeded with surface-findings only, cut to defer rather than dig open-endedly. Applied Day 7 Task 3 + Day 8 flake-rate investigation; pattern flagged as candidate for ratification pending second-data-point cycle
> - **Clean-baseline regression signal** — any regression from baseline is unambiguous signal; investigate before categorizing. **Day 8 evolution (candidate refinement, Appendix D):** single-shot suite runs aren't proof of clean baseline if a failure mode is intermittent. For test surfaces with non-deterministic-prone tests (integration / network / heavy fixture / real-subprocess), the evidence standard for "clean baseline" is N≥5 samples produced by the same code state, not a single full-suite pass. Pending ratification at second data point
> - **Single-venv discipline (candidate, Day 8 Appendix C):** when uv is the dependency manager, treat `.venv` as the canonical project venv; manually-created venvs at custom paths fight uv's defaults. Pending ratification at second data point
>
> Do not begin code until I confirm your reading and session plan.

---

*Note for the fresh session: Day 8 closed all three Bucket A items
and delivered the end-of-day three-commit remediation phase. The
day's main durable artifact is `DECISIONS [2026-04-29 Day 8]
EXTRACT invariant retired pre-public-push` — Day 9 README work
needs to internalize that prompt-fragment constants are now
Concierge-canonical (not byte-identical to OpenClaw sources). The
two new candidate patterns (single-venv discipline, clean-baseline-
flake-rate refinement) are flagged in Appendices C+D pending second
data points before formal ratification.*

*Open questions still outstanding (not blocking Day 9):*
- *Whether Fork 1 / Fork 4 deserve formal DECISIONS entries post-hoc (Fix Day 3)*
- *Install-path auto-transition vs scanner-owned state changes (Fix Day 3 Question 2)*
- *Skills-specific "used" detection signal sources (Fix Day 3 Question 3 / Fix Day 4 Fork H)*
- *Loader-emit wiring scheduling (Fix Day 4 Open Question 2 — when first real backing-server registration arrives)*
- *Catalog-slug aliasing convention (Fix Day 5 — well-known-tool-name → slug helper, e.g. `mlr` → `miller-mlr`; rides along with future grep work)*
- *Venv-corruption-events Appendix as ops-protocol section (Day 7 Appendix C — candidate, awaiting second data point)*
- *Time-box discipline on ambiguous-scope investigations (Day 7 Appendix E — candidate, awaiting second data point)*
- *Single-venv discipline (Day 8 Appendix C — candidate, awaiting second data point)*
- *Clean-baseline-flake-rate refinement (Day 8 Appendix D — candidate, awaiting second data point)*
- *`~/.satiety-pipeline/` path generic-equivalent question (Day 8 forward-pointer for Day 9 README review — consider whether worked examples should use `~/agent-workspace/drafts/` or similar)*
- *UI shape for Day 10 (TBD at Day 10 alignment session per Days 9-12 arc)*
