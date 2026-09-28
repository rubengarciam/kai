"""Offline tests for skills/gear-maintenance/scripts/tyres.py (synthetic data, no network).

Run from the repo root:  .venv/bin/python3 -m unittest discover -s tests -v
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "skills" / "gear-maintenance"
spec = importlib.util.spec_from_file_location("tyres", SRC / "scripts" / "tyres.py")
ty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ty)

TODAY = date(2026, 6, 1)
REPORT_FIELDS = ("id", "wheelset", "fitted_date", "retired", "wear_check_interval_km")


def base_ledger():
    return {
        "_doc": "keep me",
        "wheelsets": {
            "road": {"name": "Road wheels", "usual_bike": "Road bike", "gear_ids": ["b1"]},
            "tt": {"name": "TT wheels", "usual_bike": "TT bike", "gear_ids": ["b2", "b3"]},
            "store": {"name": "Stored wheels", "usual_bike": "", "gear_ids": []},
        },
        "tyres": [{"id": "road-old-2026-01-01", "wheelset": "road", "model": "Old", "fitted_date": "2026-01-01",
                   "fitted_bike_odometer_km": 100, "wear_check_interval_km": 500, "replace_at_km": 4000,
                   "retired": False, "manual_include_ids": [42], "manual_exclude_ids": [], "note": "interim",
                   "custom_field": {"keep": True}}],
    }


def ns(**kw):
    base = dict(ledger=None, wheelset=None, name=None, usual_bike=None, gear_id=[], model=None, date=None,
                odometer=None, wear_interval=None, replace_at=None, note=None, replace=False, tyre_id=None, json=False)
    base.update(kw)
    return Namespace(**base)


class TempLedger(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "tyres.json"

    def write(self, data):
        self.path.write_text(json.dumps(data, indent=2))

    def read(self):
        return json.loads(self.path.read_text())

    def quiet(self, fn, *a, **kw):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = fn(*a, **kw)
        return rc, out.getvalue()


class AddWheelset(TempLedger):
    def test_creates_the_ledger(self):
        self.quiet(ty.cmd_add_wheelset, ns(ledger=str(self.path), wheelset="road", name="Road", usual_bike="Bike", gear_id=["b123"]))
        self.assertEqual(self.read(), {"wheelsets": {"road": {"name": "Road", "usual_bike": "Bike", "gear_ids": ["b123"]}}, "tyres": []})

    def test_wheelset_without_gear_ids_is_allowed(self):
        self.quiet(ty.cmd_add_wheelset, ns(ledger=str(self.path), wheelset="store", name="Stored"))
        self.assertEqual(self.read()["wheelsets"]["store"]["gear_ids"], [])

    def test_validation(self):
        self.write(base_ledger())
        for kw, msg in [(dict(wheelset="road", name="x"), "already exists"), (dict(wheelset="Bad Id", name="x"), "lowercase"),
                        (dict(wheelset="n", name="x", gear_id=["g55"]), "not a Strava bike id"),
                        (dict(wheelset="n", name="x", gear_id=["b1", "b1"]), "twice")]:
            with self.assertRaisesRegex(ty.TyreError, msg):
                ty.cmd_add_wheelset(ns(ledger=str(self.path), **kw))


class AddSet(TempLedger):
    def setUp(self):
        super().setUp()
        self.write(base_ledger())

    def add(self, fetch=lambda gid: 2222.26, **kw):
        kw.setdefault("ledger", str(self.path))
        return self.quiet(ty.cmd_add_set, ns(**kw), fetch=fetch, today=TODAY)

    def test_refuses_while_the_wheelset_has_an_active_set(self):
        with self.assertRaisesRegex(ty.TyreError, "already has an active tyre set"):
            self.add(wheelset="road", model="New")
        self.assertEqual(len(self.read()["tyres"]), 1)

    def test_replace_retires_the_old_set_and_fits_the_new_one_in_one_write(self):
        rc, out = self.add(wheelset="road", model="GP5000 28mm", replace=True, odometer=500.0, replace_at="4000")
        tyres = self.read()["tyres"]
        old, new = tyres
        self.assertTrue(old["retired"])
        self.assertEqual(old["retired_date"], "2026-06-01")
        self.assertFalse(new["retired"])
        self.assertEqual((new["fitted_date"], new["fitted_bike_odometer_km"], new["replace_at_km"]), ("2026-06-01", 500.0, 4000))
        self.assertIn("Retired road-old-2026-01-01", out)

    def test_replacement_date_before_the_active_set_was_fitted_is_rejected(self):
        with self.assertRaisesRegex(ty.TyreError, "before the active set"):
            self.add(wheelset="road", model="New", replace=True, date="2025-12-01")
        self.assertFalse(self.read()["tyres"][0]["retired"])

    def test_id_format_and_collisions(self):
        self.add(wheelset="store", model="Vittoria Corsa Pro 30mm!", date="2026-05-01")
        self.add(wheelset="tt", model="X", date="2026-05-01")
        ids = [t["id"] for t in self.read()["tyres"]]
        self.assertIn("store-vittoria-corsa-pro-30mm-2026-05-01", ids)
        self.add(wheelset="tt", model="X", date="2026-05-01", replace=True)
        ids = [t["id"] for t in self.read()["tyres"]]
        self.assertIn("tt-x-2026-05-01-2", ids)
        self.add(wheelset="tt", model="X", date="2026-05-01", replace=True)
        ids = [t["id"] for t in self.read()["tyres"]]
        self.assertIn("tt-x-2026-05-01-3", ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_odometer_from_strava_only_with_exactly_one_gear_id_and_today(self):
        self.add(wheelset="store", model="A")                       # no gear ids
        self.add(wheelset="tt", model="B")                          # two gear ids
        self.add(wheelset="road", model="C", replace=True, date="2026-05-30")  # not today
        by_wheelset = {t["wheelset"]: t for t in self.read()["tyres"] if not t.get("retired")}
        self.assertIsNone(by_wheelset["store"]["fitted_bike_odometer_km"])
        self.assertIsNone(by_wheelset["tt"]["fitted_bike_odometer_km"])
        self.assertIsNone(by_wheelset["road"]["fitted_bike_odometer_km"])
        self.add(wheelset="road", model="D", replace=True)          # one gear id, today
        self.assertEqual(self.read()["tyres"][-1]["fitted_bike_odometer_km"], 2222.3)

    def test_explicit_odometer_wins_and_strava_failure_never_blocks(self):
        def boom(gid):
            raise ty.OdometerUnavailable("HTTP 401")
        rc, out = self.add(wheelset="road", model="E", replace=True, fetch=boom)
        self.assertEqual(rc, 0)
        self.assertIsNone(self.read()["tyres"][-1]["fitted_bike_odometer_km"])
        self.assertIn("odometer not recorded", out)
        self.add(wheelset="road", model="F", replace=True, odometer=1234.56, fetch=boom)
        self.assertEqual(self.read()["tyres"][-1]["fitted_bike_odometer_km"], 1234.6)

    def test_defaults_and_optional_replace_at(self):
        self.add(wheelset="store", model="G")
        entry = self.read()["tyres"][-1]
        self.assertEqual(entry["wear_check_interval_km"], 500)
        self.assertNotIn("replace_at_km", entry)
        self.assertEqual((entry["retired"], entry["manual_include_ids"], entry["manual_exclude_ids"], entry["note"]), (False, [], [], ""))

    def test_validation(self):
        for kw, msg in [(dict(wheelset="nope", model="x"), "Unknown wheelset"),
                        (dict(wheelset="store", model="x", date="2026-07-01"), "future"),
                        (dict(wheelset="store", model="x", date="1/6/2026"), "Invalid date"),
                        (dict(wheelset="store", model="x", wear_interval="0"), "greater than 0"),
                        (dict(wheelset="store", model="x", replace_at="abc"), "number of km"),
                        (dict(wheelset="store", model="x", odometer=-5.0), "negative")]:
            with self.assertRaisesRegex(ty.TyreError, msg):
                self.add(**kw)


class Retire(TempLedger):
    def setUp(self):
        super().setUp()
        self.write(base_ledger())

    def test_retire_sets_flag_date_and_appends_note(self):
        self.quiet(ty.cmd_retire, ns(ledger=str(self.path), tyre_id="road-old-2026-01-01", date="2026-05-01", note="cut"), today=TODAY)
        t = self.read()["tyres"][0]
        self.assertEqual((t["retired"], t["retired_date"], t["note"]), (True, "2026-05-01", "interim | cut"))

    def test_errors(self):
        for kw, msg in [(dict(tyre_id="nope"), "Unknown tyre set"), (dict(tyre_id="road-old-2026-01-01", date="2025-01-01"), "before the set was fitted"),
                        (dict(tyre_id="road-old-2026-01-01", date="2026-12-01"), "future")]:
            with self.assertRaisesRegex(ty.TyreError, msg):
                ty.cmd_retire(ns(ledger=str(self.path), **kw), today=TODAY)
        self.quiet(ty.cmd_retire, ns(ledger=str(self.path), tyre_id="road-old-2026-01-01"), today=TODAY)
        with self.assertRaisesRegex(ty.TyreError, "already retired"):
            ty.cmd_retire(ns(ledger=str(self.path), tyre_id="road-old-2026-01-01"), today=TODAY)


class LedgerSafety(TempLedger):
    def test_unknown_fields_notes_and_key_order_survive_a_write(self):
        self.write(base_ledger())
        self.quiet(ty.cmd_add_wheelset, ns(ledger=str(self.path), wheelset="extra", name="Extra"))
        data = self.read()
        self.assertEqual(data["_doc"], "keep me")
        self.assertEqual(list(data), ["_doc", "wheelsets", "tyres"])
        self.assertEqual(data["tyres"][0], base_ledger()["tyres"][0])   # untouched, incl. custom_field and manual_include_ids

    def test_corrupt_ledger_is_reported_and_left_alone(self):
        self.path.write_text("{ nope")
        for fn, a in [(ty.cmd_add_wheelset, ns(wheelset="x", name="X")), (ty.cmd_list, ns()), (ty.cmd_retire, ns(tyre_id="x"))]:
            with self.assertRaisesRegex(ty.TyreError, "not valid JSON"):
                fn(Namespace(**{**vars(a), "ledger": str(self.path)}))
        self.assertEqual(self.path.read_text(), "{ nope")

    def test_wrong_shape_and_missing_ledger(self):
        self.write({"wheelsets": []})
        with self.assertRaisesRegex(ty.TyreError, "does not look like"):
            ty.load_ledger(self.path)
        with self.assertRaisesRegex(ty.TyreError, "add-wheelset"):
            ty.load_ledger(self.dir / "missing.json")

    def test_failed_write_keeps_the_original_and_leaves_no_temp_file(self):
        self.write(base_ledger())
        before = self.path.read_text()
        with self.assertRaises(TypeError):
            ty.save_ledger(self.path, {"wheelsets": {"x": object()}, "tyres": []})
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["tyres.json"])

    def test_list_reports_orphans(self):
        data = base_ledger(); data["tyres"][0]["wheelset"] = "gone"
        self.write(data)
        rc, out = self.quiet(ty.cmd_list, ns(ledger=str(self.path)))
        self.assertIn("unknown wheelset: road-old-2026-01-01", out)


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class LedgerLocationAndReport(unittest.TestCase):
    """Runs the real scripts in a temp copy of the skill so the default ledger paths are exercised."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.skill = self.root / "skills" / "gear-maintenance"
        shutil.copytree(SRC / "scripts", self.skill / "scripts")
        (self.skill / "data").mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("STRAVA_", "TYRES_"))}
        self.env["HOME"] = str(self.root)

    def tyres(self, *args):
        return subprocess.run([sys.executable, str(self.skill / "scripts" / "tyres.py"), *args],
                              capture_output=True, text=True, env=self.env, timeout=60)

    def report(self):
        return subprocess.run(["bash", str(self.skill / "scripts" / "tyre-mileage.sh")],
                              capture_output=True, text=True, env=self.env, timeout=60)

    def test_legacy_only_ledger_is_edited_in_place_and_no_new_file_is_created(self):
        legacy = self.root / "skills" / "strava" / "data"
        legacy.mkdir(parents=True)
        (legacy / "tyres.json").write_text(json.dumps(base_ledger()))
        p = self.tyres("add-wheelset", "extra", "--name", "Extra")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("old location", p.stderr)
        self.assertFalse((self.skill / "data" / "tyres.json").exists())
        self.assertIn("extra", json.loads((legacy / "tyres.json").read_text())["wheelsets"])
        self.assertIn("old location", self.report().stderr)   # the report sees the same file

    def test_new_location_wins_over_legacy(self):
        legacy = self.root / "skills" / "strava" / "data"
        legacy.mkdir(parents=True)
        (legacy / "tyres.json").write_text("{}")
        (self.skill / "data" / "tyres.json").write_text(json.dumps(base_ledger()))
        p = self.tyres("list")
        self.assertNotIn("old location", p.stderr)
        self.assertIn("Road wheels", p.stdout)

    def test_helper_output_is_accepted_by_the_mileage_report(self):
        self.assertEqual(self.tyres("add-wheelset", "road", "--name", "Road", "--gear-id", "b123").returncode, 0)
        p = self.tyres("add-set", "road", "--model", "GP5000", "--date", "2026-01-01", "--odometer", "10", "--replace-at", "4000")
        self.assertEqual(p.returncode, 0, p.stderr)
        r = self.report()   # empty HOME, no token: must get past the ledger checks
        self.assertIn("STRAVA_ACCESS_TOKEN not set", r.stderr)
        self.assertNotIn("no tyre ledger", r.stderr)
        ledger = json.loads((self.skill / "data" / "tyres.json").read_text())
        tyre = ledger["tyres"][0]
        for field in REPORT_FIELDS:
            self.assertIn(field, tyre)
        self.assertRegex(tyre["fitted_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn(tyre["wheelset"], ledger["wheelsets"])
        self.assertIs(tyre["retired"], False)

    def test_cli_errors_exit_1_without_a_traceback(self):
        p = self.tyres("retire", "nope")
        self.assertEqual(p.returncode, 1)
        self.assertIn("Error:", p.stderr)
        self.assertNotIn("Traceback", p.stderr)

    def test_ledger_path_precedence(self):
        with mock.patch.dict(os.environ, {"TYRES_LEDGER": "/tmp/from-env.json"}):
            self.assertEqual(ty.ledger_path("/tmp/arg.json"), Path("/tmp/arg.json"))
            self.assertEqual(ty.ledger_path(None), Path("/tmp/from-env.json"))


if __name__ == "__main__":
    unittest.main()
