# AirIntel runbook

How to diagnose and fix the problems AirIntel is most likely to have. Each entry gives the symptom, how to confirm the cause, and the fix.

## Before you start

**Find the logs.** Render dashboard → `airintel-backend` → **Logs**. Every line is JSON, and every request line has a `request_id`, `path`, `status` and `duration_ms`.

**Follow one request.** Every response carries an `X-Request-ID` header. The admin tool prints it, and so does a failed health check. Search the logs for that ID to see everything that happened during that request.

**Check the backend from your terminal:**

```
cd backend
export BACKEND_URL=https://airintel-backend-c61b.onrender.com
export ALERT_CRON_SECRET=...        # same value as on Render
python scripts/airintel_admin.py health
python scripts/airintel_admin.py risk 38.9 -77.0
python scripts/airintel_admin.py stats --days 7
```

**Remember the free plan sleeps.** After about 15 idle minutes, Render stops the backend. The next request takes 30 to 60 seconds while it starts again. A single slow first response is normal and not a problem.

---

## "Live health check failing" issue opened

The daily workflow couldn't get a valid risk assessment from the live API. The issue contains the response it got.

1. Run `python scripts/airintel_admin.py health`.
   - **It can't connect, or it times out after 90 seconds:** the service is down. In Render, check **Events** for a failed deploy or a crash. If the last deploy failed, its build log shows why. Fix the cause, or roll back with **Manual Deploy → Deploy a previous commit**.
   - **It's up:** go to step 2.
2. Run `python scripts/airintel_admin.py risk 40.7 -74.0`.
   - **HTTP 502:** see [API returns 502](#api-returns-502).
   - **It works:** the failure was temporary, probably the backend waking up. The issue closes itself after the next successful run, or you can rerun the workflow from the Actions tab.

## "Push alert check failing" issue opened

The every-30-minutes workflow couldn't run the alert check. Read the status code in the issue:

| Status | Meaning | Fix |
|---|---|---|
| `401` | The secrets don't match | `ALERT_CRON_SECRET` must be exactly the same on Render and in GitHub (**Settings → Secrets and variables → Actions**). Watch for a trailing space or newline. |
| `503` | No database configured | `DATABASE_URL` is missing on Render. See [API returns 503](#api-returns-503). |
| `500` | The check crashed | Search the logs for `"level": "ERROR"` around the time of the run. |
| Timeout or no response | Backend down or asleep for too long | Same as the first step of the health check entry above. |

## Users say alerts aren't arriving

1. Run `python scripts/airintel_admin.py check-alerts` and read the summary:
   - **`devices=0`:** nobody is registered. Make sure the app successfully called `/api/alerts/register`; a `422` in the logs means it sent a malformed token or location.
   - **`aqi_failures` above 0:** air quality lookups are failing for some locations. Search the logs for `AQI lookup failed for device`.
   - **`push_failures` above 0:** Expo rejected or didn't accept the push. Search the logs for `Push notification failed` to see Expo's message. These devices are retried on the next run.
   - **`removed` above 0:** Expo reported those tokens as `DeviceNotRegistered` (usually the app was uninstalled), so the devices were deleted. This is expected.
2. **Everything looks fine but nothing was sent:** alerts only go out when the risk becomes `high` or worse, and only once until the air clears. Run `stats` to see the recent risk levels per device. If none reached `high`, the system is working as intended.
3. Make sure the **AQI alert check** workflow is actually running in the Actions tab. GitHub can pause scheduled workflows in a public repository after 60 days with no commits. Re-enable it there.

## API returns 502

Every air quality source failed: Open-Meteo twice, then WAQI if it's configured. The response says only "temporarily unavailable"; the logs have the details.

1. Search the logs for `AQI source` warnings and `All AQI sources failed` errors.
2. Check Open-Meteo directly: `curl "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=40.7&longitude=-74&current=us_aqi"`.
3. If Open-Meteo is down and `WAQI_TOKEN` isn't set on Render, set it ([free token](https://aqicn.org/data-platform/token/)) to turn on the backup source.

## API returns 503

The alert endpoints need a database. `DATABASE_URL` is unset or the database is unreachable.

1. Check `DATABASE_URL` in Render → **Environment**. It must be the Neon connection string.
2. Check that the database still exists in the Neon console. (This is why we don't use Render's free Postgres: it's deleted after 30 days.)
3. Neon sleeps when idle; the backend reconnects on its own, so a single 503 right after a quiet period doesn't need any action.

## API returns 429

A caller went over the rate limit (30 risk lookups or 10 alert registrations per minute per IP address). This is intended. If real users hit it:

- Check that the app isn't calling in a loop. The request logs show the path and timing of each call.
- If you're testing locally and the limit gets in your way, set `RATE_LIMIT_ENABLED=false`. Never set this in production.

## Backend won't start after a deploy

Database migrations run when the app starts. If one fails, the app stops and the Render log shows an `alembic` error.

1. Read the error. Common causes are a database that can't be reached, or a migration that conflicts with a manual change made to the database.
2. Roll back to the previous deploy in Render so users aren't affected.
3. Reproduce locally with `docker compose up --build`, which runs the same migrations against a fresh Postgres.

## Checking the database directly

Run `python scripts/airintel_admin.py stats --days 30` for totals, a breakdown by risk level and main pollutant, and per-device history. For anything else, connect with the Neon SQL editor. The tables are `devices` and `alert_history` (90 days of readings, one row per device per check).
