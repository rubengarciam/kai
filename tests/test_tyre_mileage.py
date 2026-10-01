"""Offline tests for the ledger-location logic of skills/gear-maintenance/scripts/tyre-mileage.sh.

The script checks for its ledger before any network call, and stops on a missing Strava token, so
these run with no network and no credentials (HOME points at an empty directory).
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import atexit


_TEMP_DIRS = []


def make_temp_dir():
    """A temp directory that is removed when the test run ends. (Tests used to leave about a hundred
    folders behind in /tmp per run, and /tmp is held in RAM on some machines.)"""
    path = tempfile.mkdtemp()
    _TEMP_DIRS.append(path)
    return path


atexit.register(lambda: [shutil.rmtree(p, ignore_errors=True) for p in _TEMP_DIRS])

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "skills" / "gear-maintenance"


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class TyreLedgerLocation(unittest.TestCase):
    def setUp(self):
        self.root = Path(make_temp_dir())
        shutil.copytree(SRC / "scripts", self.root / "skills" / "gear-maintenance" / "scripts")
        (self.root / "skills" / "gear-maintenance" / "data").mkdir(parents=True)
        self.script = self.root / "skills" / "gear-maintenance" / "scripts" / "tyre-mileage.sh"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("STRAVA_")}
        self.env["HOME"] = str(self.root)

    def run_script(self):
        return subprocess.run(["bash", str(self.script)], capture_output=True, text=True, env=self.env, timeout=60)

    def test_missing_ledger_explains_what_to_do(self):
        p = self.run_script()
        self.assertEqual(p.returncode, 1)
        self.assertIn("no tyre ledger", p.stderr)
        self.assertIn("tyres.example.json", p.stderr)

    def test_ledger_in_the_new_location_is_used_silently(self):
        (self.root / "skills" / "gear-maintenance" / "data" / "tyres.json").write_text("{}")
        p = self.run_script()
        self.assertNotIn("old location", p.stderr)
        self.assertIn("STRAVA_ACCESS_TOKEN not set", p.stderr)   # got past the ledger check

    def test_legacy_ledger_is_used_with_a_notice(self):
        legacy = self.root / "skills" / "strava" / "data"
        legacy.mkdir(parents=True)
        (legacy / "tyres.json").write_text("{}")
        p = self.run_script()
        self.assertIn("old location", p.stderr)
        self.assertIn("skills/gear-maintenance", p.stderr)
        self.assertIn("STRAVA_ACCESS_TOKEN not set", p.stderr)

    def test_new_location_wins_over_legacy(self):
        (self.root / "skills" / "gear-maintenance" / "data" / "tyres.json").write_text("{}")
        legacy = self.root / "skills" / "strava" / "data"
        legacy.mkdir(parents=True)
        (legacy / "tyres.json").write_text("{}")
        self.assertNotIn("old location", self.run_script().stderr)

    def test_example_ledger_is_valid_json(self):
        import json
        data = json.loads((SRC / "data" / "tyres.example.json").read_text())
        self.assertIn("wheelsets", data)


if __name__ == "__main__":
    unittest.main()
