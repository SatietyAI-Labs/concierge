# Sample task — CSV analysis

**Task:** Analyze this CSV of subscriber signups. I want column-level
statistics (min / max / mean / null counts) for the numeric columns,
and the top-5 rows by `open_rate`. The file has quoted string fields
and UTF-8 emoji in the `display_name` column, so naive awk/cut won't
handle it cleanly.

**Working directory:** `/home/lewie/work/subscribers-analysis`

**Task hint:** `data-analysis`

**Active tools at task time (what the caller already has loaded):** none
relevant — agent is reaching for something new.

**CSV path:** `./subscribers.csv` (see `sample-csv.csv` in this
folder for the exemplar shape)

## Why this is the canonical task

- Exercises the **lightweight-first preference** protocol — the
  catalog has both `csvstat` (lightweight CLI from `csvkit` pack)
  and `pandas` (heavyweight Python library); the correct recommendation
  prefers `csvstat` for this task shape per the tool-recommendation
  skill.
- Exercises **realistic edge cases** (quoted fields, UTF-8) that
  filter out trivial workarounds (`awk`, `cut`, `sort`) the protocol
  explicitly warns against.
- Ground truth is stable: `csvstat` has been the right answer for
  this task class since Apr 13 (see `_legacy/tool-requests/resolved/
  2026-04-13-2018-csvkit-for-csv-analysis.md`). If Opus stops
  preferring it, that is either a real regression or a reality-shift
  worth investigating.
