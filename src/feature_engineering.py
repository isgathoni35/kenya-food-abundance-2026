from __future__ import annotations

import pandas as pd


def compute_rainfall_anomaly(rainfall_df: pd.DataFrame, scenario_year: int) -> pd.DataFrame:
    historical = rainfall_df[rainfall_df["Year"] < scenario_year].copy()
    if historical.empty:
        raise ValueError("Rainfall dataset has no years prior to the scenario year.")

    climatology = (
        historical.groupby("County", as_index=False)["MAM_Rainfall_mm"]
        .mean()
        .rename(columns={"MAM_Rainfall_mm": "Rainfall_Climatology_mm"})
    )

    scenario = rainfall_df[rainfall_df["Year"] == scenario_year][["County", "MAM_Rainfall_mm"]].copy()
    if scenario.empty:
        raise ValueError(
            f"Rainfall dataset has no rows for scenario year {scenario_year}."
        )

    merged = scenario.merge(climatology, on="County", how="left")
    merged["Rainfall_Anomaly"] = (
        merged["MAM_Rainfall_mm"] - merged["Rainfall_Climatology_mm"]
    ) / merged["Rainfall_Climatology_mm"].replace(0, pd.NA)
    merged["Rainfall_Anomaly"] = merged["Rainfall_Anomaly"].fillna(0.0)

    return merged[["County", "MAM_Rainfall_mm", "Rainfall_Climatology_mm", "Rainfall_Anomaly"]]


def compute_subsidy_index(subsidy_df: pd.DataFrame, scenario_year: int) -> pd.DataFrame:
    scenario = subsidy_df[subsidy_df["Year"] == scenario_year][["County", "Subsidy_Tonnes"]].copy()
    if scenario.empty:
        raise ValueError(
            f"Subsidy dataset has no rows for scenario year {scenario_year}."
        )

    max_subsidy = scenario["Subsidy_Tonnes"].max()
    if not max_subsidy or max_subsidy <= 0:
        scenario["Subsidy_Index"] = 0.0
    else:
        scenario["Subsidy_Index"] = scenario["Subsidy_Tonnes"] / max_subsidy

    return scenario[["County", "Subsidy_Tonnes", "Subsidy_Index"]]


def build_training_table(
    baseline_df: pd.DataFrame,
    rainfall_df: pd.DataFrame,
    subsidy_df: pd.DataFrame,
    yield_df: pd.DataFrame,
) -> pd.DataFrame:
    merged = (
        yield_df.merge(rainfall_df, on=["County", "Year"], how="inner")
        .merge(subsidy_df, on=["County", "Year"], how="inner")
        .merge(
            baseline_df[["County", "Zone", "Base_Yield", "Base_Rain", "Base_Fert"]],
            on="County",
            how="left",
        )
    )

    # County-specific anomaly against available history in training rows.
    county_rain_mean = merged.groupby("County")["MAM_Rainfall_mm"].transform("mean")
    merged["Rainfall_Anomaly"] = (
        (merged["MAM_Rainfall_mm"] - county_rain_mean) / county_rain_mean.replace(0, pd.NA)
    ).fillna(0.0)

    max_subsidy = merged.groupby("Year")["Subsidy_Tonnes"].transform("max").replace(0, pd.NA)
    merged["Subsidy_Index"] = (merged["Subsidy_Tonnes"] / max_subsidy).fillna(0.0)

    out_cols = [
        "County",
        "Year",
        "Zone",
        "Observed_Yield_Bags",
        "MAM_Rainfall_mm",
        "Rainfall_Anomaly",
        "Subsidy_Tonnes",
        "Subsidy_Index",
        "Base_Rain",
        "Base_Fert",
        "Base_Yield",
    ]
    return merged[out_cols].dropna().reset_index(drop=True)


def build_2026_feature_table(
    baseline_df: pd.DataFrame,
    rainfall_2026_df: pd.DataFrame,
    subsidy_2026_df: pd.DataFrame,
) -> pd.DataFrame:
    table = (
        baseline_df[["County", "Zone", "Base_Yield", "Base_Rain", "Base_Fert"]]
        .merge(rainfall_2026_df, on="County", how="left")
        .merge(subsidy_2026_df, on="County", how="left")
    )

    table["Rainfall_Anomaly"] = table["Rainfall_Anomaly"].fillna(0.0)
    table["Subsidy_Index"] = table["Subsidy_Index"].fillna(0.0)
    return table
