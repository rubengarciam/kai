# Strava Skill

Load and analyze your Strava activities, gear mileage, and training stats using the Strava API. Works with any AI assistant that supports skills.

## Features

- List recent activities with flexible date and count filters
- Full activity detail: pace, heart rate, elevation, power, cadence
- Time-series streams: HR, pace, cadence, power, altitude per second
- Lap splits for interval analysis
- Gear mileage: lifetime distance for all bikes and shoes
- Athlete profile and all-time / YTD cumulative stats
- HR and power training zones
- Auto token refresh (tokens expire every 6 hours)
- No dependencies beyond `curl` and `python3` (stdlib only)

## Requirements

- `curl`
- `python3` (stdlib only)
- A Strava account with an API application

## Setup

### 1. Create a Strava API application

Visit https://www.strava.com/settings/api and create an app. Note your **Client ID** and **Client Secret**.

### 2. Authorize and get tokens

Authorize with `activity:read_all` scope and exchange the code for tokens via OAuth. Save the result to `~/.config/strava/credentials.json`:

```bash
mkdir -p ~/.config/strava
```

```json
{
  "STRAVA_CLIENT_ID": "your-client-id",
  "STRAVA_CLIENT_SECRET": "your-client-secret",
  "STRAVA_ACCESS_TOKEN": "your-access-token",
  "STRAVA_REFRESH_TOKEN": "your-refresh-token"
}
```

All scripts load credentials from this file automatically. Alternatively, set `STRAVA_ACCESS_TOKEN` as an environment variable — no file needed for read-only use.

### 3. Refresh tokens when needed

Access tokens expire every 6 hours. Refresh with:

```bash
bash skills/strava/scripts/refresh_token.sh
```

Run this if a script returns a 401 error. New tokens are written back to the credentials file automatically.

## Scripts

### `activities.sh` — Recent activities

```bash
bash skills/strava/scripts/activities.sh              # last 14 days
bash skills/strava/scripts/activities.sh --days 30
bash skills/strava/scripts/activities.sh --days 7 --count 20
```

Output: date, sport type, name, distance, time, elevation, avg HR.

### `athlete-stats.sh` — All-time totals

```bash
bash skills/strava/scripts/athlete-stats.sh
```

Returns cumulative all-time and YTD totals for Run, Ride, and Swim: activity count, distance, time, and elevation.

### `gear-mileage.sh` — Bike and shoe mileage

```bash
bash skills/strava/scripts/gear-mileage.sh            # scans last 250 activities
bash skills/strava/scripts/gear-mileage.sh --pages 10 # scan further back
```

Discovers all gear via activity `gear_id` fields and returns lifetime distance for bikes and shoes in separate sections. Requires `activity:read_all` scope only — no gear endpoint needed.

### `shoe-mileage.sh` — Shoe mileage only

```bash
bash skills/strava/scripts/shoe-mileage.sh
```

Shoes only. Use `gear-mileage.sh` for both bikes and shoes.

## Inline API calls

For one-off queries, use Python directly (credentials are auto-loaded):

```python
import json, urllib.request, os

token = os.environ.get("STRAVA_ACCESS_TOKEN")
if not token:
    path = os.path.expanduser("~/.config/strava/credentials.json")
    if os.path.exists(path):
        with open(path) as f:
            token = json.load(f)["STRAVA_ACCESS_TOKEN"]

def strava(path):
    req = urllib.request.Request(
        f"https://www.strava.com/api/v3{path}",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# Athlete profile
athlete = strava("/athlete")

# All-time stats
stats = strava(f"/athletes/{athlete['id']}/stats")

# Full activity detail
activity = strava("/activities/ACTIVITY_ID")

# Lap splits
laps = strava("/activities/ACTIVITY_ID/laps")

# Time-series streams (HR, pace, cadence, power, altitude)
streams = strava("/activities/ACTIVITY_ID/streams?keys=heartrate,velocity_smooth,cadence,watts,altitude")

# Athlete HR and power zones
zones = strava("/athlete/zones")
```

## API coverage

| Endpoint | Description |
|----------|-------------|
| `GET /athlete` | Athlete profile |
| `GET /athletes/{id}/stats` | All-time and YTD stats |
| `GET /athlete/activities` | List activities |
| `GET /activities/{id}` | Full activity detail |
| `GET /activities/{id}/laps` | Lap splits |
| `GET /activities/{id}/streams` | Time-series data (HR, pace, power, cadence, altitude) |
| `GET /athlete/zones` | HR and power training zones |
| `POST /oauth/token` | Token refresh |

## Activity data fields

Key fields available on activity objects:

| Field | Description |
|-------|-------------|
| `name`, `sport_type`, `start_date_local` | Basic metadata |
| `distance` | Meters |
| `moving_time`, `elapsed_time` | Seconds |
| `total_elevation_gain` | Meters |
| `average_speed`, `max_speed` | m/s |
| `average_heartrate`, `max_heartrate` | bpm |
| `average_watts`, `weighted_average_watts` | Power meter data |
| `gear_id` | Shoe or bike used |

## Rate limits

- 200 requests per 15 minutes
- 2,000 requests per day

## Links

- [Strava Developers](https://developers.strava.com/)
- [API Reference](https://developers.strava.com/docs/reference/)
- [Create an app](https://www.strava.com/settings/api)

## License

GPL v3
