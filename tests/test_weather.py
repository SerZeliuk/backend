# tests/test_app.py
import json
import datetime as dt
import pytest
from unittest.mock import patch, MagicMock

from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    return app.test_client()

def make_response(ok: bool, status_code: int, payload: dict):
    """
    Helper to create a fake requests.Response-like object.
    """
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp

# ── Tests for /api/weather ──────────────────────────────────────────

@patch('app.requests.get')
def test_weather_daily_success(mock_get, client):
    # raw payload from Open-Meteo
    raw = {
        "daily": {
            "time": ["2025-06-01", "2025-06-02"],
            "sunshine_duration": [3600, 7200],
            "temperature_2m_max": [25, 26],
            "temperature_2m_min": [15, 16],
            "weather_code": [0, 1]
        },
        "daily_units": {
            "sunshine_duration": "s",
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C"
        }
    }
    mock_get.return_value = make_response(True, 200, raw)

    resp = client.get('/api/weather/10/20/2025-06-01/2025-06-02')
    assert resp.status_code == 200

    expected = {
        "daily": raw["daily"],
        "daily_units": raw["daily_units"]
    }
    assert resp.get_json() == expected

@patch('app.requests.get')
def test_weather_daily_invalid_latlon(mock_get, client):
    # Non‐numeric lat/lon should be caught before any HTTP call
    resp = client.get('/api/weather/foo/bar')
    assert resp.status_code == 400
    assert b"Latitude and longitude must be numeric" in resp.data

@patch('app.requests.get')
def test_weather_daily_no_data(mock_get, client):
    # Simulate Open-Meteo returning {} → 404
    mock_get.return_value = make_response(True, 200, {})
    resp = client.get('/api/weather/10/20')
    assert resp.status_code == 404
    assert b"No weather data found" in resp.data

@patch('app.requests.get')
def test_weather_daily_bad_date_order(mock_get, client):
    
    resp = client.get('/api/weather/10/20/2025-06-10/2025-06-05')
    assert resp.status_code == 400
    assert b"start_date cannot be after end_date" in resp.data

@patch('app.requests.get')
def test_weather_weekly_success(mock_get, client):
    raw = {
        "daily": {
            "time": ["2025-06-01", "2025-06-02"],
            "pressure_msl_mean": [1000, 1020],
            "temperature_2m_max": [5, 10],
            "temperature_2m_min": [2, 0],
            "sunshine_duration": [3600, 3600],
            "weather_code": [3, 3, 2]
        }
    }
    mock_get.return_value = make_response(True, 200, raw)

    resp = client.get('/api/weekly/10/20/2025-06-01/2025-06-02')
    assert resp.status_code == 200

    body = resp.get_json()
    # avg_pressure = mean([1000,1020])=1010.0 → rounded to 1010.0
    assert pytest.approx(body["avg_pressure_hPa"], rel=1e-3) == 1010.0
    # max temp = 10, min temp = 0
    assert body["weekly_max_temp"] == 10
    assert body["weekly_min_temp"] == 0
    # avg_sunshine_hours = mean([3600,3600])/3600 = 1.0
    assert pytest.approx(body["avg_sunshine_hours"], rel=1e-3) == 1.0
    # most frequent code = 3
    assert body["most_frequent_weather_code"] == 3
    # start_date/end_date echoed from raw
    assert body["start_date"] == "2025-06-01"
    assert body["end_date"]   == "2025-06-02"

@patch('app.requests.get')
def test_weather_weekly_invalid_latlon(mock_get, client):
    resp = client.get('/api/weekly/foo/bar')
    assert resp.status_code == 400
    assert b"Latitude and longitude must be numeric" in resp.data

@patch('app.requests.get')
def test_weather_weekly_empty_data(mock_get, client):
    # daily exists but all arrays empty → 404
    raw = {"daily": {}}
    mock_get.return_value = make_response(True, 200, raw)

    resp = client.get('/api/weekly/10/20')
    assert resp.status_code == 404
    assert b"Weather service returned empty data set" in resp.data

@patch('app.requests.get')
def test_weather_weekly_no_daily(mock_get, client):
    # missing 'daily' key → 404
    mock_get.return_value = make_response(True, 200, {})
    resp = client.get('/api/weekly/10/20')
    assert resp.status_code == 404
    assert b"No weather data found" in resp.data
