# Garmin Health Analysis Skill

Query health and training metrics from Garmin Connect. Works with any AI assistant that supports skills.

## Features

- Sleep analysis: hours, stages (light/deep/REM/awake), scores, HRV, respiration
- Recovery tracking: Body Battery, HRV trends, stress levels
- Training metrics: readiness score, training load, VO2 max, lactate threshold
- Race predictions: Garmin-estimated times for 5K, 10K, half marathon, marathon
- Health data: resting HR, body composition, weight history, SPO2, steps
- Workout listing: activities by type, duration, calories, pace, elevation
- Intraday time-series: HR and stress throughout the day
- Personal records from Garmin Connect
- Activity lap splits
- Interactive HTML dashboards (Chart.js)
- Session tokens auto-refresh via garth (no repeated logins)

## Requirements

- Python 3.7+
- `pip3 install garminconnect fitparse gpxpy`
- A Garmin Connect account

## Setup

### 1. Install dependencies

```bash
pip3 install garminconnect fitparse gpxpy
```

### 2. Authenticate

```bash
python3 scripts/garmin_auth.py login --email you@example.com --password yourpassword
# 🔐 Logging in as you@example.com...
# ✅ Tokens saved to /home/user/.config/garminconnect
# ✅ Login successful! User: YourName
```

Tokens are stored at `~/.config/garminconnect/` and auto-refresh. You should only need to run this once unless your session expires.

Alternatively, set `GARMIN_EMAIL` and `GARMIN_PASSWORD` as environment variables and omit the flags.

### 3. Check auth status

```bash
python3 scripts/garmin_auth.py status
```

## Credentials

Stored at `~/.config/garminconnect/`:
- `config.json` — keys: `email`, `password` (optional; env vars also accepted)
- Token files managed by garth (auto-refresh)

## Scripts

### `garmin_auth.py` — Authentication

```bash
python3 scripts/garmin_auth.py login --email EMAIL --password PASSWORD
python3 scripts/garmin_auth.py status
```

### `garmin_data.py` — Core health metrics

```bash
python3 scripts/garmin_data.py <metric> [--days N] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

| Metric | What it returns |
|--------|----------------|
| `sleep` | Sleep stages, score, HRV, respiration |
| `body_battery` | Body Battery throughout the day (0–100) |
| `hrv` | Nightly HRV avg, weekly avg, 5-min high, status |
| `heart_rate` | Resting HR, daily min/max, avg |
| `activities` | Workouts logged to Garmin Connect |
| `stress` | Daily stress levels |
| `summary` | Sleep + HRV + Body Battery + activities combined |
| `profile` | Athlete profile and settings |

```bash
python3 scripts/garmin_data.py summary --days 1
python3 scripts/garmin_data.py sleep --days 7
python3 scripts/garmin_data.py hrv --days 30
python3 scripts/garmin_data.py heart_rate --days 14
python3 scripts/garmin_data.py activities --days 7
python3 scripts/garmin_data.py sleep --start 2026-04-01 --end 2026-04-07
```

### `garmin_data_extended.py` — Training and performance metrics

```bash
python3 scripts/garmin_data_extended.py <metric> [--date YYYY-MM-DD] [--start ...] [--end ...]
```

| Metric | What it returns |
|--------|----------------|
| `training_readiness` | Daily readiness score (0–100) |
| `training_status` | Training load, VO2 max, training effect |
| `max_metrics` | VO2 max and max performance metrics |
| `race_predictions` | Predicted race times (5K, 10K, HM, Marathon) |
| `lactate_threshold` | Lactate threshold pace and HR |
| `endurance_score` | Garmin endurance score |
| `hill_score` | Garmin hill score |
| `body_composition` | Weight, body fat %, muscle mass |
| `weigh_ins` | Weight measurements over time |
| `spo2` | Blood oxygen percentage |
| `respiration` | Breathing rate throughout the day |
| `steps` | Detailed step data |
| `floors` | Floors climbed |
| `intensity_minutes` | Vigorous and moderate intensity minutes |
| `hydration` | Water intake |
| `stress_detailed` | All-day stress time-series |
| `hr_intraday` | HR time-series throughout the day |
| `personal_records` | Personal records from Garmin Connect |
| `activity_splits` | Lap splits for a specific activity |

```bash
python3 scripts/garmin_data_extended.py training_readiness
python3 scripts/garmin_data_extended.py race_predictions
python3 scripts/garmin_data_extended.py max_metrics
python3 scripts/garmin_data_extended.py body_composition
python3 scripts/garmin_data_extended.py weigh_ins --start 2026-01-01 --end 2026-04-07
python3 scripts/garmin_data_extended.py spo2 --date 2026-04-06
python3 scripts/garmin_data_extended.py activity_splits --activity-id 12345678
python3 scripts/garmin_data_extended.py personal_records
```

### `garmin_chart.py` — Interactive HTML charts

```bash
python3 scripts/garmin_chart.py <chart> [--days N] [--output path.html]
```

| Chart | What it shows |
|-------|--------------|
| `sleep` | Sleep hours and scores over time |
| `body_battery` | Body Battery recovery (color-coded) |
| `hrv` | HRV and resting HR trends |
| `activities` | Activity summary by type |
| `dashboard` | All four charts combined |

```bash
python3 scripts/garmin_chart.py dashboard --days 30
python3 scripts/garmin_chart.py hrv --days 90 --output ~/hrv-trend.html
```

Charts open in the default browser. Built with Chart.js.

### `garmin_query.py` — Time-based queries

Query data at a specific time of day:

```bash
python3 scripts/garmin_query.py heart_rate "3pm"
python3 scripts/garmin_query.py heart_rate "15:00" --date 2026-04-06
```

## Key metrics reference

### Body Battery (0–100)
- **75–100**: Fully recharged, ready for high intensity
- **50–74**: Moderate energy, good for regular training
- **25–49**: Limited energy, recovery needed
- **0–24**: Depleted, prioritize rest

### Training Readiness (0–100)
Composite score combining sleep, HRV, Body Battery, stress, and training history.
- **>75**: Ready for hard training
- **50–75**: Moderate training OK
- **<50**: Recovery day recommended

### HRV
Higher is better. Track trends over time, not individual values.

### Resting HR
Trained athletes typically range 40–55 bpm. Sudden increases suggest fatigue, illness, or overtraining.

## Notes

- All dates: `YYYY-MM-DD`
- Some metrics require specific devices (Body Battery needs an HRV-capable watch)
- Garmin rate-limits API requests — if data is missing, wait a few minutes and retry
- `GARMIN_EMAIL` and `GARMIN_PASSWORD` env vars override `config.json`

## Troubleshooting

**401 / auth error**: Run `python3 scripts/garmin_auth.py login` again.

**Missing data**: Check the device was worn during the time period. Some metrics need specific hardware.

**Library outdated**: `pip3 install --upgrade garminconnect`

## Links

- [python-garminconnect](https://github.com/cyberjunky/python-garminconnect)
- [Garmin Connect](https://connect.garmin.com)

## License

GPL v3
