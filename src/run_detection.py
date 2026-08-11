"""
Runs the complete leak detection pipeline.

Workflow
--------
1. Read all customers from the database.
2. Load hourly consumption from SQLite.
3. Execute leak detection.
4. Save current detection results.
5. Save historical detection record.
6. Record algorithm run summary.

Author: Arlene
"""

import time

import pandas as pd

from database import get_connection
from leak_detection_database import run_customer_detection


# =============================================================================
# DATABASE HELPERS
# =============================================================================

def get_all_customers(connection):
    """
    Retrieve all customers stored in the database.
    """

    query = """
    SELECT
        KM_Number,
        Name,
        Category
    FROM Customers
    ORDER BY KM_Number
    """

    return pd.read_sql_query(query, connection)


def load_customer_consumption(connection, customer_id):
    """
    Load one customer's hourly consumption history.
    """

    query = """
    SELECT
        Timestamp,
        ConsumptionM3
    FROM HourlyConsumption
    WHERE KM_Number = ?
    ORDER BY Timestamp
    """

    df = pd.read_sql_query(
        query,
        connection,
        params=(customer_id,)
    )

    df["Timestamp"] = pd.to_datetime(df["Timestamp"])

    return df

# =============================================================================
# SAVE CURRENT RESULT
# =============================================================================

def save_detection_result(connection, result):
    """
    Update the latest detection result for one customer.
    """

    cursor = connection.cursor()

    # -------------------------------------------------------------------------
    # Preserve FirstDetected across pipeline runs
    # -------------------------------------------------------------------------

    cursor.execute(
        """
        SELECT FirstDetected
        FROM DetectionResults
        WHERE KM_Number = ?
        """,
        (result["KM_Number"],)
    )

    existing = cursor.fetchone()

    if existing and existing[0] is not None:
        first_detected = existing[0]
    else:
        first_detected = result["LastDetected"]

    cursor.execute(
        """
        INSERT OR REPLACE INTO DetectionResults (

            KM_Number,
            DetectionStatus,
            LeakType,
            PriorityScore,
            PriorityLevel,
            HistoricalNightFloor,
            RecentNightFloor,
            RecentVsBaselinePctChange,
            NightTroughRatio,
            MK_PValue,
            MK_SenSlope,
            PeakZScore,
            Evidence,
            DataCompleteness,
            EstimatedWaterLoss,
            EstimatedRevenueLoss,
            EstimationMethod,
            AppliedTariff,
            Recommendation,
            AISummary,
            FirstDetected,
            LastDetected

        )

        VALUES (

            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?

        )
        """,
        (
            result["KM_Number"],
            result["DetectionStatus"],
            result["LeakType"],
            result["PriorityScore"],
            result["PriorityLevel"],
            result["HistoricalNightFloor"],
            result["RecentNightFloor"],
            result["Recent_Vs_Baseline_Pct_Change"],
            result["NightTroughRatio"],
            result["MK_PValue"],
            result["MK_SenSlope"],
            result["PeakZScore"],
            result["Evidence"],
            result["DataCompleteness"],
            result["EstimatedWaterLoss"],
            result["EstimatedRevenueLoss"],
            result["EstimationMethod"],
            result["AppliedTariff"],
            result["Recommendation"],
            result["AISummary"],
            first_detected,
            result["LastDetected"],
        ),
    )

def save_detection_timeline(connection, result):
    """
    Save the hourly investigation timeline for one customer.
    """

    cursor = connection.cursor()

    timeline = result.get("TimelineData", [])

    if not timeline:
        return

    # Replace the previous timeline for this customer
    cursor.execute(
        """
        DELETE FROM DetectionTimeline
        WHERE KM_Number = ?
        """,
        (result["KM_Number"],)
    )

    for row in timeline:

        cursor.execute(
            """
            INSERT INTO DetectionTimeline (

                KM_Number,
                Timestamp,
                Period,
                ConsumptionM3,
                BaselineM3,
                DeviationM3,
                ZScore,
                IsAnomaly,
                IsLeakSignal

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["KM_Number"],
                row["Timestamp"],
                row["Period"],
                row["ConsumptionM3"],
                row["BaselineM3"],
                row["DeviationM3"],
                row["ZScore"],
                row["IsAnomaly"],
                row["IsLeakSignal"],
            )
        )

# =============================================================================
# SAVE CURRENT HISTORY
# =============================================================================

def save_detection_history(connection, run_id, result):

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO DetectionHistory (

            RunID,
            KM_Number,
            DetectionStatus,
            LeakType,
            PriorityScore,
            HistoricalNightFloor,
            RecentNightFloor,
            RecentVsBaselinePctChange,
            NightTroughRatio,
            MK_PValue,
            MK_SenSlope,
            PeakZScore,
            Evidence,
            EstimatedWaterLoss,
            EstimatedRevenueLoss,
            EstimationMethod,
            AppliedTariff,
            Recommendation

        )

        VALUES (

            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?

        )
        """,
        (
            run_id,
            result["KM_Number"],
            result["DetectionStatus"],
            result["LeakType"],
            result["PriorityScore"],
            result["HistoricalNightFloor"],
            result["RecentNightFloor"],
            result["Recent_Vs_Baseline_Pct_Change"],
            result["NightTroughRatio"],
            result["MK_PValue"],
            result["MK_SenSlope"],
            result["PeakZScore"],
            result["Evidence"],
            result["EstimatedWaterLoss"],
            result["EstimatedRevenueLoss"],
            result["EstimationMethod"],
            result["AppliedTariff"],
            result["Recommendation"],
        ),
    )


# =============================================================================
# MAIN
# =============================================================================

def main():

    print("=" * 60)
    print("Water Leakage Detection Pipeline")
    print("=" * 60)

    start = time.time()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
    """
    INSERT INTO AlgorithmRuns (

        CustomersProcessed,
        LeaksDetected,
        RuntimeSeconds,
        Status

    )

    VALUES (?, ?, ?, ?)
    """,
    (
        0,
        0,
        0,
        "RUNNING"
    )
)

    run_id = cursor.lastrowid

    connection.commit()

    customers_processed = 0
    leaks_detected = 0

    try:

        customers = get_all_customers(connection)

        print(f"\nCustomers Found : {len(customers)}")

        for _, customer in customers.iterrows():

            customer_id = customer["KM_Number"]

            print(f"\nProcessing {customer_id}")

            df = load_customer_consumption(
                connection,
                customer_id
            )

            if df.empty:

                print("No consumption data. Skipping.")
                continue

            result = run_customer_detection(
                customer_id=customer_id,
                category=customer["Category"],
                consumption_df=df
            )

            save_detection_result(
                connection,
                result
            )

            save_detection_history(
                connection,
                run_id,
                result
            )

            save_detection_timeline(
                connection,
                result
            )

            connection.commit()

            customers_processed += 1

            if result["DetectionStatus"] == "Leak Detected":
                leaks_detected += 1

            print(
                f"Finished -> {result['DetectionStatus']}"
            )

        runtime = time.time() - start

        cursor.execute(
        """
        UPDATE AlgorithmRuns
        SET
            CustomersProcessed = ?,
            LeaksDetected = ?,
            RuntimeSeconds = ?,
            Status = ?
        WHERE RunID = ?
        """,
        (
            customers_processed,
            leaks_detected,
            runtime,
            "SUCCESS",
            run_id,
        ),
    )

        connection.commit()

        print("\n" + "=" * 60)
        print("Pipeline Summary")
        print("=" * 60)

        print(f"Customers Processed : {customers_processed}")
        print(f"Leaks Detected      : {leaks_detected}")
        print(f"Runtime             : {runtime:.2f} sec")

        print("\nPipeline completed successfully.")

    except Exception as e:

        runtime = time.time() - start

        cursor.execute(
        """
        UPDATE AlgorithmRuns
        SET
            CustomersProcessed = ?,
            LeaksDetected = ?,
            RuntimeSeconds = ?,
            Status = ?,
            ErrorMessage = ?
        WHERE RunID = ?
        """,
        (
            customers_processed,
            leaks_detected,
            runtime,
            "FAILED",
            str(e),
            run_id,
        ),
    )

        connection.commit()

        raise

    finally:

        connection.close()

        print("Database connection closed.")


if __name__ == "__main__":
    main()