# What Kai does, in detail

The [capability table](../README.md#what-kai-does) in the README summarises these. Commands for each skill are in the skill's own README.

Ask "how did that session go?" and Kai pulls the workout from TrainingPeaks, the lap splits from Strava, and your recovery context from Garmin (sleep, HRV, resting HR). It then gives you:

- an **overall read**: execution quality, load vs plan, conditions
- a **planned vs actual table**: duration, pace, TSS, IF, HR, cadence, RPE and so on
- a **lap-by-lap breakdown** of intervals: pacing, HR drift, consistency

Kai reads the numbers *before* it reads your comments. If you say the run felt easy and the HR says otherwise, it tells you, instead of nodding along. It also knows the traps: smart-trainer ERG mode makes power look "perfectly paced", treadmill and GPS glitches corrupt pace, and TrainingPeaks has no lap data.

## Tracks fitness, fatigue and recovery
CTL / ATL / TSB (fitness, fatigue, form), weekly TSS, HRV and resting-HR trends, sleep, Body Battery and training readiness. It reads these together, since load without recovery context is only half the picture. This is what lets it answer "am I ready to add intensity?" or "why do I feel flat this week?" with data.

## Builds training plans (if you don't have a coach)
Kai can write a periodized plan (base, build, peak, taper) for triathlon, marathon or ultra events:

- assesses your current form and training history, then **checks that assessment with you** before writing anything
- sets training zones from your thresholds (FTP, run threshold, CSS), or prescribes field tests when it doesn't have them
- sets weekly load targets and a race-day CTL/TSB target
- writes sport-specific workouts with zones and paces, and a race-day pacing and nutrition plan

## Or supports the coach you already have
If you have a human coach, tell Kai in `USER.md`. It switches to analyst mode: it interprets your data, prepares your questions for your next check-in, explains what a session was for, and never overrides the plan.

## Optional extras
- **Gear tracking**: live shoe and bike mileage from Strava, tyre wear per wheelset, replacement and maintenance alerts.
- **Chain wax log**: `skills/gear-maintenance/scripts/chain-wax.py` keeps a ledger of waxes per bike (date, odometer, product, whether the chain was degreased) and reads live odometers from Strava. `report` shows km since the last wax and the next-due odometer, and flags `DUE SOON` (last 10% before the minimum), `DUE` and `OVERDUE`. By default a hot wax is followed by an early re-wax at 150-250 km (the first coating is thin), then 450-500 km; drip lube is 200-300 km; you can set any interval. Bikes without Strava tracking, like a partner's, work too: you give their odometer by hand and the report tells you when the reading is getting old. Kai runs the script instead of doing the arithmetic, so the answer is the same every session.
- **Nutrition and weight tracking**: log food and weight in plain chat. Weight goes to TrainingPeaks, food to a local CSV. Kai tracks kcal and protein, paces deficits to your training load, and checks tomorrow's session before recommending a low-carb day.
- **Race notes**: race-specific tactics, pacing and taper plans are saved to memory so they're available in any later chat.
- **Proactive checks**: with heartbeats enabled, Kai can watch for things like a recovery trend turning bad or a gear threshold approaching.

## Things to ask

> "Analyze this morning's run."
>
> "How's my training load? Am I ready to add intensity?"
>
> "I have a marathon on 2026-11-15. Review my fitness and build me a plan."
>
> "How's my recovery looking this week?"
>
> "What's my shoe mileage? Anything close to replacement?"
>
> "I waxed the road bike today. When is it due again?"
>
> "Log weight 72.4. Had oats and a protein shake for breakfast."
