# Installation

Everything you need to get Kai's data connections working. For the short version see the [quick start](../README.md#quick-start); to run Kai in a particular agent, see [OpenClaw](openclaw.md), [Claude Code and Codex](claude-code-codex.md) or [Hermes](hermes.md).

## Requirements

Kai runs on **Linux or macOS** (on Windows, use WSL). Verified on Raspberry Pi OS (Debian) with Python 3.13. The Garmin skill needs Python 3.12 or newer; TrainingPeaks and Strava work on older Python 3 versions.

| Requirement | Version | Needed for | How to get it |
| ----------- | ------- | ---------- | ------------- |
| Agent runtime | One of: [OpenClaw](https://docs.openclaw.ai) (needs Node.js 24.16+ or 26.1+, which its installer sets up), [Claude Code](https://code.claude.com), [Codex](https://developers.openai.com/codex) or [Hermes Agent](https://hermes-agent.nousresearch.com) | Everything | Follow the runtime's install guide |
| `git` | any | Cloning this repo | `sudo apt install git` / `brew install git` |
| `python3` | **3.12 or newer** for Garmin (TrainingPeaks needs 3.6+) | Garmin and TrainingPeaks skills | Check with `python3 --version`. If it's older, use `uv` (see [Python packages](#python-packages-garmin-only)) |
| `python3-venv` | matches Python | Isolating the Garmin packages | Debian/Ubuntu/Raspberry Pi OS: `sudo apt install python3-venv`. macOS: included with Python |
| `curl` and `bash` | any | Strava skill | Preinstalled on Linux and macOS |
| Python packages | `garminconnect` 0.3.x, `fitparse`, `gpxpy` (listed in `requirements.txt`) | Garmin skill only | See [Python packages](#python-packages-garmin-only) |
| Internet access | | All data sources; Garmin dashboards also load Chart.js from a CDN | |
| Accounts | at least one of TrainingPeaks, Garmin Connect, Strava | Data | You may skip any you don't use |

The TrainingPeaks and gear-maintenance skills use only the Python standard library, and the Strava skill only needs `curl` and Python. **Only Garmin needs extra packages.** Live odometers for gear maintenance come from the Strava skill's credentials; bikes not on Strava can be tracked by hand.



## Python packages (Garmin only)

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

## Connect your data sources

Each skill has its own setup guide (linked below). You can connect any subset. Credentials are stored on your machine under `~/.config/<service>/`.

| Source | What you need | Guide |
| ------ | ------------- | ----- |
| TrainingPeaks | Your `Production_tpAuth` browser cookie (no API key) | [skills/trainingpeaks](../skills/trainingpeaks/README.md) |
| Garmin Connect | The [Python packages](#python-packages-garmin-only), then a one-time login (`garmin_auth.py login`, shown above) | [skills/garmin-health-analysis](../skills/garmin-health-analysis/README.md) |
| Strava | A free Strava API app (client ID and secret) and one OAuth authorization | [skills/strava](../skills/strava/README.md) |

## Gear maintenance (optional): chain wax and tyres

The `gear-maintenance` skill tracks when each bike's chain was last waxed and how far your tyres have run. Odometers come from Strava (set it up above), or you give them by hand for a bike that isn't on Strava, like a partner's. Skip this step if you don't want it.

```bash
# Chain wax: add each bike, record its last wax, then get the report
python3 skills/gear-maintenance/scripts/chain-wax.py add-bike road --name "Road bike" --gear-id <your Strava bike id>
python3 skills/gear-maintenance/scripts/chain-wax.py log road --odometer <km at your last wax> --date <YYYY-MM-DD> --product "Hot wax"
python3 skills/gear-maintenance/scripts/chain-wax.py report

# A bike that isn't on Strava
python3 skills/gear-maintenance/scripts/chain-wax.py add-bike partner --name "Partner's bike" --manual --odometer <km>

# Tyres: add each wheelset, fit its tyres, then get the mileage report
python3 skills/gear-maintenance/scripts/tyres.py add-wheelset road_wheels --name "Road wheels" --usual-bike "Road bike" --gear-id <your Strava bike id>
python3 skills/gear-maintenance/scripts/tyres.py add-set road_wheels --model "GP5000 28mm" --date <YYYY-MM-DD> --replace-at 4000
bash skills/gear-maintenance/scripts/tyre-mileage.sh

# Later, when you fit new tyres (retires the old set as of the same date)
python3 skills/gear-maintenance/scripts/tyres.py add-set road_wheels --model "GP5000 28mm" --replace
```

Find your Strava bike ids with `bash skills/strava/scripts/gear-mileage.sh`. From then on Kai runs the report itself whenever bike mileage or maintenance comes up, and you can just tell it "I waxed the road bike today" to log it. Your ledgers are plain files in `skills/gear-maintenance/data/`, git-ignored so they never get committed. See [skills/gear-maintenance](../skills/gear-maintenance/README.md) for the statuses, the default intervals and how tyre mileage treats indoor rides.
