# Workflow: Kenya Food Abundance 2026 (Python + Streamlit)

## 1. Project Goal
Build an interactive Streamlit dashboard that visualizes Kenya's projected 2026 food abundance using:
- Rainfall data (focus on MAM and seasonal trends)
- Fertilizer subsidy effects
- County-level yield response assumptions

The app must also include a comparison view between:
- Kenya
- Europe (regional aggregate)
- America (regional aggregate)

## 2. Scope and Deliverables
### Core Deliverables
1. Kenya county-level dynamic map (Folium embedded in Streamlit)
2. Data pipeline that combines rainfall and fertilizer signals
3. Food abundance index for 2026
4. Comparison section for Kenya vs Europe vs America
5. Basic documentation for assumptions and update process

### Out of Scope (v1)
- Full causal inference modeling
- Commodity-level forecasting for all crops
- Policy simulation with uncertainty intervals

## 3. Recommended Project Structure
Use this structure as implementation grows:

```text
.
|-- app.py
|-- data/
|   |-- raw/
|   |-- processed/
|   |-- reference/
|-- src/
|   |-- data_ingestion.py
|   |-- feature_engineering.py
|   |-- abundance_model.py
|   |-- map_builder.py
|   |-- comparison.py
|   |-- validation.py
|-- README.md
|-- WORKFLOW.md
|-- requirements.txt
```

## 4. Data Requirements
### Kenya Rainfall Data
- Source candidates: CHIRPS, Kenya Meteorological Department, FEWS NET, or ERA5
- Required fields:
  - county
  - date (monthly preferred)
  - rainfall_mm
  - seasonal aggregation tags (MAM, JJA, OND)

### Fertilizer Subsidy Data
- Source candidates: Ministry of Agriculture reports, policy bulletins, county-level distribution records
- Required fields:
  - county
  - year
  - subsidy_rate (percent or KES support)
  - fertilizer_access_proxy (distribution volume or farmer coverage)

### Production or Abundance Proxy
- Source candidates: KNBS, FAOSTAT, WFP, or agricultural bulletins
- Required fields:
  - county
  - crop_yield_proxy
  - baseline production index

### Comparison Data (Kenya, Europe, America)
- Create a normalized index dataset for 2026 with aligned features:
  - region
  - rainfall_anomaly
  - fertilizer_support_index
  - output_or_abundance_proxy
  - final_food_abundance_index

Notes:
- Use regional aggregates for Europe and America in v1.
- Optionally add country-level drilldown (for example Germany, France, USA, Brazil) in v2.

## 5. Data Pipeline Workflow
1. Ingest raw files from trusted sources into data/raw.
2. Standardize schema names and units (rainfall in mm, subsidy in numeric index).
3. Handle missing values:
   - Fill short gaps with interpolation.
   - Flag long gaps for manual review.
4. Aggregate to county-month and county-season levels.
5. Build a 2026 abundance modeling table with one row per county.
6. Save curated datasets into data/processed.

## 6. Feature Engineering and Index Design
### Suggested Kenya Features
- rainfall_deviation_index (from historical average)
- mam_rain_score
- fertilizer_support_score
- yield_sensitivity_factor (county-specific assumption)

### Example Composite Index
Use a weighted index to start:

FoodAbundanceIndex = 0.45 x RainfallScore + 0.35 x FertilizerScore + 0.20 x BaselineProductionScore

Normalize final index to 0-100 for clear map legends and regional comparison.

## 7. Streamlit Implementation Steps
1. Build base app shell in app.py.
2. Add sidebar controls:
   - data scenario
   - county filter
   - month or season selector
   - index weighting sliders (optional)
3. Build Folium Kenya map:
   - county choropleth by FoodAbundanceIndex
   - popup with rainfall, subsidy, and final score
4. Embed map with streamlit-folium.
5. Add trend charts below map (county and national trends).

## 8. Comparison Section (Kenya vs Europe vs America)
Create a dedicated section below the Kenya map with:

1. Metric cards:
   - Food Abundance Index (2026)
   - Rainfall anomaly index
   - Fertilizer support index
2. Grouped bar chart for Kenya, Europe, America
3. Radar chart or normalized profile chart for multi-factor comparison
4. Interpretation panel:
   - Highlight strengths and risks for each region
   - Explain that indices are normalized for comparability, not absolute output parity

## 9. Validation and Quality Checks
1. Range checks:
   - Rainfall and subsidies within realistic bounds
2. Consistency checks:
   - No duplicated county-season rows
3. Sanity tests:
   - Counties with severe rainfall deficits should not score unrealistically high without strong subsidy support
4. Manual review:
   - Spot-check 5 counties against source reports

## 10. Iterative Delivery Plan
### Milestone 1: Data Foundation
- Collect and standardize Kenya rainfall and subsidy datasets
- Prepare county-level reference geometry

### Milestone 2: Kenya Dynamic Map
- Produce county-level abundance index
- Render interactive map with filters

### Milestone 3: Regional Comparison
- Add Kenya-Europe-America normalized dataset
- Implement comparison charts and summary text

### Milestone 4: Hardening and Deployment
- Add validation checks
- Improve UX and performance
- Deploy Streamlit app (Streamlit Community Cloud or container host)

## 11. Definition of Done (v1)
The project is complete for v1 when:
1. Kenya county map loads and updates with selected scenario or season.
2. Rainfall and fertilizer variables are visible and traceable in UI.
3. A clear comparison panel for Kenya, Europe, and America is available.
4. Data assumptions are documented in README.md.
5. App is deployable and reproducible with requirements.txt.

## 12. Suggested Next Tasks
1. Create app.py and src modules from the structure above.
2. Add sample CSV templates to data/reference.
3. Implement first-pass index computation and map rendering.
4. Add comparison section with placeholder normalized values, then replace with validated data.
