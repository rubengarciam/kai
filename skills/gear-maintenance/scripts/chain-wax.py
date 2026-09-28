#!/usr/bin/env python3
"""Chain wax log and km-since-wax report.

Keeps one ledger of chain waxes per bike (skills/gear-maintenance/data/chain-wax.json) and works out, from the
bike's live Strava odometer, how far each chain has run since its last wax and when the next wax is due.

Usage:
  chain-wax.py [--ledger PATH] report [--json]
  chain-wax.py log BIKE [--odometer KM] [--date YYYY-MM-DD] [--product TEXT] [--kind hot|drip]
                        [--interval MIN-MAX] [--degreased] [--force]
  chain-wax.py set-odometer BIKE KM [--date YYYY-MM-DD]        (manually tracked bikes only)
  chain-wax.py add-bike BIKE --name TEXT (--gear-id ID | --manual [--odometer KM]) [--kind hot|drip]

How it works
  * Odometer: bikes with a Strava gear id read the lifetime distance from /gear/{id} (indoor rides
    included: a chain wears on the trainer as well). Other bikes are manual: you give the odometer
    with `set-odometer` or `log --odometer`, and `report` shows how old that reading is.
  * The due range is fixed when a wax is logged (next_due_km = [min, max] km after that wax). Defaults:
    hot wax = early first re-wax at 150-250 km, then 450-500 km; drip = 200-300 km. --interval overrides.
  * Status, from km since the last wax and the range [min, max]:
      OK         more than 10% of `min` still to go
      DUE SOON   within the last 10% before `min`
      DUE        between `min` and `max`
      OVERDUE    past `max`

Strava credentials come from STRAVA_ACCESS_TOKEN or ~/.config/strava/credentials.json
(run skills/strava/scripts/refresh_token.sh if a call returns 401).

Exit codes: 0 ok, 1 error (bad input, ledger problem), 2 report printed but an odometer was unavailable.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

DEFAULT_LEDGER = Path(__file__).resolve().parent.parent / "data" / "chain-wax.json"
# Before v2.2 the ledger lived in the Strava skill; still honoured (with a notice) if it is the only one
LEGACY_LEDGER = Path(__file__).resolve().parent.parent.parent / "strava" / "data" / "chain-wax.json"
SOON_FRACTION = 0.10   # DUE SOON = within the last 10% before the minimum
STALE_DAYS = 30        # a manual odometer reading older than this is flagged
INTERVALS = {          # (min, max) km after a wax, by kind and whether it is the bike's first wax
    "hot": {"first": (150, 250), "later": (450, 500)},
    "drip": {"first": (200, 300), "later": (200, 300)},
}
BIKE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ChainWaxError(Exception):
    """A problem the user can fix; printed without a traceback."""


class OdometerUnavailable(ChainWaxError):
    pass


# ---------------------------------------------------------------- ledger

def ledger_path(arg):
    explicit = arg or os.environ.get("CHAIN_WAX_LEDGER")
    if explicit:
        return Path(explicit).expanduser()
    if not DEFAULT_LEDGER.exists() and LEGACY_LEDGER.exists():
        print(f"Note: using the ledger at its old location {LEGACY_LEDGER}. "
              f"Move it to {DEFAULT_LEDGER} (the chain wax log now lives in skills/gear-maintenance).", file=sys.stderr)
        return LEGACY_LEDGER
    return DEFAULT_LEDGER


def load_ledger(path):
    """Read the ledger. A missing file is an error with a hint; a corrupt one is never overwritten."""
    if not path.exists():
        raise ChainWaxError(
            f"No ledger at {path}.\n"
            "Create it by adding a bike:  chain-wax.py add-bike road --name \"Road bike\" --gear-id <strava gear id>\n"
            "(find gear ids with skills/strava/scripts/gear-mileage.sh), or copy data/chain-wax.example.json.")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ChainWaxError(f"{path} is not valid JSON ({e}). Fix or restore it; nothing was changed.")
    if not isinstance(data, dict) or not isinstance(data.get("bikes"), dict):
        raise ChainWaxError(f"{path} has no \"bikes\" object. Nothing was changed.")
    return data


def save_ledger(path, data):
    """Atomic write: a crash mid-write can't leave a truncated ledger."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def get_bike(data, bike_id):
    bikes = data["bikes"]
    if bike_id not in bikes:
        known = ", ".join(sorted(bikes)) or "none"
        raise ChainWaxError(f"Unknown bike '{bike_id}'. Known bikes: {known}.")
    return bikes[bike_id]


# ---------------------------------------------------------------- Strava

def strava_token():
    token = os.environ.get("STRAVA_ACCESS_TOKEN")
    if not token:
        creds = Path.home() / ".config" / "strava" / "credentials.json"
        if creds.exists():
            token = json.loads(creds.read_text()).get("STRAVA_ACCESS_TOKEN")
    if not token:
        raise OdometerUnavailable("STRAVA_ACCESS_TOKEN not set (run skills/strava/scripts/refresh_token.sh)")
    return token


def fetch_gear_km(gear_id):
    """Lifetime distance of a Strava bike in km."""
    req = urllib.request.Request(f"https://www.strava.com/api/v3/gear/{gear_id}",
                                 headers={"Authorization": f"Bearer {strava_token()}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())["distance"] / 1000.0
    except urllib.error.HTTPError as e:
        hint = " (token expired: run skills/strava/scripts/refresh_token.sh)" if e.code == 401 else ""
        raise OdometerUnavailable(f"Strava returned HTTP {e.code} for gear {gear_id}{hint}")
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
        raise OdometerUnavailable(f"could not read gear {gear_id} from Strava: {e}")


def current_odometer(bike, fetch):
    """(km, source, as_of) for a bike: live from Strava, or the stored manual reading."""
    if bike.get("strava_gear_id"):
        return fetch(bike["strava_gear_id"]), "strava", None
    if bike.get("odometer_km") is None:
        raise OdometerUnavailable("manual bike with no odometer yet: run set-odometer")
    return float(bike["odometer_km"]), "manual", bike.get("odometer_date")


# ---------------------------------------------------------------- logic

def parse_date(text, what="date"):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise ChainWaxError(f"Invalid {what} '{text}': use YYYY-MM-DD.")


def parse_interval(text):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", text or "")
    if not m or float(m.group(1)) > float(m.group(2)) or float(m.group(1)) <= 0:
        raise ChainWaxError(f"Invalid --interval '{text}': use MIN-MAX in km, e.g. 450-500.")
    return [float(m.group(1)), float(m.group(2))]


def default_interval(kind, is_first):
    lo, hi = INTERVALS[kind]["first" if is_first else "later"]
    return [lo, hi]


def status_for(km_since, lo, hi):
    if km_since < 0:
        return "CHECK ODOMETER"
    if km_since > hi:
        return "OVERDUE"
    if km_since >= lo:
        return "DUE"
    if km_since >= lo * (1 - SOON_FRACTION):
        return "DUE SOON"
    return "OK"


def assess(bike_id, bike, odometer, source, as_of, today):
    """One bike's row of the report."""
    row = {"bike": bike_id, "name": bike.get("name", bike_id), "source": source,
           "odometer_km": round(odometer, 1), "odometer_date": as_of, "odometer_age_days": None,
           "stale": False, "last_wax": None, "km_since_wax": None, "next_due_km": None,
           "due_from_odometer_km": None, "due_by_odometer_km": None, "remaining_to_min_km": None,
           "status": "NO WAX LOGGED"}
    if source == "manual" and as_of:
        age = (today - parse_date(as_of, "odometer_date")).days
        row["odometer_age_days"] = age
        row["stale"] = age > STALE_DAYS
    waxes = bike.get("waxes") or []
    if not waxes:
        return row
    last = waxes[-1]
    lo, hi = last["next_due_km"]
    since = odometer - last["odometer_km"]
    row.update({
        "last_wax": {k: last.get(k) for k in ("date", "odometer_km", "product", "kind", "degreased")},
        "km_since_wax": round(since, 1), "next_due_km": [lo, hi],
        "due_from_odometer_km": round(last["odometer_km"] + lo, 1),
        "due_by_odometer_km": round(last["odometer_km"] + hi, 1),
        "remaining_to_min_km": round(lo - since, 1),
        "status": status_for(since, lo, hi)})
    return row


def build_report(data, fetch=fetch_gear_km, today=None):
    today = today or date.today()
    rows, problems = [], []
    for bike_id, bike in data["bikes"].items():
        try:
            odo, source, as_of = current_odometer(bike, fetch)
            rows.append(assess(bike_id, bike, odo, source, as_of, today))
        except OdometerUnavailable as e:
            problems.append({"bike": bike_id, "name": bike.get("name", bike_id), "error": str(e)})
    return rows, problems


def render_report(rows, problems):
    lines = []
    if rows:
        head = ("Bike", "Odometer", "Last wax", "Since", "Next due (odometer)", "Status")
        table = [head]
        for r in rows:
            lw = r["last_wax"]
            odo = f"{r['odometer_km']:,.1f} km" + (" (manual)" if r["source"] == "manual" else "")
            last = f"{lw['date']} @ {lw['odometer_km']:,.1f}" if lw else "-"
            since = f"{r['km_since_wax']:,.1f} km" if lw else "-"
            due = (f"{r['due_from_odometer_km']:,.1f} - {r['due_by_odometer_km']:,.1f}" if lw else "-")
            table.append((r["name"], odo, last, since, due, r["status"]))
        widths = [max(len(row[i]) for row in table) for i in range(len(head))]
        for n, row in enumerate(table):
            lines.append("  ".join(c.ljust(widths[i]) for i, c in enumerate(row)).rstrip())
            if n == 0:
                lines.append("  ".join("-" * w for w in widths))
        for r in rows:
            if r["status"] in ("DUE SOON", "DUE", "OVERDUE"):
                rem = r["remaining_to_min_km"]
                when = f"{abs(rem):,.0f} km {'past' if rem < 0 else 'before'} the minimum"
                lines.append(f"! {r['name']}: {r['status']} ({when})")
            if r["status"] == "CHECK ODOMETER":
                lines.append(f"! {r['name']}: odometer is below the odometer at the last wax; "
                             "was the Strava gear reset or the ledger mistyped?")
            if r["stale"]:
                lines.append(f"! {r['name']}: manual odometer reading is {r['odometer_age_days']} days old "
                             "(set a fresh one with set-odometer)")
    for p in problems:
        lines.append(f"! {p['name']}: odometer unavailable: {p['error']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- commands

def cmd_report(args, fetch=fetch_gear_km):
    data = load_ledger(ledger_path(args.ledger))
    rows, problems = build_report(data, fetch)
    if args.json:
        print(json.dumps({"bikes": rows, "problems": problems}, indent=2))
    else:
        print(render_report(rows, problems) if (rows or problems) else "No bikes in the ledger yet.")
    return 2 if problems else 0


def cmd_log(args, fetch=fetch_gear_km, today=None):
    path = ledger_path(args.ledger)
    data = load_ledger(path)
    bike = get_bike(data, args.bike)
    today = today or date.today()
    when = parse_date(args.date) if args.date else today
    if when > today:
        raise ChainWaxError(f"--date {when} is in the future.")

    if args.odometer is not None:
        odometer = args.odometer
    elif not bike.get("strava_gear_id"):
        raise ChainWaxError(f"'{args.bike}' is a manual bike: give the odometer with --odometer KM.")
    elif when != today:
        raise ChainWaxError("A past --date needs --odometer KM: Strava can't give the odometer for an earlier day.")
    else:
        odometer, _, _ = current_odometer(bike, fetch)
    odometer = round(odometer, 1)

    waxes = bike.setdefault("waxes", [])
    if waxes and odometer < waxes[-1]["odometer_km"] and not args.force:
        raise ChainWaxError(f"Odometer {odometer:,.1f} km is below the last wax ({waxes[-1]['odometer_km']:,.1f} km). "
                            "Check the number, or pass --force if the gear was reset.")
    if waxes and when < parse_date(waxes[-1]["date"], "last wax date") and not args.force:
        raise ChainWaxError(f"--date {when} is before the last logged wax ({waxes[-1]['date']}). "
                            "Waxes are logged in order; pass --force to override.")

    kind = args.kind or bike.get("default_kind") or "hot"
    interval = parse_interval(args.interval) if args.interval else default_interval(kind, not waxes)
    entry = {"date": when.isoformat(), "odometer_km": odometer, "kind": kind,
             "product": args.product or "", "degreased": bool(args.degreased), "next_due_km": interval}
    waxes.append(entry)
    if not bike.get("strava_gear_id"):
        bike["odometer_km"], bike["odometer_date"] = odometer, when.isoformat()
    save_ledger(path, data)

    lo, hi = interval
    print(f"Logged wax for {bike.get('name', args.bike)}: {when} at {odometer:,.1f} km "
          f"({kind}{', ' + args.product if args.product else ''}).")
    print(f"Next wax due at {odometer + lo:,.1f} - {odometer + hi:,.1f} km "
          f"({lo:g}-{hi:g} km from now). Override with --interval MIN-MAX.")
    return 0


def cmd_set_odometer(args, today=None):
    path = ledger_path(args.ledger)
    data = load_ledger(path)
    bike = get_bike(data, args.bike)
    if bike.get("strava_gear_id"):
        raise ChainWaxError(f"'{args.bike}' reads its odometer live from Strava; set-odometer is for manual bikes.")
    if args.km < 0:
        raise ChainWaxError("The odometer can't be negative.")
    when = parse_date(args.date) if args.date else (today or date.today())
    bike["odometer_km"], bike["odometer_date"] = round(args.km, 1), when.isoformat()
    save_ledger(path, data)
    print(f"Odometer for {bike.get('name', args.bike)} set to {args.km:,.1f} km ({when}).")
    return 0


def cmd_add_bike(args):
    path = ledger_path(args.ledger)
    if not BIKE_ID.match(args.bike):
        raise ChainWaxError("Bike id must be lowercase letters, digits, '_' or '-' (e.g. road, tt_bike).")
    if path.exists():
        data = load_ledger(path)
    else:
        data = {"bikes": {}}
    if args.bike in data["bikes"]:
        raise ChainWaxError(f"Bike '{args.bike}' already exists.")
    if bool(args.gear_id) == bool(args.manual):
        raise ChainWaxError("Give exactly one of --gear-id ID (Strava bike) or --manual.")
    bike = {"name": args.name, "strava_gear_id": args.gear_id or None, "default_kind": args.kind, "waxes": []}
    if args.manual:
        if args.odometer is not None:
            bike["odometer_km"], bike["odometer_date"] = round(args.odometer, 1), date.today().isoformat()
    elif args.odometer is not None:
        raise ChainWaxError("--odometer is only for manual bikes; Strava bikes read it live.")
    data["bikes"][args.bike] = bike
    save_ledger(path, data)
    print(f"Added {args.name} ({'Strava ' + args.gear_id if args.gear_id else 'manual'}) to {path}.")
    print(f"Record its last wax with:  chain-wax.py log {args.bike} --odometer KM --date YYYY-MM-DD")
    return 0


# ---------------------------------------------------------------- CLI

def build_parser():
    p = argparse.ArgumentParser(description="Chain wax log and km-since-wax report.",
                                epilog="Run with no command for the report. See the top of this file for details.")
    p.add_argument("--ledger", help=f"ledger file (default: $CHAIN_WAX_LEDGER or {DEFAULT_LEDGER})")
    sub = p.add_subparsers(dest="command")

    r = sub.add_parser("report", help="km since last wax and next due, per bike (default)")
    r.add_argument("--json", action="store_true", help="machine-readable output")

    lg = sub.add_parser("log", help="record a wax")
    lg.add_argument("bike")
    lg.add_argument("--odometer", type=float, help="odometer in km (default: live Strava odometer; required for manual bikes)")
    lg.add_argument("--date", help="YYYY-MM-DD (default: today)")
    lg.add_argument("--product", help="wax or lube used")
    lg.add_argument("--kind", choices=sorted(INTERVALS), help="hot wax or drip lube (default: the bike's default)")
    lg.add_argument("--interval", help="MIN-MAX km until the next wax (default depends on kind and whether it is the first wax)")
    lg.add_argument("--degreased", action="store_true", help="the chain was fully degreased before this wax")
    lg.add_argument("--force", action="store_true", help="allow an odometer or date earlier than the last wax")

    so = sub.add_parser("set-odometer", help="update a manually tracked bike's odometer")
    so.add_argument("bike")
    so.add_argument("km", type=float)
    so.add_argument("--date", help="date of the reading (default: today)")

    ab = sub.add_parser("add-bike", help="add a bike to the ledger (creates the ledger if needed)")
    ab.add_argument("bike", help="short id, e.g. road")
    ab.add_argument("--name", required=True)
    ab.add_argument("--gear-id", help="Strava bike id (starts with b); see skills/strava/scripts/gear-mileage.sh")
    ab.add_argument("--manual", action="store_true", help="track the odometer by hand instead of via Strava")
    ab.add_argument("--odometer", type=float, help="current odometer for a manual bike")
    ab.add_argument("--kind", choices=sorted(INTERVALS), default="hot")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        cmd = args.command or "report"
        if cmd == "report":
            if args.command is None:
                args.json = False
            return cmd_report(args)
        return {"log": cmd_log, "set-odometer": cmd_set_odometer, "add-bike": cmd_add_bike}[cmd](args)
    except ChainWaxError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
