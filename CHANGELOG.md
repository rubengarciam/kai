# Changelog

The full notes for each release, with upgrade steps, are on the [releases page](https://github.com/rubengarciam/kai/releases). This is the short version. Versions follow [semantic versioning](https://semver.org/): a change that breaks documented commands, paths or Python requirements bumps the major version.

## Unreleased

- **Added: CI** ([#4](https://github.com/rubengarciam/kai/issues/4)). A GitHub Actions workflow runs `py_compile`, `bash -n` and `shellcheck` on the scripts, then the unit tests on Python 3.12 and 3.13 for every push to main and every pull request, plus a weekly run on main to catch upstream dependency changes. New tests: every tracked Python script prints usage on `--help`, and tracked symlinks resolve. Maintainer-side only: no change to the skills or `AGENTS.md`.
- **Changed: issue and pull-request auto-assignment reads repository variables instead of fixed usernames** ([#55](https://github.com/rubengarciam/kai/issues/55)). `ISSUE_ASSIGNEE`, `PR_ASSIGNEE` and `PR_REVIEWER` set who is assigned; unset (as in every fork) means nobody is. The third-party `auto-assign-action` and `.github/auto_assign.yml` are gone. Maintainer-side only: no change to the skills or `AGENTS.md`.
- **Changed: recovery data is read from TrainingPeaks first and labelled with its age** ([#31](https://github.com/rubengarciam/kai/issues/31)). HRV, resting HR and sleep hours now come from `tp.py metrics`, with Garmin as failover when TrainingPeaks has no value for the day (Garmin stays the only source for Body Battery, readiness, stress and sleep stages). Every recovery figure Kai quotes now carries its date, and one that isn't from today is flagged, for example "HRV 82 (STALE: measured 3 days ago)", with a note before any conclusion is drawn from it. This is a change to the instructions in `AGENTS.md` and the coach skill, not to any script. If you copied `AGENTS.md` into your own agent, copy the new "Recovery data: source and freshness" section too.
- **Changed: `tp.py profile` shows your age instead of your date of birth, and no longer prints sex.** Nothing in Kai uses either, so there is no reason to print them. `profile --json` still returns the raw response from TrainingPeaks.
- **Removed a stray file:** `fitdecode-0.0.0-py3-none-any.whl`, a 2 KB placeholder package (metadata only, no code) that a `pip download` check left in the repo folder and that was committed by mistake in v2.3.2. It is still inside the v2.3.2, v2.4.0 and v2.5.0 source archives, but nothing used it. `.gitignore` now excludes build and download artifacts, and a test fails if one is ever tracked.

## [2.5.0](https://github.com/rubengarciam/kai/releases/tag/v2.5.0) - 2026-10-01

- **Added: `garmin_activity_files.py` reads TCX files** ([#36](https://github.com/rubengarciam/kai/issues/36)). `parse`, `query` and `analyze` accept `.tcx` (any case) and return the same record fields as for FIT (timestamp, heart rate, distance, altitude, speed, power, cadence, position) plus a summary per lap, using only the standard library. This makes indoor rides uploaded by third-party apps analysable: their FIT files can't be decoded, but their TCX exports carry the full data. `analyze` gives the same statistics from a TCX as from the FIT of the same activity.
- **Changed:** when a FIT file can't be decoded, the error now says to download the same activity with `--format tcx` and parse that.
- A TCX that declares a DTD or XML entities is refused (a TCX file never has them), which closes the usual XML entity-expansion trick.

## [2.4.0](https://github.com/rubengarciam/kai/releases/tag/v2.4.0) - 2026-10-01

- **Changed: Garmin dashboards no longer need the internet** ([#7](https://github.com/rubengarciam/kai/issues/7)). `garmin_chart.py` loaded Chart.js from `cdn.jsdelivr.net`, so a dashboard was blank offline and depended on a third-party server. Chart.js 4.4.0 (the official build from npm, checked against the registry's integrity hash, with its MIT licences) is now bundled in `skills/garmin-health-analysis/assets/` and embedded in each page, which also means a dashboard keeps working after you move or email it. If the bundled file is ever missing, the script warns and falls back to the CDN. Pages are about 200 KB larger.

## [2.3.2](https://github.com/rubengarciam/kai/releases/tag/v2.3.2) - 2026-09-29

- **Fixed: `garmin_activity_files.py download --format fit` saved a ZIP archive under a `.fit` name** ([#15](https://github.com/rubengarciam/kai/issues/15)). Garmin sends the original file zipped, so `parse`, `query` and `analyze` failed with "Invalid .FIT File Header". The FIT file is now unpacked on download, and `parse`/`query`/`analyze` also accept a ZIP-wrapped FIT, so files an earlier version left on disk work without re-downloading.
- **Fixed:** `download` failed if `--output-dir` didn't exist. It is now created (mode `700`).
- **Fixed:** `.FIT` (capitals), which devices and Garmin Express write, was rejected as an unsupported file type.
- **Changed:** downloaded activity files are saved owner-only (`600`) and never written through a symlink at the destination. They hold GPS tracks, and the default folder, `/tmp`, is shared.
- **Changed: `SECURITY.md` renamed to `CREDENTIALS.md`.** It held Kai's own credential-handling rules, but GitHub treats the `SECURITY.md` filename as the repository's vulnerability-reporting policy. A real `SECURITY.md` with a reporting policy replaces it ([#24](https://github.com/rubengarciam/kai/issues/24)). See [upgrading](docs/upgrading.md#securitymd-renamed-to-credentialsmd) if you copied this workspace elsewhere.

## [2.3.1](https://github.com/rubengarciam/kai/releases/tag/v2.3.1) - 2026-09-29

- **Fixed: `tyre-mileage.sh` read a tyre's `fitted_date` as midnight UTC** instead of the athlete's own local date, so a ride on the local morning of the fit day (east of UTC) could be missed entirely, and a ride the evening before (west of UTC) could be wrongly counted ([#22](https://github.com/rubengarciam/kai/issues/22)). It now compares each activity's own local date, which Strava already provides, so no timezone configuration is needed.

## [2.3.0](https://github.com/rubengarciam/kai/releases/tag/v2.3.0) - 2026-09-29

- **Added: tyre ledger helpers** ([#16](https://github.com/rubengarciam/kai/issues/16)): `tyres.py` adds wheelsets and fits, replaces and retires tyre sets, so the tyre ledger no longer needs hand-editing.
- **Docs restructure:** the README is now a short front door (381 → 123 lines); installation, per-agent setup, upgrading, features and architecture moved to `docs/`, contributing to `CONTRIBUTING.md`. Added this changelog and GitHub pull request and issue templates.

## [2.2.1](https://github.com/rubengarciam/kai/releases/tag/v2.2.1) - 2026-09-28

- **Fixed:** five Garmin scripts and the Garmin README still told users to run `login --password`, a flag removed in v2.0.
- **Changed:** skill docs use plain paths from the repo root instead of an OpenClaw-specific base-directory placeholder ([#3](https://github.com/rubengarciam/kai/issues/3)).
- Added branch naming and PR conventions; more tests.

## [2.2.0](https://github.com/rubengarciam/kai/releases/tag/v2.2.0) - 2026-09-28

- **Changed:** chain wax and tyre tracking moved out of the Strava skill into a new `gear-maintenance` skill. Ledgers in the old location still work, with a notice. See [upgrading](docs/upgrading.md#gear-maintenance-moved-v22).

## [2.1.0](https://github.com/rubengarciam/kai/releases/tag/v2.1.0) - 2026-09-28

- **Added:** `chain-wax.py`, a chain wax ledger with km-since-wax reports and DUE SOON / DUE / OVERDUE statuses ([#10](https://github.com/rubengarciam/kai/issues/10)).

## [2.0.0](https://github.com/rubengarciam/kai/releases/tag/v2.0.0) - 2026-09-28

- **Breaking:** the Garmin skill needs `garminconnect` 0.3.x and Python 3.12+, and everyone logs in once more. `login --password` is removed and passwords are no longer read from `config.json`. See [upgrading](docs/upgrading.md#from-v1x-to-v20-garmin-login).
- **Added:** hidden password and MFA prompts, `--password-stdin`, `GARMIN_TOKEN_DIR`, offline tests.

## [1.1.0](https://github.com/rubengarciam/kai/releases/tag/v1.1.0) - 2026-09-28

- **Added:** Claude Code and Codex support (`CLAUDE.md` and skill symlinks); runtime-neutral README.

## [1.0.0](https://github.com/rubengarciam/kai/releases/tag/v1.0.0) - 2026-09-28

- First release: Kai's instructions and four skills (endurance coach, TrainingPeaks, Garmin, Strava).
