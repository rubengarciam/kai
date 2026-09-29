# Security Policy

This is a personal, hobby-maintained project. There's no dedicated security team and no SLA, but reports are taken seriously and looked at as soon as possible.

## Supported versions

Only the **latest release** gets security fixes. Older versions are not patched; upgrade to the latest tag instead of requesting a backport.

## What's in scope

Anything in this repository: the skill scripts (TrainingPeaks, Garmin, Strava, gear maintenance, the coaching skill) and the setup instructions in `AGENTS.md`. Examples of what's worth reporting:

- Credentials (tokens, cookies, passwords) written somewhere they shouldn't be, logged, or sent anywhere unexpected.
- A way to make a script read or write outside its intended files (path traversal, symlink following, etc.).
- Anything that would let one person's data or credentials leak to another user or process.

**Not in scope:** vulnerabilities in TrainingPeaks, Garmin Connect, Strava or the third-party `garminconnect` library itself — report those to the vendor. The Garmin and TrainingPeaks integrations use unofficial interfaces by design; that's a known, documented trade-off (see [docs/architecture.md](docs/architecture.md#privacy)), not something to report here.

## How to report

Use GitHub's **[private vulnerability reporting](https://github.com/rubengarciam/kai/security/advisories/new)** for this repository, rather than a public issue. Include:

- What the problem is and why it matters.
- Steps to reproduce, or a proof of concept.
- The affected file(s) and version (`git describe --tags`).

**Do not include real tokens, passwords, cookies, athlete IDs or your own training data in a report.** Use fabricated example values; a report is enough to reproduce the class of bug without needing real credentials attached to it. If you already have real personal data in a public issue by mistake, open a private report instead so it can be removed.

## What to expect

An acknowledgement within a few days, and a fix or a response with more questions after that. There's no bug bounty.

---

Looking for Kai's own rules on handling *your* credentials as its user (not reporting a bug in the code)? See [CREDENTIALS.md](CREDENTIALS.md).
