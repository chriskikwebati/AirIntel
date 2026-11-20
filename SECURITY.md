# Security

## Reporting a problem

If you find a security issue, please don't open a public issue. Use GitHub's **Report a vulnerability** button on the Security tab of this repository so it can be fixed before it is made public.

## How AirIntel protects itself

**Secrets**
- Secrets (database URL, alert secret, WAQI token) are only stored in Render and GitHub Actions secrets, never in the code. `.env` is ignored by git.
- The internal endpoints (`/internal/alerts/check`, `/internal/stats`) require the `X-Alert-Secret` header. It is compared in constant time (`hmac.compare_digest`) so response timing can't reveal the secret. If no secret is configured, these endpoints stay locked.

**Input**
- Coordinates must be real (latitude −90 to 90, longitude −180 to 180), and push tokens must match Expo's format. Anything else is rejected with `422` before it reaches the database.
- All database access goes through SQLAlchemy with bound parameters, including the hand-written stats queries, so input is never pasted into SQL.

**Abuse**
- Rate limits per IP: 30 risk lookups and 10 alert registrations or unregistrations per minute. Behind Render's or Cloud Run's proxy, the limit uses the address the proxy recorded, not one the client could fake.
- Browser access (CORS) is limited to the origins in `ALLOWED_ORIGINS`.

**Leaking information**
- Errors from upstream services are logged but not returned to callers: a failed lookup only says "temporarily unavailable."
- The stats endpoint returns device IDs and counts only, never push tokens or locations.
- Responses include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`.

**Runtime**
- The Docker image runs as an unprivileged user, not root.

**Data kept**
- Alert history is deleted after 90 days. Devices that Expo reports as unregistered are deleted automatically.

**Checked on every push (CI)**
- Bandit: static analysis of the Python code.
- pip-audit and npm audit: known vulnerabilities in dependencies.
- Dependabot opens pull requests for dependency and GitHub Actions updates.
