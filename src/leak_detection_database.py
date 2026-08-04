"""
Database wrapper for the production leak detection engine.

This module adapts SQLite data to the original
file-based leak detection engine without modifying
the validated algorithm.

Author: Arlene
"""

from datetime import datetime

from leak_detection_pipeline import analyze_leak_production_grade


# =============================================================================
# CONFIGURATION
# =============================================================================

# Placeholder tariff for the proof-of-concept.
# Replace with the official Kahramaa tariff if available.
WATER_TARIFF_QAR_PER_M3 = 4.5


# =============================================================================
# MAIN
# =============================================================================

def run_customer_detection(customer_id, category, consumption_df):

    raw = analyze_leak_production_grade(
        consumption_df=consumption_df,
        folder_type=category
    )

    # -------------------------------------------------------------------------
    # Estimated Daily Water Loss
    #
    # Uses the increase in Minimum Night Flow (MNF) as an estimate of
    # continuous leakage.
    #
    # Estimated Daily Water Loss =
    # (Recent Night Floor - Historical Night Floor) × 24 hours
    # -------------------------------------------------------------------------

    historical_night_floor = raw["Historical_Night_Floor_m3"]
    recent_night_floor = raw["Recent_Night_Floor_m3"]

    if (
        historical_night_floor is not None
        and recent_night_floor is not None
    ):

        estimated_water_loss = max(
            0,
            recent_night_floor - historical_night_floor
        ) * 24

        estimated_revenue_loss = (
            estimated_water_loss *
            WATER_TARIFF_QAR_PER_M3
        )

    else:

        estimated_water_loss = None
        estimated_revenue_loss = None

    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    result = {

        "KM_Number": customer_id,

        "DetectionStatus":
            "Leak Detected"
            if raw["Leak_Suspected"] == "YES"
            else "Normal",

        "LeakType":
            raw["Priority_Reasons"],

        "PriorityScore":
            raw["Priority_Score"],

        "PriorityLevel":
            raw["Priority_Tier"],

        "HistoricalNightFloor":
            historical_night_floor,

        "RecentNightFloor":
            recent_night_floor,

        "NightTroughRatio":
            raw["Night_Trough_Ratio"],

        "MK_PValue":
            raw["MK_P_Value"],

        "MK_SenSlope":
            raw["MK_Sen_Slope"],

        # Future enhancement
        "PeakZScore":
            None,

        "Evidence":
            raw["Priority_Reasons"],

        "DataCompleteness":
            raw["Data_Completeness_Recent"],

        # ---------------------------------------------------------------------
        # Newly Implemented Business Metrics
        # ---------------------------------------------------------------------

        "EstimatedWaterLoss":
            estimated_water_loss,

        "EstimatedRevenueLoss":
            estimated_revenue_loss,

        "Recommendation":
            raw["Details"],

        # Future enhancement
        "AISummary":
            raw["Details"],

        # FirstDetected will be preserved by run_detection.py
        "FirstDetected":
            None,

        # Updated every pipeline execution
        "LastDetected":
            current_timestamp,
    }

    return result