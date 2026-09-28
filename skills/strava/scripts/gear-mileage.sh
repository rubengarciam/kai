#!/usr/bin/env bash
# Show bike and running shoe mileage from Strava.
#
# Usage: bash gear-mileage.sh [--pages N]
#
# Scans recent activities to discover gear IDs (bikes start with 'b', shoes with 'g'),
# then calls /gear/{id} for each to get accurate lifetime distance totals.
# Defaults to scanning 5 pages (250 activities). Pass --pages N to scan more.
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

# --- Scan activity pages to discover gear IDs ---
print(f"Scanning {pages} pages of activities for gear IDs...", file=sys.stderr)

seen = set()
bike_ids = []
shoe_ids = []

for page in range(1, pages + 1):
    activities = api_get(f"/athlete/activities?per_page=50&page={page}")
    if not activities:
        break
    for act in activities:
        gear_id = act.get("gear_id")
        if gear_id and gear_id not in seen:
            seen.add(gear_id)
            if gear_id.startswith("b"):
                bike_ids.append(gear_id)
            elif gear_id.startswith("g"):
                shoe_ids.append(gear_id)

print(f"Found {len(bike_ids)} bike(s), {len(shoe_ids)} shoe(s). Fetching mileage...", file=sys.stderr)

def fetch_and_sort(ids):
    items = [api_get(f"/gear/{gid}") for gid in ids]
    items.sort(key=lambda g: g.get("distance", 0), reverse=True)
    return items

def print_table(items, label):
    if not items:
        print(f"\nNo {label} found in scanned activities.")
        return
    col = max((len(g.get("name", "")) for g in items), default=4)
    col = max(col, len(label))
    header = f"{'─' * (col + 2)}{'─' * 12}{'─' * 10}"
    print(f"\n{label.upper()}")
    print(f"{'Name':<{col}}  {'Distance':>10}  Status")
    print("─" * (col + 24))
    for g in items:
        name = g.get("name", g.get("id", "?"))
        dist_km = g.get("distance", 0) / 1000
        status = "retired" if g.get("retired") else "active"
        print(f"{name:<{col}}  {dist_km:>9.1f}km  {status}")
    print("─" * (col + 24))

bikes = fetch_and_sort(bike_ids)
shoes = fetch_and_sort(shoe_ids)

print_table(bikes, "Bikes")
print_table(shoes, "Shoes")
print("\n(Lifetime totals from Strava)")
PYEOF
