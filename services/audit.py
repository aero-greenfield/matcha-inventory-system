# ADDED: these imports were all at the top of inventory_app.py — only the ones
#        actually used by the functions in this file are kept here.
from database import get_db_connection
import pandas as pd
import logging


def log_action(action, details=None):
    """
    Writes an entry to the audit_log table.
    Called from app.py after any successful data mutation.

    action: short string describing what happened (e.g. 'material_added')
    details: optional string with relevant context (e.g. 'name=Matcha, stock=100')
    """
    db = get_db_connection()
    cursor = db.cursor()
    try:
        db.execute(cursor, """
            INSERT INTO audit_log (action, details)
            VALUES (%s, %s)
        """, (action, details))
        db.commit()
    except Exception as e:
        logging.error(f"Failed to write audit log: {e}")
    finally:
        db.close()

def view_logs():
    """
    View audit log — shows all recorded actions with timestamps.
    GET route, read-only.
    """
    db = get_db_connection()
    query = """SELECT action, details, timestamp
                FROM audit_log
                ORDER BY timestamp DESC LIMIT 200"""
    df = pd.read_sql_query(query, db.conn)
    db.close()
    return df