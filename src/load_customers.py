"""
Loads the customer master file into the SQLite database.

This script:
    1. Reads the customer master Excel file.
    2. Validates the data.
    3. Replaces the Customers table with the latest records.

The customer master file is considered the source of truth,
therefore the Customers table is fully refreshed each time
this script is executed.

Author: Arlene
"""

import pandas as pd

from config import CUSTOMER_MASTER_FILE
from database import get_connection


# =============================================================================
# CONFIGURATION
# =============================================================================

REQUIRED_COLUMNS = [
    "KM Number",
    "Name",
    "Zone",
    "Category",
    "Estimated Revenue QAR",
    "Peak Demand m3",
    "Total m3"
]

COLUMN_MAPPING = {
    "KM Number": "KM_Number",
    "Name": "Name",
    "Zone": "Zone",
    "Category": "Category",
    "Estimated Revenue QAR": "EstimatedRevenueQAR",
    "Peak Demand m3": "PeakDemandM3",
    "Total m3": "TotalConsumptionM3"
}


# =============================================================================
# READ CUSTOMER FILE
# =============================================================================

def read_customer_file():

    print("\nReading customer master file...")

    df = pd.read_excel(CUSTOMER_MASTER_FILE)

    # Keep only rows with numeric KM Numbers
    df = df[
        pd.to_numeric(df["KM Number"], errors="coerce").notna()
    ].copy()

    df["KM Number"] = df["KM Number"].astype(str).str.strip()
    df["Name"] = df["Name"].fillna("").astype(str).str.strip()
    df["Zone"] = df["Zone"].fillna("").astype(str).str.strip()
    df["Category"] = df["Category"].fillna("").astype(str).str.strip()

    print(f"Loaded {len(df)} customer records.")

    print(f"Rows after cleaning: {len(df)}")

    return df


# =============================================================================
# VALIDATE CUSTOMER DATA
# =============================================================================

def validate_customer_data(df):
    """
    Validate the customer master before importing.

    Checks:
        - Required columns exist
        - KM Numbers are unique
        - KM Numbers are not blank
        - Categories are not blank

    Raises
    ------
    ValueError
        If validation fails.
    """


    # -------------------------------------------------------------------------
    # Missing KM Numbers
    # -------------------------------------------------------------------------
    print(df["KM Number"])
    if df["KM Number"].isna().any():
        raise ValueError("Customer master contains blank KM Numbers.")

    # -------------------------------------------------------------------------
    # Duplicate KM Numbers
    # -------------------------------------------------------------------------

    duplicates = df[df["KM Number"].duplicated()]

    if not duplicates.empty:
        duplicate_ids = duplicates["KM Number"].tolist()

        raise ValueError(
            f"Duplicate KM Numbers found: {duplicate_ids}"
        )

    # -------------------------------------------------------------------------
    # Missing Categories
    # -------------------------------------------------------------------------

    if df["Category"].isna().any():
        raise ValueError(
            "Customer master contains missing categories."
        )

    print("Validation successful.")


# =============================================================================
# REPLACE CUSTOMER TABLE
# =============================================================================

def replace_customer_table(df):
    """
    Replace the Customers table with the latest customer master.

    Parameters
    ----------
    df : pandas.DataFrame
        Validated customer data.
    """

    print("\nUpdating Customers table...")

    df = df.rename(columns=COLUMN_MAPPING)

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("DELETE FROM Customers")

        # Reset AUTOINCREMENT (POC only)
        cursor.execute(
            "DELETE FROM sqlite_sequence WHERE name='Customers';"
        )

        customer_records = list(
            df[
                [
                    "KM_Number",
                    "Name",
                    "Zone",
                    "Category",
                    "EstimatedRevenueQAR",
                    "PeakDemandM3",
                    "TotalConsumptionM3"
                ]
            ].itertuples(index=False, name=None)
        )

        #print(df[df["Name"].isna()])

        cursor.executemany(
            """
            INSERT INTO Customers (
                KM_Number,
                Name,
                Zone,
                Category,
                EstimatedRevenueQAR,
                PeakDemandM3,
                TotalConsumptionM3
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            customer_records
        )

        connection.commit()

        print(f"Inserted {len(customer_records)} customers.")

    finally:

        connection.close()


# =============================================================================
# MAIN
# =============================================================================

def load_customers():
    """Load the customer master into the SQLite database."""

    print("=" * 60)
    print("Loading Customer Master")
    print("=" * 60)

    df = read_customer_file()

    validate_customer_data(df)

    replace_customer_table(df)

    print("\n[SUCCESS] Customer master imported successfully.")


if __name__ == "__main__":
    load_customers()