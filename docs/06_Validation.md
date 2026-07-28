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

## Type-consistency bug found while building the automated test suite

Writing `tests/test_mnf_and_intermittent.py` and `tests/test_mann_kendall.py`
immediately surfaced a real bug, independent of detection accuracy:
`MNF_Applicable` was being returned as `numpy.bool_` rather than a native
Python `bool`, because `and` short-circuits between a plain bool and a numpy
comparison result without re-casting. This silently broke `json.dumps()`
compatibility and `is True`/`is False` identity comparisons, even though the
underlying logical value was always correct. Fixed by explicitly casting
with `bool(...)` at the point of computation. See `tests/README.md` for
detail — kept here as a reminder that a test suite catches classes of bugs
(type consistency, serialization compatibility) that manual accuracy
validation does not.

## External Benchmark: BATADAL Investigation

This section covers a real, independent test we ran outside our own data.
It also covers a deep investigation into why the result was weaker than
expected, three different fixes we tried, and why none of them were safe
to use. This is one of the most important sections in this document,
because it explains a real limitation of the system and shows the proof
behind that explanation.

### What BATADAL is and why we used it

BATADAL is a public dataset built for testing cyber-attack detection on
water networks. It comes from sensors on tanks, pumps, and valves in a
simulated water distribution system, not from customer water meters. It
was created by researchers, not by us, and it includes labels that say
exactly when a real attack happened. This matters because every other test
in this document uses data we generated ourselves. BATADAL is the first
test using labels we did not create and cannot control.

Two files were used:

| File | What it contains |
|---|---|
| `dataset03.csv` | One full year (Jan 2014 – Jan 2015). Zero attacks the whole year. Used to check how often we wrongly flag a leak when nothing is wrong. |
| `dataset04.csv` | About six months (Jul – Dec 2016). Seven separate attack periods, each lasting 24 to 110 hours. Used to check how often we correctly catch a real problem. |

We mapped one sensor, `F_V2` (a valve flow sensor), into our system as if
it were a customer's hourly water use, and ran the current detection
logic (`analyze_leak_production_grade`, the same function used for real
customers) against it. Category was set to `"Industrial"`, the closest
match to a network-scale flow sensor.

**Important limit to keep in mind while reading this section:** BATADAL is
testing a different kind of problem (a cyber-attack on network equipment)
using a different kind of signal (a network valve) than our real use case
(a leak in a customer's home or business, measured by a billing meter).
A result here tells us something about whether our underlying math
generalizes to a different real-world signal. It does not directly prove
or disprove how well the system works on real customer leaks.

### How we tested it

Our detection function only looks at one time window per file: the most
recent 4 weeks, compared against the 8 weeks before that. To get more than
one single result, we cut each file short at many different points in
time and treated each cut as a separate test. For each cut, we checked
whether a real attack fell inside that cut's own "most recent 4 weeks"
window (using the exact same window definition our code uses), and we
compared that against what our system predicted.

This gave us 18 separate test cases: one for each of the 7 real attack
periods, 3 extra cases in between attacks, and 8 cases spread across the
fully clean year.

The full script used for this test is `batadal_benchmark.py`. Anyone can
run it themselves against the same two files to reproduce these exact
numbers.

### The real results

|  | Predicted YES | Predicted NO |
|---|---|---|
| **Real attack was there** | 1 (True Positive) | 8 (False Negative) |
| **Nothing was actually wrong** | 1 (False Positive) | 8 (True Negative) |

- **Precision: 50%** — of everything we flagged, half was a real attack.
- **Recall: 11%** — of all the real attacks, we only caught 1 out of 9
  positive test cases.
- **F1 score: 0.18** — a low combined score, driven mainly by the low
  recall.
- **False Positive Rate: 11%** — of everything that was actually fine, we
  wrongly flagged about 1 in 9.

Recall of 11% is a real, low number. We did not round it up or soften it.
The rest of this section explains exactly why it is this low, using real
evidence, not guesses.

### Why recall was so low: two separate causes

We did not stop at "the number is low." We opened up individual test
cases and found two different, unrelated reasons for the misses.

**Cause 1: Baseline contamination.**

Our system builds a picture of "normal" behavior from the 8 weeks right
before the 4 weeks we are checking. We call those 8 weeks the *baseline*.
If a real attack happened during those same 8 weeks, our "normal" picture
already includes some of the attack. This can make a real problem later
look smaller than it really is, because the baseline itself is no longer
clean.

We checked this directly. Out of the 6 missed attacks, **5 had an earlier
attack sitting inside their own baseline window**. Only 1 missed attack
(the second one) had a genuinely clean baseline.

**Cause 2: A sensor that behaves nothing like a customer meter.**

We looked closely at the one miss with a clean baseline (attack #2) to
understand why it was still missed. The answer was not about baselines at
all. The sensor we mapped, `F_V2`, sits at exactly `0.00` for **27% of all
hours** in the dataset. It is not a smoothly changing number like a
customer's water use. It behaves like a valve switching fully open or
fully closed, not like a household using more or less water throughout
the day. Our whole detection system is built around the idea that a
customer's water use rises and falls smoothly, with a real quiet period at
night. This sensor does not behave that way at all, so parts of our
system that depend on finding a real "quiet period" struggle with it.

This second finding is a limit of this specific benchmark, not
necessarily a limit of the system for real customers. Every real customer
file we have tested throughout this whole project (see the rest of this
document) shows a continuously changing pattern, not an on/off valve.

### Is baseline contamination a solved problem in the industry?

We searched for this specifically before trying to fix it ourselves. Short
answer: **no, it is not a solved problem.** It is a real, actively
studied topic, with a specific name in research papers: *training data
contamination* or *anomaly contamination* in time series anomaly
detection.

A few things we found, in plain terms:

- Multiple recent research papers exist specifically about this problem
  (for example: RSM-GAN, RiAD, and robust deep state-space models). The
  fact that many separate research teams are still actively publishing
  new attempts tells us this is not something with one standard, agreed
  fix.
- One paper (on a method called RSM-GAN) found that ordinary, simple
  detection methods, when the training data is contaminated, tend to
  reach 100% recall (catching everything) but only by paying for it with
  a false positive rate as high as 26.4%. That is a named, recognized
  trap in this field: catching more real problems by accidentally
  flagging almost everything.
- There is a well-known, real industry technique called **RobustSTL**
  (Robust Seasonal-Trend decomposition), used at companies like Yahoo, that
  is specifically designed to resist outliers when splitting a signal into
  its normal daily pattern and its irregular parts. It is a real,
  respected, widely used method. But a 2025 research paper studying this
  exact question found that RobustSTL, and even the earlier plain version
  (STL), still struggle specifically with what researchers call a
  *collective anomaly* — a problem that lasts for a stretch of time (hours
  or days), rather than a single bad reading. The paper shows that this
  kind of sustained problem gets absorbed directly into what the method
  thinks is "normal," which then makes it harder, not easier, to catch.

This last point matters a lot for us. A BATADAL attack is not one bad
reading. It lasts 24 to 110 hours. That is exactly the kind of "collective
anomaly" that even a well-established, widely used robust method is
documented to struggle with.

### Three fixes we tried, and why each one failed

We did not stop at finding the two causes above. We tried to fix the
contamination problem three separate times. Every attempt was tested with
real numbers before being accepted or rejected, the same way every other
part of this system has been tested throughout this project.

**Attempt 1: Trim outliers out of the baseline before using it.**

*The idea:* for each hour-of-week, look at the 8 baseline readings for
that slot, and throw out any reading that is unusually far from the
typical value for that slot, before computing the "normal" number. This
uses a common robust statistics trick called MAD (median absolute
deviation) — a way of measuring how spread out normal values are, that is
less thrown off by outliers than a plain standard deviation.

*What happened:* we tested this end-to-end against all 7 real attacks and
all 8 clean-year checkpoints.
- Recall jumped from 1/7 to 7/7 attacks caught.
- But the false positive rate on the fully clean year jumped from 0/8 to
  **7/8** — a 0% to 87.5% jump.

*Why it failed:* the trimming step could not tell the difference between
"this reading is part of a real attack" and "this reading is the valve's
completely normal closed state." Because the valve is closed roughly a
quarter of the time, the trimming step kept throwing out those normal
closed readings, thinking they were outliers. This pushed the "normal"
baseline number artificially higher across the board, which then made
almost everything, attack or not, look unusually high by comparison. This
is the same 100%-recall-at-the-cost-of-huge-false-positives trap the
research papers above describe.

*Decision:* rejected. Not used anywhere in the real system.

**Attempt 2: Detect contamination without trying to fix it — compare the
first half of the baseline to the second half.**

*The idea:* instead of trying to correct the baseline, just warn a person
when it looks suspicious. Split the 8-week baseline into two 4-week
halves, and compare their overall typical value. If they are very
different, flag it as a possible sign that something real happened partway
through the baseline period.

*What happened:* we tested this on the same 7 attacks and 8 clean-year
checkpoints.
- The difference between the two halves was small (under 5%) in every
  single case, attack or clean.
- The flag never fired at all, on anything.

*Why it failed:* the valve's on/off pattern is so dominant (0.00 a
quarter of the time) that it swamps the overall typical value regardless
of whether an attack happened. A single overall number for a 4-week block
is too blunt an instrument for this kind of signal.

*Decision:* rejected. Too insensitive to be useful.

**Attempt 3: Same idea as Attempt 2, but compare each hour-of-week slot
separately instead of one overall number.**

*The idea:* rather than one number per half, compare each of the 168
hour-of-week slots (24 hours × 7 days) between the first and second half
of the baseline, and count how many slots shifted by a meaningful amount.

*What happened:* we tested this on BATADAL first, then again on synthetic
data shaped like a real, normal customer (smooth daily pattern, real
night-time quiet period), to make sure a bad result on BATADAL's unusual
valve signal was not the only reason it failed.
- On BATADAL: it fired on almost everything, including 8 out of 8 fully
  clean checkpoints in the clean year.
- On realistic customer-shaped synthetic data: at every sensitivity
  setting we tried, a deliberately contaminated baseline produced a number
  that fell inside the normal range produced by genuinely clean
  baselines. There was no setting where contaminated and clean cases were
  reliably different from each other.

*Why it failed:* with only 8 weeks of baseline data, each hour-of-week
slot only has about 4 samples in each half. Ordinary week-to-week
randomness is already about as large as the shift a real event causes.
There simply is not enough data in a single slot to tell the difference
between "this shifted because something real happened" and "this shifted
because of normal week-to-week noise."

*Decision:* rejected. Not reliable on either signal type we tested it
against.

### Methods we did not build or test, but literature tells us about

Two further approaches exist in published research that we did **not**
attempt to build, because they need things we do not currently have.
Listing them here is important so nobody re-invents the same wheel later
without knowing this context.

- **Changepoint detection** (for example, algorithms called PELT and
  BOCPD). Instead of comparing two fixed halves like our Attempt 2 and 3,
  these methods search the whole baseline period for the exact point
  where behavior genuinely shifted, using proper statistical tests built
  for this purpose, not a simple comparison. This is a more principled
  approach than anything we tried, and it remains a real, promising future
  option. We have not built or tested it yet. Based on what the same 2025
  research paper says, even purpose-built changepoint methods still find
  this kind of sustained, multi-hour problem harder than a single bad
  reading — so it is a promising direction, not a guaranteed fix.
- **Machine learning models trained specifically to be resistant to
  contaminated data** (for example, methods named RSM-GAN and RiAD in the
  research we found). These are reported in published papers to
  meaningfully outperform simple statistical methods under contamination.
  But they need a real training dataset with many examples, and
  supporting infrastructure to build, train, and validate them properly.
  This is exactly the kind of thing that becomes possible once more
  customer data and confirmed outcomes (real, confirmed leaks and real,
  confirmed non-leaks) have been collected. It is listed as a future work
  item, not something we can respons­ibly build today.

### Why the current system is the best we can do right now

Putting all of the above together, our current approach — comparing
recent behavior to a fixed 8-week history, with no attempt to automatically
detect or correct for contamination inside that baseline — is the right
choice today, for three specific, evidenced reasons:

**(a) Every simple fix we tried made things worse, not better.** This is
not a guess. We built and tested three different approaches, and every
one of them either failed to catch real problems, or caught more problems
only by wrongly flagging far more clean cases. Shipping any of them would
have made the system less trustworthy, not more.

**(b) The two more promising alternatives both need something we do not
yet have.** Changepoint detection is a more careful, principled idea
worth building later, but it has not been built or tested yet, and even
published, purpose-built versions of it are documented to struggle with
the same kind of sustained problem we are dealing with. Machine
learning-based fixes need real training data and confirmed outcomes,
which do not exist yet for this project.

**(c) This is a genuinely open problem across the wider field, not
something unique to us.** Multiple active, ongoing research papers — some
as recent as 2025 — are still being published about exactly this problem,
and they confirm that even industry-standard, widely used methods (like
RobustSTL) have real, documented weaknesses against the exact kind of
sustained, multi-hour problem this project needs to detect. If well-funded
research teams and established methods have not fully solved this yet,
it is reasonable that a project at this stage, with the data available
today, has not solved it either.

Given (a), (b), and (c) together, the honest, responsible choice is to
keep the current logic as-is, be upfront about this specific limitation
in this document, and treat a real fix as future work that depends on
either more sophisticated engineering (changepoint detection, properly
tested) or more data (enough confirmed outcomes to train and validate a
machine learning approach). Both paths are listed in
`08_Future_Work.md`.

## Known validation gaps

- ~~No automated regression test suite exists yet.~~ **Closed** — see
  `tests/`. All 24 tests pass against the current source.
- No validation against real, confirmed customer leak/no-leak outcomes.
  The BATADAL benchmark above is real, independently-labeled data, but from
  a different domain (network cyber-attacks, not customer billing meters) —
  see the domain-mismatch caveat in that section.
- No validation against real-world data quality issues (negative readings,
  DST transitions, duplicate meters, inconsistent units).
- Baseline contamination remains unsolved. Three fix attempts were tried
  and rejected (see the BATADAL section above); a real fix needs either
  changepoint detection (untested, promising, not yet built) or a
  machine-learning approach (needs training data we don't have yet).