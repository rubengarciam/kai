# TrainingPeaks Skill

CLI access to the TrainingPeaks internal API. Pure Python stdlib — no pip dependencies. Works with any AI assistant that supports skills.

## Features

- Fetch current fitness metrics: CTL, ATL, TSB
- List and inspect planned and completed workouts
- Pull personal records by sport and duration
- Query health metrics: weight, HR, HRV, sleep, SPO2, steps
- Log health metrics back to TrainingPeaks
- Cookie-based auth with automatic token refresh, a hidden-prompt login and a one-command check that the cookie still works

## Requirements

- Python 3.6+
- A TrainingPeaks account

## Setup

### 1. Get your auth cookie

TrainingPeaks has no personal API key, so this skill signs in the way the website does: with the `Production_tpAuth` cookie your browser receives when you log in. **Treat it like a password**: anyone who has it can read and change your TrainingPeaks account. Don't paste it into chat, email or a screenshot (blur it in any screenshot you share), and don't commit it.

Log in to [TrainingPeaks](https://app.trainingpeaks.com) first, then follow the steps for your browser. Menu names differ a little between versions; if a step doesn't match, look for the browser's developer tools and its cookie storage.

> The screenshots below are placeholders and will be replaced. The steps were written from the browsers' documented menus and haven't yet been re-checked on every version, so tell us if one is out of date.

#### Chrome, Edge, Brave and other Chromium browsers

1. On `app.trainingpeaks.com`, press `F12` (or `Ctrl+Shift+I`; on a Mac `Cmd+Option+I`) to open DevTools.
2. Open the **Application** tab (if you don't see it, click `»` at the end of the tab row).
3. In the left list open **Storage → Cookies → https://app.trainingpeaks.com**.
4. Click the row named `Production_tpAuth`. Its value appears in the panel at the bottom (or double-click the **Value** cell).
5. Select the whole value and copy it (`Ctrl+C` / `Cmd+C`). It is a long string of letters, digits and symbols.

![Chrome or Edge: Application tab, Cookies, Production_tpAuth](images/chrome-cookie.svg)

#### Firefox

1. On `app.trainingpeaks.com`, press `F12` (Mac: `Cmd+Option+I`) to open the developer tools.
2. Open the **Storage** tab (enable it under the `⋯` menu → Settings if it's missing).
3. Open **Cookies → https://app.trainingpeaks.com**.
4. Click the row `Production_tpAuth`. Its value is shown in the side panel; double-click the **Value** cell to select it.
5. Copy the whole value.

![Firefox: Storage tab, Cookies, Production_tpAuth](images/firefox-cookie.svg)

#### Safari

1. Once: open **Safari → Settings → Advanced** and tick **Show features for web developers** (older versions: "Show Develop menu in menu bar").
2. On `app.trainingpeaks.com`, choose **Develop → Show Web Inspector** (`Cmd+Option+I`).
3. Open the **Storage** tab, then **Cookies → app.trainingpeaks.com**.
4. Click the row `Production_tpAuth` and copy its value.

![Safari: Web Inspector, Storage, Cookies, Production_tpAuth](images/safari-cookie.svg)

Don't read the cookie with a script or a browser extension, and don't use a shared computer for this.

### 2. Authenticate

Run this **in your own terminal** (an AI agent must never run it for you, because the cookie is your credential):

```bash
python3 skills/trainingpeaks/scripts/tp.py auth
# Paste your Production_tpAuth cookie value (hidden as you type).
# Cookie:
# ✓ Authenticated successfully!
#   Account: user@example.com
#   Athlete ID: 1234567
```

Paste the value and press Enter. Nothing is shown as you type or paste; that is expected. Pasting `Production_tpAuth=<value>`, or the value with quotes, also works.

![Terminal: running tp.py auth](images/terminal-auth.svg)

Other ways to give it the cookie:
- `tp.py auth --stdin` reads the first line of standard input, for scripts (for example `pbpaste | tp.py auth --stdin` on a Mac). Nothing appears on the command line.
- `tp.py auth "<value>"` still works, but the value then lands in your shell history and in the process list while the command runs. Prefer the two forms above.

Credentials are stored at `~/.config/trainingpeaks/`, each file readable by you only (mode `600`):
- `cookie` — the `Production_tpAuth` cookie value
- `token.json` — cached Bearer token (auto-refreshes)
- `config.json` — cached athlete ID, account info and when the cookie was stored

`TP_AUTH_COOKIE` env var overrides the stored cookie. Tokens refresh automatically from the stored cookie.

### 3. Check it, and renew it when it expires

```bash
python3 skills/trainingpeaks/scripts/tp.py auth-status           # offline: shows "stored N days ago"
python3 skills/trainingpeaks/scripts/tp.py auth-status --check   # one request: asks TrainingPeaks if the cookie still works
```

The cookie has no expiry date you can read, and how long it lasts is TrainingPeaks' decision: in practice it has lasted weeks to months, but there is no promise. So the skill can't warn you ahead of time. What it can do is tell you how long ago you stored it, and `--check` tells you right now whether it still works. `--check` says "could not check" (exit code 2) on a network problem, which does not mean the cookie expired.

When TrainingPeaks rejects the cookie, every command stops with the same short instructions: log in, copy the cookie again (step 1), run `tp.py auth` again (step 2). Nothing else needs resetting.

### Why a cookie, and what the alternative is

TrainingPeaks has an official Partner API with OAuth sign-in, but it is for approved companies, not for an individual's own account, and the application form currently says new partners aren't accepted. So there is no supported login a single athlete can set up today, and this skill uses the same session cookie the website does. Two consequences: it is an unofficial route that TrainingPeaks could change or block at any time (`auth-status --check` shows quickly if it has), and using it may not be covered by TrainingPeaks' terms of service, which is your call to make. If TrainingPeaks ever opens self-service API access, that would replace the cookie.

### Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Can't find `Production_tpAuth` | You aren't logged in on `app.trainingpeaks.com`, or you're looking at another site's cookies. Log in, reload, look again. |
| "login cookie has expired or is invalid", or "Token exchange failed (HTTP 500)", right after pasting | A character was lost or added, or the value isn't the `Production_tpAuth` cookie (a made-up value gets the HTTP 500). Copy the whole value again; quotes, spaces and a trailing `;` are fine. |
| Nothing appears when pasting | Expected: the prompt is hidden. Press Enter. |
| "No terminal to ask on" | You ran `auth` somewhere without a keyboard (a script, a chat tool). Use `tp.py auth --stdin`, or run it in a normal terminal. |
| Worked yesterday, fails today | The cookie expired or you logged out everywhere. Repeat steps 1 and 2. |
| `auth-status --check` says "could not check" | Network or TrainingPeaks outage. Try again later. |

## Usage

All commands: `python3 skills/trainingpeaks/scripts/tp.py <command> [options]`

### `auth-status` — Check authentication

```bash
python3 skills/trainingpeaks/scripts/tp.py auth-status           # offline: cookie source and age
python3 skills/trainingpeaks/scripts/tp.py auth-status --check   # also asks TrainingPeaks if the cookie works
```

### `profile` — Athlete profile

```bash
python3 skills/trainingpeaks/scripts/tp.py profile
```

Returns name, email, athlete ID, account type, weight, age (not the date of birth) and FTPs.

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
