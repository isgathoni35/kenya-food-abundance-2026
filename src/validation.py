from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.model import ModelBundle


def evaluate_training_fit(training_table: pd.DataFrame, bundle: ModelBundle) -> dict[str, float]:
    zone_dummies = pd.get_dummies(training_table["Zone"], prefix="Zone", drop_first=True)
    X = pd.concat(
        [
            training_table[[
                "Rainfall_Anomaly",
                "Subsidy_Index",
                "Base_Yield",
                "Base_Rain",
                "Base_Fert",
            ]],
            zone_dummies,
        ],
        axis=1,
    )

    for col in bundle.feature_columns:
        if col not in X.columns:
            X[col] = 0.0
    X = X[bundle.feature_columns]

    y_true = training_table["Observed_Yield_Bags"].astype(float).to_numpy()
    y_pred = bundle.model.predict(X)

    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))

    return {
        "rmse": rmse,
        "mae": mae,
        "r2": r2,
        "residual_std": float(bundle.residual_std),
    }


def elasticity_summary(bundle: ModelBundle, reference_df: pd.DataFrame) -> dict[str, float]:
    mean_yield = float(reference_df["Observed_Yield_Bags"].mean())
    rainfall_coef = float(bundle.coefficients.get("Rainfall_Anomaly", 0.0))
    subsidy_coef = float(bundle.coefficients.get("Subsidy_Index", 0.0))

    if mean_yield <= 0:
        return {
            "rainfall_effect_pct": 0.0,
            "subsidy_effect_pct": 0.0,
        }

    # Approximate percent effect relative to average county yield.
    return {
        "rainfall_effect_pct": (rainfall_coef / mean_yield) * 100.0,
        "subsidy_effect_pct": (subsidy_coef / mean_yield) * 100.0,
    }
