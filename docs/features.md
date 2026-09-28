# What Kai does, in detail

The [capability table](../README.md#what-kai-does) in the README is the summary. This page explains how each capability works, what it needs, what the output looks like and where its limits are. Commands live in each skill's own README, linked from every section.

**On this page:** [Workout analysis](#workout-analysis) · [Fitness, fatigue and load](#fitness-fatigue-and-load) · [Recovery monitoring](#recovery-monitoring) · [Training plans](#training-plans) · [Analyst mode](#analyst-mode) · [Gear tracking](#gear-tracking) · [Chain wax log](#chain-wax-log) · [Nutrition and weight](#nutrition-and-weight) · [Race notes](#race-notes) · [Memory and personalisation](#memory-and-personalisation) · [Proactive checks](#proactive-checks) · [Safety and boundaries](#safety-and-boundaries) · [Things to ask](#things-to-ask)

## Workout analysis

**What you get.** Ask "how did that session go?" and Kai answers in two layers: an **overall read** (execution quality, load against plan, conditions) and a **lap-by-lap breakdown** of each rep with pace or power, heart rate, cadence, drift and consistency. Planned and actual numbers sit side by side:

```
Overall: 5 x 6' at threshold, well executed; HR drifted 4 bpm across the set

| Metric     | Planned    | Actual     |
| ---------- | ---------- | ---------- |
| Duration   | 1:10:00    | 1:11:20    |
| Avg pace   | —          | 4:52 /km   |
| TSS        | 68         | 71 ✓       |
| IF         | 0.86       | 0.87 ✓     |
| Avg HR     | —          | 158        |
| RPE        | —          | 7          |
```

(Example numbers.) `—` marks a metric with no planned target, `✓` one that hit plan.

**How it works.**
1. Kai loads your load metrics and the workout from TrainingPeaks, the lap splits from Strava (TrainingPeaks has no lap data) and your recovery context from Garmin: sleep, HRV and resting heart rate for the last three days. A session can't be read without both sides.
2. It analyses the **raw data first**, on its own: splits, pace or power against the prescribed zone, heart rate, cadence.
3. **Only then** does it read your comment or RPE, as a cross-check. If they disagree, it says so plainly instead of letting your framing explain away an anomaly. If you say the run felt easy and the heart rate says otherwise, you'll hear about it.

**Traps it knows about.**
- A smart trainer in **ERG mode** locks power to the target, so perfectly flat power isn't pacing discipline. Kai reads heart-rate drift, cadence and RPE instead.
- **Treadmill pace, hand-tapped laps and GPS glitches** are the exceptions where it distrusts the device and trusts your account; stop-start traffic that inflates elapsed time is corrected for.
- TrainingPeaks' **shoe field** auto-assigns the last shoe used, so Kai asks which shoe you wore instead of trusting it.
- The TrainingPeaks **"Feeling" scale** runs low = good, high = bad (like RPE); Kai confirms this with you the first time.
- It uses TrainingPeaks' TSS, normalised power and IF, not Strava's, which are less accurate.

**Needs.** TrainingPeaks (load and the workout), plus Strava for laps and Garmin for recovery context. With fewer sources Kai works with what it has and says what's missing.

**Good to know.** Garmin data lags by a day or two after a sync, so the newest day can be empty; Kai fetches a few days and uses the latest complete one. On chat surfaces that don't render tables (WhatsApp, some Discord setups) it uses bullet lists.

**Skill docs.** [TrainingPeaks](../skills/trainingpeaks/README.md), [Strava](../skills/strava/README.md), [Garmin](../skills/garmin-health-analysis/README.md).

## Fitness, fatigue and load

**What you get.** The training-load picture from TrainingPeaks: **CTL** (fitness, builds slowly), **ATL** (fatigue, spikes with hard training) and **TSB** (form = CTL − ATL), plus weekly TSS, workout TSS and intensity factor, and personal records by sport and duration (bike power from 5 seconds to 90 minutes, run speeds from 400 m to the marathon). Kai reads them against a simple scale:

| TSB | State | Meaning |
| --- | ----- | ------- |
| +15 to +25 | Fresh / peaked | Race ready; may lose fitness if held |
| +5 to +15 | Rested | Good for quality sessions and minor events |
| −10 to +5 | Neutral | Normal training |
| −10 to −30 | Fatigued | Building load; recovery needed soon |
| below −30 | Overreaching | High injury and burnout risk; reduce load |

**Race-day targets** it plans towards: TSB of about 0 to +10 for a sprint triathlon, +5 to +15 for Olympic, +10 to +20 for a 70.3 or a marathon, +15 to +25 for an Ironman, with tapers from about a week (sprint) to three to four weeks (Ironman). Details, including CTL ramp-rate limits by athlete level and weekly TSS by phase, are in the coach skill's [load management guide](../skills/endurance-training-coach/reference/load-management.md).

**Needs.** TrainingPeaks. This is the source of truth for load; without it Kai asks you for your recent training instead.

**Good to know.** TrainingPeaks access uses your browser's login cookie, which lasts weeks and then needs renewing; see the [TrainingPeaks skill](../skills/trainingpeaks/README.md).

## Recovery monitoring

**What you get.** Load without recovery is half the picture, so Kai reads both. From Garmin Connect:
- **Sleep:** hours, light/deep/REM/awake stages, score, HRV, respiration.
- **Recovery:** resting heart rate, HRV trend, Body Battery, stress, training readiness and training status.
- **Fitness markers:** VO2 max, lactate threshold, endurance and hill scores, fitness age, race predictions (5K to marathon).
- **Other:** body composition and weigh-ins, SpO2, steps, floors, intensity minutes, hydration, all-day and intraday heart rate and stress.
- **Ask by time:** "what was my heart rate at 3pm yesterday?" is answered from the intraday data.
- **Dashboards:** sleep, Body Battery, HRV and activity charts, or a combined dashboard, generated as a local HTML page.
- **Activity files:** GPX (and FIT) downloads with elevation, pace or heart rate looked up at any distance or time.

This is what lets Kai answer "am I ready to add intensity?" or "why do I feel flat this week?" with data instead of guesses.

**How it interprets it.** Before reading intensity or HRV at face value, Kai checks `USER.md` and its memory for illness or injury history: a low HRV after a bug means something different from a low HRV in a normal week.

**Needs.** A Garmin Connect account, Python 3.12+ and the packages in `requirements.txt`, and a one-time login that **you run yourself in your own terminal**: the password is never stored and Kai never asks for it in chat. See [installation](installation.md#python-packages-garmin-only).

**Limits.** The Garmin connection uses a community library, not an official API, so it can break or be rate-limited. FIT files are currently saved as ZIP archives, so analysing them fails (tracked in [#15](https://github.com/rubengarciam/kai/issues/15)); GPX works. Some metrics need specific hardware (Body Battery needs an HRV-capable watch).

**Skill doc.** [garmin-health-analysis](../skills/garmin-health-analysis/README.md).

## Training plans

**What you get.** If you don't have a human coach, Kai builds a **periodized plan** for triathlon, marathon or ultra events, with zones and paces for every workout, weekly load targets and a race-day plan. It works in six steps and won't skip the one that matters:

1. **Gather data** from whatever is connected, or ask the questions in the [assessment guide](../skills/endurance-training-coach/reference/assessment.md) if nothing is.
2. **Assess** your current form (the last 8 to 12 weeks) separately from your athletic foundation (two-plus years and past races), because a recent break matters more than an old PR. It also looks for limiters and strengths across sports.
3. **Validate with you.** Kai presents its assessment (background, form, strengths, recovery, constraints, goals, preferences, which days suit long sessions) and waits for your confirmation **before writing anything**.
4. **Set zones and load.** Zones come from your thresholds (FTP, run threshold, CSS); if you don't have them, Kai prescribes a field test: a 30-minute run threshold test, a 20-minute FTP test or a critical swim speed test. It then sets weekly TSS progression, a target CTL and the taper. Reference: [zones and testing](../skills/endurance-training-coach/reference/zones.md).
5. **Design the plan:** base (about 40 to 50% of the time available), build (30 to 40%), peak (10 to 15%) and a taper of one to three weeks, in 3:1 or 4:1 loading blocks, with key sessions, recovery days, long sessions and bricks for triathlon. Reference: [periodization](../skills/endurance-training-coach/reference/periodization.md).
6. **Deliver** the plan, a zone card, a race-day checklist and a nutrition plan. Race execution covers pacing by event length, triathlon swim/bike/run-off-bike pacing, marathon pacing, heart-rate ceilings for long events, and carbohydrate and hydration targets, with specific plans for a 70.3 and an Ironman. Reference: [race day](../skills/endurance-training-coach/reference/race-day.md).

**Principles it plans by.** Consistency over heroics; easy days easy and hard days hard; recovery is when adaptation happens; put time into the limiter; be more specific as the race nears; practise fuelling in long sessions; be conservative with progression ("better to undercook than overcook"); don't panic-add volume during the taper.

**Needs.** Any one data source, or nothing but a chat: without data it falls back to questions.

**Good to know.** The coach skill's workout-template pages describe a template command line from the original project it was adapted from; that tool isn't part of this repo, so Kai composes weekly schedules directly.

**Skill doc.** [endurance-training-coach](../skills/endurance-training-coach/README.md).

## Analyst mode

If you already have a human coach, say so in `USER.md` (the "Coaching setup" section). Kai then **doesn't write plans or override your coach**. It interprets your data and trends, assesses recovery, explains what a session was for, and prepares the questions and key data points for your next check-in. If `USER.md` doesn't say either way, Kai asks.

## Gear tracking

**What you get.**
- **Shoes and bikes:** lifetime distance for every bike and pair of shoes, read live from Strava, never stored as a stale number. Kai keeps your rotation and replacement thresholds in its memory and warns when one is within about 10%. Sensible defaults: racing shoes about 500 km, training shoes 700 to 800 km.
- **Tyres, per wheelset:** tyres wear with the wheels, not the bike, so they're tracked per wheelset. Mileage counts **outdoor** rides since the tyre's fitted date; indoor rides (virtual rides, trainer rides, rides with no GPS) are excluded, because tyres don't wear on a trainer. The report flags a wear-and-cut check every 500 km (configurable) and a replacement watch as you near the end-of-life distance you set.
- **Tyre changes without editing JSON:** `tyres.py` adds wheelsets, fits a new set, retires the old one and lists everything. A wheelset wears one set at a time, so fitting a new set while one is active needs `--replace`, which retires the old set on the same date in a single safe write.
- **Other maintenance:** brake pad, rotor, chain and full-service intervals are kept in Kai's memory notes and raised proactively as they approach.

**Needs.** Strava for odometers. Tyres also need a ledger: `tyres.py add-wheelset` creates it.

**Skill docs.** [gear-maintenance](../skills/gear-maintenance/README.md) (tyres), [strava](../skills/strava/README.md) (mileage).

## Chain wax log

**What you get.** A per-bike ledger of chain waxes and a report that says how far each chain has run since its last wax and when the next is due:

```
Bike        Odometer          Last wax              Since     Next due (odometer)  Status
----------  ----------------  --------------------  --------  -------------------  --------
Road bike   4,210.0 km        2026-08-01 @ 3,800.0  410.0 km  4,250.0 - 4,300.0    DUE SOON
Partner's   130.0 km (manual) 2026-04-22 @ 40.0     90.0 km   490.0 - 540.0        OK
! Partner's: manual odometer reading is 60 days old (set a fresh one with set-odometer)
```

(Example numbers.)

- **Statuses.** `OK`; `DUE SOON` in the last 10% before the minimum of the due range; `DUE` between the minimum and maximum; `OVERDUE` past the maximum.
- **Due ranges are fixed when a wax is logged**, so a later change of defaults never rewrites history. Defaults: for hot wax, an early first re-wax at 150 to 250 km (the first coating is thin), then 450 to 500 km; for drip lube, 200 to 300 km. Any interval can be set per wax.
- **Indoor kilometres count**, because a chain wears on the trainer too (unlike tyres).
- **Manual bikes** (a partner's bike, one not on Strava) take their odometer from you, and the report flags a reading that's getting old.
- **Logging** is as easy as telling Kai "I waxed the road bike today": it records the date, the live odometer and the product, and reads the next-due range back to you.
- **Safe by design:** Kai runs the script instead of doing the arithmetic, so the answer is the same every session. The ledger is written atomically, and a corrupt one is reported, never overwritten.

**Needs.** Strava for live odometers (or manual bikes only). **Skill doc.** [gear-maintenance](../skills/gear-maintenance/README.md).

## Nutrition and weight

Optional, and handled by Kai itself because nutrition and training load are too coupled to hand off.

- **Log in plain chat:** "Log weight 72.4. Had oats and a protein shake for breakfast." Weight is written to TrainingPeaks, which stays the single source of truth. Food is estimated and appended to a local CSV (`date, description, est_kcal, est_protein_g, notes`; see [the example](../data/nutrition-log.example.csv)).
- **Calories and protein by default.** Carbs and fat are added only if something looks off: a weight stall across two or more check-ins despite a logged deficit, or unexplained energy dips.
- **Your defaults are remembered.** Tell Kai once that "coffee" means a black espresso or "protein shake" means a specific brand, and it's saved and reused.
- **Tomorrow's session first.** Before any nutrition advice Kai checks the next day's training. It won't suggest a carb-light or deficit day before a hard or long session, because the 12 to 15 hours before it matter for glycogen.
- **Deficits follow load.** Deficits ease off in high-TSS weeks, and Kai never suggests one in race week. A weekly check-in compares your weight trend with your target pace and adjusts.

**Needs.** TrainingPeaks for weight and the schedule.

## Race notes

If you work out tactics for a specific race in its own chat, Kai writes the plan (pacing, fuelling, pack and position calls, taper) to `memory/project_race_<race-name>.md` as it firms up, updating the same file rather than creating conflicting versions. It's indexed in `MEMORY.md`, so any later chat can find it.

## Memory and personalisation

Everything Kai remembers is **plain markdown in your folder**, so it survives a change of model or agent and you can read or edit it.
- **`USER.md`:** you: thresholds, goals, race calendar, constraints, injury and health notes, whether you have a coach, preferences.
- **`MEMORY.md`:** an index of the notes in `memory/`. Each note has a type: `user` (facts about you), `feedback` (a correction or confirmed approach, with the reason), `project` (an ongoing block, injury or race, updated in place) or `reference` (where live data lives).
- **Corrections stick.** Tell Kai "don't do X, because Y" and it records a feedback note.
- **Daily notes** (`memory/YYYY-MM-DD.md`) log what happened; recent ones are read at the start of each session.
- **Multi-step tasks** get short progress messages ("Pulling laps…", "Analysing splits…") so you're not left in silence.

## Proactive checks

On agents that send **heartbeat** polls (OpenClaw does), Kai keeps a small `HEARTBEAT.md` checklist (recovery trend, upcoming key session, gear thresholds, missed sessions), records when each check last ran, and stays quiet unless something needs attention or it's late at night. On other agents Kai only answers when you talk to it; running it on a schedule there is on the [roadmap](https://github.com/rubengarciam/kai/issues/11).

## Safety and boundaries

- **Not a doctor.** Persistent pain, dizziness, chest symptoms, unexplained fatigue lasting weeks and blood-work questions get a plain recommendation to see a professional, and Kai stops short of diagnosing.
- **Credentials.** Kai never asks for passwords or tokens in chat and never writes them to memory or logs. The Garmin login is yours to run.
- **Asks before it acts outside your folder:** anything that leaves the machine (emails, posts, sharing your data), and anything destructive.
- **Group chats.** Kai is a participant, not your voice, and speaks when asked or when it adds real value.
- **Direct.** If the data says you under-executed or are overreaching, it says so, with the numbers.

What crosses the network, and what stays on your machine, is described in [architecture and privacy](architecture.md#privacy).

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
> "I fitted new tyres on the road wheels today."
>
> "Log weight 72.4. Had oats and a protein shake for breakfast."
>
> "Prepare my questions for Thursday's session with my coach."
