"""
Matcha Inventory Management System
Core functions for database operations and queries
"""

from database import get_db_connection
import pandas as pd
from datetime import datetime
import os
import logging

_UNSET = object()  # sentinel for optional fields that can be explicitly set to None

#LOGGING SET UP

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

# ========================
# DATABASE SETUP
# ========================

# NOTE: This function only for local SQLite - use init_db.py for PostgreSQL
def create_database():
    """Creates database with raw_materials, recipes, and ready_to_ship tables"""
    import sqlite3
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    #Raw Materials 

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_materials(
                   material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL UNIQUE,
                   category TEXT,
                   stock_level REAL,
                   unit TEXT,
                   reorder_level REAL,
                   cost_per_unit REAL,
                   supplier TEXT,
                   is_housemade BOOLEAN DEFAULT FALSE

                   )
                   """)
    
    #Recipes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recipes(
                   recipe_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   product_name TEXT NOT NULL,
                   notes TEXT
                   
                   
                   )
                   """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recipe_materials(
                   recipe_material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   recipe_id INTEGER,
                   material_id INTEGER,
                   material_name TEXT,
                   quantity_needed REAL,
                   FOREIGN KEY (material_id) REFERENCES raw_materials(material_id),
                   FOREIGN KEY (recipe_id) REFERENCES recipes(recipe_id)
                   
                   )
                   """)

    # Ready to ship
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batches(
                    batch_id INTEGER PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    quantity INTEGER,
                    date_completed TEXT,
                    status TEXT DEFAULT 'Ready',
                    notes TEXT,
                    date_shipped TEXT,
                    expiration_date TEXT,
                    planned_completion_date TEXT,
                    batch_type TEXT DEFAULT 'standard',
                    promotion_failure_reason TEXT
                    
                   
                
                   )
                   """)
    
    
    #Batch_materials
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batch_materials(
                   batch_material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   batch_id INTEGER,
                   material_id INTEGER,
                   quantity_used REAL,
                   FOREIGN KEY (material_id) REFERENCES raw_materials(material_id),
                   FOREIGN KEY (batch_id) REFERENCES batches(batch_id)           
                  
                   
                   ) """)
    
    #Audit Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log(
                   log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   action TEXT NOT NULL,
                   details TEXT,
                   timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                   )""")

    # Save all table creations to the database
    conn.commit()
    conn.close()
    print(" Database created")



# ========================
# RAW MATERIALS FUNCTIONS
# ========================
 
def add_raw_material(name, category, stock_level, unit, reorder_level, cost_per_unit=None, supplier=None, is_housemade=False):
    # adds material to raw_materials

    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, "SELECT material_id FROM raw_materials WHERE LOWER(name) = LOWER(%s)", (name,))
        if cursor.fetchone():
            return "duplicate"

        db.execute(cursor, """
            INSERT INTO raw_materials (name, category, stock_level, unit, reorder_level, cost_per_unit, supplier, is_housemade)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)

                        """, (name, category, stock_level, unit, reorder_level, cost_per_unit, supplier, is_housemade))

        db.commit()
        print(f"Added {name} to raw materials")
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

    SELECT name, category, stock_level, reorder_level, unit, cost_per_unit, supplier
    FROM raw_materials
    WHERE stock_level <= reorder_level
    ORDER BY (stock_level / NULLIF(reorder_level, 0))
    """
    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result


def get_all_materials():
    "Returns all materials"
    db = get_db_connection()
    cursor = db.cursor()

    query = """
    SELECT name, category, stock_level, unit, reorder_level, cost_per_unit, supplier, is_housemade
    FROM raw_materials
    ORDER BY category, name
    """

    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result



def get_material_by_id(material_id):
    "Returns material given its material_id"
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        SELECT material_id, name, category, stock_level, unit, reorder_level, cost_per_unit, supplier, is_housemade
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


def update_raw_material(material_id, name=None, category=None, stock_level=None, unit=None, reorder_level=None, cost_per_unit=None, supplier=None):
    """changes raw material info given id and which parameters are not None (ONLY CHANGES details, not stock level)"""

    db = get_db_connection()
    cursor = db.cursor()

    field = {} # dictionary to hold fields to update, only the ones that are not None

    #iterate through params, if not None, add to field dict to update
    for key, value in [("name", name), ("category", category), ("stock_level", stock_level), ("unit", unit), ("reorder_level", reorder_level), ("cost_per_unit", cost_per_unit), ("supplier", supplier)]:
        if value is not None:
            field[key] = value 

    if not field: #empty dictionary, no fields to update
        print("No fields to update")
        return

    try:
        for key in field:
            db.execute(cursor,f"""
            UPDATE raw_materials
            SET {key} = %s
            WHERE material_id = %s
            """, (field[key], material_id,))
        
        
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
        SELECT material_id, name, stock_level, reorder_level, cost_per_unit
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


def get_all_materials_with_id():

    db = get_db_connection()
    cursor = db.cursor()


    try:

        query = """
        SELECT material_id, name, category, stock_level, unit, reorder_level, cost_per_unit, supplier, is_housemade
        FROM raw_materials
        ORDER BY category, name
        """

        result = pd.read_sql_query(query, db.conn)
        db.close()
        return result

    except Exception as e:
        logging.error(f"error getting all materials with id: {e}")
        db.close()
        return None

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

# ========================
# BATCHES FUNCTIONS
# ========================

def add_to_batches(product_name, quantity, notes=None, batch_id=None, deduct_resources=True, expiration_date=None, planned_completion_date=None, batch_type='standard'):
    """
    adds batch to ready to ship, but asks user if they want to deduct from resources, or just add it.
    If planned_completion_date is provided, batch is created with status 'Planned' instead of 'Ready'.
    batch_type can be 'standard', 'mix', or 'finished' — used to auto-determine whether to defer deduction for planned batches.
    if standard or mix, deduction happens immediately at batch creation regardless of planned vs ready status. and adds mixed batch to raw_materials with is_housemade = True, so they can be used in future batches.
    if finished, deduction is deferred until promotion time for planned batches, happens immediately for ready batches.
    """
    # Connect to the database
    db = get_db_connection()
    cursor = db.cursor()



    try:

        #get recipe data frame
        recipe_df = get_recipe(product_name)

        if recipe_df is None or recipe_df.empty:
            raise ValueError(
                f"Recipe '{product_name}' has no materials. "
                "A material may have been deleted — please recreate it or update the recipe."
            )

        # Determine status and date_completed based on whether a planned date was given
        if planned_completion_date:
            status = 'Planned'
            date_completed = None
        else:
            status = 'Ready'
            date_completed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


        # Auto-derive whether to defer deduction.
        # finished + Planned = skip deduction now, will deduct at promotion time.
        # mix and standard always deduct immediately, regardless of status.
        defer_deduction = (batch_type == 'finished' and status == 'Planned')


        if batch_id is not None:

                #add to batches

                # check if batch_id already exists

            db.execute(cursor, """
                SELECT 1
                FROM batches
                WHERE batch_id = %s
            """, (batch_id,))
            if cursor.fetchone():
                raise ValueError(f"Batch ID {batch_id} already exists.")



            
            db.execute(cursor, """
            INSERT INTO batches (batch_id, product_name, quantity, date_completed, status, notes, expiration_date, planned_completion_date, batch_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (batch_id, product_name, quantity, date_completed, status, notes, expiration_date, planned_completion_date, batch_type))

        
        else:#batch_id is None, let database auto assign id
            db.execute(cursor, """
            INSERT INTO batches (product_name, quantity, date_completed, status, notes, expiration_date, planned_completion_date, batch_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (product_name, quantity, date_completed, status, notes, expiration_date, planned_completion_date, batch_type))
            batch_id = db.get_last_insert_id(cursor)
               


        #Deducting resources:


        if deduct_resources and not defer_deduction: # if defer_deduction, will be deducted later in promotion from planned. 


            #check in there is needed resources
            for _, row in recipe_df.iterrows(): #iterate through each row of recipe df
                material_id_recipe = row['material_id'] #get id
                material_name = row['material_name'] #get material name
                quantity_needed = row['quantity_needed'] # needed amount

                material_info = get_raw_material(material_name)
                if not material_info:
                    raise ValueError(f"Material {material_name}: not found in inventory")


                material_id, name, stock_level, reorder_level, cost_per_unit = material_info #break down tuple

                required_amount = quantity_needed * quantity

                if stock_level < required_amount:
                    raise ValueError(f"Insufficient {material_name}: need {required_amount}, have {stock_level}")


                #deduct from raw_materials
            for _, row in recipe_df.iterrows(): #iterate through each row of recipe df
                material_id = row['material_id'] #get id
                material_name = row['material_name'] #get material name
                quantity_needed = row['quantity_needed'] # needed amount
                required_amount = quantity_needed * quantity

                #deduct from raw_materials
                db.execute(cursor, """
                UPDATE raw_materials
                SET stock_level = stock_level - %s
                WHERE material_id = %s
                    """,(required_amount, material_id,))
                
                if cursor.rowcount == 0:
                    raise ValueError(
                    f"Failed to deduct stock for '{material_name}' (id={material_id}). "
                    "The material may have been deleted or the recipe has a broken reference."
    )

                #add to batch_materials
                db.execute(cursor, """
                INSERT INTO batch_materials (batch_id, material_id, quantity_used)
                    VALUES (%s, %s, %s)
                    """, (batch_id, material_id, required_amount))


        
        # ALSO IF BATCH TYPE IS MIX, ADD THE MIXED PRODUCT TO RAW_MATERIALS WITH is_housemade = True, SO IT CAN BE USED IN FUTURE BATCHES.if not already in raw_materials,
        # otherwise if its already in raw_materials, just update the stock level by adding the quantity of the batch we just made.
        if batch_type == 'mix': # add to raw_materials.
            existing_mix = get_raw_material(product_name)
            if existing_mix:
                db.execute(cursor, """
                    UPDATE raw_materials SET stock_level = stock_level + %s
                    WHERE material_id = %s
                """, (quantity, existing_mix[0]))
            else:
                db.execute(cursor, """
                    INSERT INTO raw_materials (name, category, stock_level, unit, reorder_level, is_housemade)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (product_name, 'Mix', quantity, 'units', 0, True))


        
        



        db.commit()
        print(f"Added {quantity} units of {product_name} (Batch {batch_id})")
        return batch_id


    except ValueError as e:
        # Re-raise ValueError so app.py can catch it and show to user
        logging.error(f"Error adding to batches: {e}")
        db.rollback()
        raise  # ← Re-raises the ValueError to app.py

    except Exception as e:
        # If any error occurs during the process, print it and undo all changes
        logging.error(f"Error adding to batches: {e}")
        db.rollback()  # Rollback ensures database stays consistent
        return None

    finally:
        # Always close the database connection, even if an error occurred
        db.close()


def get_batches():
    """Gets all batches ready to ship"""
    promote_planned_batches() # call func to transition planned batches to raedy 
    #if date passed before usesr even sees page. 
    db = get_db_connection()

    query = """
    SELECT batch_id, product_name, batch_type, quantity, date_completed, notes, expiration_date
    FROM batches
    WHERE status = 'Ready'
    ORDER BY batch_id DESC
    """

    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result


def get_batches_shipped():
    """Gets all batches that have been shipped"""
    db = get_db_connection()

    query = """
    SELECT batch_id, product_name, quantity, date_completed, date_shipped, notes, expiration_date
    FROM batches
    WHERE status = 'Shipped'
    ORDER BY date_shipped DESC
    """

    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result

def mark_as_shipped(batch_id):
    """Marks a batch as shipped"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        UPDATE batches
        SET status = 'Shipped', date_shipped = %s
        WHERE batch_id = %s
        """, (datetime.now().strftime('%Y-%m-%d'), batch_id))


        if cursor.rowcount == 0: # make sure the batch id exists and was updated
            print(f"Batch ID {batch_id} not found. No batch marked as shipped.") # if doesnt exist, there was an error marking batch as shipped. 
            db.rollback()
            return False


        db.commit()
        print(f" Marked batch {batch_id} as shipped")
        return True

    except Exception as e:
        logging.error(f" Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def delete_batch(batch_id, reallocate=False):
    """
    Deletes a batch from batches.
    Optionally reallocates raw materials back into inventory.
    """

    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Get batch info
        db.execute(cursor, """
            SELECT product_name, quantity
            FROM batches
            WHERE batch_id = %s
        """, (batch_id,))
        row = cursor.fetchone()

        if not row:
            logging.info(f"Batch ID {batch_id} not found in batches.")
            return None





        if reallocate:

            materials_added = []
            #get batch material info from batch id
            db.execute(cursor, """
            SELECT bm.batch_material_id, bm.material_id, bm.quantity_used, rm.name AS material_name
            FROM batch_materials AS bm
            JOIN raw_materials AS rm ON bm.material_id = rm.material_id
            WHERE bm.batch_id = %s
                           """,(batch_id,))

            batch_materials = cursor.fetchall()



            for _, material_id, quantity_used, material_name in batch_materials:

                db.execute(cursor, """
                    UPDATE raw_materials
                    SET stock_level = stock_level + %s
                    WHERE material_id = %s
                """, (quantity_used, material_id))

                materials_added.append({
                    "material": material_name,
                    "quantity_added": quantity_used
                    })
            # delete batch materials after adding to list
            db.execute(cursor, """
                DELETE 
                FROM batch_materials
                WHERE batch_id = %s        
                                 
                   """,(batch_id,))
            # Delete batch
            db.execute(cursor, """
                DELETE FROM batches
                WHERE batch_id = %s
            """, (batch_id,))
            #make sure it deleted it
            if cursor.rowcount == 0:
                raise ValueError(f"batch ID {batch_id} not found — nothing deleted")
            
            db.commit()
            
            logging.info(
                f"Successfully deleted batch {batch_id}.\n"
                f"Reallocated materials: {materials_added}"
                )
            return True

        else:
            db.execute(cursor, """
                DELETE FROM batch_materials
                WHERE batch_id = %s
            """, (batch_id,))
            db.execute(cursor, """
                DELETE FROM batches
                WHERE batch_id = %s
            """, (batch_id,))
            #check it deleted
            if cursor.rowcount == 0:
                raise ValueError(f"batch ID {batch_id} not found — nothing deleted")
            db.commit()
            logging.info(f"Successfully deleted batch {batch_id}.")
            return True




    except Exception as e:
        db.rollback()
        logging.error(f"Error deleting batch: {e}")
        return None

    finally:
        db.close()

def get_all_batches_with_id():
    """
    Get all batches including shipped ones, using batch_id

    used for manage page
    """
    promote_planned_batches()
    db = get_db_connection()

    try:
        query = """

        SELECT batch_id, product_name, quantity, date_completed, status, notes, date_shipped, expiration_date, planned_completion_date
        FROM batches
        ORDER BY date_completed DESC
        """

        result = pd.read_sql_query(query, db.conn)
        
        return result

    except Exception as e:
        logging.error(f"error getting all materials with id: {e}")
        
        return None
    
    finally:
        db.close()

def get_batch_by_id(batch_id):
    """
    get batch using its id, 
    for manage page.

    """

    db = get_db_connection()
    cursor = db.cursor()

    try:
        query = """
        SELECT batch_id, product_name, quantity, date_completed, status, notes, date_shipped, expiration_date, planned_completion_date
        FROM batches
        WHERE batch_id = %s

        """
        db.execute(cursor, query, (batch_id,))
        result = cursor.fetchone()
        return result
    
    except Exception as e:
        logging.error(f"error getting batch by id: {e}")
        
        return None
    
    finally:
        db.close()

def update_batch(batch_id, product_name=None, quantity=None, date_completed=None, notes=None, expiration_date=_UNSET, planned_completion_date=_UNSET):
    """
    changes the details of batch, BESIDES STATUS, doesnt change status.

    note: similar to update_materials func

    for quantity change, must deduct from raw materials if quantity is increased, and add back to raw materials if quantity is decreased. will check for sufficient stock if quantity is increased. 
    """

    db = get_db_connection()
    cursor = db.cursor()

    field = {} # dictionary to hold fields to update, only the ones that are not None

    #iterate through params, if not None, add to field dict to update
    for key, value in [("product_name", product_name), ("quantity", quantity), ("date_completed", date_completed), ("notes", notes)]:
        if value is not None:
            field[key] = value
    # expiration_date and planned_completion_date use sentinel so None can explicitly clear the field
    if expiration_date is not _UNSET:
        field["expiration_date"] = expiration_date
    
    if planned_completion_date is not _UNSET:
        field["planned_completion_date"] = planned_completion_date

    if not field: #empty dictionary, no fields to update
        logging.info("No fields to update")
        return

    try:
        for key in field: #for each key and its value, update the batch.
            db.execute(cursor,f"""
            UPDATE batches
            SET {key} = %s
            WHERE batch_id = %s
            """, (field[key], batch_id,))         
        
        if cursor.rowcount == 0:
                raise ValueError(f"batch ID {batch_id} not found — nothing updated")
        db.commit()
        logging.info(f"Updated batch with id:{batch_id}")

        return True
    
    except Exception as e:
        logging.error(f"Error changing batch details: {e}")
        db.rollback()
        return None
    
    finally:
        db.close()


def update_batch_status(batch_id, new_status):
    """
    changes the status of batch, only changes status, not other details.
    """

    db = get_db_connection()
    cursor = db.cursor()

    try:
        if new_status == 'Shipped':
            db.execute(cursor, """
            UPDATE batches
            SET status = %s, date_shipped = %s
            WHERE batch_id = %s
            """, (new_status, datetime.now().strftime('%Y-%m-%d'), batch_id))


        elif new_status == 'Planned':
            # Batch is not yet done — clear completion and ship dates
            db.execute(cursor, """
            UPDATE batches
            SET status = 'Planned', date_completed = NULL, date_shipped = NULL
            WHERE batch_id = %s
            """, (batch_id,))
            
        else:
            # Manually marking Ready — stamp the actual completion time
            db.execute(cursor, """
            UPDATE batches
            SET status = %s, date_shipped = NULL, date_completed = %s
            WHERE batch_id = %s
            """, (new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), batch_id))

        if cursor.rowcount == 0:
                raise ValueError(f"batch ID {batch_id} not found — nothing updated")

        db.commit()
        logging.info(f"Batch {batch_id} status updated to {new_status}")
        return True

    except Exception as e:
        logging.error(f"Error updating batch status: {e}")
        db.rollback()
        return None

    finally:
        db.close()

def promote_planned_batches():

    """
    Promotes overdue Planned batches to Ready.
    - standard/mix batches: flip status directly (deduction already happened at creation)
    - finished batches: attempt deduction first; if insufficient stock, leave as Planned
      and record the reason in promotion_failure_reason
    Called lazily from get_batches() and get_all_batches_with_id().
    
    """


    db = get_db_connection()
    cursor = db.cursor()
    try:
        now = datetime.now().strftime('%Y-%m-%d')

        #get all overdue batches

        db.execute(cursor, """
            SELECT batch_id, product_name, quantity, batch_type, planned_completion_date
            FROM batches
            WHERE status = 'Planned'
            AND planned_completion_date IS NOT NULL
            AND planned_completion_date <= %s 
                   
                   """, (now,))
        overdue = cursor.fetchall()

        #for each over due batch:
        for batch_id, product_name, quantity, batch_type, planned_completion_date in overdue:

            if batch_type in ('standard', 'mix'):
                #deduction happened upon batch creation, only status flip here
                db.execute(cursor, """
                    UPDATE batches
                    SET status = 'Ready',
                        date_completed = %s,
                        promotion_failure_reason = NULL      
                    WHERE batch_id = %s
                           
                           """, (planned_completion_date, batch_id))
                
                if cursor.rowcount == 0:
                    raise ValueError(f"Batch {batch_id} not found during promotion — nothing updated")
                
                log_action('planned_batch_promoted',
                           f"batch_id={batch_id}, product={product_name}, type={batch_type}")
            
            #now for "finished batches, deduction happens here, must do a stock check though."

            elif batch_type == 'finished':
                recipe_df = get_recipe(product_name)
                if recipe_df is None or recipe_df.empty:
                    db.execute(cursor,"""
                        UPDATE batches
                        SET promotion_failure_reason = %s
                        WHERE batch_id = %s   
                               
                               """, (f"No recipe found for {product_name}", batch_id, ))
                    continue

                failure_reason = None #initialize failure reason
                #if recipe_df not none/empty:
                for _, row in recipe_df.iterrows(): # get each mat in recipe
                    material_name = row['material_name']
                    required = row['quantity_needed'] * quantity


                    db.execute(cursor, """
                        SELECT stock_level, unit FROM raw_materials
                        WHERE LOWER(name) = LOWER(%s)
                    """, (material_name,))
                    mat = cursor.fetchone()
                    if not mat:
                        failure_reason = f"Material not found: {material_name}"
                        break

                    stock, unit = mat
                    if stock < required: #if not enough
                        failure_reason = (
                            f"Insufficient stock: {material_name} "
                            f"(need {required} {unit}, have {round(stock, 2)} {unit})"
                            )
                        break
                
                if failure_reason:
                    # Leave as Planned, record why
                    db.execute(cursor, """
                        UPDATE batches
                        SET promotion_failure_reason = %s
                        WHERE batch_id = %s
                    """, (failure_reason, batch_id))
                    logging.warning(f"Batch {batch_id} could not promote: {failure_reason}")
                    

                else: #if there was valid stock levels, deduct and promote:

                     
                    for _, row in recipe_df.iterrows():
                        material_name = row['material_name']
                        material_id = row['material_id']
                        required = row['quantity_needed'] * quantity
                        db.execute(cursor, """
                            UPDATE raw_materials
                            SET stock_level = stock_level - %s
                            WHERE material_id = %s
                        """, (required, material_id))
                        db.execute(cursor, """
                            INSERT INTO batch_materials (batch_id, material_id, quantity_used)
                            VALUES (%s, %s, %s)
                        """, (batch_id, material_id, required))

                    db.execute(cursor, """
                        UPDATE batches
                        SET status = 'Ready',
                            date_completed = %s,
                            promotion_failure_reason = NULL
                        WHERE batch_id = %s
                    """, (planned_completion_date, batch_id))
                    
                    if cursor.rowcount == 0:
                        raise ValueError(f"Batch {batch_id} not found during promotion — nothing updated")

                    log_action('planned_batch_promoted',
                               f"batch_id={batch_id}, product={product_name}, type=finished")

        db.commit()


    except Exception as e:
        logging.error(f"Error transitioning planned batches: {e}")
        db.rollback()

    finally:
        db.close()




def get_batches_planned():
    """Gets all Planned batches ordered by planned_completion_date ascending."""
    db = get_db_connection()
    query = """
    SELECT batch_id, product_name, batch_type, quantity, planned_completion_date, notes, expiration_date, promotion_failure_reason
    FROM batches
    WHERE status = 'Planned'
    ORDER BY batch_id DESC
    """
    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result


def get_batch_materials(batch_id):
    """
    Gets all batch materials for specific batch_id

    """
    db = get_db_connection()
    cursor = db.cursor()

    try:

        query="""
        SELECT rm.name AS material_name, bm.quantity_used, rm.unit, bm.material_id
        FROM batch_materials bm
        JOIN raw_materials rm ON bm.material_id = rm.material_id
        WHERE bm.batch_id = %s
        ORDER BY rm.name ASC
        """
        db.execute(cursor, query, (batch_id,))
        result = cursor.fetchall()
        return result if result else []

    except Exception as e:
        logging.error(f"Error getting batch materials: {e}")
        return []
    
    finally:
        db.close()




def adjust_batch_material(batch_id, new_quantities: dict):
    """
    Updates batch_materials.quantity_used and applies delta to raw_materials.stock_level.
    new_quantities: {material_id (int): new_quantity_used (float)}
    Delta logic: stock_level -= (new - old), so increasing qty deducts more, decreasing returns stock.
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        for material_id, new_qty in new_quantities.items(): #for each material and its new quantity. 
            db.execute(cursor, """
                SELECT quantity_used FROM batch_materials 
                WHERE batch_id = %s AND material_id = %s
            """, (batch_id, material_id)) # get old quantity 
            row = cursor.fetchone()
            if row is None: # make sure batch_material record exists for this batch and material
                logging.warning(f"No batch_material record for batch {batch_id}, material {material_id} — aborting")
                db.rollback()
                return None

            old_qty = row[0] # get old quantity
            delta = new_qty - old_qty# data is change in quantity
            
            #must check if there is enough stock to increase quantity if delta is positive
            if delta > 0:
                db.execute(cursor, """
                    SELECT stock_level 
                    FROM raw_materials
                    WHERE material_id = %s
                """, (material_id,))
                stock_row = cursor.fetchone()
                if not stock_row:
                    logging.warning(f"Material ID {material_id} not found in raw_materials during batch adjustment — aborting")
                    db.rollback()
                    return None

                stock_level = stock_row[0]
                if stock_level < delta:
                    logging.warning(f"Insufficient stock to increase material {material_id} for batch {batch_id}: need additional {delta}, have {stock_level} — aborting")
                    db.rollback()
                    return None


            db.execute(cursor, """
                UPDATE batch_materials
                SET quantity_used = %s
                WHERE batch_id = %s AND material_id = %s
            """, (new_qty, batch_id, material_id))#update batch_materials with new quantity

            db.execute(cursor, """
                UPDATE raw_materials
                SET stock_level = stock_level - %s
                WHERE material_id = %s
            """, (delta, material_id))# apply delta to stock level

        db.commit()
        logging.info(f"Adjusted materials for batch {batch_id} with changes: {new_quantities}")
        return True

    except Exception as e:
        logging.error(f"Error adjusting batch materials: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def check_batch_materials_stock(batch_id, new_quantities: dict):
    """
    Used to check if new qantites for batch materials availible in stock before adjusting. 
    
    """
    db = get_db_connection()
    cursor = db.cursor()
    
    for material_id, new_qty in new_quantities.items():
        
        try:
            db.execute(cursor, """
                SELECT quantity_used FROM batch_materials 
                WHERE batch_id = %s AND material_id = %s
            """, (batch_id, material_id)) # get old quantity 
            row = cursor.fetchone()
            if row is None: # make sure batch_material record exists for this batch and material
                logging.warning(f"No batch_material record for batch {batch_id}, material {material_id} during stock check")
                return False

            old_qty = row[0] # get old quantity
            delta = new_qty - old_qty# data is change in quantity
            
            if delta > 0:
                db.execute(cursor, """
                    SELECT stock_level 
                    FROM raw_materials
                    WHERE material_id = %s
                """, (material_id,))
                stock_row = cursor.fetchone()
                if not stock_row:
                    logging.warning(f"Material ID {material_id} not found in raw_materials during stock check")
                    return False

                stock_level = stock_row[0]
                if stock_level < delta:
                    logging.warning(f"Insufficient stock to increase material {material_id} for batch {batch_id} during stock check: need additional {delta}, have {stock_level}")
                    return False

        except Exception as e:
            logging.error(f"Error checking batch materials stock: {e}")
            return False

        finally:
            db.close()
# ========================
# RECIPE FUNCTIONS
# ========================


def get_recipe(product_name):
    """
    Gets recipe from recipes, which refrences recipe materials

    """

    db = get_db_connection()
    cursor = db.cursor()

    try:
        
        db.execute(cursor,"""
        SELECT recipe_id
        FROM recipes
        WHERE LOWER(product_name) = LOWER(%s)   
                       """,(product_name,))
        row = cursor.fetchone() # get recipe_id from product name

        if not row:
            print(f"{product_name} not found in recipes")
            return None
        recipe_id = row[0]
        
        query = ("""
        SELECT r.product_name,
        r.notes,
        rm.material_id,
        raw.name AS material_name,
        rm.quantity_needed
        FROM recipes r
        JOIN recipe_materials rm ON r.recipe_id = rm.recipe_id
        JOIN raw_materials raw ON rm.material_id = raw.material_id
        WHERE r.recipe_id = %s
        ORDER BY rm.material_name ASC
        """)

        db.execute(cursor, query, (recipe_id,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(rows, columns=columns)

        return df
        




    except Exception as e:
        logging.error(f"Error: {e} \ngetting recipe:{product_name}.")
        return None
    
    finally:
        db.close()
    


def get_all_recipes():
    """
    Returns all recipes and their materials as a DataFrame

    Columns returned:
    - recipe_product_name: Name of the recipe/product
    - notes: Optional notes about the recipe
    - material_name: Name of the material/ingredient
    - quantity: Amount of material needed per batch
    - unit: Unit of measurement (from raw_materials table)
    """
    db = get_db_connection()

    query = """
    SELECT
        r.product_name AS recipe_product_name,
        r.notes,
        raw.name AS material_name,
        rm.quantity_needed AS quantity,
        raw.unit
    FROM recipes r
    JOIN recipe_materials rm ON r.recipe_id = rm.recipe_id
    JOIN raw_materials raw ON rm.material_id = raw.material_id
    ORDER BY r.product_name ASC, raw.name ASC
    """
    # Note: unit comes from raw_materials (raw.unit), NOT recipe_materials

    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result

    
        

    

def add_recipe(product_name, materials, notes=None):
     
    db = get_db_connection()
    cursor = db.cursor()


    """
    Adds a new recipe to the database.

    Parameters:
        product_name (str): Name of the product.
        materials (list of dict): Each dict contains 'material_name' and 'quantity_needed'.
        notes (str, optional): Additional notes for the recipe.

    Example:
        materials = [
            {'material_name': 'Matcha Powder', 'quantity_needed': 10},
            {'material_name': 'Milk', 'quantity_needed': 200}
        ]
        add_recipe('Matcha Latte', materials, notes='Sweetened')
    """

    try:

        db.execute(cursor,"""
        INSERT INTO recipes (product_name, notes)
        VALUES (%s, %s)
         """,(product_name, notes))
        recipe_id = db.get_last_insert_id(cursor) # get recipe_id, able to add to recipe_materials



        for material in materials:
            material_name = material["material_name"]
            quantity_needed = material['quantity_needed']

            #check material is in database

            material_info = get_raw_material(material_name)

            if not material_info:
                logging.error(f"Material '{material_name}' not found in raw_materials while adding recipe '{product_name}'.")
                raise ValueError(f"Material '{material_name}' not found in raw_materials. Please add it to inventory before creating the recipe.")
                

            else:
                material_id = material_info[0]#get material_id, first value from get_raw_material result


            db.execute(cursor,"""
            INSERT INTO recipe_materials (
                   recipe_id,
                   material_name,
                   material_id,
                   quantity_needed)
            VALUES (%s,%s,%s,%s)                              
              """,(recipe_id, material_name, material_id, quantity_needed))
            

        db.commit()
        print(f"Recipe '{product_name}' added successfully with {len(materials)} materials.")
        return recipe_id



    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None
    
    finally:
        db.close()
     

def change_recipe(product_name, materials, notes= None):
    """
    changes a pre exisitng recipe 

    Parameters:
        product_name (str): Name of the product.
        materials (list of dict): Each dict contains 'material_name' and 'quantity_needed'.
        notes (str, optional): Additional notes for the recipe.

    Example:
        materials = [
            {'material_name': 'Matcha Powder', 'quantity_needed': 10},
            {'material_name': 'Milk', 'quantity_needed': 200}
        ]
        change_recipe('Matcha Latte', materials, notes='Sweetened')

        
        
        """
    
    db = get_db_connection()
    cursor = db.cursor()
    
    try:

        db.execute(cursor,"""
        SELECT recipe_id
        FROM recipes
        WHERE LOWER(product_name) = LOWER(%s)

                       """,(product_name,))
        recipe_id = cursor.fetchone()

        if not recipe_id:
            print(f"No recipe found for {product_name}")
            return None
        recipe_id = recipe_id[0]



        db.execute(cursor,"""
        UPDATE recipes
        SET notes = %s
        WHERE LOWER(product_name) = LOWER(%s)               
                       
                       """,(notes, product_name,))
        

        db.execute(cursor,"""
        DELETE FROM recipe_materials
        WHERE recipe_id = %s               
                       """,(recipe_id,))
        

        for material in materials:
            material_name = material["material_name"]
            quantity_needed = material['quantity_needed']


            material_info = get_raw_material(material_name)

            if not material_info:
                logging.error(f"Material '{material_name}' not found in raw _materials while updating recipe '{product_name}'.") 
                raise ValueError(f"Material '{material_name}' not found in raw_materials. Please add it to inventory before updating the recipe.")
                    

            else:
                material_id = material_info[0]#get material_id, first value from get_raw_material result


            db.execute(cursor,"""
            INSERT INTO recipe_materials (
            
            recipe_id,
            material_name,
            material_id,
            quantity_needed)
            VALUES (%s,%s,%s,%s)                             
                """, (recipe_id, material_name, material_id, quantity_needed))
        

        db.commit()
        print(f"Recipe '{product_name}' changed successfully with {len(materials)} materials.")
        return recipe_id
        

    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None
    
    finally:
        db.close()
    

def delete_recipe(product_name):
    


    "deletes recipe"

    db = get_db_connection()
    cursor = db.cursor()

    try:

        #get id
        db.execute(cursor,"""
        SELECT recipe_id
        FROM recipes
        WHERE LOWER(product_name) = LOWER(%s)
                       """,(product_name,))
        row = cursor.fetchone()

        if not row:
            print(f"Recipe for {product_name} not found.")
            return None
        recipe_id = row[0]

        
        
        #get materials that will be deleted 
        query = ("""
        SELECT material_name, quantity_needed               
        FROM recipe_materials
        WHERE recipe_id = %s                             
                       """)
        df = pd.read_sql_query(query, db.conn, params=(recipe_id,) )

        #clean query for presentation

        df = df.rename(columns={
            'material_name': 'Material',
        'quantity_needed': 'Quantity Needed'
            })
        
        
        #delete recipe from recipes
        db.execute(cursor,"""
        DELETE FROM recipes
        WHERE LOWER(product_name) = LOWER(%s)               
                       """,(product_name,))
        
        if cursor.rowcount == 0:
            print(f"Recipe '{product_name}' not found.")
            db.close()
            return None


        db.execute(cursor, """
        DELETE FROM recipe_materials
        WHERE recipe_id = %s
                       """,(recipe_id,))


        
        
        db.commit()

        print(f"Deleted {product_name} from recipe log, {product_name}'s recipe:\n{df}")
    
    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None
    
    finally:
        db.close()


def get_all_recipes_with_id():
    """
    returns all recipes with their recipe_id, 
    used for manage page when editing recipe, 
    to get recipe id from product name.
    """


    db = get_db_connection()
    cursor = db.cursor()

    try:
        query = """
        SELECT DISTINCT r.recipe_id, r.product_name, r.notes
        FROM recipes r
        JOIN recipe_materials rm ON rm.recipe_id = r.recipe_id
        JOIN raw_materials raw ON rm.material_id = raw.material_id
        ORDER BY r.product_name ASC
        """
# uses joins to get recipe_id, product name, and notes for all recipes, then uses DISTINCT to only get one row per recipe 
# (since there are multiple rows per recipe in recipe_materials), orders by product name.
# this is done because view_recipes() uses joins aswell, so they both show same list of recipes. 
        result = pd.read_sql_query(query, db.conn)
        return result

    except Exception as e:
        logging.error(f"Error getting all recipes with id: {e}")
        return None
    
    finally:
        db.close()


    
def get_recipe_by_id(recipe_id):
    """
    gets recipe by id, used for managment page, 
    
    returns full recipe details, including materials and quantities, 
    given recipe_id, used for manage page when editing recipe, 
    to get recipe details from recipe id.
    
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        query = ("""
       SELECT r.recipe_id, 
       r.product_name, 
       r.notes, 
       rm.material_id, 
       raw.name AS material_name, 
       rm.quantity_needed 
       FROM recipes r
       JOIN recipe_materials rm ON rm.recipe_id = r.recipe_id
       JOIN raw_materials raw ON rm.material_id = raw.material_id
       WHERE r.recipe_id = %s
        """)

        db.execute(cursor, query, (recipe_id,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(rows, columns=columns)

        return df

    except Exception as e:
        logging.error(f"Error: {e} \ngetting recipe by id:{recipe_id}.")
        return None
    
    finally:
        db.close()


def update_recipe(recipe_id, product_name=None, materials=None, notes=None):
    """
    changes a pre exisitng recipe 

    Parameters:
        recipe_id (int): The ID of the recipe to change.
        materials (list of dict): Each dict contains 'material_name' and 'quantity_needed'.
        notes (str, optional): Additional notes for the recipe.

    Example:
        materials = [
            {'material_name': 'Matcha Powder', 'quantity_needed': 10},
            {'material_name': 'Milk', 'quantity_needed': 200}
        ]
        change_recipe('Matcha Latte', materials, notes='Sweetened')

        
        
        """
    
    db = get_db_connection()
    cursor = db.cursor()
    
    try:


        
        # for changing notes
        db.execute(cursor,""" 
        UPDATE recipes
        SET notes = %s 
        WHERE recipe_id = %s               
                        
                """,(notes, recipe_id,))
            
        if product_name is not None:
            db.execute(cursor, """
            UPDATE recipes
            SET product_name = %s
            WHERE recipe_id = %s
            """, (product_name, recipe_id))


        db.execute(cursor,"""
        DELETE FROM recipe_materials
        WHERE recipe_id = %s               
                       """,(recipe_id,)) # delete old materials
        

        for material in materials: 
            material_name = material["material_name"]
            quantity_needed = material['quantity_needed']


            material_info = get_raw_material(material_name)

            if not material_info:
                print(f"Warning: Material '{material_name}' not found in raw_materials.")
                material_id = None

            else:
                material_id = material_info[0]#get material_id, first value from get_raw_material result


            db.execute(cursor,"""
            INSERT INTO recipe_materials (
            
            recipe_id,
            material_name,
            material_id,
            quantity_needed)
            VALUES (%s,%s,%s,%s)                             
                """, (recipe_id, material_name, material_id, quantity_needed))
        

            if cursor.rowcount == 0:
                    raise ValueError(f"recipe ID {recipe_id} not found — nothing inserted")
        db.commit()
        logging.info(f"Recipe with recipe_id:{recipe_id} changed successfully with {len(materials)} materials.")
        return recipe_id
        

    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None
    
    finally:
        db.close()


def delete_recipe_by_id(recipe_id):
    "deletes recipe by id"

    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        DELETE FROM recipe_materials
        WHERE recipe_id = %s
        """, (recipe_id,))

        db.execute(cursor, """
        DELETE FROM recipes
        WHERE recipe_id = %s
        """, (recipe_id,))

        if cursor.rowcount == 0:
            raise ValueError(f"Recipe with id {recipe_id} not found.")

        db.commit()
        logging.info(f"Deleted recipe with id {recipe_id}")
        return True

    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()