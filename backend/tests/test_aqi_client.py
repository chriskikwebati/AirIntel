import pytest
import requests

from app import aqi_client
from app.aqi_client import AirQualityError, fetch_observations


class FakeResponse:
    def __init__(self, status_code=200, payload=None, bad_json=False):
        self.status_code = status_code
        self._payload = payload
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._payload


OPEN_METEO_OK = {"current": {"us_aqi_pm2_5": 59, "us_aqi_ozone": 20, "us_aqi_pm10": None}}
WAQI_OK = {"status": "ok", "data": {"iaqi": {"pm25": {"v": 120}, "o3": {"v": 40}, "t": {"v": 12}}}}


@pytest.fixture
def calls(monkeypatch):
    """Queue responses (or exceptions) per host; record which hosts were hit."""
    queue = {"open-meteo": [], "waqi": []}
    hits = []

    def fake_get(url, params=None, timeout=None):
        host = "waqi" if "waqi" in url else "open-meteo"
        hits.append(host)
        item = queue[host].pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(aqi_client.requests, "get", fake_get)
    monkeypatch.delenv("WAQI_TOKEN", raising=False)
    return queue, hits


def test_open_meteo_success_skips_nulls(calls):
    queue, hits = calls
    queue["open-meteo"].append(FakeResponse(payload=OPEN_METEO_OK))
    obs = fetch_observations(40.7, -74.0)
    assert {o["pollutant"]: o["aqi"] for o in obs} == {"PM2.5": 59, "O3": 20}
    assert hits == ["open-meteo"]


def test_open_meteo_retries_once(calls):
    queue, hits = calls
    queue["open-meteo"] += [requests.Timeout("slow"), FakeResponse(payload=OPEN_METEO_OK)]
    assert fetch_observations(1, 2)
    assert hits == ["open-meteo", "open-meteo"]


def test_falls_back_to_waqi_when_token_set(calls, monkeypatch):
    queue, hits = calls
    monkeypatch.setenv("WAQI_TOKEN", "test-token")
    queue["open-meteo"] += [FakeResponse(status_code=503), FakeResponse(bad_json=True)]
    queue["waqi"].append(FakeResponse(payload=WAQI_OK))
    obs = fetch_observations(1, 2)
    assert {o["pollutant"]: o["aqi"] for o in obs} == {"PM2.5": 120, "O3": 40}
    assert hits == ["open-meteo", "open-meteo", "waqi"]


def test_all_sources_fail_raises_airquality_error(calls, monkeypatch):
    queue, _ = calls
    monkeypatch.setenv("WAQI_TOKEN", "test-token")
    queue["open-meteo"] += [requests.ConnectionError("down"), FakeResponse(payload={"current": {}})]
    queue["waqi"].append(FakeResponse(payload={"status": "error", "data": "Invalid key"}))
    with pytest.raises(AirQualityError, match="All AQI sources failed"):
        fetch_observations(1, 2)


def test_no_waqi_without_token(calls):
    queue, hits = calls
    queue["open-meteo"] += [FakeResponse(status_code=500), FakeResponse(status_code=500)]
    with pytest.raises(AirQualityError):
        fetch_observations(1, 2)
    assert "waqi" not in hits
