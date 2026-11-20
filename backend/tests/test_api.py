from fastapi.testclient import TestClient

from app import main
from app.aqi_client import AirQualityError
from app.models import Device

from .conftest import VALID_TOKEN

client = TestClient(main.app)


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_aqi_risk_returns_assessment(monkeypatch):
    monkeypatch.setattr(main, "fetch_observations", lambda lat, lon: [{"aqi": 59, "pollutant": "PM2.5"}])
    body = client.get("/api/aqi-risk", params={"lat": 40.7, "lon": -74.0}).json()
    assert body["category_name"] == "Moderate"
    assert body["risk_level"] == "low"


def test_aqi_risk_returns_502_without_leaking_upstream_errors(monkeypatch):
    def boom(lat, lon):
        raise AirQualityError("Request to https://internal.example failed: secret detail")

    monkeypatch.setattr(main, "fetch_observations", boom)
    response = client.get("/api/aqi-risk", params={"lat": 1, "lon": 2})
    assert response.status_code == 502
    assert "internal.example" not in response.text


def test_alert_check_rejects_bad_secret_before_touching_db(monkeypatch):
    monkeypatch.setenv("ALERT_CRON_SECRET", "right")
    response = client.post("/internal/alerts/check", headers={"X-Alert-Secret": "wrong"})
    assert response.status_code == 401


def test_alert_endpoints_return_503_without_database(monkeypatch):
    from app import db

    monkeypatch.setattr(db, "SessionLocal", None)
    monkeypatch.setenv("ALERT_CRON_SECRET", "right")
    assert client.post("/internal/alerts/check", headers={"X-Alert-Secret": "right"}).status_code == 503
    assert client.post("/api/alerts/register", json={"push_token": VALID_TOKEN, "lat": 0, "lon": 0}).status_code == 503


def test_register_then_unregister_device(db_session):
    payload = {"push_token": VALID_TOKEN, "lat": 38.9, "lon": -77.0}
    assert client.post("/api/alerts/register", json=payload).status_code == 200
    # Registering again updates the location instead of adding a second row.
    assert client.post("/api/alerts/register", json={**payload, "lat": 39.0}).status_code == 200
    devices = db_session.query(Device).all()
    assert len(devices) == 1 and devices[0].lat == 39.0

    assert client.post("/api/alerts/unregister", json={"push_token": VALID_TOKEN}).status_code == 200
    assert db_session.query(Device).count() == 0
