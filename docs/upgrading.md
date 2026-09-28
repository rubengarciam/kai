# Upgrading

Release-by-release changes are in the [changelog](../CHANGELOG.md). This page covers the upgrades that need you to do something.

## From v1.x to v2.0 (Garmin login)

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

# 1. Python 3.12+ (check with `python3 --version`; if older, install uv as in [Installation](installation.md#python-packages-garmin-only))
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

## Gear maintenance moved (v2.2)

Chain waxing (`chain-wax.py`) and tyre tracking (`tyre-mileage.sh`) moved out of the Strava skill into their own skill, `skills/gear-maintenance/`, because they aren't Strava-specific (a bike without Strava tracking works too). Update any commands you use from `skills/strava/scripts/` to `skills/gear-maintenance/scripts/`, and move your ledgers from `skills/strava/data/` to `skills/gear-maintenance/data/`:

```bash
mkdir -p skills/gear-maintenance/data
mv skills/strava/data/chain-wax.json skills/strava/data/tyres.json skills/gear-maintenance/data/ 2>/dev/null
```

A ledger left in the old place still works, with a notice, so nothing breaks in the meantime.
