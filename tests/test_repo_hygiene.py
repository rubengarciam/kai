"""Checks that the right files are tracked and personal ones are ignored (needs a git checkout).

A bad .gitignore pattern once silently dropped templates/ from the repo, so this guards against it.
"""
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

TRACKED = ["templates/USER.md", "templates/MEMORY.md", "README.md", "CONTRIBUTING.md", "CHANGELOG.md", "docs/installation.md", "docs/architecture.md", "docs/upgrading.md",
           ".github/pull_request_template.md", ".github/ISSUE_TEMPLATE/bug_report.md",
           "skills/garmin-health-analysis/assets/chart.umd.js", "skills/garmin-health-analysis/assets/LICENSE-chartjs.md",
           "skills/gear-maintenance/data/tyres.example.json",
           "skills/gear-maintenance/data/chain-wax.example.json", "skills/gear-maintenance/SKILL.md",
           ".claude/skills/gear-maintenance", ".agents/skills/gear-maintenance", "data/nutrition-log.example.csv", "requirements.txt"]
IGNORED = ["USER.md", "MEMORY.md", "memory/notes.md", "data/nutrition-log.csv",
           "skills/gear-maintenance/data/tyres.json", "skills/gear-maintenance/data/chain-wax.json",
           "skills/strava/data/tyres.json", "skills/strava/data/chain-wax.json", ".env"]


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


@unittest.skipUnless((REPO / ".git").exists(), "not a git checkout")
class Hygiene(unittest.TestCase):
    def test_required_files_are_tracked(self):
        tracked = set(git("ls-files").stdout.split())
        for f in TRACKED:
            self.assertIn(f, tracked, f"{f} is not tracked (check .gitignore)")

    def test_personal_files_are_ignored(self):
        for f in IGNORED:
            self.assertEqual(git("check-ignore", "-q", f).returncode, 0, f"{f} would not be ignored")

    def test_no_build_artifacts_are_tracked(self):
        # A stray `pip download` once left a .whl in the repo folder and a blanket `git add -A` committed it
        artifacts = [f for f in git("ls-files").stdout.split()
                     if f.lower().endswith((".whl", ".tar.gz", ".tgz", ".egg", ".zip", ".pyc", ".pyo"))
                     or "/__pycache__/" in f or ".egg-info/" in f]
        self.assertEqual(artifacts, [], "build or download artifacts must not be committed")

    def test_tests_clean_up_their_temp_directories(self):
        # Each test file defines make_temp_dir(), which removes its folders when the run ends. Calling
        # tempfile.mkdtemp() anywhere else leaves a folder behind in /tmp on every run.
        offenders = []
        for f in sorted((REPO / "tests").glob("test_*.py")):
            if f.name == Path(__file__).name:       # this file names the call in its own comments
                continue
            calls = f.read_text().count("tempfile.mkdtemp()")
            allowed = 1 if "def make_temp_dir" in f.read_text() else 0
            if calls > allowed:
                offenders.append(f"{f.name}: {calls - allowed} direct call(s)")
        self.assertEqual(offenders, [], "use make_temp_dir() instead of tempfile.mkdtemp() in tests")

    def test_build_artifacts_are_ignored(self):
        for f in ("x-1.0-py3-none-any.whl", "x-1.0.tar.gz", "pkg.egg-info/PKG-INFO", "dist/x.whl", "build/lib/x.py"):
            self.assertEqual(git("check-ignore", "-q", f).returncode, 0, f"{f} would not be ignored")

    def test_no_personal_files_are_tracked(self):
        tracked = set(git("ls-files").stdout.split())
        for f in IGNORED:
            self.assertNotIn(f, tracked, f"{f} must not be committed")


if __name__ == "__main__":
    unittest.main()
