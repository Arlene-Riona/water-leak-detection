"""
Tests for data ingestion edge cases: header row auto-detection, files with
too little history, and files that don't have the expected columns.
"""
import numpy as np
import pandas as pd
from leak_detection import analyze_leak_production_grade


def test_header_row_autodetected_with_extra_rows_above(tmp_path):
    """
    Files with title/metadata rows above the real header (a real quirk found
    in production data during development) should still parse correctly.
    """
    rng = pd.date_range("2026-01-01", periods=24 * 7 * 12, freq="h")
    hour = rng.hour
    rgen = np.random.default_rng(3)
    base = np.where((hour >= 1) & (hour <= 4), 0.01, 0.15) + rgen.random(len(rng)) * 0.02
    df = pd.DataFrame({"Hourly": rng, "Consumption m3": base})
    path = tmp_path / "with_extra_rows.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, startrow=2)  # 2 blank/title rows above the real header

    result = analyze_leak_production_grade(str(path), "Residential")

    assert result["Status"] == "SUCCESS"


def test_clean_header_still_works(tmp_path):
    """A file with a normal header at row 0 should be unaffected by the
    auto-detection logic added for the case above."""
    rng = pd.date_range("2026-01-01", periods=24 * 7 * 12, freq="h")
    hour = rng.hour
    rgen = np.random.default_rng(3)
    base = np.where((hour >= 1) & (hour <= 4), 0.01, 0.15) + rgen.random(len(rng)) * 0.02
    path = tmp_path / "clean_header.xlsx"
    pd.DataFrame({"Hourly": rng, "Consumption m3": base}).to_excel(path, index=False)

    result = analyze_leak_production_grade(str(path), "Residential")

    assert result["Status"] == "SUCCESS"


def test_insufficient_history_is_skipped_not_evaluated(tmp_path):
    """A file with less than 4 weeks of baseline history should be SKIPPED,
    not silently evaluated with an unreliable baseline."""
    rng = pd.date_range("2026-06-01", periods=24 * 10, freq="h")  # only 10 days total
    rgen = np.random.default_rng(4)
    base = rgen.random(len(rng)) * 0.2
    path = tmp_path / "too_short.csv"
    pd.DataFrame({"Hourly": rng, "Consumption m3": base}).to_csv(path, index=False)

    result = analyze_leak_production_grade(str(path), "Commercial")

    assert result["Status"] == "SKIPPED"
    assert result["Leak_Suspected"] == "NO"  # skipped, not a positive claim of "clean"


def test_missing_consumption_column_returns_error_not_crash(tmp_path):
    """A malformed file (wrong column name) should return a clear ERROR
    status rather than raising an unhandled exception."""
    rng = pd.date_range("2026-01-01", periods=24 * 7 * 12, freq="h")
    rgen = np.random.default_rng(5)
    df = pd.DataFrame({"Hourly": rng, "WrongColumn": rgen.random(len(rng))})
    path = tmp_path / "broken.xlsx"
    df.to_excel(path, index=False)

    result = analyze_leak_production_grade(str(path), "Commercial")

    assert result["Status"] == "ERROR"
    assert result["Details"] is not None
