"""Pure, offline-testable logic for deciding which Strava activities count towards a tyre set's mileage.

Used by tyre-mileage.sh. Kept in its own module (rather than inline in the script's Python heredoc) so
this logic — the part that was wrong (see the module docstring on local_date) — can be unit tested
without a network call or a Strava account.
"""

from datetime import datetime, timezone

# The `after=` fetch below is only a network-efficiency filter, not the correctness filter (local_date
# is). 24 hours of margin covers every real-world UTC offset (-12 to +14) with room to spare: the most
# extreme case is a ride at local midnight of fitted_date in UTC+14, which lands at
# (fitted_date - 1) 10:00 UTC, still after (fitted_date - 1) 00:00 UTC.
FETCH_MARGIN_HOURS = 24


def fetch_after_epoch(fitted_date_str):
    """Unix epoch to pass to Strava's `after=` filter: deliberately earlier than local midnight of
    fitted_date in any timezone, so the real filter (local_date, below) never misses a ride. Over-fetching
    is harmless: the extra activities are filtered out afterwards by classify_activity."""
    midnight_utc = datetime.strptime(fitted_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(midnight_utc.timestamp()) - FETCH_MARGIN_HOURS * 3600


def local_date(act):
    """An activity's local calendar date (YYYY-MM-DD), read from Strava's own `start_date_local`.

    `start_date_local` carries the activity's local wall-clock time — per Strava's own per-activity
    timezone detection, from the ride's GPS start — serialized with a trailing "Z" that does NOT mean
    UTC. Comparing this directly against a ledger's `fitted_date` needs no timezone conversion or
    machine/ledger-configured timezone at all: both are already the athlete's own local dates.
    """
    return act.get("start_date_local", "")[:10]


def is_indoor(act):
    """True if the ride did not use the tyres (indoor): a trainer wears the chain but not the tyres."""
    if act.get("type") == "VirtualRide" or act.get("sport_type") == "VirtualRide":
        return True
    if act.get("trainer"):
        return True
    # plain Ride with no GPS start location -> indoor, no route
    if not act.get("start_latlng"):
        return True
    return False


def classify_activity(act, fitted_date, gear_ids, include_ids, exclude_ids):
    """Decide whether an activity counts towards a tyre set's mileage.

    Returns ("counted", None), ("excluded", reason) or ("skip", None). "skip" activities are not shown
    anywhere: they simply used different gear and are irrelevant to this tyre set.

    The fitted_date check is a hard boundary that manual_include_ids does not override: including a ride
    with the wrong gear_id, or one wrongly classified as indoor, is what manual_include_ids is for — not
    backdating a tyre set's fitting.
    """
    aid = act.get("id")
    if aid in exclude_ids:
        return "excluded", "manual_exclude"
    if local_date(act) < fitted_date:
        return "excluded", "before fitted_date"
    forced_in = aid in include_ids
    if not forced_in and act.get("gear_id") not in gear_ids:
        return "skip", None
    if not forced_in and is_indoor(act):
        return "excluded", "indoor"
    return "counted", None
