"""Alert statistics, written as plain SQL that runs on both Postgres and SQLite."""

from datetime import timedelta

from sqlalchemy import DateTime, bindparam, text
from sqlalchemy.orm import Session

from .models import utcnow

# Typed so SQLAlchemy stores and compares timestamps in the same format on every database.
_since = bindparam("since", type_=DateTime(timezone=True))

TOTALS_SQL = text(
    """
    SELECT
        (SELECT COUNT(*) FROM devices) AS registered_devices,
        COUNT(h.id) AS checks,
        COALESCE(SUM(CASE WHEN h.notified THEN 1 ELSE 0 END), 0) AS alerts_sent,
        MAX(h.aqi) AS worst_aqi
    FROM alert_history h
    WHERE h.checked_at >= :since
    """
).bindparams(_since)

BY_RISK_LEVEL_SQL = text(
    """
    SELECT h.risk_level, COUNT(*) AS checks, ROUND(AVG(h.aqi), 1) AS avg_aqi
    FROM alert_history h
    WHERE h.checked_at >= :since
    GROUP BY h.risk_level
    ORDER BY checks DESC, h.risk_level
    """
).bindparams(_since)

BY_POLLUTANT_SQL = text(
    """
    SELECT h.dominant_pollutant AS pollutant, COUNT(*) AS checks, MAX(h.aqi) AS worst_aqi
    FROM alert_history h
    WHERE h.checked_at >= :since
    GROUP BY h.dominant_pollutant
    ORDER BY checks DESC, pollutant
    """
).bindparams(_since)

# Every registered device, including ones with no readings in the window (LEFT JOIN).
# Push tokens and locations are deliberately left out.
DEVICES_SQL = text(
    """
    SELECT
        d.id AS device_id,
        COUNT(h.id) AS checks,
        COALESCE(SUM(CASE WHEN h.notified THEN 1 ELSE 0 END), 0) AS alerts_sent,
        MAX(h.aqi) AS worst_aqi,
        MAX(h.checked_at) AS last_checked_at
    FROM devices d
    LEFT JOIN alert_history h ON h.device_id = d.id AND h.checked_at >= :since
    GROUP BY d.id
    ORDER BY alerts_sent DESC, worst_aqi DESC, d.id
    """
).bindparams(_since)


def _rows(db, statement, since):
    return [dict(row) for row in db.execute(statement, {"since": since}).mappings()]


def alert_stats(db: Session, days: int):
    since = utcnow() - timedelta(days=days)
    totals = dict(db.execute(TOTALS_SQL, {"since": since}).mappings().one())
    devices = _rows(db, DEVICES_SQL, since)
    for device in devices:
        # SQLite returns MAX() of a timestamp as a plain string; Postgres returns a datetime.
        if device["last_checked_at"] is not None and not isinstance(device["last_checked_at"], str):
            device["last_checked_at"] = device["last_checked_at"].isoformat()
    return {
        "days": days,
        "since": since.isoformat(),
        **totals,
        "by_risk_level": _rows(db, BY_RISK_LEVEL_SQL, since),
        "by_pollutant": _rows(db, BY_POLLUTANT_SQL, since),
        "devices": devices,
    }
