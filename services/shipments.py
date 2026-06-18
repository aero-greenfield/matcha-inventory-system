from database import get_db_connection
from services.audit import log_action
from datetime import datetime
import logging
import pandas as pd

_UNSET = object()
_EPS = 1e-9  # float tolerance when comparing allocated REAL quantities against a batch total


def _generate_shipment_number(cursor, db) -> str:
    today = datetime.now().strftime('%Y-%m-%d')
    db.execute(cursor, "SELECT COUNT(*) FROM shipments WHERE date_shipped = %s", (today,))
    count = cursor.fetchone()[0]
    return f"SHP-{today}-{count+1:03d}"


def _batch_remaining(cursor, db, batch_id, exclude_shipment_id=None):
    """
    Remaining unshipped quantity of a batch = produced quantity - SUM of its allocations.
    Pass exclude_shipment_id to ignore this shipment's own current allocation (used when
    re-validating an edit, so a line can keep/raise its quantity up to the true remaining).
    Returns None if the batch does not exist.
    """
    db.execute(cursor, "SELECT quantity FROM batches WHERE batch_id = %s", (batch_id,))
    row = cursor.fetchone()
    if not row:
        return None
    total = row[0] or 0

    if exclude_shipment_id is None:
        db.execute(cursor, "SELECT COALESCE(SUM(quantity), 0) FROM shipment_batches WHERE batch_id = %s", (batch_id,))
    else:
        db.execute(cursor,
                   "SELECT COALESCE(SUM(quantity), 0) FROM shipment_batches WHERE batch_id = %s AND shipment_id != %s",
                   (batch_id, exclude_shipment_id))
    allocated = cursor.fetchone()[0] or 0
    return total - allocated


def _recompute_batch_status(cursor, db, batch_id):
    """
    Recompute a batch's shipment state from its allocations. Status is derived, not manually flipped:
      nothing allocated      -> 'Ready'
      0 < allocated < total  -> 'Partially Shipped'
      allocated >= total     -> 'Shipped'
    date_shipped becomes the latest date of the shipments it's on (NULL when none).
    Guarded to only touch produced batches — a 'Planned' batch (deferred production) is never
    changed by shipment logic.
    """
    db.execute(cursor, """
        UPDATE batches SET
            status = CASE
                WHEN (SELECT COALESCE(SUM(quantity), 0) FROM shipment_batches WHERE batch_id = %s) <= 0
                THEN 'Ready'
               
                WHEN (SELECT COALESCE(SUM(quantity), 0) FROM shipment_batches WHERE batch_id = %s) < quantity
                THEN 'Partially Shipped'
               
                ELSE 'Shipped'
            END,
            date_shipped = (SELECT MAX(s.date_shipped)
                            FROM shipment_batches sb
                            JOIN shipments s ON sb.shipment_id = s.shipment_id
                            WHERE sb.batch_id = %s)
        WHERE batch_id = %s AND status IN ('Ready', 'Partially Shipped', 'Shipped')
    """, (batch_id, batch_id, batch_id, batch_id))


def create_shipment(lines, destination=None, notes=None):
    """
    Creates one shipment drawing the given quantities from one or more batches.
    `lines` is a dict {batch_id: quantity}. Each batch must be produced (status 'Ready' or
    'Partially Shipped') and the requested quantity must not exceed its remaining quantity.
    Returns the new shipment_id on success, None on unexpected error.
    Raises ValueError on bad input (batch missing/not shippable/over-allocated).


    note-- this loops over each batch in lines, and does 2 queries per batch: (might be optimized in the future)
    """
    if not lines:
        raise ValueError("A shipment must include at least one batch.")

    db = get_db_connection()
    cursor = db.cursor()
    try:
        # Validation pass — no writes until every line checks out.
        normalized = {}
        for batch_id, qty in lines.items():
            batch_id = int(batch_id)
            qty = float(qty)
            if qty <= 0:
                continue  # skip blank/zero lines
            
           
            #check each batch status
            db.execute(cursor, "SELECT status FROM batches WHERE batch_id = %s", (batch_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Batch {batch_id} not found.")
            if row[0] not in ('Ready', 'Partially Shipped'):
                raise ValueError(f"Batch {batch_id} has status '{row[0]}' — only produced batches with "
                                 f"remaining quantity can be shipped.")

            #check remaining quantity of each batch
            remaining = _batch_remaining(cursor, db, batch_id)
            if qty > remaining + _EPS:
                raise ValueError(f"Batch {batch_id}: requested {qty} exceeds remaining {remaining}.")
            normalized[batch_id] = qty #add validated batch_id and quantity to the normalized dictionary

        if not normalized:
            raise ValueError("A shipment must include at least one batch with a positive quantity.")

         #validation done--

        today = datetime.now().strftime('%Y-%m-%d')
        shipment_number = _generate_shipment_number(cursor, db)

        db.execute(cursor, """
            INSERT INTO shipments (shipment_number, date_shipped, destination, notes)
            VALUES (%s, %s, %s, %s)
        """, (shipment_number, today, destination, notes))
        shipment_id = db.get_last_insert_id(cursor)

        for batch_id, qty in normalized.items():
            db.execute(cursor, """
                INSERT INTO shipment_batches (shipment_id, batch_id, quantity)
                VALUES (%s, %s, %s)
            """, (shipment_id, batch_id, qty))
            _recompute_batch_status(cursor, db, batch_id) # update the status of the batch

        db.commit()
        log_action('shipment_created', f"shipment_id={shipment_id}, number={shipment_number}, lines={normalized}")
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
    Returns (DataFrame, total) of all shipments with the number of batch lines on each.
    page=None returns all records without LIMIT (used by /manage-shipments).
    """
    db = get_db_connection()
    cursor = db.cursor()

    columns = ['shipment_id', 'shipment_number', 'date_shipped', 'destination', 'notes', 'batch_count']
    base_query = """
    SELECT s.shipment_id, s.shipment_number, s.date_shipped, s.destination, s.notes,
           COUNT(sb.shipment_batch_id) AS batch_count
    FROM shipments s
    LEFT JOIN shipment_batches sb ON sb.shipment_id = s.shipment_id
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
    Each batch line carries `quantity` (amount shipped on THIS shipment) plus `batch_quantity`
    (the batch's produced total, for reference).
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
            SELECT sb.shipment_batch_id, b.batch_id, b.batch_number, b.product_name,
                   sb.quantity, b.quantity, b.date_completed, b.expiration_date,
                   (SELECT product_unit FROM recipes
                    WHERE LOWER(recipes.product_name) = LOWER(b.product_name) LIMIT 1) AS product_unit
            FROM shipment_batches sb
            JOIN batches b ON sb.batch_id = b.batch_id
            WHERE sb.shipment_id = %s
            ORDER BY b.batch_id ASC
        """, (shipment_id,))
        batch_rows = cursor.fetchall()
        batches = [
            {
                'shipment_batch_id': r[0],
                'batch_id': r[1],
                'batch_number': r[2],
                'product_name': r[3],
                'quantity': r[4],         # amount shipped on this shipment
                'batch_quantity': r[5],   # batch produced total
                'date_completed': r[6],
                'expiration_date': r[7],
                'product_unit': r[8],
            }
            for r in batch_rows
        ]

        return {'shipment': shipment, 'batches': batches}

    except Exception as e:
        logging.error(f"Error getting shipment {shipment_id}: {e}")
        return None

    finally:
        db.close()


def update_shipment(shipment_id, destination=_UNSET, notes=_UNSET, lines=_UNSET):
    """
    Updates a shipment's editable fields and/or its batch lines.
    - destination/notes use the _UNSET sentinel so None can explicitly clear a field.
    - lines (dict {batch_id: quantity}), when provided, replaces the shipment's batch lines:
      batches absent from the dict (or with qty<=0) are removed, others are added/adjusted.
      Each batch's status/remaining is recomputed afterwards.
    Returns True on success, None on exception. Raises ValueError on bad input.
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, "SELECT shipment_id FROM shipments WHERE shipment_id = %s", (shipment_id,))
        if not cursor.fetchone():
            raise ValueError(f"Shipment {shipment_id} not found — nothing updated.")

        # --- field updates ---
        fields = {}
        if destination is not _UNSET:
            fields['destination'] = destination
        if notes is not _UNSET:
            fields['notes'] = notes
        if fields:
            set_clause = ', '.join(f"{k} = %s" for k in fields)
            params = (*fields.values(), shipment_id)
            db.execute(cursor, f"UPDATE shipments SET {set_clause} WHERE shipment_id = %s", params)

        # --- line edits ---
        if lines is not _UNSET:
            db.execute(cursor,
                       "SELECT batch_id, shipment_batch_id FROM shipment_batches WHERE shipment_id = %s",
                       (shipment_id,))
            existing = {r[0]: r[1] for r in cursor.fetchall()}

            new_lines = {}
            for batch_id, qty in lines.items():
                qty = float(qty)
                if qty <= 0:
                    continue
                new_lines[int(batch_id)] = qty

            if not new_lines:
                raise ValueError("A shipment must keep at least one batch line — delete the shipment instead.")

            # Validate every new/changed line against remaining (excluding this shipment's own allocation).
            for batch_id, qty in new_lines.items():
                remaining = _batch_remaining(cursor, db, batch_id, exclude_shipment_id=shipment_id)
                if remaining is None:
                    raise ValueError(f"Batch {batch_id} not found.")
                if qty > remaining + _EPS:
                    raise ValueError(f"Batch {batch_id}: requested {qty} exceeds remaining {remaining}.")

            affected = set(existing) | set(new_lines)

            # Remove lines no longer present.
            for batch_id, sbid in existing.items():
                if batch_id not in new_lines:
                    db.execute(cursor, "DELETE FROM shipment_batches WHERE shipment_batch_id = %s", (sbid,))

            # Add or adjust the rest.
            for batch_id, qty in new_lines.items():
                if batch_id in existing:
                    db.execute(cursor, "UPDATE shipment_batches SET quantity = %s WHERE shipment_batch_id = %s",
                               (qty, existing[batch_id]))
                else:
                    db.execute(cursor, "INSERT INTO shipment_batches (shipment_id, batch_id, quantity) VALUES (%s, %s, %s)",
                               (shipment_id, batch_id, qty))

            for batch_id in affected:
                _recompute_batch_status(cursor, db, batch_id)

        if not fields and lines is _UNSET:
            return True

        db.commit()
        log_action('shipment_updated',
                   f"shipment_id={shipment_id}, fields={list(fields.keys())}, lines_changed={lines is not _UNSET}")
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
    Deletes a shipment and its batch lines, then recomputes each affected batch's status/remaining
    (a batch returns toward 'Ready' if it has no other allocations).
    Returns True on success, None on exception. Raises ValueError if shipment not found.
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, "SELECT shipment_id FROM shipments WHERE shipment_id = %s", (shipment_id,))
        if not cursor.fetchone():
            raise ValueError(f"Shipment {shipment_id} not found — nothing deleted.")

        db.execute(cursor, "SELECT DISTINCT batch_id FROM shipment_batches WHERE shipment_id = %s", (shipment_id,))
        affected = [r[0] for r in cursor.fetchall()]

        db.execute(cursor, "DELETE FROM shipment_batches WHERE shipment_id = %s", (shipment_id,))
        db.execute(cursor, "DELETE FROM shipments WHERE shipment_id = %s", (shipment_id,))

        for batch_id in affected:
            _recompute_batch_status(cursor, db, batch_id)

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
