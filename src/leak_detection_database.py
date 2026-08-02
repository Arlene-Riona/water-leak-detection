"""
Database wrapper for the production leak detection engine.

This module acts as the bridge between the SQLite pipeline and the
validated leak detection algorithm.

It intentionally contains no detection logic. All analysis is performed
by leak_detection.py.

Author: Arlene
"""

from pathlib import Path

from leak_detection import analyze_leak_production_grade


def run_customer_detection(customer_id, category, consumption_file):
    """
    Run leak detection for a single customer.

    Parameters
    ----------
    customer_id : str
        Unique customer identifier.

    category : str
        Customer category
        (Residential, Commercial, Government, Industrial, etc.)

    consumption_file : str | Path
        Path to the customer's consumption dataset.

    Returns
    -------
    dict
        Detection results produced by the leak detection engine,
        with the customer ID attached.
    """

    consumption_file = Path(consumption_file)

    results = analyze_leak_production_grade(
        file_path=str(consumption_file),
        folder_type=category
    )

    results["Customer_ID"] = customer_id
    results["Consumption_File"] = str(consumption_file)

    return results