#!/usr/bin/env bash
# List recent Strava activities.
#
# Usage: bash activities.sh [--days N] [--count N]
#
# Defaults: last 14 days, up to 50 activities.
#
# Credentials are read from (in priority order):
#   1. Environment variables (STRAVA_ACCESS_TOKEN)
#   2. ~/.config/strava/credentials.json

set -e

DAYS=14
COUNT=50

while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)  DAYS="$2";  shift 2 ;;
    --count) COUNT="$2"; shift 2 ;;
    *) echo "Usage: $0 [--days N] [--count N]"; exit 1 ;;
  esac
done

python3 - "$DAYS" "$COUNT" <<'PYEOF'
import json, os, sys, urllib.request, time
from datetime import datetime, timezone, timedelta

days  = int(sys.argv[1])
count = int(sys.argv[2])

# --- Load credentials ---
token = os.environ.get("STRAVA_ACCESS_TOKEN")
if not token:
    creds_path = os.path.expanduser("~/.config/strava/credentials.json")
    if os.path.exists(creds_path):
        with open(creds_path) as f:
            token = json.load(f).get("STRAVA_ACCESS_TOKEN")

if not token:
    print("Error: STRAVA_ACCESS_TOKEN not set.", file=sys.stderr)
    print("Run: bash refresh_token.sh", file=sys.stderr)
    sys.exit(1)

after = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())

req = urllib.request.Request(
    f"https://www.strava.com/api/v3/athlete/activities?per_page={count}&after={after}",
    headers={"Authorization": f"Bearer {token}"}
)
with urllib.request.urlopen(req) as resp:
    activities = json.loads(resp.read())

if not activities:
    print(f"No activities in the last {days} days.")
    sys.exit(0)

# Sort oldest first
activities.sort(key=lambda a: a["start_date"])

col_name = max((len(a.get("name","")) for a in activities), default=4)
col_name = min(max(col_name, 4), 35)

header = f"{'Date':<10}  {'Type':<8}  {'Name':<{col_name}}  {'Dist':>7}  {'Time':>7}  {'Elev':>6}  {'HR':>4}"
print(header)
print("-" * len(header))

for a in activities:
    date  = a["start_date_local"][:10]
    atype = a.get("sport_type", a.get("type", "?"))[:8]
    name  = a.get("name", "")[:col_name]
    dist  = a.get("distance", 0)
    dist_str = f"{dist/1000:.1f}km" if dist else "—"
    secs  = a.get("moving_time", 0)
    h, m  = divmod(secs // 60, 60)
    time_str = f"{h}h{m:02d}m" if h else f"{m}m"
    elev  = a.get("total_elevation_gain")
    elev_str = f"{elev:.0f}m" if elev else "—"
    hr    = a.get("average_heartrate")
    hr_str = f"{hr:.0f}" if hr else "—"
    print(f"{date:<10}  {atype:<8}  {name:<{col_name}}  {dist_str:>7}  {time_str:>7}  {elev_str:>6}  {hr_str:>4}")

print("-" * len(header))
print(f"{len(activities)} activities in the last {days} days")
PYEOF
