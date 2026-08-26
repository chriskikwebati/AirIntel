import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .aqi_client import AirNowError, fetch_observations
from .risk import assess_asthma_risk

app = FastAPI(title="AirIntel")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/aqi-risk")
def get_aqi_risk(lat: float = Query(...), lon: float = Query(...)):
    try:
        observations = fetch_observations(lat, lon)
    except AirNowError as e:
        raise HTTPException(status_code=502, detail=str(e))

    risk = assess_asthma_risk(observations)
    return {"lat": lat, "lon": lon, **risk}
