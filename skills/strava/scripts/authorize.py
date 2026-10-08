#!/usr/bin/env python3
"""First-time Strava setup: authorize the app and write ~/.config/strava/credentials.json.

Run it once after creating your Strava API application:

    python3 skills/strava/scripts/authorize.py            # paste mode (works over SSH and on headless machines)
    python3 skills/strava/scripts/authorize.py --listen   # a one-shot listener catches the redirect for you

Your app's "Authorization Callback Domain" must be `localhost` (https://www.strava.com/settings/api).

The client ID and secret come from STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET, then from an existing
credentials file, then from a prompt (the secret is never taken as a command-line argument, so it stays
out of shell history and `ps`). The authorization code and the tokens are never printed. Standard library only.
"""
import argparse
import getpass
import json
import os
import secrets
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
SCOPE = "activity:read_all"
DEFAULT_PORT = 8721
LISTEN_TIMEOUT_SECONDS = 180
CLIENT_HINT = "Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET and run it again."
CREDENTIALS_FILE = Path.home() / ".config" / "strava" / "credentials.json"


class AuthorizeError(Exception):
    """Something the user can fix; the message is safe to print (it never holds a code, token or secret)."""


# --- Inputs -----------------------------------------------------------------

def _has_terminal():
    if sys.stdin.isatty():
        return True
    try:
        os.close(os.open("/dev/tty", os.O_RDWR))
        return True
    except OSError:
        return False


def _prompt(text, what, hint, secret=False):
    """Prompt on the terminal, never on a pipe."""
    if not _has_terminal():
        raise AuthorizeError(f"Need your {what} but there is no terminal to ask on. {hint}")
    if secret:
        return getpass.getpass(text)
    if sys.stdin.isatty():
        return input(text)
    with open("/dev/tty", "r+") as tty:
        tty.write(text)
        tty.flush()
        return tty.readline().rstrip("\n")


def load_credentials(path):
    """The credentials file as a dict; {} if it doesn't exist. A file that isn't a JSON object is an error."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise AuthorizeError(f"{path} exists but can't be read as JSON ({type(e).__name__}). "
                             "Fix or move it, or run again with --force to replace it.")
    if not isinstance(data, dict):
        raise AuthorizeError(f"{path} exists but isn't a JSON object. Fix or move it, or run again with --force.")
    return data


def resolve_client(existing):
    """Client ID and secret: environment, then the credentials file, then a prompt."""
    client_id = os.environ.get("STRAVA_CLIENT_ID") or existing.get("STRAVA_CLIENT_ID")
    if not client_id:
        client_id = _prompt("Strava client ID: ", "client ID", CLIENT_HINT).strip()
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET") or existing.get("STRAVA_CLIENT_SECRET")
    if not client_secret:
        client_secret = _prompt("Strava client secret (hidden): ", "client secret", CLIENT_HINT, secret=True).strip()
    if not client_id or not client_secret:
        raise AuthorizeError("A client ID and a client secret are both required.")
    return str(client_id), str(client_secret)


# --- Authorization ------------------------------------------------------------

def new_state():
    return secrets.token_urlsafe(16)


def build_authorize_url(client_id, redirect_uri, state):
    query = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "force",
        "scope": SCOPE,
        "state": state,
    })
    return f"{AUTHORIZE_URL}?{query}"


def parse_redirect(text):
    """Pull the authorization result out of what the user pasted.

    Accepts the full redirect URL, just its query string, or a bare code. Returns a dict with `code`, and
    `state` / `scope` / `error` when present. A bare code is marked `bare` (it carries no state to check).
    """
    text = (text or "").strip().strip("<>\"'")
    if not text:
        raise AuthorizeError("Nothing was pasted.")
    if "=" not in text and "?" not in text and "://" not in text:
        return {"code": text, "bare": True}
    query = urllib.parse.urlsplit(text).query if ("?" in text or "://" in text) else text
    params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
    return {k: params[k] for k in ("code", "state", "scope", "error") if params.get(k)}


def check_result(result, expected_state):
    """Return the authorization code, or raise a readable error. Never includes the code in a message."""
    if result.get("error"):
        if result["error"] == "access_denied":
            raise AuthorizeError("Authorization was declined on the Strava page. Run it again and click Authorize.")
        raise AuthorizeError(f"Strava returned an error: {result['error']}")
    if not result.get("bare") and not secrets.compare_digest(result.get("state", ""), expected_state):
        raise AuthorizeError("The redirect's state value is missing or doesn't match this run, so it was ignored. "
                             "Open the URL printed by this run (not an older one) and paste the whole address.")
    granted = [s for s in result.get("scope", "").split(",") if s]
    if granted and SCOPE not in granted:
        raise AuthorizeError(f"The {SCOPE} permission was not granted (granted: {', '.join(granted)}). "
                             f"Run it again and keep the 'View data about your private activities' box ticked.")
    if not result.get("code"):
        raise AuthorizeError("No authorization code found. Paste the whole address from the browser's address bar.")
    return result["code"]


def paste_for_code(expected_state):
    pasted = _prompt("Paste the address from the browser's address bar (or just the code): ", "redirect URL",
                     "Run this in a terminal, or add --listen to catch the redirect automatically.")
    return check_result(parse_redirect(pasted), expected_state)


def listen_for_code(expected_state, port):
    """Serve the redirect on 127.0.0.1 only, until a request carrying a code or error arrives or time runs out."""
    outcome = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            params = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items()}
            if "code" not in params and "error" not in params:
                self.send_error(404)
                return
            outcome["result"] = {k: params[k] for k in ("code", "state", "scope", "error") if params.get(k)}
            body = (b"<html><body><h3>Strava authorization received</h3>"
                    b"<p>You can close this tab and go back to the terminal.</p></body></html>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # the request line holds the authorization code
            pass

    try:
        server = HTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        raise AuthorizeError(f"Couldn't listen on 127.0.0.1:{port} ({e.strerror}). Use another --port, "
                             "or leave out --listen and paste the address instead.")
    deadline = time.monotonic() + LISTEN_TIMEOUT_SECONDS
    try:
        while "result" not in outcome:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AuthorizeError(f"No redirect arrived within {LISTEN_TIMEOUT_SECONDS} seconds. "
                                     "If the browser is on another machine, leave out --listen and paste the address.")
            server.timeout = remaining
            server.handle_request()
    finally:
        server.server_close()
    return check_result(outcome["result"], expected_state)


# --- Token exchange and storage -----------------------------------------------

def http_post(url, fields):
    """POST form fields and return (status, parsed JSON or None). The request body is never echoed."""
    data = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except (urllib.error.URLError, OSError) as e:
        raise AuthorizeError(f"Couldn't reach Strava ({type(e).__name__}). Check the network and try again.")
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, None


def exchange_code(client_id, client_secret, code):
    """Trade the authorization code for tokens. Returns {'access_token', 'refresh_token', 'expires_at'}."""
    status, body = http_post(TOKEN_URL, {
        "client_id": client_id, "client_secret": client_secret,
        "code": code, "grant_type": "authorization_code",
    })
    if status != 200 or not isinstance(body, dict):
        detail = ""
        if isinstance(body, dict):
            parts = [str(body["message"])] if body.get("message") else []
            parts += [f"{e.get('resource', '?')}/{e.get('field', '?')}: {e.get('code', '?')}"
                      for e in body.get("errors", []) if isinstance(e, dict)]
            detail = f": {'; '.join(parts)}" if parts else ""
        hint = (" The code is single-use and expires quickly, so start again from the URL. If the client ID or "
                "secret is wrong, fix that first." if status in (400, 401) else "")
        raise AuthorizeError(f"Strava rejected the token request (HTTP {status}{detail}).{hint}")
    access, refresh, expires = body.get("access_token"), body.get("refresh_token"), body.get("expires_at")
    if not (isinstance(access, str) and access and isinstance(refresh, str) and refresh
            and isinstance(expires, int) and not isinstance(expires, bool)):
        raise AuthorizeError("Strava's reply didn't contain an access token, refresh token and expiry.")
    return {"access_token": access, "refresh_token": refresh, "expires_at": expires}


def write_credentials(path, updates):
    """Merge updates into the credentials file. Directory 700; the file is created 600 and swapped in whole,
    so it is never readable by others, not even for a moment."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    existing = load_credentials(path) if path.exists() else {}
    existing.update(updates)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".credentials-", suffix=".tmp")  # mkstemp: mode 600
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(existing, f, indent=4)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


# --- Command line ---------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="Authorize Strava and write ~/.config/strava/credentials.json.")
    parser.add_argument("--listen", action="store_true",
                        help="Catch the redirect with a one-shot listener on 127.0.0.1 instead of pasting the address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Port used in the redirect address (default {DEFAULT_PORT}); with --listen, also the port listened on")
    parser.add_argument("--force", action="store_true",
                        help="Replace tokens that are already in the credentials file")
    args = parser.parse_args(argv)

    try:
        existing = {}
        try:
            existing = load_credentials(CREDENTIALS_FILE)
        except AuthorizeError:
            if not args.force:
                raise
        if existing.get("STRAVA_REFRESH_TOKEN") and not args.force:
            raise AuthorizeError(f"{CREDENTIALS_FILE} already holds tokens, and replacing them would break a "
                                 "working setup. To renew an expired access token run refresh_token.sh instead; "
                                 "to authorize again from scratch (for example after changing the scope), run "
                                 "this with --force.")
        client_id, client_secret = resolve_client(existing)

        state = new_state()
        redirect_uri = f"http://localhost:{args.port}/"
        print("1. In https://www.strava.com/settings/api set 'Authorization Callback Domain' to: localhost")
        print("2. Open this address in a browser, click Authorize, and keep the activity-data box ticked:\n")
        print(f"   {build_authorize_url(client_id, redirect_uri, state)}\n")
        if args.listen:
            print(f"Waiting up to {LISTEN_TIMEOUT_SECONDS} seconds for the redirect on 127.0.0.1:{args.port} ...")
            code = listen_for_code(state, args.port)
        else:
            print("3. Strava then sends the browser to a localhost page that won't load. That's expected: "
                  "copy the full address from the address bar.")
            code = paste_for_code(state)

        tokens = exchange_code(client_id, client_secret, code)
        write_credentials(CREDENTIALS_FILE, {
            "STRAVA_CLIENT_ID": client_id,
            "STRAVA_CLIENT_SECRET": client_secret,
            "STRAVA_ACCESS_TOKEN": tokens["access_token"],
            "STRAVA_REFRESH_TOKEN": tokens["refresh_token"],
        })
        expires = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tokens["expires_at"]))
        print(f"✓ Authorized. Credentials saved to {CREDENTIALS_FILE} (access token valid until {expires}).")
        print("  Access tokens last 6 hours; refresh with: bash skills/strava/scripts/refresh_token.sh")
        return 0
    except AuthorizeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
