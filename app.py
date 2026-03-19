import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import requests

# 1. Page Configuration
st.set_page_config(layout="wide", page_title="Kenya Food Abundance 2026")

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
@st.cache_data(ttl=600)
def get_weather_forecast(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
        return None
    except:
        return None # Graceful failure triggers fallback UI

# ==========================================
# 3. SIDEBAR: THE WEATHER STATION & SIMULATION
# ==========================================
st.sidebar.title("☁️ Live Weather Station")

county_coords = {
    "Uasin Gishu": (0.5143, 35.2698),
    "Trans Nzoia": (1.0191, 34.9961),
    "Nakuru": (-0.3031, 36.0800),
    "Machakos": (-1.5177, 37.2634),
    "Turkana": (3.1166, 35.5973)
}
selected_c = st.sidebar.selectbox("Monitor Forecast For:", list(county_coords.keys()))
lat, lon = county_coords[selected_c]

with st.sidebar:
    with st.spinner("Connecting to meteorological sensors..."):
        w_data = get_weather_forecast(lat, lon)

# Render Live Data OR Fallback Data
if isinstance(w_data, dict) and 'current' in w_data:
    c_temp = w_data['current']['temperature_2m']
    c_rain = w_data['current']['precipitation']
    
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Current Temp", f"{c_temp}°C")
    col2.metric("Rain Today", f"{c_rain}mm")
    
    st.sidebar.subheader("7-Day Temp Forecast")
    forecast_df = pd.DataFrame({
        "Day": w_data['daily']['time'],
        "Max Temp": w_data['daily']['temperature_2m_max'],
        "Min Temp": w_data['daily']['temperature_2m_min']
    }).set_index("Day")
    st.sidebar.line_chart(forecast_df)
else:
    # THE FALLBACK: Keep app functional if API fails
    st.sidebar.warning(f"📡 Sensor timeout for {selected_c}. Displaying offline historical estimates.")
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Est. Temp", "28.5°C")
    col2.metric("Est. Rain", "0.0mm")
    st.sidebar.caption("Open-Meteo API connection timed out. Simulators still functional.")

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

# Prepare Data (Hypothetical maize yield baseline for major counties)
mock_data = []
base_counties = [
    {"County": "Uasin Gishu", "Zone": "High Altitude", "Base_Rain": 450, "Base_Fert": 0.85, "Base_Yield": 4000000, "Lat": 0.5143, "Lon": 35.2698},
    {"County": "Trans Nzoia", "Zone": "High Altitude", "Base_Rain": 420, "Base_Fert": 0.80, "Base_Yield": 3500000, "Lat": 1.0191, "Lon": 34.9961},
    {"County": "Nakuru",      "Zone": "Rift Valley",   "Base_Rain": 300, "Base_Fert": 0.65, "Base_Yield": 2000000, "Lat": -0.3031, "Lon": 36.0800},
    {"County": "Machakos",    "Zone": "Semi-Arid",     "Base_Rain": 150, "Base_Fert": 0.40, "Base_Yield": 500000, "Lat": -1.5177, "Lon": 37.2634},
    {"County": "Turkana",     "Zone": "Arid (ASAL)",   "Base_Rain": 50,  "Base_Fert": 0.10, "Base_Yield": 50000, "Lat": 3.1166, "Lon": 35.5973}
]

for c in base_counties:
    mock_data.append({
        "County": c["County"],
        "Zone": c["Zone"],
        "Simulated_Yield": int(c["Base_Yield"] * rain_factor * fert_factor),
        "Lat": c["Lat"], "Lon": c["Lon"]
    })
df = pd.DataFrame(mock_data)

# Layout for Map and Data Table
col_m, col_t = st.columns([2, 1])

with col_m:
    st.subheader("Interactive Abundance Map")
    kenya_map = folium.Map(location=[0.5, 37.8], zoom_start=6, tiles="CartoDB positron")
    
    for i, row in df.iterrows():
        # PROFESSOR'S FINAL ADDITION: Styled HTML Popup instead of single-line tooltip
        color = "green" if row['Simulated_Yield'] > 1000000 else "red"
        
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
            location=[row['Lat'], row['Lon']],
            radius=max(row['Simulated_Yield'] / 250000, 7),
            popup=popup_obj, # Using dynamic HTML popup
            tooltip=f"{row['County']} (Click for details)",
            color=color, fill=True, fill_color=color, fill_opacity=0.6
        ).add_to(kenya_map)
    st_folium(kenya_map, width="100%", height=500)

with col_t:
    st.subheader("Yield Estimates")
    st.dataframe(
        df[["County", "Simulated_Yield"]], 
        use_container_width=True,
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