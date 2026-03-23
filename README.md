# Kenya Food Abundance 2026

This app helps you explore how food production might look across all 47 counties in Kenya in 2026.

It is made for learning and planning. It is not a government forecast.

## What The App Does
- Shows all 47 counties on an interactive map.
- Estimates maize yield (in 90kg bags) for each county.
- Lets you adjust two important factors:
  - rainfall situation,
  - fertilizer support.
- Shows live weather for the county you choose.
- Keeps working even if live weather is temporarily unavailable.

## Why This Is Useful
- You can quickly see which counties may improve or struggle under different conditions.
- You can compare possible outcomes when rainfall is better or worse.
- You can understand how fertilizer support may change yield estimates.

## What You See On The Screen
1. Sidebar (left side)
- Choose a county to monitor.
- View current temperature and rain (live weather).
- Adjust rainfall and fertilizer sliders.

2. Main map (center)
- County circles show estimated abundance.
- Click a county marker to see details.

3. Yield table (right side)
- Ranked list of counties by estimated yield.

4. Comparison section (bottom)
- Simple Kenya vs Europe vs America model summary.

## About Live Weather
- The app first tries Open-Meteo.
- If that fails, it can try OpenWeatherMap (if key is set).
- If both fail, the app shows a safe offline estimate so it does not crash.

## Quick Start (Simple Steps)
1. Install requirements:

```bash
pip install -r requirements.txt
```

2. Start the app:

```bash
python -m streamlit run app.py --server.port 8501
```

3. Open the local link shown in the terminal (usually `http://localhost:8501`).

## Optional: Enable Backup Weather Provider
This is only needed if you want better weather reliability.

Create `.streamlit/secrets.toml` and add:

```toml
OPEN_WEATHER_MAP_API_KEY = "your_openweathermap_api_key"
```

## Project Files (For Reference)
- `app.py`: main dashboard app.
- `data/kenya_counties_baseline.csv`: county baseline data.
- `src/weather_providers.py`: weather provider logic.
- `src/weather_normalization.py`: weather data formatting.
- `requirements.txt`: required Python packages.

## Important Note
The numbers in this app are simulation-based estimates meant for educational and planning discussions.
