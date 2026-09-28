# Endurance Training Coach Skill

Create personalized, periodized training plans for triathlon, marathon, and ultra-endurance events. Integrates with TrainingPeaks, Garmin, and Strava to build data-driven plans from your actual training history and current fitness.

## Features

- Periodized training plans: base, build, peak, and taper phases
- CTL/ATL/TSB-driven load management and weekly TSS targets
- Sport-specific training zones derived from field test data (FTP, LTHR, CSS)
- Athlete assessment: current form, athletic foundation, strengths and limiters
- Recovery-aware scheduling using HRV, Body Battery, and resting HR trends
- Workout library: structured sessions for run, bike, and swim
- Race day strategy: pacing, nutrition, and execution plan
- Works with any combination of TrainingPeaks, Garmin, and Strava — falls back to manual assessment if none are configured

## Requirements

- At least one of: TrainingPeaks, Garmin, or Strava skill configured
- Python 3.12+ for the Garmin skill (TrainingPeaks needs 3.6+)

## How It Works

The coach reads your configured data source skills to gather training context before writing any plan. It does not hardcode queries — it reads each skill's SKILL.md and uses whatever is available.

**Data priority:**
- Training load (CTL/ATL/TSB, workouts, PRs) → TrainingPeaks
- Recovery and readiness (HRV, Body Battery, sleep) → Garmin
- Activity detail (laps, splits, intervals) → Strava or Garmin

If no skills are configured, the coach falls back to a manual questionnaire covering training history, race goals, and current fitness.

## Setup

No additional setup beyond the data source skills. Ensure at least one of TrainingPeaks, Garmin, or Strava is authenticated.

To use, ask Kai for a training plan or coaching advice. Example prompts:

> "Build me a 16-week Ironman plan targeting the race on 2026-09-15."

> "I have a marathon in 12 weeks. Can you review my current fitness and build a plan?"

> "How's my training load looking? Am I ready to add intensity?"

## Reference Files

| File | Contents |
|------|----------|
| `reference/assessment.md` | How to interpret athlete data and validate the assessment |
| `reference/zones.md` | Training zone calculations and field test protocols |
| `reference/load-management.md` | CTL/ATL/TSB targets, weekly TSS, progression guidelines |
| `reference/periodization.md` | Macrocycle structure, phase design, recovery weeks |
| `reference/workouts.md` | Sport-specific workout library |
| `reference/templates.md` | Plan template syntax and examples |
| `reference/race-day.md` | Pacing strategy, nutrition, and race execution |

## Key Concepts

| Term | Description |
|------|-------------|
| **CTL** | Chronic Training Load — fitness. Builds slowly over weeks. |
| **ATL** | Acute Training Load — fatigue. Spikes with hard training. |
| **TSB** | Training Stress Balance — form. TSB = CTL − ATL. Positive = fresh. |
| **TSS** | Training Stress Score per workout. |
| **FTP** | Functional Threshold Power (bike). |
| **LTHR** | Lactate Threshold Heart Rate. |
| **CSS** | Critical Swim Speed. |

## Credits

Originally based on [endurance-coach](https://github.com/shiv19/endurance-coach-skill) by shiv19 (MIT). Adapted with multi-skill data integration, replacing the original SQLite/Strava sync approach with direct skill delegation.

## License

GPL v3
