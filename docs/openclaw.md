# Running Kai on OpenClaw

Kai was built on [OpenClaw](https://docs.openclaw.ai), so this is the reference setup. Check the [requirements](installation.md#requirements) first (OpenClaw itself needs Node.js 24.16+ or 26.1+, which its installer sets up).

## 1. Get the workspace

```bash
git clone https://github.com/rubengarciam/kai.git ~/.openclaw/workspace-kai
openclaw agents add kai --workspace ~/.openclaw/workspace-kai
```

Bind the agent to a channel with `--bind` if you want to chat with it there (see `openclaw agents --help`).

## 2. Tell Kai about yourself

```bash
cd ~/.openclaw/workspace-kai
cp templates/USER.md USER.md
cp templates/MEMORY.md MEMORY.md
```

Fill in `USER.md` (thresholds, goals, race calendar, injuries, whether you have a coach). Or skip this and say hello: on first contact Kai interviews you and writes it for you.

## 3. Install the Python packages and connect your data

Follow [Installation](installation.md): the Python packages (Garmin only), then each data source, then the optional gear maintenance step. Run the commands from the workspace folder.

## What OpenClaw adds

Chat-app delivery, heartbeat polling (proactive checks) and push notifications are OpenClaw features. Kai's memory works on any runtime, because it is plain files.
