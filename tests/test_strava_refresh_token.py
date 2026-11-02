"""Offline tests for skills/strava/scripts/refresh_token.py (fake tokens, scratch HOME, no network).

Run from the repo root:  .venv/bin/python3 -m unittest discover -s tests -v
"""
import atexit
import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

_TEMP_DIRS = []


def make_temp_dir():
    """A temp directory that is removed when the test run ends."""
    path = tempfile.mkdtemp()
    _TEMP_DIRS.append(path)
    return path


atexit.register(lambda: [shutil.rmtree(p, ignore_errors=True) for p in _TEMP_DIRS])

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "strava" / "scripts" / "refresh_token.py"
spec = importlib.util.spec_from_file_location("refresh_token", SCRIPT)
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)

ENV_KEYS = ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN", "STRAVA_ACCESS_TOKEN")
GOOD = {"access_token": "new-access-FAKE", "refresh_token": "new-refresh-FAKE", "expires_at": 1893456000,
        "token_type": "Bearer"}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def respond(payload):
    return FakeResponse(json.dumps(payload).encode())


class RefreshToken(unittest.TestCase):
    def setUp(self):
        self.home = Path(make_temp_dir())
        self.cfg = self.home / ".config" / "strava"
        self.path = self.cfg / "credentials.json"
        env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
        env["HOME"] = str(self.home)
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        # The bug only shows with a permissive umask (the usual 022), so pin it instead of trusting the runner's
        self.addCleanup(os.umask, os.umask(0o022))

    def write_creds(self, mode=0o600, **extra):
        self.cfg.mkdir(parents=True, exist_ok=True)
        creds = {"STRAVA_CLIENT_ID": "111", "STRAVA_CLIENT_SECRET": "secret-FAKE",
                 "STRAVA_ACCESS_TOKEN": "old-access-FAKE", "STRAVA_REFRESH_TOKEN": "old-refresh-FAKE"}
        creds.update(extra)
        self.path.write_text(json.dumps(creds, indent=4))
        os.chmod(self.path, mode)
        return creds

    def run_main(self, urlopen_result=None, urlopen_error=None):
        out, err = io.StringIO(), io.StringIO()
        target = mock.Mock(side_effect=urlopen_error) if urlopen_error else mock.Mock(return_value=urlopen_result)
        with mock.patch.object(rt.urllib.request, "urlopen", target), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rt.main([])
        self.target = target
        return code, out.getvalue(), err.getvalue()

    def mode(self):
        return stat.S_IMODE(self.path.stat().st_mode)

    def test_mode_600_stays_600_and_tokens_are_updated(self):
        self.write_creds(0o600)
        code, out, _ = self.run_main(respond(GOOD))
        self.assertEqual(code, 0)
        self.assertEqual(self.mode(), 0o600)
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["STRAVA_ACCESS_TOKEN"], "new-access-FAKE")
        self.assertEqual(saved["STRAVA_REFRESH_TOKEN"], "new-refresh-FAKE")
        self.assertIn("Token refreshed successfully", out)
        self.assertIn("Updated", out)

    def test_loose_file_is_tightened_to_600(self):
        self.write_creds(0o664)
        self.assertEqual(self.run_main(respond(GOOD))[0], 0)
        self.assertEqual(self.mode(), 0o600)

    def test_other_keys_are_kept(self):
        self.write_creds(extra_key="keep me")
        self.run_main(respond(GOOD))
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["extra_key"], "keep me")
        self.assertEqual(saved["STRAVA_CLIENT_SECRET"], "secret-FAKE")

    def test_no_temp_file_is_left_behind(self):
        self.write_creds()
        self.run_main(respond(GOOD))
        self.assertEqual([p.name for p in self.cfg.iterdir()], ["credentials.json"])

    def test_request_carries_the_refresh_grant_in_the_body_not_the_url(self):
        self.write_creds()
        self.run_main(respond(GOOD))
        req = self.target.call_args[0][0]
        self.assertEqual(req.full_url, "https://www.strava.com/oauth/token")
        self.assertEqual(req.get_method(), "POST")
        body = req.data.decode()
        self.assertIn("grant_type=refresh_token", body)
        self.assertIn("refresh_token=old-refresh-FAKE", body)
        self.assertIn("client_id=111", body)

    def test_response_without_an_access_token_leaves_the_file_byte_identical(self):
        self.write_creds(0o664)
        before = self.path.read_bytes()
        code, out, _ = self.run_main(respond({"message": "Authorization Error"}))
        self.assertEqual(code, 1)
        self.assertIn("Token refresh failed", out)
        self.assertIn("Authorization Error", out)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.mode(), 0o664)  # untouched, including its mode

    def test_response_without_a_refresh_token_is_a_failure(self):
        self.write_creds()
        before = self.path.read_bytes()
        code, _, _ = self.run_main(respond({"access_token": "only-access-FAKE"}))
        self.assertEqual(code, 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_non_json_response_is_a_failure(self):
        self.write_creds()
        before = self.path.read_bytes()
        code, out, _ = self.run_main(FakeResponse(b"<html>bad gateway</html>"))
        self.assertEqual(code, 1)
        self.assertIn("bad gateway", out)
        self.assertEqual(self.path.read_bytes(), before)

    def test_http_error_body_is_reported(self):
        self.write_creds()
        err = urllib.error.HTTPError(rt.TOKEN_URL, 400, "Bad Request", {}, io.BytesIO(b'{"message":"Bad Request"}'))
        code, out, _ = self.run_main(urlopen_error=err)
        self.assertEqual(code, 1)
        self.assertIn("Bad Request", out)

    def test_network_error_is_a_failure_and_leaves_the_file_alone(self):
        self.write_creds()
        before = self.path.read_bytes()
        code, out, _ = self.run_main(urlopen_error=urllib.error.URLError("offline"))
        self.assertEqual(code, 1)
        self.assertIn("could not reach Strava", out)
        self.assertEqual(self.path.read_bytes(), before)

    def test_env_credentials_with_no_file_refresh_but_create_nothing(self):
        os.environ.update(STRAVA_CLIENT_ID="111", STRAVA_CLIENT_SECRET="s-FAKE", STRAVA_REFRESH_TOKEN="r-FAKE")
        code, out, err = self.run_main(respond(GOOD))
        self.assertEqual(code, 0)
        self.assertIn("skipping write-back", err)
        self.assertFalse(self.cfg.exists())

    def test_missing_credentials_is_an_error_and_makes_no_request(self):
        code, out, _ = self.run_main(respond(GOOD))
        self.assertEqual(code, 1)
        self.assertIn("Missing Strava credentials", out)
        self.target.assert_not_called()

    def test_environment_wins_and_the_file_fills_the_gaps(self):
        self.write_creds()
        os.environ["STRAVA_REFRESH_TOKEN"] = "env-refresh-FAKE"
        self.run_main(respond(GOOD))
        body = self.target.call_args[0][0].data.decode()
        self.assertIn("refresh_token=env-refresh-FAKE", body)  # from the environment
        self.assertIn("client_id=111", body)                   # from the file

    def test_malformed_credentials_file_is_reported_and_not_overwritten(self):
        self.cfg.mkdir(parents=True)
        self.path.write_text("{not json")
        before = self.path.read_bytes()
        code, _, err = self.run_main(respond(GOOD))
        self.assertEqual(code, 1)
        self.assertIn("cannot read", err)
        self.assertEqual(self.path.read_bytes(), before)

    def test_token_text_is_never_run_as_code(self):
        """The old script pasted the tokens into a Python heredoc; a quote in a token must be plain data now."""
        self.write_creds()
        tricky = dict(GOOD, access_token='x"; import os; os.system("true") #')
        self.run_main(respond(tricky))
        self.assertEqual(json.loads(self.path.read_text())["STRAVA_ACCESS_TOKEN"], tricky["access_token"])

    def test_shell_wrapper_still_reaches_the_python_script(self):
        wrapper = REPO / "skills" / "strava" / "scripts" / "refresh_token.sh"
        # No credentials anywhere: the script must stop at "Missing Strava credentials" before any network call
        env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
        r = subprocess.run(["bash", str(wrapper)], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Missing Strava credentials", r.stdout)


if __name__ == "__main__":
    unittest.main()
