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

`TP_AUTH_COOKIE` env var overrides the stored cookie. Tokens auto-refresh from the stored cookie. All files are mode `600`. The cookie has no readable expiry and lasts weeks to months (not guaranteed): `auth-status` shows how long ago it was stored, `auth-status --check` asks TrainingPeaks whether it still works (exit 0 valid, 1 rejected, 2 could not check, which is not the same as expired).

## Setup: Getting Your Auth Cookie

The cookie is the athlete's credential: **they** copy it from their own browser and run the command in their own terminal. An agent must not run `auth`, ask for the cookie in chat, or put it in a command. Step-by-step instructions for Chrome/Edge, Firefox and Safari are in [README.md](README.md) (section "Get your auth cookie"); point the athlete there.

```bash
python3 skills/trainingpeaks/scripts/tp.py auth          # hidden prompt, keeps it out of shell history
python3 skills/trainingpeaks/scripts/tp.py auth --stdin  # scripts: first line of stdin
# ✓ Authenticated successfully!
#   Account: user@example.com
#   Athlete ID: 1234567
```

If any command says the cookie has expired or is invalid, stop (don't retry) and tell the athlete to repeat the setup above.

## Commands

All commands: `python3 skills/trainingpeaks/scripts/tp.py <command> [options]`

### `auth-status` — Check Authentication

```bash
python3 skills/trainingpeaks/scripts/tp.py auth-status
```

### `profile` — Athlete Profile

```bash
python3 skills/trainingpeaks/scripts/tp.py profile
```

Returns name, email, athlete ID, account type, weight, age (not the date of birth) and FTPs.

### `workouts <start> <end>` — List Workouts

```bash
# All workouts in a week
python3 skills/trainingpeaks/scripts/tp.py workouts 2026-04-01 2026-04-07

# Filter by status
python3 skills/trainingpeaks/scripts/tp.py workouts 2026-04-01 2026-04-07 --filter completed
python3 skills/trainingpeaks/scripts/tp.py workouts 2026-04-01 2026-04-07 --filter planned

# JSON output
python3 skills/trainingpeaks/scripts/tp.py workouts 2026-04-01 2026-04-07 --json
```

Output columns: Date, Title, Sport, Status (✓/○), Planned duration, Actual duration, TSS, Distance.
Max range: 90 days.

### `workout <id>` — Workout Detail

```bash
python3 skills/trainingpeaks/scripts/tp.py workout 123456789
python3 skills/trainingpeaks/scripts/tp.py workout 123456789 --json
```

Returns full detail: description, coach notes, planned vs actual metrics, all TSS/IF values.

### `fitness` — CTL / ATL / TSB

```bash
python3 skills/trainingpeaks/scripts/tp.py fitness           # last 90 days
python3 skills/trainingpeaks/scripts/tp.py fitness --days 365
python3 skills/trainingpeaks/scripts/tp.py fitness --json
```

Shows current CTL (fitness), ATL (fatigue), TSB (form) with status interpretation and 14-day daily table.

### `peaks <sport> <pr_type>` — Personal Records

```bash
# Best 20-minute power ever
python3 skills/trainingpeaks/scripts/tp.py peaks Bike power20min

# 5K run PRs from last year
python3 skills/trainingpeaks/scripts/tp.py peaks Run speed5K --days 365

# 5-second max power
python3 skills/trainingpeaks/scripts/tp.py peaks Bike power5sec
```

**Bike PR types:** `power5sec`, `power1min`, `power5min`, `power10min`, `power20min`, `power60min`, `power90min`, `hR5sec`–`hR90min`

**Run PR types:** `hR5sec`–`hR90min`, `speed400Meter`, `speed800Meter`, `speed1K`, `speed1Mi`, `speed5K`, `speed10K`, `speedHalfMarathon`, `speedMarathon`, `speed50K`

### `metrics <start> <end>` — Health Metrics

Get weight, HR, HRV, sleep, steps, SPO2, RMR, injury score:

```bash
python3 skills/trainingpeaks/scripts/tp.py metrics 2026-04-01 2026-04-07
python3 skills/trainingpeaks/scripts/tp.py metrics 2026-04-01 2026-04-07 --json
```

Available metrics: `weight` (kg), `pulse` (bpm), `hrv`, `sleep` (hours), `spo2` (%), `steps`, `rmr` (kcal), `injury` (1–10)

The table has one row per date, with `—` where a metric has no value. Check the date of the newest value before quoting it: it may not be today's.

### `log-metric <date> <metric> <value>` — Log a Health Metric

```bash
python3 skills/trainingpeaks/scripts/tp.py log-metric 2026-04-07 weight 73.5
python3 skills/trainingpeaks/scripts/tp.py log-metric 2026-04-07 pulse 44
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
