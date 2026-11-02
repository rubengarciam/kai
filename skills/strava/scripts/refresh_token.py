#!/usr/bin/env python3
"""Refresh the Strava access token and write the new tokens back to the credentials file.

Credentials are read from (in priority order):
  1. Environment variables STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN
  2. ~/.config/strava/credentials.json (fills in whichever of the three the environment lacks)

On success the new access and refresh tokens are written back to ~/.config/strava/credentials.json, if that
file exists. The file is never more open than 600: the replacement is created owner-only, and a file that was
already looser is tightened by the swap. A failed refresh leaves the file untouched.

Exit codes: 0 ok, 1 error (missing credentials, refresh refused, unreadable credentials file).
Standard library only.
"""

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

TOKEN_URL = "https://www.strava.com/oauth/token"
NEEDED = ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN")


def credentials_path():
    return Path(os.path.expanduser("~/.config/strava/credentials.json"))


def load_credentials(path):
    """The three values needed for a refresh: environment first, the credentials file for what is missing."""
    creds = {k: os.environ.get(k, "") for k in NEEDED}
    if all(creds.values()) or not path.is_file():
        return creds
    with open(path) as f:
        stored = json.load(f)
    for key in NEEDED:
        if not creds[key]:
            creds[key] = str(stored.get(key) or "")
    return creds


def request_new_tokens(creds):
    """POST the refresh grant. Returns the parsed response, or raises RuntimeError with a safe message."""
    body = urllib.parse.urlencode({
        "client_id": creds["STRAVA_CLIENT_ID"],
        "client_secret": creds["STRAVA_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": creds["STRAVA_REFRESH_TOKEN"],
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"could not reach Strava: {e}")
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if not isinstance(data, dict) or not data.get("access_token") or not data.get("refresh_token"):
        # A refusal carries a message and no tokens; the cut keeps an unexpected body from flooding the log
        raise RuntimeError(raw[:500])
    return data


def write_back(path, access_token, refresh_token):
    """Swap the new tokens into the credentials file through an owner-only temp file in the same directory."""
    with open(path) as f:
        creds = json.load(f)
    creds["STRAVA_ACCESS_TOKEN"] = access_token
    creds["STRAVA_REFRESH_TOKEN"] = refresh_token
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)  # created 0600
    try:
        with os.fdopen(fd, "w") as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump(creds, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def expires_text(expires_at):
    try:
        return datetime.fromtimestamp(int(expires_at)).astimezone().strftime("%a %d %b %Y %H:%M:%S %Z")
    except (TypeError, ValueError, OverflowError, OSError):
        return str(expires_at)


def main(argv=None):
    argparse.ArgumentParser(
        description="Refresh the Strava access token and write the new tokens back to "
                    "~/.config/strava/credentials.json (mode 600).",
        epilog="Credentials: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET and STRAVA_REFRESH_TOKEN from the "
               "environment, or from ~/.config/strava/credentials.json.",
    ).parse_args(argv)

    path = credentials_path()
    try:
        creds = load_credentials(path)
    except (OSError, ValueError) as e:
        print(f"Error: cannot read {path}: {e}", file=sys.stderr)
        return 1
    if not all(creds.values()):
        print("Error: Missing Strava credentials.")
        print("Set environment variables or create ~/.config/strava/credentials.json with:")
        print("  STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN")
        return 1

    try:
        data = request_new_tokens(creds)
    except RuntimeError as e:
        print("Error: Token refresh failed")
        print(e)
        return 1

    print("✓ Token refreshed successfully")
    print(f"  Expires at: {expires_text(data.get('expires_at'))}")

    if not path.exists():
        print("Warning: ~/.config/strava/credentials.json not found, skipping write-back.", file=sys.stderr)
        return 0
    try:
        write_back(path, data["access_token"], data["refresh_token"])
    except (OSError, ValueError) as e:
        print(f"Error: could not update {path}: {e}", file=sys.stderr)
        print("The tokens were refreshed but not saved; the old refresh token may no longer work.", file=sys.stderr)
        return 1
    print(f"✓ Updated {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
