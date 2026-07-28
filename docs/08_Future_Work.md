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
| Dynamic baseline updating + real contamination fix | Confirmed genuinely hard, not just deferred: three fix attempts were built and tested against real (BATADAL) and synthetic data, and all three failed — see `06_Validation.md`. A real fix needs either (a) changepoint detection (PELT/BOCPD — more principled than what we tried, not yet built or tested), or (b) a machine-learning approach trained to resist contaminated data (RSM-GAN/RiAD-style, needs real training data + confirmed outcomes we don't have) |
| Validation against real, confirmed customer outcomes | **Meaningfully addressed** — see `06_Validation.md`. Two independent real, labeled datasets tested: BATADAL (cross-domain, network cyber-attacks — weak result, honest domain-mismatch caveat) and BattLeDIM (same-domain, actual pipe leaks on customer-shaped demand data — strong result: 100% precision, 71% recall, 0% false positive rate on 27 real test cases). Both point to the same open weakness (baseline contamination). Still needed: validation against *your own* real customers' confirmed leak/no-leak outcomes, since both benchmarks above are simulated networks, not real billing meters |

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
| Automated regression test suite | **Done** — see `tests/`. Covers every detection path (MNF, adaptive trough, intermittent leaks, Mann-Kendall, both burst paths, seasonal confounds including Ramadan-specific mechanisms, peer comparison, data handling edge cases). Immediately caught a real bug (`MNF_Applicable` returning `numpy.bool_` instead of Python `bool`) on first run |
| Robustness to messy real-world data | **Not done.** Not tested against: negative readings (meter rollback), DST transitions, duplicate meters per customer, inconsistent units across files, corrupted rows |
| Category-matching robustness | **Not done.** Folder-name substring matching is order-dependent and can misfire on combined keywords (e.g. "Government Villas") — flagged early, never fixed |

## Recommended next priorities, in order

1. **Start the feedback loop now**, even manually — a simple log of
   flagged-customer outcomes is the prerequisite for almost everything in
   the data-blocked list above, and the sooner it starts, the sooner those
   items become buildable.
2. **Close the burst-path seasonal gap** — the one identified, unfixed
   correctness issue remaining from real-data testing.
3. **Harden against real-world data quality issues** before this moves past
   proof-of-concept status into anything resembling production use.

## Explicitly out of scope for this proof-of-concept

This codebase is a validated proof-of-concept for the *detection logic and
architecture*. It has not been hardened against real-world data issues and
should not be deployed as-is against production data, or used for
autonomous (non-human-reviewed) dispatch decisions, without the work listed
above.