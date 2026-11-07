import os

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .aqi_client import AirQualityError, fetch_observations
from .db import Base, engine, get_db
from .models import Device
from .push import run_alert_check
from .risk import assess_asthma_risk

app = FastAPI(title="AirIntel")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

if engine:
    Base.metadata.create_all(bind=engine)


@app.get("/api/aqi-risk")
def get_aqi_risk(lat: float = Query(...), lon: float = Query(...)):
    try:
        observations = fetch_observations(lat, lon)
    except AirQualityError as e:
        raise HTTPException(status_code=502, detail=str(e))

    risk = assess_asthma_risk(observations)
    return {"lat": lat, "lon": lon, **risk}


class AlertRegistration(BaseModel):
    push_token: str
    lat: float
    lon: float


class AlertUnregistration(BaseModel):
    push_token: str


@app.post("/api/alerts/register")
def register_alert(body: AlertRegistration, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.push_token == body.push_token).first()
    if device:
        device.lat = body.lat
        device.lon = body.lon
    else:
        device = Device(push_token=body.push_token, lat=body.lat, lon=body.lon)
        db.add(device)
    db.commit()
    return {"status": "registered"}


@app.post("/api/alerts/unregister")
def unregister_alert(body: AlertUnregistration, db: Session = Depends(get_db)):
    db.query(Device).filter(Device.push_token == body.push_token).delete()
    db.commit()
    return {"status": "unregistered"}


@app.post("/internal/alerts/check")
def check_alerts(
    x_alert_secret: str = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_alert_secret or x_alert_secret != os.getenv("ALERT_CRON_SECRET"):
        raise HTTPException(status_code=401, detail="Invalid alert secret")

    run_alert_check(db)
    return {"status": "checked"}
