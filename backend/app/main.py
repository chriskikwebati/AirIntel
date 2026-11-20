import hmac
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from . import db as database
from .aqi_client import AirQualityError, fetch_observations
from .db import get_db
from .logging_config import configure_logging, request_id_var
from .migrate import upgrade_database
from .models import Device
from .push import run_alert_check
from .risk import assess_asthma_risk
from .stats import alert_stats

configure_logging()
logger = logging.getLogger("airintel.api")

# Expo push tokens look like ExponentPushToken[xxxxxxxx] (older ones start with ExpoPushToken).
# Bandit mistakes this for a hard-coded password because of the name; it is only a format.
PUSH_TOKEN_PATTERN = r"^Expo(nent)?PushToken\[[A-Za-z0-9_-]{1,200}\]$"  # nosec B105
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def behind_proxy():
    # Render sets RENDER and Cloud Run sets K_SERVICE; TRUST_PROXY overrides either way.
    default = "true" if (os.getenv("RENDER") or os.getenv("K_SERVICE")) else "false"
    return os.getenv("TRUST_PROXY", default).lower() == "true"


def client_ip(request: Request):
    """The caller's IP, used as the rate-limit key.

    Behind a proxy (Render, Cloud Run) every request arrives from the proxy, so we use the
    right-most X-Forwarded-For entry instead: the one the proxy added itself. Entries to its
    left are supplied by the client and can be faked.
    """
    if behind_proxy():
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(
    key_func=client_ip,
    enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false",
)

@asynccontextmanager
async def lifespan(_app):
    # Run migrations here rather than only in a start script, so the schema is current
    # however the app is launched (Render, Docker, or plain uvicorn).
    if database.engine is not None:
        upgrade_database()
    yield


app = FastAPI(title="AirIntel", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Tag every request with an ID, log its outcome and timing, and add basic security headers."""
    incoming = request.headers.get("x-request-id", "")
    request_id = incoming if REQUEST_ID_PATTERN.match(incoming) else uuid.uuid4().hex
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        logger.info(
            "request",
            extra={
                "fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                }
            },
        )
    except Exception:
        logger.exception("Unhandled error", extra={"fields": {"method": request.method, "path": request.url.path}})
        raise
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def require_alert_secret(x_alert_secret: str | None = Header(default=None)):
    expected = os.getenv("ALERT_CRON_SECRET")
    # compare_digest takes the same time however much of the secret matches, so response
    # timing can't be used to guess it one character at a time.
    if not expected or not x_alert_secret or not hmac.compare_digest(x_alert_secret.encode(), expected.encode()):
        logger.warning("Rejected request with invalid alert secret")
        raise HTTPException(status_code=401, detail="Invalid alert secret")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/aqi-risk")
@limiter.limit("30/minute")
def get_aqi_risk(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    try:
        observations = fetch_observations(lat, lon)
    except AirQualityError as e:
        logger.error("All AQI sources failed", extra={"fields": {"error": str(e)}})
        raise HTTPException(status_code=502, detail="Air quality data is temporarily unavailable")

    risk = assess_asthma_risk(observations)
    return {"lat": lat, "lon": lon, **risk}


class AlertRegistration(BaseModel):
    push_token: str = Field(pattern=PUSH_TOKEN_PATTERN)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class AlertUnregistration(BaseModel):
    push_token: str = Field(pattern=PUSH_TOKEN_PATTERN)


@app.post("/api/alerts/register")
@limiter.limit("10/minute")
def register_alert(request: Request, body: AlertRegistration, db: Session = Depends(get_db)):
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
@limiter.limit("10/minute")
def unregister_alert(request: Request, body: AlertUnregistration, db: Session = Depends(get_db)):
    db.query(Device).filter(Device.push_token == body.push_token).delete()
    db.commit()
    return {"status": "unregistered"}


@app.post("/internal/alerts/check", dependencies=[Depends(require_alert_secret)])
def check_alerts(db: Session = Depends(get_db)):
    return {"status": "checked", **run_alert_check(db)}


@app.get("/internal/stats", dependencies=[Depends(require_alert_secret)])
def get_stats(days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db)):
    return alert_stats(db, days)
