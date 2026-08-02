"""
Creates the SQLite database from schema.sql.

This script should only be run when:
- setting up the project for the first time
- rebuilding the database from scratch

Author: Arlene
"""

from pathlib import Path
from database import get_connection, DATABASE_PATH


def create_database():
    """Create the SQLite database using schema.sql."""

    # Project root
    from config import SCHEMA_PATH


    print("=" * 60)
    print("Water Leakage Detection Database")
    print("=" * 60)

    print(f"Schema   : {SCHEMA_PATH}")
    print(f"Database : {DATABASE_PATH}")

    # Create database connection
    connection = get_connection()

    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as sql_file:
            schema = sql_file.read()

        connection.executescript(schema)

        connection.commit()

        print("\n[SUCCESS] Database created successfully.")
        print("[SUCCESS] Schema executed successfully.")

    except Exception as e:
        print(f"\n[ERROR] Database creation failed: {e}")

        raise

    finally:
        connection.close()

        print("\nConnection closed.")


if __name__ == "__main__":
    create_database()