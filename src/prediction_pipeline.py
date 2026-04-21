from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.data_fetcher import align_counties_to_baseline, load_county_baseline, load_raw_inputs
from src.feature_engineering import (
    build_2026_feature_table,
    build_training_table,
    compute_rainfall_anomaly,
    compute_subsidy_index,
)
from src.model import fit_abundance_model, model_summary_frame, predict_2026_yield
from src.validation import elasticity_summary, evaluate_training_fit


def run_prediction_pipeline(project_root: Path, scenario_year: int = 2026) -> dict[str, str]:
    baseline = load_county_baseline(project_root)
    raw = load_raw_inputs(project_root)

    rainfall = align_counties_to_baseline(raw["rainfall"], baseline, "rainfall_history.csv")
    subsidy = align_counties_to_baseline(raw["subsidy"], baseline, "subsidy_history.csv")
    maize_yield = align_counties_to_baseline(raw["yield"], baseline, "maize_yield_history.csv")

    training_table = build_training_table(
        baseline_df=baseline,
        rainfall_df=rainfall,
        subsidy_df=subsidy,
        yield_df=maize_yield,
    )
    if training_table.empty:
        raise ValueError("Training table is empty after merging rainfall/subsidy/yield datasets.")

    rainfall_2026 = compute_rainfall_anomaly(rainfall, scenario_year)
    subsidy_2026 = compute_subsidy_index(subsidy, scenario_year)
    feature_2026 = build_2026_feature_table(baseline, rainfall_2026, subsidy_2026)

    bundle = fit_abundance_model(training_table)
    predictions_2026 = predict_2026_yield(feature_2026, bundle)

    metrics = evaluate_training_fit(training_table, bundle)
    elasticity = elasticity_summary(bundle, training_table)

    processed_dir = project_root / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    training_path = processed_dir / "model_training_table.csv"
    prediction_path = processed_dir / "2026_predictions.csv"
    summary_path = processed_dir / "model_coefficients.csv"
    metrics_path = processed_dir / "validation_metrics.json"

    training_table.to_csv(training_path, index=False)
    predictions_2026.to_csv(prediction_path, index=False)
    model_summary_frame(bundle).to_csv(summary_path, index=False)

    payload = {
        **metrics,
        **elasticity,
        "scenario_year": scenario_year,
        "county_predictions": int(predictions_2026["County"].nunique()),
    }
    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {
        "training_table": str(training_path),
        "predictions": str(prediction_path),
        "coefficients": str(summary_path),
        "metrics": str(metrics_path),
    }


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    outputs = run_prediction_pipeline(project_root=project_root, scenario_year=2026)
    print("Prediction pipeline completed.")
    for key, value in outputs.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
