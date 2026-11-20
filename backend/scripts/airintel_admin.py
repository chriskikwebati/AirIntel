#!/usr/bin/env python3
"""Command-line tool for checking on a running AirIntel backend.

Examples:
    python scripts/airintel_admin.py health
    python scripts/airintel_admin.py risk 38.9 -77.0
    python scripts/airintel_admin.py stats --days 30
    python scripts/airintel_admin.py check-alerts

Reads BACKEND_URL (default http://localhost:8000) and, for stats and check-alerts,
ALERT_CRON_SECRET from the environment.
"""

import argparse
import json
import os
import sys
import time

import requests

TIMEOUT = 90  # free Render instances can take ~a minute to wake up


def backend_url():
    return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


def secret_headers():
    secret = os.getenv("ALERT_CRON_SECRET")
    if not secret:
        sys.exit("ALERT_CRON_SECRET is not set")
    return {"X-Alert-Secret": secret}


def call(method, path, **kwargs):
    url = backend_url() + path
    start = time.perf_counter()
    try:
        response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as e:
        sys.exit(f"Could not reach {url}: {e}")
    elapsed = time.perf_counter() - start
    request_id = response.headers.get("X-Request-ID", "-")
    if not response.ok:
        sys.exit(f"{method} {path} failed: HTTP {response.status_code} (request id {request_id})\n{response.text}")
    return response.json(), elapsed, request_id


def table(rows, columns):
    if not rows:
        print("  (none)")
        return
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    print("  " + "  ".join(c.ljust(widths[c]) for c in columns))
    for row in rows:
        print("  " + "  ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))


def cmd_health(_args):
    body, elapsed, _ = call("GET", "/healthz")
    print(f"{backend_url()} is up ({body['status']}, {elapsed:.2f}s)")


def cmd_risk(args):
    body, elapsed, request_id = call("GET", "/api/aqi-risk", params={"lat": args.lat, "lon": args.lon})
    print(f"AQI {body['aqi']} ({body['category_name']}), main pollutant {body['dominant_pollutant']}")
    print(f"Asthma risk: {body['risk_level']}. {body['message']}")
    print(f"[{elapsed:.2f}s, request id {request_id}]")


def cmd_check_alerts(_args):
    body, elapsed, request_id = call("POST", "/internal/alerts/check", headers=secret_headers())
    body.pop("status", None)
    print("Alert check finished: " + ", ".join(f"{k}={v}" for k, v in body.items()))
    print(f"[{elapsed:.2f}s, request id {request_id}]")


def cmd_stats(args):
    stats, _, _ = call("GET", "/internal/stats", params={"days": args.days}, headers=secret_headers())
    if args.json:
        print(json.dumps(stats, indent=2))
        return
    print(f"Last {stats['days']} days")
    print(f"  Registered devices: {stats['registered_devices']}")
    print(f"  Readings taken:     {stats['checks']}")
    print(f"  Alerts sent:        {stats['alerts_sent']}")
    print(f"  Worst AQI:          {stats['worst_aqi'] if stats['worst_aqi'] is not None else '-'}")
    print("\nBy risk level")
    table(stats["by_risk_level"], ["risk_level", "checks", "avg_aqi"])
    print("\nBy main pollutant")
    table(stats["by_pollutant"], ["pollutant", "checks", "worst_aqi"])
    print("\nDevices")
    table(stats["devices"], ["device_id", "checks", "alerts_sent", "worst_aqi", "last_checked_at"])


def main():
    parser = argparse.ArgumentParser(description="Check on a running AirIntel backend.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="check the backend is up").set_defaults(func=cmd_health)

    risk = sub.add_parser("risk", help="look up the asthma risk for a location")
    risk.add_argument("lat", type=float)
    risk.add_argument("lon", type=float)
    risk.set_defaults(func=cmd_risk)

    sub.add_parser("check-alerts", help="run the push alert check now").set_defaults(func=cmd_check_alerts)

    stats = sub.add_parser("stats", help="show alert statistics")
    stats.add_argument("--days", type=int, default=7, help="how far back to look (1-90, default 7)")
    stats.add_argument("--json", action="store_true", help="print the raw JSON")
    stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
