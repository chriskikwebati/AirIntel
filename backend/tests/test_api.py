from fastapi.testclient import TestClient

from app import main
from app.aqi_client import AirQualityError

client = TestClient(main.app)


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_aqi_risk_returns_assessment(monkeypatch):
    monkeypatch.setattr(main, "fetch_observations", lambda lat, lon: [{"aqi": 59, "pollutant": "PM2.5"}])
    body = client.get("/api/aqi-risk", params={"lat": 40.7, "lon": -74.0}).json()
    assert body["category_name"] == "Moderate"
    assert body["risk_level"] == "low"


def test_aqi_risk_returns_502_when_sources_fail(monkeypatch):
    def boom(lat, lon):
        raise AirQualityError("All AQI sources failed")

    monkeypatch.setattr(main, "fetch_observations", boom)
    response = client.get("/api/aqi-risk", params={"lat": 1, "lon": 2})
    assert response.status_code == 502
