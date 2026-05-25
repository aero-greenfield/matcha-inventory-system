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
    from psycopg2 import pool as pg_pool  # ADDED: ThreadedConnectionPool lives here
    PSYCOPG2_AVAILABLE = True
except ImportError:
    # psycopg2 not installed (local development)
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    pg_pool = None

# Check if we're running in cloud
# Railway automatically sets DATABASE_URL environment variable
DATABASE_URL = os.getenv('DATABASE_URL')

# ISSUE: every get_db_connection() call opened a fresh TCP connection to PostgreSQL —
#        a full handshake on each service function call. A single HTTP request that calls
#        five service functions opens and destroys five connections serially.
# FIX: keep a module-level ThreadedConnectionPool alive for the process lifetime.
#      get_connection() draws from it; DatabaseConnection.close() returns to it.
#      SQLite is unaffected (no pool needed for a local file).

# ADDED: module-level pool singleton; None until first PostgreSQL connection is requested
_pool = None


def _init_pool():
    # ADDED: lazily creates the pool on first use so import-time startup isn't blocked
    #        by network. min=2 keeps two warm connections ready; max=10 caps concurrency
    #        at a safe level for Railway's free tier (which allows ~25 simultaneous conns).
    global _pool
    if _pool is None:
        connection_string = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        _pool = pg_pool.ThreadedConnectionPool(minconn=2, maxconn=10, dsn=connection_string)



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
       if not PSYCOPG2_AVAILABLE:
           raise ImportError(
               "DATABASE_URL is set but psycopg2 is not installed. "
               "Install it with: pip install psycopg2-binary"
           )

       # REMOVED: bare psycopg2.connect() — opened a new TCP connection on every call
       # return psycopg2.connect(connection_string)

       # ADDED: draw a connection from the pool (no TCP handshake if one is already warm)
       _init_pool()
       return _pool.getconn()

   else:
       # ========================================
       # LOCAL MODE: Use SQLite
       # ========================================
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
        """Close the database connection (or return it to the pool for PostgreSQL)."""
        # ISSUE: conn.close() destroyed the physical connection every time, so the next
        #        service function had to open a brand-new TCP connection.
        # FIX: for PostgreSQL, putconn() returns the connection to the pool so it stays
        #      alive and ready for the next caller. For SQLite, close() as before.
        if _pool is not None:
            # ADDED: return to pool instead of closing — connection stays alive
            _pool.putconn(self.conn)
        else:
            # SQLite: still close the file handle normally
            self.conn.close()


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
            return result
        else:
            # SQLite: Use cursor.lastrowid property
            return cursor.lastrowid


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