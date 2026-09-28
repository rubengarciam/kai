#!/usr/bin/env bash
# Show tyre mileage per wheelset from Strava.
#
# Usage: bash tyre-mileage.sh [--json] [--verbose]
#
# Tyres are tied to WHEELSETS (see ../data/tyres.json). For each active tyre set,
# this sums the distance of qualifying OUTDOOR rides since its fitted_date across
# the wheelset's Strava gear_ids.
#
# A ride is EXCLUDED (treated as indoor / tyres not used) when any of:
#   - type/sport_type is VirtualRide
#   - trainer flag is true
#   - it is a plain Ride with no GPS start location (indoor, no route)
# manual_include_ids / manual_exclude_ids in tyres.json override the above.
#
# Credentials are read from (in priority order):
#   1. Environment variable STRAVA_ACCESS_TOKEN
#   2. ~/.config/strava/credentials.json
#
#   --json     machine-readable output
#   --verbose  list every counted / excluded ride

set -e

JSON=0
VERBOSE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON=1; shift ;;
    --verbose) VERBOSE=1; shift ;;
    *) echo "Usage: $0 [--json] [--verbose]"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LEDGER="$SCRIPT_DIR/../data/tyres.json"
# Before v2.2 the ledger lived in the Strava skill; still honoured (with a notice) if it is the only one
LEGACY_LEDGER="$SCRIPT_DIR/../../strava/data/tyres.json"
if [ ! -f "$LEDGER" ] && [ -f "$LEGACY_LEDGER" ]; then
  echo "Note: using the tyre ledger at its old location $LEGACY_LEDGER." >&2
  echo "      Move it to $LEDGER (tyre tracking now lives in skills/gear-maintenance)." >&2
  LEDGER="$LEGACY_LEDGER"
fi
if [ ! -f "$LEDGER" ]; then
  echo "Error: no tyre ledger at $LEDGER." >&2
  echo "Copy $SCRIPT_DIR/../data/tyres.example.json to tyres.json and edit it." >&2
  exit 1
fi

python3 - "$LEDGER" "$JSON" "$VERBOSE" <<'PYEOF'
import json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone

ledger_path = sys.argv[1]
as_json = sys.argv[2] == "1"
verbose = sys.argv[3] == "1"

# --- Load credentials ---
token = os.environ.get("STRAVA_ACCESS_TOKEN")
if not token:
    creds_path = os.path.expanduser("~/.config/strava/credentials.json")
    if os.path.exists(creds_path):
        with open(creds_path) as f:
            token = json.load(f).get("STRAVA_ACCESS_TOKEN")
if not token:
    print("Error: STRAVA_ACCESS_TOKEN not set. Run: bash skills/strava/scripts/refresh_token.sh", file=sys.stderr)
    sys.exit(1)

with open(ledger_path) as f:
    ledger = json.load(f)

def api_get(path):
    req = urllib.request.Request(
        f"https://www.strava.com/api/v3{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def fetch_since(after_epoch):
    """All activities after the given epoch, following pagination."""
    out, page = [], 1
    while True:
        batch = api_get(f"/athlete/activities?after={after_epoch}&per_page=100&page={page}")
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return out

def is_indoor(act):
    """True if the ride did not use the tyres (indoor)."""
    if act.get("type") == "VirtualRide" or act.get("sport_type") == "VirtualRide":
        return True
    if act.get("trainer"):
        return True
    # plain Ride with no GPS start location -> indoor, no route
    if not act.get("start_latlng"):
        return True
    return False

wheelsets = ledger.get("wheelsets", {})
results = []

for tyre in ledger.get("tyres", []):
    if tyre.get("retired"):
        continue
    ws = wheelsets.get(tyre["wheelset"], {})
    gear_ids = set(ws.get("gear_ids", []))
    inc = set(tyre.get("manual_include_ids", []))
    exc = set(tyre.get("manual_exclude_ids", []))

    fitted = datetime.strptime(tyre["fitted_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    after_epoch = int(fitted.timestamp()) - 1

    acts = fetch_since(after_epoch)

    counted, excluded, dist_m = [], [], 0.0
    for a in acts:
        aid = a.get("id")
        # forced overrides first
        if aid in exc:
            excluded.append((a, "manual_exclude"))
            continue
        forced_in = aid in inc
        if not forced_in and a.get("gear_id") not in gear_ids:
            continue
        if not forced_in and is_indoor(a):
            excluded.append((a, "indoor"))
            continue
        dist_m += a.get("distance", 0)
        counted.append(a)

    km = dist_m / 1000
    interval = tyre.get("wear_check_interval_km", 500)
    replace_at = tyre.get("replace_at_km")
    checks_done = int(km // interval)
    next_check = (checks_done + 1) * interval

    flags = []
    # wear/cut check: within 25 km of the next 500 km boundary, or just past one
    if km >= next_check - 25:
        flags.append(f"WEAR/CUT CHECK due ~{next_check:.0f} km")
    if replace_at:
        if km >= replace_at:
            flags.append(f"REPLACE — past {replace_at:.0f} km end-of-life")
        elif km >= replace_at - 300:
            flags.append(f"replacement watch — approaching {replace_at:.0f} km")

    results.append({
        "id": tyre["id"],
        "wheelset": ws.get("name", tyre["wheelset"]),
        "usual_bike": ws.get("usual_bike", ""),
        "model": tyre.get("model", ""),
        "fitted_date": tyre["fitted_date"],
        "km": round(km, 1),
        "rides_counted": len(counted),
        "rides_excluded": len(excluded),
        "next_check_km": next_check,
        "replace_at_km": replace_at,
        "flags": flags,
        "note": tyre.get("note", ""),
        "_counted": counted,
        "_excluded": excluded,
    })

if as_json:
    for r in results:
        r.pop("_counted", None); r.pop("_excluded", None)
    print(json.dumps(results, indent=2))
    sys.exit(0)

if not results:
    print("No active tyre sets in ledger.")
    sys.exit(0)

print("TYRE MILEAGE (outdoor rides only)\n")
for r in results:
    print(f"● {r['wheelset']}  —  {r['model']}")
    print(f"  Bike: {r['usual_bike']}")
    print(f"  Fitted: {r['fitted_date']}   Mileage: {r['km']:.1f} km   "
          f"({r['rides_counted']} rides counted, {r['rides_excluded']} indoor excluded)")
    line = f"  Next wear/cut check: ~{r['next_check_km']:.0f} km"
    if r['replace_at_km']:
        line += f"   |   End-of-life target: {r['replace_at_km']:.0f} km"
    print(line)
    for fl in r["flags"]:
        print(f"  ⚠️  {fl}")
    if r["note"]:
        print(f"  ℹ️  {r['note']}")
    if verbose:
        print("    Counted:")
        for a in r["_counted"]:
            print(f"      + {a['start_date_local'][:10]}  {a.get('distance',0)/1000:6.1f}km  {a.get('name','')[:40]}")
        print("    Excluded (indoor):")
        for a, why in r["_excluded"]:
            print(f"      - {a['start_date_local'][:10]}  {a.get('distance',0)/1000:6.1f}km  [{why}]  {a.get('name','')[:34]}")
    print()

print("(Tyres tied to wheelset; indoor rides — VirtualRide, trainer, or GPS-less — excluded.)")
PYEOF
