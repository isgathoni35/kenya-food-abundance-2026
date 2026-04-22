import json
import os
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.weather_normalization import build_forecast_frame
from src.weather_providers import fetch_weather_cascade

# 1. Page Configuration
st.set_page_config(layout="wide", page_title="Kenya Food Abundance 2026")

COUNTY_DATA_PATH = Path(__file__).resolve().parent / "data" / "kenya_counties_baseline.csv"
PREDICTIONS_2026_PATH = Path(__file__).resolve().parent / "data" / "processed" / "2026_predictions.csv"
WEATHER_CACHE_TTL_SECONDS = 60
WEATHER_RETRY_ATTEMPTS = 3
WEATHER_PRIMARY_TIMEOUT_SECONDS = 10
WEATHER_SECONDARY_TIMEOUT_SECONDS = 8
GROUP_MEMBERS = [
    "Naimadu Madina Naserian - H12/4972/2020",
    "Parsley Mboya Ngaira - H12/1778/2022",
    "Matilda Valerie Odalo - H12/3174/2022",
    "Gathoni Elias Warutere - H12/1790/2022",
    "Brianna Muchiku - H12/1777/2022",
]

# 1.1 Custom Theme Fix (To ensure dark mode with custom primary color)
# We can optionally hide this later if dark mode base works
st.markdown("""
<style>
/* Adjusting slider track color to match neon green */
div[data-baseweb="slider"] > div > div > div {
    background-color: #00E676 !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. ROBUST WEATHER API (With Fallback)
# ==========================================
@st.cache_data(ttl=3600)
def load_county_data(path):
    counties = pd.read_csv(path)
    counties["County"] = counties["County"].astype(str).str.strip()

    numeric_cols = ["Lat", "Lon", "Base_Rain", "Base_Fert", "Base_Yield"]
    for col in numeric_cols:
        counties[col] = pd.to_numeric(counties[col], errors="coerce")

    counties = counties.drop_duplicates(subset=["County"], keep="first")
    counties = counties.sort_values("County").reset_index(drop=True)
    return counties


@st.cache_data(ttl=300)
def load_prediction_data(path):
    prediction_cols = ["County", "Predicted_Yield_Bags_2026", "CI_Lower_90", "CI_Upper_90"]
    if not Path(path).exists():
        return pd.DataFrame(columns=prediction_cols)

    pred = pd.read_csv(path)
    required_cols = {"County", "Predicted_Yield_Bags_2026"}
    if not required_cols.issubset(set(pred.columns)):
        return pd.DataFrame(columns=prediction_cols)

    # Keep only app-consumed prediction fields so structural columns never collide on merge.
    pred = pred[[c for c in prediction_cols if c in pred.columns]].copy()

    pred["County"] = pred["County"].astype(str).str.strip()
    for col in ["Predicted_Yield_Bags_2026", "CI_Lower_90", "CI_Upper_90"]:
        if col in pred.columns:
            pred[col] = pd.to_numeric(pred[col], errors="coerce")

    return pred


@st.cache_data(ttl=300)
def load_model_metrics(path):
    metrics_path = Path(path)
    if not metrics_path.exists():
        return {}
    try:
        return json.loads(metrics_path.read_text())
    except Exception:
        return {}


@st.cache_data(ttl=300)
def load_model_coefficients(path):
    coeff_path = Path(path)
    if not coeff_path.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(coeff_path)
    except Exception:
        return pd.DataFrame()
    if not {"Feature", "Coefficient"}.issubset(frame.columns):
        return pd.DataFrame()
    return frame


def validate_county_data(counties):
    issues = []
    required_cols = {"County", "Zone", "Lat", "Lon", "Base_Rain", "Base_Fert", "Base_Yield"}
    invalid_counties = []

    missing_cols = required_cols.difference(counties.columns)
    if missing_cols:
        issues.append(f"Missing columns: {', '.join(sorted(missing_cols))}")
        return counties.iloc[0:0].copy(), issues, invalid_counties

    valid_mask = (
        counties["County"].notna()
        & counties["Zone"].notna()
        & counties["Lat"].notna()
        & counties["Lon"].notna()
        & counties["Base_Rain"].notna()
        & counties["Base_Fert"].notna()
        & counties["Base_Yield"].notna()
        & (counties["Base_Rain"] >= 0)
        & (counties["Base_Fert"] >= 0)
        & (counties["Base_Yield"] >= 0)
        & (counties["Lat"].between(-90, 90))
        & (counties["Lon"].between(-180, 180))
    )
    dropped_rows = (~valid_mask).sum()
    if dropped_rows > 0:
        invalid_counties = counties.loc[~valid_mask, "County"].fillna("<unknown>").astype(str).tolist()
        issues.append(
            "Dropped invalid county row(s): "
            + ", ".join(sorted(invalid_counties))
            + "."
        )
    counties = counties.loc[valid_mask].copy()

    expected_count = 47
    unique_count = counties["County"].nunique()
    if unique_count != expected_count:
        issues.append(f"Expected {expected_count} unique counties, found {unique_count}.")

    return counties, issues, invalid_counties


@st.cache_data(ttl=WEATHER_CACHE_TTL_SECONDS)
def get_weather_forecast(lat, lon, refresh_nonce=0):
    api_key = None
    try:
        api_key = st.secrets.get("OPEN_WEATHER_MAP_API_KEY")
    except Exception:
        api_key = os.getenv("OPEN_WEATHER_MAP_API_KEY")

    result = fetch_weather_cascade(
        lat=lat,
        lon=lon,
        primary_retries=WEATHER_RETRY_ATTEMPTS,
        primary_timeout=WEATHER_PRIMARY_TIMEOUT_SECONDS,
        secondary_timeout=WEATHER_SECONDARY_TIMEOUT_SECONDS,
        secondary_api_key=api_key,
    )
    result["refresh_nonce"] = refresh_nonce
    return result


def offline_weather_estimate(selected_row):
    # Zone defaults keep the sidebar informative even when live weather is unavailable.
    zone_temp_map = {
        "Arid (ASAL)": 31.0,
        "Coastal Humid": 29.0,
        "Coastal Mixed": 28.5,
        "Semi-Arid": 27.0,
        "High Altitude": 20.0,
        "Central Highlands": 21.5,
        "Rift Valley": 23.0,
        "Western High Rainfall": 24.0,
        "Lake Basin": 25.0,
        "Urban Mixed": 24.5,
    }

    zone = selected_row["Zone"]
    est_temp = zone_temp_map.get(zone, 26.0)
    est_rain = round(max(selected_row["Base_Rain"] / 90.0, 0.0), 1)
    return est_temp, est_rain

# ==========================================
# 3. SIDEBAR: THE WEATHER STATION & SIMULATION
# ==========================================
st.sidebar.title("☁️ Live Weather Station")

counties_df = load_county_data(COUNTY_DATA_PATH)
counties_df, county_issues, invalid_counties = validate_county_data(counties_df)
predictions_df = load_prediction_data(PREDICTIONS_2026_PATH)

if not predictions_df.empty:
    counties_df = counties_df.merge(predictions_df, on="County", how="left")
else:
    counties_df["Predicted_Yield_Bags_2026"] = pd.NA

# Defensive guard: keep a canonical Zone column even if upstream schema drifts.
if "Zone" not in counties_df.columns:
    if "Zone_x" in counties_df.columns:
        counties_df["Zone"] = counties_df["Zone_x"]
    elif "Zone_y" in counties_df.columns:
        counties_df["Zone"] = counties_df["Zone_y"]
    else:
        counties_df["Zone"] = "Unknown"
        st.warning("Zone metadata missing from merged county data. Using fallback zone label.")

if county_issues:
    st.warning("County data quality checks found issues: " + " | ".join(county_issues))

if counties_df.empty:
    st.error("County dataset has no valid rows. Please review data/kenya_counties_baseline.csv")
    st.stop()

county_names = counties_df["County"].tolist()
selected_c = st.sidebar.selectbox("Monitor Forecast For:", county_names)

selected_matches = counties_df.loc[counties_df["County"] == selected_c]
if selected_matches.empty:
    st.sidebar.error(f"County lookup failed for {selected_c}. Select another county.")
    st.stop()
selected_row = selected_matches.iloc[0]
lat, lon = selected_row["Lat"], selected_row["Lon"]

if "weather_last_live" not in st.session_state:
    st.session_state["weather_last_live"] = {}
if "weather_refresh_nonce" not in st.session_state:
    st.session_state["weather_refresh_nonce"] = 0

if st.sidebar.button("Retry Live Weather Now"):
    st.session_state["weather_refresh_nonce"] += 1

with st.sidebar:
    with st.spinner("Connecting to meteorological sensors..."):
        w_data = get_weather_forecast(lat, lon, st.session_state["weather_refresh_nonce"])

# Render Live Data OR Fallback Data
current = w_data.get("current", {})
c_temp = current.get("temperature_2m") if isinstance(current, dict) else None
c_rain = current.get("precipitation") if isinstance(current, dict) else None
forecast_df = build_forecast_frame(w_data)
weather_status = w_data.get("status", "fallback")
weather_reason = w_data.get("reason", "unknown")
weather_attempts = w_data.get("attempts", 0)
weather_provider = w_data.get("provider", "offline")

if weather_status in {"live_full", "live_partial"} and w_data.get("last_live_utc"):
    st.session_state["weather_last_live"][selected_c] = w_data["last_live_utc"]

reason_labels = {
    "ok": "Live weather is healthy.",
    "forecast_incomplete": "Live current weather available; forecast feed is partial.",
    "current_missing": "Provider returned incomplete current weather.",
    "timeout": "Weather provider request timed out.",
    "http_error": "Weather provider returned an HTTP error.",
    "invalid_json": "Weather provider returned unreadable data.",
    "invalid_coordinates": "County coordinates are invalid.",
    "malformed_payload": "Weather provider payload shape is invalid.",
    "unexpected_error": "Unexpected weather pipeline error.",
    "primary_timeout_secondary_not_configured": "Primary provider timed out and backup provider key is not configured.",
    "primary_http_error_secondary_not_configured": "Primary provider HTTP error and backup provider key is not configured.",
}

st.sidebar.caption(
    f"Weather status: {weather_status.replace('_', ' ').title()} | "
    f"Attempts: {weather_attempts}"
)
provider_label = {
    "open-meteo": "Open-Meteo (Primary)",
    "openweathermap": "OpenWeatherMap (Backup)",
    "offline": "Offline Estimate",
}
st.sidebar.caption(f"Provider used: {provider_label.get(weather_provider, weather_provider)}")
st.sidebar.caption(reason_labels.get(weather_reason, f"Reason: {weather_reason}"))

last_live_for_county = st.session_state["weather_last_live"].get(selected_c)
if last_live_for_county:
    st.sidebar.caption(f"Last live update (UTC): {last_live_for_county}")

if c_temp is not None and c_rain is not None:
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Current Temp", f"{c_temp}°C")
    col2.metric("Rain Today", f"{c_rain}mm")

    st.sidebar.subheader("7-Day Temp Forecast")
    if forecast_df is not None:
        st.sidebar.line_chart(forecast_df)
    else:
        st.sidebar.caption("Forecast stream incomplete. Showing live current weather only.")
else:
    # Retry-first failed, so fallback keeps the app functional for every county.
    est_temp, est_rain = offline_weather_estimate(selected_row)
    st.sidebar.warning(f"📡 Live weather unavailable for {selected_c}. Showing offline estimates.")
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Est. Temp", f"{est_temp}°C")
    col2.metric("Est. Rain", f"{est_rain}mm")
    st.sidebar.caption("Retries were attempted before fallback. Simulators remain fully functional.")

st.sidebar.divider()

# Simulation Controls
st.sidebar.header("🚜 2026 Yield Simulation")
st.sidebar.write("Adjust factors to see real-time biochemical impact.")
rain_factor = st.sidebar.slider("MAM Rainfall Variation", 0.5, 1.5, 1.0, help="1.0 is average, 0.5 is severe drought")
fert_factor = st.sidebar.slider("Fertilizer Subsidy Impact", 0.5, 1.5, 1.0, help="1.0 is average, 1.5 is ideal distribution")


# ==========================================
# 4. MAIN DASHBOARD: MAP & ANALYSIS
# ==========================================
st.title("Kenya Food Abundance & Meteorological Mapping 2026")
st.write("University of Nairobi | Food and Microbial Biochemistry Analysis")
st.subheader("Group Members")
for member in GROUP_MEMBERS:
    st.markdown(f"- {member}")

# Prepare Data (Hypothetical maize yield baseline for major counties)
mock_data = []
prediction_mode = False
for _, c in counties_df.iterrows():
    predicted_base = c.get("Predicted_Yield_Bags_2026")
    if pd.notna(predicted_base):
        base_yield = float(predicted_base)
        prediction_mode = True
    else:
        base_yield = float(c["Base_Yield"])

    mock_data.append({
        "County": c["County"],
        "Zone": c["Zone"],
        "Simulated_Yield": int(max(base_yield * rain_factor * fert_factor, 0)),
        "Lat": c["Lat"],
        "Lon": c["Lon"],
    })
df = pd.DataFrame(mock_data)

if prediction_mode:
    st.caption("Yield base source: 2026 model predictions from data/processed/2026_predictions.csv")
else:
    st.caption("Yield base source: baseline county assumptions (prediction file not found)")

# Layout for Map and Data Table
col_m, col_t = st.columns([2, 1])

with col_m:
    st.subheader("Interactive Abundance Map")
    kenya_map = folium.Map(location=[0.5, 37.8], zoom_start=6, tiles="CartoDB positron")

    low_cut = df["Simulated_Yield"].quantile(0.33)
    high_cut = df["Simulated_Yield"].quantile(0.67)
    y_min = df["Simulated_Yield"].min()
    y_max = df["Simulated_Yield"].max()
    y_span = max(y_max - y_min, 1)
    
    for i, row in df.iterrows():
        # PROFESSOR'S FINAL ADDITION: Styled HTML Popup instead of single-line tooltip
        if row["Simulated_Yield"] >= high_cut:
            color = "green"
        elif row["Simulated_Yield"] >= low_cut:
            color = "orange"
        else:
            color = "red"

        normalized = (row["Simulated_Yield"] - y_min) / y_span
        marker_radius = max(6, min(22, 6 + normalized * 16))
        
        popup_html = f"""
        <div style="font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 14px; width: 220px; color: #333;">
            <b style="font-size: 16px; color: #2E7D32;">{row['County']}</b><br>
            <span style="color: #666;">({row['Zone']} Region)</span>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 8px 0;">
            <b>MAM Rain Factor:</b> {rain_factor}x<br>
            <b>Subsidy Factor:</b> {fert_factor}x<br>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 8px 0;">
            <b><span style="font-size: 15px;">Est. 2026 Yield:</span></b><br>
            <span style="font-size: 18px; color: {color}; font-weight: bold;">
                {row['Simulated_Yield']:,} 90kg Bags
            </span>
        </div>
        """
        
        popup_obj = folium.Popup(popup_html, max_width=250)
        
        folium.CircleMarker(
            location=[row["Lat"], row["Lon"]],
            radius=marker_radius,
            popup=popup_obj, # Using dynamic HTML popup
            tooltip=f"{row['County']} (Click for details)",
            color=color, fill=True, fill_color=color, fill_opacity=0.6
        ).add_to(kenya_map)
    st_folium(kenya_map, width="100%", height=500)

with col_t:
    st.subheader("Yield Estimates")
    st.dataframe(
        df[["County", "Simulated_Yield"]].sort_values("Simulated_Yield", ascending=False),
        use_container_width=True,
        height=500,
        hide_index=True,
        column_config={
            "Simulated_Yield": st.column_config.NumberColumn(
                "Estimated Bags",
                format="%d"
            )
        }
    )

# 5. Global Comparison Section
st.divider()
st.header("Global Agricultural Paradigms: A Biochemical Comparison")
c1, c2, c3 = st.columns(3)
with c1:
    st.subheader("🇰🇪 Kenya")
    st.write("**Model:** Rain-fed & Subsidy-Driven. Focuses on maximizing Nitrogen/Phosphorus uptake for staple biomass.")
with c2:
    st.subheader("🇪🇺 Europe")
    st.write("**Model:** Precision 'Farm to Fork'. Focuses on Nitrogen Use Efficiency (NUE) and microbial soil health.")
with c3:
    st.subheader("🇺🇸 America")
    st.write("**Model:** Industrial & Genetic. Relies on GMO drought-resistance and massive irrigation infrastructure.")
