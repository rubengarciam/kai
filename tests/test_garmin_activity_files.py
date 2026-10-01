"""Offline tests for skills/garmin-health-analysis/scripts/garmin_activity_files.py (synthetic data, no network).

Covers https://github.com/rubengarciam/kai/issues/15 (FIT) and https://github.com/rubengarciam/kai/issues/36 (TCX): `download --format fit` saved the ZIP archive Garmin
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
from datetime import timezone
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
            self.assertIn("--format tcx", out["error"])   # #36: point to the export that does work

    def test_other_extensions_are_still_unsupported(self):
        for action, code in (("parse", 0), ("query", 1), ("analyze", 1)):
            p = subprocess.run([sys.executable, str(SCRIPT), action, "--file", str(self.write("a.kml", b"<x/>"))],
                               capture_output=True, text=True, timeout=60)
            self.assertIn("Unsupported file type", p.stdout, action)
            self.assertEqual(p.returncode, code, action)


# --------------------------------------------------------------------------- TCX (#36)

TCX_V2 = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
TCX_EXT_V2 = "http://www.garmin.com/xmlschemas/ActivityExtension/v2"


def tcx_point(seconds, hr=None, dist=None, alt=None, pos=None, cadence=None, run_cadence=None, speed=None, watts=None):
    """A <Trackpoint> shaped like Garmin's export: every field optional, speed/watts/run cadence in <Extensions>."""
    parts = [f"<Time>2026-01-01T09:00:{seconds:02d}.000Z</Time>"]
    if pos:
        parts.append(f"<Position><LatitudeDegrees>{pos[0]}</LatitudeDegrees><LongitudeDegrees>{pos[1]}</LongitudeDegrees></Position>")
    if alt is not None:
        parts.append(f"<AltitudeMeters>{alt}</AltitudeMeters>")
    if dist is not None:
        parts.append(f"<DistanceMeters>{dist}</DistanceMeters>")
    if hr is not None:
        parts.append(f"<HeartRateBpm><Value>{hr}</Value></HeartRateBpm>")
    if cadence is not None:
        parts.append(f"<Cadence>{cadence}</Cadence>")
    ext = "".join(x for x in (f"<Speed>{speed}</Speed>" if speed is not None else "",
                              f"<Watts>{watts}</Watts>" if watts is not None else "",
                              f"<RunCadence>{run_cadence}</RunCadence>" if run_cadence is not None else "") if x)
    parts.append(f"<Extensions><TPX xmlns=\"{TCX_EXT_V2}\">{ext}</TPX></Extensions>" if ext else "<Extensions/>")
    return "<Trackpoint>" + "".join(parts) + "</Trackpoint>"


def build_tcx(laps, ns=TCX_V2):
    """laps: list of (lap_xml_children, [trackpoint_xml, ...])."""
    body = ""
    for children, points in laps:
        body += f'<Lap StartTime="2026-01-01T09:00:00.000Z">{children}<Track>{"".join(points)}</Track></Lap>'
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<TrainingCenterDatabase xmlns="{ns}">'
            f"<Activities><Activity Sport=\"Biking\"><Id>2026-01-01T09:00:00.000Z</Id>{body}</Activity></Activities>"
            "</TrainingCenterDatabase>").encode()


FULL_POINT = tcx_point(7, hr=151, dist=1234.5, alt=88.2, pos=(-33.5, 151.2), cadence=88, speed=9.75, watts=210)
LAP_XML = ("<TotalTimeSeconds>600.5</TotalTimeSeconds><DistanceMeters>5000.0</DistanceMeters>"
           "<MaximumSpeed>12.5</MaximumSpeed><Calories>150</Calories>"
           "<AverageHeartRateBpm><Value>140</Value></AverageHeartRateBpm><MaximumHeartRateBpm><Value>175</Value></MaximumHeartRateBpm>"
           "<Intensity>Active</Intensity><Cadence>85</Cadence><TriggerMethod>Manual</TriggerMethod>"
           f'<Extensions><LX xmlns="{TCX_EXT_V2}"><AvgSpeed>8.3</AvgSpeed><AvgWatts>200</AvgWatts>'
           "<MaxWatts>480</MaxWatts><MaxBikeCadence>120</MaxBikeCadence></LX></Extensions>")


class ParseTcx(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def parse(self, data, name="a.tcx"):
        path = self.root / name
        path.write_bytes(data if isinstance(data, bytes) else data.encode())
        return gaf.parse_tcx_file(str(path))

    def test_every_field_is_mapped_to_the_name_the_fit_parser_uses(self):
        rec = self.parse(build_tcx([("", [FULL_POINT])]))["records"][0]
        self.assertEqual(rec, {"timestamp": gaf.datetime(2026, 1, 1, 9, 0, 7, tzinfo=timezone.utc),
                               "latitude": -33.5, "longitude": 151.2, "altitude": 88.2, "distance": 1234.5,
                               "heart_rate": 151, "cadence": 88, "speed": 9.75, "power": 210})
        self.assertIsInstance(rec["heart_rate"], int)
        self.assertIsInstance(rec["power"], int)
        self.assertIsNotNone(rec["timestamp"].tzinfo)   # UTC-aware, so time queries need no guessing

    def test_run_cadence_comes_from_the_extension_when_there_is_no_plain_cadence(self):
        rec = self.parse(build_tcx([("", [tcx_point(1, hr=150, run_cadence=86, speed=3.1)])]))["records"][0]
        self.assertEqual((rec["cadence"], rec["speed"]), (86, 3.1))

    def test_fields_a_point_lacks_are_left_out(self):
        pool = tcx_point(1, hr=120)                       # a pool swim: time and heart rate only
        gps_gap = tcx_point(2, hr=130, dist=10.0)         # no position, no altitude, no speed
        records = self.parse(build_tcx([("", [pool, gps_gap])]))["records"]
        self.assertEqual(sorted(records[0]), ["heart_rate", "timestamp"])
        self.assertEqual(sorted(records[1]), ["distance", "heart_rate", "timestamp"])

    def test_a_point_with_nothing_in_it_is_skipped(self):
        records = self.parse(build_tcx([("", ["<Trackpoint></Trackpoint>", tcx_point(1, hr=100)])]))["records"]
        self.assertEqual(len(records), 1)

    def test_unreadable_values_are_dropped_not_fatal(self):
        bad = ("<Trackpoint><Time>not a time</Time><HeartRateBpm><Value>abc</Value></HeartRateBpm>"
               "<DistanceMeters>12.5</DistanceMeters><AltitudeMeters></AltitudeMeters></Trackpoint>")
        rec = self.parse(build_tcx([("", [bad])]))["records"][0]
        self.assertEqual(rec, {"distance": 12.5})

    def test_other_tcx_and_extension_versions_parse_the_same(self):
        v1 = build_tcx([("", [FULL_POINT])], ns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v1")
        v1 = v1.replace(TCX_EXT_V2.encode(), b"http://www.garmin.com/xmlschemas/ActivityExtension/v1")
        self.assertEqual(self.parse(v1)["records"], self.parse(build_tcx([("", [FULL_POINT])]))["records"])

    def test_points_keep_file_order_across_laps_and_tracks(self):
        data = build_tcx([("", [tcx_point(1, hr=101), tcx_point(2, hr=102)]), ("", [tcx_point(3, hr=103)])])
        self.assertEqual([r["heart_rate"] for r in self.parse(data)["records"]], [101, 102, 103])

    def test_laps_use_the_fit_lap_field_names(self):
        result = self.parse(build_tcx([(LAP_XML, [tcx_point(1, hr=120)])]))
        lap = result["laps"][0]
        self.assertEqual({k: v for k, v in lap.items() if k != "start_time"},
                         {"total_elapsed_time": 600.5, "total_distance": 5000.0, "max_speed": 12.5, "total_calories": 150.0,
                          "avg_cadence": 85.0, "avg_heart_rate": 140, "max_heart_rate": 175, "intensity": "Active",
                          "avg_speed": 8.3, "avg_power": 200.0, "max_power": 480.0, "max_cadence": 120.0})
        self.assertEqual(lap["start_time"].isoformat(), "2026-01-01T09:00:00+00:00")
        self.assertEqual((result["sessions"], result["total_records"]), ([], 1))

    def test_run_lap_cadence_comes_from_the_lap_extension(self):
        lx = f'<Extensions><LX xmlns="{TCX_EXT_V2}"><AvgRunCadence>84</AvgRunCadence><MaxRunCadence>96</MaxRunCadence></LX></Extensions>'
        lap = self.parse(build_tcx([(lx, [tcx_point(1, hr=120)])]))["laps"][0]
        self.assertEqual((lap["avg_cadence"], lap["max_cadence"]), (84.0, 96.0))


class TcxErrors(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def parse(self, data):
        path = self.root / "a.tcx"
        path.write_bytes(data)
        return gaf.parse_tcx_file(str(path))

    def test_not_xml(self):
        for junk in (b"", b"this is not xml", b"<TrainingCenterDatabase><Activities>"):
            self.assertIn("Could not read this TCX file", self.parse(junk)["error"], junk)

    def test_xml_that_is_not_tcx(self):
        self.assertIn("Not a TCX file (its root element is <gpx>)", self.parse(b'<gpx xmlns="http://www.topografix.com/GPX/1/1"/>')["error"])

    def test_a_dtd_or_entity_declaration_is_refused(self):
        bomb = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
                b'<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>'
                b'<TrainingCenterDatabase xmlns="' + TCX_V2.encode() + b'"><Activities>&lol3;</Activities></TrainingCenterDatabase>')
        for doc in (bomb, b"<!doctype x><TrainingCenterDatabase/>", b"<!ENTITY a 'b'><TrainingCenterDatabase/>"):
            self.assertIn("DTD or XML entities", self.parse(doc)["error"])

    def test_a_missing_file_is_an_error_dict(self):
        self.assertIn("error", gaf.parse_tcx_file(str(self.root / "nope.tcx")))

    def test_an_oversized_file_is_refused_before_it_is_read(self):
        with mock.patch.object(gaf, "MAX_TCX_BYTES", 10):
            self.assertIn("larger than", self.parse(build_tcx([("", [FULL_POINT])]))["error"])

    def test_a_tcx_with_no_trackpoints_parses_to_nothing(self):
        result = self.parse(build_tcx([("", [])]))
        self.assertEqual((result["records"], result["total_records"]), ([], 0))
        self.assertIn("error", gaf.analyze_activity(result))     # "No data records to analyze", not a crash


class ParseActivityFile(unittest.TestCase):
    def test_dispatch_is_by_extension_in_any_case(self):
        root = Path(tempfile.mkdtemp())
        for name in ("a.tcx", "A.TCX", "a.Tcx"):
            (root / name).write_bytes(build_tcx([("", [FULL_POINT])]))
            self.assertEqual(gaf.parse_activity_file(str(root / name))["total_records"], 1, name)

    def test_unknown_extensions_return_none(self):
        for name in ("a.kml", "a.txt", "tcx", "a.tcx.bak", "a"):
            self.assertIsNone(gaf.parse_activity_file(name), name)


@unittest.skipUnless(gaf.HAS_FITPARSE, "needs fitparse (pip install -r requirements.txt)")
class TcxEndToEnd(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60)

    def tcx_file(self, name="activity.tcx"):
        points = [tcx_point(sec, hr=hr, dist=dist_cm / 100) for sec, hr, dist_cm in SAMPLES]
        path = self.root / name
        path.write_bytes(build_tcx([("", points)]))
        return path

    def test_the_same_activity_as_fit_and_as_tcx_gives_identical_statistics(self):
        fit = self.root / "a.fit"
        fit.write_bytes(FIT)
        from_fit = gaf.analyze_activity(gaf.parse_fit_file(str(fit)))
        from_tcx = gaf.analyze_activity(gaf.parse_tcx_file(str(self.tcx_file())))
        self.assertEqual(from_fit["heart_rate"], {"avg": 120.0, "max": 140, "min": 100})   # guards the comparison itself
        self.assertEqual(from_tcx, from_fit)

    def test_parse_query_and_analyze_accept_tcx_in_any_case(self):
        for name in ("activity.tcx", "ACTIVITY.TCX"):
            path = self.tcx_file(name)
            parsed = json.loads(self.run_cli("parse", "--file", str(path)).stdout)
            self.assertEqual(parsed["total_records"], 5, name)
            analyzed = json.loads(self.run_cli("analyze", "--file", str(path)).stdout)
            self.assertEqual((analyzed["total_points"], analyzed["duration_seconds"], analyzed["distance_meters"]), (5, 4.0, 40.0), name)
            queried = json.loads(self.run_cli("query", "--file", str(path), "--distance", "20").stdout)
            self.assertEqual(queried["heart_rate"], 120, name)

    def test_query_by_time_works_with_the_utc_timestamps_in_tcx(self):
        path = self.tcx_file()
        out = json.loads(self.run_cli("query", "--file", str(path), "--time", "2026-01-01T09:00:03Z").stdout)
        self.assertEqual(out["heart_rate"], 130)

    def test_a_real_looking_swim_with_no_distance_still_analyzes(self):
        path = self.root / "swim.tcx"
        path.write_bytes(build_tcx([("", [tcx_point(sec, hr=110 + sec) for sec in range(6)])]))
        out = json.loads(self.run_cli("analyze", "--file", str(path)).stdout)
        self.assertNotIn("error", out)
        self.assertEqual((out["heart_rate"]["avg"], out["distance_meters"]), (112.5, None))

    def test_a_downloaded_tcx_is_saved_as_is_and_then_parses(self):
        payload = build_tcx([("", [FULL_POINT])])
        result = gaf.download_activity_file(FakeClient(payload), 9, "tcx", str(self.root))
        self.assertEqual(Path(result["file"]).read_bytes(), payload)
        self.assertEqual(gaf.parse_activity_file(result["file"])["total_records"], 1)


if __name__ == "__main__":
    unittest.main()
