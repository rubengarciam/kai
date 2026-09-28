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


def slugs(md_path):
    """GitHub-style heading anchors for a markdown file (ignores headings inside code fences)."""
    seen, out, in_code = {}, set(), False
    for line in md_path.read_text(errors="ignore").splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        m = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if in_code or not m:
            continue
        text = re.sub(r"`", "", m.group(1)).lower()
        slug = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE).strip().replace(" ", "-")
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        out.add(slug if n == 0 else f"{slug}-{n}")
    return out


LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")


@unittest.skipUnless((REPO / ".git").exists(), "not a git checkout")
class Links(unittest.TestCase):
    def markdown_files(self):
        # templates/ holds files meant to be copied and filled in, so their sample links are not checked
        return [f for f in tracked_docs() if f.suffix == ".md" and "templates" not in f.relative_to(REPO).parts]

    def test_relative_links_and_anchors_resolve(self):
        broken = []
        for f in self.markdown_files():
            text = re.sub(r"```.*?```", "", f.read_text(errors="ignore"), flags=re.S)
            for target in LINK_RE.findall(text):
                if re.match(r"^(https?:|mailto:|tel:)", target):
                    continue
                path_part, _, anchor = target.partition("#")
                dest = f if not path_part else (f.parent / path_part).resolve()
                if not dest.exists():
                    broken.append(f"{f.relative_to(REPO)}: {target} (no such file)")
                elif anchor and dest.suffix == ".md" and anchor not in slugs(dest):
                    broken.append(f"{f.relative_to(REPO)}: {target} (no such heading)")
        self.assertEqual(broken, [])

    def test_anchors_that_published_releases_link_to_still_exist(self):
        # v2.0.0's release notes link to README#upgrading-from-v1x
        self.assertIn("upgrading-from-v1x", slugs(REPO / "README.md"))

    def test_readme_stays_a_short_front_door(self):
        lines = len((REPO / "README.md").read_text().splitlines())
        self.assertLessEqual(lines, 160, f"README is {lines} lines: put detail in docs/ and link to it")

    def test_every_docs_page_is_linked_from_the_readme(self):
        readme = (REPO / "README.md").read_text()
        for page in sorted((REPO / "docs").glob("*.md")):
            self.assertIn(f"docs/{page.name}", readme, f"{page.name} is not linked from the README")


if __name__ == "__main__":
    unittest.main()
