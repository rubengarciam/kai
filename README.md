# Kai 💪 — an AI endurance coach

Kai is an AI coaching agent for triathletes, runners, cyclists and swimmers. It connects to the platforms you already train with (TrainingPeaks, Garmin Connect, Strava), reads your actual data, and does what a good coach does with it: analyzes your sessions, tracks fitness and fatigue, watches recovery, and, if you don't have a human coach, builds periodized training plans for your races.

It's built as an [OpenClaw](https://docs.openclaw.ai) agent workspace: a folder of plain markdown instructions plus four skills. There is no server or app to deploy. You point an agent at this folder and chat with it in whatever channel your OpenClaw is connected to.

> Kai is a coaching assistant, not a doctor. It will flag things that look medical and tell you to see a professional.

## What Kai does

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

## Setup

**You need:** a working [OpenClaw](https://docs.openclaw.ai) install, Python 3, and an account on at least one of TrainingPeaks, Garmin Connect or Strava.

### 1. Get the workspace

```bash
git clone https://github.com/gertybot/kai.git ~/.openclaw/workspace-kai
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

### 3. Connect your data sources

Each skill has its own setup guide. Credentials are stored on your machine under `~/.config/<service>/`.

| Source | What you need | Guide |
| ------ | ------------- | ----- |
| TrainingPeaks | Your `Production_tpAuth` browser cookie (no API key) | [skills/trainingpeaks](skills/trainingpeaks/README.md) |
| Garmin Connect | `pip3 install garminconnect fitparse gpxpy`, then a one-time login | [skills/garmin-health-analysis](skills/garmin-health-analysis/README.md) |
| Strava | A free Strava API app (client ID and secret) and one OAuth authorization | [skills/strava](skills/strava/README.md) |

Optional gear tracking: `cp skills/strava/data/tyres.example.json skills/strava/data/tyres.json` and edit it.

### 4. Start talking

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

## Repository layout

```
AGENTS.md          Kai's operating manual: session routine, roles, analysis format, quirks
SOUL.md            Personality and boundaries
IDENTITY.md        Name and vibe
SECURITY.md        Hard rules on credentials
templates/         Starter USER.md and MEMORY.md
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
