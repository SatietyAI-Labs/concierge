# Expected recommendation — canonical assertion for soak baseline

Given `sample-task.md` + `sample-catalog-state.json`, the
recommendation engine (`POST /recommend`) should produce a ranked
list in which **a csvkit-family tool (`csvstat`, `csvsort`, or
`csvgrep`) ranks above `pandas`** for this task.

The machine assertion in `tests/test_smoke_live_anthropic.py` is
the code expression of this doc. Both point at the same truth;
keep them synchronized.

## Assertion detail

**Primary expectation:**
- `rank` of any csvkit-family tool (`tool_slug in {csvstat, csvsort,
  csvgrep, csvlook}`) is strictly less than the `rank` of `pandas`.
- If `pandas` is not in the returned list at all, the assertion
  passes (lightweight-first preference fully honored).
- If neither `pandas` nor any csvkit tool appears, the assertion
  fails — Opus declined to use the catalog.

**Secondary observations (logged, not asserted):**
- `confidence` on the top pick. High/medium expected; low signals
  Opus is uncertain about the catalog's fit.
- Whether `is_in_catalog=False` discovery recs appear — not a
  failure mode, but a signal worth logging for soak analysis.
- Token cost per request (from the response's `token_usage` field)
  — soak operator uses this to track cost-per-recommendation drift.

## Why this is the right assertion

The tool-awareness + tool-recommendation skills (X3 / X4,
byte-identical in `core/prompts/`) explicitly name the
**lightweight-first preference**: prefer CLI tools over
library/framework tools when both would serve a task. The sample
task's shape (one-shot column stats over a CSV with quoting
complications) is the textbook case for the lightweight option.

## Drift interpretation

If this assertion starts failing during soak:

1. **Reality-shift candidate:** Opus 4.7 behavior under the pinned
   model id changed. Log, escalate, do not immediately retune the
   prompt.
2. **Regression candidate:** a prompt-fragment drift, a
   preamble edit, or a memory-state change introduced a behavioral
   shift. Check git log + the prompt-body DEBUG log for the
   specific run that broke.
3. **Catalog-state drift:** `sample-catalog-state.json` was edited
   without a DECISIONS entry. Git blame the file; revert if
   unsanctioned.

The fixture corpus's purpose is precisely to make these three
failure modes distinguishable by bisection.
