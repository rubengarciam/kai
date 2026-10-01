"""Offline tests for the bundled Chart.js in skills/garmin-health-analysis/scripts/garmin_chart.py.

Covers https://github.com/rubengarciam/kai/issues/7: dashboards loaded Chart.js from a CDN, so they were
blank without internet access. Chart.js is now vendored and embedded in each generated page.

These tests check the generated HTML's structure. The actual rendering with the network off was checked
in a headless browser when the change was made (see the pull request); a browser isn't a test dependency.

Run from the repo root:  .venv/bin/python3 -m unittest discover -s tests -v
"""
import hashlib
import importlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "garmin-health-analysis"
SCRIPTS = SKILL / "scripts"
ASSETS = SKILL / "assets"


def load_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        with mock.patch.dict(os.environ, {"GARMIN_TOKEN_DIR": tempfile.mkdtemp()}):
            for name in ("garmin_chart", "garmin_auth", "garmin_data"):
                sys.modules.pop(name, None)
            return importlib.import_module("garmin_chart")
    finally:
        sys.path.remove(str(SCRIPTS))


gc = load_module()

CHARTS = {"stats": {"Avg Sleep": "7.4h"},
          "charts": [{"title": "T", "chart": {"type": "bar", "data": {"labels": ["a"], "datasets": [{"data": [1]}]}}}]}


def script_tags(html):
    """(opening tags, closing tags) of <script> elements."""
    return len(re.findall(r"<script[\s>]", html)), html.count("</script>")


class BundledAsset(unittest.TestCase):
    def test_the_vendored_file_matches_its_recorded_checksum(self):
        recorded, name = (ASSETS / "chart.umd.js.sha256").read_text().split()
        self.assertEqual(name, "chart.umd.js")
        self.assertEqual(hashlib.sha256((ASSETS / "chart.umd.js").read_bytes()).hexdigest(), recorded,
                         "chart.umd.js changed: update it the documented way (assets/README.md) and its .sha256")

    def test_it_keeps_its_licence_banner_and_ships_both_licences(self):
        head = (ASSETS / "chart.umd.js").read_text(encoding="utf-8")[:300]
        self.assertIn("Chart.js v4.4.0", head)
        self.assertIn("Released under the MIT License", head)
        self.assertIn("Chart.js Contributors", (ASSETS / "LICENSE-chartjs.md").read_text())
        self.assertIn("Jukka Kurkela", (ASSETS / "LICENSE-kurkle-color.md").read_text())

    def test_it_has_no_literal_script_end_tag_that_would_break_inlining(self):
        self.assertNotIn("</script", (ASSETS / "chart.umd.js").read_text(encoding="utf-8").lower())


class GeneratedDashboard(unittest.TestCase):
    def setUp(self):
        self.html = gc.generate_html(CHARTS, "Test")

    def test_chart_js_is_embedded_and_nothing_is_loaded_from_the_network(self):
        self.assertIn("Released under the MIT License", self.html)
        self.assertIn("window.Chart=", self.html)
        self.assertEqual(re.findall(r"<script[^>]+src=", self.html), [])
        self.assertEqual(re.findall(r"(?:src|href)=[\"']https?://", self.html), [])
        self.assertNotIn("cdn.jsdelivr", self.html)

    def test_the_library_comes_before_the_code_that_uses_it(self):
        self.assertLess(self.html.index("window.Chart="), self.html.index("Chart.defaults.color"))

    def test_the_page_structure_is_intact(self):
        opens, closes = script_tags(self.html)
        self.assertEqual((opens, closes), (2, 2))          # the library and the page's own script
        self.assertEqual(self.html.count("</html>"), 1)
        self.assertIn("const chartsData = ", self.html)
        self.assertIn('"Avg Sleep": "7.4h"', self.html)

    def test_the_dangling_source_map_pointer_is_dropped(self):
        self.assertIn("sourceMappingURL", (ASSETS / "chart.umd.js").read_text())   # it is in the vendored file...
        self.assertNotIn("sourceMappingURL", self.html)                            # ...but not in the page

    def test_the_only_change_to_the_library_is_that_line(self):
        original = (ASSETS / "chart.umd.js").read_text(encoding="utf-8")
        wanted = "\n".join(l for l in original.splitlines() if not l.startswith("//# sourceMappingURL="))
        self.assertIn(wanted, self.html)

    def test_the_page_is_large_enough_to_hold_the_library(self):
        self.assertGreater(len(self.html), (ASSETS / "chart.umd.js").stat().st_size)


class MissingAsset(unittest.TestCase):
    def test_a_missing_bundle_falls_back_to_the_cdn_with_a_warning(self):
        with mock.patch.object(gc, "CHART_JS_ASSET", Path(tempfile.mkdtemp()) / "nope.js"), \
             mock.patch("sys.stderr") as err:
            html = gc.generate_html(CHARTS, "Test")
        self.assertIn(f'<script src="{gc.CHART_JS_CDN}"></script>', html)
        self.assertEqual(script_tags(html), (2, 2))
        self.assertIn("missing", "".join(c.args[0] for c in err.write.call_args_list))

    def test_the_fallback_url_names_the_same_version_as_the_bundle(self):
        self.assertIn("chart.js@4.4.0", gc.CHART_JS_CDN)
        self.assertIn("Chart.js v4.4.0", (ASSETS / "chart.umd.js").read_text(encoding="utf-8")[:200])


if __name__ == "__main__":
    unittest.main()
