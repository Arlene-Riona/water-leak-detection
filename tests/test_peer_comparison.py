"""
Tests for the portfolio-level peer/cohort comparison pass. These run through
the crawler (run_portfolio_leak_audit), not the single-file function, since
peer comparison only exists at that level.
"""
import numpy as np
import pandas as pd
from leak_detection import run_portfolio_leak_audit


def _write_cohort(tmp_path, members, category="Commercial"):
    """
    members: list of (filename, seed, recent_multiplier, extra_addend) tuples.
    Every member shares the same base shape and gets `recent_multiplier`
    applied to the whole recent window (simulating a shared demand rise),
    plus `extra_addend` on top (simulating an individual leak).
    """
    rng = pd.date_range("2026-01-01", periods=24 * 7 * 12, freq="h")
    hour = rng.hour
    leak_start = len(rng) - 24 * 7 * 3
    folder = tmp_path / "customers" / category
    folder.mkdir(parents=True)
    for name, seed, multiplier, addend in members:
        rgen = np.random.default_rng(seed)
        base_level = 5.0
        base = np.where((hour >= 2) & (hour <= 4), base_level * 0.15, base_level) + rgen.random(len(rng)) * 0.3
        base[leak_start:] *= multiplier
        base[leak_start:] += addend
        pd.DataFrame({"Hourly": rng, "Consumption m3": base}).to_csv(folder / f"{name}.csv", index=False)
    return str(tmp_path / "customers")


def test_outlier_boosted_above_cohort(tmp_path):
    """
    A customer riding the same shared demand rise as their peers, PLUS a
    real additional leak on top, should stand out and get boosted -- not
    diluted by the shared cause. This is the specific design flaw that was
    caught and corrected before implementing peer comparison.
    """
    members = [(f"shared_{i}", 100 + i, 1.25, 0.0) for i in range(6)]
    members.append(("outlier", 999, 1.25, 3.5))
    base_folder = _write_cohort(tmp_path, members)

    results = run_portfolio_leak_audit(base_folder=base_folder)
    by_name = {r["Filename"]: r for r in results}
    outlier = by_name["outlier.csv"]

    assert outlier["Leak_Suspected"] == "YES"
    assert outlier["Peer_Z_Score"] is not None and outlier["Peer_Z_Score"] > 2.0
    assert outlier["Priority_Tier"] == "High - Dispatch"


def test_shared_cause_capped_but_not_erased(tmp_path):
    """
    Customers sharing an ordinary demand rise (no individual leak) should
    have their tier capped below auto-dispatch if it would've hit High, but
    the underlying evidence/score must remain visible, not be silently
    zeroed out.
    """
    members = [(f"shared_{i}", 100 + i, 1.25, 0.0) for i in range(6)]
    base_folder = _write_cohort(tmp_path, members)

    results = run_portfolio_leak_audit(base_folder=base_folder)
    flagged = [r for r in results if r["Leak_Suspected"] == "YES"]

    assert len(flagged) >= 1
    for r in flagged:
        assert r["Priority_Tier"] != "High - Dispatch"
        assert r["Peer_Comparison_Note"] is not None
        assert r["Priority_Score"] is not None and r["Priority_Score"] > 0


def test_small_cohort_skipped(tmp_path):
    """A cohort below the minimum size should be left untouched by peer logic."""
    members = [(f"c_{i}", 200 + i, 1.0, (2.0 if i == 0 else 0.0)) for i in range(3)]
    base_folder = _write_cohort(tmp_path, members, category="Government")

    results = run_portfolio_leak_audit(base_folder=base_folder)

    for r in results:
        assert r["Peer_Comparison_Note"] is not None
        assert "too small" in r["Peer_Comparison_Note"].lower()


def test_clean_cohort_peer_comparison_inert(tmp_path):
    """A cohort with no leaks at all should have nothing for peer logic to adjust."""
    members = [(f"clean_{i}", 300 + i, 1.0, 0.0) for i in range(6)]
    base_folder = _write_cohort(tmp_path, members)

    results = run_portfolio_leak_audit(base_folder=base_folder)

    assert all(r["Leak_Suspected"] == "NO" for r in results)
