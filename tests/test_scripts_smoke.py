"""Every Python script with a command line must start and print its usage on --help.

Needs the packages in requirements.txt (the Garmin scripts import them). Only Python scripts are run: shell
scripts are deliberately NOT started with --help, because several ignore the flag and execute for real against the
credentials in ~/.config; they get `bash -n` and shellcheck in CI instead.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def cli_scripts():
    """Tracked skills/*/scripts/*.py that define a command line (library modules have no argparse)."""
    out = subprocess.run(["git", "ls-files", "skills/*/scripts/*.py"], cwd=REPO, capture_output=True, text=True).stdout
    return [REPO / f for f in out.split() if "argparse" in (REPO / f).read_text()]


@unittest.skipUnless((REPO / ".git").exists(), "not a git checkout")
class ScriptSmoke(unittest.TestCase):
    def test_there_are_scripts_to_check(self):
        self.assertGreaterEqual(len(cli_scripts()), 8)  # guards against the discovery silently finding nothing

    def test_every_cli_script_prints_usage_on_help(self):
        for script in cli_scripts():
            with self.subTest(script=script.relative_to(REPO).as_posix()):
                r = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 0, r.stderr[-500:])
                self.assertIn("usage:", r.stdout.lower())


if __name__ == "__main__":
    unittest.main()
