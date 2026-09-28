# Kai — an AI endurance coach

Kai is an AI coaching agent for triathletes, runners, cyclists and swimmers. It connects to the platforms you already train with (TrainingPeaks, Garmin Connect, Strava), reads your actual data, and does what a good coach does with it: analyzes your sessions, tracks fitness and fatigue, watches recovery, and, if you don't have a human coach, builds periodized training plans for your races.

It's built as an [OpenClaw](https://docs.openclaw.ai) agent workspace: a folder of plain markdown instructions plus four skills. There is no server or app to deploy. You point an agent at this folder and chat with it in whatever channel your agent runtime is connected to. It should also work with [Hermes Agent](#using-kai-with-hermes) (see below; untested).

> Kai is a coaching assistant, not a doctor. It will flag things that look medical and tell you to see a professional.

## What Kai does

| Capability | What you get | Needs |
| ---------- | ------------ | ----- |
| **Workout analysis** | Overall read, planned-vs-actual table and lap-by-lap breakdown; data is read before your comments | TrainingPeaks, plus Strava for laps and Garmin for recovery context |
| **Fitness and fatigue tracking** | CTL / ATL / TSB, weekly TSS, form for race day | TrainingPeaks |
| **Recovery monitoring** | HRV, resting HR, sleep, Body Battery and readiness trends read alongside load | Garmin |
| **Training plans** | Periodized plans (base, build, peak, taper) with zones, paces, workouts and a race-day plan, validated with you first | Any one data source, or just a chat |
| **Analyst mode** | Interprets data and preps questions for your human coach; never overrides the plan | Any data source |
| **Gear tracking** | Live shoe and bike mileage, per-wheelset tyre wear, replacement and maintenance alerts | Strava |
| **Chain wax log** | Wax dates and odometer per bike, km since last wax, next-due alerts (early first re-wax, then a full interval) | Strava for mileage; log kept in memory |
| **Nutrition and weight** | Log food and weight in chat; deficits paced to training load; checks tomorrow's session first | Optional; weight syncs to TrainingPeaks |
| **Race notes** | Race-specific pacing, fueling and taper plans saved for later chats | Nothing |
| **Proactive checks** | Watches for bad recovery trends, upcoming key sessions and gear thresholds | A runtime with heartbeats or scheduling |

The details, one capability at a time:

### Analyzes your workouts
Ask "how did that session go?" and Kai pulls the workout from TrainingPeaks, the lap splits from Strava, and your recovery context from Garmin (sleep, HRV, resting HR). It then gives you:

- an **overall read**: execution quality, load vs plan, conditions
- a **planned vs actual table**: duration, pace, TSS, IF, HR, cadence, RPE and so on
- a **lap-by-lap breakdown** of intervals: pacing, HR drift, consistency

Kai reads the numbers *before* it reads your comments. If you say the run felt easy and the HR says otherwise, it tells you, instead of nodding along. It also knows the traps: smart-trainer ERG mode makes power look "perfectly paced", treadmill and GPS glitches corrupt pace, and TrainingPeaks has no lap data.

### Tracks fitness, fatigue and recovery
CTL / ATL / TSB (fitness, fatigue, form), weekly TSS, HRV and resting-HR trends, sleep, Body Battery and training readiness. It reads these together, since load without recovery context is only half the picture. This is what lets it answer "am I ready to add intensity?" or "why do I feel flat this week?" with data.

### Builds training plans (if you don't have a coach)
Kai can write a periodized plan (base, build, peak, taper) for triathlon, marathon or ultra events:

- assesses your current form and training history, then **checks that assessment with you** before writing anything
- sets training zones from your thresholds (FTP, run threshold, CSS), or prescribes field tests when it doesn't have them
- sets weekly load targets and a race-day CTL/TSB target
- writes sport-specific workouts with zones and paces, and a race-day pacing and nutrition plan

### Or supports the coach you already have
If you have a human coach, tell Kai in `USER.md`. It switches to analyst mode: it interprets your data, prepares your questions for your next check-in, explains what a session was for, and never overrides the plan.

### Optional extras
- **Gear tracking**: live shoe and bike mileage from Strava, tyre wear per wheelset, replacement and maintenance alerts.
- **Chain wax log**: Kai keeps a wax log per bike (date, odometer, product) and works out km since the last wax from live Strava mileage. It suggests re-waxing early the first time, then at a full interval (about 450-500 km for hot wax, 200-300 km for drip wax), and warns you when a bike is close. Bikes without Strava tracking, like a partner's, can be logged by hand.
- **Nutrition and weight tracking**: log food and weight in plain chat. Weight goes to TrainingPeaks, food to a local CSV. Kai tracks kcal and protein, paces deficits to your training load, and checks tomorrow's session before recommending a low-carb day.
- **Race notes**: race-specific tactics, pacing and taper plans are saved to memory so they're available in any later chat.
- **Proactive checks**: with heartbeats enabled, Kai can watch for things like a recovery trend turning bad or a gear threshold approaching.

## How it works

```
You (chat) ──► Kai (OpenClaw agent)
                 │  reads AGENTS.md, SOUL.md, USER.md, memory/
                 │
                 ├─ skills/trainingpeaks ─────► TrainingPeaks  (load, workouts, PRs, weight)
                 ├─ skills/garmin-health-analysis ► Garmin Connect (sleep, HRV, readiness)
                 ├─ skills/strava ────────────► Strava         (laps, streams, gear)
                 └─ skills/endurance-training-coach  (zones, periodization, workouts, race day)
```

Data priority when sources overlap: TrainingPeaks for load, Garmin for recovery, Strava for lap-level detail. You don't need all three. Kai uses what's configured and falls back to asking you questions for the rest.

Memory is plain markdown in `memory/`, so it survives model or runtime changes and you can read or edit it yourself.

## Requirements

Kai runs on **Linux or macOS** (on Windows, use WSL). Verified on Raspberry Pi OS (Debian) with Python 3.13; the package pins need Python 3.10+.

| Requirement | Version | Needed for | How to get it |
| ----------- | ------- | ---------- | ------------- |
| Agent runtime | [OpenClaw](https://docs.openclaw.ai) (needs Node.js 24.16+ or 26.1+, which its installer sets up) or [Hermes Agent](https://hermes-agent.nousresearch.com) | Everything | Follow the runtime's install guide |
| `git` | any | Cloning this repo | `sudo apt install git` / `brew install git` |
| `python3` | **3.10 or newer** | Garmin and TrainingPeaks skills | Check with `python3 --version` |
| `python3-venv` | matches Python | Isolating the Garmin packages | Debian/Ubuntu/Raspberry Pi OS: `sudo apt install python3-venv`. macOS: included with Python |
| `curl` and `bash` | any | Strava skill | Preinstalled on Linux and macOS |
| Python packages | `garminconnect==0.2.38`, `fitparse`, `gpxpy` (pinned in `requirements.txt`) | Garmin skill only | See "Install the Python packages" below |
| Internet access | | All data sources; Garmin dashboards also load Chart.js from a CDN | |
| Accounts | at least one of TrainingPeaks, Garmin Connect, Strava | Data | You may skip any you don't use |

The TrainingPeaks skill uses only the Python standard library, and the Strava skill only needs `curl` and Python. **Only Garmin needs extra packages.**

> **Pin, don't upgrade:** the Garmin scripts need `garminconnect` 0.2.x. A plain `pip install garminconnect` now installs 0.3.x, which needs Python 3.12+ and removed the login-token API these scripts use, so the Garmin skill breaks. Always install from `requirements.txt`.

## Setup

These steps are for OpenClaw. For Hermes, see [Using Kai with Hermes](#using-kai-with-hermes).

Check the [requirements](#requirements) first.

### 1. Get the workspace (OpenClaw)

```bash
git clone https://github.com/rubengarciam/kai.git ~/.openclaw/workspace-kai
openclaw agents add kai --workspace ~/.openclaw/workspace-kai
```

Bind the agent to a channel with `--bind` if you want to chat with it there (see `openclaw agents --help`).

### 2. Tell Kai about yourself

```bash
cd ~/.openclaw/workspace-kai
cp templates/USER.md USER.md
cp templates/MEMORY.md MEMORY.md
```

Fill in `USER.md` (thresholds, goals, race calendar, injuries, whether you have a coach). Or skip this and say hello: on first contact Kai interviews you and writes it for you.

### 3. Install the Python packages (Garmin only)

Skip this if you don't use Garmin. Create a virtual environment inside the Kai folder and install the pinned packages:

```bash
cd ~/.openclaw/workspace-kai
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

If `python3 -m venv` fails with "ensurepip is not available", run `sudo apt install python3-venv` and retry. Kai's `AGENTS.md` tells the agent to run the Garmin scripts with `.venv/bin/python3` when the folder exists. Use the same interpreter when you run them yourself, for example:

```bash
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py login --email you@example.com --password 'your-password'
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py status
```

If your Garmin account uses two-factor authentication, run the login command in a terminal: it will ask for the code.

### 4. Connect your data sources

Each skill has its own setup guide. Credentials are stored on your machine under `~/.config/<service>/`.

| Source | What you need | Guide |
| ------ | ------------- | ----- |
| TrainingPeaks | Your `Production_tpAuth` browser cookie (no API key) | [skills/trainingpeaks](skills/trainingpeaks/README.md) |
| Garmin Connect | The packages from step 3, then a one-time login (`garmin_auth.py login`, shown above) | [skills/garmin-health-analysis](skills/garmin-health-analysis/README.md) |
| Strava | A free Strava API app (client ID and secret) and one OAuth authorization | [skills/strava](skills/strava/README.md) |

Optional gear tracking: `cp skills/strava/data/tyres.example.json skills/strava/data/tyres.json` and edit it.

### 5. Start talking

Example prompts:

> "Analyze this morning's run."
>
> "How's my training load? Am I ready to add intensity?"
>
> "I have a marathon on 2026-11-15. Review my fitness and build me a plan."
>
> "How's my recovery looking this week?"
>
> "What's my shoe mileage? Anything close to replacement?"
>
> "Log weight 72.4. Had oats and a protein shake for breakfast."

## Using Kai with Hermes

Kai also works with [Hermes Agent](https://hermes-agent.nousresearch.com) (Nous Research). Hermes reads `AGENTS.md` from the working directory, uses the same `SKILL.md` skill format, and keeps its identity in a global `SOUL.md`. This setup is based on Hermes's documentation. It has not been tested against a live Hermes install yet, so report any rough edges.

```bash
# 1. Get the workspace anywhere you like
git clone https://github.com/rubengarciam/kai.git ~/kai
cd ~/kai

# 2. Personalize
cp templates/USER.md USER.md
cp templates/MEMORY.md MEMORY.md

# 3. Garmin only: install the pinned Python packages (see Requirements)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 4. Give Kai its personality (Hermes only reads SOUL.md from its home directory)
cp SOUL.md ~/.hermes/SOUL.md     # or $HERMES_HOME/SOUL.md

# 5. Start Hermes from this folder so it picks up AGENTS.md
hermes
```

Notes:

- **Run Hermes from the repo folder.** Hermes loads `AGENTS.md` from the working directory. Kai's instructions and the `skills/...` paths in them are relative to that folder. If you'd rather keep Kai separate from your other Hermes use, create a dedicated profile with `hermes profile create kai` and copy `SOUL.md` into that profile's home.
- **Skills work in place.** Kai's `AGENTS.md` tells the agent to run the scripts under `skills/`, so nothing has to be installed. If you also want them as slash commands (`/strava`, `/trainingpeaks` and so on), copy or symlink the four folders in `skills/` into `~/.hermes/skills/`, or add the repo's `skills/` folder as an external skill directory (see the Hermes docs).
- **Skill docs mention `{baseDir}`.** That placeholder is an OpenClaw convention meaning "this skill's folder". If Hermes doesn't substitute it, tell Kai the skills live in `./skills/<name>`, or use the paths shown in `AGENTS.md`.
- **Memory.** Kai's own memory (`USER.md`, `MEMORY.md`, `memory/`) is plain files in the repo and is read and written through Hermes's file tools. Hermes also has its own built-in memory, and the two will coexist. To keep things simple, tell Kai to keep athlete details in `USER.md` and `memory/`.
- **Credentials** are set up per skill, exactly as in the OpenClaw steps above. They live in `~/.config/<service>/`, independent of the agent runtime.
- **OpenClaw-only bits** (the `openclaw agents add` command, heartbeat polling and push-notification delivery) don't apply. Use Hermes's own scheduler if you want proactive checks.

## Repository layout

```
AGENTS.md          Kai's operating manual: session routine, roles, analysis format, quirks
SOUL.md            Personality and boundaries
IDENTITY.md        Name and vibe
SECURITY.md        Hard rules on credentials
templates/         Starter USER.md and MEMORY.md
requirements.txt   Pinned Python packages for the Garmin skill
data/              Example nutrition log
skills/
  endurance-training-coach/   Plan creation: assessment, zones, load, periodization, workouts, race day
  trainingpeaks/              TrainingPeaks CLI (pure Python stdlib)
  garmin-health-analysis/     Garmin Connect metrics and HTML dashboards
  strava/                     Strava activities, laps, streams, gear and tyre mileage
```

## Privacy

- Your credentials and data stay on your machine. Nothing is sent anywhere except the calls to TrainingPeaks / Garmin / Strava and to the language model your OpenClaw is configured with. That model provider will see the training data Kai reads.
- `.gitignore` excludes `USER.md`, `MEMORY.md`, `memory/`, your nutrition log and your tyre ledger, so you won't accidentally push your own data if you fork this.
- TrainingPeaks and Garmin access use unofficial, reverse-engineered interfaces (cookie auth and the community `garminconnect` library). They can break or be rate-limited, and their terms may not endorse this use. Strava uses the official API.

## Customizing

Kai's behavior lives in `AGENTS.md`, `SOUL.md` and `IDENTITY.md`. Edit them: change the tone, drop the nutrition section, add your own rules. When you correct Kai ("don't do X, because Y"), it records that as a `feedback` memory so the correction sticks.

## Credits and license

The skills are also published individually, and the coaching skill is adapted from [endurance-coach](https://github.com/shiv19/endurance-coach-skill) by shiv19 (MIT). Garmin skill originally by EversonL. See each skill's README for details.

Licensed under GPL v3. See [LICENSE](LICENSE).
