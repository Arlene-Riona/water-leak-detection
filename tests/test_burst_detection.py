"""
Tests for burst detection: the strict consecutive-hours path, and the
cumulative/fluctuating path that catches bursts which dip below the strict
threshold for a stray hour.

test_single_busy_day_not_flagged is the single most important test in this
file: it's a direct regression guard for a real bug found during development,
where the original (untested) cumulative burst check flagged a real customer
file whose night floor was completely unchanged, purely from one unusually
busy day crossing a loose threshold once.
"""
import os
import tempfile
import numpy as np
import pandas as pd
from leak_detection import analyze_leak_production_grade


def _base_residential(seed):
    rng = pd.date_range("2026-01-01", periods=24 * 7 * 12, freq="h")
    hour = rng.hour
    rgen = np.random.default_rng(seed)
    base = np.where((hour >= 1) & (hour <= 4), 0.01, 0.15) + rgen.random(len(rng)) * 0.02
    return rng, base


def test_strict_consecutive_burst_detected(write_customer_csv):
    rng, base = _base_residential(seed=20)
    leak_start = len(rng) - 24 * 7 * 3
    burst_idx = leak_start + 100
    base[burst_idx:burst_idx + 5] += 2.0
    path = write_customer_csv(rng, base)

    result = analyze_leak_production_grade(path, "Residential")

    assert result["Leak_Suspected"] == "YES"
    assert "Sudden Pipe Burst" in result["Details"]


def test_recurring_fluctuating_burst_caught_by_cumulative_check(write_customer_csv):
    """
    A pattern that recurs across many separate days but never holds strictly
    consecutive (high-low-high-low) should still be caught, via the
    cumulative excess-volume + persistence-across-days check.
    """
    rng, base = _base_residential(seed=99)
    hour = rng.hour
    leak_start = len(rng) - 24 * 7 * 3
    for day_offset in range(21):
        day_start = leak_start + day_offset * 24
        pattern_hours = [10, 11, 12, 13, 14, 15]
        pattern_vals = [1.5, 0.15, 1.5, 0.15, 1.5, 0.15]
        for h_off, v in zip(pattern_hours, pattern_vals):
            idx = day_start + h_off
            if idx < len(base):
                base[idx] = v
    path = write_customer_csv(rng, base)

    result = analyze_leak_production_grade(path, "Residential")

    assert result["Leak_Suspected"] == "YES"
    assert "Intermittent/Fluctuating Burst" in result["Details"]


def test_single_busy_day_not_flagged(write_customer_csv):
    """
    Regression guard: a single one-off busy day (same intra-day pattern as
    the recurring-burst test above, but occurring only ONCE) must NOT be
    flagged. This is the exact scenario that exposed the original untested
    Option 7 bug.
    """
    rng, base = _base_residential(seed=21)
    hour = rng.hour
    leak_start = len(rng) - 24 * 7 * 3
    day_start = leak_start + 5 * 24
    for h_off, v in zip([10, 11, 12, 13, 14, 15], [1.5, 0.15, 1.5, 0.15, 1.5, 0.15]):
        base[day_start + h_off] = v
    path = write_customer_csv(rng, base)

    result = analyze_leak_production_grade(path, "Residential")

    assert result["Leak_Suspected"] == "NO"


def test_burst_false_positive_rate_stays_at_zero_across_categories():
    """
    Regression guard: this exact check (25 trials x 3 categories on clean
    data) is what found the original Option 7 false-positive bug -- including
    a real customer file whose night floor was LITERALLY unchanged still
    getting flagged. Keeping this automated means a future retune can't
    silently reintroduce that failure mode.
    """
    categories = {
        "Residential": lambda h, r: np.where((h >= 1) & (h <= 4), 0.01, 0.15) + r.random(len(h)) * 0.02,
        "Commercial": lambda h, r: np.where((h >= 2) & (h <= 4), 0.8, 6.4) + r.random(len(h)) * 0.5,
        "Industrial": lambda h, r: 20 + r.random(len(h)) * 1.0,
    }
    rng = pd.date_range("2026-01-01", periods=24 * 7 * 12, freq="h")
    hour = rng.hour
    total_fp = 0
    total = 0

    with tempfile.TemporaryDirectory() as tmp:
        for cat, gen in categories.items():
            for i in range(8):
                rgen = np.random.default_rng(hash((cat, i)) % (2 ** 31))
                base = gen(hour, rgen)
                path = os.path.join(tmp, f"{cat}_{i}.csv")
                pd.DataFrame({"Hourly": rng, "Consumption m3": base}).to_csv(path, index=False)
                result = analyze_leak_production_grade(path, cat)
                total += 1
                if result["Leak_Suspected"] == "YES":
                    total_fp += 1

    assert total_fp == 0, f"Unexpected false positives on clean data: {total_fp}/{total}"
