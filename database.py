"""
Database Connection Abstraction Layer

PURPOSE:
- Makes app work with BOTH SQLite (local) and PostgreSQL (cloud)
- Automatically detects which database to use based on environment
- No code changes needed when deploying!

HOW IT WORKS:
- Local dev: Uses SQLite (data/inventory.db)
- Cloud (Railway): Uses PostgreSQL (from DATABASE_URL env variable)
"""

import os
import sqlite3

# Try to import psycopg2 (only available when installed)
# This prevents import warnings in your IDE
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    # psycopg2 not installed (local development)
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

# Check if we're running in cloud
# Railway automatically sets DATABASE_URL environment variable
DATABASE_URL = os.getenv('DATABASE_URL')

print(f"[DEBUG] database.py: DATABASE_URL = {DATABASE_URL[:50] if DATABASE_URL else 'None'}...")
print(f"[DEBUG] database.py: PSYCOPG2_AVAILABLE = {PSYCOPG2_AVAILABLE}")


def get_connection():
   """
   Returns database connection based on environment.
   Returns:
     Connection object (sqlite3.Connection or psycopg2.Connection)

   Example usage:
       conn = get_connection()
       cursor = conn.cursor()
       cursor.execute("SELECT * FROM materials")
       conn.close()

   How it decides:
   - If DATABASE_URL exists → PostgreSQL (we're in cloud)
   - If DATABASE_URL is None → SQLite (we're local)
   """

   if DATABASE_URL:
       # ========================================
       # CLOUD MODE: Use PostgreSQL
       # ========================================
       print("[DEBUG] get_connection: Using PostgreSQL")

       if not PSYCOPG2_AVAILABLE:
           raise ImportError(
               "DATABASE_URL is set but psycopg2 is not installed. "
               "Install it with: pip install psycopg2-binary"
           )

       # Railway gives URL like: postgres://user:pass@host/db
       # psycopg2 expects: postgresql://user:pass@host/db
       # Fix: Replace "postgres://" with "postgresql://"
       connection_string = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

       print(f"[DEBUG] get_connection: Connecting to {connection_string[:50]}...")

       # Connect to PostgreSQL
       return psycopg2.connect(connection_string)

   else:
       # ========================================
       # LOCAL MODE: Use SQLite
       # ========================================
       print("[DEBUG] get_connection: Using SQLite (data/inventory.db)")
       return sqlite3.connect('data/inventory.db')


# ============================================================
# DATABASE WRAPPER CLASS
# ============================================================

class DatabaseConnection:
    """
    Wrapper around database connection that handles SQLite/PostgreSQL differences.

    KEY DIFFERENCES HANDLED:
    1. Parameter placeholders: %s (PostgreSQL) vs ? (SQLite)
    2. Last insert ID: LASTVAL() (PostgreSQL) vs cursor.lastrowid (SQLite)

    USAGE:
        from database import get_db_connection

        db = get_db_connection()
        cursor = db.cursor()

        # Write queries using %s (works for both databases!)
        db.execute(cursor, "SELECT * FROM users WHERE name = %s", (name,))

        # Get last inserted ID (works for both!)
        new_id = db.get_last_insert_id(cursor)

        db.commit()
        db.close()
    """

    def __init__(self, raw_connection):
        """
        Initialize wrapper around raw database connection.

        Args:
            raw_connection: Either sqlite3.Connection or psycopg2.Connection
        """
        self.conn = raw_connection
        self.is_postgres = DATABASE_URL is not None

        print(f"[DEBUG] DatabaseConnection: Initialized ({'PostgreSQL' if self.is_postgres else 'SQLite'} mode)")


    def cursor(self):
        """
        Get a cursor from the connection.

        Returns:
            Database cursor object
        """
        return self.conn.cursor()


    def commit(self):
        """Commit the current transaction."""
        return self.conn.commit()


    def rollback(self):
        """Rollback the current transaction."""
        return self.conn.rollback()


    def close(self):
        """Close the database connection."""
        return self.conn.close()


    def execute(self, cursor, query, params=None):
        """
        Execute a query with automatic parameter placeholder conversion.

        WHY THIS EXISTS:
        - PostgreSQL uses %s for parameters: "WHERE id = %s"
        - SQLite uses ? for parameters: "WHERE id = ?"
        - This method lets you write ALL queries with %s
        - It automatically converts %s to ? when using SQLite

        Args:
            cursor: Database cursor
            query: SQL query string (use %s for parameters)
            params: Tuple of parameter values

        Example:
            db.execute(cursor, "INSERT INTO users (name) VALUES (%s)", ("Alice",))
            # PostgreSQL: Runs as-is with %s
            # SQLite: Automatically converts to "... VALUES (?)"
        """
        if self.is_postgres:
            # PostgreSQL: Use query as-is (already has %s)
            cursor.execute(query, params)
        else:
            # SQLite: Convert %s to ?
            sqlite_query = query.replace('%s', '?')
            cursor.execute(sqlite_query, params)


    def get_last_insert_id(self, cursor):
        """
        Get the ID of the last inserted row.

        WHY THIS EXISTS:
        - PostgreSQL uses: SELECT LASTVAL()
        - SQLite uses: cursor.lastrowid
        - This method handles both automatically

        Args:
            cursor: The cursor that just performed an INSERT

        Returns:
            Integer ID of the last inserted row

        Example:
            db.execute(cursor, "INSERT INTO users (name) VALUES (%s)", ("Alice",))
            new_id = db.get_last_insert_id(cursor)
            print(f"New user ID: {new_id}")
        """
        if self.is_postgres:
            # PostgreSQL: Use LASTVAL() function
            cursor.execute("SELECT LASTVAL()")
            result = cursor.fetchone()[0]
            print(f"[DEBUG] get_last_insert_id (PostgreSQL): {result}")
            return result
        else:
            # SQLite: Use cursor.lastrowid property
            result = cursor.lastrowid
            print(f"[DEBUG] get_last_insert_id (SQLite): {result}")
            return result


# ============================================================
# WRAPPER CONVENIENCE FUNCTION
# ============================================================

def get_db_connection():
    """
    Returns DatabaseConnection wrapper (RECOMMENDED for new code).

    This provides automatic handling of SQLite/PostgreSQL differences.
    Use this instead of get_connection() for new code.

    Returns:
        DatabaseConnection wrapper object

    Example:
        db = get_db_connection()
        cursor = db.cursor()
        db.execute(cursor, "SELECT * FROM users WHERE id = %s", (user_id,))
        results = cursor.fetchall()
        db.close()
    """
    raw_conn = get_connection()  # Get the raw connection (sqlite3 or psycopg2)
    return DatabaseConnection(raw_conn)  # Wrap it