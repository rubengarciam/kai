# Architecture, layout and privacy

## How it works

```
You (chat) ──► Kai (your agent runtime)
                 │  reads AGENTS.md, SOUL.md, USER.md, memory/
                 │
                 ├─ skills/trainingpeaks ─────► TrainingPeaks  (load, workouts, PRs, weight)
                 ├─ skills/garmin-health-analysis ► Garmin Connect (sleep, HRV, readiness)
                 ├─ skills/strava ────────────► Strava         (laps, streams, gear)
                 ├─ skills/gear-maintenance ──► chain wax + tyre ledgers (odometers from Strava or by hand)
                 └─ skills/endurance-training-coach  (zones, periodization, workouts, race day)
```

Data priority when sources overlap: TrainingPeaks for load, Garmin for recovery, Strava for lap-level detail. You don't need all three. Kai uses what's configured and falls back to asking you questions for the rest.

Memory is plain markdown in `memory/`, so it survives model or runtime changes and you can read or edit it yourself.

## Repository layout

```
AGENTS.md          Kai's operating manual (for the agent): session routine, roles, analysis format, quirks
CLAUDE.md          Imports AGENTS.md for Claude Code
SOUL.md            Personality and boundaries
IDENTITY.md        Name and vibe
CREDENTIALS.md     Hard rules on credentials (for the agent)
SECURITY.md        How to report a vulnerability in this repo (for people, not the agent)
README.md          Front door: what Kai is, capabilities, quick start
docs/              Installation, running Kai per agent, upgrading, features, this page
CONTRIBUTING.md    Branches, pull requests, tests, releases
CHANGELOG.md       What changed in each release
.github/           Pull request and issue templates
templates/         Starter USER.md and MEMORY.md
requirements.txt   Python packages for the Garmin skill (garminconnect 0.3.x, Python 3.12+)
tests/             Offline tests: Garmin login, chain wax log, tyre ledger, docs checks, repo checks
.claude/skills/    Symlinks to skills/ for Claude Code
.agents/skills/    Symlinks to skills/ for Codex
data/              Example nutrition log
skills/
  endurance-training-coach/   Plan creation: assessment, zones, load, periodization, workouts, race day
  trainingpeaks/              TrainingPeaks CLI (pure Python stdlib)
  garmin-health-analysis/     Garmin Connect metrics and HTML dashboards
  strava/                     Strava activities, laps, streams and gear mileage
  gear-maintenance/           Chain wax log and tyre ledgers (odometers from Strava or by hand)
```

## Customizing

Kai's behavior lives in `AGENTS.md`, `SOUL.md` and `IDENTITY.md`. Edit them: change the tone, drop the nutrition section, add your own rules. When you correct Kai ("don't do X, because Y"), it records that as a `feedback` memory so the correction sticks.

## Privacy

- Your credentials and data stay on your machine. Nothing is sent anywhere except the calls to TrainingPeaks / Garmin / Strava and to the language model your agent runtime is configured with. That model provider will see the training data Kai reads.
- Kai never stores your Garmin password. `login` asks for it on the terminal, uses it once, and keeps only the session tokens (`garmin_tokens.json`, readable by you alone). There is no `--password` flag, so the password can't end up in shell history, and Kai's instructions tell the agent never to ask for it in chat.
- `.gitignore` excludes `USER.md`, `MEMORY.md`, `memory/`, your nutrition log, your tyre ledger and your chain wax ledger, so you won't accidentally push your own data if you fork this.
- TrainingPeaks and Garmin access use unofficial, reverse-engineered interfaces (cookie auth and the community `garminconnect` library). They can break or be rate-limited, and their terms may not endorse this use. Strava uses the official API.
