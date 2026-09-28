"""Doc checks: no agent-specific placeholders, and every repo path mentioned in the docs exists."""
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PATH_RE = re.compile(r"skills/[a-z][a-z-]*/(?:scripts|data|reference|references)/[A-Za-z0-9_.-]+")
# Files that exist only on a user's machine (git-ignored), or are deliberately mentioned as legacy locations
PERSONAL = {"chain-wax.json", "tyres.json", "nutrition-log.csv", "config.json", "credentials.json"}
LEGACY_PREFIX = "skills/strava/data/"


def tracked_docs():
    files = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.split()
    return [REPO / f for f in files if f.endswith((".md", ".py", ".sh", ".json")) and "/.venv/" not in f]


@unittest.skipUnless((REPO / ".git").exists(), "not a git checkout")
class Docs(unittest.TestCase):
    def test_no_basedir_placeholder(self):
        offenders = [str(f.relative_to(REPO)) for f in tracked_docs()
                     if f.name != "test_docs.py" and "{baseDir}" in f.read_text(errors="ignore")]
        self.assertEqual(offenders, [], "use plain paths from the repo root instead of {baseDir}")

    def test_referenced_repo_paths_exist(self):
        missing = []
        for f in tracked_docs():
            if f.suffix != ".md":
                continue
            for ref in set(PATH_RE.findall(f.read_text(errors="ignore"))):
                if ref.startswith(LEGACY_PREFIX) or ref.rsplit("/", 1)[1] in PERSONAL:
                    continue
                if not (REPO / ref).exists():
                    missing.append(f"{f.relative_to(REPO)}: {ref}")
        self.assertEqual(missing, [])

    def test_docs_never_tell_users_to_pass_a_password_argument(self):
        offenders = []
        for f in tracked_docs():
            if f.suffix == ".md" and f.name != "CHANGELOG.md":
                for n, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
                    if re.search(r"garmin_auth\.py login[^\n]*--password(?!-stdin)", line):
                        offenders.append(f"{f.relative_to(REPO)}:{n}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
