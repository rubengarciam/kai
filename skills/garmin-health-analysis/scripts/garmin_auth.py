#!/usr/bin/env python3
"""
Garmin Connect authentication helper.
Handles login and stores session tokens.

Requires garminconnect 0.3.x (Python 3.12+); see requirements.txt in the Kai repo root.

The password is only used for the initial login. It is never written to disk:
only the session tokens are kept (garmin_tokens.json, mode 600, in a 700 directory).
"""

import argparse
import getpass
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from garminconnect import (
        Garmin,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )
except ImportError:
    print("❌ garminconnect library not installed", file=sys.stderr)
    print("Install with: pip install -r requirements.txt (in the Kai repo root)", file=sys.stderr)
    sys.exit(1)

CONFIG_DIR = Path.home() / ".config" / "garminconnect"
# GARMIN_TOKEN_DIR lets you keep tokens somewhere else (e.g. a scratch dir for testing)
TOKEN_DIR = Path(os.environ["GARMIN_TOKEN_DIR"]).expanduser() if os.environ.get("GARMIN_TOKEN_DIR") else CONFIG_DIR
TOKEN_FILE = TOKEN_DIR / "garmin_tokens.json"
LEGACY_TOKEN_FILE = TOKEN_DIR / "oauth1_token.json"  # written by garminconnect 0.2.x (garth)
CONFIG_FILE = CONFIG_DIR / "config.json"  # optional: {"email": "you@example.com"}

NO_TERMINAL_HELP = """\
❌ No terminal available to ask for your {what}.

Run the login yourself in a terminal, so the password never passes through a chat or an agent:

    .venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py login

Other options: pipe it with --password-stdin, or set GARMIN_PASSWORD for a single command."""


class NoTerminalError(RuntimeError):
    def __init__(self, what):
        super().__init__(what)
        self.what = what


def _has_terminal():
    """True if there is a controlling terminal we can prompt on."""
    if sys.stdin.isatty():
        return True
    try:
        os.close(os.open("/dev/tty", os.O_RDWR))
        return True
    except OSError:
        return False


def _prompt(text, what, secret=False):
    """Prompt on the terminal (never on a pipe). Raises NoTerminalError if there is none."""
    if not _has_terminal():
        raise NoTerminalError(what)
    if secret:
        return getpass.getpass(text)
    # Read from the controlling terminal even when stdin is a pipe (e.g. --password-stdin)
    if sys.stdin.isatty():
        return input(text)
    with open("/dev/tty", "r+") as tty:
        tty.write(text)
        tty.flush()
        return tty.readline().rstrip("\n")


def load_config():
    """Load optional settings (the email address) from the config file."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except Exception as e:
        print(f"⚠️  Failed to load config: {e}", file=sys.stderr)
        return {}
    if "password" in config:
        print(f"⚠️  Ignoring the password in {CONFIG_FILE}: passwords are no longer read from disk. "
              "Delete that line; you will be prompted at login.", file=sys.stderr)
    return config


def prompt_mfa():
    """Prompt the user for their MFA/2FA code once."""
    return _prompt("🔑 MFA required. Enter the code from your authenticator app (or email): ", "MFA code").strip()


def resolve_credentials(email, password_stdin):
    """Work out email and password without ever taking the password from the command line.

    Password: --password-stdin, then GARMIN_PASSWORD, then a hidden prompt.
    Email: --email, then GARMIN_EMAIL, then config.json, then a prompt.
    """
    email = email or os.environ.get("GARMIN_EMAIL") or load_config().get("email")
    if not email:
        email = _prompt("Garmin email: ", "email address").strip()

    if password_stdin:
        password = sys.stdin.readline().rstrip("\n")
    elif os.environ.get("GARMIN_PASSWORD"):
        password = os.environ["GARMIN_PASSWORD"]
    else:
        password = _prompt(f"Garmin password for {email}: ", "password", secret=True)

    if not email or not password:
        raise GarminConnectAuthenticationError("Email and password are required")
    return email, password


def login(email, password):
    """Log in with credentials and save the session tokens."""
    try:
        print(f"🔐 Logging in as {email}...", file=sys.stderr)

        TOKEN_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)

        # A fresh credential login (no tokenstore), so any old tokens are never reused.
        # MFA callback prompts once instead of retrying.
        client = Garmin(email, password, prompt_mfa=prompt_mfa)
        client.login()

        # dump() writes garmin_tokens.json as 600 inside a 700 directory
        client.client.dump(str(TOKEN_DIR))
        print(f"✅ Tokens saved to {TOKEN_FILE}", file=sys.stderr)

        try:
            profile = client.get_user_summary(datetime.now().strftime("%Y-%m-%d"))
            print(f"✅ Login successful! User: {profile.get('displayName', 'Unknown')}", file=sys.stderr)
        except Exception as e:
            print(f"✅ Login successful! (Unable to fetch profile: {e})", file=sys.stderr)

        return True

    except NoTerminalError as e:
        print(NO_TERMINAL_HELP.format(what=e.what), file=sys.stderr)
        return False
    except GarminConnectTooManyRequestsError:
        print("❌ Garmin is rate-limiting logins from this connection. Wait a while (an hour is safe) "
              "and try again; repeated attempts make it worse.", file=sys.stderr)
        return False
    except GarminConnectAuthenticationError as e:
        print(f"❌ Authentication failed: {e}", file=sys.stderr)
        print("Check your email/password and try again.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Login error: {e}", file=sys.stderr)
        return False


def _not_logged_in_hint():
    if LEGACY_TOKEN_FILE.exists() and not TOKEN_FILE.exists():
        print("⚠️  Found tokens from an older version of this skill (garminconnect 0.2.x). "
              "They cannot be used any more: run the login command once to sign in again.", file=sys.stderr)
    else:
        print("❌ Not authenticated", file=sys.stderr)
    print("Run: .venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py login", file=sys.stderr)


def get_client():
    """Get authenticated Garmin client, using saved tokens if available."""
    if not TOKEN_FILE.exists():
        _not_logged_in_hint()
        return None

    try:
        # Loads the saved tokens and refreshes them if they are about to expire.
        # No credentials are passed: if the tokens are rejected this fails instead of logging in.
        client = Garmin()
        client.login(tokenstore=str(TOKEN_DIR))

        # Test if tokens still work
        client.get_user_summary(datetime.now().strftime("%Y-%m-%d"))
        return client

    except Exception as e:
        print(f"⚠️  Saved tokens expired or invalid: {e}", file=sys.stderr)
        print("Run the login command again.", file=sys.stderr)
        return None


def check_status():
    """Check if we have valid authentication."""
    if not TOKEN_FILE.exists():
        _not_logged_in_hint()
        return False

    print(f"✅ Token file found at {TOKEN_FILE}", file=sys.stderr)

    client = get_client()
    if client:
        try:
            profile = client.get_user_summary(datetime.now().strftime("%Y-%m-%d"))
            print(f"✅ Authentication valid! User: {profile.get('displayName', 'Unknown')}", file=sys.stderr)
            return True
        except Exception as e:
            print(f"⚠️  Tokens may be expired: {e}", file=sys.stderr)
            return False

    print("❌ Authentication invalid. Please login again.", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(description="Garmin Connect authentication")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    login_parser = subparsers.add_parser(
        "login", help="Login to Garmin Connect (asks for your password on the terminal)")
    login_parser.add_argument("--email", help="Garmin account email (or GARMIN_EMAIL, or config.json, or prompted)")
    login_parser.add_argument("--password-stdin", action="store_true",
                              help="Read the password from the first line of stdin instead of prompting")
    # Removed: a password on the command line leaks into shell history and the process list
    login_parser.add_argument("--password", help=argparse.SUPPRESS)

    subparsers.add_parser("status", help="Check authentication status")

    args = parser.parse_args()

    if args.command == "login":
        if args.password is not None:
            print("❌ --password has been removed: a password on the command line ends up in your shell "
                  "history and the process list.\n"
                  "   Run the command without it to be prompted, or use --password-stdin.", file=sys.stderr)
            sys.exit(2)
        try:
            email, password = resolve_credentials(args.email, args.password_stdin)
        except NoTerminalError as e:
            print(NO_TERMINAL_HELP.format(what=e.what), file=sys.stderr)
            sys.exit(1)
        except GarminConnectAuthenticationError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0 if login(email, password) else 1)

    elif args.command == "status":
        sys.exit(0 if check_status() else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
