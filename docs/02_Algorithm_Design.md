# Algorithm Design

This document describes every detection path in detail: what it measures, how
its thresholds are derived, and what failure mode it exists to catch.

## Category configuration

Thresholds are set per customer category (matched by keywords in the folder
name: `Residential`/`Villa`/`Flat`, `Government`, `Industrial`, else
`Commercial`/`Hotels`):

| Category | Night hours | Night drift multiplier | Night drift abs. floor (m³) | z-threshold | Consecutive hours | Burst volume threshold (m³) |
|---|---|---|---|---|---|---|
| Residential/Villa/Flat | 1–4 | 1.6x | 0.020 | 4.0 | 4 | 0.150 |
| Government | 0,1,5,6 | 1.5x | 0.100 | 4.5 | 6 | 0.800 |
| Industrial | 2–4 | 1.4x | 0.180 | 5.0 | 6 | 1.500 |
| Commercial/Hotel | 2–4 | 1.5x | 0.090 | 4.0 | 4 | 0.500 |

`std_floor_pct = 0.15` for all categories (see Statistical Deviation below).
These are hand-set starting points, not fitted values — see
`07_Design_Decisions.md` and `08_Future_Work.md` for why.

## Data preparation

1. **Header auto-detection** — scans the first 10 rows for the row that
   literally contains both `Hourly` and `Consumption m3` as values, so files
   with extra title/metadata rows above the real header still parse correctly.
2. **Reindex to a complete hourly grid** — from the file's min to max
   timestamp. Missing hours become explicit `NaN` rows rather than silently
   not existing, so every later rolling-window/consecutive-hour check
   operates on true wall-clock time, not row count.
3. **Timeline split** — most recent 4 weeks = `Recent_Evaluation`; the 8 weeks
   before that = `Historical_Baseline`. Files with less than 4 weeks of
   history before the evaluation window are `SKIPPED` outright.

## Statistical deviation measurement

For every `(day_of_week, hour)` cell:
- `baseline_median` — median consumption for that hour-of-week slot across
  the 8-week baseline
- `baseline_std` — that slot's own historical standard deviation

```
abs_deviation = actual_consumption - baseline_median
group_std_floor = max(0.010, baseline_median * 0.15)
z_score = abs_deviation / (baseline_std + group_std_floor)
```

The floor is scaled to each cell's *own* median rather than one global
number — without it, near-zero-variance night cells would produce
wildly inflated z-scores from trivial absolute changes.

Missing readings are kept as `NaN` through this calculation, not
zero-filled — a dead meter must not look identical to confirmed-normal usage.

## Path A: Slow leak detection (Minimum Night Flow)

**Mechanism:** a real leak runs 24 hours a day, including the quietest hour.
If the minimum night-time flow has structurally risen, that's a stronger
signal than total usage rising, because normal daytime demand shouldn't
touch the night floor at all.

**Attempt 1 — fixed category night hours.** Computes:
- `historical_min_flow` = 5th percentile of baseline night-hour readings
- `highest_observed_floor` = max of rolling 7-calendar-day minimums in the
  recent window (a leak signature is a floor that stays elevated across a
  whole week, not one low-coverage day)
- `night_trough_ratio = historical_min_flow / baseline_all_median` — if this
  exceeds **0.55**, there's no real quiet period for this account (e.g. a
  24/7 operation), and MNF is not applicable.

**Attempt 2 — adaptive trough discovery.** If the fixed hours show no real
trough, the account's own lowest-usage hours (from its own baseline data,
not the category assumption) are used instead, and the same computation is
re-run on those hours. Rescues accounts whose real quiet period doesn't
match their category's default (e.g. a single-shift industrial site).

**Leak decision (fixed or adaptive):**
```
night_drift_threshold = max(night_drift_abs_floor, historical_min_flow * (multiplier - 1))
elevated_threshold = historical_min_flow + night_drift_threshold
LEAK if highest_observed_floor > elevated_threshold AND highest_observed_floor > 0.02
```

**Intermittent / duty-cycled leak (fallback within Path A):** if the
continuous check doesn't fire but at least 10 clean nights exist, counts how
many individual nights crossed `elevated_threshold`. If **≥60%** of nights
were elevated, flags an intermittent leak — catches a leak that cycles on
and off, which would otherwise pull the rolling 7-day minimum back down and
mask itself.

## Path B: Slow trend detection (Mann-Kendall)

Used only when **no** trough exists (fixed or adaptive) — i.e. a genuinely
continuous account (24/7 operation, or Commercial/Hotel during Ramadan; see
`Seasonal Confound Handling` below).

- Nonparametric one-sided trend test on the daily-averaged deseasonalized
  residual (`abs_deviation`), requiring ≥14 clean recent days.
- Returns a real p-value (`p_one_sided`) and Sen's slope (robust,
  outlier-resistant estimate of daily drift rate).
- **Dual gate:** flags only if `p_one_sided < 0.05` (statistical
  significance) **and** `sen_slope * n_days > night_drift_abs_floor`
  (a minimum real volume increase — statistical significance alone isn't
  enough if the trend is trivially small).
- Chosen over a CUSUM control chart because it makes no Gaussian assumption
  and its false-alarm rate is controlled directly by α rather than an
  empirically-tuned control limit. See `07_Design_Decisions.md`.

## Path C: Burst detection

**Strict consecutive-hours check:** flags if `z_score > z_threshold` AND
`abs_deviation > burst_vol_threshold` hold for `consecutive_hours` *truly
consecutive* hours (time-based rolling window, so a data gap cannot count as
consecutive).

**Cumulative / fluctuating burst check** (only runs if the strict check
doesn't fire): catches bursts that dip below the strict threshold for a
stray hour (pressure noise, partial blockage) instead of holding perfectly
steady.
```
soft_z_threshold = z_threshold * 0.75
cumulative_excess_threshold = burst_vol_threshold * 4.0
```
Sums positive excess volume (hours above `soft_z_threshold`) over a rolling
6-hour window, and requires the threshold to be exceeded on **at least 3
separate calendar days** — not a single lucky/unlucky window. This
persistence requirement was added after testing showed the original
single-occurrence version produced false positives on genuinely clean data.
See `06_Validation.md`.

## Path D: Residential Consumption Profile Check (informational, not a detection path)

Added after the database/dashboard layer was built (see
`09_Database_and_Dashboard.md`) — this is a simpler, independent signal
for Residential/Flat/Villa customers, **deliberately not wired into
`Leak_Suspected` or `Priority_Score`**. It exists to give investigators
extra context on the Investigation dashboard, not to trigger a flag on
its own.

```
RESIDENTIAL_PROFILE_THRESHOLDS = {"Residential": 0.005, "Flat": 0.005, "Villa": 0.0075}  # m3/hour
PROFILE_CHECK_DAYS = 5
```

For the last 5 complete calendar days, checks whether that day's minimum
hourly consumption stayed above the category threshold. If true for all 5
days, flags `Abnormal Consumption`; if the minimum dropped below
threshold on at least one day, `Normal Consumption`; if fewer than 5
complete days exist, `Insufficient Data`.

This is conceptually adjacent to Minimum Night Flow (a household that
never goes quiet), but uses a fixed absolute threshold rather than a
comparison against that customer's own historical baseline, which is why
it's kept as a separate, simpler signal rather than merged into Path A.
Whether this should eventually feed into the leak verdict is an open
question, not yet decided — see `09_Database_and_Dashboard.md`.

## Seasonal confound handling

A rule-based (not learned) calendar lookup of known regional high-variance
periods (Ramadan/Eid al-Fitr, Eid al-Adha, UAE National Day, New Year,
summer school holidays). If the recent evaluation window overlaps one:

- A note is attached to `Details` and the priority tier is capped below
  "High - Dispatch" (evidence stays visible, just not auto-escalated).

**Ramadan gets a deeper, mechanism-specific fix**, because it's the one
confound that shifts *when* customers are active into hours normally
treated as quiet (not just how much they use overall):
- **Residential/Villa/Flat:** night-hours window shifts to `[4,5,6]` to
  route around suhoor (the pre-dawn meal, typically ~3–5am).
- **Commercial/Hotel:** MNF is skipped entirely for the evaluation (treated
  the same as a permanently-24/7 account) and falls through to Mann-Kendall,
  since extended iftar/suhoor service can mean the business is legitimately
  active overnight for the whole month.

Other confounds (Eid al-Adha, National Day, summer, New Year) only get the
shallow flag-and-cap treatment, since they raise general daytime demand
without the same night-shifting mechanism.

## Priority scoring and explainability

Each fired detection path carries a point value:

| Signal | Points |
|---|---|
| Slow Constant Leak (MNF) | 35 |
| Intermittent Slow Leak | 25 |
| Slow Trend Leak (Mann-Kendall, p<0.01) | 35 |
| Slow Trend Leak (Mann-Kendall, p<0.05) | 25 |
| Sudden Pipe Burst (strict) | 40 |
| Intermittent/Fluctuating Burst | 30 |

```
raw_score = min(100, sum of fired reason points)
completeness_factor = 1.0, or max(data_completeness_recent, 0.3) if < 80% complete
priority_score = round(raw_score * completeness_factor)
```

Tiers: `>=70` High - Dispatch, `>=40` Medium - Monitor, `>0` Low - Review
Only, `0` None. **Not a calibrated probability** — there is no labeled
outcome data yet to validate a percentage against. It is an additive
suspicion score for triage/ranking only. See `07_Design_Decisions.md`.

## Peer / cohort comparison

A second-pass, portfolio-level check (see `01_System_Architecture.md`):
compares each already-flagged customer's overall demand change
(`Recent_Vs_Baseline_Pct_Change`) against the median of their category peers
in the same run, using a robust z-score:

```
peer_z = (customer_pct_change - cohort_median) / max(cohort_MAD * 1.4826, 0.05)
```

- `peer_z >= 2.0` → boosts score (+15, capped at 100), overrides seasonal cap
- `peer_z <= 0.5` → caps tier only (never touches score/reasons)
- Cohort size `< 5` → skipped entirely

This generalizes protection to *any* shared cause across a category, known
or unknown — not just the hardcoded Ramadan/Eid dates.