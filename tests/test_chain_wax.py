"""Offline tests for skills/gear-maintenance/scripts/chain-wax.py (synthetic data, no network).

Run from the repo root:  .venv/bin/python3 -m unittest discover -s tests -v
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest import mock
import atexit
import shutil


_TEMP_DIRS = []


def make_temp_dir():
    """A temp directory that is removed when the test run ends. (Tests used to leave about a hundred
    folders behind in /tmp per run, and /tmp is held in RAM on some machines.)"""
    path = tempfile.mkdtemp()
    _TEMP_DIRS.append(path)
    return path


atexit.register(lambda: [shutil.rmtree(p, ignore_errors=True) for p in _TEMP_DIRS])

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "gear-maintenance" / "scripts" / "chain-wax.py"
spec = importlib.util.spec_from_file_location("chain_wax", SCRIPT)
cw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cw)

TODAY = date(2026, 6, 1)


def wax(d, odo, interval, kind="hot"):
    return {"date": d, "odometer_km": odo, "kind": kind, "product": "test", "degreased": False, "next_due_km": interval}


def ledger():
    return {"bikes": {
        "road": {"name": "Road", "strava_gear_id": "b1", "default_kind": "hot",
                 "waxes": [wax("2026-01-10", 1000.0, [150, 250]), wax("2026-02-10", 1200.0, [450, 500])]},
        "kid": {"name": "Kid bike", "strava_gear_id": None, "default_kind": "hot", "odometer_km": 90.0,
                "odometer_date": "2026-05-30", "waxes": [wax("2026-05-01", 40.0, [450, 500])]},
        "new": {"name": "No waxes", "strava_gear_id": "b2", "default_kind": "drip", "waxes": []},
    }}


def ns(**kw):
    base = dict(ledger=None, bike=None, odometer=None, date=None, product=None, kind=None, interval=None,
                degreased=False, force=False, km=None, name=None, gear_id=None, manual=False, json=False)
    base.update(kw)
    return Namespace(**base)


class TempLedger(unittest.TestCase):
    def setUp(self):
        self.dir = Path(make_temp_dir())
        self.path = self.dir / "chain-wax.json"

    def write(self, data):
        self.path.write_text(json.dumps(data))

    def read(self):
        return json.loads(self.path.read_text())

    def run_quiet(self, fn, *a, **kw):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = fn(*a, **kw)
        return rc, out.getvalue()


class Status(unittest.TestCase):
    def test_thresholds(self):
        for since, expected in [(0, "OK"), (404.9, "OK"), (405, "DUE SOON"), (449.9, "DUE SOON"), (450, "DUE"),
                                (500, "DUE"), (500.1, "OVERDUE"), (-1, "CHECK ODOMETER")]:
            self.assertEqual(cw.status_for(since, 450, 500), expected, since)

    def test_default_intervals(self):
        self.assertEqual(cw.default_interval("hot", True), [150, 250])
        self.assertEqual(cw.default_interval("hot", False), [450, 500])
        self.assertEqual(cw.default_interval("drip", True), [200, 300])
        self.assertEqual(cw.default_interval("drip", False), [200, 300])

    def test_interval_parsing(self):
        self.assertEqual(cw.parse_interval("450-500"), [450.0, 500.0])
        for bad in ("500-450", "abc", "450", "0-10", ""):
            with self.assertRaises(cw.ChainWaxError):
                cw.parse_interval(bad)


class Report(TempLedger):
    def test_assess_uses_the_range_stored_on_the_last_wax(self):
        bike = ledger()["bikes"]["road"]
        row = cw.assess("road", bike, 1700.0, "strava", None, TODAY)
        self.assertEqual(row["km_since_wax"], 500.0)
        self.assertEqual((row["due_from_odometer_km"], row["due_by_odometer_km"]), (1650.0, 1700.0))
        self.assertEqual(row["status"], "DUE")
        self.assertEqual(row["remaining_to_min_km"], -50.0)
        self.assertEqual(row["last_wax"], {"date": "2026-02-10", "odometer_km": 1200.0, "product": "test",
                                           "kind": "hot", "degreased": False})

    def test_bike_without_waxes(self):
        row = cw.assess("new", ledger()["bikes"]["new"], 10.0, "strava", None, TODAY)
        self.assertEqual(row["status"], "NO WAX LOGGED")
        self.assertIsNone(row["km_since_wax"])

    def test_report_mixes_live_and_manual_bikes(self):
        rows, problems = cw.build_report(ledger(), fetch=lambda gid: {"b1": 1610.0, "b2": 5.0}[gid], today=TODAY)
        by = {r["bike"]: r for r in rows}
        self.assertEqual(problems, [])
        self.assertEqual(by["road"]["status"], "DUE SOON")     # 410 of 450
        self.assertEqual(by["kid"]["source"], "manual")
        self.assertEqual(by["kid"]["km_since_wax"], 50.0)
        self.assertFalse(by["kid"]["stale"])

    def test_stale_manual_reading_is_flagged(self):
        rows, _ = cw.build_report(ledger(), fetch=lambda gid: 0.0, today=date(2026, 8, 1))
        kid = next(r for r in rows if r["bike"] == "kid")
        self.assertTrue(kid["stale"])
        self.assertEqual(kid["odometer_age_days"], 63)
        self.assertIn("days old", cw.render_report(rows, []))

    def test_strava_failure_is_reported_not_fatal(self):
        def boom(gid):
            raise cw.OdometerUnavailable("HTTP 401")
        rows, problems = cw.build_report(ledger(), fetch=boom, today=TODAY)
        self.assertEqual([r["bike"] for r in rows], ["kid"])
        self.assertEqual({p["bike"] for p in problems}, {"road", "new"})
        self.assertIn("odometer unavailable", cw.render_report(rows, problems))

    def test_report_exit_code_2_when_an_odometer_is_missing(self):
        self.write(ledger())
        def boom(gid):
            raise cw.OdometerUnavailable("no token")
        rc, out = self.run_quiet(cw.cmd_report, ns(ledger=str(self.path)), fetch=boom)
        self.assertEqual(rc, 2)
        self.assertIn("Kid bike", out)

    def test_json_output_is_valid(self):
        data = ledger(); data["bikes"] = {"kid": data["bikes"]["kid"]}
        self.write(data)
        rc, out = self.run_quiet(cw.cmd_report, ns(ledger=str(self.path), json=True))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["bikes"][0]["bike"], "kid")


class Log(TempLedger):
    def setUp(self):
        super().setUp()
        self.write(ledger())

    def log(self, **kw):
        kw.setdefault("ledger", str(self.path))
        return self.run_quiet(cw.cmd_log, ns(**kw), fetch=lambda gid: 1650.0, today=TODAY)

    def test_defaults_to_live_odometer_and_later_interval(self):
        self.log(bike="road", product="Wax X", degreased=True)
        last = self.read()["bikes"]["road"]["waxes"][-1]
        self.assertEqual((last["date"], last["odometer_km"], last["next_due_km"]), ("2026-06-01", 1650.0, [450, 500]))
        self.assertTrue(last["degreased"])
        self.assertEqual(last["product"], "Wax X")

    def test_first_hot_wax_gets_the_early_window(self):
        self.write({"bikes": {"b": {"name": "B", "strava_gear_id": "b9", "default_kind": "hot", "waxes": []}}})
        self.log(bike="b")
        self.assertEqual(self.read()["bikes"]["b"]["waxes"][0]["next_due_km"], [150, 250])

    def test_drip_default_and_kind_from_bike(self):
        self.write({"bikes": {"b": {"name": "B", "strava_gear_id": "b9", "default_kind": "drip", "waxes": []}}})
        self.log(bike="b")
        entry = self.read()["bikes"]["b"]["waxes"][0]
        self.assertEqual((entry["kind"], entry["next_due_km"]), ("drip", [200, 300]))

    def test_interval_override(self):
        self.log(bike="road", interval="300-350")
        self.assertEqual(self.read()["bikes"]["road"]["waxes"][-1]["next_due_km"], [300.0, 350.0])

    def test_manual_bike_requires_an_odometer(self):
        with self.assertRaisesRegex(cw.ChainWaxError, "manual bike"):
            self.log(bike="kid")

    def test_manual_bike_logging_updates_its_odometer(self):
        self.log(bike="kid", odometer=130.0)
        kid = self.read()["bikes"]["kid"]
        self.assertEqual((kid["odometer_km"], kid["odometer_date"]), (130.0, "2026-06-01"))

    def test_past_date_needs_an_explicit_odometer_for_strava_bikes(self):
        with self.assertRaisesRegex(cw.ChainWaxError, "past --date"):
            self.log(bike="road", date="2026-05-20")
        self.log(bike="road", date="2026-05-20", odometer=1600.0)
        self.assertEqual(self.read()["bikes"]["road"]["waxes"][-1]["date"], "2026-05-20")

    def test_rejects_future_date_bad_date_and_unknown_bike(self):
        for kw, msg in [(dict(bike="road", date="2026-07-01"), "future"),
                        (dict(bike="road", date="01/06/2026"), "Invalid date"),
                        (dict(bike="nope"), "Unknown bike")]:
            with self.assertRaisesRegex(cw.ChainWaxError, msg):
                self.log(**kw)

    def test_rejects_odometer_below_last_wax_unless_forced(self):
        with self.assertRaisesRegex(cw.ChainWaxError, "below the last wax"):
            self.log(bike="road", odometer=900.0)
        self.assertEqual(len(self.read()["bikes"]["road"]["waxes"]), 2)
        self.log(bike="road", odometer=900.0, force=True)
        self.assertEqual(len(self.read()["bikes"]["road"]["waxes"]), 3)

    def test_rejects_date_before_last_wax_unless_forced(self):
        with self.assertRaisesRegex(cw.ChainWaxError, "before the last logged wax"):
            self.log(bike="road", odometer=1700.0, date="2026-02-01")


class SetOdometerAndAddBike(TempLedger):
    def test_set_odometer_manual_only(self):
        self.write(ledger())
        self.run_quiet(cw.cmd_set_odometer, ns(ledger=str(self.path), bike="kid", km=120.0, date="2026-05-31"))
        self.assertEqual(self.read()["bikes"]["kid"]["odometer_km"], 120.0)
        with self.assertRaisesRegex(cw.ChainWaxError, "live from Strava"):
            cw.cmd_set_odometer(ns(ledger=str(self.path), bike="road", km=1.0))
        with self.assertRaisesRegex(cw.ChainWaxError, "negative"):
            cw.cmd_set_odometer(ns(ledger=str(self.path), bike="kid", km=-1.0))

    def test_add_bike_creates_the_ledger(self):
        self.assertFalse(self.path.exists())
        self.run_quiet(cw.cmd_add_bike, ns(ledger=str(self.path), bike="road", name="Road", gear_id="b123", kind="hot"))
        self.assertEqual(self.read()["bikes"]["road"]["strava_gear_id"], "b123")
        self.run_quiet(cw.cmd_add_bike, ns(ledger=str(self.path), bike="kid", name="Kid", manual=True, odometer=10.0, kind="hot"))
        self.assertEqual(self.read()["bikes"]["kid"]["odometer_km"], 10.0)

    def test_add_bike_validation(self):
        self.write(ledger())
        for kw, msg in [(dict(bike="road", name="x", gear_id="b1"), "already exists"),
                        (dict(bike="Bad Id", name="x", gear_id="b1"), "lowercase"),
                        (dict(bike="a", name="x"), "exactly one"),
                        (dict(bike="a", name="x", gear_id="b1", manual=True), "exactly one"),
                        (dict(bike="a", name="x", gear_id="b1", odometer=5.0), "only for manual")]:
            with self.assertRaisesRegex(cw.ChainWaxError, msg):
                cw.cmd_add_bike(ns(ledger=str(self.path), kind="hot", **kw))


class LedgerSafety(TempLedger):
    def test_missing_ledger_explains_how_to_create_one(self):
        with self.assertRaisesRegex(cw.ChainWaxError, "add-bike"):
            cw.load_ledger(self.path)

    def test_corrupt_ledger_is_reported_and_left_alone(self):
        self.path.write_text("{ not json")
        with self.assertRaisesRegex(cw.ChainWaxError, "not valid JSON"):
            cw.load_ledger(self.path)
        with self.assertRaises(cw.ChainWaxError):
            cw.cmd_add_bike(ns(ledger=str(self.path), bike="x", name="X", gear_id="b1", kind="hot"))
        self.assertEqual(self.path.read_text(), "{ not json")

    def test_ledger_without_bikes_is_rejected(self):
        self.write({"nope": 1})
        with self.assertRaisesRegex(cw.ChainWaxError, "bikes"):
            cw.load_ledger(self.path)

    def test_failed_write_keeps_the_original_and_leaves_no_temp_files(self):
        self.write(ledger())
        before = self.path.read_text()
        with self.assertRaises(TypeError):
            cw.save_ledger(self.path, {"bikes": {"x": object()}})
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["chain-wax.json"])

    def test_ledger_path_precedence(self):
        with mock.patch.dict(os.environ, {"CHAIN_WAX_LEDGER": "/tmp/from-env.json"}):
            self.assertEqual(cw.ledger_path("/tmp/arg.json"), Path("/tmp/arg.json"))
            self.assertEqual(cw.ledger_path(None), Path("/tmp/from-env.json"))

    def test_legacy_ledger_location_is_used_with_a_notice(self):
        legacy = self.dir / "legacy.json"
        legacy.write_text(json.dumps(ledger()))
        new = self.dir / "new" / "chain-wax.json"
        err = io.StringIO()
        with mock.patch.object(cw, "DEFAULT_LEDGER", new), mock.patch.object(cw, "LEGACY_LEDGER", legacy), \
             mock.patch.dict(os.environ, {}, clear=False), contextlib.redirect_stderr(err):
            os.environ.pop("CHAIN_WAX_LEDGER", None)
            self.assertEqual(cw.ledger_path(None), legacy)
        self.assertIn("old location", err.getvalue())

    def test_new_location_wins_over_legacy(self):
        legacy, new = self.dir / "legacy.json", self.dir / "chain-wax.json"
        legacy.write_text("{}"); new.write_text("{}")
        with mock.patch.object(cw, "DEFAULT_LEDGER", new), mock.patch.object(cw, "LEGACY_LEDGER", legacy), \
             mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHAIN_WAX_LEDGER", None)
            self.assertEqual(cw.ledger_path(None), new)

    def test_no_ledger_anywhere_uses_the_new_location(self):
        new = self.dir / "new" / "chain-wax.json"
        with mock.patch.object(cw, "DEFAULT_LEDGER", new), mock.patch.object(cw, "LEGACY_LEDGER", self.dir / "nope.json"), \
             mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHAIN_WAX_LEDGER", None)
            self.assertEqual(cw.ledger_path(None), new)


class Cli(TempLedger):
    def test_cli_round_trip_on_a_manual_bike(self):
        L = ["--ledger", str(self.path)]
        for argv in (["add-bike", "kid", "--name", "Kid", "--manual", "--odometer", "10"],
                     ["log", "kid", "--odometer", "10", "--date", "2026-05-01", "--interval", "450-500"],
                     ["set-odometer", "kid", "470", "--date", "2026-05-30"]):
            rc, _ = self.run_quiet(cw.main, L + argv)
            self.assertEqual(rc, 0, argv)
        with mock.patch.object(cw, "date") as fake_date:
            fake_date.today.return_value = date(2026, 6, 1)
            fake_date.side_effect = lambda *a, **k: date(*a, **k)
            rc, out = self.run_quiet(cw.main, L + ["report", "--json"])
        row = json.loads(out)["bikes"][0]
        self.assertEqual((rc, row["km_since_wax"], row["status"]), (0, 460.0, "DUE"))

    def test_errors_exit_1_without_a_traceback(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = cw.main(["--ledger", str(self.path), "log", "nope"])
        self.assertEqual(rc, 1)
        self.assertIn("Error:", err.getvalue())

    def test_example_ledger_is_valid_and_reports(self):
        example = SCRIPT.parent.parent / "data" / "chain-wax.example.json"
        data = cw.load_ledger(example)
        rows, problems = cw.build_report(data, fetch=lambda gid: 1500.0, today=date(2026, 3, 5))
        self.assertEqual(problems, [])
        self.assertEqual({r["bike"] for r in rows}, {"road", "partner_bike"})


if __name__ == "__main__":
    unittest.main()
