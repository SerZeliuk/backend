from flask import Flask, jsonify, abort
from flask_cors import CORS

from statistics import mean
from collections import Counter
import datetime as dt
import requests

REQUEST_TIMEOUT = 8          

def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    def build_api_call(lat: float, lon: float, daily : bool,
                       start: str | None = None,
                       end:   str | None = None, 
                       ) -> str:

        today = dt.date.today()
        if start is None:
            start = today.strftime('%Y-%m-%d')
        if end is None:
            end = (today + dt.timedelta(days=7)).strftime('%Y-%m-%d')

        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise ValueError("Latitude and longitude must be numeric (e.g. 37.77 -122.42).")

        if not (-90 <= int(lat) <= 90) or not (-180 <= int(lon) <= 180):
            raise ValueError("Latitude must be −90…90 and longitude −180…180.")

        try:
            start_d = dt.date.fromisoformat(start)
            end_d   = dt.date.fromisoformat(end)
        except ValueError:
            raise ValueError("Dates must be YYYY-MM-DD.")

        if start_d > end_d:
            raise ValueError("start_date cannot be after end_date.")

        lat, lon = round(lat, 2), round(lon, 2)

        pressure =  "" if daily else ",pressure_msl_mean"
        return (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}"
            f"&longitude={lon}"
            "&daily=sunshine_duration,temperature_2m_max,temperature_2m_min,"
            f"weather_code{pressure}"
            "&timezone=auto"
            f"&start_date={start}"
            f"&end_date={end}"
        )

    def fetch_weather(lat, lon, daily, start=None, end=None):
        url = build_api_call(lat, lon, daily, start, end)
        r   = requests.get(url, timeout=REQUEST_TIMEOUT)
        if r.ok:
            return r.json()
        abort(r.status_code, description="Open-Meteo error")

    @app.route("/api/weather/<lat>/<lon>")
    @app.route("/api/weather/<lat>/<lon>/<start>/<end>")
    def weather_daily(lat, lon, start=None, end=None):
        # ── 1 · validate & cast lat/lon ───────────────────────────────
        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            abort(400, description="Latitude and longitude must be numeric (e.g. 37.77 -122.42).")

        # ── 2 · fetch raw payload ────────────────────────────────────────
        try:
            raw = fetch_weather(lat, lon, True, start, end)   # your helper
        except ValueError as e:
            abort(400, description=str(e))

        if not raw or "daily" not in raw:
            abort(404, description="No weather data found for the given location and date range.")

        # ── 3 · pluck only the fields the frontend needs ────────────────
        daily      = raw["daily"]
        daily_units = raw.get("daily_units", {})

        filtered = {
            "daily": {
                "time":                 daily.get("time", []),
                "sunshine_duration":    daily.get("sunshine_duration", []),
                "temperature_2m_max":   daily.get("temperature_2m_max", []),
                "temperature_2m_min":   daily.get("temperature_2m_min", []),
                "weather_code":         daily.get("weather_code", []),
            },
            "daily_units": {
                "sunshine_duration":    daily_units.get("sunshine_duration", ""),
                "temperature_2m_max":   daily_units.get("temperature_2m_max", ""),
                "temperature_2m_min":   daily_units.get("temperature_2m_min", ""),
            }
        }

        return jsonify(filtered)

    @app.route("/api/weekly/<lat>/<lon>")
    @app.route("/api/weekly/<lat>/<lon>/<start>/<end>")
    def weather_weekly(lat, lon, start=None, end=None):
        # ── 1 · validate & cast lat/­lon ───────────────────────────────
        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            abort(400, description="Latitude and longitude must be numeric (e.g. 37.77 -122.42).")

        # ── 2 · fetch the daily array payload (8 data points max) ─────
        try:
            data = fetch_weather(lat, lon, False, start, end)  # your helper
        except ValueError as e:
            abort(400, description=str(e))

        if not data or "daily" not in data:
            abort(404, description="No weather data found for the given location and date range.")

        daily = data["daily"]

        # ── 3 · extract lists safely ──────────────────────────────────
        pressures = daily.get("pressure_msl_mean", [])
        t_max     = daily.get("temperature_2m_max", [])
        t_min     = daily.get("temperature_2m_min", [])
        sunshine  = daily.get("sunshine_duration", [])
        codes     = daily.get("weather_code", [])

        # make sure there's at least one data point
        if not any([pressures, t_max, t_min, sunshine, codes]):
            abort(404, description="Weather service returned empty data set.")

        # ── 4 · derive weekly statistics ──────────────────────────────
        result = {
            "avg_pressure_hPa": round(mean(pressures), 1)            if pressures else None,
            "weekly_max_temp": max(t_max)                            if t_max      else None,
            "weekly_min_temp": min(t_min)                            if t_min      else None,
            "avg_sunshine_hours": round(mean(sunshine) / 3600, 2)    if sunshine   else None,
            "most_frequent_weather_code":
                Counter(codes).most_common(1)[0][0]                  if codes      else None,
            # keep original meta for context (optional)
            "latitude":  data.get("latitude"),
            "longitude": data.get("longitude"),
            "start_date": daily["time"][0] if daily.get("time") else start,
            "end_date":   daily["time"][-1] if daily.get("time") else end,
        }

        return jsonify(result)             # 200 OK with the aggregate stats


   
    return app
