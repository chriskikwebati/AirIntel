# AirIntel

Web app that checks whether your current location presents an asthma risk, based on AQI.

## Backend

```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

AQI data comes from the [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), which needs no API key. If Open-Meteo fails twice in a row, the backend falls back to [WAQI](https://aqicn.org/api/) when `WAQI_TOKEN` is set (free token).

Run the tests:

```
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

GitHub Actions runs these tests on every push, and a daily job checks that the live backend (`BACKEND_URL` secret) still returns a risk assessment.

Alert endpoints require `DATABASE_URL` and `ALERT_CRON_SECRET` in a `.env` file at the repo root (see `.env.example`).

## Frontend

```
cd frontend
npm install
npm run dev
```
