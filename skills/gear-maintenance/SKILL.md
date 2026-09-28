---
name: gear-maintenance
description: Track bike chain waxing and tyre wear by mileage. Use when the athlete mentions waxing a chain, changing tyres, or asks what gear maintenance is due. Ledger-based; odometers come from Strava or are entered by hand.
---

# Gear Maintenance

Ledger-based maintenance tracking for bikes: when the chain was last waxed and when it is due again, and how far each tyre set has run. Odometers come from Strava (lifetime gear distance) or, for bikes without Strava tracking, are entered by hand. Python 3 with the standard library only; no extra packages.

Personal ledgers live in `skills/gear-maintenance/data/` and are git-ignored: `chain-wax.json` and `tyres.json` (copy the `*.example.json` files or let `chain-wax.py add-bike` create the first one).

## Credentials

Strava odometers use the Strava skill's credentials: `STRAVA_ACCESS_TOKEN`, or `~/.config/strava/credentials.json`. Tokens last 6 hours; if a call says the token expired, run `bash skills/strava/scripts/refresh_token.sh` and retry. Find your Strava bike ids with `bash skills/strava/scripts/gear-mileage.sh`.

## `chain-wax.py` — Chain wax log

```bash
python3 skills/gear-maintenance/scripts/chain-wax.py report              # km since last wax, next due, status per bike
python3 skills/gear-maintenance/scripts/chain-wax.py report --json
python3 skills/gear-maintenance/scripts/chain-wax.py add-bike road --name "Road bike" --gear-id b1234567
python3 skills/gear-maintenance/scripts/chain-wax.py add-bike partner --name "Partner's bike" --manual --odometer 120
python3 skills/gear-maintenance/scripts/chain-wax.py log road --product "Hot wax" --degreased      # today, live odometer
python3 skills/gear-maintenance/scripts/chain-wax.py log road --odometer 1500 --date 2026-03-01 --interval 450-500
python3 skills/gear-maintenance/scripts/chain-wax.py set-odometer partner 180                     # manual bikes only
```

- Strava bikes read their lifetime distance from `/gear/{id}`. Indoor rides are included, since a chain wears on the trainer too.
- Manual bikes use the odometer you give; `report` flags readings older than 30 days.
- The due range `[min, max]` km is **fixed when a wax is logged**. Hot wax defaults to 150-250 km for the first re-wax (the first coating is thin) and 450-500 km after that; drip lube to 200-300 km; or pass `--interval MIN-MAX`.
- Status: `OK`, `DUE SOON` (within the last 10% before `min`), `DUE` (between `min` and `max`), `OVERDUE` (past `max`).
- `log` uses the live odometer by default. A past `--date`, or a manual bike, needs `--odometer`.
- Exit code 2 means a Strava odometer could not be read. A corrupt ledger is reported and never overwritten.

## `tyre-mileage.sh` — Tyre wear per wheelset

```bash
bash skills/gear-maintenance/scripts/tyre-mileage.sh              # per wheelset, outdoor km since fitted
bash skills/gear-maintenance/scripts/tyre-mileage.sh --verbose    # list every counted / excluded ride
bash skills/gear-maintenance/scripts/tyre-mileage.sh --json
```

Tyres are tied to **wheelsets**, in `data/tyres.json` (see `data/tyres.example.json`). Mileage is the sum of qualifying **outdoor** rides since the tyre's `fitted_date` across the wheelset's Strava gear ids. Indoor rides are excluded (VirtualRide, trainer flag, or a plain Ride with no GPS start), because tyres don't wear on a trainer; `manual_include_ids` / `manual_exclude_ids` override this. It flags a wear check every `wear_check_interval_km` and a replacement watch near `replace_at_km`. To replace a set: set `retired: true` on the old entry and add a new one.

## Notes

- Before v2.2 these scripts and ledgers lived in the Strava skill (`skills/strava/`). A ledger left there is still used, with a notice; move it to `skills/gear-maintenance/data/`.
- Chains and tyres differ on purpose: the chain counts indoor kilometres, the tyres don't.
