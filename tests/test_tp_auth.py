"""Offline tests for TrainingPeaks cookie setup in tp.py: auth, auth-status, file modes (no network).

The cookie below is a made-up string. Run from the repo root:  .venv/bin/python3 -m unittest discover -s tests -v
"""
import atexit
import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

_TEMP_DIRS = []


def make_temp_dir():
    """A temp directory that is removed when the test run ends."""
    path = tempfile.mkdtemp()
    _TEMP_DIRS.append(path)
    return path


atexit.register(lambda: [shutil.rmtree(p, ignore_errors=True) for p in _TEMP_DIRS])

ROOT = Path(__file__).resolve().parent.parent
TP_PATH = ROOT / "skills" / "trainingpeaks" / "scripts" / "tp.py"
spec = importlib.util.spec_from_file_location("tp_auth_under_test", TP_PATH)
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)

FAKE_COOKIE = "FAKE-cookie-value-0123456789"
TOKEN_RESPONSE = {"token": {"access_token": "FAKE-bearer", "expires_in": 3600},
                  "athleteId": 4242, "username": "rider@example.com"}


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class TpCase(unittest.TestCase):
    """Points tp.py at a scratch config folder and blocks real network and environment cookies."""

    def setUp(self):
        d = Path(make_temp_dir()) / "tp"
        self.dir = d
        patches = [
            mock.patch.object(tp, "CONFIG_DIR", d),
            mock.patch.object(tp, "COOKIE_FILE", d / "cookie"),
            mock.patch.object(tp, "TOKEN_FILE", d / "token.json"),
            mock.patch.object(tp, "CONFIG_FILE", d / "config.json"),
            mock.patch.dict(os.environ, {}, clear=False),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("TP_AUTH_COOKIE", None)
        self.network = mock.patch.object(tp, "_http_request", side_effect=AssertionError("unexpected network call"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def run_cmd(self, fn, **kw):
        out, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                fn(Namespace(**kw))
        except SystemExit as e:
            code = e.code
        return code, out.getvalue(), err.getvalue()

    def fake_exchange(self, status=200, data=None):
        return mock.patch.object(tp, "_http_request", return_value=(status, TOKEN_RESPONSE if data is None else data))


class CleanCookie(unittest.TestCase):
    def test_accepts_what_people_really_paste(self):
        for raw in (FAKE_COOKIE, f"  {FAKE_COOKIE}\n", f"Production_tpAuth={FAKE_COOKIE}",
                    f"Production_tpAuth={FAKE_COOKIE};", f'"{FAKE_COOKIE}"', f"'{FAKE_COOKIE}';"):
            self.assertEqual(tp.clean_cookie(raw), FAKE_COOKIE, raw)

    def test_empty_stays_empty(self):
        for raw in ("", "   ", "Production_tpAuth=", ";"):
            self.assertEqual(tp.clean_cookie(raw), "")


class AuthInput(TpCase):
    def auth(self, **kw):
        args = {"cookie": None, "stdin": False}
        args.update(kw)
        with self.fake_exchange():
            return self.run_cmd(tp.cmd_auth, **args)

    def test_no_argument_uses_the_hidden_prompt(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch.object(tp.getpass, "getpass", return_value=FAKE_COOKIE) as prompt:
            code, out, err = self.auth()
        self.assertEqual(code, 0)
        prompt.assert_called_once()
        self.assertEqual((self.dir / "cookie").read_text(), FAKE_COOKIE)
        self.assertNotIn(FAKE_COOKIE, out + err)

    def test_prompt_names_the_readme_section(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=True), \
                mock.patch.object(tp.getpass, "getpass", return_value=FAKE_COOKIE):
            _, out, _ = self.auth()
        self.assertIn("skills/trainingpeaks/README.md", out)

    def test_argument_form_still_works_and_suggests_the_safer_way(self):
        code, out, err = self.auth(cookie=FAKE_COOKIE)
        self.assertEqual(code, 0)
        self.assertEqual((self.dir / "cookie").read_text(), FAKE_COOKIE)
        self.assertIn("no argument", err)
        self.assertNotIn(FAKE_COOKIE, out + err)

    def test_stdin_reads_the_first_line(self):
        with mock.patch.object(sys, "stdin", io.StringIO(f"Production_tpAuth={FAKE_COOKIE}\nignored\n")):
            code, out, err = self.auth(stdin=True)
        self.assertEqual(code, 0)
        self.assertEqual((self.dir / "cookie").read_text(), FAKE_COOKIE)
        self.assertNotIn(FAKE_COOKIE, out + err)

    def test_no_terminal_and_no_flag_explains_stdin_and_stores_nothing(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            code, out, err = self.auth()
        self.assertEqual(code, 1)
        self.assertIn("--stdin", err)
        self.assertFalse((self.dir / "cookie").exists())

    def test_empty_input_is_refused(self):
        with mock.patch.object(sys, "stdin", io.StringIO("\n")):
            code, _, err = self.auth(stdin=True)
        self.assertEqual(code, 1)
        self.assertIn("empty", err)
        self.assertFalse((self.dir / "cookie").exists())

    def test_argument_and_stdin_together_are_refused(self):
        code, _, err = self.auth(cookie=FAKE_COOKIE, stdin=True)
        self.assertEqual(code, 1)
        self.assertIn("not both", err)

    def test_server_error_on_a_pasted_cookie_hints_at_copying_it_again(self):
        with self.fake_exchange(status=500, data={}):
            code, _, err = self.run_cmd(tp.cmd_auth, cookie=FAKE_COOKIE, stdin=False)
        self.assertEqual(code, 1)
        self.assertIn("HTTP 500", err)
        self.assertIn("copy the whole value again", err)
        self.assertFalse((self.dir / "cookie").exists())
        self.assertNotIn(FAKE_COOKIE, err)

    def test_rejected_cookie_is_not_stored(self):
        with self.fake_exchange(status=401, data={}):
            code, _, err = self.run_cmd(tp.cmd_auth, cookie=FAKE_COOKIE, stdin=False)
        self.assertEqual(code, 1)
        self.assertFalse((self.dir / "cookie").exists())
        self.assertNotIn(FAKE_COOKIE, err)

    def test_saved_time_is_recorded_for_auth_status(self):
        self.auth(cookie=FAKE_COOKIE)
        saved = json.loads((self.dir / "config.json").read_text())["cookie_saved_at"]
        age = datetime.now(timezone.utc) - datetime.fromisoformat(saved)
        self.assertLess(age, timedelta(minutes=1))
        self.assertNotIn(FAKE_COOKIE, (self.dir / "config.json").read_text())


class FileModes(TpCase):
    def test_secret_files_are_owner_only(self):
        with self.fake_exchange():
            self.run_cmd(tp.cmd_auth, cookie=FAKE_COOKIE, stdin=False)
        for name in ("cookie", "token.json", "config.json"):
            self.assertEqual(mode(self.dir / name), 0o600, name)

    def test_cookie_file_is_never_created_wider_than_600(self):
        # The old code wrote the file with the default mode and tightened it afterwards.
        modes = []
        real_open = os.open

        def spy(path, flags, m=0o777, *a, **k):
            if str(path).startswith(str(self.dir)):
                modes.append(m)
            return real_open(path, flags, m, *a, **k)

        with mock.patch.object(os, "open", spy):
            tp.store_cookie(FAKE_COOKIE)
        self.assertEqual(modes, [0o600])

    def test_rewriting_keeps_600_and_leaves_no_temp_file(self):
        tp.store_cookie("first")
        tp.store_cookie(FAKE_COOKIE)
        self.assertEqual(mode(self.dir / "cookie"), 0o600)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["cookie"])
        self.assertEqual((self.dir / "cookie").read_text(), FAKE_COOKIE)

    def test_a_loose_old_cookie_file_is_tightened_on_rewrite(self):
        self.dir.mkdir(parents=True)
        (self.dir / "cookie").write_text("old")
        (self.dir / "cookie").chmod(0o664)
        tp.store_cookie(FAKE_COOKIE)
        self.assertEqual(mode(self.dir / "cookie"), 0o600)


class AuthStatus(TpCase):
    def status(self, check=False):
        return self.run_cmd(tp.cmd_auth_status, check=check)

    def store(self, saved_days_ago=None):
        tp.store_cookie(FAKE_COOKIE)
        cfg = {}
        if saved_days_ago is not None:
            cfg["cookie_saved_at"] = (datetime.now(timezone.utc) - timedelta(days=saved_days_ago, hours=1)).isoformat()
        tp.save_config(cfg)

    def test_shows_how_old_the_cookie_is(self):
        self.store(saved_days_ago=12)
        code, out, _ = self.status()
        self.assertEqual(code, 0)
        self.assertIn("stored 12 days ago", out)

    def test_singular_and_today(self):
        self.store(saved_days_ago=1)
        self.assertIn("stored 1 day ago", self.status()[1])
        tp.save_config({"cookie_saved_at": datetime.now(timezone.utc).isoformat()})
        self.assertIn("stored today", self.status()[1])

    def test_cookie_saved_before_the_date_was_recorded_says_unknown(self):
        self.store()
        _, out, _ = self.status()
        self.assertIn("date unknown", out)

    def test_garbage_date_says_unknown(self):
        self.store()
        tp.save_config({"cookie_saved_at": "yesterday-ish"})
        self.assertIn("date unknown", self.status()[1])

    def test_default_is_offline(self):
        self.store(saved_days_ago=3)
        code, out, _ = self.status()  # any network call raises AssertionError
        self.assertEqual(code, 0)
        self.assertIn("--check", out)

    def test_not_authenticated_points_at_the_readme(self):
        code, out, _ = self.status()
        self.assertEqual(code, 1)
        self.assertIn("skills/trainingpeaks/README.md", out)

    def test_check_valid(self):
        self.store(saved_days_ago=3)
        with self.fake_exchange(200):
            code, out, err = self.status(check=True)
        self.assertEqual(code, 0)
        self.assertIn("accepted", out)
        self.assertNotIn(FAKE_COOKIE, out + err)

    def test_check_expired_gives_the_recovery_steps(self):
        self.store(saved_days_ago=3)
        with self.fake_exchange(401, {}):
            code, out, err = self.status(check=True)
        self.assertEqual(code, 1)
        self.assertIn("rejected", out)
        self.assertIn("tp.py auth", out)
        self.assertIn("skills/trainingpeaks/README.md", out)
        self.assertNotIn(FAKE_COOKIE, out + err)

    def test_check_with_network_trouble_does_not_say_expired(self):
        self.store(saved_days_ago=3)
        with mock.patch.object(tp, "_http_request", return_value=(0, None)):
            code, out, _ = self.status(check=True)
        self.assertEqual(code, 2)
        self.assertIn("Could not check", out)
        self.assertNotIn("expired", out.replace("does not mean it expired", ""))

    def test_check_with_server_error_does_not_say_expired(self):
        self.store(saved_days_ago=3)
        with self.fake_exchange(503, {}):
            code, out, _ = self.status(check=True)
        self.assertEqual(code, 2)
        self.assertIn("HTTP 503", out)
        self.assertIn("copy the whole cookie value again", out)


class ExpiredCookieMessage(TpCase):
    def test_a_401_during_normal_use_gives_numbered_steps_without_the_cookie(self):
        tp.store_cookie(FAKE_COOKIE)
        with self.fake_exchange(401, {}):
            code, _, err = self.run_cmd(lambda a: tp.ensure_token())
        self.assertEqual(code, 1)
        for needle in ("expired", "1.", "2.", "3.", "tp.py auth", "skills/trainingpeaks/README.md"):
            self.assertIn(needle, err)
        self.assertNotIn(FAKE_COOKIE, err)

    def test_check_cookie_network_failure_does_not_exit(self):
        # Un-mocked path: _http_request(fatal=False) returns (0, None) on a network error.
        self.network.stop()
        try:
            with mock.patch.object(tp.urllib.request, "urlopen", side_effect=tp.urllib.error.URLError("boom")):
                self.assertEqual(tp.check_cookie(FAKE_COOKIE)[0], "unreachable")
        finally:
            self.network.start()


if __name__ == "__main__":
    unittest.main()
