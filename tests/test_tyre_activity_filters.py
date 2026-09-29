"""Offline tests for skills/gear-maintenance/scripts/tyre_activity_filters.py (synthetic data, no network).

Covers the bug in https://github.com/rubengarciam/kai/issues/22: fitted_date used to be compared against
each activity's UTC timestamp, so a ride on the local morning of the fit day (east of UTC, e.g. Sydney)
could be missed entirely, and a ride the evening before (west of UTC) could be wrongly counted.

Run from the repo root:  .venv/bin/python3 -m unittest discover -s tests -v
"""
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "gear-maintenance" / "scripts" / "tyre_activity_filters.py"
spec = importlib.util.spec_from_file_location("tyre_activity_filters", SCRIPT)
taf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(taf)


def activity(id, local_iso, gear_id="b1", indoor=False):
    """A minimal synthetic Strava activity. local_iso is the athlete's local wall-clock start time,
    formatted the way Strava serializes start_date_local: no real UTC offset, just a trailing 'Z'."""
    act = {"id": id, "gear_id": gear_id, "start_date_local": local_iso + "Z", "distance": 10000}
    if indoor:
        act["trainer"] = True
    else:
        act["start_latlng"] = [1.0, 2.0]
    return act


class LocalDate(unittest.TestCase):
    def test_reads_the_date_part_of_start_date_local_not_start_date(self):
        # start_date_local carries a trailing Z but is NOT UTC; local_date must not touch start_date
        act = {"start_date_local": "2026-09-26T05:18:53Z", "start_date": "2026-09-25T19:18:53Z"}
        self.assertEqual(taf.local_date(act), "2026-09-26")

    def test_missing_field_is_handled_without_crashing(self):
        self.assertEqual(taf.local_date({}), "")


class FetchAfterEpoch(unittest.TestCase):
    def test_margin_covers_every_real_world_utc_offset(self):
        fitted = "2026-06-01"
        naive_utc_midnight = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
        after = taf.fetch_after_epoch(fitted)
        self.assertLess(after, naive_utc_midnight)
        # UTC+14 (the most extreme real timezone, e.g. Kiribati): local midnight of fitted_date is
        # (fitted_date - 1) 10:00 UTC. The fetch boundary must be at or before that.
        utc14_local_midnight = naive_utc_midnight - 14 * 3600
        self.assertLessEqual(after, utc14_local_midnight)

    def test_margin_is_exactly_24_hours_before_utc_midnight(self):
        after = taf.fetch_after_epoch("2026-06-01")
        expected = int(datetime(2026, 5, 31, tzinfo=timezone.utc).timestamp())
        self.assertEqual(after, expected)


class IsIndoor(unittest.TestCase):
    def test_virtual_ride_type_or_sport_type(self):
        self.assertTrue(taf.is_indoor({"type": "VirtualRide"}))
        self.assertTrue(taf.is_indoor({"sport_type": "VirtualRide"}))

    def test_trainer_flag(self):
        self.assertTrue(taf.is_indoor({"type": "Ride", "trainer": True, "start_latlng": [1, 2]}))

    def test_no_gps_start(self):
        self.assertTrue(taf.is_indoor({"type": "Ride", "start_latlng": None}))
        self.assertTrue(taf.is_indoor({"type": "Ride"}))

    def test_outdoor_ride_with_gps_is_not_indoor(self):
        self.assertFalse(taf.is_indoor({"type": "Ride", "trainer": False, "start_latlng": [1, 2]}))


class ClassifyActivity(unittest.TestCase):
    """The regression cases from issue #22: synthetic activities either side of local midnight,
    in a timezone east of UTC (Sydney, UTC+10) and one west of UTC (US Eastern, UTC-5)."""

    def classify(self, act, fitted="2026-06-01", gear_ids=None, inc=None, exc=None):
        return taf.classify_activity(act, fitted, gear_ids or {"b1"}, inc or set(), exc or set())

    # --- Sydney, UTC+10: a ride in the local morning of the fit day must not be missed ---

    def test_sydney_morning_ride_on_fit_day_is_counted(self):
        # 07:00 local in Sydney on 2026-06-01 is 21:00 UTC on 2026-05-31 -- before UTC midnight of the fit
        # date, which is exactly what made the old (UTC-based) filter drop it.
        ride = activity(1, "2026-06-01T07:00:00")
        self.assertEqual(self.classify(ride), ("counted", None))

    def test_sydney_ride_the_evening_before_the_fit_day_is_excluded(self):
        ride = activity(2, "2026-05-31T20:00:00")
        self.assertEqual(self.classify(ride), ("excluded", "before fitted_date"))

    # --- US Eastern, UTC-5: an evening ride the day before must not be wrongly counted ---

    def test_us_eastern_evening_ride_the_day_before_is_excluded(self):
        # 20:00 local on 2026-05-31 in UTC-5 is 01:00 UTC on 2026-06-01 -- after UTC midnight of the fit
        # date, which is exactly what made the old (UTC-based) filter wrongly count it.
        ride = activity(3, "2026-05-31T20:00:00")
        self.assertEqual(self.classify(ride), ("excluded", "before fitted_date"))

    def test_us_eastern_ride_just_after_local_midnight_on_the_fit_day_is_counted(self):
        ride = activity(4, "2026-06-01T00:05:00")
        self.assertEqual(self.classify(ride), ("counted", None))

    # --- the other classification rules, unchanged by the fix ---

    def test_manual_exclude_wins_over_everything(self):
        ride = activity(5, "2026-06-01T07:00:00")
        self.assertEqual(self.classify(ride, exc={5}), ("excluded", "manual_exclude"))

    def test_wrong_gear_is_skipped_not_excluded(self):
        ride = activity(6, "2026-06-01T07:00:00", gear_id="b2")
        self.assertEqual(self.classify(ride), ("skip", None))

    def test_manual_include_rescues_wrong_gear(self):
        ride = activity(7, "2026-06-01T07:00:00", gear_id="b2")
        self.assertEqual(self.classify(ride, inc={7}), ("counted", None))

    def test_indoor_ride_is_excluded(self):
        ride = activity(8, "2026-06-01T07:00:00", indoor=True)
        self.assertEqual(self.classify(ride), ("excluded", "indoor"))

    def test_manual_include_rescues_a_misclassified_indoor_ride(self):
        ride = activity(9, "2026-06-01T07:00:00", indoor=True)
        self.assertEqual(self.classify(ride, inc={9}), ("counted", None))

    def test_manual_include_does_not_rescue_a_ride_before_fitted_date(self):
        # manual_include_ids fixes gear/indoor misclassification, not backdating a tyre's fitting.
        ride = activity(10, "2026-05-31T20:00:00")
        self.assertEqual(self.classify(ride, inc={10}), ("excluded", "before fitted_date"))

    def test_on_the_boundary_the_fit_date_itself_counts(self):
        ride = activity(11, "2026-06-01T00:00:00")
        self.assertEqual(self.classify(ride), ("counted", None))


if __name__ == "__main__":
    unittest.main()
