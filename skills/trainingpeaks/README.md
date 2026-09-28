# TrainingPeaks Skill

CLI access to the TrainingPeaks internal API. Pure Python stdlib — no pip dependencies. Works with any AI assistant that supports skills.

## Features

- Fetch current fitness metrics: CTL, ATL, TSB
- List and inspect planned and completed workouts
- Pull personal records by sport and duration
- Query health metrics: weight, HR, HRV, sleep, SPO2, steps
- Log health metrics back to TrainingPeaks
- Cookie-based auth with automatic token refresh

## Requirements

- Python 3.6+
- A TrainingPeaks account

## Setup

### 1. Get your auth cookie

1. Log in to [TrainingPeaks](https://app.trainingpeaks.com) in your browser
2. Open DevTools → Application → Cookies → `app.trainingpeaks.com`
3. Find `Production_tpAuth` and copy the value

### 2. Authenticate

```bash
python3 skills/trainingpeaks/scripts/tp.py auth "eyJhbGci..."
# ✓ Authenticated successfully!
#   Account: user@example.com
#   Athlete ID: 1234567
```

Credentials are stored at `~/.config/trainingpeaks/`:
- `cookie` — the `Production_tpAuth` cookie value
- `token.json` — cached Bearer token (auto-refreshes)
- `config.json` — cached athlete ID and account info

`TP_AUTH_COOKIE` env var overrides the stored cookie. Tokens auto-refresh automatically. The cookie lasts weeks — if it expires, repeat the auth step.

## Usage

All commands: `python3 skills/trainingpeaks/scripts/tp.py <command> [options]`

### `auth-status` — Check authentication

```bash
python3 skills/trainingpeaks/scripts/tp.py auth-status
```

### `profile` — Athlete profile

```bash
python3 skills/trainingpeaks/scripts/tp.py profile
```

Returns name, email, athlete ID, account type, bike FTP.

### `workouts` — List workouts

```bash
python3 skills/trainingpeaks/scripts/tp.py workouts 2026-04-01 2026-04-07

# Filter by status
python3 skills/trainingpeaks/scripts/tp.py workouts 2026-04-01 2026-04-07 --filter completed
python3 skills/trainingpeaks/scripts/tp.py workouts 2026-04-01 2026-04-07 --filter planned

# JSON output
python3 skills/trainingpeaks/scripts/tp.py workouts 2026-04-01 2026-04-07 --json
```

Output columns: Date, Title, Sport, Status (✓/○), Planned duration, Actual duration, TSS, Distance. Max range: 90 days.

### `workout` — Workout detail

```bash
python3 skills/trainingpeaks/scripts/tp.py workout 123456789
python3 skills/trainingpeaks/scripts/tp.py workout 123456789 --json
```

Returns full detail: description, coach notes, planned vs actual metrics, TSS, IF.

### `fitness` — CTL / ATL / TSB

```bash
python3 skills/trainingpeaks/scripts/tp.py fitness           # last 90 days
python3 skills/trainingpeaks/scripts/tp.py fitness --days 365
python3 skills/trainingpeaks/scripts/tp.py fitness --json
```

Shows current CTL (fitness), ATL (fatigue), TSB (form) with status interpretation and 14-day daily table.

### `peaks` — Personal records

```bash
python3 skills/trainingpeaks/scripts/tp.py peaks Bike power20min
python3 skills/trainingpeaks/scripts/tp.py peaks Run speed5K --days 365
python3 skills/trainingpeaks/scripts/tp.py peaks Bike power5sec
```

**Bike PR types:** `power5sec`, `power1min`, `power5min`, `power10min`, `power20min`, `power60min`, `power90min`, `hR5sec`–`hR90min`

**Run PR types:** `hR5sec`–`hR90min`, `speed400Meter`, `speed800Meter`, `speed1K`, `speed1Mi`, `speed5K`, `speed10K`, `speedHalfMarathon`, `speedMarathon`, `speed50K`

### `metrics` — Health metrics

```bash
python3 skills/trainingpeaks/scripts/tp.py metrics 2026-04-01 2026-04-07
python3 skills/trainingpeaks/scripts/tp.py metrics 2026-04-01 2026-04-07 --json
```

Available metrics: `weight` (kg), `pulse` (bpm), `hrv`, `sleep` (hours), `spo2` (%), `steps`, `rmr` (kcal), `injury` (1–10)

### `log-metric` — Log a health metric

```bash
python3 skills/trainingpeaks/scripts/tp.py log-metric 2026-04-07 weight 73.5
python3 skills/trainingpeaks/scripts/tp.py log-metric 2026-04-07 pulse 44
```

## Key Metrics

| Metric | Description |
|--------|-------------|
| **CTL** | Chronic Training Load — fitness. Builds slowly over weeks. |
| **ATL** | Acute Training Load — fatigue. Spikes with hard training. |
| **TSB** | Training Stress Balance — form. TSB = CTL − ATL. Positive = fresh, negative = tired. |
| **TSS** | Training Stress Score per workout. |
| **IF** | Intensity Factor — workout intensity relative to threshold. IF > 1.0 = above threshold. |

## Notes

- All dates: `YYYY-MM-DD`
- Rate limiting: 150ms minimum between API requests
- `TP_AUTH_COOKIE` env var overrides stored cookie
- Default output is human-readable; `--json` gives raw API data

## License

GPL v3
