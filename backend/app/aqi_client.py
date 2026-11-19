import logging
import os

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WAQI_URL = "https://api.waqi.info/feed/geo:{lat};{lon}/"

REQUEST_TIMEOUT = 10
OPEN_METEO_ATTEMPTS = 2

POLLUTANTS = {
    "us_aqi_pm2_5": "PM2.5",
    "us_aqi_pm10": "PM10",
    "us_aqi_ozone": "O3",
    "us_aqi_nitrogen_dioxide": "NO2",
    "us_aqi_sulphur_dioxide": "SO2",
    "us_aqi_carbon_monoxide": "CO",
}

WAQI_POLLUTANTS = {
    "pm25": "PM2.5",
    "pm10": "PM10",
    "o3": "O3",
    "no2": "NO2",
    "so2": "SO2",
    "co": "CO",
}


class AirQualityError(Exception):
    pass


def _get_json(url, params):
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        raise AirQualityError(f"Request to {url} failed: {e}") from e

    if response.status_code != 200:
        raise AirQualityError(f"{url} returned status {response.status_code}")

    try:
        return response.json()
    except ValueError as e:
        raise AirQualityError(f"{url} returned invalid JSON") from e


def _numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def fetch_open_meteo(lat, lon):
    data = _get_json(
        OPEN_METEO_URL,
        {"latitude": lat, "longitude": lon, "current": ",".join(POLLUTANTS)},
    )
    current = data.get("current") or {}
    observations = [
        {"aqi": current[field], "pollutant": name}
        for field, name in POLLUTANTS.items()
        if _numeric(current.get(field))
    ]
    if not observations:
        raise AirQualityError("Open-Meteo returned no AQI observations for this location")
    return observations


def fetch_waqi(lat, lon, token):
    data = _get_json(WAQI_URL.format(lat=lat, lon=lon), {"token": token})
    if data.get("status") != "ok":
        raise AirQualityError(f"WAQI returned status {data.get('status')!r}")

    iaqi = (data.get("data") or {}).get("iaqi") or {}
    observations = [
        {"aqi": iaqi[key]["v"], "pollutant": name}
        for key, name in WAQI_POLLUTANTS.items()
        if isinstance(iaqi.get(key), dict) and _numeric(iaqi[key].get("v"))
    ]
    if not observations:
        raise AirQualityError("WAQI returned no AQI observations for this location")
    return observations


def _sources():
    sources = [("Open-Meteo", fetch_open_meteo)] * OPEN_METEO_ATTEMPTS
    token = os.getenv("WAQI_TOKEN")
    if token:
        sources.append(("WAQI", lambda lat, lon: fetch_waqi(lat, lon, token)))
    return sources


def fetch_observations(lat, lon):
    """Try Open-Meteo (with one retry), then WAQI if WAQI_TOKEN is set."""
    errors = []
    for name, fetch in _sources():
        try:
            return fetch(lat, lon)
        except AirQualityError as e:
            logger.warning("AQI source %s failed: %s", name, e)
            errors.append(f"{name}: {e}")
    raise AirQualityError("All AQI sources failed (" + "; ".join(errors) + ")")
