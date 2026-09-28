"""Checks that the right files are tracked and personal ones are ignored (needs a git checkout).

A bad .gitignore pattern once silently dropped templates/ from the repo, so this guards against it.
"""
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

TRACKED = ["templates/USER.md", "templates/MEMORY.md", "skills/strava/data/tyres.example.json",
           "skills/strava/data/chain-wax.example.json", "data/nutrition-log.example.csv", "requirements.txt"]
IGNORED = ["USER.md", "MEMORY.md", "memory/notes.md", "data/nutrition-log.csv",
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

    def test_no_personal_files_are_tracked(self):
        tracked = set(git("ls-files").stdout.split())
        for f in IGNORED:
            self.assertNotIn(f, tracked, f"{f} must not be committed")


if __name__ == "__main__":
    unittest.main()
