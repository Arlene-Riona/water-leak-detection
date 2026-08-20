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
WATER_TARIFFS = {
    "Residential": 4.4,
    "Villa": 4.4,
    "Flat": 4.4,
    "Commercial": 5.2,
    "Hotel": 5.2,
    "Industrial": 4.4,
    "Government": 7.0,
    "Productive Farm": 5.2,
}


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

    historical_daily = raw["Historical_Daily_Median_Consumption_m3"]
    recent_daily = raw["Recent_Daily_Median_Consumption_m3"]

    # -------------------------------------------------------------------------
    # Determine applicable water tariff
    # -------------------------------------------------------------------------

    if "Government" in category:
        tariff = 7.0

    elif "Industrial" in category:
        tariff = 4.4

    elif (
        "Commercial" in category
        or "Hotel" in category
        or "Farm" in category
    ):
        tariff = 5.2

    elif (
        "Residential" in category
        or "Villa" in category
        or "Flat" in category
    ):
        tariff = 4.4

    else:
        tariff = 4.4

    # -------------------------------------------------------------------------
    # Business Impact Estimation
    # -------------------------------------------------------------------------

    estimated_water_loss = None
    estimated_revenue_loss = None
    estimation_method = None

    # Consumption Baseline Estimate
    #
    # Used only when Minimum Night Flow cannot be evaluated.
    # Assumes any sustained increase in median daily consumption
    # represents potential leakage.

    if raw["Leak_Suspected"] == "YES":

        # Method 1 - Minimum Night Flow
        if historical_night_floor is not None and recent_night_floor is not None:

            estimated_water_loss = max(
                0,
                recent_night_floor - historical_night_floor
            ) * 24

            estimation_method = "Minimum Night Flow"

        # Method 2 - Burst Excess Volume
        elif raw["Cumulative_Burst_Max_Excess_m3"] is not None:

            estimated_water_loss = raw["Cumulative_Burst_Max_Excess_m3"]

            estimation_method = "Burst Excess Volume"

        # Method 3 - Consumption Baseline Estimate
        elif (
            historical_daily is not None
            and recent_daily is not None
        ):

            estimated_water_loss = max(
                0,
                recent_daily - historical_daily
            )

            estimation_method = "Consumption Baseline Estimate"

        # Revenue loss (AFTER the final water loss is known)
        if estimated_water_loss is not None:

            estimated_revenue_loss = estimated_water_loss * tariff

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

        "Recent_Vs_Baseline_Pct_Change":
            raw["Recent_Vs_Baseline_Pct_Change"],

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

        "EstimationMethod":
            estimation_method,

        "AppliedTariff":
            tariff,

        "Recommendation":
            raw["Details"],

        # Future enhancement
        "AISummary":
            raw["Details"],

        # ---------------------------------------------------------------------
        # Residential Consumption Profile Check
        # ---------------------------------------------------------------------

        "Consumption_Profile_Status":
            raw.get("Consumption_Profile_Status"),

        "Consumption_Profile_Reason":
            raw.get("Consumption_Profile_Reason"),

        "Consumption_Profile_Threshold_m3":
            raw.get("Consumption_Profile_Threshold_m3"),

        "Consumption_Profile_Days_Checked":
            raw.get("Consumption_Profile_Days_Checked"),

        # FirstDetected will be preserved by run_detection.py
        "FirstDetected":
            None,

        # Updated every pipeline execution
        "LastDetected":
            current_timestamp,

        "TimelineData":
            raw.get("TimelineData", []),

    }

    return result