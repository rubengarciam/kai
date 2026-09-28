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
- Session tokens auto-refresh (no repeated logins); your password is never stored

## Requirements

- Python 3.12+
- The Python packages in the Kai repo's `requirements.txt` (`garminconnect` 0.3.x, `fitparse`, `gpxpy`)
- A Garmin Connect account

## Setup

### 1. Install dependencies

From the Kai repo root, in a virtual environment (see [docs/installation.md](../../docs/installation.md#python-packages-garmin-only)):

```bash
.venv/bin/pip install -r requirements.txt
```

On Python older than 3.12, use `uv` (see [docs/installation.md](../../docs/installation.md#python-packages-garmin-only)).

### 2. Authenticate

```bash
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py login
# Garmin email: you@example.com
# Garmin password for you@example.com:   (hidden)
# 🔐 Logging in as you@example.com...
# ✅ Tokens saved to /home/user/.config/garminconnect/garmin_tokens.json
# ✅ Login successful! User: YourName
```

Tokens are stored at `~/.config/garminconnect/` and auto-refresh. You should only need to run this once unless your session expires.

The password is asked for on the terminal and is never written to disk. Run this yourself in a terminal. Alternatives: `--email you@example.com` or `GARMIN_EMAIL` to skip the email prompt, and `--password-stdin` or `GARMIN_PASSWORD` for scripting. There is deliberately no `--password` flag: a password on the command line ends up in shell history and the process list. If your account uses two-factor authentication you'll be asked for the code.

**Upgrading from an older version:** tokens saved by garminconnect 0.2.x can't be used any more. Run `login` once.

### 3. Check auth status

```bash
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py status
```

## Credentials

Stored at `~/.config/garminconnect/`:
- `garmin_tokens.json` — session tokens (mode 600, in a 700 directory; auto-refresh)
- `config.json` — optional, key `email` only. A `password` key is ignored, with a warning
- `GARMIN_TOKEN_DIR` — optional, keep the tokens somewhere else

## Scripts

### `garmin_auth.py` — Authentication

```bash
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py login            # prompts for email, password and MFA code (run it yourself in a terminal)
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py status
```

### `garmin_data.py` — Core health metrics

```bash
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data.py <metric> [--days N] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
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
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data.py summary --days 1
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data.py sleep --days 7
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data.py hrv --days 30
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data.py heart_rate --days 14
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data.py activities --days 7
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data.py sleep --start 2026-04-01 --end 2026-04-07
```

### `garmin_data_extended.py` — Training and performance metrics

```bash
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data_extended.py <metric> [--date YYYY-MM-DD] [--start ...] [--end ...]
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
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data_extended.py training_readiness
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data_extended.py race_predictions
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data_extended.py max_metrics
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data_extended.py body_composition
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data_extended.py weigh_ins --start 2026-01-01 --end 2026-04-07
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data_extended.py spo2 --date 2026-04-06
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data_extended.py activity_splits --activity-id 12345678
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_data_extended.py personal_records
```

### `garmin_chart.py` — Interactive HTML charts

```bash
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_chart.py <chart> [--days N] [--output path.html]
```

| Chart | What it shows |
|-------|--------------|
| `sleep` | Sleep hours and scores over time |
| `body_battery` | Body Battery recovery (color-coded) |
| `hrv` | HRV and resting HR trends |
| `activities` | Activity summary by type |
| `dashboard` | All four charts combined |

```bash
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_chart.py dashboard --days 30
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_chart.py hrv --days 90 --output ~/hrv-trend.html
```

Charts open in the default browser. Built with Chart.js.

### `garmin_query.py` — Time-based queries

Query data at a specific time of day:

```bash
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_query.py heart_rate "3pm"
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_query.py heart_rate "15:00" --date 2026-04-06
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
- `GARMIN_EMAIL` overrides `config.json`; `GARMIN_PASSWORD` is used instead of the prompt when set

## Troubleshooting

**401 / auth error**: Run `.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py login` again.

**Missing data**: Check the device was worn during the time period. Some metrics need specific hardware.

**Library errors**: this skill needs `garminconnect` 0.3.x and Python 3.12+. Reinstall with `pip install -r requirements.txt` from the Kai repo root.

**Rate limited on login**: Garmin blocks repeated logins from one connection. Wait an hour before trying again.

## Links

- [python-garminconnect](https://github.com/cyberjunky/python-garminconnect)
- [Garmin Connect](https://connect.garmin.com)

## License

GPL v3
