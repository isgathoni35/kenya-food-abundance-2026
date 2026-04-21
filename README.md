# Kenya Food Abundance 2026

This app is a simple decision-support tool that helps you explore possible maize food production across all 47 counties in Kenya for the year 2026.

It is designed for learning, planning, and discussion.
It is not an official government forecast.

## In Plain Language: What This App Is About
- It gives each county an estimated maize output (in 90kg bags).
- It shows this estimate on a map and in a ranked table.
- It lets you test "what if" scenarios by changing rainfall and fertilizer support.
- It shows live weather when available, and safe fallback weather when live data is unavailable.
- It includes a model evidence panel so you can see how well the model fit historical data.

## Why Someone Would Use It
- To compare counties that may do better or worse under different weather and fertilizer conditions.
- To understand how rainfall and fertilizer support can affect county food output.
- To have a visual and easy way to discuss food planning scenarios.

## What You Will See In The App
1. Left panel (Live Weather Station)
- Select a county.
- See current temperature and rain (if live weather is available).
- Use sliders to change rainfall and fertilizer impact.

2. Main map
- Colored circles represent county output levels.
- Click a county marker to view details.

3. Ranked table
- Counties listed from higher to lower simulated output.

4. Model Evidence section
- Shows model quality numbers and feature influence values.

## Where The Numbers Come From
The app uses three data layers:
- County baseline data (location, zone, and base values).
- Rainfall history.
- Fertilizer and yield history used to train a simple prediction model.

The model then predicts county output for 2026.
Those predictions are used as the base values that your slider changes are applied to.

## Important Data Transparency Note
- Rainfall data is sourced from a public weather API.
- Fertilizer and historical yield data in this project are transparent proxy datasets for assignment use.
- This means results are scenario estimates, not official national statistics.

## Easy Explanation Of Model Terms
about RMSE, MAE, and R². Here is a simple explanation:

- RMSE (Root Mean Squared Error)
  - Think of this as the model's "typical big mistake size."
  - Lower is better.
  - It gives more weight to large mistakes.

- MAE (Mean Absolute Error)
  - Think of this as the model's "average mistake size."
  - Lower is better.
  - It treats all mistakes more evenly.

- R² (R-squared)
  - Think of this as "how much of the pattern in the data the model can explain."
  - Closer to 1 is better.
  - Example: 0.80 means the model explains about 80% of variation in historical data.

Simple rule of thumb:
- Lower RMSE and MAE are good.
- Higher R² is good.

## How To Read Results Carefully
- Use outputs as guidance for comparison, not exact future truth.
- Focus on county-to-county trends and direction of change.
- Test multiple slider settings before making conclusions.
- Remember that real-world events (policy, pests, prices, conflict, logistics) can change outcomes.

## Quick Start
1. Install dependencies

```bash
pip install -r requirements.txt
```

2. Run the app

```bash
python -m streamlit run app.py --server.port 8501
```

3. Open the URL printed in terminal (usually http://localhost:8501)

## Optional: Better Weather Reliability
If you want a backup weather source, create .streamlit/secrets.toml with:

```toml
OPEN_WEATHER_MAP_API_KEY = "your_openweathermap_api_key"
```

## Main Files In This Project
- app.py: dashboard and user interface.
- data/kenya_counties_baseline.csv: county baseline inputs.
- data/raw/: raw rainfall, subsidy, and yield inputs.
- data/processed/: generated predictions and model evidence outputs.
- src/prediction_pipeline.py: script that trains model and creates 2026 predictions.

## Final Reminder
This app is best used for education, scenario planning, and discussion.
It should not be treated as an official forecast or policy decision tool on its own.
