from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, func

from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    push_token = Column(String, unique=True, nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    last_notified_risk_level = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AlertHistory(Base):
    """One row per device per alert check: the reading taken and whether a push was sent."""

    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True)
    # Keep the history when a device unregisters, but drop the link to it.
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    checked_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    aqi = Column(Integer, nullable=False)
    category_name = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    dominant_pollutant = Column(String, nullable=False)
    notified = Column(Boolean, nullable=False, default=False)
