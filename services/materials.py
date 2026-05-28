# ADDED: these imports were all at the top of inventory_app.py — only the ones
#        actually used by the functions in this file are kept here.
from database import get_db_connection
import pandas as pd
from datetime import datetime
import logging

_MATERIAL_UPDATABLE_COLS = frozenset({"name", "category", "stock_level", "unit", "reorder_level"})


def add_raw_material(name, category, unit, reorder_level, is_housemade=False):
    # adds material to raw_materials

    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, "SELECT material_id FROM raw_materials WHERE LOWER(name) = LOWER(%s)", (name,))
        if cursor.fetchone():
            return "duplicate"

        db.execute(cursor, """
            INSERT INTO raw_materials (name, category, unit, reorder_level, is_housemade)
            VALUES (%s,%s,%s,%s,%s)

                        """, (name, category, unit, reorder_level, is_housemade))

        db.commit()
        logging.info(f"added new material: {name}")
        return db.get_last_insert_id(cursor)

    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_low_stock_materials():
    "Return raw materials below if low on stock"

    db = get_db_connection()
    cursor = db.cursor()

    query = """

    SELECT name, category, stock_level, reorder_level, unit
    FROM raw_materials
    WHERE stock_level <= reorder_level
    ORDER BY (stock_level / NULLIF(reorder_level, 0))
    """
    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result


def get_all_materials(page=None, per_page=50):
    """
    Returns all materials. Stock is derived from SUM of active lot quantities.

    # ADDED: page/per_page pagination parameters.
    # page=None  → full table, no LIMIT (used by export routes and create-batch); returns (df, None)
    # page=int   → paginated slice; returns (df, total_material_count)
    """
    db = get_db_connection()
    cursor = db.cursor()
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        columns = ['material_id', 'name', 'category', 'stock_level', 'unit', 'reorder_level', 'is_housemade']

        # does not include expired lots in the stock quantity
        base_query = """
        SELECT rm.material_id, rm.name, rm.category,
               SUM(CASE WHEN rm_lot.quantity > 0 AND (rm_lot.expiration_date IS NULL OR rm_lot.expiration_date > %s)
                   THEN rm_lot.quantity ELSE 0 END) as stock_level,
               rm.unit, rm.reorder_level, rm.is_housemade
        FROM raw_materials rm
        LEFT JOIN raw_material_lots rm_lot ON rm.material_id = rm_lot.material_id
        GROUP BY rm.material_id
        ORDER BY category, name
        """

        if page is None:
            # ADDED: page=None → return full table without LIMIT (exports, create-batch)
            db.execute(cursor, base_query, (now,))
            result = cursor.fetchall()
            return (pd.DataFrame(result, columns=columns), None)

        # ADDED: get total row count for pagination metadata (one count per material, not per lot)
        db.execute(cursor, "SELECT COUNT(DISTINCT material_id) FROM raw_materials")
        total = cursor.fetchone()[0]

        # ADDED: append LIMIT/OFFSET for the requested page
        db.execute(cursor, base_query + " LIMIT %s OFFSET %s", (now, per_page, (page - 1) * per_page))
        result = cursor.fetchall()
        return (pd.DataFrame(result, columns=columns), total)

    except Exception as e:
        logging.error(f"Error getting all materials, (get_all_materials function) e: {e}")
        return (pd.DataFrame(), 0)

    finally:
        db.close()


def get_material_by_id(material_id):
    "Returns material given its material_id"
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        SELECT material_id, name, category, unit, reorder_level
        FROM raw_materials
        WHERE material_id = %s
                       """,(material_id,))
        result = cursor.fetchone()
        return result

    except Exception as e:
        logging.error(f"Error: {e}")
        return None

    finally:
        db.close()


def update_raw_material(material_id, name=None, category=None, stock_level=None, unit=None, reorder_level=None):
    """changes raw material info given id and which parameters are not None (ONLY CHANGES details, not stock level)"""

    db = get_db_connection()
    cursor = db.cursor()

    field = {} # dictionary to hold fields to update, only the ones that are not None

    #iterate through params, if not None, add to field dict to update
    for key, value in [("name", name), ("category", category), ("stock_level", stock_level), ("unit", unit), ("reorder_level", reorder_level)]:
        if value is not None:
            field[key] = value

    if not field: #empty dictionary, no fields to update
        print("No fields to update")
        return

    invalid = set(field) - _MATERIAL_UPDATABLE_COLS
    if invalid:
        raise ValueError(f"Invalid column name(s): {invalid}")

    try:
        # ISSUE: the loop issued one UPDATE per field — a separate round-trip for each column
        #        changed. 5 changed fields = 5 sequential SQL statements.
        # FIX: build the SET clause dynamically and run one multi-column UPDATE.
        #      Keys come from the hardcoded list above (not user input) so f-string is safe.

        # REMOVED: per-field UPDATE loop
        # for key in field:
        #     db.execute(cursor, f"UPDATE raw_materials SET {key} = %s WHERE material_id = %s", ...)

        # ADDED: single multi-column UPDATE replacing the loop
        set_clause = ', '.join(f"{key} = %s" for key in field)
        params = (*field.values(), material_id)  # *field.values() unpacks column values; material_id goes last for the WHERE
        db.execute(cursor, f"UPDATE raw_materials SET {set_clause} WHERE material_id = %s", params)

        if cursor.rowcount == 0:
            raise ValueError(f"material ID {material_id} not found — nothing updated")
        db.commit()
        logging.info(f"Updated material with id:{material_id}")

        return True

    except Exception as e:
        logging.error(f"Error changing material details: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def increase_raw_material(material_id, increase_amount):

    """ increases amount of material given its material_id and amount to add"""

    db = get_db_connection()
    cursor = db.cursor()

    try:

        db.execute(cursor, """
        SELECT material_id, stock_level, unit
        FROM raw_materials
        WHERE material_id = %s
        """, (material_id,))
        result = cursor.fetchone()
        # gets the result from the query in form of a tuple

        if not result:
            print(f"Material with ID {material_id} not found in raw_materials")
            return None
        # if the query doesnt work, tells user

        (material_id, current_stock, unit) = result # breaks tuple down to three new variables

        db.execute(cursor, """
        UPDATE raw_materials
        SET stock_level = stock_level + %s
        WHERE material_id = %s

        """, (increase_amount, material_id,) )
        db.commit()

        #get new stock level
        db.execute(cursor, """
        SELECT stock_level
        FROM raw_materials
        WHERE material_id = %s

         """, (material_id,))

        new_stock_level = cursor.fetchone()[0] # fetchone() returns a tuple, so get the first and only value in tuple instead of tuple
        db.close()
        print(f"Succesfully added, material with id:{material_id} is now at {new_stock_level}")
        return new_stock_level

    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def get_raw_material(name):

    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        SELECT material_id, name, reorder_level
        FROM raw_materials
        WHERE LOWER(name) = LOWER(%s)
                       """,(name,))
        result = cursor.fetchone()


        return result

    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def get_all_materials_with_id(page=None, per_page=50):
    # ADDED: page/per_page pagination parameters (same sentinel convention as get_all_materials).
    # page=None → full table; returns (df, None)
    # page=int  → paginated slice; returns (df, total_count)
    #
    # CHANGED: was pd.read_sql_query(query, db.conn) — converted to cursor approach so
    #          LIMIT/OFFSET params go through the %s→? wrapper consistently.

    db = get_db_connection()
    cursor = db.cursor()

    try:
        columns = ['material_id', 'name', 'category', 'stock_level', 'unit', 'reorder_level', 'is_housemade']
        base_query = """
        SELECT material_id, name, category, stock_level, unit, reorder_level, is_housemade
        FROM raw_materials
        ORDER BY category, name
        """

        if page is None:
            # ADDED: full table path — no LIMIT/OFFSET
            db.execute(cursor, base_query)
            result = cursor.fetchall()
            return (pd.DataFrame(result, columns=columns), None)

        # ADDED: count total materials for pagination metadata
        db.execute(cursor, "SELECT COUNT(*) FROM raw_materials")
        total = cursor.fetchone()[0]

        # ADDED: LIMIT/OFFSET for requested page
        db.execute(cursor, base_query + " LIMIT %s OFFSET %s", (per_page, (page - 1) * per_page))
        result = cursor.fetchall()
        return (pd.DataFrame(result, columns=columns), total)

    except Exception as e:
        logging.error(f"error getting all materials with id: {e}")
        return (pd.DataFrame(), 0)

    finally:
        db.close()

def decrease_raw_material(material_id, decrease_amount):
    """Decreases amount of material given its material_id and amount to subtract"""

    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        SELECT material_id, stock_level, unit
        FROM raw_materials
        WHERE material_id = %s
        """, (material_id,))
        result = cursor.fetchone()

        if not result:
            print(f"Material with ID {material_id} not found in raw_materials")
            return None

        (material_id, current_stock, unit) = result

        # Check if there's enough stock
        if current_stock < decrease_amount:
            print(f"Insufficient stock: Material with ID {material_id} has {current_stock} {unit}, but {decrease_amount} {unit} is needed")
            return None

        db.execute(cursor, """
        UPDATE raw_materials
        SET stock_level = stock_level - %s
        WHERE material_id = %s
        """, (decrease_amount, material_id))

        db.commit()

        # Get new stock level
        db.execute(cursor, """
        SELECT stock_level
        FROM raw_materials
        WHERE material_id = %s
        """, (material_id,))

        new_stock_level = cursor.fetchone()[0]
        print(f"Successfully deducted {decrease_amount} {unit} from material with ID :{material_id}. New stock level: {new_stock_level} {unit}")
        return new_stock_level

    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()

def delete_raw_material(material_id):

    """Deletes raw material from database given its material_id"""

    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        SELECT DISTINCT batch_id FROM batch_materials
        WHERE material_id = %s
        """, (material_id,))
        affected_batches = [row[0] for row in cursor.fetchall()]

        db.execute(cursor, """
        DELETE FROM raw_material_lots
        WHERE material_id = %s
        """, (material_id,))

        db.execute(cursor, """
        DELETE FROM recipe_materials
        WHERE material_id = %s
        """, (material_id,))

        db.execute(cursor, """
        DELETE FROM batch_materials
        WHERE material_id = %s
        """, (material_id,))

        db.execute(cursor, """
        DELETE FROM raw_materials
        WHERE material_id = %s
        """, (material_id,))

        if cursor.rowcount == 0:
            raise ValueError(f"Material ID {material_id} not found — nothing deleted")

        db.commit()
        logging.info(f"Deleted material with ID {material_id} from raw materials")
        return {"deleted": True, "affected_batches": affected_batches}

    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def get_housemade_materials():
    """
    returns all materials in RM that are is_housemade == True
    """
    try:
        db = get_db_connection()
        query = """
        SELECT name, stock_level, unit
        FROM raw_materials
        WHERE is_housemade = TRUE
        ORDER BY name

        """
        result = pd.read_sql_query(query, db.conn)
        db.close()
        return result

    except Exception as e:
        logging.error(f"Could not get housemade_materials df: {e}")
        return pd.DataFrame()

    finally:
        db.close()


def get_mix_stock(material_name):
    """Returns current stock_level for a housemade material by name. Returns 0.0 if not found."""
    db = get_db_connection()
    cursor = db.cursor()
    try:
        db.execute(cursor, """
            SELECT stock_level FROM raw_materials
            WHERE LOWER(name) = LOWER(%s) AND is_housemade = TRUE
        """, (material_name,))
        row = cursor.fetchone()
        return float(row[0]) if row else 0.0
    except Exception as e:
        logging.error(f"get_mix_stock: {e}")
        return 0.0
    finally:
        db.close()


def get_material_by_name(name):
    # ADDED: single-row lookup replacing the get_all_materials() + pandas filter pattern
    #        in /api/material-unit. One indexed seek; no JOIN, no GROUP BY, no aggregation.
    db = get_db_connection()
    cursor = db.cursor()
    try:
        db.execute(cursor,
            "SELECT name, unit FROM raw_materials WHERE LOWER(name) = LOWER(%s) LIMIT 1",
            (name,))
        return cursor.fetchone()  # (name, unit) tuple or None
    except Exception as e:
        logging.error(f"get_material_by_name: {e}")
        return None
    finally:
        db.close()


def get_material_names(q=""):
    # ADDED: lightweight name-search for the /api/materials autocomplete endpoint.
    #        Returns up to 50 names matching the search string; filtering happens in SQL,
    #        not by fetching the full table into Python.
    db = get_db_connection()
    cursor = db.cursor()
    try:
        db.execute(cursor,
            "SELECT name FROM raw_materials WHERE LOWER(name) LIKE LOWER(%s) ORDER BY name LIMIT 50",
            (f"%{q}%",))
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"get_material_names: {e}")
        return []
    finally:
        db.close()


def get_material_id(name):

    """
    get name of a product,
    returns its material_id

    used for recieve lot func in app.py


    """

    db = get_db_connection()
    cursor = db.cursor()

    try:

        db.execute(cursor, """
        SELECT material_id
        FROM raw_materials
        WHERE LOWER(name) = LOWER(%s)
        """, (name,))
        row = cursor.fetchone()
        return (row[0]) if row else None

    except Exception as e:
        logging.error(f"didnt find material_id for name,(for recieve lot func)")
        return None

    finally:
        db.close()
