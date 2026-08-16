"""
Database connection utilities.

Provides a single location for creating SQLite connections used
throughout the Water Leakage Detection System.

Author: Arlene
"""

from pathlib import Path
import sqlite3


from src.config import DATABASE_PATH


def get_connection():
    """
    Returns a SQLite database connection.
    """

    connection = sqlite3.connect(DATABASE_PATH)

    # Makes rows behave like dictionaries.
    # Instead of row[0], we can write row["KM_Number"].
    connection.row_factory = sqlite3.Row

    return connection