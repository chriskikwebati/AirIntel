from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import main, push
from app.aqi_client import AirQualityError
from app.models import AlertHistory, Device, utcnow

client = TestClient(main.app)
SECRET = {"X-Alert-Secret": "right"}


@pytest.fixture(autouse=True)
def alert_secret(monkeypatch):
    monkeypatch.setenv("ALERT_CRON_SECRET", "right")


def add_device(db, token, lat=1.0, lon=1.0, last=None):
    device = Device(push_token=token, lat=lat, lon=lon, last_notified_risk_level=last)
    db.add(device)
    db.commit()
    return device


def fake_aqi(by_lat):
    """Return a given AQI per device latitude; None means the lookup fails."""

    def fetch(lat, lon):
        if by_lat[lat] is None:
            raise AirQualityError("down")
        return [{"aqi": by_lat[lat], "pollutant": "PM2.5"}]

    return fetch


def test_alert_check_notifies_records_history_and_reports_summary(db_session, monkeypatch):
    add_device(db_session, "ExponentPushToken[risky]", lat=1.0)
    add_device(db_session, "ExponentPushToken[clean]", lat=2.0)
    add_device(db_session, "ExponentPushToken[down]", lat=3.0)
    sent = []
    monkeypatch.setattr(push, "fetch_observations", fake_aqi({1.0: 180, 2.0: 20, 3.0: None}))
    monkeypatch.setattr(push, "send_expo_push", lambda token, title, body: sent.append(token))

    body = client.post("/internal/alerts/check", headers=SECRET).json()

    assert sent == ["ExponentPushToken[risky]"]
    assert body == {
        "status": "checked", "devices": 3, "checked": 2, "notified": 1,
        "aqi_failures": 1, "push_failures": 0, "removed": 0,
    }
    history = db_session.query(AlertHistory).order_by(AlertHistory.aqi).all()
    assert [(h.aqi, h.risk_level, h.notified) for h in history] == [(20, "low", False), (180, "high", True)]


def test_alert_check_does_not_repeat_notifications(db_session, monkeypatch):
    add_device(db_session, "ExponentPushToken[risky]", last="high")
    sent = []
    monkeypatch.setattr(push, "fetch_observations", fake_aqi({1.0: 180}))
    monkeypatch.setattr(push, "send_expo_push", lambda *args: sent.append(args))
    push.run_alert_check(db_session)
    assert sent == []


def test_failed_push_is_retried_next_run(db_session, monkeypatch):
    device = add_device(db_session, "ExponentPushToken[risky]")
    monkeypatch.setattr(push, "fetch_observations", fake_aqi({1.0: 180}))

    def fail(*args):
        raise push.PushError("Expo down")

    monkeypatch.setattr(push, "send_expo_push", fail)
    summary = push.run_alert_check(db_session)
    assert summary["push_failures"] == 1
    assert device.last_notified_risk_level is None  # so the next run sends it again


def test_device_removed_when_expo_says_not_registered(db_session, monkeypatch):
    add_device(db_session, "ExponentPushToken[gone]")
    monkeypatch.setattr(push, "fetch_observations", fake_aqi({1.0: 180}))

    def gone(*args):
        raise push.DeviceNotRegistered("DeviceNotRegistered")

    monkeypatch.setattr(push, "send_expo_push", gone)
    assert push.run_alert_check(db_session)["removed"] == 1
    assert db_session.query(Device).count() == 0


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.mark.parametrize(
    "status_code, payload, expected",
    [
        (200, {"data": {"status": "ok", "id": "x"}}, None),
        (200, {"data": [{"status": "ok"}]}, None),
        (500, {}, push.PushError),
        (200, {"data": {"status": "error", "message": "bad"}}, push.PushError),
        (200, {"data": {"status": "error", "details": {"error": "DeviceNotRegistered"}}}, push.DeviceNotRegistered),
    ],
)
def test_send_expo_push_reads_expo_result(monkeypatch, status_code, payload, expected):
    monkeypatch.setattr(push.requests, "post", lambda *a, **kw: FakeResponse(status_code, payload))
    if expected is None:
        push.send_expo_push("ExponentPushToken[x]", "t", "b")
    else:
        with pytest.raises(expected):
            push.send_expo_push("ExponentPushToken[x]", "t", "b")


def test_old_history_is_pruned(db_session, monkeypatch):
    db_session.add(
        AlertHistory(
            checked_at=utcnow() - timedelta(days=100), aqi=50,
            category_name="Good", risk_level="low", dominant_pollutant="O3",
        )
    )
    db_session.commit()
    push.run_alert_check(db_session)
    assert db_session.query(AlertHistory).count() == 0


def test_stats_aggregates_recent_history(db_session):
    a = add_device(db_session, "ExponentPushToken[a]")
    b = add_device(db_session, "ExponentPushToken[b]")
    add_device(db_session, "ExponentPushToken[quiet]")
    now = utcnow()
    rows = [
        (a.id, now - timedelta(hours=1), 180, "high", "PM2.5", True),
        (a.id, now - timedelta(hours=2), 120, "moderate", "PM2.5", False),
        (b.id, now - timedelta(hours=3), 40, "low", "O3", False),
        (b.id, now - timedelta(days=20), 300, "very_high", "O3", True),  # outside the 7-day window
    ]
    for device_id, checked_at, aqi, risk, pollutant, notified in rows:
        db_session.add(
            AlertHistory(
                device_id=device_id, checked_at=checked_at, aqi=aqi, category_name="x",
                risk_level=risk, dominant_pollutant=pollutant, notified=notified,
            )
        )
    db_session.commit()

    response = client.get("/internal/stats", params={"days": 7}, headers=SECRET)
    assert response.status_code == 200
    stats = response.json()

    assert stats["registered_devices"] == 3
    assert stats["checks"] == 3
    assert stats["alerts_sent"] == 1
    assert stats["worst_aqi"] == 180
    assert {r["risk_level"]: r["checks"] for r in stats["by_risk_level"]} == {"high": 1, "moderate": 1, "low": 1}
    assert stats["by_pollutant"][0] == {"pollutant": "PM2.5", "checks": 2, "worst_aqi": 180}

    devices = {d["device_id"]: d for d in stats["devices"]}
    assert devices[a.id]["alerts_sent"] == 1 and devices[a.id]["checks"] == 2
    assert devices[b.id]["worst_aqi"] == 40
    assert all("push_token" not in d for d in stats["devices"])
    assert stats["devices"][0]["device_id"] == a.id  # most alerts first
    quiet = [d for d in stats["devices"] if d["checks"] == 0]
    assert len(quiet) == 1 and quiet[0]["last_checked_at"] is None


def test_stats_rejects_out_of_range_days(db_session):
    assert client.get("/internal/stats", params={"days": 0}, headers=SECRET).status_code == 422
    assert client.get("/internal/stats", params={"days": 365}, headers=SECRET).status_code == 422
