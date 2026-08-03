"""
Database wrapper for the production leak detection engine.

This module adapts SQLite data to the original
file-based leak detection engine without modifying
the validated algorithm.

Author: Arlene
"""

import tempfile
from pathlib import Path

from leak_detection_pipeline import analyze_leak_production_grade


def run_customer_detection(customer_id, category, consumption_df):

    raw = analyze_leak_production_grade(
        consumption_df=consumption_df,
        folder_type=category
    )

    result = {

        "KM_Number": customer_id,

        "DetectionStatus":
            "Leak Detected"
            if raw["Leak_Suspected"] == "YES"
            else "Normal",

        "LeakType": raw["Priority_Reasons"],

        "PriorityScore": raw["Priority_Score"],

        "PriorityLevel": raw["Priority_Tier"],

        "HistoricalNightFloor":
            raw["Historical_Night_Floor_m3"],

        "RecentNightFloor":
            raw["Recent_Night_Floor_m3"],

        "NightTroughRatio":
            raw["Night_Trough_Ratio"],

        "MK_PValue":
            raw["MK_P_Value"],

        "MK_SenSlope":
            raw["MK_Sen_Slope"],

        # Your detector currently doesn't calculate this
        "PeakZScore": None,

        "Evidence":
            raw["Priority_Reasons"],

        "DataCompleteness":
            raw["Data_Completeness_Recent"],

        # Not yet implemented
        "EstimatedWaterLoss": None,

        "EstimatedRevenueLoss": None,

        "Recommendation":
            raw["Details"],

        # Could later be generated with GPT
        "AISummary":
            raw["Details"],

        "FirstDetected": None,

        "LastDetected": None,
    }

    return result