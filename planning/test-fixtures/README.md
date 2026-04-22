# Test fixtures — operational baseline for soak diagnostics

These are not "test inputs." They are the **known-good corpus** used
for soak observability: a fixed input set replayed against Concierge
during the 48h operational-shakedown gate (Days 5-6) to detect
regression (did something break?) and reality-shift (did Opus 4.7's
recommendation behavior change under the same prompt?).

Per `docs/concierge-operations-protocol.md` §Test-fixture management,
the same fixtures are used for every test, every soak probe, every
troubleshooting scenario, every day of the week. Same input → known
output. Drift in the output is a signal.

## Contents

- **`sample-task.md`** — the canonical realistic Claude Code task
  description that triggers Concierge (the "analyze this CSV" task).
  Input to `POST /recommend`.
- **`sample-csv.csv`** — the CSV referenced by `sample-task.md`.
  Not consumed by Concierge itself, but documents the task's
  grounding so an operator re-running the scenario has the same
  artifact Claude Code would see.
- **`sample-tool-request.md`** — a pending tool-request file in the
  X10 schema. Written into `pending/` by the round-trip smoke test;
  exercises N7's parser + writer + cron-compatibility on a realistic
  payload.
- **`sample-catalog-state.json`** — the catalog starting state used
  by the smoke suite's fixture-driven recommendation path. Two packs
  (`csvkit` containing `csvstat`/`csvsort`/`csvgrep`/`csvlook`,
  plus `data-processing` containing `pandas`) so the N8 live
  assertion can rank lightweight vs heavyweight.
- **`expected-recommendation.md`** — the human-readable contract for
  what Opus 4.7 is expected to produce for `sample-task.md` given
  `sample-catalog-state.json`. The machine assertion in
  `tests/test_smoke_live_anthropic.py` is the code expression of
  this doc; both point at the same truth.

## Drift discipline

Changing a fixture is a **Decision**, not a routine edit. Log it to
`planning/decisions/DECISIONS.md` with the rationale. The soak corpus
is worthless as a baseline if it silently mutates between runs.
Post-hackathon, pin fixture SHAs in a manifest file.
