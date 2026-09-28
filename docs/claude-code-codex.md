# Running Kai with Claude Code or Codex

Both read the same files Kai is built from, so no conversion is needed. The repo includes what each tool looks for:

| File | For | What it does |
| ---- | --- | ------------ |
| `AGENTS.md` | Codex (native), Claude Code (via `CLAUDE.md`) | Kai's operating manual |
| `CLAUDE.md` | Claude Code | One line, `@AGENTS.md`, which imports the manual (Claude Code reads `CLAUDE.md`, not `AGENTS.md`) |
| `.claude/skills/` | Claude Code | Symlinks to the five skills in `skills/` |
| `.agents/skills/` | Codex | Symlinks to the same five skills |

```bash
# 1. Get the workspace
git clone https://github.com/rubengarciam/kai.git ~/kai
cd ~/kai

# 2. Personalize
cp templates/USER.md USER.md
cp templates/MEMORY.md MEMORY.md

# 3. Garmin only: install the Python packages (Python 3.12+, see [Requirements](installation.md#requirements))
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 4. Start your tool from this folder
claude      # Claude Code
codex       # Codex
```

Then [connect your data sources](installation.md#connect-your-data-sources) and say hello.

Notes:

- **Start the tool from the repo folder.** Both load instructions and skills relative to the working directory. Kai's `AGENTS.md` tells the agent to read `SOUL.md`, `USER.md` and its memory files itself, so nothing else needs installing.
- **Tested with Claude Code only.** In a scratch copy of the repo, Claude Code picked up `AGENTS.md` through `CLAUDE.md`, took on the Kai role, and listed the skills. Codex is based on its documentation (it reads `AGENTS.md` and scans `.agents/skills/`) and hasn't been run against this repo.
- **Symlinks need Linux or macOS** (or WSL on Windows). If your checkout has no symlinks, the skills still work: `AGENTS.md` refers to them by their `skills/` paths.
- **What you don't get:** these are terminal coding tools, so you chat with Kai in the terminal. Heartbeat checks, push notifications and chat-app delivery are OpenClaw features. Memory still works, because it's plain files.
- **Permissions:** Kai runs scripts and writes files (`USER.md`, `memory/`), so the tool will ask you to approve those actions unless you've configured it otherwise.
