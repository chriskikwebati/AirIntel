# AirIntel

Web app that checks whether your current location presents an asthma risk, based on AQI.

## Backend

```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

AQI data comes from the [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), which needs no API key.

Alert endpoints require `DATABASE_URL` and `ALERT_CRON_SECRET` in a `.env` file at the repo root (see `.env.example`).

## Frontend

```
cd frontend
npm install
npm run dev
```
