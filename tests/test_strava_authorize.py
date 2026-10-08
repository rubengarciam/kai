"""Offline tests for skills/strava/scripts/authorize.py (no network, no Strava account, no real credentials file).

Run from the repo root:  python3 -m unittest discover -s tests -v
All tokens, ids and secrets below are made-up placeholders.
"""
import atexit
import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
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
SCRIPT = REPO / "skills" / "strava" / "scripts" / "authorize.py"

spec = importlib.util.spec_from_file_location("strava_authorize", SCRIPT)
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)

CLIENT_ID, CLIENT_SECRET = "12345", "fake-client-secret-aaaa"
CODE, ACCESS, REFRESH = "fake-auth-code-bbbb", "fake-access-cccc", "fake-refresh-dddd"
GOOD_TOKENS = {"access_token": ACCESS, "refresh_token": REFRESH, "expires_at": 1_900_000_000,
               "athlete": {"firstname": "Test"}}


def redirect(state, scope="read,activity:read_all", code=CODE, extra=""):
    return f"http://localhost:8721/?state={state}&code={code}&scope={scope}{extra}"


class AuthorizeUrl(unittest.TestCase):
    def test_url_has_the_required_parameters(self):
        url = auth.build_authorize_url(CLIENT_ID, "http://localhost:8721/", "STATE")
        self.assertTrue(url.startswith("https://www.strava.com/oauth/authorize?"))
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).items()}
        self.assertEqual(q["client_id"], CLIENT_ID)
        self.assertEqual(q["response_type"], "code")
        self.assertEqual(q["redirect_uri"], "http://localhost:8721/")
        self.assertEqual(q["scope"], "activity:read_all")
        self.assertEqual(q["approval_prompt"], "force")
        self.assertEqual(q["state"], "STATE")

    def test_the_secret_is_not_in_the_url(self):
        self.assertNotIn(CLIENT_SECRET, auth.build_authorize_url(CLIENT_ID, "http://localhost:8721/", "S"))

    def test_state_is_random_and_long_enough(self):
        states = {auth.new_state() for _ in range(50)}
        self.assertEqual(len(states), 50)
        self.assertTrue(all(len(s) >= 16 for s in states))


class ParsingAndChecking(unittest.TestCase):
    def check(self, text, state="S1", **kw):
        return auth.check_result(auth.parse_redirect(text), state)

    def test_full_redirect_url(self):
        self.assertEqual(self.check(redirect("S1")), CODE)

    def test_url_wrapped_in_quotes_or_angle_brackets_or_with_spaces(self):
        for wrapped in (f'  "{redirect("S1")}" ', f"<{redirect('S1')}>"):
            self.assertEqual(self.check(wrapped), CODE)

    def test_query_string_only(self):
        self.assertEqual(self.check(f"state=S1&code={CODE}&scope=read,activity:read_all"), CODE)

    def test_bare_code_is_accepted_without_a_state(self):
        self.assertEqual(self.check(CODE), CODE)

    def test_access_denied(self):
        with self.assertRaisesRegex(auth.AuthorizeError, "declined"):
            self.check("http://localhost:8721/?error=access_denied&state=S1")

    def test_other_error(self):
        with self.assertRaisesRegex(auth.AuthorizeError, "boom"):
            self.check("http://localhost:8721/?error=boom&state=S1")

    def test_wrong_state_is_refused(self):
        with self.assertRaisesRegex(auth.AuthorizeError, "state"):
            self.check(redirect("OTHER"))

    def test_missing_state_in_a_url_is_refused(self):
        with self.assertRaisesRegex(auth.AuthorizeError, "state"):
            self.check(f"http://localhost:8721/?code={CODE}&scope=read,activity:read_all")

    def test_missing_code(self):
        with self.assertRaisesRegex(auth.AuthorizeError, "No authorization code"):
            self.check("http://localhost:8721/?state=S1&scope=read,activity:read_all")

    def test_empty_paste(self):
        for empty in ("", "   ", None):
            with self.assertRaisesRegex(auth.AuthorizeError, "Nothing was pasted"):
                auth.parse_redirect(empty)

    def test_missing_scope_is_refused_before_any_exchange(self):
        for scope in ("read", "read,activity:read"):
            with self.subTest(scope=scope), self.assertRaisesRegex(auth.AuthorizeError, "permission was not granted"):
                self.check(redirect("S1", scope=scope))

    def test_error_messages_never_contain_the_code(self):
        for text, state in ((redirect("OTHER"), "S1"), (redirect("S1", scope="read"), "S1")):
            with self.assertRaises(auth.AuthorizeError) as caught:
                auth.check_result(auth.parse_redirect(text), state)
            self.assertNotIn(CODE, str(caught.exception))


class TokenExchange(unittest.TestCase):
    def exchange(self, status, body):
        with mock.patch.object(auth, "http_post", return_value=(status, body)) as post:
            return auth.exchange_code(CLIENT_ID, CLIENT_SECRET, CODE), post

    def test_success_sends_the_authorization_code_grant(self):
        tokens, post = self.exchange(200, GOOD_TOKENS)
        self.assertEqual(tokens, {"access_token": ACCESS, "refresh_token": REFRESH, "expires_at": 1_900_000_000})
        url, fields = post.call_args.args
        self.assertEqual(url, "https://www.strava.com/oauth/token")
        self.assertEqual(fields, {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                                  "code": CODE, "grant_type": "authorization_code"})

    def test_http_errors_become_readable_messages_without_secrets(self):
        body = {"message": "Bad Request", "errors": [{"resource": "Application", "field": "client_id", "code": "invalid"}]}
        for status in (400, 401, 500):
            with self.subTest(status=status), self.assertRaises(auth.AuthorizeError) as caught:
                self.exchange(status, body)
            text = str(caught.exception)
            self.assertIn(f"HTTP {status}", text)
            self.assertIn("Bad Request", text)
            self.assertIn("Application/client_id: invalid", text)
            for secret in (CODE, CLIENT_SECRET):
                self.assertNotIn(secret, text)

    def test_malformed_json_reply(self):
        with self.assertRaisesRegex(auth.AuthorizeError, "HTTP 200"):
            self.exchange(200, None)

    def test_reply_missing_fields_or_wrong_types(self):
        for bad in ({}, {"access_token": ACCESS}, {**GOOD_TOKENS, "expires_at": "soon"},
                    {**GOOD_TOKENS, "refresh_token": ""}, {**GOOD_TOKENS, "expires_at": True}):
            with self.subTest(bad=bad), self.assertRaisesRegex(auth.AuthorizeError, "didn't contain"):
                self.exchange(200, bad)

    def test_http_post_maps_network_errors_and_error_bodies(self):
        with mock.patch.object(urllib.request, "urlopen", side_effect=urllib.error.URLError("no route")):
            with self.assertRaisesRegex(auth.AuthorizeError, "Couldn't reach Strava"):
                auth.http_post("https://example.invalid/", {"a": "b"})
        err = urllib.error.HTTPError("u", 401, "x", {}, io.BytesIO(b'{"message": "Authorization Error"}'))
        with mock.patch.object(urllib.request, "urlopen", side_effect=err):
            self.assertEqual(auth.http_post("https://example.invalid/", {}), (401, {"message": "Authorization Error"}))


class Storage(unittest.TestCase):
    def path(self):
        return Path(make_temp_dir()) / ".config" / "strava" / "credentials.json"

    def mode(self, p):
        return stat.S_IMODE(p.stat().st_mode)

    def test_new_file_and_directory_are_private(self):
        p = self.path()
        auth.write_credentials(p, {"STRAVA_ACCESS_TOKEN": ACCESS})
        self.assertEqual(self.mode(p), 0o600)
        self.assertEqual(self.mode(p.parent), 0o700)
        self.assertEqual(json.loads(p.read_text()), {"STRAVA_ACCESS_TOKEN": ACCESS})

    def test_existing_keys_are_kept_and_mode_is_tightened(self):
        p = self.path()
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"EXTRA": "keep me", "STRAVA_ACCESS_TOKEN": "old"}))
        p.chmod(0o664)
        auth.write_credentials(p, {"STRAVA_ACCESS_TOKEN": ACCESS})
        self.assertEqual(json.loads(p.read_text()), {"EXTRA": "keep me", "STRAVA_ACCESS_TOKEN": ACCESS})
        self.assertEqual(self.mode(p), 0o600)

    def test_no_temp_file_is_left_behind_and_a_failed_write_keeps_the_old_file(self):
        p = self.path()
        auth.write_credentials(p, {"A": "1"})
        with mock.patch.object(auth.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                auth.write_credentials(p, {"A": "2"})
        self.assertEqual(json.loads(p.read_text()), {"A": "1"})
        self.assertEqual([f.name for f in p.parent.iterdir()], ["credentials.json"])

    def test_the_temp_file_is_private_before_it_is_swapped_in(self):
        p = self.path()
        seen = []
        real_replace = os.replace

        def spy(src, dst):
            seen.append(self.mode(Path(src)))
            real_replace(src, dst)

        with mock.patch.object(auth.os, "replace", side_effect=spy):
            auth.write_credentials(p, {"A": "1"})
        self.assertEqual(seen, [0o600])

    def test_unreadable_json_is_an_error_not_a_crash(self):
        p = self.path()
        p.parent.mkdir(parents=True)
        for junk in ("{not json", "[1, 2]"):
            p.write_text(junk)
            with self.subTest(junk=junk), self.assertRaises(auth.AuthorizeError):
                auth.load_credentials(p)


class Listener(unittest.TestCase):
    def free_port(self):
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def fetch(self, port, path, results):
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
                    results.append((r.status, r.read()))
                return
            except urllib.error.HTTPError as e:
                results.append((e.code, b""))
                return
            except OSError:
                time.sleep(0.05)

    def run_listener(self, port, state, paths):
        results, errors = [], []

        def client():
            for path in paths:
                self.fetch(port, path, results)

        t = threading.Thread(target=client)
        t.start()
        try:
            code = auth.listen_for_code(state, port)
        except auth.AuthorizeError as e:
            code = None
            errors.append(e)
        t.join()
        return code, results, errors

    def test_serves_one_redirect_and_returns_the_code(self):
        port = self.free_port()
        query = f"/?state=S1&code={CODE}&scope=read,activity:read_all"
        code, results, errors = self.run_listener(port, "S1", ["/favicon.ico", query])
        self.assertEqual(code, CODE, errors)
        self.assertEqual([status for status, _ in results], [404, 200])
        self.assertIn(b"close this tab", results[1][1])
        self.assertNotIn(CODE.encode(), results[1][1])

    def test_the_authorization_code_is_never_logged(self):
        port = self.free_port()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code, _, _ = self.run_listener(port, "S1", [f"/?state=S1&code={CODE}&scope=read,activity:read_all"])
        self.assertEqual(code, CODE)
        self.assertNotIn(CODE, out.getvalue() + err.getvalue())

    def test_wrong_state_is_refused(self):
        port = self.free_port()
        code, _, errors = self.run_listener(port, "S1", [f"/?state=EVIL&code={CODE}&scope=read,activity:read_all"])
        self.assertIsNone(code)
        self.assertRegex(str(errors[0]), "state")

    def test_binds_to_loopback_only(self):
        captured = {}
        real = auth.HTTPServer

        class Spy(real):
            def __init__(self, address, handler):
                captured["address"] = address
                super().__init__(address, handler)

        with mock.patch.object(auth, "HTTPServer", Spy), mock.patch.object(auth, "LISTEN_TIMEOUT_SECONDS", 0.2):
            with self.assertRaisesRegex(auth.AuthorizeError, "No redirect arrived"):
                auth.listen_for_code("S1", self.free_port())
        self.assertEqual(captured["address"][0], "127.0.0.1")

    def test_times_out(self):
        started = time.monotonic()
        with mock.patch.object(auth, "LISTEN_TIMEOUT_SECONDS", 0.3):
            with self.assertRaisesRegex(auth.AuthorizeError, "No redirect arrived"):
                auth.listen_for_code("S1", self.free_port())
        self.assertLess(time.monotonic() - started, 5)

    def test_port_in_use_suggests_paste_mode(self):
        import socket
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            with self.assertRaisesRegex(auth.AuthorizeError, "paste"):
                auth.listen_for_code("S1", busy.getsockname()[1])


class EndToEnd(unittest.TestCase):
    """main() with a scratch credentials path, a faked Strava and a faked terminal."""

    def setUp(self):
        self.dir = Path(make_temp_dir())
        self.creds = self.dir / ".config" / "strava" / "credentials.json"
        patches = [mock.patch.object(auth, "CREDENTIALS_FILE", self.creds),
                   mock.patch.dict(os.environ, {"STRAVA_CLIENT_ID": CLIENT_ID, "STRAVA_CLIENT_SECRET": CLIENT_SECRET})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.post = mock.patch.object(auth, "http_post", return_value=(200, GOOD_TOKENS))
        self.post.start()
        self.addCleanup(self.post.stop)

    def run_main(self, argv=(), pasted=None, state="FIXEDSTATE"):
        out, err = io.StringIO(), io.StringIO()
        prompt = mock.patch.object(auth, "_prompt", return_value=pasted if pasted is not None else redirect(state))
        with mock.patch.object(auth, "new_state", return_value=state), prompt, \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = auth.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_paste_flow_writes_the_credentials_and_prints_no_secret(self):
        code, out, err = self.run_main()
        self.assertEqual(code, 0, err)
        saved = json.loads(self.creds.read_text())
        self.assertEqual(saved, {"STRAVA_CLIENT_ID": CLIENT_ID, "STRAVA_CLIENT_SECRET": CLIENT_SECRET,
                                 "STRAVA_ACCESS_TOKEN": ACCESS, "STRAVA_REFRESH_TOKEN": REFRESH})
        self.assertEqual(stat.S_IMODE(self.creds.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.creds.parent.stat().st_mode), 0o700)
        self.assertIn("localhost", out)
        self.assertIn("client_id=" + CLIENT_ID, out)
        for secret in (CLIENT_SECRET, CODE, ACCESS, REFRESH):
            self.assertNotIn(secret, out + err)

    def test_listen_flow(self):
        with mock.patch.object(auth, "listen_for_code", return_value=CODE) as listen:
            code, out, err = self.run_main(["--listen", "--port", "9999"])
        self.assertEqual(code, 0, err)
        listen.assert_called_once_with("FIXEDSTATE", 9999)
        self.assertIn("redirect_uri=http%3A%2F%2Flocalhost%3A9999%2F", out)
        self.assertEqual(json.loads(self.creds.read_text())["STRAVA_REFRESH_TOKEN"], REFRESH)

    def test_refuses_to_overwrite_working_tokens_without_force(self):
        self.creds.parent.mkdir(parents=True)
        self.creds.write_text(json.dumps({"STRAVA_REFRESH_TOKEN": "existing-working-token"}))
        code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("--force", err)
        self.assertIn("refresh_token.sh", err)
        self.assertEqual(json.loads(self.creds.read_text()), {"STRAVA_REFRESH_TOKEN": "existing-working-token"})
        self.assertFalse(auth.http_post.called)

    def test_force_replaces_tokens_and_keeps_other_keys(self):
        self.creds.parent.mkdir(parents=True)
        self.creds.write_text(json.dumps({"STRAVA_REFRESH_TOKEN": "old", "NOTE": "mine"}))
        code, _, err = self.run_main(["--force"])
        self.assertEqual(code, 0, err)
        saved = json.loads(self.creds.read_text())
        self.assertEqual((saved["STRAVA_REFRESH_TOKEN"], saved["NOTE"]), (REFRESH, "mine"))

    def test_existing_client_id_and_secret_are_reused(self):
        self.creds.parent.mkdir(parents=True)
        self.creds.write_text(json.dumps({"STRAVA_CLIENT_ID": "777", "STRAVA_CLIENT_SECRET": "stored-secret"}))
        with mock.patch.dict(os.environ, {}, clear=True):
            code, out, err = self.run_main()
        self.assertEqual(code, 0, err)
        self.assertIn("client_id=777", out)
        self.assertEqual(auth.http_post.call_args.args[1]["client_secret"], "stored-secret")

    def test_missing_client_without_a_terminal_is_a_clear_error(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(auth, "_has_terminal", return_value=False):
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(auth, "new_state", return_value="S"), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(auth.main([]), 1)
        self.assertIn("STRAVA_CLIENT_ID", err.getvalue())
        self.assertFalse(self.creds.exists())

    def test_no_terminal_for_the_redirect_suggests_listen_not_env_vars(self):
        with mock.patch.object(auth, "_has_terminal", return_value=False):
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(auth, "new_state", return_value="S"), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(auth.main([]), 1)
        self.assertIn("--listen", err.getvalue())
        self.assertNotIn("STRAVA_CLIENT_ID", err.getvalue())

    def test_failures_leave_no_file(self):
        cases = {"wrong state": redirect("EVIL"), "denied": "http://localhost:8721/?error=access_denied&state=FIXEDSTATE",
                 "no scope": redirect("FIXEDSTATE", scope="read")}
        for name, pasted in cases.items():
            with self.subTest(name):
                code, _, err = self.run_main(pasted=pasted)
                self.assertEqual(code, 1)
                self.assertTrue(err.startswith("Error:"))
                self.assertFalse(self.creds.exists())
                self.assertFalse(auth.http_post.called)

    def test_rejected_exchange_leaves_no_file_and_prints_no_secret(self):
        with mock.patch.object(auth, "http_post", return_value=(400, {"message": "Bad Request"})):
            code, out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("Bad Request", err)
        self.assertFalse(self.creds.exists())
        for secret in (CLIENT_SECRET, CODE):
            self.assertNotIn(secret, out + err)

    def test_ctrl_c_and_closed_input_exit_cleanly(self):
        for exc in (KeyboardInterrupt, EOFError):
            with self.subTest(exc=exc.__name__), mock.patch.object(auth, "_prompt", side_effect=exc):
                err = io.StringIO()
                with mock.patch.object(auth, "new_state", return_value="S"), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    self.assertEqual(auth.main([]), 1)
                self.assertIn("Cancelled", err.getvalue())


class SourceHygiene(unittest.TestCase):
    def test_the_secret_is_never_a_command_line_argument(self):
        text = SCRIPT.read_text()
        self.assertNotIn("--client-secret", text)
        self.assertNotIn("--secret", text)

    def test_standard_library_only(self):
        imports = {line.split()[1].split(".")[0] for line in SCRIPT.read_text().splitlines()
                   if line.startswith(("import ", "from "))}
        self.assertFalse(imports & {"requests", "httpx", "urllib3"}, imports)

    def test_script_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_docs_point_at_the_script(self):
        for doc in ("skills/strava/README.md", "skills/strava/SKILL.md"):
            self.assertIn("scripts/authorize.py", (REPO / doc).read_text(), doc)


if __name__ == "__main__":
    unittest.main()
