# ADDED: these imports were all at the top of inventory_app.py — only the ones
#        actually used by the functions in this file are kept here.
from database import get_db_connection
import pandas as pd
from datetime import datetime
import logging


#=======================
#LOT NUMBER FUNCTIONS
#=======================

# read functions:

def get_lots_for_material(material_id):
    """
    returns all 'active' lots (lots where quantitiy > 0) for a given material_id.
    ordered by received_date ASC.

    will be used for batch creation drop down menu when choosing which lots to deduct from.

    """

    db = get_db_connection()
    cursor = db.cursor()
    try:
        date_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        db.execute(cursor,"""
        SELECT rm_lot.lot_id, rm.name AS material_name, rm_lot.lot_number, rm_lot.quantity, rm_lot.received_date, rm_lot.status, rm_lot.expiration_date
        FROM raw_material_lots rm_lot
        JOIN raw_materials rm ON rm_lot.material_id = rm.material_id
        WHERE rm_lot.material_id = %s AND rm_lot.quantity > 0 AND rm_lot.status = 'active' AND (rm_lot.expiration_date IS NULL OR rm_lot.expiration_date > %s)
        ORDER BY rm_lot.received_date ASC

                    """, (material_id, date_now,))
        result = cursor.fetchall()
        columns = ['lot_id', 'material_name', 'lot_number', 'quantity', 'received_date', 'status', 'expiration_date']
        df = pd.DataFrame(result, columns=columns)
        return df

    except Exception as e:
        logging.error(f"Error fetching lots for material (batch drop down function) {material_id}: {e}")
        return None

    finally:
        db.close()


def get_all_lots_for_material(material_id):
    """
    same as above, but includes exired and exhausted lots
    will be used for inventory page

    returns:
    lot_id, lot_number, lot_quantity, lot_recieved_date, lot_status, lot_expiration_date, lot_location.

    """

    db = get_db_connection()
    cursor = db.cursor()
    try:


        db.execute(cursor,"""
        SELECT rm_lot.lot_id, rm_lot.lot_number, rm_lot.quantity, rm_lot.received_date, rm_lot.status, rm_lot.expiration_date, rm_lot.location, rm_lot.cost_per_unit
        FROM raw_material_lots rm_lot
        JOIN raw_materials rm ON rm_lot.material_id = rm.material_id
        WHERE rm_lot.material_id = %s
        ORDER BY rm_lot.received_date ASC

                    """, (material_id,))
        result = cursor.fetchall()
        columns = ['lot_id', 'lot_number', 'quantity', 'received_date', 'status', 'expiration_date', 'location', 'cost_per_unit']
        df = pd.DataFrame(result, columns=columns)
        return df

    except Exception as e:
        logging.error(f"Error fetching lots for material (inventory page function) {material_id}: {e}")
        return None

    finally:
        db.close()


def get_material_stock_from_lots(material_id):

    """
    Used to get stock level by diriving from SUM of active lots with given material_id.

    used for reading stock level directly.


    """
    db = get_db_connection()
    cursor = db.cursor()
    try:
        date_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute(cursor, """
        SELECT SUM(quantity) FROM raw_material_lots
        WHERE material_id = %s AND status = 'active' AND (expiration_date IS NULL OR expiration_date > %s)
        """, (material_id, date_now,))
        result = cursor.fetchone()
        return result[0] if result[0] is not None else 0.0

    except Exception as e:
        logging.error(f"Error getting stock from lots for material (for stock_level of material_id) {material_id}: {e}")
        return None

    finally:
        db.close()


#Write functions:

def receive_lot(material_id, lot_number, quantity, received_date, expiry_date=None, location=None, supplier=None):
    """
    adds new row into raw_material_lots

    validates that quantity > 0

    will be used when needed to add to a material via a new lot.

    """

    db = get_db_connection()
    cursor = db.cursor()

    try:

        #validate quantity:
        if (quantity is None) or (quantity <= 0):
            raise ValueError("Quantity must be a positive number.")


        db.execute(cursor, """
        INSERT INTO raw_material_lots (material_id, lot_number, quantity, received_date, expiration_date, location, supplier)
        VALUES(%s, %s, %s, %s, %s, %s, %s)
                   """,(material_id, lot_number, quantity, received_date, expiry_date, location, supplier))


        if cursor.rowcount == 0:
                raise ValueError(f"LOT ID not found — nothing updated when receiving lot {lot_number}")

        lot_id = db.get_last_insert_id(cursor)



        logging.info(f"Added lot number {lot_number} for material id:{material_id} with quantity {quantity}")
        db.commit()
        return lot_id


    except ValueError as e:
        logging.error(f"Value error adding new row to lot table. Error: {e}")
        db.rollback()
        return None

    except Exception as e:
        logging.error(f"Error adding a new row in lot numbers table. {material_id}/{lot_number}: {e}")
        db.rollback()
        return None

    finally:
        db.close()
