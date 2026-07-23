# Validation

## Important caveat, upfront

**All numbers in this document come from synthetic data**, generated to
exercise specific detection paths under controlled conditions. None of it is
validated against confirmed real-world leak/no-leak outcomes, because no
labeled outcome data exists yet. Treat these as evidence the *statistical
mechanics* behave sensibly, not as production accuracy guarantees. See
`08_Future_Work.md` for what closing this gap requires.

One real-data event is included below (the Ramadan mass-flagging incident)
because it's the one case where synthetic testing's blind spot was caught
by an actual customer file — which is itself a useful data point about the
limits of synthetic-only validation.

## Mann-Kendall trend detection

The slow-leak fallback for accounts with no reliable night trough went
through two iterations before landing on the current design.

**Iteration 1 — CUSUM control chart (superseded, not in current code):**
- Initial version: 14/30 false positives (47%) on clean synthetic 24/7
  accounts, traced to a coverage-check bug (boundary-truncated days at the
  evaluation-window edge were trivially passing a completeness check).
- After fixing the coverage bug: 8/30 (27%) — still too high, traced to the
  standard `h=4σ` CUSUM decision interval being too sensitive for a ~28-day
  evaluation window.
- Widened to `h=5σ`: 3/40 (7.5%) false positives, 40/40 (100%) true
  positives on a +2.5%-sustained synthetic leak.
- **Replaced entirely** with Mann-Kendall because 7.5% was still judged too
  high, and CUSUM's threshold is an approximated control limit that has to
  be empirically re-tuned, rather than a method with a real, controllable
  false-alarm rate.

**Iteration 2 — Mann-Kendall (current):**
- At `α = 0.01`: 0/40 false positives, but true-positive rate on a
  +2.5%-sustained leak dropped to 32/40 (80%), and to 26/40 (65%) on a
  smaller +1%-sustained leak.
- At `α = 0.05`, with the effect-size gate (`sen_slope * n_days >
  night_drift_abs_floor`) doing most of the false-positive suppression: 0/40
  false positives, 39/40 (97.5%) true positives on the same +2.5% leak.
- **Final confirmation on a fresh, independent seed batch** (not the same
  data used to tune α): 0/50 false positives, 48/50 (96%) true positives.

**Conclusion:** `α = 0.05` with the effect-size gate is the current setting.
The two remaining misses in the final 50-trial batch were both marginal
cases (p-value just above the 0.05 cutoff), not a systematic failure.

## Cumulative / fluctuating burst detection (Option 7)

**This is the one detection path that was shipped without upfront
validation**, and it's worth documenting honestly because of what that
caused.

- The original version (soft threshold at `0.5×z_threshold`, cumulative
  volume bar at `2.5×burst_vol_threshold`, triggered by a single occurrence
  anywhere in ~28 days) was added by reasoning alone, without the
  false-positive testing every other path received.
- It was later found to falsely flag a real customer file whose night floor
  was *literally unchanged* (0.000 m³ → 0.000 m³) — the false positive came
  entirely from ordinary daytime variation crossing a loose threshold once.
- Retuned: soft threshold raised to `0.75×z_threshold`, cumulative bar
  raised to `4.0×burst_vol_threshold`, and a persistence requirement added
  (must recur on **≥3 separate calendar days**, not one lucky window).
- **After retuning:** 0/100 false positives across all four categories (25
  trials each) on clean synthetic data.
- **True positive check:** a genuinely recurring fluctuating burst (21
  separate days, high-low-high-low pattern that never holds strictly
  consecutive) — still correctly caught.
- **Negative control:** the same fluctuating pattern occurring on a single
  one-off day — correctly returns `NO`.

**Lesson captured in `07_Design_Decisions.md`:** every new detection path
now requires the same false-positive/true-positive test before shipping,
regardless of how intuitively obvious the logic seems.

## Seasonal confound handling (real-data validation)

**The incident:** a full run against real Commercial customer files
returned `Leak_Suspected: YES` for nearly the entire category. Investigation
found the recent 4-week evaluation window for every file overlapped
Ramadan/Eid al-Fitr 2026 (Feb 18 – Mar 19/20).

**Root cause:** every detection path shares the same underlying assumption —
recent-vs-own-history comparison — which silently breaks when a shared,
real-world cause (not an individual leak) raises many customers' usage at
once. This is a structural limitation, not a bug in any single path.

**Fix and its own validation:**
- Ramadan-affected Residential test (suhoor bump at a single specific hour,
  no real leak): correctly returns `NO` after shifting the night-hours
  window — under the prior logic this would very likely have been a false
  positive.
- Ramadan-affected Commercial test (legitimate extended overnight hours, no
  real leak): MNF correctly bypassed (`MNF_Applicable: False`), Mann-Kendall
  correctly stayed just under significance (`p=0.055`) with no real trend
  present.
- **Known remaining gap:** the burst-detection paths were not routed through
  the same seasonal logic and can still fire during a Ramadan-affected
  extended-hours pattern. This does not cause an incorrect auto-escalation
  (the tier cap still applies), but the flag and its wording can be
  misleading in that specific scenario. Not yet fixed — see
  `08_Future_Work.md`.

## Peer / cohort comparison

Tested with a synthetic Commercial cohort (7 files): 5 customers sharing an
ordinary ~19% demand rise (simulating an unhardcoded shared cause) plus 1
customer with the same shared rise *and* a real additional leak on top.

- The 5 shared-cause customers: correctly capped at low/medium tiers with a
  "consistent with cohort" note, without their underlying score or evidence
  being erased.
- The outlier: correctly identified (`peer_z = 9.5`), boosted
  (+15 points), reaching `Priority_Score: 90, High - Dispatch` — confirming
  a real leak riding on top of a shared cause is *amplified*, not diluted,
  which was the specific design flaw corrected before implementation (see
  `07_Design_Decisions.md`).
- Small cohort (3 files, below the minimum of 5): peer comparison correctly
  skipped entirely; the one genuine leak in that test was left untouched.
- Fully clean cohort (6 files, no leaks): peer comparison correctly
  inert — nothing to adjust.

## Known validation gaps

- No automated regression test suite exists yet. All validation above was
  run manually and is not re-checked automatically when the code changes.
- No validation against real, confirmed leak/no-leak outcomes.
- No validation against real-world data quality issues (negative readings,
  DST transitions, duplicate meters, inconsistent units).