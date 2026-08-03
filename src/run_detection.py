"""
Runs the complete leak detection pipeline.

Workflow
--------
1. Read all customers from the database.
2. Locate each customer's consumption dataset.
3. Run the leak detection engine.
4. Store results in detection_results.

Author: Arlene
"""

from pathlib import Path
import sqlite3

from database import get_connection
from config import RAW_DATA_FOLDER
from leak_detection_database import run_customer_detection

def get_all_customers(connection):
    """
    Retrieve every customer stored in the database.
    """

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            customer_id,
            customer_name,
            category
        FROM customers
        ORDER BY customer_id
    """)

    return cursor.fetchall()

def get_all_customers(connection):
    """
    Retrieve every customer stored in the database.
    """

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            customer_id,
            customer_name,
            category
        FROM customers
        ORDER BY customer_id
    """)

    return cursor.fetchall()

def find_consumption_file(customer_id):
    """
    Search for the customer's consumption dataset.
    """

    customer_id = str(customer_id)

    for file in RAW_DATA_FOLDER.rglob("*"):

        if not file.is_file():
            continue

        if file.suffix.lower() not in [".xlsx", ".xls", ".csv"]:
            continue

        if customer_id in file.stem:
            return file

    return None

def save_detection_result(connection, result):
    """
    Store one detection result.
    """

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO detection_results (

            customer_id,
            status,
            leak_suspected,
            priority_score,
            priority_tier,
            priority_reasons,
            details,
            historical_night_floor,
            recent_night_floor,
            mnf_applicable,
            trough_detection_method,
            mk_p_value,
            data_completeness_recent,
            detection_timestamp

        )

        VALUES (

            ?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP

        )
        """,
        (
            result["Customer_ID"],
            result["Status"],
            result["Leak_Suspected"],
            result["Priority_Score"],
            result["Priority_Tier"],
            result["Priority_Reasons"],
            result["Details"],
            result["Historical_Night_Floor_m3"],
            result["Recent_Night_Floor_m3"],
            result["MNF_Applicable"],
            result["Trough_Detection_Method"],
            result["MK_P_Value"],
            result["Data_Completeness_Recent"],
        )
    )

    connection.commit()

def main():
    """
    Execute the complete leak detection pipeline.
    """

    print("=" * 60)
    print("Water Leakage Detection Pipeline")
    print("=" * 60)

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM detection_results")
    connection.commit()

    try:

        customers = get_all_customers(connection)

        print(f"\nCustomers found : {len(customers)}")

        processed = 0
        leaks_found = 0
        missing_files = 0

        for customer in customers:

            customer_id = customer["customer_id"]
            customer_name = customer["customer_name"]
            category = customer["category"]

            print(f"\nProcessing Customer {customer_id}")

            consumption_file = find_consumption_file(customer_id)

            if consumption_file is None:

                print("Consumption file not found.")

                missing_files += 1
                continue

            print(f"Found: {consumption_file.name}")

            results = run_customer_detection(
                customer_id=customer_id,
                category=category,
                consumption_file=consumption_file
            )

            save_detection_result(
                connection,
                results
            )

            processed += 1

            if results["Leak_Suspected"] == "YES":
                leaks_found += 1

            print(
                f"Finished ({results['Leak_Suspected']})"
            )

        print("\n" + "=" * 60)
        print("Pipeline Summary")
        print("=" * 60)

        print(f"Customers           : {len(customers)}")
        print(f"Processed           : {processed}")
        print(f"Leaks Found         : {leaks_found}")
        print(f"Missing Files       : {missing_files}")

        print("\nPipeline completed successfully.")

    finally:

        connection.close()

        print("Database connection closed.")

if __name__ == "__main__":
    main()    