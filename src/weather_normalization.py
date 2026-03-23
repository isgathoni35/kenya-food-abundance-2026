from __future__ import annotations

import pandas as pd


def classify_weather_payload(payload):
    if not isinstance(payload, dict):
        return {
            "status": "fallback",
            "reason": "malformed_payload",
            "current": {},
            "daily": {},
            "has_current": False,
            "has_forecast": False,
        }

    current = payload.get("current", {})
    daily = payload.get("daily", {})
    if not isinstance(current, dict):
        current = {}
    if not isinstance(daily, dict):
        daily = {}

    c_temp = current.get("temperature_2m")
    c_rain = current.get("precipitation")
    has_current = c_temp is not None and c_rain is not None

    days = daily.get("time")
    max_t = daily.get("temperature_2m_max")
    min_t = daily.get("temperature_2m_min")
    has_forecast = (
        isinstance(days, list)
        and isinstance(max_t, list)
        and isinstance(min_t, list)
        and len(days) > 0
        and len(days) == len(max_t)
        and len(days) == len(min_t)
    )

    if has_current and has_forecast:
        status = "live_full"
        reason = "ok"
    elif has_current:
        status = "live_partial"
        reason = "forecast_incomplete"
    else:
        status = "fallback"
        reason = "current_missing"

    return {
        "status": status,
        "reason": reason,
        "current": current,
        "daily": daily,
        "has_current": has_current,
        "has_forecast": has_forecast,
    }


def build_forecast_frame(weather_payload):
    daily = weather_payload.get("daily", {}) if isinstance(weather_payload, dict) else {}
    days = daily.get("time")
    max_t = daily.get("temperature_2m_max")
    min_t = daily.get("temperature_2m_min")

    if not all(isinstance(v, list) for v in [days, max_t, min_t]):
        return None
    if not days or len(days) != len(max_t) or len(days) != len(min_t):
        return None

    return pd.DataFrame({"Day": days, "Max Temp": max_t, "Min Temp": min_t}).set_index("Day")
