"""
Tests for Minimum Night Flow (fixed + adaptive trough), and the intermittent
/ duty-cycled leak fallback within that same path.
"""
import numpy as np
import pandas as pd
from leak_detection import analyze_leak_production_grade


def test_clean_residential_no_false_positive(make_hourly_series, write_customer_csv):
    rng, base = make_hourly_series(seed=1)
    path = write_customer_csv(rng, base)
    result = analyze_leak_production_grade(path, "Residential")
    assert result["Status"] == "SUCCESS"
    assert result["Leak_Suspected"] == "NO"


def test_continuous_slow_leak_detected(make_hourly_series, write_customer_csv):
    rng, base = make_hourly_series(seed=2)
    hour = rng.hour
    leak_start = len(rng) - 24 * 7 * 3
    base = base.copy()
    base[leak_start:] += np.where(np.isin(hour[leak_start:], [1, 2, 3, 4]), 0.05, 0.0)
    path = write_customer_csv(rng, base)

    result = analyze_leak_production_grade(path, "Residential")

    assert result["Leak_Suspected"] == "YES"
    assert "Slow Constant Leak" in result["Details"]
    assert result["Trough_Detection_Method"] == "fixed_category_hours"
    assert result["MNF_Applicable"] is True


def test_intermittent_duty_cycled_leak_detected(make_hourly_series, write_customer_csv):
    """
    A leak elevated on ~60% of nights (not every night) should never hold a
    continuously-elevated rolling 7-day floor, but should still be caught by
    the intermittent-leak fallback within the same MNF path.
    """
    rng, base = make_hourly_series(seed=3)
    hour = rng.hour
    recent_start = len(rng) - 24 * 7 * 4
    base = base.copy()
    for day_offset in range(28):
        day_start = recent_start + day_offset * 24
        if day_offset % 5 < 3:  # elevated on ~60% of nights, duty-cycled
            for h in [1, 2, 3, 4]:
                idx = day_start + h
                if idx < len(base):
                    base[idx] += 0.05
    path = write_customer_csv(rng, base)

    result = analyze_leak_production_grade(path, "Residential")

    assert result["Leak_Suspected"] == "YES"
    assert "Intermittent Slow Leak" in result["Details"]
    assert result["Nights_Elevated"] is not None
    assert result["Nights_Checked"] is not None


def test_adaptive_trough_rescues_single_shift_industrial(write_customer_csv):
    """
    An Industrial account whose real quiet period is late evening (not the
    category-default 2-4am) should still be caught, via adaptive trough
    discovery finding the account's OWN low-usage hours.
    """
    rng = pd.date_range("2026-01-01", periods=24 * 7 * 12, freq="h")
    hour = rng.hour
    rgen = np.random.default_rng(5)
    base = np.where((hour == 22) | (hour == 23), 0.05, 3.0) + rgen.random(len(rng)) * 0.3
    leak_start = len(rng) - 24 * 7 * 3
    base[leak_start:] += np.where((hour[leak_start:] == 22) | (hour[leak_start:] == 23), 0.4, 0.0)
    path = write_customer_csv(rng, base)

    result = analyze_leak_production_grade(path, "Industrial")

    assert result["Leak_Suspected"] == "YES"
    assert result["Trough_Detection_Method"] == "adaptive_data_driven_hours"


def test_true_24_7_account_mnf_not_applicable(write_customer_csv):
    """A genuinely flat 24/7 account should be recognized as MNF-inapplicable,
    rather than silently producing an unreliable MNF verdict."""
    rng = pd.date_range("2026-01-01", periods=24 * 7 * 12, freq="h")
    rgen = np.random.default_rng(6)
    base = 20 + rgen.random(len(rng)) * 1.0
    path = write_customer_csv(rng, base)

    result = analyze_leak_production_grade(path, "Industrial")

    assert result["MNF_Applicable"] is False
