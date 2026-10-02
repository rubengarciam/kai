# Contributing

Thanks for helping. Bugs and plans are tracked in [the issues](https://github.com/rubengarciam/kai/issues); issues labelled `help wanted` are good places to start.

## Set up

```bash
git clone https://github.com/rubengarciam/kai.git && cd kai
python3 -m venv .venv                      # Python 3.12+ (see docs/installation.md for uv on older systems)
.venv/bin/pip install -r requirements.txt
```

## Run the tests

They are offline (no network, no accounts) and must pass before you open a PR:

```bash
.venv/bin/python3 -m unittest discover -s tests -v
```

A test that needs a temporary folder uses the `make_temp_dir()` helper defined at the top of the existing test files, which removes it when the run ends; calling `tempfile.mkdtemp()` directly fails a hygiene test.

They cover the Garmin login, the chain wax and tyre helpers, the docs (every documented path and link exists) and repo hygiene (the right files are tracked, personal ones are ignored).

## Branches and pull requests

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
- A commit that changes behaviour comes with a test. Keep a change and its docs in the same PR.
- CI (`.github/workflows/ci.yml`) runs on every push to main and every pull request: syntax and `shellcheck` for the scripts, then the unit tests on Python 3.12 and 3.13, which also checks that every Python script prints its usage on `--help`. Run the same locally with `.venv/bin/python3 -m unittest discover -s tests`. A weekly run on main catches upstream dependency changes.

## Who an issue is assigned to

The assignee is whoever has the next move. New issues are assigned automatically to [@gertybot](https://github.com/gertybot), the assistant that maintains this repo. When an issue needs a decision or an action from [@rubengarciam](https://github.com/rubengarciam) (the owner), it is reassigned to him, and goes back when he has answered. Every new pull request gets @gertybot as assignee and @rubengarciam as reviewer, because he reviews and merges them. If you open an issue or a pull request, you don't need to assign anyone.

Nobody is hard-coded in the workflows. They read the repository variables `ISSUE_ASSIGNEE` (new issues), `PR_ASSIGNEE` and `PR_REVIEWER` (new pull requests), set under Settings > Secrets and variables > Actions > Variables. Variables are not copied to forks, so a fork assigns nobody until its owner sets them. To use this setup in your own copy, enable Actions and set the variables to your own login (or leave them unset).

## Keep personal data out

Everything you push is public: code, issues, PR comments, commit messages. Never include real tokens, passwords, cookies, athlete IDs, Strava gear IDs, or your own mileage and training numbers. Describe results ("matched") instead of quoting them. The repo-hygiene test checks that personal files are ignored, but it can't read your comments.

## Adding a skill

A skill is a folder under `skills/<name>/`:

- `SKILL.md` with `name` and `description` frontmatter (put the trigger words first), and a `README.md`.
- Commands in the docs written as paths from the repo root (`skills/<name>/scripts/...`), never a placeholder.
- Credentials in `~/.config/<service>/` with `600` permissions, never in the repo. Personal data files (ledgers, logs) go in `.gitignore`, anchored to the repo root, with an `*.example.*` file checked in.
- Offline tests in `tests/`. Then list the skill in `AGENTS.md`, add symlinks in `.claude/skills/` and `.agents/skills/`, and add it to the README's skills table and `docs/architecture.md`.

Prefer official or clearly documented interfaces over reverse-engineered ones, and say in the skill's README when an interface is unofficial.

## Documentation

Each command lives in exactly one place, the skill's README; other pages link to it instead of repeating it. The README is the front door and stays short: put detail in `docs/`. `AGENTS.md` is written for the agent, not for people.

## Releases

Releases are tags on `main` named `vMAJOR.MINOR.PATCH`, published on GitHub with notes. A change that breaks documented commands, paths or Python requirements bumps the major version, and the notes say how to upgrade. Add a line to [CHANGELOG.md](CHANGELOG.md) in the PR that changes behaviour.
