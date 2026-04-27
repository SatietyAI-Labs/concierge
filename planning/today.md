# Today — 2026-05-03 (Day 12 — Final review + GitHub push) — placeholder

*Opens on: `SESSION-2026-05-02-01.md` (Day 11 close-out — six commits landing forward-carry polish + public-release housekeeping artifacts: Task 1.2 hx-indicator `ac2541d`, Task 1.3 health counter `c8fe991`, Task 1.1 README dashboard section `42cbbdb`, Task 2.1 CHANGELOG `6205d4c`, Task 2.2 CONTRIBUTING `3882044`, Task 2.3 issue templates `acd8e78`. Suite at clean baseline 826/0/1/2 (`-m 'not slow'`). DECISIONS `[2026-05-02 Day 11]` covers D1-D5: counter conjunctive filter, CHANGELOG voice + 10 subgroups, CONTRIBUTING shape + GitHub-Issues-only channel, issue template structure + surface-then-execute education, marketing-copy-drafts-as-working-artifacts durable principle. Task 3 produced five drafts on disk at `planning/scratch/day-11-launch-content/` — NOT committed per D5; paths in Day 11 SESSION close-out Appendix D.)*

## Governing framing

**Final review + GitHub push.** Three placeholder task ladders below. **No production-code changes planned** — Day 11 forward-carry items requiring code (approve-action 8s perf; token-weight tracker; `/stats/top-tools` event-type filter cutover; Phase 2 UI sections) are explicitly out-of-scope for Day 12.

**Day 12 alignment session ratifies the task structure below** — placeholder shape, expected to be refined fresh-each-day per established daily-rhythm pattern. Don't begin code at alignment.

## Day 12 — Final review + GitHub push (placeholder)

### Task A0 — API key audit (BLOCKING; gates Task A3 GitHub push)

**Operator context:** An API key from early build days needs verification — used during human testing in a secondary Claude Code terminal session around Day 3-4. The same key feeds the operator's separate OpenClaw harness (Moltbot system, primary agent Alfred); a leak compromises both systems and requires key rotation across both before remediation. Audit must clear before any push to a public remote.

**Discipline:** the audit is a sequence of checks. **Surface findings; do NOT auto-remediate.** History-rewrite remediation (`git filter-repo`, BFG) is destructive and needs operator alignment on approach, timing, and impact before execution.

**Sub-checks (execute in order):**

- **A0.1** — `git grep "sk-ant-"` across current working tree. Confirms no current-tracked file contains the key string. Cheap; first signal.
- **A0.2** — `git log --all -p -S "sk-ant-"` across full history. **Load-bearing — this is the check that matters.** `-S` finds any commit whose diff contains the pattern, even if a subsequent commit removed the line; `git log -p` exposes the historical diff regardless of subsequent commits. A clean A0.1 with a dirty A0.2 is the worst case (key removed but still in history).
- **A0.3** — Confirm gitignore coverage for `.env`, `concierge.db`, `secrets.*`, and any other env/secret-shaped files. List what's ignored vs. untracked-but-not-ignored. **Untracked-but-not-ignored files are vulnerable to accidental future `git add .`** — surface gaps if they exist. Cross-check `.gitignore` against actual filesystem state on the operator's machine.
- **A0.4** — Cross-check for soft disclosures: search planning docs, code, config files, and SESSION snapshots for references to OpenClaw paths, Moltbot, env-file paths on the operator's local machine, or other third-party system paths that could disclose where the key is stored. The key itself in history is the primary concern; cross-system references that disclose key storage location are a secondary concern but still load-bearing.
- **A0.5** — Surface all findings to operator before any remediation. If the audit finds anything in history, the Day 12 plan changes substantially — push gets deferred, remediation surfaces become the day's work, and key rotation across both Concierge and OpenClaw/Moltbot must happen before any history-rewrite commences.

**Acceptance:**

- A0.1 returns zero matches across current working tree
- A0.2 returns zero matches across full history (`--all` covers all refs, branches, tags)
- A0.3 confirms `.env`, `concierge.db`, env/secret files are gitignored OR surfaces gaps for operator decision
- A0.4 returns no cross-system path disclosures OR surfaces them for operator decision
- Operator explicitly confirms A0 clear before Task A3 GitHub push proceeds

**Forward-carry contingency:** if A0 finds anything in history, the Day 12 plan changes:
- Day 12 GitHub push (Task A3) is **deferred** to Day 13+
- Remediation work becomes Day 12 focus
- Key rotation across both Concierge and OpenClaw/Moltbot **happens first** (before any `git filter-repo` / BFG / force-push), since a leaked key compromises both systems regardless of which repo's history exposed it
- New DECISIONS entry lands documenting the remediation approach + timing + scope
- New SESSION snapshot captures the day's pivot

### Task A1 — Repo URL fill-ins (placeholder)

Three sub-locations need `<repo-url>` placeholder replacement once the GitHub repo URL is known:

- **`pyproject.toml [project.urls]`** — homepage, repository, issues entries (commit-tracked change; lands as part of the Day 12 production-code commit chain)
- **`README.md` clone command** — replace `<repo-url>` literal in the install section's `git clone` block (commit-tracked change)
- **Content drafts at `planning/scratch/day-11-launch-content/`** — LinkedIn / YouTube / HN drafts each carry `<repo-url>` placeholders. **These are operator-side updates to working artifacts, NOT commit-tracked changes** — same logic as the demo video master files per DECISIONS `[2026-05-02 Day 11]` D5 (marketing-copy drafts pre-publication are working artifacts, not durable record). Updated on disk for operator use; canonical published versions will live on the destination platforms (LinkedIn / YouTube / HN) after publication.

### Task A2 — Final review pass (placeholder)

One-pass operator + agent review for any drift caught during Days 9-11. Surfaces:

- `README.md` — opens-on-front-page; install/dashboard/Quick start/usage/architecture/origin/license sections
- `ABOUT.md` — Lewis bio + SatietyAI mission + prior-systems context
- `LICENSE` — MIT, Day 9 commit
- `CHANGELOG.md` — Day 11 commit `6205d4c`
- `CONTRIBUTING.md` — Day 11 commit `3882044`
- `.github/ISSUE_TEMPLATE/` — Day 11 commit `acd8e78`
- `pyproject.toml` metadata — name, version, description, license, authors, classifiers, urls
- High-level structure: directory layout, public-vs-internal surface, anything that reads as work-in-progress that should be flagged

### Task A3 — Initial GitHub push (placeholder; gated on Task A0 clear)

**DOES NOT PROCEED until Task A0 audit is explicitly clear.**

Initial commit chain to public remote. Surfaces:

- Remote setup (URL, branch protection, default branch)
- Issues enablement (verify form templates render correctly post-push)
- Public-visibility verification (no internal-only paths leaked through `.gitignore` review)
- Forward-carry: HN submission timing decision is **separate campaign-level call** (operator + agent crew at campaign level); not Day 12 execution-time.

## End-of-day deliverable (placeholder)

- Repo URL fill-ins landed in `pyproject.toml` + README (commit-tracked); content drafts updated on disk (NOT commit-tracked)
- Final review pass complete; any drift caught and resolved
- Initial GitHub push complete; public repo surface verified
- Suite at clean baseline preserved
- DECISIONS bundled entry `[2026-05-03 Day 12]` written at Day 12 close-out (per Day 7 ratified bundled-entry pattern, if any design decisions land during the day)
- Day 12 SESSION close-out snapshot at `planning/sessions/SESSION-2026-05-03-01.md` (logical-day form per established day-shift pattern)
- today.md updated to Day 13 placeholder OR retired if Day 12 closes the build week

## Checkpoint criteria (placeholder)

**Task A0 — API key audit (BLOCKING; gates Task A3):**

- [ ] A0.1 — `git grep "sk-ant-"` returns zero matches in current working tree
- [ ] A0.2 — `git log --all -p -S "sk-ant-"` returns zero matches across full history
- [ ] A0.3 — `.env`, `concierge.db`, env/secret files gitignored coverage confirmed (or gaps surfaced)
- [ ] A0.4 — no cross-system path disclosures (OpenClaw / Moltbot / local env-file paths) found (or surfaced for operator decision)
- [ ] Operator explicitly confirms A0 clear before A3 GitHub push proceeds

**Tasks A1-A3:**

- [ ] `pyproject.toml [project.urls]` populated with homepage, repository, issues
- [ ] `README.md` clone-command `<repo-url>` literal replaced
- [ ] Content drafts at `planning/scratch/day-11-launch-content/` updated on disk (NOT commit-tracked); LinkedIn / YouTube / HN drafts carry the actual repo URL
- [ ] Final review pass complete across README / ABOUT / LICENSE / CHANGELOG / CONTRIBUTING / pyproject.toml metadata
- [ ] Initial GitHub push complete (gated on Task A0 clear)
- [ ] Issues enabled on the repo; bug_report.yml + feature_request.yml render correctly as forms
- [ ] No internal-only paths leaked through (planning/scratch/ stays gitignored; .venv stays gitignored; etc.)
- [ ] Suite regression at clean baseline post-Task-A1 (only commit-tracked changes can affect suite; Day 12 expected to land 0 wiring-test deltas)
- [ ] DECISIONS bundled entry written if any design decisions land during Day 12 (per Day 7 pattern); mandatory if Task A0 surfaces findings (remediation approach is a logged decision)
- [ ] Day 12 SESSION snapshot at `planning/sessions/SESSION-2026-05-03-01.md`
- [ ] today.md updated for Day 13 OR retired

## Session opener (placeholder — paste verbatim into a fresh Claude Code session to kick off Day 12 alignment)

---

> Read in order, then confirm understanding before acting:
>
> 1. `CLAUDE.md` (project root — pruned in Day 9 to definitive voice; 92 lines)
> 2. `planning/concierge-operations-protocol.md` ← three ratified disciplines: "Decision-edit pattern", "Wiring-test discipline", and "Live verify discipline"
> 3. `planning/sessions/SESSION-2026-05-02-01.md` ← Day 11 close-out (six commits landing forward-carry polish + housekeeping; five Task 3 drafts on disk NOT committed per D5; today.md self-correction caught and resolved during execution)
> 4. `planning/today.md` ← this file (Day 12 placeholder: final review + GitHub push; no production code changes planned)
> 5. `planning/decisions/DECISIONS.md` — tail; especially `[2026-05-02 Day 11]` (D1 counter conjunctive filter; D2 CHANGELOG voice + 10 subgroups; D3 CONTRIBUTING shape + channel-purity; D4 issue template structure; D5 marketing-copy drafts as durable principle)
>
> Today is Day 12 — final review + GitHub push day. **No production-code changes planned**; Day 11 forward-carry items requiring code are explicitly out-of-scope for Day 12.
>
> Four-task placeholder structure (alignment session ratifies / refines):
>
> - **Task A0** = API key audit (**BLOCKING**; gates Task A3 GitHub push). Operator context: an Anthropic API key from early build days was used during human testing in a secondary Claude Code terminal session ~Day 3-4; the same key feeds the operator's separate OpenClaw/Moltbot harness — a leak compromises both systems and requires key rotation across both before any remediation. Sub-checks (surface findings; do NOT auto-remediate): `git grep "sk-ant-"` working tree (A0.1); `git log --all -p -S "sk-ant-"` full history (A0.2 — load-bearing); gitignore coverage for `.env`, `concierge.db`, `secrets.*` (A0.3); cross-system path disclosure check for OpenClaw/Moltbot/local env paths (A0.4); surface findings for operator alignment before any history-rewrite (A0.5). If A0 finds anything, push deferred and remediation becomes the day's work.
> - **Task A1** = Repo URL fill-ins (`pyproject.toml [project.urls]`, README clone command, content drafts at `planning/scratch/day-11-launch-content/` — note: drafts are operator-side updates to working artifacts, NOT commit-tracked changes per D5 durable principle)
> - **Task A2** = Final review pass across README / ABOUT / LICENSE / CHANGELOG / CONTRIBUTING / pyproject.toml metadata for any drift caught during Days 9-11
> - **Task A3** = Initial GitHub push (remote setup, branch protection, Issues enablement, public-visibility verification) — **DOES NOT PROCEED until Task A0 clear**
>
> Effort: max throughout. Public-launch day; A0 audit blocks push hygiene; review quality and push hygiene matter.
>
> **Discipline carry-forward (durable constraints from Days 2-11):**
> - Test-fails-first for any new test landing on a fix
> - Wiring tests assert client-observable contracts — default rule
> - Live shakedowns are fresh-session-only for user-experience claims
> - Surface-then-execute for architectural decisions
> - Mid-stream re-surface for forks
> - In-place DECISIONS edits OK for current-day entries
> - Report between steps; proceed unless intervened
> - Time-box discipline on ambiguous-scope investigations (candidate)
> - Clean-baseline regression signal with N≥5 flake-rate characterization for intermittent failures
> - Single-venv discipline (candidate, Day 8): `.venv` is canonical when uv is the dependency manager
> - Lewis/Lewie naming convention (candidate, Day 9; second occurrence Day 11 — ratification eligible): Lewis (legal) public; Lewie (operational) internal
> - Read-after-edit for structural config files (candidate, Day 9; multiple Day-10/Day-11 data points): edit-success ≠ semantic correctness; applies to TOML / YAML / Markdown structural edits at Task A1 entry
> - Public-contact-info-confirmation rule (Day 9, codified durably via feedback memory; second occurrence Day 11 — ratification eligible): never infer email/phone/handle/real-name from git/env/auto-memory for public artifacts; `hello@satietyai.io` is the only authorized public-facing email
> - Factory-only app composition (Day 10): both `core.app` and `ui.app` are factory-only; canonical launch via `--factory` flag
> - Marketing-copy drafts as working artifacts (Day 11 D5): drafts pre-publication live on disk under `planning/scratch/`, NOT committed; canonical published versions live on platforms; same treatment as demo video masters
> - Cross-prescription consistency check at today.md sign-off (candidate, Day 11; ratification on second occurrence)
>
> Do not begin code on tasks until you've surfaced the task-level approach and I've confirmed alignment. Surface-then-execute applies at task entry.

---

*48h shakedown clock continues running cleanly through Day 11 — Day 11 changes touched UI partial (action-button hx-indicator), one core API endpoint (Health/Stats counter SQL filter, surgically scoped), README copy, three new public-release files, and on-disk content drafts. Substrate paths (recommend / SSE wire format / lifecycle store) untouched. Day 12 is final-review + push; no production-code changes planned. Soak observations should land in the Day 12 SESSION snapshot.*

*Forward-carry items not in Day 12 scope:*

- *Approve action 8s performance investigation (Day 10) — future-day priority*
- *Token-weight tracker (Day 10 alignment forward-carry) — Phase 2 design surface*
- *`GET /stats/top-tools` event-type filter cutover (Day 10) — when used-event-wiring lands*
- *HN submission timing decision — separate campaign-level call (operator + agent crew at campaign level); not Day 12 execution-time*
- *HN comments thread engagement readiness — campaign-level concern*
- *Phase 2 UI sections (Lifecycle Activity / Wishlist Patterns / Cross-Agent Map / Settings) — not v0.1*
- *Whether Fork 1 / Fork 4 deserve formal DECISIONS entries post-hoc (Fix Day 3)*
- *Install-path auto-transition vs scanner-owned state changes (Fix Day 3 Question 2)*
- *Skills-specific "used" detection signal sources (Fix Day 3 Question 3 / Fix Day 4 Fork H)*
- *Loader-emit wiring scheduling (Fix Day 4 Open Question 2)*
- *Catalog-slug aliasing convention (Fix Day 5)*
- *Venv-corruption-events Appendix as ops-protocol section (Day 7 Appendix C — candidate)*
- *Time-box discipline on ambiguous-scope investigations (Day 7 Appendix E — candidate)*
- *Single-venv discipline (Day 8 Appendix C — candidate)*
- *Clean-baseline-flake-rate refinement (Day 8 Appendix D — candidate)*
- *Lewis/Lewie naming convention (Day 9 — candidate; ratification eligible after Day 11 second occurrence)*
- *Read-after-edit discipline for structural config files (Day 9 — candidate; multiple data points logged on Days 10-11)*
- *Vision-section "verbatim" preservation refinement (Day 9 — candidate)*
- *Public-contact-info-confirmation rule (Day 9 — codified via memory; ratification eligible after Day 11 second occurrence)*
- *Flake-rate P2 investigation (Day 8 Appendix B; 1/5 = 20%) — pushed past Day 12 unless headroom*
- *Cross-prescription consistency check at today.md sign-off (Day 11 — new candidate; ratification on second occurrence)*
