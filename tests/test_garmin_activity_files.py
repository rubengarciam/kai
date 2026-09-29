"""Offline tests for skills/garmin-health-analysis/scripts/garmin_activity_files.py (synthetic data, no network).

Covers https://github.com/rubengarciam/kai/issues/15: `download --format fit` saved the ZIP archive Garmin
returns for the "original" format under a .fit name, so parse/analyze/query failed with
"Invalid .FIT File Header"; and `download` failed if the output directory didn't exist.

Run from the repo root:  .venv/bin/python3 -m unittest discover -s tests -v
"""
import importlib
import io
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "garmin-health-analysis" / "scripts"
SCRIPT = SCRIPTS / "garmin_activity_files.py"


def load_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        with mock.patch.dict(os.environ, {"GARMIN_TOKEN_DIR": tempfile.mkdtemp()}):
            sys.modules.pop("garmin_activity_files", None)
            sys.modules.pop("garmin_auth", None)
            return importlib.import_module("garmin_activity_files")
    finally:
        sys.path.remove(str(SCRIPTS))


gaf = load_module()

_CRC_TABLE = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
              0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]


def fit_crc(data, crc=0):
    """The CRC-16 the FIT file format specifies."""
    for byte in data:
        tmp = _CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ _CRC_TABLE[byte & 0xF]
        tmp = _CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ _CRC_TABLE[(byte >> 4) & 0xF]
    return crc


def build_fit(samples):
    """A minimal valid FIT file with one 'record' message per (seconds, heart_rate, distance_cm) sample."""
    definition = (bytes([0x40, 0x00, 0x00]) + struct.pack("<H", 20) + bytes([3])
                  + bytes([253, 4, 0x86])     # timestamp, uint32
                  + bytes([3, 1, 0x02])       # heart_rate, uint8
                  + bytes([5, 4, 0x86]))      # distance, uint32 (scale 100 -> metres)
    body = definition
    for seconds, hr, dist_cm in samples:
        body += bytes([0x00]) + struct.pack("<I", 1_000_000_000 + seconds) + bytes([hr]) + struct.pack("<I", dist_cm)
    header = struct.pack("<BBHI4s", 14, 0x10, 2000, len(body), b".FIT")
    header += struct.pack("<H", fit_crc(header))
    return header + body + struct.pack("<H", fit_crc(header + body))


SAMPLES = [(0, 100, 0), (1, 110, 1000), (2, 120, 2000), (3, 130, 3000), (4, 140, 4000)]
FIT = build_fit(SAMPLES)


def build_fit_with_zero_size_float(samples):
    """Like build_fit, but the record definition also declares a float32 field of size 0. The fit parser
    fails on this with "Invalid struct format: <0f", exactly as it does on the FIT files some third-party
    apps write (seen with indoor rides uploaded from TrainingPeaks Virtual)."""
    definition = (bytes([0x40, 0x00, 0x00]) + struct.pack("<H", 20) + bytes([4])
                  + bytes([253, 4, 0x86]) + bytes([3, 1, 0x02]) + bytes([5, 4, 0x86]) + bytes([200, 0, 0x88]))
    body = definition
    for seconds, hr, dist_cm in samples:
        body += bytes([0x00]) + struct.pack("<I", 1_000_000_000 + seconds) + bytes([hr]) + struct.pack("<I", dist_cm)
    header = struct.pack("<BBHI4s", 14, 0x10, 2000, len(body), b".FIT")
    header += struct.pack("<H", fit_crc(header))
    return header + body + struct.pack("<H", fit_crc(header + body))


def make_zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


class FakeClient:
    """Stands in for garminconnect.Garmin: hands back preset bytes, records the format asked for."""

    class ActivityDownloadFormat:
        ORIGINAL, GPX, TCX = "ORIGINAL", "GPX", "TCX"

    def __init__(self, payload):
        self.payload = payload
        self.asked_for = None

    def download_activity(self, activity_id, dl_fmt=None):
        self.asked_for = dl_fmt
        return self.payload


class FitBytesFrom(unittest.TestCase):
    def test_a_bare_fit_file_passes_through_unchanged(self):
        self.assertEqual(gaf.fit_bytes_from(FIT), FIT)

    def test_a_zip_holding_one_fit_file_is_unwrapped(self):
        for name in ("12345678901_ACTIVITY.fit", "ACTIVITY.FIT", "nested/dir/a.Fit"):
            self.assertEqual(gaf.fit_bytes_from(make_zip({name: FIT})), FIT, name)

    def test_other_files_in_the_zip_are_ignored(self):
        self.assertEqual(gaf.fit_bytes_from(make_zip({"readme.txt": b"hi", "a.fit": FIT})), FIT)

    def test_a_zip_with_no_fit_file_says_what_it_does_contain(self):
        with self.assertRaisesRegex(gaf.FitDataError, r"no \.fit file.*notes\.txt"):
            gaf.fit_bytes_from(make_zip({"notes.txt": b"x"}))

    def test_a_zip_with_two_fit_files_is_ambiguous(self):
        with self.assertRaisesRegex(gaf.FitDataError, "more than one .fit file"):
            gaf.fit_bytes_from(make_zip({"a.fit": FIT, "b.fit": FIT}))

    def test_a_fit_member_that_is_not_fit_data_is_rejected(self):
        with self.assertRaisesRegex(gaf.FitDataError, "not a valid FIT file"):
            gaf.fit_bytes_from(make_zip({"a.fit": b"this is not a fit file at all"}))

    def test_neither_fit_nor_zip_is_rejected(self):
        for junk in (b"<gpx></gpx>", b"PK\x03\x04 truncated", b"x" * 100):
            with self.assertRaisesRegex(gaf.FitDataError, "neither a FIT file nor a ZIP"):
                gaf.fit_bytes_from(junk)

    def test_empty_data_is_rejected(self):
        for empty in (b"", None):
            with self.assertRaisesRegex(gaf.FitDataError, "no data"):
                gaf.fit_bytes_from(empty)

    def test_an_oversized_member_is_rejected_before_it_is_read(self):
        with mock.patch.object(gaf, "MAX_FIT_BYTES", 10):
            with self.assertRaisesRegex(gaf.FitDataError, "larger than"):
                gaf.fit_bytes_from(make_zip({"a.fit": FIT}))


class DownloadActivityFile(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def download(self, payload, fmt="fit", out=None, activity_id=123):
        client = FakeClient(payload)
        result = gaf.download_activity_file(client, activity_id, fmt, str(out or self.root))
        return result, client

    def test_fit_download_unwraps_the_zip_and_saves_a_real_fit_file(self):
        result, client = self.download(make_zip({"123_ACTIVITY.fit": FIT}))
        self.assertEqual(client.asked_for, "ORIGINAL")
        self.assertEqual(result["file"], str(self.root / "activity_123.fit"))
        self.assertEqual((self.root / "activity_123.fit").read_bytes(), FIT)

    def test_a_bare_fit_from_garmin_is_saved_as_is(self):
        self.download(FIT)
        self.assertEqual((self.root / "activity_123.fit").read_bytes(), FIT)

    def test_gpx_and_tcx_are_saved_untouched_with_the_right_download_format(self):
        for fmt, expected in (("gpx", "GPX"), ("tcx", "TCX"), ("GPX", "GPX")):
            result, client = self.download(b"<gpx>data</gpx>", fmt=fmt)
            self.assertEqual(client.asked_for, expected)
            self.assertEqual(Path(result["file"]).read_bytes(), b"<gpx>data</gpx>")

    def test_unsupported_format_is_reported(self):
        result, client = self.download(b"x", fmt="kml")
        self.assertIn("Unsupported format", result["error"])
        self.assertIsNone(client.asked_for)

    def test_bad_download_reports_an_error_and_writes_nothing(self):
        result, _ = self.download(make_zip({"notes.txt": b"x"}))
        self.assertIn("no .fit file", result["error"])
        self.assertEqual(result["activity_id"], 123)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_output_directory_is_created_private(self):
        out = self.root / "a" / "b" / "c"
        result, _ = self.download(FIT, out=out)
        self.assertNotIn("error", result)
        self.assertTrue((out / "activity_123.fit").exists())
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)

    def test_an_existing_output_directory_keeps_its_permissions(self):
        os.chmod(self.root, 0o755)
        self.download(FIT)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o755)

    def test_files_are_owner_only_even_when_overwriting_a_permissive_one(self):
        target = self.root / "activity_123.fit"
        target.write_bytes(b"old")
        os.chmod(target, 0o664)
        self.download(FIT)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(target.read_bytes(), FIT)

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "needs O_NOFOLLOW")
    def test_a_symlink_at_the_destination_is_not_followed(self):
        victim = self.root / "victim.txt"
        victim.write_text("precious")
        out = self.root / "out"
        out.mkdir()
        os.symlink(victim, out / "activity_123.fit")
        result, _ = self.download(FIT, out=out)
        self.assertIn("error", result)
        self.assertEqual(victim.read_text(), "precious")

    def test_a_hostile_member_name_cannot_write_outside_the_output_directory(self):
        out = self.root / "out"
        result, _ = self.download(make_zip({"../../evil.fit": FIT}), out=out)
        self.assertNotIn("error", result)
        self.assertEqual({p.name for p in self.root.rglob("*") if p.is_file()}, {"activity_123.fit"})
        self.assertEqual((out / "activity_123.fit").read_bytes(), FIT)


@unittest.skipUnless(gaf.HAS_FITPARSE, "needs fitparse (pip install -r requirements.txt)")
class ParseAndAnalyze(unittest.TestCase):
    """The end-to-end symptom from the issue: a downloaded activity must actually parse."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def analyze_cli(self, path):
        p = subprocess.run([sys.executable, str(SCRIPT), "analyze", "--file", str(path)],
                           capture_output=True, text=True, timeout=60, env={**os.environ, "GARMIN_TOKEN_DIR": str(self.root)})
        return p, json.loads(p.stdout)

    def test_my_synthetic_fit_is_valid(self):
        # guards the test helper itself: if this fails, the tests below prove nothing
        data = gaf.parse_fit_file(str(self.write("plain.fit", FIT)))
        self.assertEqual(data["total_records"], 5)
        self.assertEqual([r["heart_rate"] for r in data["records"]], [100, 110, 120, 130, 140])

    def write(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_download_then_analyze_works(self):
        result = gaf.download_activity_file(FakeClient(make_zip({"x_ACTIVITY.fit": FIT})), 7, "fit", str(self.root))
        _, out = self.analyze_cli(result["file"])
        self.assertNotIn("error", out)
        self.assertEqual(out["total_points"], 5)
        self.assertEqual(out["heart_rate"], {"avg": 120.0, "max": 140, "min": 100})
        self.assertEqual(out["duration_seconds"], 4.0)
        self.assertEqual(out["distance_meters"], 40.0)

    def test_a_zip_saved_under_a_fit_name_by_an_earlier_version_still_parses(self):
        # exactly the file the bug left on disk
        path = self.write("activity_1.fit", make_zip({"1_ACTIVITY.fit": FIT}))
        data = gaf.parse_fit_file(str(path))
        self.assertNotIn("error", data)
        self.assertEqual(data["total_records"], 5)

    def test_uppercase_extension_is_accepted_by_every_action(self):
        path = self.write("ACTIVITY.FIT", FIT)
        for action in ("parse", "analyze"):
            p = subprocess.run([sys.executable, str(SCRIPT), action, "--file", str(path)], capture_output=True, text=True, timeout=60)
            self.assertNotIn("Unsupported", p.stdout, action)
            self.assertNotIn('"error"', p.stdout, action)
        p = subprocess.run([sys.executable, str(SCRIPT), "query", "--file", str(path), "--distance", "20"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(p.stdout)["heart_rate"], 120)

    def test_garbage_gives_a_clear_error_not_a_parser_traceback(self):
        path = self.write("bad.fit", b"not a fit file")
        _, out = self.analyze_cli(path)
        self.assertIn("neither a FIT file nor a ZIP", out["error"])

    def test_a_fit_file_the_parser_cannot_decode_gets_a_readable_error(self):
        # the failure #15's own example activity hits once the ZIP is out of the way: a separate problem
        path = self.write("thirdparty.fit", build_fit_with_zero_size_float(SAMPLES))
        for wrapped in (path, self.write("wrapped.fit", make_zip({"a.fit": path.read_bytes()}))):
            _, out = self.analyze_cli(wrapped)
            self.assertIn("Could not read this FIT file", out["error"])
            self.assertIn("Invalid struct format", out["error"])
            self.assertIn("garmin_data.py", out["error"])

    def test_other_extensions_are_still_unsupported(self):
        p = subprocess.run([sys.executable, str(SCRIPT), "parse", "--file", str(self.write("a.tcx", b"<x/>"))],
                           capture_output=True, text=True, timeout=60)
        self.assertIn("Unsupported file type", p.stdout)


if __name__ == "__main__":
    unittest.main()
