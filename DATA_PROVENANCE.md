# Data Provenance

This project uses three data layers:

## 1. Rainfall History
- Source: Open-Meteo archive API
- Measure: March-April-May (MAM) rainfall total in mm
- Coverage: 47 Kenyan counties
- Years: 2020, 2021, 2022, 2023, and a 2026 scenario value
- Notes: 2020-2023 are fetched from the public archive API; 2026 is set to the county average of 2020-2023 as a documented scenario input.

## 2. Fertilizer Support
- Source type: transparent county proxy
- Measure: subsidy tonnage proxy in tonnes
- Coverage: 47 Kenyan counties
- Years: 2020, 2021, 2022, 2023, and 2026
- Notes: Public county-by-county subsidy records were not available in a clean machine-readable form during implementation, so this dataset is generated from county baseline fertility values plus a small year trend. It is labeled as a proxy and should be treated as an assumption, not an official count.

## 3. Maize Yield History
- Source type: transparent county proxy built from county baseline yield plus rainfall and subsidy signals
- Measure: observed yield in 90kg bags
- Coverage: 47 Kenyan counties
- Years: 2020, 2021, 2022, 2023
- Notes: County-level official maize yield series were not available in a ready-to-use public CSV during implementation, so this dataset is a reproducible proxy used to demonstrate the model pipeline.

## Files
- Raw inputs: `data/raw/`
- Processed outputs: `data/processed/`

## Important Limitation
Only rainfall is sourced directly from a public external API in the current implementation. Subsidy and yield are documented proxy datasets so the assignment can run end-to-end without inventing hidden data sources.
