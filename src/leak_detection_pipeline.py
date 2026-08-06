import os
import math
import pandas as pd
import numpy as np
import tempfile
import os

# --- KNOWN REGIONAL HIGH-VARIANCE CALENDAR PERIODS ---
# Rule-based (declarative) seasonality: unlike statistically-learned seasonality
# (which needs 1yr+ of history per customer to know "what does March normally
# look like" -- data we don't have yet), this just encodes KNOWN facts about the
# calendar and flags when an evaluation window overlaps one. Buildable today with
# zero additional data. Islamic holidays are lunar and shift ~11 days/year, so
# they're hardcoded per-year (with a few days of buffer for moon-sighting
# uncertainty) rather than computed from a rule. Extend this list as more years
# of data become available or if other known regional demand-shifting events
# (e.g. Dubai Shopping Festival, major public holidays) turn out to matter.
_FIXED_YEAR_CONFOUND_PERIODS = [
    # (name, start_date, end_date) -- approximate, includes moon-sighting buffer
    ("Ramadan/Eid al-Fitr 2025", "2025-02-26", "2025-04-02"),
    ("Eid al-Adha 2025", "2025-06-04", "2025-06-11"),
    ("Ramadan/Eid al-Fitr 2026", "2026-02-16", "2026-03-24"),
    ("Eid al-Adha 2026", "2026-05-24", "2026-06-01"),
    ("Ramadan/Eid al-Fitr 2027", "2027-02-04", "2027-03-14"),
]


def _get_confound_periods(years):
    """
    Returns a list of (name, start_timestamp, end_timestamp) for known regional
    high-variance calendar periods relevant to the given years. Combines the
    hardcoded lunar Islamic holidays above with fixed-date Gregorian periods
    (New Year, UAE National Day, summer school holidays) generated for each year.
    """
    periods = [
        (name, pd.Timestamp(start), pd.Timestamp(end))
        for name, start, end in _FIXED_YEAR_CONFOUND_PERIODS
    ]
    for year in years:
        periods.append((f"New Year {year}", pd.Timestamp(f"{year}-12-28"), pd.Timestamp(f"{year + 1}-01-04")))
        periods.append((f"UAE National Day {year}", pd.Timestamp(f"{year}-11-30"), pd.Timestamp(f"{year}-12-04")))
        periods.append((f"Summer School Holidays {year}", pd.Timestamp(f"{year}-06-15"), pd.Timestamp(f"{year}-08-31")))
    return periods


def _find_confound_overlaps(window_start, window_end):
    """
    Given an evaluation window, returns the names of any known calendar confound
    periods it overlaps. Checks both the window's own year and the year before/
    after to safely catch windows that straddle a year boundary.
    """
    years_to_check = sorted({window_start.year - 1, window_start.year, window_end.year, window_end.year + 1})
    overlaps = []
    for name, period_start, period_end in _get_confound_periods(years_to_check):
        if window_start <= period_end and window_end >= period_start:
            overlaps.append(name)
    return overlaps


def _mann_kendall_trend(values):
    """
    One-sided Mann-Kendall trend test (testing specifically for an INCREASING
    trend, since a leak only ever adds volume) plus Sen's slope estimator.

    Nonparametric: makes no assumption about the residuals being Gaussian --
    only about their relative ordering -- which is what makes it a better fit
    here than a parametric method like CUSUM on a short, possibly non-Gaussian
    daily series. Returns None if there isn't enough data (n < 5).

    Returns dict with:
      n           - number of points used
      s_stat      - the raw Mann-Kendall S statistic
      z           - standardized z-score
      p_one_sided - one-sided p-value (probability of this much or more
                    apparent increase happening by chance if there's truly no trend)
      sen_slope   - Sen's slope: median of all pairwise slopes (x_j-x_i)/(j-i),
                    a robust (outlier-resistant) estimate of the per-day drift rate
    """
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < 5:
        return None

    s_stat = 0.0
    slopes = []
    for i in range(n - 1):
        diffs = x[i + 1:] - x[i]
        s_stat += np.sum(np.sign(diffs))
        gaps = np.arange(i + 1, n) - i
        slopes.extend((diffs / gaps).tolist())

    _, tie_counts = np.unique(x, return_counts=True)
    tie_term = np.sum(tie_counts * (tie_counts - 1) * (2 * tie_counts + 5))
    var_s = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0

    if var_s <= 0:
        return None

    if s_stat > 0:
        z = (s_stat - 1) / math.sqrt(var_s)
    elif s_stat < 0:
        z = (s_stat + 1) / math.sqrt(var_s)
    else:
        z = 0.0

    p_one_sided = 1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))
    sen_slope = float(np.median(slopes))

    return {
        "n": n,
        "s_stat": float(s_stat),
        "z": float(z),
        "p_one_sided": float(p_one_sided),
        "sen_slope": sen_slope,
    }


def _detect_header_row(file_path, time_col, consumption_col, max_scan_rows=10):
    """
    Scans the first `max_scan_rows` rows of the file (with no header assumed) and
    returns the index of the first row that actually contains both `time_col` and
    `consumption_col` as literal cell values. This handles files that have extra
    title/metadata rows above the real column headers (a common export quirk),
    without needing a fixed header=N assumption that only works for some files.
    Falls back to row 0 if nothing matches, so behavior is unchanged for files
    that already have a clean header on the first row.
    """
    try:
        if file_path.endswith('.csv'):
            preview = pd.read_csv(file_path, header=None, nrows=max_scan_rows)
        else:
            preview = pd.read_excel(file_path, header=None, nrows=max_scan_rows)
    except Exception:
        return 0

    for i in range(len(preview)):
        row_vals = preview.iloc[i].astype(str).str.strip().tolist()
        if time_col in row_vals and consumption_col in row_vals:
            return i
    return 0


def _compute_night_floor(baseline_data, df, recent_mask, night_hours, time_col, consumption_col):
    """
    Shared Minimum Night Flow computation: given a set of "trough hours" (whether
    fixed by category or discovered adaptively), returns:
      - historical_min_flow: 5th percentile of baseline readings in those hours
      - highest_observed_floor: max of rolling 7-calendar-day minimums in the
        recent window (a leak signature is a floor that stays elevated across a
        whole week, not just one low-coverage day)
      - evaluated: whether enough clean data existed to trust the result
      - daily_min_series: the clean (coverage-checked) per-day minimum night flow
        series itself -- returned so the caller can reuse it for intermittency
        detection (a duty-cycled leak: elevated on many but not all nights)
        without recomputing the same groupby/coverage-filter work twice.

    Used identically for the fixed category night_hours and for the adaptive,
    data-driven trough hours (Option 1), so both attempts get the exact same
    gap-aware, coverage-checked treatment.
    """
    hist_night = baseline_data[baseline_data['hour'].isin(night_hours)]
    historical_min_flow = hist_night[consumption_col].quantile(0.05) if not hist_night.empty else np.nan

    recent_night_mask = recent_mask & df['hour'].isin(night_hours)
    recent_night = df[recent_night_mask].copy()
    highest_observed_floor = np.nan
    evaluated = False
    daily_min_series = pd.Series(dtype=float)

    if not recent_night.empty and pd.notna(historical_min_flow):
        recent_night['date'] = recent_night[time_col].dt.floor('D')
        day_group = recent_night.groupby('date')[consumption_col]
        daily_min = day_group.min()
        # Coverage must be measured against the TRUE expected count (len(night_hours)),
        # not against however many rows happen to already be in that day's group --
        # a day truncated by the recent-window boundary (e.g. only 1 of 4 night hours
        # actually falls after the cutoff) would otherwise trivially show 100%
        # "coverage" of itself and pass, producing a wildly unrepresentative daily min.
        expected_per_day = len(night_hours)
        daily_coverage = day_group.apply(lambda s: s.notna().sum() / expected_per_day)
        daily_min = daily_min[daily_coverage >= 0.75]
        daily_min_series = daily_min.sort_index()

        if not daily_min.empty:
            daily_min = daily_min.sort_index()
            rolling_week_min = daily_min.rolling('7D', min_periods=5).min()
            if rolling_week_min.notna().any():
                highest_observed_floor = rolling_week_min.max()
                evaluated = True

    return historical_min_flow, highest_observed_floor, evaluated, daily_min_series


def analyze_leak_production_grade(
    consumption_df,
    folder_type
):
    """
    Wrapper used by the SQLite pipeline.

    Converts a dataframe into the same temporary Excel format
    expected by the validated leak detection engine.
    """

    df = consumption_df.copy()

    df = df.rename(
        columns={
            "Timestamp": "Hourly",
            "ConsumptionM3": "Consumption m3"
        }
    )

    with tempfile.NamedTemporaryFile(
        suffix=".xlsx",
        delete=False
    ) as tmp:

        temp_path = tmp.name

    df.to_excel(
        temp_path,
        index=False
    )

    try:

        results = _analyze_leak_production_grade(
            file_path=temp_path,
            folder_type=folder_type
        )

    finally:

        if os.path.exists(temp_path):
            os.remove(temp_path)

    return results


def _analyze_leak_production_grade(file_path, folder_type, time_col='Hourly', consumption_col='Consumption m3'):
    """
    High-fidelity water leak detection engine.

    v3 changes vs prior version:
      1. Std floor for z-scores is computed per (day_of_week, hour) group instead of
         one global scalar -> night hours (naturally low variance) aren't drowned out
         by daytime variance when picking the floor.
      2. Night-leak drift threshold scales to each customer's OWN historical night
         floor (category gives a multiplier + absolute backstop, not one fixed m3
         value for every customer in that category).
      3. Data is reindexed onto a complete expected hourly grid before any rolling
         logic, so "7 days" / "N consecutive hours" are true wall-clock windows and
         not just "N rows", which previously could be silently wrong across data gaps.
      4. Data completeness is measured explicitly (recent window + night hours) and
         returned in the output, and an `MNF_Evaluated` flag distinguishes
         "confirmed normal" from "could not evaluate reliably due to missing data".
    """
    try:
        # --- 1. DATA INGESTION & ROBUST HYGIENE ---
        header_row = _detect_header_row(file_path, time_col, consumption_col)
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, header=header_row)
        else:
            df = pd.read_excel(file_path, header=header_row)

        df[time_col] = pd.to_datetime(df[time_col])
        df = df.sort_values(time_col).drop_duplicates(subset=[time_col]).reset_index(drop=True)

        # --- 2. REINDEX TO A COMPLETE HOURLY GRID (gap-safety for all rolling logic) ---
        full_index = pd.date_range(df[time_col].min(), df[time_col].max(), freq='h')
        df = df.set_index(time_col).reindex(full_index)
        df.index.name = time_col
        df = df.reset_index()
        # consumption_col is now NaN wherever a reading was missing -- this is intentional
        # and tracked, rather than silently treated as "normal" later on.

        df['hour'] = df[time_col].dt.hour
        df['day_of_week'] = df[time_col].dt.dayofweek

        # --- 3. DYNAMIC OPERATIONAL CONFIGURATIONS ---
        # night_drift_multiplier: recent floor must exceed historical floor by this
        # multiple before being flagged. night_drift_abs_floor: backstop so tiny
        # historical floors (near-zero) still require a minimum real volume increase.
        if any(kw in folder_type for kw in ["Residential", "Villa", "Flat"]):
            night_hours = [1, 2, 3, 4]
            night_drift_multiplier = 1.6
            night_drift_abs_floor = 0.020
            z_threshold = 4.0
            consecutive_hours = 4
            burst_vol_threshold = 0.150
            std_floor_pct = 0.15

        elif "Government" in folder_type:
            night_hours = [0, 1, 5, 6]
            night_drift_multiplier = 1.5
            night_drift_abs_floor = 0.100
            z_threshold = 4.5
            consecutive_hours = 6
            burst_vol_threshold = 0.800
            std_floor_pct = 0.15

        elif "Industrial" in folder_type:
            night_hours = [2, 3, 4]
            night_drift_multiplier = 1.4
            night_drift_abs_floor = 0.180
            z_threshold = 5.0
            consecutive_hours = 6
            burst_vol_threshold = 1.500
            std_floor_pct = 0.15

        else:  # Commercial / Hotels
            night_hours = [2, 3, 4]
            night_drift_multiplier = 1.5
            night_drift_abs_floor = 0.090
            z_threshold = 4.0
            consecutive_hours = 4
            burst_vol_threshold = 0.500
            std_floor_pct = 0.15

        # --- 4. TIMELINE SEGREGATION & SANITY CHECKS ---
        max_date = df[time_col].max()
        four_weeks_ago = max_date - pd.Timedelta(weeks=4)
        eight_weeks_prior = four_weeks_ago - pd.Timedelta(weeks=8)

        min_date = df[time_col].min()
        if min_date >= four_weeks_ago:
            return {
                "Status": "SKIPPED",
                "Leak_Suspected": "NO",
                "Priority_Score": 0,
                "Priority_Tier": "None",
                "Priority_Reasons": "Not evaluated (insufficient historical data).",
                "Details": "Insufficient historical data footprint to map normal behavior profiles safely.",
                "Seasonal_Confound_Recent": None,
                "Seasonal_Confound_Baseline": None,
                "Recent_Vs_Baseline_Pct_Change": None,
                "MNF_Applicable": None,
                "Trough_Detection_Method": None,
                "Night_Trough_Ratio": None,
                "MNF_Evaluated": False,
                "Nights_Elevated": None,
                "Nights_Checked": None,
                "MK_Evaluated": False,
                "MK_P_Value": None,
                "MK_Sen_Slope": None,
                "Cumulative_Burst_Max_Excess_m3": None,
                "Data_Completeness_Recent": None,
                "Data_Completeness_Night": None,
            }

        df['period'] = 'Ignore'
        df.loc[(df[time_col] >= eight_weeks_prior) & (df[time_col] < four_weeks_ago), 'period'] = 'Historical_Baseline'
        df.loc[df[time_col] >= four_weeks_ago, 'period'] = 'Recent_Evaluation'

        # --- SEASONAL / CALENDAR CONFOUND CHECK ---
        # A leak flag during a known high-variance calendar period (Ramadan/Eid,
        # summer holidays, etc.) needs a human to sanity-check it before dispatch --
        # the model has no way to tell "everyone got busier for Eid" apart from
        # "everyone independently developed a leak" using only a 12-week window.
        info_notes = []
        recent_confounds = _find_confound_overlaps(four_weeks_ago, max_date)
        baseline_confounds = _find_confound_overlaps(eight_weeks_prior, four_weeks_ago)

        seasonal_confound_note = None
        if recent_confounds:
            seasonal_confound_note = (
                f"Recent evaluation window overlaps known high-variance period(s): "
                f"{', '.join(recent_confounds)}. Elevated readings may reflect normal "
                f"seasonal/holiday demand rather than a leak -- verify before dispatch."
            )
        elif baseline_confounds:
            seasonal_confound_note = (
                f"Historical baseline window overlaps known high-variance period(s): "
                f"{', '.join(baseline_confounds)}. The 'normal' baseline itself may be "
                f"skewed, which can affect results in either direction."
            )

        # --- RAMADAN-SPECIFIC NIGHT-HOUR HANDLING ---
        # Ramadan doesn't just raise total demand -- it specifically shifts WHEN
        # people/businesses are active into hours normally treated as the quiet
        # trough, which is the one kind of confound that can actually fool MNF
        # (a general demand increase during the day wouldn't touch the night floor
        # at all). Two different mechanisms need two different fixes:
        NIGHT_SHIFTING_KEYWORD = "Ramadan"
        ramadan_active_recent = any(NIGHT_SHIFTING_KEYWORD in c for c in recent_confounds)
        force_mnf_inapplicable = False

        if ramadan_active_recent:
            if any(kw in folder_type for kw in ["Residential", "Villa", "Flat"]):
                # Mechanism: suhoor (the pre-dawn meal) is eaten roughly 3-5am,
                # squarely inside the normal [1,2,3,4] night window -- a narrow,
                # predictable shift, so route around it rather than abandoning MNF.
                original_night_hours = night_hours
                night_hours = [4, 5, 6]
                info_notes.append(
                    f"Ramadan active in recent window: shifted night-hours check from "
                    f"{original_night_hours} to {night_hours} to route around the suhoor "
                    f"(pre-dawn meal) period, which is not a genuine quiet trough during Ramadan."
                )
            elif "Industrial" not in folder_type and "Government" not in folder_type:
                # Commercial / Hotel: extended iftar/suhoor service can mean the
                # business is legitimately open and active through the night for
                # the whole month -- not a narrow, predictable window like suhoor
                # at home, so there's no single safe hour range to fall back to.
                # Treat this the same way a permanently-24/7 account is treated:
                # skip MNF entirely for this evaluation and rely on Mann-Kendall,
                # which doesn't depend on any hour being quiet.
                force_mnf_inapplicable = True
                info_notes.append(
                    "Ramadan active in recent window: Commercial/Hotel accounts may run "
                    "extended overnight hours for iftar/suhoor service, so the night trough "
                    "cannot be trusted this month. Minimum Night Flow skipped for this "
                    "evaluation; using Mann-Kendall trend detection instead."
                )

        # --- 5. DATA COMPLETENESS (now meaningful, since the grid is complete) ---
        recent_mask = df['period'] == 'Recent_Evaluation'
        recent_total_rows = int(recent_mask.sum())
        recent_present_rows = int(df.loc[recent_mask, consumption_col].notna().sum())
        data_completeness_recent = round(recent_present_rows / recent_total_rows, 3) if recent_total_rows else 0.0

        recent_night_mask = recent_mask & df['hour'].isin(night_hours)
        recent_night_total = int(recent_night_mask.sum())
        recent_night_present = int(df.loc[recent_night_mask, consumption_col].notna().sum())
        data_completeness_night = round(recent_night_present / recent_night_total, 3) if recent_night_total else 0.0

        # --- 6. BEHAVIOR BASELINE COMPOSITION ---
        baseline_data = df[df['period'] == 'Historical_Baseline']

        baseline_profile = baseline_data.groupby(['day_of_week', 'hour'])[consumption_col].median().reset_index(name='baseline_median')
        baseline_std = baseline_data.groupby(['day_of_week', 'hour'])[consumption_col].std().reset_index(name='baseline_std')

        df = pd.merge(df, baseline_profile, on=['day_of_week', 'hour'], how='left')
        df = pd.merge(df, baseline_std, on=['day_of_week', 'hour'], how='left')

        # Per-(day_of_week, hour) std floor, scaled off that cell's own median rather
        # than a single global number. Night cells (naturally near-zero, low variance)
        # get a small floor; daytime cells get a floor proportional to their own scale.
        df['group_std_floor'] = df['baseline_median'].clip(lower=0) * std_floor_pct
        df['group_std_floor'] = df['group_std_floor'].clip(lower=0.010)

        # --- 7. STATISTICAL DEVIATION MEASUREMENT ---
        df['abs_deviation'] = df[consumption_col] - df['baseline_median']
        df['z_score'] = df['abs_deviation'] / (df['baseline_std'].fillna(0) + df['group_std_floor'])
        # Missing consumption readings must NOT collapse to "0 deviation" -- that would
        # make a dead meter look identical to confirmed-normal usage. Keep them NaN and
        # exclude from anomaly logic explicitly (handled by is_anomaly's NaN-safe compare).
        df.loc[df[consumption_col].isna(), ['abs_deviation', 'z_score']] = np.nan

        # --- 8. CORE LEAK EVALUATION ---
        leak_detected = False
        leak_reasons = []
        NIGHT_TROUGH_RATIO_THRESHOLD = 0.55

        def _trough_ratio(hist_min_flow, all_hours_median):
            if pd.notna(hist_min_flow) and all_hours_median and all_hours_median > 0:
                return hist_min_flow / all_hours_median
            return np.nan

        baseline_all_median = baseline_data[consumption_col].median()

        # --- COHORT COMPARISON METRIC ---
        # A general, signal-agnostic "how much did this account's overall usage
        # rise" number, computed for every customer regardless of which (if any)
        # individual detection path fires. This is what the crawler later uses to
        # compare a customer against their category peers -- self-comparison stays
        # the primary decision-maker; this is only ever a confidence MODIFIER
        # applied afterward, never a leak-detection signal on its own.
        # Historical daily consumption
        historical_daily = (
            baseline_data
            .groupby(baseline_data[time_col].dt.floor("D"))[consumption_col]
            .sum()
        )

        # Recent daily consumption
        recent_daily = (
            df.loc[recent_mask]
            .groupby(df.loc[recent_mask, time_col].dt.floor("D"))[consumption_col]
            .sum()
        )

        baseline_daily_median = historical_daily.median()
        recent_daily_median = recent_daily.median()

        if (
            pd.notna(baseline_daily_median)
            and baseline_daily_median > 0
            and pd.notna(recent_daily_median)
        ):
            recent_vs_baseline_pct_change = (
                recent_daily_median - baseline_daily_median
            ) / baseline_daily_median
        else:
            recent_vs_baseline_pct_change = None

        # --- ATTEMPT 1: FIXED CATEGORY NIGHT HOURS ---
        if force_mnf_inapplicable:
            # Skip computing a floor at all -- during Ramadan, a Commercial/Hotel
            # account's "quiet" hours may not be quiet, so there's no trustworthy
            # trough to measure even via adaptive discovery (which would just find
            # a different, still-contaminated low point from the same window).
            historical_min_flow, highest_observed_floor, mnf_evaluated = np.nan, np.nan, False
            night_trough_ratio = np.nan
            mnf_applicable = False
            trough_method = "ramadan_seasonal_override"
            active_daily_min = pd.Series(dtype=float)
        else:
            historical_min_flow, highest_observed_floor, mnf_evaluated, active_daily_min = _compute_night_floor(
                baseline_data, df, recent_mask, night_hours, time_col, consumption_col
            )
            night_trough_ratio = _trough_ratio(historical_min_flow, baseline_all_median)
            mnf_applicable = bool(pd.notna(night_trough_ratio) and night_trough_ratio <= NIGHT_TROUGH_RATIO_THRESHOLD)
            trough_method = "fixed_category_hours" if mnf_applicable else None
            if not mnf_applicable:
                # A floor could still be computed from the data, but since it isn't a
                # real trough (ratio check failed), it's not a valid MNF evaluation --
                # don't let it masquerade as one before the adaptive attempt runs.
                mnf_evaluated = False

        # --- ATTEMPT 2 (Option 1): ADAPTIVE, DATA-DRIVEN TROUGH DISCOVERY ---
        # If this customer's category-assumed night hours aren't actually a quiet
        # period for them (e.g. a single-shift "Industrial" account, or a
        # "Commercial" account with real off-hours), don't give up on MNF --
        # find whichever hours of the day ARE this customer's own low point from
        # their own baseline data, and re-run the same floor logic on those.
        if not mnf_applicable and not force_mnf_inapplicable:
            hourly_avg = baseline_data.groupby('hour')[consumption_col].median()
            if not hourly_avg.empty:
                k = max(2, len(night_hours))
                adaptive_hours = hourly_avg.sort_values().index[:k].tolist()
                adaptive_hist_min, adaptive_floor, adaptive_evaluated, adaptive_daily_min = _compute_night_floor(
                    baseline_data, df, recent_mask, adaptive_hours, time_col, consumption_col
                )
                adaptive_ratio = _trough_ratio(adaptive_hist_min, baseline_all_median)

                if pd.notna(adaptive_ratio) and adaptive_ratio <= NIGHT_TROUGH_RATIO_THRESHOLD:
                    mnf_applicable = True
                    trough_method = "adaptive_data_driven_hours"
                    historical_min_flow = adaptive_hist_min
                    highest_observed_floor = adaptive_floor
                    mnf_evaluated = adaptive_evaluated
                    active_daily_min = adaptive_daily_min
                    night_trough_ratio = adaptive_ratio
                    info_notes.append(
                        f"Fixed category night hours showed no real trough; used this customer's own "
                        f"lowest-usage hours {sorted(adaptive_hours)} instead (adaptive trough ratio "
                        f"{adaptive_ratio:.0%})."
                    )

        nights_checked = None
        nights_elevated = None

        if mnf_applicable and mnf_evaluated:
            night_drift_threshold = max(night_drift_abs_floor, historical_min_flow * (night_drift_multiplier - 1))
            elevated_threshold = historical_min_flow + night_drift_threshold

            if highest_observed_floor > elevated_threshold and highest_observed_floor > 0.02:
                leak_detected = True
                leak_reasons.append({
                    "text": (
                        f"Slow Constant Leak: Night minimum floor structurally rose from "
                        f"{historical_min_flow:.3f} to {highest_observed_floor:.3f} m3 "
                        f"(threshold drift: {night_drift_threshold:.3f} m3, method: {trough_method})."
                    ),
                    "points": 35,
                })
            elif len(active_daily_min) >= 10:
                # --- Option 8: INTERMITTENT / DUTY-CYCLED LEAK DETECTION ---
                # A leak that cycles on and off (leak, stop, leak, stop) won't show up
                # as a continuously elevated rolling floor above -- some nights will
                # look normal, pulling the rolling minimum back down. Instead, count
                # how many of the recent nights individually crossed the elevated
                # threshold. Reuses the same daily_min series and threshold already
                # computed for the continuous check above -- no extra computation,
                # just a different way of reading the same numbers.
                nights_checked = int(len(active_daily_min))
                nights_elevated = int((active_daily_min > elevated_threshold).sum())
                intermittency_ratio = nights_elevated / nights_checked

                INTERMITTENCY_RATIO_THRESHOLD = 0.6
                if intermittency_ratio >= INTERMITTENCY_RATIO_THRESHOLD:
                    leak_detected = True
                    leak_reasons.append({
                        "text": (
                            f"Intermittent Slow Leak: elevated minimum night flow on {nights_elevated} of "
                            f"the last {nights_checked} nights (threshold: {elevated_threshold:.3f} m3), "
                            f"even though not every night was elevated (method: {trough_method})."
                        ),
                        "points": 25,
                    })
        elif not mnf_applicable:
            info_notes.append(
                "Minimum Night Flow not applicable even after adaptive trough search: this account never "
                "drops to a real quiet period (likely continuous/24-7 operation). Falling back to trend-based "
                "slow-leak detection (Mann-Kendall) instead."
            )

        # --- ATTEMPT 3 (Option 2): MANN-KENDALL TREND DETECTION ---
        # Only used when NO trough (fixed or adaptive) exists at all -- i.e. a
        # genuinely continuous account where a small leak is a tiny fraction of a
        # large flat baseline. Instead of a quiet-period floor, this looks for a
        # slow, SUSTAINED upward drift in the deseasonalized daily signal
        # (abs_deviation, already adjusted for each hour's normal day/hour
        # pattern). Mann-Kendall is nonparametric (no Gaussian assumption on the
        # residuals, unlike a CUSUM control chart) and gives a real p-value, so
        # the false-alarm rate is controlled directly by ALPHA rather than by an
        # approximated control-chart threshold that has to be re-tuned empirically.
        MK_ALPHA = 0.05  # one-sided significance threshold
        # Note: the effect-size gate below (total_projected_increase > night_drift_abs_floor)
        # does most of the false-positive suppression work here, which is what allows
        # ALPHA to sit at the conventional 0.05 rather than a much stricter value --
        # empirically, alpha=0.01 traded away real detection power (dropped true-positive
        # rate on a 2.5%-sustained synthetic leak from ~97% to ~80%) without actually
        # lowering the false-positive rate any further (both held at 0% in testing).
        mk_evaluated = False
        mk_p_value = None
        mk_sen_slope = None
        trough_method = trough_method or "none"

        if not mnf_applicable:
            recent_slice = df[df['period'] == 'Recent_Evaluation'].copy()
            recent_slice['date'] = recent_slice[time_col].dt.floor('D')
            recent_day_group = recent_slice.groupby('date')[consumption_col]
            recent_daily = recent_slice.groupby('date')['abs_deviation'].mean()
            # Same boundary-truncation guard as MNF/CUSUM: require each day to
            # actually have (close to) 24 real hourly readings.
            recent_daily_coverage = recent_day_group.apply(lambda s: s.notna().sum() / 24.0)
            recent_daily = recent_daily[recent_daily_coverage >= 0.9].sort_index()

            if len(recent_daily) >= 14:
                mk_result = _mann_kendall_trend(recent_daily.values)
                if mk_result is not None:
                    mk_evaluated = True
                    mk_p_value = round(mk_result["p_one_sided"], 5)
                    mk_sen_slope = round(mk_result["sen_slope"], 5)

                    # Effect-size gate: statistical significance alone isn't enough --
                    # a p<0.01 trend that only adds a trivial amount of water over the
                    # whole window isn't worth flagging. Reuse the category's own
                    # night_drift_abs_floor as "the minimum real volume increase we'd
                    # already consider leak-worthy elsewhere" rather than inventing a
                    # separate, untested threshold just for this path.
                    n_days = mk_result["n"]
                    total_projected_increase = mk_result["sen_slope"] * n_days

                    if (mk_result["sen_slope"] > 0
                            and mk_result["p_one_sided"] < MK_ALPHA
                            and total_projected_increase > night_drift_abs_floor):
                        leak_detected = True
                        mk_points = 35 if mk_result["p_one_sided"] < 0.01 else 25
                        leak_reasons.append({
                            "text": (
                                f"Slow Trend Leak (Mann-Kendall): statistically significant upward drift "
                                f"(p={mk_result['p_one_sided']:.4f}, one-sided) over {n_days} days, projected "
                                f"total increase {total_projected_increase:.3f} m3; used because no reliable "
                                f"night trough exists for this account."
                            ),
                            "points": mk_points,
                        })
                else:
                    info_notes.append("Mann-Kendall trend check skipped: could not compute a valid test statistic.")
            else:
                info_notes.append("Mann-Kendall trend check skipped: fewer than 14 clean recent days available.")

        # --- VERIFICATION PATH B: SUDDEN MECHANICAL BURSTS (time-true consecutiveness) ---
        df['is_anomaly'] = (
            (df['period'] == 'Recent_Evaluation') &
            (df['z_score'] > z_threshold) &
            (df['abs_deviation'] > burst_vol_threshold)
        ).fillna(False)

        anomaly_series = df.set_index(time_col)['is_anomaly'].astype(int)
        # Time-based rolling window with min_periods == consecutive_hours: since the
        # index is now a complete hourly grid, this can only reach consecutive_hours
        # if that many TRUE hourly points genuinely fall inside the trailing window --
        # a gap in the middle breaks the streak instead of being silently skipped over.
        window_str = f"{consecutive_hours}h"
        consecutive_sum = anomaly_series.rolling(window_str, min_periods=consecutive_hours).sum()

        strict_burst_fired = (consecutive_sum >= consecutive_hours).any()
        if strict_burst_fired:
            leak_detected = True
            hit_times = consecutive_sum[consecutive_sum >= consecutive_hours].index
            window_rows = df[df[time_col].isin(hit_times)]
            max_z = window_rows['z_score'].max()
            peak_volume = window_rows[consumption_col].max()
            # Estimated burst water loss (m3)
            baseline_during_burst = window_rows["baseline_median"].fillna(0)

            burst_excess_volume = (
                window_rows[consumption_col] - baseline_during_burst
            ).clip(lower=0).sum()
            leak_reasons.append({
                "text": (
                    f"Sudden Pipe Burst: Sustained, uncharacteristic high volume event for "
                    f"{consecutive_hours}+ consecutive hours (Peak Vol: {peak_volume:.3f} m3, Peak Z: {max_z:.1f})."
                ),
                "points": 40,
            })

        cumulative_burst_max_excess = None
        burst_excess_volume = None
        if not strict_burst_fired:
            # --- Option 7: CUMULATIVE / FLUCTUATING BURST DETECTION (retuned) ---
            # A burst that fluctuates (e.g. pressure variation causing it to dip below
            # z_threshold for a stray hour or two) can fail the strict consecutive-hours
            # check even though a large amount of excess water is clearly going out over
            # a short window. Complementary check: sum up the POSITIVE excess volume
            # (only counting hours that are at least somewhat anomalous) over a rolling
            # 6-hour window. v1 of this check flagged on a SINGLE window crossing a loose
            # threshold anywhere in ~28 days, with no false-positive validation -- testing
            # showed that produced false positives even on genuinely clean data (a single
            # busy day was enough). Retuned: tighter thresholds, AND requires the excess
            # to recur on multiple separate days -- a real ongoing intermittent burst
            # keeps showing up; one unusually busy day does not.
            CUMULATIVE_WINDOW_HOURS = 6
            soft_z_threshold = z_threshold * 0.75
            cumulative_excess_threshold = burst_vol_threshold * 4.0
            MIN_OCCURRENCE_DAYS = 3

            is_soft_anomaly = (df['period'] == 'Recent_Evaluation') & (df['z_score'] > soft_z_threshold)
            excess_series = df['abs_deviation'].where(is_soft_anomaly & (df['abs_deviation'] > 0), 0.0)
            excess_series = excess_series.fillna(0.0)
            excess_indexed = pd.Series(excess_series.values, index=df[time_col])
            rolling_excess = excess_indexed.rolling(f"{CUMULATIVE_WINDOW_HOURS}h", min_periods=CUMULATIVE_WINDOW_HOURS).sum()

            if rolling_excess.notna().any():
                cumulative_burst_max_excess = round(float(rolling_excess.max()), 4)
                # Persistence: count DISTINCT calendar days that had at least one
                # window cross the threshold, not just how many overlapping hourly
                # windows did (adjacent windows on the same single event are
                # trivially correlated and would otherwise inflate the count).
                exceeding = rolling_excess[rolling_excess > cumulative_excess_threshold]
                days_with_exceedance = int(exceeding.index.floor('D').nunique()) if not exceeding.empty else 0

                if days_with_exceedance >= MIN_OCCURRENCE_DAYS:
                    leak_detected = True
                    leak_reasons.append({
                        "text": (
                            f"Intermittent/Fluctuating Burst: cumulative excess volume exceeded "
                            f"{cumulative_excess_threshold:.3f} m3 within {CUMULATIVE_WINDOW_HOURS}-hour "
                            f"windows on {days_with_exceedance} separate days (peak {cumulative_burst_max_excess:.3f} m3), "
                            f"even though usage didn't stay anomalous for {consecutive_hours} strictly consecutive hours."
                        ),
                        "points": 30,
                    })

        # --- 9. PRIORITY SCORE & EXPLAINABILITY ---
        # Deliberately NOT a calibrated probability -- we have no confirmed leak
        # labels yet to validate against, so calling this a "risk %" would overstate
        # confidence the system doesn't actually have. It's an additive suspicion
        # score built directly from which independent signals fired, meant for
        # triage/ranking (dispatch the highest scores first), not as a statistical
        # probability of a true leak.
        raw_score = sum(r["points"] for r in leak_reasons)
        raw_score = min(raw_score, 100)

        # Discount (not zero out) the score when recent data is meaningfully
        # incomplete, since every method above is only as trustworthy as the data
        # feeding it. Only kicks in below 80% completeness, and is floored at 0.3
        # so a still-somewhat-usable file isn't driven all the way to a 0 score.
        completeness_factor = 1.0
        if data_completeness_recent is not None and data_completeness_recent < 0.8:
            completeness_factor = max(data_completeness_recent, 0.3)

        priority_score = int(round(raw_score * completeness_factor))

        if seasonal_confound_note:
            info_notes.append(seasonal_confound_note)

        if priority_score >= 70:
            priority_tier = "High - Dispatch"
        elif priority_score >= 40:
            priority_tier = "Medium - Monitor"
        elif priority_score > 0:
            priority_tier = "Low - Review Only"
        else:
            priority_tier = "None"

        # A flag landing on a known seasonal confound shouldn't auto-escalate to
        # "dispatch now" -- cap it at Medium so a human reviews the context first,
        # without hiding or discarding the underlying signal.
        if recent_confounds and priority_tier == "High - Dispatch":
            priority_tier = "Medium - Monitor (Seasonal Overlap)"

        if leak_reasons:
            priority_reasons_parts = [f"{r['text']} (+{r['points']}pts)" for r in leak_reasons]
        else:
            priority_reasons_parts = ["No leak signals triggered."]
        if completeness_factor < 1.0:
            priority_reasons_parts.append(
                f"Score discounted for incomplete recent data ({data_completeness_recent:.0%} complete)."
            )
        priority_reasons_str = " | ".join(priority_reasons_parts)

        # --- 10. UNIFIED OPERATIONAL OUTPUT ---
        detail_parts = [r["text"] for r in leak_reasons] if leak_reasons else ["Normal consumer operational patterns detected."]
        detail_parts = detail_parts + info_notes  # advisory notes shown regardless of verdict

        return {
            "Status": "SUCCESS",
            "Leak_Suspected": "YES" if leak_detected else "NO",
            "Priority_Score": priority_score,
            "Priority_Tier": priority_tier,
            "Priority_Reasons": priority_reasons_str,
            "Details": " | ".join(detail_parts),
            "Seasonal_Confound_Recent": ", ".join(recent_confounds) if recent_confounds else None,
            "Seasonal_Confound_Baseline": ", ".join(baseline_confounds) if baseline_confounds else None,
            "Recent_Vs_Baseline_Pct_Change": round(recent_vs_baseline_pct_change, 4) if recent_vs_baseline_pct_change is not None else None,
            "Historical_Night_Floor_m3": round(historical_min_flow, 4) if pd.notna(historical_min_flow) else None,
            "Recent_Night_Floor_m3": round(highest_observed_floor, 4) if pd.notna(highest_observed_floor) else None,
            "Historical_Daily_Median_Consumption_m3":
                round(baseline_daily_median, 4)
                if pd.notna(baseline_daily_median)
                else None,

            "Recent_Daily_Median_Consumption_m3":
                round(recent_daily_median, 4)
                if pd.notna(recent_daily_median)
                else None,
            "MNF_Applicable": mnf_applicable,
            "Trough_Detection_Method": trough_method,
            "Night_Trough_Ratio": round(night_trough_ratio, 3) if pd.notna(night_trough_ratio) else None,
            "MNF_Evaluated": mnf_evaluated,
            "Nights_Elevated": nights_elevated,
            "Nights_Checked": nights_checked,
            "MK_Evaluated": mk_evaluated,
            "MK_P_Value": mk_p_value,
            "MK_Sen_Slope": mk_sen_slope,
            "Cumulative_Burst_Max_Excess_m3": cumulative_burst_max_excess,
            "Data_Completeness_Recent": data_completeness_recent,
            "Data_Completeness_Night": data_completeness_night,
        }

    except Exception as e:
        return {
            "Status": "ERROR",
            "Leak_Suspected": "UNKNOWN",
            "Priority_Score": None,
            "Priority_Tier": None,
            "Priority_Reasons": None,
            "Seasonal_Confound_Recent": None,
            "Seasonal_Confound_Baseline": None,
            "Recent_Vs_Baseline_Pct_Change": None,
            "Details": f"Execution Engine Failure: {str(e)}",
            "Historical_Night_Floor_m3": 0,
            "Recent_Night_Floor_m3": None,
            "Historical_Daily_Median_Consumption_m3": None,
            "Recent_Daily_Median_Consumption_m3": None,
            "MNF_Applicable": None,
            "Trough_Detection_Method": None,
            "Night_Trough_Ratio": None,
            "MNF_Evaluated": False,
            "Nights_Elevated": None,
            "Nights_Checked": None,
            "MK_Evaluated": False,
            "MK_P_Value": None,
            "MK_Sen_Slope": None,
            "Cumulative_Burst_Max_Excess_m3": None,
            "Data_Completeness_Recent": None,
            "Data_Completeness_Night": None,
        }


# =====================================================================
# PORTFOLIO CRAWLER
# =====================================================================

def _apply_peer_comparison(results_list, min_cohort_size=5, outlier_z=2.0, consistent_z=0.5, score_bonus=15):
    """
    Second-pass, crawler-level comparison: for each customer already flagged
    Leak_Suspected == 'YES' by the per-file self-comparison logic, compares
    their overall demand rise (Recent_Vs_Baseline_Pct_Change) against the
    median rise of their OWN category peers in this same run.

    This generalizes the seasonal-confound handling to ANY shared cause, known
    or unknown -- it doesn't need Ramadan (or any other event) to be hardcoded
    to notice "this customer's rise looks just like everyone else's in their
    category right now."

    Design rule, deliberately asymmetric:
      - Self-comparison (MNF/Mann-Kendall/burst) remains the ONLY thing that can
        create a leak flag. Peer comparison is applied only AFTER that, and only
        to already-flagged customers -- it never turns a NO into a YES.
      - It can BOOST confidence (a customer standing out well above their peers
        even during a shared event is stronger evidence, not weaker -- a real
        leak riding on top of a seasonal bump should look like exactly this).
      - It can only ever CAP the tier label, never reduce the underlying score
        or remove the reasons already recorded -- softening confidence in how a
        result is acted on is not the same as suppressing the evidence itself.
      - Categories with too few files this run (< min_cohort_size) are left
        untouched -- a median/spread computed from 2-3 files isn't trustworthy.
    """
    from collections import defaultdict
    import statistics

    groups = defaultdict(list)
    for r in results_list:
        if r.get("Status") == "SUCCESS" and r.get("Recent_Vs_Baseline_Pct_Change") is not None:
            groups[r.get("Profile_Folder")].append(r)

    for folder, members in groups.items():
        if len(members) < min_cohort_size:
            for r in members:
                r["Cohort_Median_Pct_Change"] = None
                r["Peer_Z_Score"] = None
                r["Peer_Comparison_Note"] = f"Cohort too small ({len(members)} files) for peer comparison."
            continue

        pct_changes = [r["Recent_Vs_Baseline_Pct_Change"] for r in members]
        cohort_median = statistics.median(pct_changes)
        abs_devs = [abs(p - cohort_median) for p in pct_changes]
        cohort_mad = statistics.median(abs_devs) * 1.4826  # scale to be std-comparable under normality
        cohort_mad_floor = max(cohort_mad, 0.05)  # floor so a very tight cohort doesn't explode the z-score

        for r in members:
            peer_z = (r["Recent_Vs_Baseline_Pct_Change"] - cohort_median) / cohort_mad_floor
            r["Cohort_Median_Pct_Change"] = round(cohort_median, 4)
            r["Peer_Z_Score"] = round(peer_z, 2)

            if r.get("Leak_Suspected") != "YES":
                r["Peer_Comparison_Note"] = "Not applicable (no leak signal to compare)."
                continue

            if peer_z >= outlier_z:
                # Stands out clearly even against peers -- boost, and this is
                # strong enough evidence to override a seasonal-overlap cap,
                # since it directly argues AGAINST "this is just the shared pattern".
                old_score = r.get("Priority_Score") or 0
                new_score = min(100, old_score + score_bonus)
                r["Priority_Score"] = new_score
                if new_score >= 70:
                    r["Priority_Tier"] = "High - Dispatch"
                elif new_score >= 40:
                    r["Priority_Tier"] = "Medium - Monitor"
                else:
                    r["Priority_Tier"] = "Low - Review Only"
                note = (
                    f"Stands out from category peers (z={peer_z:.1f} vs cohort median "
                    f"{cohort_median:+.1%} change) -- likely an individual issue, not just "
                    f"a shared portfolio-wide pattern. (+{score_bonus}pts)"
                )
                r["Peer_Comparison_Note"] = note
                r["Priority_Reasons"] = (r.get("Priority_Reasons") or "") + " | " + note
                r["Details"] = (r.get("Details") or "") + " | " + note

            elif peer_z <= consistent_z:
                # Rise is unremarkable next to peers -- don't erase the evidence,
                # just don't let it auto-escalate to "dispatch now" on its own.
                note = (
                    f"Rise is consistent with or below the category's typical change this "
                    f"period (z={peer_z:.1f} vs cohort median {cohort_median:+.1%}) -- may "
                    f"reflect a shared cause across many customers rather than an individual leak."
                )
                r["Peer_Comparison_Note"] = note
                if r.get("Priority_Tier") == "High - Dispatch":
                    r["Priority_Tier"] = "Medium - Monitor (Cohort-Consistent)"
                    r["Priority_Reasons"] = (r.get("Priority_Reasons") or "") + " | " + note
                    r["Details"] = (r.get("Details") or "") + " | " + note
            else:
                r["Peer_Comparison_Note"] = (
                    f"Within normal range vs peers (z={peer_z:.1f}) -- no adjustment."
                )

    return results_list


def run_portfolio_leak_audit(base_folder="customers", time_col='Hourly', consumption_col='Consumption m3'):
    """
    Crawls through `base_folder`, finds every customer data file inside category
    subfolders (e.g. 'Villa (Residential)', 'Commercial', 'Government', ...),
    and runs analyze_leak_production_grade on each one.

    Each subfolder name is passed straight through as `folder_type`, so the
    category keyword matching inside analyze_leak_production_grade (looking for
    "Residential", "Villa", "Government", "Industrial", else Commercial) is driven
    by however you've actually named your folders -- rename folders, not code, to
    retarget a customer set to a different category profile.
    """
    results_list = []

    if not os.path.exists(base_folder):
        print(f"Directory path error: base folder '{base_folder}' does not exist.")
        return results_list

    print(f"Scanning '{base_folder}' for customer data files...\n")

    file_count = 0
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            # Excel and CSV both supported by analyze_leak_production_grade
            is_excel = file.endswith(('.xlsx', '.xls')) and not file.startswith('~$')
            is_csv = file.endswith('.csv')
            if not (is_excel or is_csv):
                continue

            full_file_path = os.path.join(root, file)
            folder_category = os.path.basename(root)
            file_count += 1

            print(f"  [{file_count}] {full_file_path}  (profile: {folder_category})")

            # analyze_leak_production_grade already wraps its own logic in a
            # try/except and returns a Status: ERROR dict on failure, so one bad
            # file cannot crash the whole portfolio run. This outer try/except is
            # a second safety net only for something going wrong outside that
            # function (e.g. an unexpected exception raised while calling it).
            try:
                audit_summary = analyze_leak_production_grade(
                    file_path=full_file_path,
                    folder_type=folder_category,
                    time_col=time_col,
                    consumption_col=consumption_col,
                )
            except Exception as e:
                audit_summary = {
                    "Status": "ERROR",
                    "Leak_Suspected": "UNKNOWN",
                    "Priority_Score": None,
                    "Priority_Tier": None,
                    "Priority_Reasons": None,
                    "Seasonal_Confound_Recent": None,
                    "Seasonal_Confound_Baseline": None,
                    "Recent_Vs_Baseline_Pct_Change": None,
                    "Details": f"Unhandled crawler-level failure: {str(e)}",
                    "Historical_Night_Floor_m3": 0,
                    "Recent_Night_Floor_m3": None,
                    "Historical_Daily_Median_Consumption_m3": None,
                    "Recent_Daily_Median_Consumption_m3": None,
                    "MNF_Applicable": None,
                    "Trough_Detection_Method": None,
                    "Night_Trough_Ratio": None,
                    "MNF_Evaluated": False,
                    "Nights_Elevated": None,
                    "Nights_Checked": None,
                    "MK_Evaluated": False,
                    "MK_P_Value": None,
                    "MK_Sen_Slope": None,
                    "Cumulative_Burst_Max_Excess_m3": None,
                    "Data_Completeness_Recent": None,
                    "Data_Completeness_Night": None,
                }

            audit_summary["Filename"] = file
            audit_summary["Full_Path"] = full_file_path
            audit_summary["Profile_Folder"] = folder_category
            results_list.append(audit_summary)

            if audit_summary.get("Status") == "ERROR":
                print(f"        -> ERROR: {audit_summary.get('Details')}")
            elif audit_summary.get("Status") == "SKIPPED":
                print(f"        -> SKIPPED: {audit_summary.get('Details')}")
            else:
                print(f"        -> {audit_summary.get('Leak_Suspected')}")

    if file_count == 0:
        print(f"No .xlsx / .xls / .csv files found anywhere under '{base_folder}'.")

    results_list = _apply_peer_comparison(results_list)
    return results_list


# =====================================================================
# PIPELINE EXECUTION ENGINE
# =====================================================================

if __name__ == "__main__":
    # 1. Run the audit pipeline across your customer folder tree.
    #    Point this at your actual data root, e.g. "customers" if your files are
    #    laid out as customers/Villa (Residential)/*.xlsx, customers/Commercial/*.xlsx, etc.
    all_audit_results = run_portfolio_leak_audit(base_folder="customers")

    # 2. Turn results into a structured DataFrame if anything was found/processed.
    if all_audit_results:
        summary_df = pd.DataFrame(all_audit_results)

        # Reorder columns so identifying info leads, then verdict, then diagnostics.
        preferred_order = [
            "Filename", "Profile_Folder", "Status", "Leak_Suspected",
            "Priority_Score", "Priority_Tier", "Priority_Reasons", "Details",
            "Seasonal_Confound_Recent", "Seasonal_Confound_Baseline",
            "Recent_Vs_Baseline_Pct_Change", "Cohort_Median_Pct_Change", "Peer_Z_Score", "Peer_Comparison_Note",
            "Historical_Night_Floor_m3", "Recent_Night_Floor_m3",
            "MNF_Applicable", "Trough_Detection_Method", "Night_Trough_Ratio", "MNF_Evaluated",
            "Nights_Elevated", "Nights_Checked",
            "MK_Evaluated", "MK_P_Value", "MK_Sen_Slope",
            "Cumulative_Burst_Max_Excess_m3",
            "Data_Completeness_Recent", "Data_Completeness_Night", "Full_Path",
        ]
        existing_cols = [c for c in preferred_order if c in summary_df.columns]
        remaining_cols = [c for c in summary_df.columns if c not in existing_cols]
        summary_df = summary_df[existing_cols + remaining_cols]

        # 3. Export to a master tracking CSV.
        output_file = "portfolio_leakage_audit_summary.csv"
        summary_df.to_csv(output_file, index=False)

        n_leaks = (summary_df["Leak_Suspected"] == "YES").sum()
        n_errors = (summary_df["Status"] == "ERROR").sum()
        n_skipped = (summary_df["Status"] == "SKIPPED").sum()
        n_mnf_na = (summary_df["MNF_Applicable"] == False).sum() if "MNF_Applicable" in summary_df else 0

        print(f"\nSUCCESS: audited {len(summary_df)} files -> exported to '{output_file}'")
        print(f"  Leaks suspected : {n_leaks}")
        print(f"  Errors          : {n_errors}")
        print(f"  Skipped (short) : {n_skipped}")
        print(f"  MNF not applicable (24/7-style accounts): {n_mnf_na}")
        print()
        print(summary_df.head())
    else:
        print("Pipeline finished: no data records found or processed inside target directory tree.")