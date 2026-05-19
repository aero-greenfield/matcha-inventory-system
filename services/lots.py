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

def receive_lot(material_id, lot_number, quantity, received_date, expiry_date=None, location=None, supplier=None, cost_per_unit=None):
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
        INSERT INTO raw_material_lots (material_id, lot_number, quantity, received_date, expiration_date, location, supplier, cost_per_unit)
        VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
                   """,(material_id, lot_number, quantity, received_date, expiry_date, location, supplier, cost_per_unit))


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


def get_all_lots(material_id=None):
    """
    returns all lots, for given material_id if provided, otherwise all materials. 
    
    returns:
    lot_id, lot_number, material_name, material_id, quantity, received_date, expiration, 
    location, supplier, cost_per_unit, status
    """

    db = get_db_connection()
    cursor = db.cursor()

    try:

        if material_id:

            db.execute(cursor, """
            SELECT rml.lot_id, rml.lot_number, rm.name AS material_name, rm.material_id,
            rml.quantity, rml.received_date, rml.expiration_date,
            rml.location, rml.supplier, rml.cost_per_unit, rml.status
            FROM raw_material_lots rml
            JOIN raw_materials rm ON rml.material_id = rm.material_id
            WHERE rml.material_id = %s 
            ORDER BY rm.name ASC, rml.received_date ASC           
                    
                    """, (material_id,))
            
            result = cursor.fetchall()
            columns = ['lot_id', 'lot_number', 'material_name', 'material_id', 'quantity', 'received_date', 'expiration_date', 'location', 'supplier', 'cost_per_unit', 'status']
            df = pd.DataFrame(result, columns=columns)
        else:
            db.execute(cursor, """
            SELECT rml.lot_id, rml.lot_number, rm.name AS material_name, rm.material_id,
            rml.quantity, rml.received_date, rml.expiration_date,
            rml.location, rml.supplier, rml.cost_per_unit, rml.status
            FROM raw_material_lots rml
            JOIN raw_materials rm ON rml.material_id = rm.material_id
            ORDER BY rm.name ASC, rml.received_date ASC

                    """, ())
            result = cursor.fetchall()
            columns = ['lot_id', 'lot_number', 'material_name', 'material_id', 'quantity', 'received_date', 'expiration_date', 'location', 'supplier', 'cost_per_unit', 'status']
            df = pd.DataFrame(result, columns=columns)
            
    
    except Exception as e:
        logging.error(f"Error fetching all lots (with or without material_id {material_id}): {e}")
        return None

    finally:
        db.close()
    
    return df

def get_lot_by_id(lot_id):

    """
    
    returns:
    every lot column, material name, material is housemad boolean
    
    
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        SELECT rml.*, rm.name AS material_name, rm.is_housemade
        FROM raw_material_lots rml
        JOIN raw_materials rm ON rml.material_id = rm.material_id
        WHERE rml.lot_id = %s
        """, (lot_id,))
        result = cursor.fetchone()
        if result is None:
            raise ValueError(f"Lot with ID {lot_id} not found.")
        
        columns = ['lot_id', 'material_id', 'lot_number', 'quantity', 'received_date', 'expiration_date', 'location', 'supplier', 'cost_per_unit', 'status', 'material_name', 'is_housemade']
        df = pd.DataFrame([result], columns=columns) # create a dataframe with a single row. 

        return df

    except ValueError as e:
        logging.error(f"Value error fetching lot by id {lot_id}. Error: {e}")
        return None

    except Exception as e:
        logging.error(f"Error fetching lot by id {lot_id}. Error: {e}")
        return None

    finally:
        db.close()


def update_lot(lot_id, lot_number=None, quantity=None, received_date=None, expiration_date=None, location=None, supplier=None, cost_per_unit=None, status=None, is_housemade=None):
    """
    
    lets user update any lot information. 


    If is_housemade is True 
    (or lot_number starts with MIX-BATCH-), skip updating quantity (guard in service layer).


    returns True if successful, False otherwise.
    
    """

    db = get_db_connection()
    cursor = db.cursor()

    

    field = {}
    # for each value provided, add to field dict. 
    for key, value in { 
        'lot_number': lot_number, 
        'quantity': quantity, 
        'received_date': received_date, 
        'expiration_date': expiration_date, 
        'location': location, 
        'supplier': supplier, 
        'cost_per_unit': cost_per_unit, 
        'status': status,
        
    }.items():
        if value is not None:
            field[key] = value

    if not field:
        raise ValueError("No fields provided for update.")
    
    #cant update quantity for housemade lots, this is done in batch field. 
    if (is_housemade or (lot_number and lot_number.startswith("MIX-BATCH-"))) and 'quantity' in field:
        logging.warning(f"Attempted to update quantity for housemade lot {lot_id}. This is not allowed. Quantity will not be updated.")
        del field['quantity']
    
    try:
        for key in field: #for each key and its value, update the lot.
            db.execute(cursor,f"""
            UPDATE raw_material_lots
            SET {key} = %s
            WHERE lot_id = %s
            """, (field[key], lot_id,))

        if cursor.rowcount == 0:
                raise ValueError(f"lot ID {lot_id} not found — nothing updated")
        db.commit()
        logging.info(f"Updated lot with id:{lot_id}")

        return True
    
    except ValueError as e:
        logging.error(f"Value error updating lot with id {lot_id}. Error: {e}")
        db.rollback()
        return False

    finally:
        db.close()


def get_batches_for_lot(lot_id):
    """
    Returns all batches that reference this lot in batch_materials.
    Used to warn the user before deleting a lot that is tracked in a batch.
    Returns a list of dicts with batch_id and batch_name, or an empty list.
    """
    db = get_db_connection()
    cursor = db.cursor()
    try:
        db.execute(cursor, """
        SELECT DISTINCT b.batch_id, b.batch_name
        FROM batch_materials bm
        JOIN batches b ON bm.batch_id = b.batch_id
        WHERE bm.lot_id = %s
        """, (lot_id,))
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        logging.error(f"Error fetching batches for lot {lot_id}: {e}")
        return []
    finally:
        db.close()


def delete_lot(lot_id):
    """
    Permanently deletes a lot from raw_material_lots.
    Returns True on success, False on failure.
    """
    db = get_db_connection()
    cursor = db.cursor()
    try:
        db.execute(cursor, """
        DELETE FROM raw_material_lots
        WHERE lot_id = %s
        """, (lot_id,))
        db.commit()
        logging.info(f"Deleted lot with id:{lot_id}")
        return True
    except Exception as e:
        logging.error(f"Error deleting lot with id {lot_id}. Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()








