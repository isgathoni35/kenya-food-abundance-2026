from __future__ import annotations

from datetime import datetime, timezone
import time
from collections import defaultdict

import requests

from src.weather_normalization import classify_weather_payload


def _open_meteo_payload(lat, lon, timeout_seconds):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,precipitation"
        "&daily=temperature_2m_max,temperature_2m_min"
        "&forecast_days=7&timezone=auto"
    )
    r = requests.get(url, timeout=timeout_seconds)
    r.raise_for_status()
    return r.json()


def _build_daily_from_owm(forecast_list):
    grouped = defaultdict(list)
    for item in forecast_list:
        dt_txt = item.get("dt_txt", "")
        day_key = dt_txt[:10]
        if not day_key:
            continue
        main = item.get("main", {})
        t_min = main.get("temp_min")
        t_max = main.get("temp_max")
        if t_min is not None and t_max is not None:
            grouped[day_key].append((float(t_min), float(t_max)))

    days = sorted(grouped.keys())[:7]
    min_vals = []
    max_vals = []
    for day in days:
        mins = [m for m, _ in grouped[day]]
        maxs = [m for _, m in grouped[day]]
        min_vals.append(min(mins))
        max_vals.append(max(maxs))

    return {
        "time": days,
        "temperature_2m_max": max_vals,
        "temperature_2m_min": min_vals,
    }


def _open_weather_payload(lat, lon, api_key, timeout_seconds):
    # Use 5-day / 3-hour data as backup provider and normalize into app schema.
    forecast_url = (
        "https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    )
    r = requests.get(forecast_url, timeout=timeout_seconds)
    r.raise_for_status()
    payload = r.json()

    forecasts = payload.get("list", []) if isinstance(payload, dict) else []
    if not forecasts:
        return {"current": {}, "daily": {}}

    first = forecasts[0]
    main = first.get("main", {})
    rain_obj = first.get("rain", {})
    precipitation = rain_obj.get("3h", 0.0)
    current = {
        "temperature_2m": main.get("temp"),
        "precipitation": float(precipitation) if precipitation is not None else 0.0,
    }

    daily = _build_daily_from_owm(forecasts)
    return {"current": current, "daily": daily}


def _attempt_provider(provider_name, fetch_fn, retries, timeout_seconds):
    last_reason = "unknown"
    for attempt in range(1, retries + 1):
        try:
            payload = fetch_fn(timeout_seconds)
            classified = classify_weather_payload(payload)
            classified.update({"provider": provider_name, "attempts": attempt})

            if classified["status"] == "fallback" and attempt < retries:
                last_reason = classified["reason"]
                time.sleep(0.35 * attempt)
                continue

            return classified
        except requests.Timeout:
            last_reason = "timeout"
        except requests.RequestException:
            last_reason = "http_error"
        except ValueError:
            last_reason = "invalid_json"

        if attempt < retries:
            time.sleep(0.35 * attempt)

    return {
        "status": "fallback",
        "reason": last_reason,
        "provider": provider_name,
        "attempts": retries,
        "current": {},
        "daily": {},
    }


def fetch_weather_cascade(
    lat,
    lon,
    primary_retries,
    primary_timeout,
    secondary_timeout,
    secondary_api_key=None,
):
    if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return {
            "status": "fallback",
            "reason": "invalid_coordinates",
            "provider": "offline",
            "attempts": 0,
            "current": {},
            "daily": {},
            "last_live_utc": None,
        }

    primary = _attempt_provider(
        "open-meteo",
        fetch_fn=lambda timeout: _open_meteo_payload(lat, lon, timeout),
        retries=primary_retries,
        timeout_seconds=primary_timeout,
    )
    if primary["status"] in {"live_full", "live_partial"}:
        primary["last_live_utc"] = datetime.now(timezone.utc).isoformat()
        return primary

    if secondary_api_key:
        secondary = _attempt_provider(
            "openweathermap",
            fetch_fn=lambda timeout: _open_weather_payload(lat, lon, secondary_api_key, timeout),
            retries=1,
            timeout_seconds=secondary_timeout,
        )
        if secondary["status"] in {"live_full", "live_partial"}:
            secondary["last_live_utc"] = datetime.now(timezone.utc).isoformat()
            secondary["attempts"] = primary.get("attempts", primary_retries) + secondary.get("attempts", 1)
            return secondary
        return {
            "status": "fallback",
            "reason": f"primary_{primary.get('reason', 'failed')}_secondary_{secondary.get('reason', 'failed')}",
            "provider": "offline",
            "attempts": primary.get("attempts", primary_retries) + secondary.get("attempts", 1),
            "current": {},
            "daily": {},
            "last_live_utc": None,
        }

    return {
        "status": "fallback",
        "reason": f"primary_{primary.get('reason', 'failed')}_secondary_not_configured",
        "provider": "offline",
        "attempts": primary.get("attempts", primary_retries),
        "current": {},
        "daily": {},
        "last_live_utc": None,
    }
