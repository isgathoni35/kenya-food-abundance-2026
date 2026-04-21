from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


REQUIRED_FILES: Dict[str, str] = {
    "rainfall": "rainfall_history.csv",
    "subsidy": "subsidy_history.csv",
    "yield": "maize_yield_history.csv",
}


REQUIRED_COLUMNS: Dict[str, list[str]] = {
    "rainfall": ["County", "Year", "MAM_Rainfall_mm"],
    "subsidy": ["County", "Year", "Subsidy_Tonnes"],
    "yield": ["County", "Year", "Observed_Yield_Bags"],
}


def _normalize_county_column(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["County"] = out["County"].astype(str).str.strip()
    return out


def _validate_columns(df: pd.DataFrame, required: list[str], dataset_name: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{dataset_name} is missing required columns: {', '.join(missing)}")


def load_county_baseline(project_root: Path) -> pd.DataFrame:
    baseline_path = project_root / "data" / "kenya_counties_baseline.csv"
    baseline = pd.read_csv(baseline_path)
    baseline = _normalize_county_column(baseline)

    required_cols = ["County", "Zone", "Lat", "Lon", "Base_Rain", "Base_Fert", "Base_Yield"]
    _validate_columns(baseline, required_cols, "kenya_counties_baseline.csv")

    numeric_cols = ["Lat", "Lon", "Base_Rain", "Base_Fert", "Base_Yield"]
    for col in numeric_cols:
        baseline[col] = pd.to_numeric(baseline[col], errors="coerce")

    baseline = baseline.drop_duplicates(subset=["County"], keep="first").reset_index(drop=True)
    return baseline


def load_raw_inputs(project_root: Path) -> dict[str, pd.DataFrame]:
    raw_dir = project_root / "data" / "raw"
    datasets: dict[str, pd.DataFrame] = {}

    for key, file_name in REQUIRED_FILES.items():
        file_path = raw_dir / file_name
        if not file_path.exists():
            raise FileNotFoundError(
                f"Missing raw input: {file_path}. "
                f"Add this file (see templates in data/raw/) before running the pipeline."
            )

        df = pd.read_csv(file_path)
        _validate_columns(df, REQUIRED_COLUMNS[key], file_name)
        df = _normalize_county_column(df)
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        for col in REQUIRED_COLUMNS[key]:
            if col not in {"County", "Year"}:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        datasets[key] = df.dropna().copy()

    return datasets


def align_counties_to_baseline(df: pd.DataFrame, baseline: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    county_set = set(baseline["County"].tolist())
    unknown = sorted(set(df["County"].tolist()) - county_set)
    if unknown:
        raise ValueError(
            f"{dataset_name} has county names not present in baseline: {', '.join(unknown)}"
        )

    return df[df["County"].isin(county_set)].copy()
