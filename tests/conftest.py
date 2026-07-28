"""
Shared pytest fixtures for the water leak detection test suite.

Adds src/ to the import path so tests can `from leak_detection import ...`
without needing the package installed.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pandas as pd
import numpy as np
import pytest


@pytest.fixture
def make_hourly_series():
    """
    Returns a helper that builds a synthetic hourly consumption series with a
    configurable night trough. Defaults produce a clean, leak-free
    Residential-shaped account over a 12-week window.
    """
    def _make(
        start="2026-01-01",
        periods=24 * 7 * 12,
        night_hours=(1, 2, 3, 4),
        day_level=0.15,
        night_level=0.01,
        noise=0.02,
        seed=0,
    ):
        rng = pd.date_range(start, periods=periods, freq="h")
        hour = rng.hour
        rgen = np.random.default_rng(seed)
        base = np.where(np.isin(hour, night_hours), night_level, day_level) + rgen.random(len(rng)) * noise
        return rng, base

    return _make


@pytest.fixture
def write_customer_csv(tmp_path):
    """Returns a helper that writes a (timestamps, values) series to a CSV file."""
    def _write(rng, values, filename="customer.csv"):
        path = tmp_path / filename
        pd.DataFrame({"Hourly": rng, "Consumption m3": values}).to_csv(path, index=False)
        return str(path)

    return _write
