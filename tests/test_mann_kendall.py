"""
Tests for the Mann-Kendall trend detection fallback (used when no reliable
night trough exists). Includes a regression guard for the false-positive
rate -- this is the exact class of check that caught the original CUSUM
version's 47% false-positive bug during development; keeping it automated
here means a future change can't silently reintroduce that class of bug.
"""
import os
import tempfile
import numpy as np
import pandas as pd
from leak_detection import analyze_leak_production_grade


def _make_247_series(seed, extra=0.0, leak_window_hours=24 * 7 * 3):
    rng = pd.date_range("2026-01-01", periods=24 * 7 * 12, freq="h")
    rgen = np.random.default_rng(seed)
    base = 20 + rgen.random(len(rng)) * 1.0
    if extra:
        leak_start = len(rng) - leak_window_hours
        base[leak_start:] += extra
    return rng, base


def test_clean_247_account_no_false_positive(write_customer_csv):
    rng, base = _make_247_series(seed=9000)
    path = write_customer_csv(rng, base)

    result = analyze_leak_production_grade(path, "Industrial")

    assert result["MNF_Applicable"] is False
    assert result["Leak_Suspected"] == "NO"


def test_sustained_leak_detected_via_mann_kendall(write_customer_csv):
    rng, base = _make_247_series(seed=9500, extra=0.5)  # ~2.5% sustained increase
    path = write_customer_csv(rng, base)

    result = analyze_leak_production_grade(path, "Industrial")

    assert result["MNF_Applicable"] is False
    assert result["MK_Evaluated"] is True
    assert result["Leak_Suspected"] == "YES"
    assert result["MK_P_Value"] is not None and result["MK_P_Value"] < 0.05
    assert result["MK_Sen_Slope"] is not None and result["MK_Sen_Slope"] > 0


def test_mk_false_positive_rate_stays_low():
    """
    Regression guard: false-positive rate on clean, leak-free 24/7 accounts
    must stay low. During development this exact check found a 47% false
    positive rate in an earlier (CUSUM-based) version of this fallback path.
    """
    trials = 20
    false_positives = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(trials):
            rng, base = _make_247_series(seed=20000 + i)
            path = os.path.join(tmp, f"clean_{i}.csv")
            pd.DataFrame({"Hourly": rng, "Consumption m3": base}).to_csv(path, index=False)
            result = analyze_leak_production_grade(path, "Industrial")
            if result["Leak_Suspected"] == "YES":
                false_positives += 1

    assert false_positives / trials <= 0.10, (
        f"MK false positive rate too high: {false_positives}/{trials}"
    )
