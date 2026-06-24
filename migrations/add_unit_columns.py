# ADDED: units-conversion-layer feature — one-time, run-once migration for the
#        unit-of-measurement + conversion work.
"""Add the unit-of-measurement columns to an existing database.

This is a STANDALONE one-time script — it is deliberately NOT wired into
`create_database()` (services/setup.py) or `upgrade_schema()` (init_db.py), so
those setup files stay uncluttered. Fresh databases already get these columns
from the updated CREATE TABLE definitions; this script only patches a database
that existed before the feature.

What it does (idempotent — safe to run more than once):
  - raw_materials  : + dimension TEXT  (the existing `unit` column is the display unit)
  - recipe_materials: + unit TEXT
  - (PostgreSQL only) raw_material_lots.quantity      -> NUMERIC
  - (PostgreSQL only) recipe_materials.quantity_needed -> NUMERIC

It does NOT touch any data values. Per the plan, the handful of real
quantities are re-entered through the UI in the new base units after this runs.

Usage (from the project root, with the same .env the app uses):
    python migrations/add_unit_columns.py
"""

import os
import sys

# Make the project root importable when run as `python migrations/add_unit_columns.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection


def _sqlite_columns(db, cursor, table):
    """Return the set of existing column names for a SQLite table."""
    db.execute(cursor, f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _add_column_sqlite(db, cursor, table, column, coltype):
    """SQLite has no ADD COLUMN IF NOT EXISTS — check PRAGMA first, like setup.py does."""
    if column not in _sqlite_columns(db, cursor, table):
        db.execute(cursor, f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        print(f"  + {table}.{column} ({coltype})")
    else:
        print(f"  = {table}.{column} already present, skipped")


def migrate():
    db = get_db_connection()
    cursor = db.cursor()
    try:
        if db.is_postgres:
            print("PostgreSQL detected — adding columns and widening to NUMERIC.")
            # ADD COLUMN IF NOT EXISTS is native in PostgreSQL and idempotent.
            db.execute(cursor, "ALTER TABLE raw_materials   ADD COLUMN IF NOT EXISTS dimension TEXT")
            db.execute(cursor, "ALTER TABLE recipe_materials ADD COLUMN IF NOT EXISTS unit TEXT")
            # Quantities -> NUMERIC for exact gram storage. Re-running on a column that
            # is already NUMERIC is harmless.
            db.execute(cursor, "ALTER TABLE raw_material_lots ALTER COLUMN quantity TYPE NUMERIC")
            db.execute(cursor, "ALTER TABLE recipe_materials  ALTER COLUMN quantity_needed TYPE NUMERIC")
            print("  + raw_material_lots.quantity -> NUMERIC")
            print("  + recipe_materials.quantity_needed -> NUMERIC")
        else:
            print("SQLite detected — adding columns (type stays REAL locally).")
            _add_column_sqlite(db, cursor, "raw_materials", "dimension", "TEXT")
            _add_column_sqlite(db, cursor, "recipe_materials", "unit", "TEXT")

        db.commit()
        print("\nMigration complete. Next: set dimension/display_unit per material and "
              "re-enter stock in base units (grams for mass).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
