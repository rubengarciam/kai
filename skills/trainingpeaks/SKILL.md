---
name: trainingpeaks
description: Pull real-time training plans, workouts, fitness metrics (CTL/ATL/TSB), and personal records from TrainingPeaks. Uses cookie-based authentication (no API key needed).
---

# TrainingPeaks Skill

CLI access to the TrainingPeaks internal API. Pure Python stdlib — no pip dependencies.

## Credentials

Stored at `~/.config/trainingpeaks/`:
- `cookie` — `Production_tpAuth` cookie value
- `token.json` — cached Bearer token (auto-refreshes)
- `config.json` — cached athlete ID and account info

`TP_AUTH_COOKIE` env var overrides the stored cookie. Tokens auto-refresh from the stored cookie. Cookie lasts weeks — if expired, re-authenticate.

## Setup: Getting Your Auth Cookie

1. Log in to [TrainingPeaks](https://app.trainingpeaks.com) in your browser
2. Open DevTools → Application → Cookies → `app.trainingpeaks.com`
3. Find `Production_tpAuth`, copy the value

```bash
python3 {baseDir}/scripts/tp.py auth "eyJhbGci..."
# ✓ Authenticated successfully!
#   Account: user@example.com
#   Athlete ID: 1234567
```

## Commands

All commands: `python3 {baseDir}/scripts/tp.py <command> [options]`

### `auth-status` — Check Authentication

```bash
python3 {baseDir}/scripts/tp.py auth-status
```

### `profile` — Athlete Profile

```bash
python3 {baseDir}/scripts/tp.py profile
```

Returns name, email, athlete ID, account type, bike FTP.

### `workouts <start> <end>` — List Workouts

```bash
# All workouts in a week
python3 {baseDir}/scripts/tp.py workouts 2026-04-01 2026-04-07

# Filter by status
python3 {baseDir}/scripts/tp.py workouts 2026-04-01 2026-04-07 --filter completed
python3 {baseDir}/scripts/tp.py workouts 2026-04-01 2026-04-07 --filter planned

# JSON output
python3 {baseDir}/scripts/tp.py workouts 2026-04-01 2026-04-07 --json
```

Output columns: Date, Title, Sport, Status (✓/○), Planned duration, Actual duration, TSS, Distance.
Max range: 90 days.

### `workout <id>` — Workout Detail

```bash
python3 {baseDir}/scripts/tp.py workout 123456789
python3 {baseDir}/scripts/tp.py workout 123456789 --json
```

Returns full detail: description, coach notes, planned vs actual metrics, all TSS/IF values.

### `fitness` — CTL / ATL / TSB

```bash
python3 {baseDir}/scripts/tp.py fitness           # last 90 days
python3 {baseDir}/scripts/tp.py fitness --days 365
python3 {baseDir}/scripts/tp.py fitness --json
```

Shows current CTL (fitness), ATL (fatigue), TSB (form) with status interpretation and 14-day daily table.

### `peaks <sport> <pr_type>` — Personal Records

```bash
# Best 20-minute power ever
python3 {baseDir}/scripts/tp.py peaks Bike power20min

# 5K run PRs from last year
python3 {baseDir}/scripts/tp.py peaks Run speed5K --days 365

# 5-second max power
python3 {baseDir}/scripts/tp.py peaks Bike power5sec
```

**Bike PR types:** `power5sec`, `power1min`, `power5min`, `power10min`, `power20min`, `power60min`, `power90min`, `hR5sec`–`hR90min`

**Run PR types:** `hR5sec`–`hR90min`, `speed400Meter`, `speed800Meter`, `speed1K`, `speed1Mi`, `speed5K`, `speed10K`, `speedHalfMarathon`, `speedMarathon`, `speed50K`

### `metrics <start> <end>` — Health Metrics

Get weight, HR, HRV, sleep, steps, SPO2, RMR, injury score:

```bash
python3 {baseDir}/scripts/tp.py metrics 2026-04-01 2026-04-07
python3 {baseDir}/scripts/tp.py metrics 2026-04-01 2026-04-07 --json
```

Available metrics: `weight` (kg), `pulse` (bpm), `hrv`, `sleep` (hours), `spo2` (%), `steps`, `rmr` (kcal), `injury` (1–10)

### `log-metric <date> <metric> <value>` — Log a Health Metric

```bash
python3 {baseDir}/scripts/tp.py log-metric 2026-04-07 weight 73.5
python3 {baseDir}/scripts/tp.py log-metric 2026-04-07 pulse 44
```

## Key Metrics

- **CTL** — Chronic Training Load (fitness). Higher = more fit. Builds slowly.
- **ATL** — Acute Training Load (fatigue). Spikes with hard training.
- **TSB** — Training Stress Balance (form). TSB = CTL − ATL. Positive = fresh, negative = tired.
- **TSS** — Training Stress Score per workout.
- **IF** — Intensity Factor (workout intensity relative to threshold). IF > 1.0 = above threshold.

## Notes

- All dates: `YYYY-MM-DD`
- Rate limiting: 150ms minimum between API requests
- `TP_AUTH_COOKIE` env var overrides stored cookie
- Default output is human-readable; `--json` gives raw API data
- Coach writes workouts in Spanish
