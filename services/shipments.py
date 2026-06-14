from database import get_db_connection
from services.audit import log_action
from datetime import datetime
import logging
import pandas as pd

_UNSET = object()


def _generate_shipment_number(cursor, db) -> str:
    today = datetime.now().strftime('%Y-%m-%d')
    db.execute(cursor, "SELECT COUNT(*) FROM shipments WHERE date_shipped = %s", (today,))
    count = cursor.fetchone()[0]
    return f"SHP-{today}-{count+1:03d}"


def create_shipment(batch_ids: list, destination=None, notes=None):
    """
    Groups batch_ids into one shipment. All batches must be status='Ready'.
    Returns the new shipment_id on success, None on unexpected error.
    Raises ValueError if any batch is not found or not Ready.
    """
    db = get_db_connection()
    cursor = db.cursor()
    try:
        # Read pass — validate every batch before writing anything
        for batch_id in batch_ids:
            db.execute(cursor, "SELECT status FROM batches WHERE batch_id = %s", (batch_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Batch {batch_id} not found.")
            if row[0] != 'Ready':
                raise ValueError(f"Batch {batch_id} has status '{row[0]}' — only Ready batches can be shipped.")

        today = datetime.now().strftime('%Y-%m-%d')
        shipment_number = _generate_shipment_number(cursor, db)

        db.execute(cursor, """
            INSERT INTO shipments (shipment_number, date_shipped, destination, notes)
            VALUES (%s, %s, %s, %s)
        """, (shipment_number, today, destination, notes))
        shipment_id = db.get_last_insert_id(cursor)

        for batch_id in batch_ids:
            db.execute(cursor, """
                UPDATE batches
                SET status = 'Shipped', date_shipped = %s, shipment_id = %s
                WHERE batch_id = %s
            """, (today, shipment_id, batch_id))

        db.commit()
        log_action('shipment_created', f"shipment_id={shipment_id}, number={shipment_number}, batches={batch_ids}")
        return shipment_id

    except ValueError:
        db.rollback()
        raise

    except Exception as e:
        logging.error(f"Error creating shipment: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def get_all_shipments(page=None, per_page=50):
    """
    Returns (DataFrame, total) of all shipments with batch count.
    page=None returns all records without LIMIT (used by /manage-shipments).
    """
    db = get_db_connection()
    cursor = db.cursor()

    columns = ['shipment_id', 'shipment_number', 'date_shipped', 'destination', 'notes', 'batch_count']
    base_query = """
    SELECT s.shipment_id, s.shipment_number, s.date_shipped, s.destination, s.notes,
           COUNT(b.batch_id) AS batch_count
    FROM shipments s
    LEFT JOIN batches b ON b.shipment_id = s.shipment_id
    GROUP BY s.shipment_id, s.shipment_number, s.date_shipped, s.destination, s.notes
    ORDER BY s.shipment_id DESC
    """

    try:
        if page is None:
            db.execute(cursor, base_query)
            result = cursor.fetchall()
            return (pd.DataFrame(result, columns=columns), None)

        db.execute(cursor, "SELECT COUNT(*) FROM shipments")
        total = cursor.fetchone()[0]

        offset = (page - 1) * per_page
        db.execute(cursor, base_query + " LIMIT %s OFFSET %s", (per_page, offset))
        result = cursor.fetchall()
        return (pd.DataFrame(result, columns=columns), total)

    except Exception as e:
        logging.error(f"Error getting shipments: {e}")
        return (pd.DataFrame(), 0)

    finally:
        db.close()


def get_shipment_by_id(shipment_id):
    """
    Returns {'shipment': dict, 'batches': list of dicts} or None if not found.
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
            SELECT shipment_id, shipment_number, date_shipped, destination, notes
            FROM shipments WHERE shipment_id = %s
        """, (shipment_id,))
        row = cursor.fetchone()
        if not row:
            return None

        shipment = {
            'shipment_id': row[0],
            'shipment_number': row[1],
            'date_shipped': row[2],
            'destination': row[3],
            'notes': row[4],
        }

        db.execute(cursor, """
            SELECT batch_id, batch_number, product_name, quantity, date_completed, expiration_date
            FROM batches WHERE shipment_id = %s
            ORDER BY batch_id ASC
        """, (shipment_id,))
        batch_rows = cursor.fetchall()
        batches = [
            {
                'batch_id': r[0],
                'batch_number': r[1],
                'product_name': r[2],
                'quantity': r[3],
                'date_completed': r[4],
                'expiration_date': r[5],
            }
            for r in batch_rows
        ]

        return {'shipment': shipment, 'batches': batches}

    except Exception as e:
        logging.error(f"Error getting shipment {shipment_id}: {e}")
        return None

    finally:
        db.close()


def update_shipment(shipment_id, destination=_UNSET, notes=_UNSET):
    """
    Updates editable fields on a shipment. Uses sentinel so None can explicitly clear a field.
    Returns True on success, None on exception. Raises ValueError if shipment not found.
    """
    db = get_db_connection()
    cursor = db.cursor()

    fields = {}
    if destination is not _UNSET:
        fields['destination'] = destination
    if notes is not _UNSET:
        fields['notes'] = notes

    if not fields:
        return True

    try:
        set_clause = ', '.join(f"{k} = %s" for k in fields)
        params = (*fields.values(), shipment_id)
        db.execute(cursor, f"UPDATE shipments SET {set_clause} WHERE shipment_id = %s", params)

        if cursor.rowcount == 0:
            raise ValueError(f"Shipment {shipment_id} not found — nothing updated.")

        db.commit()
        log_action('shipment_updated', f"shipment_id={shipment_id}, fields={list(fields.keys())}")
        return True

    except ValueError:
        db.rollback()
        raise

    except Exception as e:
        logging.error(f"Error updating shipment {shipment_id}: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def delete_shipment(shipment_id):
    """
    Resets all Shipped batches in the shipment back to Ready, then deletes the shipment.
    Returns True on success, None on exception. Raises ValueError if shipment not found.
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
            UPDATE batches
            SET status = 'Ready', date_shipped = NULL, shipment_id = NULL
            WHERE shipment_id = %s AND status = 'Shipped'
        """, (shipment_id,))

        db.execute(cursor, "DELETE FROM shipments WHERE shipment_id = %s", (shipment_id,))

        if cursor.rowcount == 0:
            raise ValueError(f"Shipment {shipment_id} not found — nothing deleted.")

        db.commit()
        log_action('shipment_deleted', f"shipment_id={shipment_id}")
        return True

    except ValueError:
        db.rollback()
        raise

    except Exception as e:
        logging.error(f"Error deleting shipment {shipment_id}: {e}")
        db.rollback()
        return None

    finally:
        db.close()
