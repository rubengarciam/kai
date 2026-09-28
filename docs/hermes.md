# Running Kai with Hermes Agent

Kai also works with [Hermes Agent](https://hermes-agent.nousresearch.com) (Nous Research). Hermes reads `AGENTS.md` from the working directory, uses the same `SKILL.md` skill format, and keeps its identity in a global `SOUL.md`. This setup is based on Hermes's documentation. It has not been tested against a live Hermes install yet, so report any rough edges.

```bash
# 1. Get the workspace anywhere you like
git clone https://github.com/rubengarciam/kai.git ~/kai
cd ~/kai

# 2. Personalize
cp templates/USER.md USER.md
cp templates/MEMORY.md MEMORY.md

# 3. Garmin only: install the Python packages (Python 3.12+, see [Requirements](installation.md#requirements))
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 4. Give Kai its personality (Hermes only reads SOUL.md from its home directory)
cp SOUL.md ~/.hermes/SOUL.md     # or $HERMES_HOME/SOUL.md

# 5. Start Hermes from this folder so it picks up AGENTS.md
hermes
```

Notes:

- **Run Hermes from the repo folder.** Hermes loads `AGENTS.md` from the working directory. Kai's instructions and the `skills/...` paths in them are relative to that folder. If you'd rather keep Kai separate from your other Hermes use, create a dedicated profile with `hermes profile create kai` and copy `SOUL.md` into that profile's home.
- **Skills work in place.** Kai's `AGENTS.md` tells the agent to run the scripts under `skills/`, so nothing has to be installed. If you also want them as slash commands (`/strava`, `/trainingpeaks` and so on), copy or symlink the folders in `skills/` into `~/.hermes/skills/`, or add the repo's `skills/` folder as an external skill directory (see the Hermes docs).
- **Memory.** Kai's own memory (`USER.md`, `MEMORY.md`, `memory/`) is plain files in the repo and is read and written through Hermes's file tools. Hermes also has its own built-in memory, and the two will coexist. To keep things simple, tell Kai to keep athlete details in `USER.md` and `memory/`.
- **Credentials** are set up per skill, exactly as in [Installation](installation.md#connect-your-data-sources). They live in `~/.config/<service>/`, independent of the agent runtime.
- **OpenClaw-only bits** (the `openclaw agents add` command, heartbeat polling and push-notification delivery) don't apply. Use Hermes's own scheduler if you want proactive checks.
