import requests
from sqlalchemy.orm import Session

from .aqi_client import AirNowError, fetch_observations
from .models import Device
from .risk import assess_asthma_risk

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
ALERT_RISK_LEVELS = {"high", "very_high", "severe"}


def send_expo_push(push_token, title, body):
    requests.post(
        EXPO_PUSH_URL,
        json={"to": push_token, "title": title, "body": body},
        timeout=10,
    )


def run_alert_check(db: Session):
    for device in db.query(Device).all():
        try:
            observations = fetch_observations(device.lat, device.lon)
            risk = assess_asthma_risk(observations)
        except (AirNowError, requests.RequestException):
            continue

        risk_level = risk["risk_level"]
        is_risky = risk_level in ALERT_RISK_LEVELS
        was_already_notified = device.last_notified_risk_level in ALERT_RISK_LEVELS

        if is_risky and not was_already_notified:
            send_expo_push(
                device.push_token,
                "AirIntel Alert",
                f"Air quality near you is {risk['category_name']} (AQI {risk['aqi']}) — {risk['message']}",
            )
            device.last_notified_risk_level = risk_level
        elif not is_risky:
            device.last_notified_risk_level = None

    db.commit()
