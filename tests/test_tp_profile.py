"""Offline tests for the TrainingPeaks `profile` command (synthetic data, no network).

Run from the repo root:  .venv/bin/python3 -m unittest discover -s tests -v
"""
import contextlib
import importlib.util
import io
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest import mock

TP_PATH = Path(__file__).resolve().parent.parent / "skills" / "trainingpeaks" / "scripts" / "tp.py"
spec = importlib.util.spec_from_file_location("tp", TP_PATH)
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)

PROFILE = {"user": {"firstName": "Test", "lastName": "Rider", "username": "rider@example.com",
                    "personId": 1, "accountType": "Premium",
                    "athletes": [{"weight": 70, "dateOfBirth": "1990-06-15T00:00:00", "sex": "F",
                                  "cyclingFtp": 250, "runningFtp": None, "swimFtp": None}]}}


class AgeYears(unittest.TestCase):
    def test_before_and_after_the_birthday(self):
        self.assertEqual(tp._age_years("1990-06-15", today=date(2026, 6, 14)), "35")
        self.assertEqual(tp._age_years("1990-06-15", today=date(2026, 6, 15)), "36")

    def test_missing_or_bad_dates_show_a_dash(self):
        for value in (None, "", "not a date"):
            self.assertEqual(tp._age_years(value), "—")


class ProfileOutput(unittest.TestCase):
    def run_profile(self):
        out = io.StringIO()
        with mock.patch.object(tp, "api_get", return_value=(200, PROFILE)), contextlib.redirect_stdout(out):
            tp.cmd_profile(Namespace(json=False))
        return out.getvalue()

    def test_shows_age_but_not_date_of_birth_or_sex(self):
        text = self.run_profile()
        self.assertIn("Age:", text)
        self.assertNotIn("1990", text)
        self.assertNotIn("DOB", text)
        self.assertNotIn("Gender", text)

    def test_still_shows_the_training_numbers(self):
        text = self.run_profile()
        self.assertIn("250 W", text)
        self.assertIn("70 kg", text)


if __name__ == "__main__":
    unittest.main()
