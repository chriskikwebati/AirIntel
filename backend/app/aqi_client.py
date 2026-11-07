import requests

OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

POLLUTANTS = {
    "us_aqi_pm2_5": "PM2.5",
    "us_aqi_pm10": "PM10",
    "us_aqi_ozone": "O3",
    "us_aqi_nitrogen_dioxide": "NO2",
    "us_aqi_sulphur_dioxide": "SO2",
    "us_aqi_carbon_monoxide": "CO",
}


class AirQualityError(Exception):
    pass


def fetch_observations(lat, lon):
    response = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": ",".join(POLLUTANTS),
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise AirQualityError(f"Open-Meteo API returned status {response.status_code}")

    current = response.json().get("current", {})
    observations = [
        {"aqi": current[field], "pollutant": name}
        for field, name in POLLUTANTS.items()
        if current.get(field) is not None
    ]
    if not observations:
        raise AirQualityError("No AQI observations found near this location")

    return observations
