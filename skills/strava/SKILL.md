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
bash skills/strava/scripts/refresh_token.sh
```

If a script returns a 401 error, run this first.

## Scripts

### `activities.sh` — Recent Activities

```bash
bash skills/strava/scripts/activities.sh              # last 14 days
bash skills/strava/scripts/activities.sh --days 30
bash skills/strava/scripts/activities.sh --days 7 --count 20
```

Output: date, sport type, name, distance, time, elevation, avg HR.

### `gear-mileage.sh` — Bike & Shoe Mileage

```bash
bash skills/strava/scripts/gear-mileage.sh            # scans 250 activities
bash skills/strava/scripts/gear-mileage.sh --pages 10 # scan further back
```

Returns lifetime distance for all bikes (gear_id starts with `b`) and shoes (gear_id starts with `g`) in separate sections. Discovers gear via activity `gear_id` fields — requires `activity:read_all` scope only.

### `shoe-mileage.sh` — Shoes Only (legacy)

```bash
bash skills/strava/scripts/shoe-mileage.sh            # scans 250 activities
```

Shoes only. Use `gear-mileage.sh` for both bikes and shoes.

### `athlete-stats.sh` — All-Time Totals

```bash
bash skills/strava/scripts/athlete-stats.sh
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
