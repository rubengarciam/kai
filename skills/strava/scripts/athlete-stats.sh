#!/usr/bin/env bash
# Show all-time Strava athlete statistics (cumulative run/ride/swim totals).
#
# Usage: bash athlete-stats.sh
#
# Credentials are read from (in priority order):
#   1. Environment variables (STRAVA_ACCESS_TOKEN)
#   2. ~/.config/strava/credentials.json

set -e

python3 - <<'PYEOF'
import json, os, sys, urllib.request

token = os.environ.get("STRAVA_ACCESS_TOKEN")
if not token:
    creds_path = os.path.expanduser("~/.config/strava/credentials.json")
    if os.path.exists(creds_path):
        with open(creds_path) as f:
            token = json.load(f).get("STRAVA_ACCESS_TOKEN")

if not token:
    print("Error: STRAVA_ACCESS_TOKEN not set.", file=sys.stderr)
    sys.exit(1)

def api_get(path):
    req = urllib.request.Request(
        f"https://www.strava.com/api/v3{path}",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

athlete = api_get("/athlete")
athlete_id = athlete["id"]
stats = api_get(f"/athletes/{athlete_id}/stats")

def fmt_dist(m):
    return f"{m/1000:.1f}km" if m else "—"

def fmt_time(s):
    h, rem = divmod(int(s), 3600)
    m = rem // 60
    return f"{h}h{m:02d}m" if h else f"{m}m"

def fmt_elev(m):
    return f"{m:.0f}m" if m else "—"

sports = [
    ("Run",  stats.get("all_run_totals", {})),
    ("Ride", stats.get("all_ride_totals", {})),
    ("Swim", stats.get("all_swim_totals", {})),
]

header = f"{'Sport':<6}  {'Activities':>10}  {'Distance':>10}  {'Time':>9}  {'Elev':>8}"
divider = "-" * len(header)
print(header)
print(divider)

for sport, totals in sports:
    count = totals.get("count", 0)
    dist  = fmt_dist(totals.get("distance", 0))
    time  = fmt_time(totals.get("moving_time", 0))
    elev  = fmt_elev(totals.get("elevation_gain", 0))
    print(f"{sport:<6}  {count:>10}  {dist:>10}  {time:>9}  {elev:>8}")

print(divider)

# Recent 4-week and YTD
print()
print("Recent:")
for label, key in [("YTD Run", "ytd_run_totals"), ("YTD Ride", "ytd_ride_totals"), ("YTD Swim", "ytd_swim_totals")]:
    t = stats.get(key, {})
    if t.get("count"):
        print(f"  {label:<10}  {t['count']} activities  {fmt_dist(t.get('distance',0))}  {fmt_time(t.get('moving_time',0))}")
PYEOF
