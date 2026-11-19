# AirIntel

AirIntel tells people with asthma whether the air where they are right now is a risk. It reads the current Air Quality Index (AQI) for your location, finds the worst pollutant, and turns it into a plain asthma-risk level with advice. The mobile app can also send a push alert when the air near you turns unhealthy.

| Part | Folder | Tech | Where it runs |
|---|---|---|---|
| Backend API | `backend/` | Python, FastAPI | Render (free web service): `https://airintel-backend-c61b.onrender.com` |
| Mobile app | `mobile/` | Expo / React Native | Expo Go on your phone |
| Web app | `frontend/` | React, Vite | Locally |
| Alerts database | — | Postgres | Neon (free plan) |

## How it works

1. The app gets your location and calls `GET /api/aqi-risk?lat=…&lon=…`.
2. The backend fetches the current US AQI for each pollutant (PM2.5, PM10, ozone, NO2, SO2, CO) from [Open-Meteo](https://open-meteo.com/en/docs/air-quality-api). No API key needed.
3. The worst pollutant sets the EPA category (Good → Hazardous), which maps to an asthma risk level: `low`, `moderate`, `high`, `very_high` or `severe`, plus advice.
4. For alerts, the mobile app registers its push token and location. A scheduled GitHub Actions job asks the backend every 30 minutes to check each registered device and send an Expo push notification when risk becomes `high` or worse.

**Staying up:** Open-Meteo is retried once. If it still fails and `WAQI_TOKEN` is set, the backend falls back to [WAQI](https://aqicn.org/api/). If every source fails, the API returns `502` rather than crashing.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/aqi-risk?lat=&lon=` | Current AQI and asthma risk for a location |
| `GET` | `/healthz` | Liveness check (used by Render) |
| `POST` | `/api/alerts/register` | Save a device's push token and location |
| `POST` | `/api/alerts/unregister` | Remove a device |
| `POST` | `/internal/alerts/check` | Run the alert check; needs the `X-Alert-Secret` header |

The alert endpoints return `503` if no database is configured.

## Run it locally

### Backend

```
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The AQI endpoint works with no configuration. For alerts, copy `.env.example` to `.env` at the repo root and fill in `DATABASE_URL` and `ALERT_CRON_SECRET`.

### Web app

```
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173` and calls a backend on `http://localhost:8000`. To use the live backend instead:

```
VITE_API_BASE_URL=https://airintel-backend-c61b.onrender.com npm run dev
```

Your browser will ask for location permission. Use `localhost`, not your Mac's network address: browsers block location on plain `http` pages.

### Mobile app

```
cd mobile
npm install
npx expo start --tunnel
```

Scan the QR code with Expo Go. The app reads the backend address from `EXPO_PUBLIC_API_BASE_URL`, so create `mobile/.env` containing:

```
EXPO_PUBLIC_API_BASE_URL=https://airintel-backend-c61b.onrender.com
```

This project uses Expo SDK 57. See `mobile/AGENTS.md` before changing mobile code.

## Tests

```
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

The tests cover the AQI-to-risk mapping, the retry and fallback logic, and the API responses. They mock all network calls, so they run offline.

## Deployment

The backend deploys to Render from `render.yaml` at the repo root. Pushing to `main` redeploys it.

Environment variables on Render:

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | For alerts | Neon connection string. `postgres://` URLs are accepted too. |
| `ALERT_CRON_SECRET` | For alerts | Must exactly match the GitHub Actions secret of the same name. |
| `WAQI_TOKEN` | No | Turns on the backup AQI source. [Free token](https://aqicn.org/data-platform/token/). |
| `ALLOWED_ORIGINS` | No | Comma-separated origins allowed to call the API from a browser. Defaults to `http://localhost:5173`. |

> **Don't use Render's free Postgres.** It expires 30 days after creation and is then deleted, which silently broke alerts once. Neon's free plan has no time limit. The backend reconnects automatically after Neon's idle sleep.

Python is pinned to 3.12.5 (`backend/.python-version`) and every backend dependency is pinned in `requirements.txt`, so a new package release can't break a deploy.

## Monitoring

GitHub Actions workflows in `.github/workflows/`:

| Workflow | When | What it checks |
|---|---|---|
| `tests.yml` | Every push and pull request | Backend tests pass |
| `health-check.yml` | Daily at 13:00 UTC | The live backend returns a real risk assessment |
| `alert-check.yml` | Every 30 minutes | Runs the push alert check |

These need the repository secrets `BACKEND_URL` and `ALERT_CRON_SECRET`. A red run means something needs attention, so keep GitHub's email notifications for failed workflows turned on.
