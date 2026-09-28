---
name: garmin-health-analysis
description: Talk to your Garmin data naturally - "what was my fastest speed snowboarding?", "how did I sleep last night?", "what was my heart rate at 3pm?". Access 20+ metrics (sleep stages, Body Battery, HRV, VO2 max, training readiness, body composition, SPO2), download FIT/GPX files for route analysis, query elevation/pace at any point, and generate interactive health dashboards. From casual "show me this week's workouts" to deep "analyze my recovery vs training load".
version: 1.2.2
author: EversonL & Claude
homepage: https://github.com/eversonl/ClawdBot-garmin-health-analysis
metadata: {"clawdbot":{"emoji":"⌚","requires":{"env":["GARMIN_EMAIL","GARMIN_PASSWORD"]},"install":[{"id":"garminconnect","kind":"python","package":"garminconnect","label":"Install garminconnect (pip)"},{"id":"fitparse","kind":"python","package":"fitparse","label":"Install fitparse (pip)"},{"id":"gpxpy","kind":"python","package":"gpxpy","label":"Install gpxpy (pip)"}]}}
---

# Garmin Health Analysis

Query health metrics from Garmin Connect and generate interactive HTML charts.

## Credentials

Stored at `~/.config/garminconnect/`:
- `config.json` — keys: `email`, `password` (optional; env vars also accepted)
- Token files managed by garth (auto-refresh)

Auth status: `python3 {baseDir}/scripts/garmin_auth.py status`

Re-authenticate if tokens expire:
```bash
python3 {baseDir}/scripts/garmin_auth.py login --email EMAIL --password PASSWORD
```

---

## `garmin_data.py` — Core Health Metrics

```bash
python3 {baseDir}/scripts/garmin_data.py <metric> [--days N] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

**Available metrics:**

| Metric | What it returns |
|--------|----------------|
| `sleep` | Sleep stages (deep/light/REM/awake), score, HRV, respiration |
| `body_battery` | Garmin Body Battery throughout the day (0–100) |
| `hrv` | Nightly HRV avg, weekly avg, 5-min high, status |
| `heart_rate` | Resting HR, daily min/max, avg |
| `activities` | Workouts logged to Garmin Connect |
| `stress` | Daily stress levels |
| `summary` | Combined: sleep + HRV + Body Battery + activities |
| `profile` | Athlete profile and settings |

**Examples:**
```bash
python3 {baseDir}/scripts/garmin_data.py summary --days 1        # today's snapshot
python3 {baseDir}/scripts/garmin_data.py sleep --days 7
python3 {baseDir}/scripts/garmin_data.py hrv --days 30
python3 {baseDir}/scripts/garmin_data.py heart_rate --days 14
python3 {baseDir}/scripts/garmin_data.py activities --days 7
python3 {baseDir}/scripts/garmin_data.py sleep --start 2026-04-01 --end 2026-04-07
```

---

## `garmin_data_extended.py` — Training & Performance Metrics

```bash
python3 {baseDir}/scripts/garmin_data_extended.py <metric> [--date YYYY-MM-DD] [--start ...] [--end ...]
```

**Available metrics:**

| Metric | What it returns |
|--------|----------------|
| `training_readiness` | Daily training readiness score (0–100) |
| `training_status` | Training load, VO2 max, training effect |
| `max_metrics` | VO2 max and other max performance metrics |
| `race_predictions` | Garmin's predicted race times (5K, 10K, HM, Marathon) |
| `lactate_threshold` | Lactate threshold pace/HR |
| `endurance_score` | Garmin endurance score |
| `hill_score` | Garmin hill score |
| `body_composition` | Weight, body fat %, muscle mass |
| `weigh_ins` | Weight measurements over time (`--start`/`--end`) |
| `spo2` | Blood oxygen percentage |
| `respiration` | Breathing rate throughout the day |
| `steps` | Detailed step data |
| `floors` | Floors climbed |
| `intensity_minutes` | Vigorous/moderate intensity minutes |
| `hydration` | Water intake |
| `stress_detailed` | All-day stress time-series |
| `hr_intraday` | HR time-series throughout the day |
| `personal_records` | Personal records from Garmin Connect |
| `activity_splits` | Lap splits for a specific activity (`--activity-id ID`) |

**Examples:**
```bash
python3 {baseDir}/scripts/garmin_data_extended.py training_readiness
python3 {baseDir}/scripts/garmin_data_extended.py race_predictions
python3 {baseDir}/scripts/garmin_data_extended.py max_metrics
python3 {baseDir}/scripts/garmin_data_extended.py lactate_threshold
python3 {baseDir}/scripts/garmin_data_extended.py body_composition
python3 {baseDir}/scripts/garmin_data_extended.py weigh_ins --start 2026-01-01 --end 2026-04-07
python3 {baseDir}/scripts/garmin_data_extended.py spo2 --date 2026-04-06
python3 {baseDir}/scripts/garmin_data_extended.py activity_splits --activity-id 12345678
python3 {baseDir}/scripts/garmin_data_extended.py personal_records
python3 {baseDir}/scripts/garmin_data_extended.py endurance_score
```

---

## `garmin_chart.py` — Interactive HTML Charts

```bash
python3 {baseDir}/scripts/garmin_chart.py <chart> [--days N] [--output path.html]
```

| Chart | What it shows |
|-------|--------------|
| `sleep` | Sleep hours + scores over time |
| `body_battery` | Body Battery recovery (color-coded) |
| `hrv` | HRV & resting HR trends |
| `activities` | Activity summary by type |
| `dashboard` | All 4 charts combined |

```bash
python3 {baseDir}/scripts/garmin_chart.py dashboard --days 30
python3 {baseDir}/scripts/garmin_chart.py hrv --days 90 --output ~/hrv-trend.html
```

Charts open in default browser. Built with Chart.js.

---

## `garmin_query.py` — Time-Based Queries

Query data at a specific time of day (e.g. "what was my HR at 3pm?"):

```bash
python3 {baseDir}/scripts/garmin_query.py heart_rate "3pm"
python3 {baseDir}/scripts/garmin_query.py heart_rate "15:00" --date 2026-04-06
```

---

## Answering Common Questions

| Question | Command |
|----------|---------|
| "How did I sleep last night?" | `garmin_data.py summary --days 1` |
| "How's my recovery?" | `garmin_data.py body_battery --days 7` |
| "Is my HRV trending up?" | `garmin_data.py hrv --days 30` |
| "What's my training readiness?" | `garmin_data_extended.py training_readiness` |
| "What does Garmin predict for my marathon?" | `garmin_data_extended.py race_predictions` |
| "What's my VO2 max?" | `garmin_data_extended.py max_metrics` |
| "What's my lactate threshold?" | `garmin_data_extended.py lactate_threshold` |
| "Am I overtraining?" | `garmin_data.py summary --days 14` + `garmin_data_extended.py training_status` |
| "Show me lap splits for a race" | `garmin_data_extended.py activity_splits --activity-id ID` |
| "What's my current weight?" | `garmin_data_extended.py weigh_ins` |
| "Show me a health dashboard" | `garmin_chart.py dashboard --days 30` |

---

## Key Metrics Reference

### Body Battery (0–100)
- **75–100**: Fully recharged, ready for high intensity
- **50–74**: Moderate energy, good for regular training
- **25–49**: Limited energy, recovery needed
- **0–24**: Depleted, prioritize rest

### Sleep Score (0–100)
- **90–100**: Optimal
- **80–89**: Good
- **60–79**: Fair
- **<60**: Poor

### HRV (ms)
Higher = better recovery. Track trends over time, not single values.

### Training Readiness (0–100)
Garmin's composite score combining sleep, HRV, Body Battery, stress, and training history.
- **>75**: Ready for hard training
- **50–75**: Moderate training OK
- **<50**: Recovery day recommended

### Resting HR
Trained athletes typically range 40–55 bpm. Sudden increases suggest fatigue, illness, or overtraining.

---

## Troubleshooting

- **401/auth error**: Run `garmin_auth.py login` again
- **Rate limited**: Garmin rate-limits; wait a few minutes
- **Missing data**: Some metrics need specific Garmin devices (Body Battery requires HRV-capable watch)
- **Library errors**: this skill needs `garminconnect` 0.2.x (it uses `client.garth`). Reinstall the pinned version with `pip install -r requirements.txt` from the Kai repo root. Do not upgrade to 0.3.x.
