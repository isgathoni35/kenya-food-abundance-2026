from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


@dataclass
class ModelBundle:
    model: LinearRegression
    feature_columns: list[str]
    residual_std: float
    coefficients: dict[str, float]
    intercept: float


def _design_matrix(df: pd.DataFrame, include_target: bool = True):
    base_cols = ["Rainfall_Anomaly", "Subsidy_Index", "Base_Yield", "Base_Rain", "Base_Fert"]
    zone_dummies = pd.get_dummies(df["Zone"], prefix="Zone", drop_first=True)
    X = pd.concat([df[base_cols], zone_dummies], axis=1)

    if include_target:
        y = df["Observed_Yield_Bags"].astype(float)
        return X, y
    return X


def fit_abundance_model(training_table: pd.DataFrame) -> ModelBundle:
    X, y = _design_matrix(training_table, include_target=True)
    model = LinearRegression()
    model.fit(X, y)

    preds = model.predict(X)
    residuals = y.to_numpy() - preds
    residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0

    coefficients = {col: float(coef) for col, coef in zip(X.columns.tolist(), model.coef_)}
    return ModelBundle(
        model=model,
        feature_columns=X.columns.tolist(),
        residual_std=residual_std,
        coefficients=coefficients,
        intercept=float(model.intercept_),
    )


def predict_2026_yield(feature_table_2026: pd.DataFrame, bundle: ModelBundle) -> pd.DataFrame:
    X_2026 = _design_matrix(feature_table_2026, include_target=False)

    # Align scenario design matrix to the same model columns used at fit time.
    for col in bundle.feature_columns:
        if col not in X_2026.columns:
            X_2026[col] = 0.0
    X_2026 = X_2026[bundle.feature_columns]

    preds = bundle.model.predict(X_2026)
    ci_margin = 1.64 * bundle.residual_std

    out = feature_table_2026[["County", "Zone"]].copy()
    out["Predicted_Yield_Bags_2026"] = np.maximum(preds, 0.0).round(0).astype(int)
    out["CI_Lower_90"] = np.maximum(preds - ci_margin, 0.0).round(0).astype(int)
    out["CI_Upper_90"] = np.maximum(preds + ci_margin, 0.0).round(0).astype(int)
    return out


def model_summary_frame(bundle: ModelBundle) -> pd.DataFrame:
    rows = [{"Feature": "Intercept", "Coefficient": bundle.intercept}]
    rows.extend(
        {"Feature": feature, "Coefficient": coef}
        for feature, coef in sorted(bundle.coefficients.items())
    )
    return pd.DataFrame(rows)
