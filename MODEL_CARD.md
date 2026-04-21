# Model Card

## Purpose
Estimate county-level food production for Kenya in 2026 using rainfall, fertilizer support, and county baseline information.

## Model Type
Simple linear regression.

## Inputs
- Rainfall anomaly
- Subsidy index
- Baseline county yield
- Baseline county rainfall and fertility values
- County zone category

## Outputs
- Predicted 2026 yield per county
- 90% confidence interval bounds
- Validation metrics

## Training Data
- 2020-2023 county-level training table
- 47 Kenyan counties

## Validation Metrics
- RMSE: see `data/processed/validation_metrics.json`
- MAE: see `data/processed/validation_metrics.json`
- R²: see `data/processed/validation_metrics.json`

## Interpretation
- A positive rainfall coefficient means wetter MAM seasons are associated with higher yield.
- A positive subsidy coefficient means more fertilizer support is associated with higher yield.
- The model is intentionally simple so it can be explained in a class assignment.

## Limitations
- Subsidy and yield are proxy-based in the current build.
- The model does not capture pests, policy shocks, price changes, or soil micro-variation.
- Predictions should be read as scenario estimates, not official forecasts.

## Update Rule
If better raw county data becomes available, replace the proxy raw files in `data/raw/` and rerun `python -m src.prediction_pipeline`.
