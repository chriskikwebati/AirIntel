# AirIntel

Web app that checks whether your current location presents an asthma risk, based on AQI.

## Backend

```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Requires an `AIRNOW_API_KEY` in a `.env` file at the repo root (see `.env.example`).

## Frontend

```
cd frontend
npm install
npm run dev
```
