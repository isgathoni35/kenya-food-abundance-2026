# Raw Data Files

These files are used by the prediction pipeline:

- `rainfall_history.csv`
- `subsidy_history.csv`
- `maize_yield_history.csv`

## What They Mean
- Rainfall history: real MAM rainfall totals for each county.
- Subsidy history: a transparent county proxy for fertilizer support.
- Yield history: a transparent county proxy for observed maize yield.

## Important Note
The rainfall file is sourced from a public archive API. The subsidy and yield files are proxy datasets so the assignment can run end-to-end even when official county-by-county machine-readable records are not available.

## Templates
The `*_template.csv` files show the expected schema only.
