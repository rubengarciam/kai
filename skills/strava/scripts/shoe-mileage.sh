#!/usr/bin/env bash
# Show running shoe mileage from Strava.
#
# Usage: bash shoe-mileage.sh [--pages N]
#
# Scans recent activities to discover shoe gear IDs (gear IDs starting with 'g'),
# then calls /gear/{id} for each to get the accurate total lifetime distance.
# Defaults to scanning 5 pages (250 activities). Pass --pages N to scan more.
#
# Note: Strava's /athlete endpoint requires profile:read_all scope to list gear.
# This script works around that by discovering shoes via activity gear_id fields.
#
# Credentials are read from (in priority order):
#   1. Environment variables (STRAVA_ACCESS_TOKEN)
#   2. ~/.config/strava/credentials.json

set -e

PAGES=5

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pages) PAGES="$2"; shift 2 ;;
    *) echo "Usage: $0 [--pages N]"; exit 1 ;;
  esac
done

python3 - "$PAGES" <<'PYEOF'
import json, os, sys, urllib.request

pages = int(sys.argv[1])

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

def api_get(path):
    req = urllib.request.Request(
        f"https://www.strava.com/api/v3{path}",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# --- Scan activity pages to discover shoe gear IDs ---
print(f"Scanning {pages} pages of activities for shoe gear IDs...", file=sys.stderr)

seen = set()
shoe_ids = []

for page in range(1, pages + 1):
    activities = api_get(f"/athlete/activities?per_page=50&page={page}")
    if not activities:
        break
    for act in activities:
        gear_id = act.get("gear_id")
        if gear_id and gear_id.startswith("g") and gear_id not in seen:
            shoe_ids.append(gear_id)
            seen.add(gear_id)

if not shoe_ids:
    print("No shoes found in recent activities.")
    print(f"Try scanning more history: bash shoe-mileage.sh --pages 10")
    sys.exit(0)

print(f"Found {len(shoe_ids)} shoe(s). Fetching mileage...", file=sys.stderr)

# --- Fetch gear details for each shoe ---
gear_details = []
for gear_id in shoe_ids:
    gear = api_get(f"/gear/{gear_id}")
    gear_details.append(gear)

# Sort by distance descending
gear_details.sort(key=lambda g: g.get("distance", 0), reverse=True)

# --- Print table ---
col_name = max((len(g.get("name", "")) for g in gear_details), default=4)
col_name = max(col_name, 4)

header = f"{'Shoe':<{col_name}}  {'Distance':>10}  Status"
divider = "-" * len(header)
print(header)
print(divider)

for g in gear_details:
    name = g.get("name", g.get("id", "?"))
    dist_km = g.get("distance", 0) / 1000
    status = "retired" if g.get("retired") else "active"
    print(f"{name:<{col_name}}  {dist_km:>9.1f}km  {status}")

print(divider)
print("(Lifetime totals from Strava)")
PYEOF
