---
name: strava
description: Load and analyze Strava activities, stats, and workouts using the Strava API
homepage: https://developers.strava.com/
metadata: {"clawdbot":{"emoji":"🏃","requires":{"bins":["curl"],"env":["STRAVA_ACCESS_TOKEN"]},"primaryEnv":"STRAVA_ACCESS_TOKEN"}}
---

# Strava Skill

Interact with Strava to load activities, analyze workouts, and track fitness data.

## Credentials

Two options (in priority order):
1. Environment variable: `STRAVA_ACCESS_TOKEN`
2. `~/.config/strava/credentials.json` with keys:
   - `STRAVA_CLIENT_ID`
   - `STRAVA_CLIENT_SECRET`
   - `STRAVA_ACCESS_TOKEN` (expires every 6h)
   - `STRAVA_REFRESH_TOKEN`

## Token Refresh

Access tokens expire every 6 hours. Refresh:
```bash
bash {baseDir}/scripts/refresh_token.sh
```

If a script returns a 401 error, run this first.

## Scripts

### `activities.sh` — Recent Activities

```bash
bash {baseDir}/scripts/activities.sh              # last 14 days
bash {baseDir}/scripts/activities.sh --days 30
bash {baseDir}/scripts/activities.sh --days 7 --count 20
```

Output: date, sport type, name, distance, time, elevation, avg HR.

### `gear-mileage.sh` — Bike & Shoe Mileage

```bash
bash {baseDir}/scripts/gear-mileage.sh            # scans 250 activities
bash {baseDir}/scripts/gear-mileage.sh --pages 10 # scan further back
```

Returns lifetime distance for all bikes (gear_id starts with `b`) and shoes (gear_id starts with `g`) in separate sections. Discovers gear via activity `gear_id` fields — requires `activity:read_all` scope only.

### `chain-wax.py` — Chain wax log

```bash
python3 {baseDir}/scripts/chain-wax.py report              # km since last wax, next due, status per bike
python3 {baseDir}/scripts/chain-wax.py report --json
python3 {baseDir}/scripts/chain-wax.py add-bike road --name "Road bike" --gear-id b1234567
python3 {baseDir}/scripts/chain-wax.py add-bike partner --name "Partner's bike" --manual --odometer 120
python3 {baseDir}/scripts/chain-wax.py log road --product "Hot wax" --degreased      # today, live odometer
python3 {baseDir}/scripts/chain-wax.py log road --odometer 1500 --date 2026-03-01 --interval 450-500
python3 {baseDir}/scripts/chain-wax.py set-odometer partner 180                     # manual bikes only
```

Keeps `data/chain-wax.json` (see `data/chain-wax.example.json`; git-ignored). Strava bikes read their lifetime distance from `/gear/{id}` (indoor rides included, since a chain wears on the trainer); manual bikes use the odometer you give, and `report` flags readings older than 30 days. The due range `[min, max]` km is fixed when a wax is logged: hot wax defaults to 150-250 km for the first re-wax and 450-500 km after that, drip lube to 200-300 km, or pass `--interval MIN-MAX`. Status: `OK`, `DUE SOON` (within the last 10% before `min`), `DUE` (between `min` and `max`), `OVERDUE` (past `max`). Exit code 2 means a Strava odometer could not be read. Find gear ids with `gear-mileage.sh`. Standard library only.

### `shoe-mileage.sh` — Shoes Only (legacy)

```bash
bash {baseDir}/scripts/shoe-mileage.sh            # scans 250 activities
```

Shoes only. Use `gear-mileage.sh` for both bikes and shoes.

### `athlete-stats.sh` — All-Time Totals

```bash
bash {baseDir}/scripts/athlete-stats.sh
```

Returns cumulative all-time and YTD totals for Run, Ride, Swim (activity count, distance, time, elevation).

## Inline API Calls

For one-off queries, use Python directly (credentials auto-loaded):

### Activity Detail
```python
import json, urllib.request, os

token = os.environ.get("STRAVA_ACCESS_TOKEN")
if not token:
    path = os.path.expanduser("~/.config/strava/credentials.json")
    if os.path.exists(path):
        with open(path) as f:
            token = json.load(f)["STRAVA_ACCESS_TOKEN"]

def strava(path):
    req = urllib.request.Request(f"https://www.strava.com/api/v3{path}",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# Full activity detail
activity = strava("/activities/ACTIVITY_ID")

# Lap splits
laps = strava("/activities/ACTIVITY_ID/laps")

# Time-series streams (HR, pace, cadence, power, altitude)
streams = strava("/activities/ACTIVITY_ID/streams?keys=heartrate,velocity_smooth,cadence,watts,altitude")

# Athlete HR/power zones
zones = strava("/athlete/zones")

# Athlete profile
athlete = strava("/athlete")

# All-time stats
stats = strava(f"/athletes/{athlete['id']}/stats")
```

## Common Data Fields

Activity objects include:
- `name`, `sport_type`, `start_date_local`
- `distance` (meters), `moving_time` (seconds), `elapsed_time` (seconds)
- `total_elevation_gain` (meters)
- `average_speed`, `max_speed` (m/s)
- `average_heartrate`, `max_heartrate` (bpm)
- `average_watts`, `weighted_average_watts` (if power meter)
- `gear_id` — gear used (shoes for runs, bike for rides)

## Rate Limits

- 200 requests per 15 minutes
- 2,000 requests per day

## Setup (first time)

1. Go to https://www.strava.com/settings/api — create an app
2. Authorize with `activity:read_all` scope
3. Exchange code for tokens via OAuth
4. Save to `~/.config/strava/credentials.json`
