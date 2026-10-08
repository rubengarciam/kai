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
- One-command first-time setup (`authorize.py`) and auto token refresh (tokens expire every 6 hours)
- No dependencies beyond `curl` and `python3` (stdlib only)

## Requirements

- `curl`
- `python3` (stdlib only)
- A Strava account with an API application

## Setup

### 1. Create a Strava API application

Visit https://www.strava.com/settings/api and create an app. Note your **Client ID** and **Client Secret**.

### 2. Authorize and get tokens

In your app's settings on the same page, set **Authorization Callback Domain** to `localhost`. This is the one step Strava makes you do by hand; if it is wrong, Strava shows a "redirect_uri invalid" page later.

Then run the helper once:

```bash
python3 skills/strava/scripts/authorize.py
```

It asks for your Client ID and Client Secret (the secret is typed hidden and is never a command-line argument; you can also set `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`), prints an address to open, and then:

1. Open the address in a browser and click **Authorize**. Leave the box for viewing your private activities ticked.
2. Strava sends the browser to a `localhost` page that fails to load. That is expected. Copy the full address from the address bar and paste it into the terminal (the bare `code` value works too).

This default works over SSH and on machines without a display. If the browser is on the same machine you can add `--listen` and the script catches the redirect itself (a one-shot listener on `127.0.0.1` only, 3-minute limit; `--port` changes the port, default 8721).

The script exchanges the code for tokens and writes `~/.config/strava/credentials.json` with mode `600` (folder `700`). It never prints a code or token. If the file already holds tokens it stops instead of replacing them: use `refresh_token.sh` to renew, or `--force` to authorize again from scratch (for example after a wrong scope).

To do it by hand instead, save this to `~/.config/strava/credentials.json` (mode `600`):

```json
{
  "STRAVA_CLIENT_ID": "your-client-id",
  "STRAVA_CLIENT_SECRET": "your-client-secret",
  "STRAVA_ACCESS_TOKEN": "your-access-token",
  "STRAVA_REFRESH_TOKEN": "your-refresh-token"
}
```

All scripts load credentials from this file automatically. Alternatively, set `STRAVA_ACCESS_TOKEN` as an environment variable — no file needed for read-only use.

A new Strava app starts with a single-athlete limit and the rate limits below, which is plenty for one person and Kai.

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
| `GET /oauth/authorize`, `POST /oauth/token` | First-time authorization, token refresh |

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
