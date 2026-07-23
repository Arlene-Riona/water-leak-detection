# Future Work

Improvements fall into two genuinely different categories. Confusing them
leads to waiting for "more data" when the actual blocker is an engineering
task, or building more code when the actual blocker is data the team
doesn't have yet. Both are listed here, kept separate.

## Blocked on data (no amount of further coding fixes these)

| Item | What's needed |
|---|---|
| Learned/calibrated thresholds (z-scores, multipliers, priority-score weights) | Confirmed leak/no-leak outcomes to optimize against (precision/recall/F1) |
| A real calibrated risk probability, replacing the current priority score | Same — outcome labels to validate a percentage against |
| Full statistically-learned seasonality (vs. the current calendar-rule patch) | 1+ years, ideally multiple years, of history per customer |
| Dynamic baseline updating + contamination detection | Enough historical depth to safely distinguish gradual drift from genuine behavior change (deliberately deferred rather than half-built — see below) |
| Validation against real outcomes (all current numbers are synthetic) | A feedback loop logging actual investigation results against flagged customers |

**The single most important unlock here is not "more months of consumption
data" — it's a feedback loop.** Five years of hourly readings with no record
of which flagged customers turned out to have real leaks is still not
enough to calibrate anything. Start logging outcomes (confirmed leak, false
alarm, inconclusive) against `Priority_Score` as early as possible.

## Blocked on architecture (buildable now, with data already available)

| Item | Status |
|---|---|
| Cohort/peer comparison | **Done** — see `02_Algorithm_Design.md`. This was the general-purpose fix for "a shared cause fools every detection path," as opposed to hardcoding individual known confounds |
| Ramadan-specific night-hour handling | **Done** for Residential (window shift) and Commercial/Hotel (MNF bypass to Mann-Kendall) |
| Extending seasonal handling to other calendar events | Only Ramadan received the deep, mechanism-specific fix. Eid al-Adha, National Day, summer holidays, New Year only get the shallow flag-and-cap treatment. Extending deeper handling to these is engineering work, not a data-wait — but first requires deciding whether each one has a real night-shifting mechanism worth building for (Ramadan's suhoor/extended-hours mechanism does not generalize automatically to, say, summer heat, which mostly affects daytime demand) |
| Burst-path seasonal awareness | **Not done.** The burst detection paths (strict consecutive and cumulative) are not routed through the seasonal confound logic at all. During Ramadan, a Commercial/Hotel account with genuinely busier nights can still trip the cumulative burst check every night. The tier cap prevents incorrect auto-escalation, but the flag wording itself is still misleading in this specific case |
| Automated regression test suite | **Not done.** Every validation number in `06_Validation.md` came from manual, ad-hoc sandbox testing. There is no `pytest`-style suite that locks in "false positive rate must stay near 0%" so a future code change can't silently reintroduce a bug like the original untested Option 7 |
| Robustness to messy real-world data | **Not done.** Not tested against: negative readings (meter rollback), DST transitions, duplicate meters per customer, inconsistent units across files, corrupted rows |
| Category-matching robustness | **Not done.** Folder-name substring matching is order-dependent and can misfire on combined keywords (e.g. "Government Villas") — flagged early, never fixed |

## Recommended next priorities, in order

1. **Start the feedback loop now**, even manually — a simple log of
   flagged-customer outcomes is the prerequisite for almost everything in
   the data-blocked list above, and the sooner it starts, the sooner those
   items become buildable.
2. **Close the burst-path seasonal gap** — the one identified, unfixed
   correctness issue remaining from real-data testing.
3. **Build the automated test suite** — turn the ad-hoc validation scripts
   already run for this project into a real, re-runnable `pytest` suite, so
   future changes can't silently reintroduce a fixed bug.
4. **Harden against real-world data quality issues** before this moves past
   proof-of-concept status into anything resembling production use.

## Explicitly out of scope for this proof-of-concept

This codebase is a validated proof-of-concept for the *detection logic and
architecture*. It has not been hardened against real-world data issues and
should not be deployed as-is against production data, or used for
autonomous (non-human-reviewed) dispatch decisions, without the work listed
above.