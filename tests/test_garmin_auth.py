"""Offline tests for skills/garmin-health-analysis/scripts/garmin_auth.py (no network, no Garmin account).

Run from the repo root:  .venv/bin/python3 -m unittest discover -s tests -v
"""
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "garmin-health-analysis" / "scripts"
AUTH = SCRIPTS / "garmin_auth.py"


def load_auth(token_dir):
    """Import garmin_auth fresh with GARMIN_TOKEN_DIR pointing at token_dir."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        with mock.patch.dict(os.environ, {"GARMIN_TOKEN_DIR": str(token_dir)}):
            sys.modules.pop("garmin_auth", None)
            return importlib.import_module("garmin_auth")
    finally:
        sys.path.remove(str(SCRIPTS))


def run_cli(*args, env_extra=None, stdin=subprocess.DEVNULL, detach=False):
    env = {**os.environ, "GARMIN_TOKEN_DIR": tempfile.mkdtemp()}
    env.pop("GARMIN_PASSWORD", None)
    env.pop("GARMIN_EMAIL", None)
    env.update(env_extra or {})
    cmd = [sys.executable, str(AUTH), *args]
    if detach:  # drop the controlling terminal so /dev/tty is unavailable
        cmd = ["setsid", "-w", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, stdin=stdin, timeout=60)


class CommandLine(unittest.TestCase):
    def test_password_flag_is_rejected(self):
        p = run_cli("login", "--email", "a@b.c", "--password", "hunter2")
        self.assertEqual(p.returncode, 2)
        self.assertIn("--password has been removed", p.stderr)
        self.assertNotIn("hunter2", p.stdout + p.stderr)

    def test_password_flag_is_hidden_from_help(self):
        p = run_cli("login", "--help")
        self.assertNotIn("--password ", p.stdout)
        self.assertIn("--password-stdin", p.stdout)

    @unittest.skipUnless(os.name == "posix", "needs setsid")
    def test_no_terminal_gives_instructions_instead_of_hanging(self):
        p = run_cli("login", "--email", "a@b.c", detach=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("No terminal available", p.stderr)
        self.assertIn("garmin_auth.py login", p.stderr)

    def test_status_without_tokens(self):
        p = run_cli("status")
        self.assertEqual(p.returncode, 1)
        self.assertIn("Not authenticated", p.stderr)

    def test_status_detects_tokens_from_older_version(self):
        d = tempfile.mkdtemp()
        (Path(d) / "oauth1_token.json").write_text("{}")
        p = run_cli("status", env_extra={"GARMIN_TOKEN_DIR": d})
        self.assertEqual(p.returncode, 1)
        self.assertIn("older version", p.stderr)


class Credentials(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.auth = load_auth(self.dir)

    def test_password_from_stdin(self):
        with mock.patch.object(sys, "stdin", io.StringIO("s3cret\nignored\n")):
            email, pw = self.auth.resolve_credentials("a@b.c", password_stdin=True)
        self.assertEqual((email, pw), ("a@b.c", "s3cret"))

    def test_password_from_env(self):
        with mock.patch.dict(os.environ, {"GARMIN_PASSWORD": "fromenv", "GARMIN_EMAIL": "e@x.y"}):
            self.assertEqual(self.auth.resolve_credentials(None, False), ("e@x.y", "fromenv"))

    def test_password_prompt_is_hidden(self):
        with mock.patch.dict(os.environ, {}, clear=False), \
             mock.patch.object(self.auth, "_has_terminal", return_value=True), \
             mock.patch.object(self.auth.getpass, "getpass", return_value="typed") as gp:
            os.environ.pop("GARMIN_PASSWORD", None)
            self.assertEqual(self.auth.resolve_credentials("a@b.c", False), ("a@b.c", "typed"))
        gp.assert_called_once()

    def test_config_password_is_ignored_with_warning(self):
        cfg = Path(self.dir) / "config.json"
        cfg.write_text(json.dumps({"email": "cfg@x.y", "password": "plaintext"}))
        with mock.patch.object(self.auth, "CONFIG_FILE", cfg), \
             mock.patch.dict(os.environ, {"GARMIN_PASSWORD": "pw"}), \
             mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            email, pw = self.auth.resolve_credentials(None, False)
        self.assertEqual((email, pw), ("cfg@x.y", "pw"))
        self.assertIn("Ignoring the password", err.getvalue())
        self.assertNotIn("plaintext", err.getvalue())


class Login(unittest.TestCase):
    def test_login_stores_tokens_only_never_the_password(self):
        d = Path(tempfile.mkdtemp()) / "tokens"
        auth = load_auth(d)

        class FakeInner:
            def dump(self, path):
                (Path(path) / "garmin_tokens.json").write_text('{"di_token": "t"}')

        class FakeGarmin:
            def __init__(self, email=None, password=None, prompt_mfa=None):
                self.client = FakeInner()
            def login(self, tokenstore=None):
                assert tokenstore is None, "explicit login must be a fresh credential login"
            def get_user_summary(self, day):
                return {"displayName": "Tester"}

        with mock.patch.object(auth, "Garmin", FakeGarmin):
            self.assertTrue(auth.login("a@b.c", "TopSecretPassword"))
        files = list(d.rglob("*"))
        self.assertTrue(files)
        for f in files:
            if f.is_file():
                self.assertNotIn("TopSecretPassword", f.read_text())
        self.assertEqual(d.stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
