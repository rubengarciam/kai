#!/usr/bin/env python3
"""Tyre ledger helper: add wheelsets, fit new tyre sets, retire old ones.

Edits the ledger that `tyre-mileage.sh` reports on (skills/gear-maintenance/data/tyres.json), so nobody
has to hand-edit JSON. The mileage report itself stays in tyre-mileage.sh.

Usage:
  tyres.py [--ledger PATH] list [--json]
  tyres.py add-wheelset ID --name TEXT [--usual-bike TEXT] [--gear-id bXXXX ...]
  tyres.py add-set WHEELSET --model TEXT [--date YYYY-MM-DD] [--odometer KM] [--wear-interval KM]
                            [--replace-at KM] [--note TEXT] [--replace]
  tyres.py retire TYRE_ID [--date YYYY-MM-DD] [--note TEXT]

Notes
  * Tyres belong to a WHEELSET, not a bike. A wheelset wears one tyre set at a time, so `add-set`
    refuses while the wheelset already has an active set; add --replace to retire it (as of the new
    set's date) and fit the new one in a single write.
  * A wheelset may have no Strava gear ids (wheels in storage) or several. The mileage report counts
    outdoor rides for those ids since the tyre's fitted_date; indoor rides are excluded.
  * `fitted_bike_odometer_km` is informational only (the report never reads it). It is filled from
    --odometer, or from Strava when the wheelset has exactly one gear id and the set is fitted today;
    otherwise it stays null.
  * The ledger is loaded, changed and saved as a whole: unknown fields, notes and key order are kept.
    The write is atomic, and a corrupt ledger is reported and never overwritten.

Ledger location, same rule as tyre-mileage.sh: data/tyres.json next to this script, or the old
skills/strava/data/tyres.json if that is the only one (with a notice). $TYRES_LEDGER or --ledger override.
A new ledger is never created while an old-location one exists.

Strava credentials (only for the optional odometer lookup): STRAVA_ACCESS_TOKEN or
~/.config/strava/credentials.json.

Exit codes: 0 ok, 1 error (bad input, ledger problem).
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

DEFAULT_LEDGER = Path(__file__).resolve().parent.parent / "data" / "tyres.json"
LEGACY_LEDGER = Path(__file__).resolve().parent.parent.parent / "strava" / "data" / "tyres.json"
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
GEAR_ID = re.compile(r"^b\d+$")   # Strava bike ids start with 'b'
DEFAULT_WEAR_INTERVAL_KM = 500


class TyreError(Exception):
    """A problem the user can fix; printed without a traceback."""


class OdometerUnavailable(TyreError):
    pass


# ---------------------------------------------------------------- ledger

def ledger_path(arg):
    explicit = arg or os.environ.get("TYRES_LEDGER")
    if explicit:
        return Path(explicit).expanduser()
    if not DEFAULT_LEDGER.exists() and LEGACY_LEDGER.exists():
        print(f"Note: using the tyre ledger at its old location {LEGACY_LEDGER}. "
              f"Move it to {DEFAULT_LEDGER} (tyre tracking now lives in skills/gear-maintenance).", file=sys.stderr)
        return LEGACY_LEDGER
    return DEFAULT_LEDGER


def load_ledger(path, create=False):
    """Read the ledger. Missing: an error with a hint (or an empty ledger if create). Corrupt: never touched."""
    if not path.exists():
        if create:
            return {"wheelsets": {}, "tyres": []}
        raise TyreError(f"No tyre ledger at {path}.\n"
                        "Start one with:  tyres.py add-wheelset road --name \"Road wheels\" --gear-id <strava bike id>")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise TyreError(f"{path} is not valid JSON ({e}). Fix or restore it; nothing was changed.")
    if not isinstance(data, dict) or not isinstance(data.get("wheelsets", {}), dict) \
            or not isinstance(data.get("tyres", []), list):
        raise TyreError(f"{path} does not look like a tyre ledger (needs \"wheelsets\" and \"tyres\"). Nothing was changed.")
    data.setdefault("wheelsets", {})
    data.setdefault("tyres", [])
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


# ---------------------------------------------------------------- Strava (optional odometer lookup)

def fetch_gear_km(gear_id):
    token = os.environ.get("STRAVA_ACCESS_TOKEN")
    if not token:
        creds = Path.home() / ".config" / "strava" / "credentials.json"
        if creds.exists():
            token = json.loads(creds.read_text()).get("STRAVA_ACCESS_TOKEN")
    if not token:
        raise OdometerUnavailable("STRAVA_ACCESS_TOKEN not set")
    req = urllib.request.Request(f"https://www.strava.com/api/v3/gear/{gear_id}",
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())["distance"] / 1000.0
    except urllib.error.HTTPError as e:
        hint = " (token expired: run skills/strava/scripts/refresh_token.sh)" if e.code == 401 else ""
        raise OdometerUnavailable(f"Strava returned HTTP {e.code} for gear {gear_id}{hint}")
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
        raise OdometerUnavailable(f"could not read gear {gear_id} from Strava: {e}")


# ---------------------------------------------------------------- helpers

def parse_date(text, what="date"):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise TyreError(f"Invalid {what} '{text}': use YYYY-MM-DD.")


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:24].rstrip("-")) or "tyre"


def unique_tyre_id(data, wheelset, model, when):
    base = f"{wheelset}-{slugify(model)}-{when.isoformat()}"
    taken = {t.get("id") for t in data["tyres"]}
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def active_sets(data, wheelset):
    return [t for t in data["tyres"] if t.get("wheelset") == wheelset and not t.get("retired")]


def positive(text, what):
    try:
        value = float(text)
    except ValueError:
        raise TyreError(f"{what} must be a number of km.")
    if value <= 0:
        raise TyreError(f"{what} must be greater than 0.")
    return value


def num(x):
    return f"{x:g}"


# ---------------------------------------------------------------- commands

def cmd_list(args):
    data = load_ledger(ledger_path(args.ledger))
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    if not data["wheelsets"]:
        print("No wheelsets in the ledger yet.")
        return 0
    for wid, ws in data["wheelsets"].items():
        gids = ", ".join(ws.get("gear_ids") or []) or "no Strava gear (storage)"
        print(f"{wid}: {ws.get('name', wid)}  (bike: {ws.get('usual_bike') or '-'}; {gids})")
        sets = [t for t in data["tyres"] if t.get("wheelset") == wid]
        for t in sets:
            state = f"retired {t['retired_date']}" if t.get("retired") and t.get("retired_date") else \
                    "retired" if t.get("retired") else "ACTIVE"
            limits = f"check every {num(t.get('wear_check_interval_km', DEFAULT_WEAR_INTERVAL_KM))} km"
            if t.get("replace_at_km"):
                limits += f", replace at {num(t['replace_at_km'])} km"
            print(f"  - {t['id']}: {t.get('model', '')}, fitted {t.get('fitted_date')}, {state} ({limits})")
        if not sets:
            print("  (no tyre sets yet)")
    orphans = [t["id"] for t in data["tyres"] if t.get("wheelset") not in data["wheelsets"]]
    if orphans:
        print(f"! tyre sets pointing at an unknown wheelset: {', '.join(orphans)}")
    return 0


def cmd_add_wheelset(args):
    path = ledger_path(args.ledger)
    data = load_ledger(path, create=True)
    if not SLUG.match(args.wheelset):
        raise TyreError("Wheelset id must be lowercase letters, digits, '_' or '-' (e.g. road_wheels).")
    if args.wheelset in data["wheelsets"]:
        raise TyreError(f"Wheelset '{args.wheelset}' already exists.")
    for gid in args.gear_id:
        if not GEAR_ID.match(gid):
            raise TyreError(f"'{gid}' is not a Strava bike id (they look like b1234567; see skills/strava/scripts/gear-mileage.sh).")
    if len(set(args.gear_id)) != len(args.gear_id):
        raise TyreError("A gear id was given twice.")
    data["wheelsets"][args.wheelset] = {"name": args.name, "usual_bike": args.usual_bike or "",
                                        "gear_ids": list(args.gear_id)}
    save_ledger(path, data)
    gids = ", ".join(args.gear_id) or "no Strava gear"
    print(f"Added wheelset {args.wheelset} ({args.name}; {gids}) to {path}.")
    print(f"Fit its tyres with:  tyres.py add-set {args.wheelset} --model \"...\"")
    return 0


def cmd_add_set(args, fetch=fetch_gear_km, today=None):
    path = ledger_path(args.ledger)
    data = load_ledger(path)
    today = today or date.today()
    ws = data["wheelsets"].get(args.wheelset)
    if ws is None:
        known = ", ".join(sorted(data["wheelsets"])) or "none"
        raise TyreError(f"Unknown wheelset '{args.wheelset}'. Known wheelsets: {known}. Add one with add-wheelset.")
    when = parse_date(args.date) if args.date else today
    if when > today:
        raise TyreError(f"--date {when} is in the future.")
    wear = positive(args.wear_interval, "--wear-interval") if args.wear_interval is not None else DEFAULT_WEAR_INTERVAL_KM
    replace_at = positive(args.replace_at, "--replace-at") if args.replace_at is not None else None
    if args.odometer is not None and args.odometer < 0:
        raise TyreError("--odometer can't be negative.")

    active = active_sets(data, args.wheelset)
    retired_now = []
    if active:
        if not args.replace:
            names = ", ".join(f"{t['id']} (fitted {t.get('fitted_date')})" for t in active)
            raise TyreError(f"Wheelset '{args.wheelset}' already has an active tyre set: {names}.\n"
                            "A wheelset wears one set at a time. Add --replace to retire it as of the new set's date.")
        for t in active:
            fitted = parse_date(t["fitted_date"], "fitted_date") if t.get("fitted_date") else None
            if fitted and when < fitted:
                raise TyreError(f"--date {when} is before the active set was fitted ({fitted}).")
        for t in active:
            t["retired"] = True
            t["retired_date"] = when.isoformat()
            retired_now.append(t["id"])

    odometer, note_odo = None, ""
    if args.odometer is not None:
        odometer = round(args.odometer, 1)
    elif len(ws.get("gear_ids") or []) == 1 and when == today:
        try:
            odometer = round(fetch(ws["gear_ids"][0]), 1)
        except OdometerUnavailable as e:
            note_odo = f" (bike odometer not recorded: {e})"

    entry = {"id": unique_tyre_id(data, args.wheelset, args.model, when), "wheelset": args.wheelset,
             "model": args.model, "fitted_date": when.isoformat(), "fitted_bike_odometer_km": odometer,
             "wear_check_interval_km": int(wear) if wear == int(wear) else wear}
    if replace_at is not None:
        entry["replace_at_km"] = int(replace_at) if replace_at == int(replace_at) else replace_at
    entry.update({"retired": False, "manual_include_ids": [], "manual_exclude_ids": [], "note": args.note or ""})
    data["tyres"].append(entry)
    save_ledger(path, data)

    for tid in retired_now:
        print(f"Retired {tid} as of {when}.")
    print(f"Fitted {args.model} on {ws.get('name', args.wheelset)} as {entry['id']} ({when}); "
          f"wear check every {num(entry['wear_check_interval_km'])} km"
          + (f", replace at {num(entry['replace_at_km'])} km" if "replace_at_km" in entry else "") + f".{note_odo}")
    print("Mileage counts outdoor rides from that date; see it with: bash skills/gear-maintenance/scripts/tyre-mileage.sh")
    return 0


def cmd_retire(args, today=None):
    path = ledger_path(args.ledger)
    data = load_ledger(path)
    today = today or date.today()
    tyre = next((t for t in data["tyres"] if t.get("id") == args.tyre_id), None)
    if tyre is None:
        ids = ", ".join(t.get("id", "?") for t in data["tyres"]) or "none"
        raise TyreError(f"Unknown tyre set '{args.tyre_id}'. Known: {ids}.")
    if tyre.get("retired"):
        raise TyreError(f"{args.tyre_id} is already retired" + (f" ({tyre['retired_date']})." if tyre.get("retired_date") else "."))
    when = parse_date(args.date) if args.date else today
    if when > today:
        raise TyreError(f"--date {when} is in the future.")
    if tyre.get("fitted_date") and when < parse_date(tyre["fitted_date"], "fitted_date"):
        raise TyreError(f"--date {when} is before the set was fitted ({tyre['fitted_date']}).")
    tyre["retired"] = True
    tyre["retired_date"] = when.isoformat()
    if args.note:
        tyre["note"] = (tyre.get("note") + " | " if tyre.get("note") else "") + args.note
    save_ledger(path, data)
    print(f"Retired {args.tyre_id} as of {when}. Its wheelset has no active tyres now; fit new ones with add-set.")
    return 0


# ---------------------------------------------------------------- CLI

def build_parser():
    p = argparse.ArgumentParser(description="Tyre ledger helper (add wheelsets, fit and retire tyre sets).",
                                epilog="The mileage report is tyre-mileage.sh. See the top of this file for details.")
    p.add_argument("--ledger", help=f"ledger file (default: $TYRES_LEDGER or {DEFAULT_LEDGER})")
    sub = p.add_subparsers(dest="command", required=True)

    ls = sub.add_parser("list", help="wheelsets and tyre sets in the ledger")
    ls.add_argument("--json", action="store_true", help="print the raw ledger")

    aw = sub.add_parser("add-wheelset", help="add a wheelset (creates the ledger if needed)")
    aw.add_argument("wheelset", help="short id, e.g. road_wheels")
    aw.add_argument("--name", required=True)
    aw.add_argument("--usual-bike", help="free text, shown in the report")
    aw.add_argument("--gear-id", action="append", default=[], metavar="bXXXX",
                    help="Strava bike id used with this wheelset (repeatable; none for wheels in storage)")

    ad = sub.add_parser("add-set", help="fit a tyre set on a wheelset")
    ad.add_argument("wheelset")
    ad.add_argument("--model", required=True)
    ad.add_argument("--date", help="fitted date YYYY-MM-DD (default: today)")
    ad.add_argument("--odometer", type=float, help="bike odometer at fitting, km (informational; default: from Strava "
                                                  "when the wheelset has exactly one gear id and the date is today)")
    ad.add_argument("--wear-interval", help=f"km between wear/cut checks (default {DEFAULT_WEAR_INTERVAL_KM})")
    ad.add_argument("--replace-at", help="end-of-life km (optional)")
    ad.add_argument("--note")
    ad.add_argument("--replace", action="store_true", help="retire the wheelset's active set as of the new date")

    rt = sub.add_parser("retire", help="retire a tyre set")
    rt.add_argument("tyre_id")
    rt.add_argument("--date", help="retirement date YYYY-MM-DD (default: today)")
    rt.add_argument("--note", help="appended to the set's note")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return {"list": cmd_list, "add-wheelset": cmd_add_wheelset, "add-set": cmd_add_set, "retire": cmd_retire}[args.command](args)
    except TyreError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
