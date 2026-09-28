# Kai — an AI endurance coach

Kai is an AI coaching agent for triathletes, runners, cyclists and swimmers. It connects to the platforms you already train with (TrainingPeaks, Garmin Connect, Strava), reads your actual data, and does what a good coach does with it: analyzes your sessions, tracks fitness and fatigue, watches recovery, and, if you don't have a human coach, builds periodized training plans for your races.

Kai is a folder of plain markdown instructions plus four skills, using two open conventions: `AGENTS.md` for instructions and `SKILL.md` for skills. There is no server or app to deploy. You point an agent runtime at this folder and chat with it. It was built on [OpenClaw](https://docs.openclaw.ai) and also works with [Claude Code](#using-kai-with-claude-code-or-codex) (tested). [Codex](#using-kai-with-claude-code-or-codex) and [Hermes Agent](#using-kai-with-hermes) should work too (untested, based on their docs).

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
| **Chain wax log** | A ledger of waxes per bike, km since last wax, and DUE SOON / DUE / OVERDUE alerts (early first re-wax, then a full interval) | Strava for odometers; manual bikes supported |
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
- **Chain wax log**: `skills/gear-maintenance/scripts/chain-wax.py` keeps a ledger of waxes per bike (date, odometer, product, whether the chain was degreased) and reads live odometers from Strava. `report` shows km since the last wax and the next-due odometer, and flags `DUE SOON` (last 10% before the minimum), `DUE` and `OVERDUE`. By default a hot wax is followed by an early re-wax at 150-250 km (the first coating is thin), then 450-500 km; drip lube is 200-300 km; you can set any interval. Bikes without Strava tracking, like a partner's, work too: you give their odometer by hand and the report tells you when the reading is getting old. Kai runs the script instead of doing the arithmetic, so the answer is the same every session.
- **Nutrition and weight tracking**: log food and weight in plain chat. Weight goes to TrainingPeaks, food to a local CSV. Kai tracks kcal and protein, paces deficits to your training load, and checks tomorrow's session before recommending a low-carb day.
- **Race notes**: race-specific tactics, pacing and taper plans are saved to memory so they're available in any later chat.
- **Proactive checks**: with heartbeats enabled, Kai can watch for things like a recovery trend turning bad or a gear threshold approaching.

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

## Requirements

Kai runs on **Linux or macOS** (on Windows, use WSL). Verified on Raspberry Pi OS (Debian) with Python 3.13. The Garmin skill needs Python 3.12 or newer; TrainingPeaks and Strava work on older Python 3 versions.

| Requirement | Version | Needed for | How to get it |
| ----------- | ------- | ---------- | ------------- |
| Agent runtime | One of: [OpenClaw](https://docs.openclaw.ai) (needs Node.js 24.16+ or 26.1+, which its installer sets up), [Claude Code](https://code.claude.com), [Codex](https://developers.openai.com/codex) or [Hermes Agent](https://hermes-agent.nousresearch.com) | Everything | Follow the runtime's install guide |
| `git` | any | Cloning this repo | `sudo apt install git` / `brew install git` |
| `python3` | **3.12 or newer** for Garmin (TrainingPeaks needs 3.6+) | Garmin and TrainingPeaks skills | Check with `python3 --version`. If it's older, use `uv` (see step 3) |
| `python3-venv` | matches Python | Isolating the Garmin packages | Debian/Ubuntu/Raspberry Pi OS: `sudo apt install python3-venv`. macOS: included with Python |
| `curl` and `bash` | any | Strava skill | Preinstalled on Linux and macOS |
| Python packages | `garminconnect` 0.3.x, `fitparse`, `gpxpy` (listed in `requirements.txt`) | Garmin skill only | See "Install the Python packages" below |
| Internet access | | All data sources; Garmin dashboards also load Chart.js from a CDN | |
| Accounts | at least one of TrainingPeaks, Garmin Connect, Strava | Data | You may skip any you don't use |

The TrainingPeaks and gear-maintenance skills use only the Python standard library, and the Strava skill only needs `curl` and Python. **Only Garmin needs extra packages.** Live odometers for gear maintenance come from the Strava skill's credentials; bikes not on Strava can be tracked by hand.

> **Upgrading from v1.x?** The Garmin skill now needs Python 3.12+ and you have to log in to Garmin once more. See [Upgrading from v1.x](#upgrading-from-v1x).

## Setup

These steps are for OpenClaw. For other runtimes, see [Claude Code or Codex](#using-kai-with-claude-code-or-codex) and [Hermes](#using-kai-with-hermes); the Python and data source steps (3 and 4) are the same everywhere.

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

Skip this if you don't use Garmin. Create a virtual environment inside the Kai folder and install the packages:

```bash
cd ~/.openclaw/workspace-kai
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

If `python3 -m venv` fails with "ensurepip is not available", run `sudo apt install python3-venv` and retry.

**Python older than 3.12** (for example Debian 12 or Ubuntu 22.04): use [uv](https://docs.astral.sh/uv/) to get a 3.12 environment without touching the system Python:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

Kai's `AGENTS.md` tells the agent to run the Garmin scripts with `.venv/bin/python3` when the folder exists. Use the same interpreter when you run them yourself, for example:

```bash
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py login
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py status
```

`login` asks for your email and password on the terminal (the password is hidden and never stored; only session tokens are saved, readable by you alone). If your Garmin account uses two-factor authentication it asks for the code too. **Run login yourself, in your own terminal:** don't paste your password into a chat with the agent. For scripting, use `--password-stdin` or the `GARMIN_PASSWORD` variable.

### 4. Connect your data sources

Each skill has its own setup guide. Credentials are stored on your machine under `~/.config/<service>/`.

| Source | What you need | Guide |
| ------ | ------------- | ----- |
| TrainingPeaks | Your `Production_tpAuth` browser cookie (no API key) | [skills/trainingpeaks](skills/trainingpeaks/README.md) |
| Garmin Connect | The packages from step 3, then a one-time login (`garmin_auth.py login`, shown above) | [skills/garmin-health-analysis](skills/garmin-health-analysis/README.md) |
| Strava | A free Strava API app (client ID and secret) and one OAuth authorization | [skills/strava](skills/strava/README.md) |

### 5. Optional: gear maintenance (chain wax and tyres)

The `gear-maintenance` skill tracks when each bike's chain was last waxed and how far your tyres have run. Odometers come from Strava (set it up in step 4), or you give them by hand for a bike that isn't on Strava, like a partner's. Skip this step if you don't want it.

```bash
# Chain wax: add each bike, record its last wax, then get the report
python3 skills/gear-maintenance/scripts/chain-wax.py add-bike road --name "Road bike" --gear-id <your Strava bike id>
python3 skills/gear-maintenance/scripts/chain-wax.py log road --odometer <km at your last wax> --date <YYYY-MM-DD> --product "Hot wax"
python3 skills/gear-maintenance/scripts/chain-wax.py report

# A bike that isn't on Strava
python3 skills/gear-maintenance/scripts/chain-wax.py add-bike partner --name "Partner's bike" --manual --odometer <km>

# Tyres: copy the example, then edit wheelsets, Strava bike ids and fitted dates
cp skills/gear-maintenance/data/tyres.example.json skills/gear-maintenance/data/tyres.json
bash skills/gear-maintenance/scripts/tyre-mileage.sh
```

Find your Strava bike ids with `bash skills/strava/scripts/gear-mileage.sh`. From then on Kai runs the report itself whenever bike mileage or maintenance comes up, and you can just tell it "I waxed the road bike today" to log it. Your ledgers are plain files in `skills/gear-maintenance/data/`, git-ignored so they never get committed. See [skills/gear-maintenance](skills/gear-maintenance/README.md) for the statuses, the default intervals and how tyre mileage treats indoor rides.

### 6. Start talking

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
> "I waxed the road bike today. When is it due again?"
>
> "Log weight 72.4. Had oats and a protein shake for breakfast."

## Upgrading from v1.x

v2.0 changes how the Garmin skill logs in. TrainingPeaks, Strava and Kai's instructions are unchanged.

| What changed | Why it matters |
| ------------ | -------------- |
| `garminconnect` 0.3.x and **Python 3.12+** (was 0.2.x and 3.10+) | The old library needed the removed `garth` login. A plain `pip install garminconnect` gets 0.3.x, which the old scripts couldn't use |
| **Tokens are stored differently** (`garmin_tokens.json`) | Tokens saved by v1.x can't be reused. Log in once more |
| `login` **prompts** for the password (hidden) and the MFA code | The password never touches shell history or the process list, and is never stored |
| `--password` **is removed**, and a `password` in `config.json` is **ignored** (with a warning) | Passwords are no longer read from the command line or from disk. Use the prompt, `--password-stdin` or `GARMIN_PASSWORD` |
| Login **needs a terminal** | If there is none (an agent's shell), the script tells you to run it yourself instead of hanging |

To upgrade:

```bash
cd ~/.openclaw/workspace-kai        # or wherever you cloned Kai
git pull

# 1. Python 3.12+ (check with `python3 --version`; if older, install uv as in step 3 above)
# 2. Rebuild the virtual environment
rm -rf .venv
python3 -m venv .venv               # or: uv venv --python 3.12 .venv
.venv/bin/pip install -r requirements.txt    # with uv: uv pip install --python .venv/bin/python -r requirements.txt

# 3. Log in again, yourself, in a terminal
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py login
.venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py status
```

Afterwards:

- Delete the old `oauth1_token.json` and `oauth2_token.json` from `~/.config/garminconnect/` once everything works. `status` tells you when it finds them.
- Remove any `password` line from `~/.config/garminconnect/config.json` and any plaintext credentials file you created for the old flow.
- Anything of yours that calls the Garmin scripts (your own scripts, scheduled jobs, agent skills) must use `.venv/bin/python3` instead of the system `python3`, and must not pass `--password`.

### Gear maintenance moved (v2.2)

Chain waxing (`chain-wax.py`) and tyre tracking (`tyre-mileage.sh`) moved out of the Strava skill into their own skill, `skills/gear-maintenance/`, because they aren't Strava-specific (a bike without Strava tracking works too). Update any commands you use from `skills/strava/scripts/` to `skills/gear-maintenance/scripts/`, and move your ledgers from `skills/strava/data/` to `skills/gear-maintenance/data/`:

```bash
mkdir -p skills/gear-maintenance/data
mv skills/strava/data/chain-wax.json skills/strava/data/tyres.json skills/gear-maintenance/data/ 2>/dev/null
```

A ledger left in the old place still works, with a notice, so nothing breaks in the meantime.

## Using Kai with Claude Code or Codex

Both read the same files Kai is built from, so no conversion is needed. The repo includes what each tool looks for:

| File | For | What it does |
| ---- | --- | ------------ |
| `AGENTS.md` | Codex (native), Claude Code (via `CLAUDE.md`) | Kai's operating manual |
| `CLAUDE.md` | Claude Code | One line, `@AGENTS.md`, which imports the manual (Claude Code reads `CLAUDE.md`, not `AGENTS.md`) |
| `.claude/skills/` | Claude Code | Symlinks to the four skills in `skills/` |
| `.agents/skills/` | Codex | Symlinks to the same four skills |

```bash
# 1. Get the workspace
git clone https://github.com/rubengarciam/kai.git ~/kai
cd ~/kai

# 2. Personalize
cp templates/USER.md USER.md
cp templates/MEMORY.md MEMORY.md

# 3. Garmin only: install the Python packages (Python 3.12+, see Requirements)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 4. Start your tool from this folder
claude      # Claude Code
codex       # Codex
```

Then connect your data sources (step 4 of the setup above) and say hello.

Notes:

- **Start the tool from the repo folder.** Both load instructions and skills relative to the working directory. Kai's `AGENTS.md` tells the agent to read `SOUL.md`, `USER.md` and its memory files itself, so nothing else needs installing.
- **Tested with Claude Code only.** In a scratch copy of the repo, Claude Code picked up `AGENTS.md` through `CLAUDE.md`, took on the Kai role, and listed all four skills. Codex is based on its documentation (it reads `AGENTS.md` and scans `.agents/skills/`) and hasn't been run against this repo.
- **Symlinks need Linux or macOS** (or WSL on Windows). If your checkout has no symlinks, the skills still work: `AGENTS.md` refers to them by their `skills/` paths.
- **`{baseDir}` in the skill docs** is an OpenClaw placeholder for "this skill's folder". Claude Code and Codex don't substitute it, so the agent resolves it to `skills/<name>` on its own. If it stumbles, tell it so.
- **What you don't get:** these are terminal coding tools, so you chat with Kai in the terminal. Heartbeat checks, push notifications and chat-app delivery are OpenClaw features. Memory still works, because it's plain files.
- **Permissions:** Kai runs scripts and writes files (`USER.md`, `memory/`), so the tool will ask you to approve those actions unless you've configured it otherwise.

## Using Kai with Hermes

Kai also works with [Hermes Agent](https://hermes-agent.nousresearch.com) (Nous Research). Hermes reads `AGENTS.md` from the working directory, uses the same `SKILL.md` skill format, and keeps its identity in a global `SOUL.md`. This setup is based on Hermes's documentation. It has not been tested against a live Hermes install yet, so report any rough edges.

```bash
# 1. Get the workspace anywhere you like
git clone https://github.com/rubengarciam/kai.git ~/kai
cd ~/kai

# 2. Personalize
cp templates/USER.md USER.md
cp templates/MEMORY.md MEMORY.md

# 3. Garmin only: install the Python packages (Python 3.12+, see Requirements)
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
CLAUDE.md          Imports AGENTS.md for Claude Code
SOUL.md            Personality and boundaries
IDENTITY.md        Name and vibe
SECURITY.md        Hard rules on credentials
templates/         Starter USER.md and MEMORY.md
requirements.txt   Python packages for the Garmin skill (garminconnect 0.3.x, Python 3.12+)
tests/             Offline tests: Garmin login, chain wax log, and repo checks (right files tracked, personal ones ignored)
.claude/skills/    Symlinks to skills/ for Claude Code
.agents/skills/    Symlinks to skills/ for Codex
data/              Example nutrition log
skills/
  endurance-training-coach/   Plan creation: assessment, zones, load, periodization, workouts, race day
  trainingpeaks/              TrainingPeaks CLI (pure Python stdlib)
  garmin-health-analysis/     Garmin Connect metrics and HTML dashboards
  strava/                     Strava activities, laps, streams and gear mileage
  gear-maintenance/           Chain wax log and tyre wear ledgers (odometers from Strava or by hand)
```

## Privacy

- Your credentials and data stay on your machine. Nothing is sent anywhere except the calls to TrainingPeaks / Garmin / Strava and to the language model your agent runtime is configured with. That model provider will see the training data Kai reads.
- Kai never stores your Garmin password. `login` asks for it on the terminal, uses it once, and keeps only the session tokens (`garmin_tokens.json`, readable by you alone). There is no `--password` flag, so the password can't end up in shell history, and Kai's instructions tell the agent never to ask for it in chat.
- `.gitignore` excludes `USER.md`, `MEMORY.md`, `memory/`, your nutrition log, your tyre ledger and your chain wax ledger, so you won't accidentally push your own data if you fork this.
- TrainingPeaks and Garmin access use unofficial, reverse-engineered interfaces (cookie auth and the community `garminconnect` library). They can break or be rate-limited, and their terms may not endorse this use. Strava uses the official API.

## Customizing

Kai's behavior lives in `AGENTS.md`, `SOUL.md` and `IDENTITY.md`. Edit them: change the tone, drop the nutrition section, add your own rules. When you correct Kai ("don't do X, because Y"), it records that as a `feedback` memory so the correction sticks.

## Development and roadmap

Run the offline tests (no network or Garmin account needed) from the repo root, in the virtual environment:

```bash
.venv/bin/python3 -m unittest discover -s tests -v
```

Planned work and known bugs are tracked in [the issues](https://github.com/rubengarciam/kai/issues). Contributions are welcome: issues labelled `help wanted` are good places to start.

### Branches and pull requests

Work happens on short-lived branches cut from `main` and merged through a pull request, one PR per issue (put `Closes #N` in the description). Branches are deleted after they merge.

Name a branch `type/short-description`, in lowercase with hyphens:

| Prefix | For | Example |
| ------ | --- | ------- |
| `feat/` | a new capability | `feat/garmin-0.3-auth`, `feat/gear-maintenance-skill` |
| `fix/` | a bug fix | `fix/garmin-fit-zip` |
| `docs/` | README and other docs only | `docs/hermes-setup` |
| `test/` | tests and CI | `test/ci-smoke` |
| `refactor/` | restructuring without new behaviour | `refactor/strava-python-port` |
| `chore/` | housekeeping | `chore/bump-requirements` |

- Put the skill or area in the description (`garmin`, `strava`, `trainingpeaks`, `gear-maintenance`, `coach`), and use the matching **label** on the issue and PR to filter by skill. An issue number is welcome too: `feat/10-chain-wax-log`.
- Use the same type in the PR title, optionally with the area: `feat(garmin): support garminconnect 0.3.x`.
- Run the tests before opening the PR (command above); they must pass.
- Releases are tags on `main` named `vMAJOR.MINOR.PATCH`. A change that breaks documented commands, paths or Python requirements bumps the major version, and the release notes say how to upgrade.
- Keep personal data out of everything you push: issues, PR comments and commit messages included. The repo-hygiene test checks that personal files are ignored, but it can't read your comments.

## Credits and license

The skills are also published individually, and the coaching skill is adapted from [endurance-coach](https://github.com/shiv19/endurance-coach-skill) by shiv19 (MIT). Garmin skill originally by EversonL. See each skill's README for details.

Licensed under GPL v3. See [LICENSE](LICENSE).
