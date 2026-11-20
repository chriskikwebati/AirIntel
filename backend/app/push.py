import logging
from datetime import timedelta

import requests
from sqlalchemy.orm import Session

from .aqi_client import AirQualityError, fetch_observations
from .models import AlertHistory, Device, utcnow
from .risk import assess_asthma_risk

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
ALERT_RISK_LEVELS = {"high", "very_high", "severe"}
HISTORY_RETENTION = timedelta(days=90)


class PushError(Exception):
    pass


class DeviceNotRegistered(PushError):
    """Expo says this token is no longer valid (e.g. the app was uninstalled)."""


def send_expo_push(push_token, title, body):
    response = requests.post(
        EXPO_PUSH_URL,
        json={"to": push_token, "title": title, "body": body},
        timeout=10,
    )
    if response.status_code != 200:
        raise PushError(f"Expo push API returned status {response.status_code}")

    # Expo returns 200 even for a failed message; the real result is in data.status.
    data = (response.json() or {}).get("data") or {}
    if isinstance(data, list):
        data = data[0] if data else {}
    if data.get("status") == "error":
        if (data.get("details") or {}).get("error") == "DeviceNotRegistered":
            raise DeviceNotRegistered(data.get("message", "DeviceNotRegistered"))
        raise PushError(data.get("message", "Expo push failed"))


def run_alert_check(db: Session):
    summary = {"devices": 0, "checked": 0, "notified": 0, "aqi_failures": 0, "push_failures": 0, "removed": 0}

    for device in db.query(Device).all():
        summary["devices"] += 1
        try:
            observations = fetch_observations(device.lat, device.lon)
            risk = assess_asthma_risk(observations)
        except (AirQualityError, requests.RequestException) as e:
            summary["aqi_failures"] += 1
            logger.warning("AQI lookup failed for device", extra={"fields": {"device_id": device.id, "error": str(e)}})
            continue
        summary["checked"] += 1

        risk_level = risk["risk_level"]
        is_risky = risk_level in ALERT_RISK_LEVELS
        was_already_notified = device.last_notified_risk_level in ALERT_RISK_LEVELS
        notified = False

        if is_risky and not was_already_notified:
            try:
                send_expo_push(
                    device.push_token,
                    "AirIntel Alert",
                    f"Air quality near you is {risk['category_name']} (AQI {risk['aqi']}) — {risk['message']}",
                )
            except DeviceNotRegistered:
                summary["removed"] += 1
                logger.info("Removing unregistered device", extra={"fields": {"device_id": device.id}})
                db.delete(device)
                continue
            except (PushError, requests.RequestException, ValueError) as e:
                # Leave last_notified_risk_level unchanged so the next run tries again.
                summary["push_failures"] += 1
                logger.error("Push notification failed", extra={"fields": {"device_id": device.id, "error": str(e)}})
            else:
                notified = True
                summary["notified"] += 1
                device.last_notified_risk_level = risk_level
        elif not is_risky:
            device.last_notified_risk_level = None

        db.add(
            AlertHistory(
                device_id=device.id,
                aqi=round(risk["aqi"]),
                category_name=risk["category_name"],
                risk_level=risk_level,
                dominant_pollutant=risk["dominant_pollutant"],
                notified=notified,
            )
        )

    db.query(AlertHistory).filter(AlertHistory.checked_at < utcnow() - HISTORY_RETENTION).delete(
        synchronize_session=False
    )
    db.commit()
    logger.info("Alert check finished", extra={"fields": summary})
    return summary
