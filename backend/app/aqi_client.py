import os

import requests
from dotenv import load_dotenv

load_dotenv()

AIRNOW_URL = "https://www.airnowapi.org/aq/observation/latLong/current/"


class AirNowError(Exception):
    pass


def fetch_observations(lat, lon, distance=25):
    api_key = os.getenv("AIRNOW_API_KEY")
    if not api_key:
        raise AirNowError("AIRNOW_API_KEY is not set")

    response = requests.get(
        AIRNOW_URL,
        params={
            "format": "application/json",
            "latitude": lat,
            "longitude": lon,
            "distance": distance,
            "API_KEY": api_key,
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise AirNowError(f"AirNow API returned status {response.status_code}")

    observations = response.json()
    if not observations:
        raise AirNowError("No AQI observations found near this location")

    return observations
