"""
Matcha Inventory Management System
Core functions for database operations and queries
"""

from database import get_db_connection
import pandas as pd
from datetime import datetime
import os

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
                   name TEXT NOT NULL,
                   category TEXT,  
                   stock_level REAL,
                   unit TEXT,
                   reorder_level REAL, 
                   cost_per_unit REAL,
                   supplier TEXT,
                   lot_number INTEGER
                     
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
                    date_shipped TEXT
                
                   )
                   """)
    
    #Batch_materials
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batch_materials(
                   batch_material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   batch_id INTEGER,
                   material_id INTEGER,
                   quantity_used REAL,
                   lot_number INTEGER,
                   FOREIGN KEY (lot_number) REFERENCES raw_materials(lot_number),
                   FOREIGN KEY (material_id) REFERENCES raw_materials(material_id),
                   FOREIGN KEY (batch_id) REFERENCES batches(batch_id)           
                  
                   
                   ) """)
    
    # Save all table creations to the database
    conn.commit()
    conn.close()
    print(" Database created")



# ========================
# RAW MATERIALS FUNCTIONS
# ========================
 
def add_raw_material(name, category, stock_level, unit, reorder_level, cost_per_unit, supplier=None, lot_number=None):
    # adds material to raw_materials
    #new: lot number: optional integer(most mats will have it), if there is a duplicate lot number, 
    # it will just add to the existing stock level of that lot number,
    #  instead of creating a new entry. 
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
            INSERT INTO raw_materials (name, category, stock_level, unit, reorder_level, cost_per_unit, supplier, lot_number)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)

                        """, (name, category, stock_level, unit, reorder_level, cost_per_unit, supplier, lot_number))

        db.commit()
        print(f"Added {name} to raw materials")
        return db.get_last_insert_id(cursor)

    except Exception as e:
        print(f"Error: {e}")
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
    ORDER BY (stock_level / reorder_level)
    """
    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result


def get_all_materials():
    "Returns all materials"
    #lot number implimentation needed
    db = get_db_connection()
    cursor = db.cursor()

    query = """
    SELECT name, category, stock_level, unit, reorder_level, cost_per_unit, supplier, lot_number
    FROM raw_materials
    ORDER BY category, name
    """

    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result


def get_available_lots(material_name):
    """Returns all lots for a material that have stock > 0.
    Used during batch creation to show user which lots they can pick from.

    Returns DataFrame with columns: material_id, name, lot_number, stock_level, unit
    """
    db = get_db_connection()

    query = """
    SELECT material_id, name, lot_number, stock_level, unit
    FROM raw_materials
    WHERE name = %s AND stock_level > 0
    ORDER BY lot_number
    """
    result = pd.read_sql_query(query, db.conn, params=(material_name,))
    db.close()
    return result


def material_has_lot_numbers(material_name):
    """Checks if any rows for this material have a non-null lot number.
    Returns True if lot numbers exist, False if all are NULL.
    """
    db = get_db_connection()
    cursor = db.cursor()
    try:
        db.execute(cursor, """
        SELECT 1 FROM raw_materials
        WHERE name = %s AND lot_number IS NOT NULL
        LIMIT 1
        """, (material_name,))
        return cursor.fetchone() is not None
    finally:
        db.close()


def increase_raw_material(name, increase_amount, lot_number=None):

    """ increases amount of material given its name and amount to add
    it increases based on name AND lot number. 
    """

    db = get_db_connection()
    cursor = db.cursor()

    try:
# get mat_id, stock, and unit
        db.execute(cursor, """
        SELECT material_id, stock_level, unit
        FROM raw_materials
        WHERE name = %s AND lot_number = %s
        """, (name, lot_number))
        result = cursor.fetchone()
        # gets the result from the query in form of a tuple

        if not result:
            print(f"{name} not found in raw_materials")
            return None
        # if the query doesnt work, tells user

        (material_id, current_stock, unit) = result # breaks tuple down to three new variables

        db.execute(cursor, """
        UPDATE raw_materials
        SET stock_level = stock_level + %s
        WHERE material_id = %s AND lot_number = %s

        """, (increase_amount, material_id, lot_number) )
        db.commit()

        #get new stock level
        db.execute(cursor, """
        SELECT stock_level
        FROM raw_materials
        WHERE material_id = %s AND lot_number = %s

         """, (material_id, lot_number))
        new_stock_level = cursor.fetchone()[0] # fetchone() returns a tuple, so get the first and only value in tuple instead of tuple
        db.close()
        print(f"Succesfully added, {name} is now at {new_stock_level}")
        return new_stock_level

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()



def get_raw_material(name, lot_number=None):
    """
    gets raw material from name, and optional lot#.
    If lot_number is None, finds the row where lot_number IS NULL.
    If lot_number is provided, finds the row matching that lot_number.
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        if lot_number is None:
            db.execute(cursor, """
            SELECT material_id, name, stock_level, reorder_level, cost_per_unit
            FROM raw_materials
            WHERE name = %s AND lot_number IS NULL
                           """,(name,))
        else:
            db.execute(cursor, """
            SELECT material_id, name, stock_level, reorder_level, cost_per_unit
            FROM raw_materials
            WHERE name = %s AND lot_number = %s
                           """,(name, lot_number))
        result = cursor.fetchone()


        return result

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()

def decrease_raw_material(name, decrease_amount, lot_number=None):
    """Decreases amount of material given its name and lot number and amount to subtract"""
#lot number implimentation needed
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        SELECT material_id, stock_level, unit
        FROM raw_materials
        WHERE name = %s AND lot_number = %s
        """, (name, lot_number))
        result = cursor.fetchone()

        if not result:
            print(f"{name} with lot number: {lot_number} not found in raw_materials")
            return None

        (material_id, current_stock, unit) = result

        # Check if there's enough stock
        if current_stock < decrease_amount:
            print(f"Insufficient stock: {name} with lot number: {lot_number} has {current_stock} {unit}, but {decrease_amount} {unit} is needed")
            return None

        db.execute(cursor, """
        UPDATE raw_materials
        SET stock_level = stock_level - %s
        WHERE material_id = %s AND lot_number = %s
        """, (decrease_amount, material_id, lot_number))

        db.commit()

        # Get new stock level
        db.execute(cursor, """
        SELECT stock_level
        FROM raw_materials
        WHERE material_id = %s AND lot_number = %s
        """, (material_id, lot_number))

        new_stock_level = cursor.fetchone()[0]
        print(f"Successfully deducted {decrease_amount} {unit} from {name} with lot number: {lot_number}. New stock level: {new_stock_level} {unit}")
        return new_stock_level

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()

def delete_raw_material(name, lot_number):

    """Deletes raw material from database given its name and lot number"""
#lot number implimentation needed
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        DELETE FROM raw_materials
        WHERE name = %s AND lot_number = %s
                       """,(name, lot_number))
        db.commit()
        print(f"Deleted {name} with lot number: {lot_number} from raw materials")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()

# ========================
# BATCHES FUNCTIONS
# ========================

def add_to_batches(product_name, quantity, notes=None, status='Ready', batch_id = None, deduct_resources=True, lot_selections = None):
    """
    adds batch to ready to ship, but asks user if they want to deduct from resources, or just add it.
    flow: 1.check if batch already exist
    2. look up batch product recipe
    3. for each material in recipe, ask user for lot number, then check if there is enough stock in that lot number, if not, error and stop process, if yes, deduct from raw_materials.
    4. add batch to batches, and materials used to batch_materials
    """
    # added status optional change, default is ready
    # Connect to the database
    #lot number implimentation needed (biggest change)
    db = get_db_connection()
    cursor = db.cursor()
    


    try:
        
        #get recipe data frame
        recipe_df = get_recipe(product_name)

        if recipe_df is None or recipe_df.empty:
            raise ValueError(f"No recipe found for {product_name}")  #make sure there is a recipe for that product
            
        date_completed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')    
        
        

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




                #if it doesnt already exist and isnt None:

            db.execute(cursor, """
                INSERT INTO batches (batch_id, product_name, quantity, date_completed, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (batch_id, product_name, quantity, date_completed, status, notes))


        else:# if its None:


            db.execute(cursor, """
                INSERT INTO batches (product_name, quantity, date_completed, status, notes)
                VALUES (%s, %s, %s, %s, %s)
            """, (product_name, quantity, date_completed, status, notes))
            batch_id = db.get_last_insert_id(cursor)


        #Deducting resources:


        if deduct_resources:


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

                #add to batch_materials
                db.execute(cursor, """
                INSERT INTO batch_materials (batch_id, material_id, quantity_used)
                    VALUES (%s, %s, %s)
                    """, (batch_id, material_id, required_amount))

        db.commit()
        print(f"Added {quantity} units of {product_name} (Batch {batch_id})")
        return batch_id


    except ValueError as e:
        # Re-raise ValueError so app.py can catch it and show to user
        print(f"Error adding to batches: {e}")
        db.rollback()
        raise  # ← Re-raises the ValueError to app.py

    except Exception as e:
        # If any error occurs during the process, print it and undo all changes
        print(f"Error adding to batches: {e}")
        db.rollback()  # Rollback ensures database stays consistent
        return None

    finally:
        # Always close the database connection, even if an error occurred
        db.close()


def get_batches():
    """Gets all batches ready to ship"""
    db = get_db_connection()

    query = """
    SELECT batch_id, product_name, quantity, date_completed, status, notes
    FROM batches
    WHERE status = 'Ready'
    ORDER BY date_completed
    """

    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result


def get_batches_shipped():
    """Gets all batches that have been shipped"""
    db = get_db_connection()

    query = """
    SELECT batch_id, product_name, quantity, date_completed, date_shipped, notes
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

        db.commit()
        print(f" Marked batch {batch_id} as shipped")
        return True

    except Exception as e:
        print(f" Error: {e}")
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
            print(f"Batch ID {batch_id} not found in batches.")
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



            for bm_id, material_id, quantity_used, material_name in batch_materials:

                db.execute(cursor, """
                    UPDATE raw_materials
                    SET stock_level = stock_level + %s
                    WHERE material_id = %s
                """, (quantity_used, material_id))

                materials_added.append({
                    "material": material_name,
                    "quantity_added": quantity_used
                    })

            # Delete batch
            db.execute(cursor, """
                DELETE FROM batches
                WHERE batch_id = %s
            """, (batch_id,))

            db.commit()

            print(
                f"Successfully deleted batch {batch_id}.\n"
                f"Reallocated materials: {materials_added}"
                )

        else:
            db.execute(cursor, """
                DELETE FROM batches
                WHERE batch_id = %s
            """, (batch_id,))

            db.commit()
            print(f"Successfully deleted batch {batch_id}.")




    except Exception as e:
        db.rollback()
        print(f"Error deleting batch: {e}")
        return None

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
        WHERE product_name = %s   
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

        df = pd.read_sql_query(query, db.conn, params= (recipe_id,))

        return df
        




    except Exception as e:
        print(f"Error: {e} \ngetting recipe:{product_name}.")
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
        db.execute(cursor,"SELECT LASTVAL()")
        recipe_id = cursor.fetchone()[0] # get recipe_id, able to add to recipe_materials



        for material in materials:
            material_name = material["material_name"]
            quantity_needed = material['quantity_needed']

            #check material is in database

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
              """,(recipe_id, material_name, material_id, quantity_needed))
            

        db.commit()
        print(f"Recipe '{product_name}' added successfully with {len(materials)} materials.")
        return recipe_id



    except Exception as e:
        print(f"Error: {e}")
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
        WHERE product_name = %s               
               
                       """,(product_name,))
        recipe_id = cursor.fetchone()

        if not recipe_id:
            print(f"No recipe found for {product_name}")
            return None
        recipe_id = recipe_id[0]



        db.execute(cursor,"""
        UPDATE recipes
        SET notes = %s
        WHERE product_name = %s               
                       
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
        
        db.commit()
        print(f"Recipe '{product_name}' changed successfully with {len(materials)} materials.")
        return recipe_id
        

    except Exception as e:
        print(f"Error: {e}")
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
        WHERE product_name = %s         
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
        WHERE product_name = %s               
                       """,(product_name,))
        db.commit()



        db.execute(cursor, """
        DELETE FROM recipe_materials
        WHERE recipe_id = %s
                       """,(recipe_id,))
        
        db.commit()

        print(f"Deleted {product_name} from recipe log, {product_name}'s recipe:\n{df}")
    
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        return None
    
    finally:
        db.close()