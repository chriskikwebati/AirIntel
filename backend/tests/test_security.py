import pytest
from fastapi.testclient import TestClient

from app import main

from .conftest import VALID_TOKEN

client = TestClient(main.app)


@pytest.mark.parametrize(
    "params",
    [
        {"lat": 91, "lon": 0},
        {"lat": -91, "lon": 0},
        {"lat": 0, "lon": 181},
        {"lat": 0, "lon": -181},
        {"lat": "abc", "lon": 0},
        {"lat": 0},
    ],
)
def test_aqi_risk_rejects_invalid_coordinates(params):
    assert client.get("/api/aqi-risk", params=params).status_code == 422


@pytest.mark.parametrize(
    "token",
    ["", "not-a-token", "ExponentPushToken[]", "ExponentPushToken[abc]<script>", "ExponentPushToken[" + "a" * 500 + "]"],
)
def test_register_rejects_malformed_push_tokens(db_session, token):
    response = client.post("/api/alerts/register", json={"push_token": token, "lat": 0, "lon": 0})
    assert response.status_code == 422


def test_register_rejects_out_of_range_location(db_session):
    response = client.post("/api/alerts/register", json={"push_token": VALID_TOKEN, "lat": 100, "lon": 0})
    assert response.status_code == 422


@pytest.mark.parametrize("header", [None, "", "wron", "right-but-longer"])
def test_internal_endpoints_reject_bad_secrets(monkeypatch, header):
    monkeypatch.setenv("ALERT_CRON_SECRET", "right")
    headers = {} if header is None else {"X-Alert-Secret": header}
    assert client.post("/internal/alerts/check", headers=headers).status_code == 401
    assert client.get("/internal/stats", headers=headers).status_code == 401


def test_internal_endpoints_locked_when_secret_unset(monkeypatch):
    monkeypatch.delenv("ALERT_CRON_SECRET", raising=False)
    assert client.post("/internal/alerts/check", headers={"X-Alert-Secret": ""}).status_code == 401


def test_aqi_risk_is_rate_limited(monkeypatch):
    monkeypatch.setattr(main, "fetch_observations", lambda lat, lon: [{"aqi": 10, "pollutant": "O3"}])
    statuses = [client.get("/api/aqi-risk", params={"lat": 1, "lon": 1}).status_code for _ in range(31)]
    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429


def test_rate_limit_uses_proxy_added_address_only(monkeypatch):
    """A client can't dodge the limit by faking the left part of X-Forwarded-For."""
    monkeypatch.setenv("TRUST_PROXY", "true")
    monkeypatch.setattr(main, "fetch_observations", lambda lat, lon: [{"aqi": 10, "pollutant": "O3"}])
    statuses = [
        client.get(
            "/api/aqi-risk",
            params={"lat": 1, "lon": 1},
            headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"},
        ).status_code
        for i in range(31)
    ]
    assert statuses[30] == 429


def test_responses_carry_request_id_and_security_headers():
    response = client.get("/healthz", headers={"X-Request-ID": "trace-123"})
    assert response.headers["X-Request-ID"] == "trace-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_unsafe_request_id_is_replaced():
    response = client.get("/healthz", headers={"X-Request-ID": "bad id\nwith newline"})
    assert response.headers["X-Request-ID"] != "bad id\nwith newline"
    assert len(response.headers["X-Request-ID"]) == 32
