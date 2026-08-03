"""
Loads hourly customer consumption data into the SQLite database.

This script:
    1. Scans the consumption data folder.
    2. Reads each customer Excel file.
    3. Validates the data.
    4. Loads hourly consumption records into the database.

Author: Arlene
"""

from pathlib import Path
import re

import pandas as pd

from config import CONSUMPTION_DATA_DIR
from database import get_connection


# =============================================================================
# CONFIGURATION
# =============================================================================

TIME_COLUMN = "Hourly"
CONSUMPTION_COLUMN = "Consumption m3"


# =============================================================================
# SCAN CONSUMPTION FILES
# =============================================================================

def scan_consumption_files():
    """
    Scan the consumption data folder for Excel files.

    Returns
    -------
    list[Path]
        Sorted list of Excel files.
    """

    print("\nScanning consumption data folder...")

    folder = Path(CONSUMPTION_DATA_DIR)

    excel_files = sorted(
        list(folder.glob("*.xlsx")) +
        list(folder.glob("*.xls"))
    )

    if not excel_files:
        raise FileNotFoundError(
            f"No Excel files found in:\n{folder}"
        )

    print(f"Found {len(excel_files)} consumption files.")

    return excel_files


# =============================================================================
# EXTRACT CUSTOMER KM NUMBER
# =============================================================================

def extract_km_number(filepath):
    """
    Extract the customer KM Number from the filename.

    The filename may contain additional text, but must contain
    exactly one customer KM Number that exists in the database.

    Returns
    -------
    str
        Customer KM Number.

    Raises
    ------
    ValueError
        If no valid customer number or multiple customer numbers
        are found.
    """

    filename = Path(filepath).stem

    # Find every numeric sequence inside the filename
    candidates = re.findall(r"\d+", filename)

    if not candidates:
        raise ValueError(
            f"No numeric customer identifier found in '{filename}'."
        )

    connection = get_connection()

    try:

        cursor = connection.cursor()

        valid_matches = []

        for candidate in candidates:

            cursor.execute(
                """
                SELECT KM_Number
                FROM Customers
                WHERE KM_Number = ?
                """,
                (candidate,)
            )

            result = cursor.fetchone()

            if result:
                valid_matches.append(candidate)

    finally:

        connection.close()

    if len(valid_matches) == 0:

        raise ValueError(
            f"No valid customer KM Number found in '{filename}'."
        )

    if len(valid_matches) > 1:

        raise ValueError(
            f"Multiple customer KM Numbers found in '{filename}': "
            f"{valid_matches}"
        )

    return valid_matches[0]

# =============================================================================
# READ CONSUMPTION FILE
# =============================================================================

def read_consumption_file(filepath):
    """
    Read a customer consumption Excel file.

    The function automatically detects the header row,
    loads the data, converts timestamps, and sorts the records.

    Parameters
    ----------
    filepath : pathlib.Path

    Returns
    -------
    pandas.DataFrame
    """

    print(f"\nReading {filepath.name}...")

    header_row = 2

    df = pd.read_excel(
        filepath,
        header=header_row
    )
    print(df.columns)
    df[TIME_COLUMN] = pd.to_datetime(df[TIME_COLUMN])

    df = (
        df
        .sort_values(TIME_COLUMN)
        .drop_duplicates(subset=[TIME_COLUMN])
        .reset_index(drop=True)
    )

    print(f"Loaded {len(df)} hourly records.")

    return df


# =============================================================================
# DETECT HEADER ROW
# =============================================================================

def detect_header_row(filepath):
    """
    Detect the Excel header row automatically.

    Returns
    -------
    int
        Header row index.
    """

    preview = pd.read_excel(
        filepath,
        header=None,
        nrows=10
    )
    print(preview)

    for row_index in range(len(preview)):

        row = preview.iloc[row_index].astype(str).tolist()

        if (
            TIME_COLUMN in row and
            CONSUMPTION_COLUMN in row
        ):
            return row_index

    raise ValueError(
        f"Could not detect header row in {filepath.name}"
    )


# =============================================================================
# VALIDATE CONSUMPTION DATA
# =============================================================================

def validate_consumption_data(df):
    """
    Validate customer consumption data before importing.

    Checks
    ------
    - Required columns exist
    - Valid timestamps
    - Numeric consumption
    - Missing timestamps
    - Duplicate timestamps
    - Sorted chronologically

    Raises
    ------
    ValueError
        If validation fails.
    """

    print("Validating data...")

    # ----------------------------------------------------------
    # Required columns
    # ----------------------------------------------------------

    required_columns = [
        TIME_COLUMN,
        CONSUMPTION_COLUMN
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    # ----------------------------------------------------------
    # Missing timestamps
    # ----------------------------------------------------------

    if df[TIME_COLUMN].isna().any():

        raise ValueError(
            "Dataset contains missing timestamps."
        )

    # ----------------------------------------------------------
    # Numeric consumption
    # ----------------------------------------------------------

    df[CONSUMPTION_COLUMN] = pd.to_numeric(
        df[CONSUMPTION_COLUMN],
        errors="coerce"
    )

    # ----------------------------------------------------------
    # Duplicate timestamps
    # ----------------------------------------------------------

    duplicates = df[TIME_COLUMN].duplicated().sum()

    if duplicates > 0:

        raise ValueError(
            f"Dataset contains {duplicates} duplicate timestamps."
        )

    # ----------------------------------------------------------
    # Sorted timestamps
    # ----------------------------------------------------------

    if not df[TIME_COLUMN].is_monotonic_increasing:

        raise ValueError(
            "Dataset is not sorted chronologically."
        )

    print("Validation successful.")

    # ----------------------------------------------------------
    # Negative Consumption
    # ----------------------------------------------------------

    if (df[CONSUMPTION_COLUMN] < 0).any():

        negative_count = (df[CONSUMPTION_COLUMN] < 0).sum()

        raise ValueError(
            f"Dataset contains {negative_count} negative consumption values."
        )

    # ----------------------------------------------------------
    # Invalid Consumption Values
    # ----------------------------------------------------------

    if df[CONSUMPTION_COLUMN].isna().any():

        raise ValueError(
            "Dataset contains invalid or missing consumption values."
        )


# =============================================================================
# INSERT CONSUMPTION DATA
# =============================================================================

def insert_consumption_data(df, km_number):
    """
    Insert hourly consumption records into the database.

    Parameters
    ----------
    df : pandas.DataFrame
        Validated hourly consumption data.

    km_number : str
        Customer KM Number extracted from the filename.
    """

    print(f"Inserting consumption data for customer {km_number}...")

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ----------------------------------------------------------
        # Find KM_Number
        # ----------------------------------------------------------

        cursor.execute(
            """
            SELECT KM_Number
            FROM Customers
            WHERE KM_Number = ?
            """,
            (km_number,)
        )

        result = cursor.fetchone()

        if result is None:
            raise ValueError(
                f"Customer '{km_number}' does not exist in Customers table."
            )

        customer_id = result["KM_Number"]

        # ----------------------------------------------------------
        # Remove previous imported records (POC)
        # ----------------------------------------------------------

        cursor.execute(
            """
            DELETE FROM HourlyConsumption
            WHERE KM_Number = ?
            """,
            (customer_id,)
        )

        # ----------------------------------------------------------
        # Prepare records
        # ----------------------------------------------------------

        records = []

        for _, row in df.iterrows():
            records.append(
                (
                    customer_id,
                    row["Hourly"].strftime("%Y-%m-%d %H:%M:%S"),
                    float(row["Consumption m3"])
                )
            )

        # ----------------------------------------------------------
        # Bulk insert
        # ----------------------------------------------------------

        cursor.executemany(
            """
            INSERT INTO HourlyConsumption
            (
                KM_Number,
                Timestamp,
                ConsumptionM3
            )
            VALUES (?, ?, ?)
            """,
            records
        )

        connection.commit()

        print(f"Inserted {len(records)} hourly readings.")

    finally:

        connection.close()

# =============================================================================
# MAIN
# =============================================================================

def load_consumption():
    """
    Load all customer consumption files into the database.
    """

    print("=" * 60)
    print("Loading Customer Consumption Data")
    print("=" * 60)

    files = scan_consumption_files()

    imported_files = 0
    imported_records = 0
    failed_files = 0

    for file in files:
        print(file)
        print("\n" + "-" * 60)

        try:

            km_number = extract_km_number(file)

            print(f"Customer KM Number : {km_number}")

            df = read_consumption_file(file)
            print(df)

            validate_consumption_data(df)

            insert_consumption_data(df, km_number)

            imported_files += 1
            imported_records += len(df)

            print(f"[SUCCESS] {file.name}")

        except Exception as e:

            print(f"[FAILED] {file.name}")
            failed_files += 1

            print(e)

            # Continue loading the remaining files
            continue

    print("\n" + "=" * 60)
    print("Import Summary")
    print("=" * 60)

    print(f"Files Found      : {len(files)}")
    print(f"Files Imported   : {imported_files}")
    print(f"Files Failed     : {failed_files}")
    print(f"Hourly Records   : {imported_records:,}")

    print("\nConsumption import completed.")


if __name__ == "__main__":

    load_consumption()