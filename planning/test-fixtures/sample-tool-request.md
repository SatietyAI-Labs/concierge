status: pending

# Tool Request: csvkit

## Request

- **Task context:** Analyzing a subscriber CSV with quoted fields and UTF-8 emoji. Needed column-level stats and top-N-by-column. Tried awk + sort; broke on the quoted comma inside `"Edsger, W. Dijkstra"` and on the emoji byte-width mismatch.
- **Tool suggested:** csvkit
- **Category:** data
- **Install method:** pip-user
- **Discovered:** false

## Recommendation

- **Why this tool:** csvkit handles quoted fields and UTF-8 natively (`csvstat` for column stats, `csvsort` for top-N, `csvgrep` for filters). One-shot commands replace multi-line awk scripts. 2k-row subscriber exports benefit from proper CSV parsing; naive tools break on quote-containing fields.
- **Alternatives considered:** xsv (Rust, faster but less featureful), pandas (heavier for CLI tasks), miller/mlr (good but less well-known).
- **Risk/cost:** `pip install --user csvkit`; no sudo, no cost, no security concerns. Well-maintained data-journalism toolkit.
- **Confidence:** high

## Approval

- **Decision:** 
- **Conditions:** 
- **Date:** 
