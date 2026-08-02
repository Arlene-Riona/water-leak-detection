"""
Project configuration.

Contains project-wide paths and configuration constants used by
the Water Leakage Detection Decision Support System.

Author: Arlene
"""

from pathlib import Path

# ============================================================================
# PROJECT ROOT
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ============================================================================
# DATABASE
# ============================================================================

DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "water_utility.db"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"

# ============================================================================
# DATA
# ============================================================================

DATA_DIR = PROJECT_ROOT / "data"

CUSTOMER_DATA_DIR = DATA_DIR / "customers"
CONSUMPTION_DATA_DIR = DATA_DIR / "consumption"

# ============================================================================
# RESULTS
# ============================================================================

RESULTS_DIR = PROJECT_ROOT / "results"

# ============================================================================
# DOCUMENTATION
# ============================================================================

DOCS_DIR = PROJECT_ROOT / "docs"

# ============================================================================
# NOTEBOOKS
# ============================================================================

NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"