"""
Tests for seasonal/calendar confound handling: the general flag-and-cap
behavior, plus the Ramadan-specific mechanism fixes (night-hour shifting for
Residential, MNF bypass for Commercial/Hotel).

These dates are pinned to Ramadan 2026 (~Feb 18 - Mar 19); if the confound
lookup table's date ranges are ever changed, these tests need matching dates.
"""
import numpy as np
import pandas as pd
from leak_detection import analyze_leak_production_grade


def test_ramadan_confound_flag_present(write_customer_csv):
    """A recent window ending inside Ramadan 2026 should surface the confound."""
    rng = pd.date_range("2025-10-22 15:00:00", "2026-03-29 23:00:00", freq="h")
    hour = rng.hour
    rgen = np.random.default_rng(42)
    base = np.where((hour >= 2) & (hour <= 4), 0.8, 6.4) + rgen.random(len(rng)) * 2.0
    path = write_customer_csv(rng, base, filename="commercial_ramadan.csv")

    result = analyze_leak_production_grade(path, "Commercial")

    assert result["Seasonal_Confound_Recent"] is not None
    assert "Ramadan" in result["Seasonal_Confound_Recent"]


def test_residential_suhoor_bump_does_not_false_positive(write_customer_csv):
    """
    A suhoor-only consumption bump (single pre-dawn hour, no real leak)
    should NOT be flagged once the night-hours window shifts to route
    around it during Ramadan.
    """
    rng = pd.date_range("2025-10-22 15:00:00", "2026-03-29 23:00:00", freq="h")
    hour = rng.hour
    rgen = np.random.default_rng(51)
    base = np.where((hour >= 1) & (hour <= 4), 0.01, 0.15) + rgen.random(len(rng)) * 0.02
    recent_start = len(rng) - 24 * 29
    base[recent_start:] += np.where(hour[recent_start:] == 3, 0.08, 0.0)
    path = write_customer_csv(rng, base, filename="residential_ramadan.csv")

    result = analyze_leak_production_grade(path, "Residential")

    assert result["Leak_Suspected"] == "NO"


def test_commercial_mnf_bypassed_during_ramadan(write_customer_csv):
    """
    Commercial/Hotel accounts should skip Minimum Night Flow entirely during
    Ramadan (extended overnight hours make the night trough untrustworthy)
    and fall through to Mann-Kendall instead.
    """
    rng = pd.date_range("2025-10-22 15:00:00", "2026-03-29 23:00:00", freq="h")
    hour = rng.hour
    rgen = np.random.default_rng(50)
    base = np.where((hour >= 2) & (hour <= 4), 0.8, 6.4) + rgen.random(len(rng)) * 0.5
    recent_start = len(rng) - 24 * 29
    base[recent_start:] += np.where((hour[recent_start:] >= 2) & (hour[recent_start:] <= 4), 5.5, 0.0)
    path = write_customer_csv(rng, base, filename="commercial_ramadan_bypass.csv")

    result = analyze_leak_production_grade(path, "Commercial")

    assert result["MNF_Applicable"] is False
    assert result["Trough_Detection_Method"] == "ramadan_seasonal_override"


def test_no_confound_outside_known_periods(write_customer_csv):
    """A window fully outside any known confound period should show no flag."""
    rng = pd.date_range("2026-05-06 15:00:00", "2026-09-29 23:00:00", freq="h")
    rgen = np.random.default_rng(44)
    hour = rng.hour
    base = np.where((hour >= 1) & (hour <= 4), 0.01, 0.15) + rgen.random(len(rng)) * 0.02
    path = write_customer_csv(rng, base, filename="no_confound.csv")

    result = analyze_leak_production_grade(path, "Residential")

    assert result["Seasonal_Confound_Recent"] is None
