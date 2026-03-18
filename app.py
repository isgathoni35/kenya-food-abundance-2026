import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

# 1. Set up the title of your web app
st.title("Kenya Food Abundance & Meteorological Mapping 2026")
st.write("A biochemical and geospatial analysis of estimated grain yields based on MAM rainfall and fertilizer subsidies.")

# 2. Add Dynamic Controls in the Sidebar
st.sidebar.header("2026 Simulation Controls")
st.sidebar.write("Adjust the environmental and policy factors below:")

# Sliders that act as percentage modifiers (1.0 = baseline, 1.2 = 20% increase)
rain_factor = st.sidebar.slider("MAM Rainfall Variation", min_value=0.5, max_value=1.5, value=1.0, step=0.1, help="1.0 is average rainfall. 0.5 is severe drought. 1.5 is heavy flooding.")
fert_factor = st.sidebar.slider("Fertilizer Subsidy Impact", min_value=0.5, max_value=1.5, value=1.0, step=0.1, help="Impact of the KES 2,500 subsidy. 1.0 is baseline uptake.")

# 3. Apply the Professor's Biochemical Logic to the Data
# We multiply the baseline expected yield by the user's slider inputs
mock_data = [
    {"County": "Uasin Gishu", "Zone": "High Altitude", "Rainfall_MM": int(450 * rain_factor), "Fertilizer_Uptake_Score": min(0.85 * fert_factor, 1.0), "Estimated_Yield_Bags": int(4000000 * rain_factor * fert_factor), "Lat": 0.5143, "Lon": 35.2698},
    {"County": "Trans Nzoia", "Zone": "High Altitude", "Rainfall_MM": int(420 * rain_factor), "Fertilizer_Uptake_Score": min(0.80 * fert_factor, 1.0), "Estimated_Yield_Bags": int(3500000 * rain_factor * fert_factor), "Lat": 1.0191, "Lon": 34.9961},
    {"County": "Nakuru",      "Zone": "Rift Valley",   "Rainfall_MM": int(300 * rain_factor), "Fertilizer_Uptake_Score": min(0.65 * fert_factor, 1.0), "Estimated_Yield_Bags": int(2000000 * rain_factor * fert_factor), "Lat": -0.3031, "Lon": 36.0800},
    {"County": "Machakos",    "Zone": "Semi-Arid",     "Rainfall_MM": int(150 * rain_factor), "Fertilizer_Uptake_Score": min(0.40 * fert_factor, 1.0), "Estimated_Yield_Bags": int(500000 * rain_factor * (fert_factor * 0.8)), "Lat": -1.5177, "Lon": 37.2634},
    {"County": "Turkana",     "Zone": "Arid (ASAL)",   "Rainfall_MM": int(50 * rain_factor),  "Fertilizer_Uptake_Score": min(0.10 * fert_factor, 1.0), "Estimated_Yield_Bags": int(50000 * rain_factor * (fert_factor * 0.5)), "Lat": 3.1166, "Lon": 35.5973}
]

# 4. Convert the dictionary into a Pandas DataFrame
df = pd.DataFrame(mock_data)

# 5. Display the table on the website
st.subheader("2026 County-Level Projections (Dynamic Data)")
st.dataframe(df)

st.divider()

# 6. Build the Interactive Map
st.subheader("Dynamic Food Abundance Map")
st.write("Hover over the markers to view county-specific estimates. Use the sidebar to simulate different 2026 scenarios.")

kenya_map = folium.Map(location=[0.5, 37.0], zoom_start=6)

for index, row in df.iterrows():
    hover_text = f"""
    <b>{row['County']}</b><br>
    Zone: {row['Zone']}<br>
    Est. Yield: {row['Estimated_Yield_Bags']:,} bags<br>
    Rainfall: {row['Rainfall_MM']} mm<br>
    Fertilizer Subsidy Uptake: {round(row['Fertilizer_Uptake_Score'] * 100, 1)}%
    """
    
    # Logic: Green for high yield, Red for low yield
    circle_color = "green" if row['Estimated_Yield_Bags'] > 1000000 else "red"

    # Draw the dynamic circle
    folium.CircleMarker(
        location=[row['Lat'], row['Lon']],
        radius=max(row['Estimated_Yield_Bags'] / 250000, 5), # Dynamic size based on yield
        tooltip=hover_text,
        color=circle_color,
        fill=True,
        fill_color=circle_color,
        fill_opacity=0.6
    ).add_to(kenya_map)

# 7. Display the map
st_folium(kenya_map, width=700, height=500)

# 8. Global Agricultural Paradigms: Regional Comparison
st.divider()
st.header("Global Agricultural Paradigms: A Biochemical Comparison")
st.write("Contrasting Kenya's 2026 agricultural model with Europe and the Americas.")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🇰🇪 Kenya")
    st.write("**Model:** Rain-fed & Subsidy-Driven")
    st.write("**Biochemical Focus:** Maximizing primary macronutrient (Nitrogen/Phosphorus) uptake via subsidized DAP/CAN fertilizers. The goal is sheer biomass production to secure the staple food supply.")
    st.write("**System Resilience:** Highly sensitive. As seen in the map above, yields are strictly tethered to the MAM rainfall onset and the logistical success of input subsidies.")

with col2:
    st.subheader("🇪🇺 Europe")
    st.write("**Model:** Precision & Regulation ('Farm to Fork')")
    st.write("**Biochemical Focus:** High Nitrogen Use Efficiency (NUE) and microbial soil health. Strict EU limits on nitrate runoff mean farmers use soil bio-sensors to apply exact micro-doses of nutrients.")
    st.write("**System Resilience:** Highly buffered against weather anomalies due to established infrastructure, but overall yield is sometimes capped by strict environmental regulations.")

with col3:
    st.subheader("🇺🇸 America")
    st.write("**Model:** Mechanized & Genetic")
    st.write("**Biochemical Focus:** Heavy reliance on drought-resistant, genetically modified (GMO) crop strains and intense, variable-rate fertilizer application. Focus is on maximizing yield per acre at scale.")
    st.write("**System Resilience:** Robust. Massive irrigation networks (like the Ogallala Aquifer) and comprehensive crop insurance buffer the system against localized climatic shifts.")