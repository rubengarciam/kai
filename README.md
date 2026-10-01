# Kai — an AI endurance coach

Kai is an AI coaching agent for triathletes, runners, cyclists and swimmers. It connects to the platforms you already train with (TrainingPeaks, Garmin Connect, Strava), reads your actual data, and does what a good coach does with it: analyzes your sessions, tracks fitness and fatigue, watches recovery, and, if you don't have a human coach, builds periodized training plans for your races.

Kai is a folder of plain markdown instructions plus five skills, using two open conventions: `AGENTS.md` for instructions and `SKILL.md` for skills. There is no server or app to deploy: you point an agent at this folder and chat with it. It was built on [OpenClaw](https://docs.openclaw.ai) and also works with [Claude Code](docs/claude-code-codex.md) (tested). [Codex](docs/claude-code-codex.md) and [Hermes Agent](docs/hermes.md) should work too (untested, based on their docs).

> Kai is a coaching assistant, not a doctor. It will flag things that look medical and tell you to see a professional.

## What Kai does

| Capability | What you get | Needs |
| ---------- | ------------ | ----- |
| **Workout analysis** | Overall read, planned-vs-actual table and lap-by-lap breakdown; data is read before your comments | TrainingPeaks, plus Strava for laps and Garmin for recovery context |
| **Fitness and fatigue tracking** | CTL / ATL / TSB, weekly TSS, form for race day | TrainingPeaks |
| **Recovery monitoring** | HRV, resting HR, sleep, Body Battery and readiness trends read alongside load | Garmin |
| **Activity files and dashboards** | Download an activity (FIT, TCX or GPX) and ask for your heart rate, pace or power at any distance or time; TCX also covers indoor rides whose FIT file can't be decoded. Garmin dashboards are single files that work offline | Garmin |
| **Training plans** | Periodized plans (base, build, peak, taper) with zones, paces, workouts and a race-day plan, validated with you first | Any one data source, or just a chat |
| **Analyst mode** | Interprets data and preps questions for your human coach; never overrides the plan | Any data source |
| **Gear tracking** | Live shoe and bike mileage, per-wheelset tyre wear with commands to fit, replace and retire tyre sets, replacement and maintenance alerts | Strava |
| **Chain wax log** | A ledger of waxes per bike, km since last wax, and DUE SOON / DUE / OVERDUE alerts (early first re-wax, then a full interval) | Strava for odometers; manual bikes supported |
| **Nutrition and weight** | Log food and weight in chat; deficits paced to training load; checks tomorrow's session first | Optional; weight syncs to TrainingPeaks |
| **Race notes** | Race-specific pacing, fueling and taper plans saved for later chats | Nothing |
| **Proactive checks** | Watches for bad recovery trends, upcoming key sessions and gear thresholds | A runtime with heartbeats or scheduling |

Kai reads the numbers *before* it reads your comments: if you say the run felt easy and the heart rate says otherwise, it tells you. [More detail on each capability](docs/features.md).

## How it works

```
You (chat) ──► Kai (your agent runtime)
                 │  reads AGENTS.md, SOUL.md, USER.md, memory/
                 │
                 ├─ skills/trainingpeaks ─────► TrainingPeaks  (load, workouts, PRs, weight)
                 ├─ skills/garmin-health-analysis ► Garmin Connect (sleep, HRV, readiness, activity files)
                 ├─ skills/strava ────────────► Strava         (laps, streams, gear)
                 ├─ skills/gear-maintenance ──► chain wax + tyre ledgers (odometers from Strava or by hand)
                 └─ skills/endurance-training-coach  (zones, periodization, workouts, race day)
```

You don't need all the data sources: Kai uses what's configured and asks you questions for the rest. Memory is plain markdown, so it survives model or runtime changes. More in [architecture and privacy](docs/architecture.md).

## Quick start

Kai runs on Linux or macOS (Windows via WSL). Check the [requirements](docs/installation.md#requirements) first.

**1. Get Kai**

```bash
git clone https://github.com/rubengarciam/kai.git
cd kai
```

**2. Start it in your agent, from this folder**

| Agent | How | Guide |
| ----- | --- | ----- |
| OpenClaw (the reference setup) | `openclaw agents add kai --workspace <this folder>` | [docs/openclaw.md](docs/openclaw.md) |
| Claude Code | `claude` | [docs/claude-code-codex.md](docs/claude-code-codex.md) |
| Codex | `codex` | [docs/claude-code-codex.md](docs/claude-code-codex.md) |
| Hermes Agent | `hermes` (after copying `SOUL.md`) | [docs/hermes.md](docs/hermes.md) |

**3. Tell Kai about yourself**

```bash
cp templates/USER.md USER.md
cp templates/MEMORY.md MEMORY.md
```

Fill in `USER.md` (thresholds, goals, race calendar, injuries, whether you have a coach), or skip it and say hello: on first contact Kai interviews you and writes it for you.

**4. Connect your data sources** (any subset)

| Source | What you need | Guide |
| ------ | ------------- | ----- |
| TrainingPeaks | Your `Production_tpAuth` browser cookie (no API key) | [skills/trainingpeaks](skills/trainingpeaks/README.md) |
| Garmin Connect | Python 3.12+ and the packages in `requirements.txt`, then a one-time login you run yourself | [installation](docs/installation.md#python-packages-garmin-only) |
| Strava | A free Strava API app (client ID and secret) and one OAuth authorization | [skills/strava](skills/strava/README.md) |

Optional: [chain wax and tyre tracking](docs/installation.md#gear-maintenance-optional-chain-wax-and-tyres).

**5. Start talking** ([more prompts](docs/features.md#things-to-ask))

> "Analyze this morning's run."
>
> "How's my training load? Am I ready to add intensity?"
>
> "I have a marathon on 2026-11-15. Review my fitness and build me a plan."
>
> "I waxed the road bike today. When is it due again?"

## Documentation

| | |
| --- | --- |
| [Installation](docs/installation.md) | Requirements, Python packages, connecting data sources, gear maintenance |
| [OpenClaw](docs/openclaw.md), [Claude Code and Codex](docs/claude-code-codex.md), [Hermes](docs/hermes.md) | Running Kai in each agent |
| [Features in detail](docs/features.md) | What each capability does |
| [Architecture and privacy](docs/architecture.md) | How it works, repository layout, customizing, what leaves your machine |
| [Upgrading](docs/upgrading.md) | v1.x to v2, gear maintenance moved, `SECURITY.md` renamed to `CREDENTIALS.md` |
| [Changelog](CHANGELOG.md) | What changed in each release |
| [Contributing](CONTRIBUTING.md) | Branches, pull requests, tests, releases |
| [Security policy](SECURITY.md) | How to report a vulnerability privately |
| Skills | [trainingpeaks](skills/trainingpeaks/README.md), [garmin-health-analysis](skills/garmin-health-analysis/README.md), [strava](skills/strava/README.md), [gear-maintenance](skills/gear-maintenance/README.md), [endurance-training-coach](skills/endurance-training-coach/README.md) |

## Upgrading from v1.x

v2.0 changed the Garmin login: it needs Python 3.12+ and you log in once more. Steps are in [docs/upgrading.md](docs/upgrading.md).

## Privacy

- Your credentials and data stay on your machine. Nothing is sent anywhere except the calls to TrainingPeaks / Garmin / Strava and to the language model your agent runtime is configured with, which sees the training data Kai reads.
- Kai never stores your Garmin password: `login` asks for it on the terminal and keeps only session tokens. Kai's instructions tell the agent never to ask for it in chat.
- Activity files you download (FIT, TCX, GPX) contain GPS tracks. Kai saves them readable only by you, and Garmin dashboards are generated locally with Chart.js bundled, so viewing one sends nothing anywhere.
- TrainingPeaks and Garmin access use unofficial interfaces (cookie auth and the community `garminconnect` library) and can break or be rate-limited. Strava uses the official API.

More in [architecture and privacy](docs/architecture.md#privacy).

## Contributing

Bugs and plans are tracked in [the issues](https://github.com/rubengarciam/kai/issues); issues labelled `help wanted` are good places to start. See [CONTRIBUTING.md](CONTRIBUTING.md) for branches, tests and releases. Found a security problem? Please report it privately: see [SECURITY.md](SECURITY.md).

## Credits and license

The skills are also published individually, and the coaching skill is adapted from [endurance-coach](https://github.com/shiv19/endurance-coach-skill) by shiv19 (MIT). Garmin skill originally by EversonL. Garmin dashboards bundle [Chart.js](https://www.chartjs.org) and its `@kurkle/color` dependency (both MIT), with their licences in `skills/garmin-health-analysis/assets/`. See each skill's README for details.

Licensed under GPL v3. See [LICENSE](LICENSE).
