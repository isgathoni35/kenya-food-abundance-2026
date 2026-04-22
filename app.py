import json
import os
from datetime import datetime
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
    "Caesar Osebe - H12/2640/2021",
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


def get_zone_crop_suitability():
    return {
        "Arid (ASAL)": {
            "primary": ["sorghum", "millet", "pigeon pea", "green gram"],
            "secondary": ["drought-tolerant cassava", "goat keeping"],
            "note": "Best for low-rainfall, heat-tolerant crops and livestock systems.",
        },
        "Semi-Arid": {
            "primary": ["sorghum", "millet", "cowpeas", "pigeon pea"],
            "secondary": ["cassava", "sunflower"],
            "note": "Balanced drought tolerance and short-season crops work best here.",
        },
        "Coastal Humid": {
            "primary": ["cassava", "coconut", "beans", "sweet potato"],
            "secondary": ["banana", "rice"],
            "note": "Warm and humid conditions support root crops and perennial options.",
        },
        "Coastal Mixed": {
            "primary": ["cassava", "beans", "cowpeas", "groundnuts"],
            "secondary": ["maize", "banana"],
            "note": "Mixed rainfall favors resilient crops with flexible planting windows.",
        },
        "High Altitude": {
            "primary": ["maize", "beans", "potatoes", "wheat"],
            "secondary": ["peas", "barley"],
            "note": "Cooler, wetter zones are strong for cereals and tubers.",
        },
        "Central Highlands": {
            "primary": ["maize", "beans", "potatoes", "tea"],
            "secondary": ["coffee", "bananas"],
            "note": "Reliable rainfall and cool temperatures suit intensive mixed farming.",
        },
        "Rift Valley": {
            "primary": ["maize", "wheat", "barley", "beans"],
            "secondary": ["sunflower", "dairy fodder"],
            "note": "Good for cereals and livestock feed where rainfall is moderate.",
        },
        "Western High Rainfall": {
            "primary": ["maize", "beans", "sweet potato", "cassava"],
            "secondary": ["banana", "groundnuts"],
            "note": "High rainfall supports maize plus legumes and root crops.",
        },
        "Lake Basin": {
            "primary": ["maize", "cassava", "beans", "sorghum"],
            "secondary": ["rice", "sweet potato"],
            "note": "Warm, productive zones with mixed crop options and fisheries links.",
        },
        "Urban Mixed": {
            "primary": ["vegetables", "leafy greens", "beans"],
            "secondary": ["urban kitchen gardens", "horticulture"],
            "note": "Small-space, high-value, fast-turnover crops fit urban settings best.",
        },
    }

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

if "rain_factor" not in st.session_state:
    st.session_state["rain_factor"] = 1.0
if "fert_factor" not in st.session_state:
    st.session_state["fert_factor"] = 1.0

st.sidebar.caption("Quick Presets")
p1, p2, p3 = st.sidebar.columns(3)
if p1.button("Drought"):
    st.session_state["rain_factor"] = 0.7
    st.session_state["fert_factor"] = 0.9
if p2.button("Normal"):
    st.session_state["rain_factor"] = 1.0
    st.session_state["fert_factor"] = 1.0
if p3.button("Good"):
    st.session_state["rain_factor"] = 1.2
    st.session_state["fert_factor"] = 1.1

rain_factor = st.sidebar.slider(
    "MAM Rainfall Variation",
    0.5,
    1.5,
    help="1.0 is average, 0.5 is severe drought",
    key="rain_factor",
)
fert_factor = st.sidebar.slider(
    "Fertilizer Subsidy Impact",
    0.5,
    1.5,
    help="1.0 is average, 1.5 is ideal distribution",
    key="fert_factor",
)


# ==========================================
# 4. MAIN DASHBOARD: MAP & ANALYSIS
# ==========================================
st.title("Kenya Food Abundance & Meteorological Mapping 2026")
st.write("University of Nairobi | Food and Microbial Biochemistry Analysis")
st.subheader("Group Members")
for member in GROUP_MEMBERS:
    st.markdown(f"- {member}")
st.caption("Data transparency: rainfall uses Open-Meteo; subsidy and yield are documented county-level proxies.")

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

if PREDICTIONS_2026_PATH.exists():
    updated_at = datetime.fromtimestamp(PREDICTIONS_2026_PATH.stat().st_mtime)
    st.caption(f"Prediction file last updated: {updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

# Layout for Map and Data Table
col_m, col_t = st.columns([2, 1])

with col_m:
    st.info("How to read this map: green = higher simulated yield, orange = medium, red = lower. Values are scenario estimates.")
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

st.divider()
st.subheader("County Highlights")
h1, h2 = st.columns(2)
with h1:
    st.caption("Top 5 counties by simulated yield")
    st.dataframe(
        df[["County", "Simulated_Yield"]].sort_values("Simulated_Yield", ascending=False).head(5),
        use_container_width=True,
        hide_index=True,
    )
with h2:
    st.caption("Bottom 5 counties by simulated yield")
    st.dataframe(
        df[["County", "Simulated_Yield"]].sort_values("Simulated_Yield", ascending=True).head(5),
        use_container_width=True,
        hide_index=True,
    )

# ==========================================
# 4. REGIONAL COMPARISON
# ==========================================
st.divider()
st.header("Global Agricultural Comparison")
st.write("A macro-level analysis of soil chemistry, microbial management, and yield strategies.")

c1, c2, c3 = st.columns(3)
with c1:
    st.subheader("🇰🇪 Kenya")
    st.write("**System:** Rain-fed Smallholder & Subsidy-Driven")
    st.write("**Biochemical Reality:** Cultivated soils often experience nitrogen depletion and high acidity. The strategy relies heavily on inorganic inputs (DAP/CAN fertilizers) provided via government subsidies to rapidly correct macronutrient deficits.")
    st.write("**Microbial Impact:** High reliance on synthetic fertilizers can temporarily suppress native soil microbiome diversity, making the crops highly dependent on external inputs and the MAM rainfall onset for nutrient transport.")

with c2:
    st.subheader("🇪🇺 Europe")
    st.write("**System:** Precision 'Farm to Fork' & Regulated")
    st.write("**Biochemical Reality:** Strict EU 'Nitrates Directives' limit synthetic nitrogen application to prevent aquatic eutrophication. The focus has shifted toward Nitrogen Use Efficiency (NUE) and organic bio-stimulants.")
    st.write("**Microbial Impact:** Agricultural policies actively promote the preservation of the soil microbiome, encouraging crop rotation and organic farming to naturally fix soil nitrogen and maintain long-term carbon sequestration.")

with c3:
    st.subheader("🇺🇸 America")
    st.write("**System:** Industrial Scale & Genetic Engineering")
    st.write("**Biochemical Reality:** Maximizes yield per acre through intensive, variable-rate application of synthetic nutrients (N-P-K). Deeply reliant on transgenic (GMO) crop strains engineered for drought tolerance and pest resistance (e.g., Bt proteins).")
    st.write("**Microbial Impact:** While precision agriculture technology minimizes chemical waste, the sheer scale of monoculture often requires targeted microbial inoculants to restore soil health in heavily farmed agricultural belts.")

st.divider()
st.header("Zone-Based Crop Suitability Guide")
st.write("This is a simple suitability guide for the county zone you selected. It does not change the maize model above.")

zone_suitability = get_zone_crop_suitability()
selected_zone = str(selected_row.get("Zone", "Unknown"))
zone_info = zone_suitability.get(
    selected_zone,
    {
        "primary": ["local staple crops"],
        "secondary": ["mixed farming options"],
        "note": "No zone-specific match found; use local agronomic advice.",
    },
)

st.subheader(f"Selected County: {selected_c}")
st.write(f"**Zone:** {selected_zone}")
st.write(f"**Recommended crops:** {', '.join(zone_info['primary'])}")
st.write(f"**Other suitable options:** {', '.join(zone_info['secondary'])}")
st.caption(zone_info["note"])
st.info("Yield simulation stays maize-focused. This guide is only for crop suitability context.")

st.subheader("All Zones at a Glance")
for zone_name, zone_details in zone_suitability.items():
    with st.expander(zone_name):
        st.write(f"**Recommended crops:** {', '.join(zone_details['primary'])}")
        st.write(f"**Other suitable options:** {', '.join(zone_details['secondary'])}")
        st.caption(zone_details["note"])
