"""
Matcha Inventory Management System
Core functions for database operations and queries
"""

import sqlite3
import pandas as pd
from datetime import datetime
import os

# ========================
# DATABASE SETUP
# ========================


def create_database():
    """Creates database with raw_materials, recipes, and ready_to_ship tables"""
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
                   supplier TEXT
                     
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
                   FOREIGN KEY (material_id) REFERENCES raw_materials(material_id),
                   FOREIGN KEY (batch_id) REFERENCES ready_to_ship(batch_id)           
                  
                   
                   ) """)
    
    # Save all table creations to the database
    conn.commit()
    conn.close()
    print(" Database created")



# ========================
# RAW MATERIALS FUNCTIONS
# ========================
 
def add_raw_material(name, category, stock_level, unit, reorder_level, cost_per_unit, supplier=None):
    # adds material to raw_materials
    
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO raw_materials (name, category, stock_level, unit, reorder_level, cost_per_unit, supplier)
            VALUES (?,?,?,?,?,?,?)
                        
                        """, (name, category, stock_level, unit, reorder_level, cost_per_unit, supplier))
        
        conn.commit()
        print(f"Added {name} to raw materials")
        return cursor.lastrowid
    
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()



def get_low_stock_materials():
    "Return raw materials below if low on stock"

    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    query = """

    SELECT name, category, stock_level, reorder_level, unit
    FROM raw_materials
    WHERE stock_level <= reorder_level
    ORDER BY (stock_level / reorder_level)
    """
    result = pd.read_sql_query(query, conn)
    conn.close()
    return result


def get_all_materials():
    "Returns all materials"
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    query = """
    SELECT name, category, stock_level, unit, reorder_level, cost_per_unit, supplier
    FROM raw_materials
    ORDER BY category, name
    """

    result = pd.read_sql_query(query,conn)
    conn.close()
    return result


def increase_raw_material(name, increase_amount):
    
    """ increases amount of material given its name and amount to add"""
    
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    try:

        cursor.execute("""
        SELECT material_id, stock_level, unit
        FROM raw_materials
        WHERE name = ?
        """, (name,))
        result = cursor.fetchone()
        # gets the result from the query in form of a tuple
        
        if not result:
            print(f"{name} not found in raw_materials")
            return None
        # if the query doesnt work, tells user
        
        (material_id, current_stock, unit) = result # breaks tuple down to three new variables

        cursor.execute("""
        UPDATE raw_materials
        SET stock_level = stock_level + ?
        WHERE material_id = ?
        
        """, (increase_amount, material_id,) )
        conn.commit()

        #get new stock level
        cursor.execute("""
        SELECT stock_level
        FROM raw_materials
        WHERE material_id = ?
                       
         """, (material_id,))
        
        new_stock_level = cursor.fetchone()[0] # fetchone() returns a tuple, so get the first and only value in tuple instead of tuple
        conn.close()
        print(f"Succesfully added, {name} is now at {new_stock_level}")
        return new_stock_level
    
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return None
    
    finally:
        conn.close()



def get_raw_material(name):

    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    try:
        cursor.execute("""
        SELECT material_id, name, stock_level, reorder_level, cost_per_unit
        FROM raw_materials       
        WHERE name = ?          
                       """,(name,))
        result = cursor.fetchone()


        return result
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return None
    
    finally:
        conn.close()

def decrease_raw_material(name, decrease_amount):
    """Decreases amount of material given its name and amount to subtract"""
    
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    try:
        cursor.execute("""
        SELECT material_id, stock_level, unit
        FROM raw_materials
        WHERE name = ?
        """, (name,))
        result = cursor.fetchone()
        
        if not result:
            print(f"{name} not found in raw_materials")
            return None
        
        (material_id, current_stock, unit) = result
        
        # Check if there's enough stock
        if current_stock < decrease_amount:
            print(f"Insufficient stock: {name} has {current_stock} {unit}, but {decrease_amount} {unit} is needed")
            return None

        cursor.execute("""
        UPDATE raw_materials
        SET stock_level = stock_level - ?
        WHERE material_id = ?
        """, (decrease_amount, material_id))
        
        conn.commit()

        # Get new stock level
        cursor.execute("""
        SELECT stock_level
        FROM raw_materials
        WHERE material_id = ?
        """, (material_id,))
        
        new_stock_level = cursor.fetchone()[0]
        print(f"Successfully deducted {decrease_amount} {unit} from {name}. New stock level: {new_stock_level} {unit}")
        return new_stock_level

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return None
    
    finally:
        conn.close()


# ========================
# READY TO SHIP FUNCTIONS
# ========================

def add_to_batches(product_name, quantity, notes=None, batch_id = None):
    """
    adds batch to ready to ship, but asks user if they want to deduct from resources, or just add it. 
    """
    # Connect to the database
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()
    


    try:
        
        #get recipe data frame
        recipe_df = get_recipe(product_name)

        if recipe_df is None or recipe_df.empty:
            raise ValueError(f"No recipe found for {product_name}")  #make sure there is a recipe for that product
            
            
        
        
        while True:

            #ask user if they want to deduct or not:

            
            user_response = input(f"Do you want to deduct from resources? (Y/N):").strip().upper()
            

            if user_response not in {"Y", "N"}:
                print("Invalid input. Please enter Y or N.")
                continue
            
            
            
            date_completed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        
        



            if user_response == "N":

                #add to batches
                
                # check if batch_id already exists
                if batch_id is not None:
                    cursor.execute("""
                        SELECT 1 
                        FROM batches
                        WHERE batch_id = ?
                    """, (batch_id,))
                    if cursor.fetchone():
                        raise ValueError(f"Batch ID {batch_id} already exists.")
                    #if it doesnt already exist and isnt None:
                    cursor.execute("""
                        INSERT INTO batches (batch_id, product_name, quantity, date_completed, status, notes)
                        VALUES (?, ?, ?, ?, 'Ready', ?)
                    """, (batch_id, product_name, quantity, date_completed, notes))
                else:# if its None:
                    cursor.execute("""
                        INSERT INTO batches (product_name, quantity, date_completed, status, notes)
                        VALUES (?, ?, ?, 'Ready', ?)
                    """, (product_name, quantity, date_completed, notes))
                    batch_id = cursor.lastrowid
                
                conn.commit()
                print(f"Added {quantity} units of {product_name} to batches (Batch {batch_id})")
                return batch_id
            
            if user_response == "Y":

            
                
                
                
                materials_deducted = []# record materials_deducted
                

                #check in there is needed resources
                for _, row in recipe_df.iterrows(): #iterate through each row of recipe df
                    material_name = row['material_name'] #get material name
                    quantity_needed = row['quantity_needed'] # needed amount

                    material_info = get_raw_material(material_name)
                    if not material_info:
                        raise ValueError(f"Material {material_name} not found in inventory")
                        
                    
                    material_id, name, stock_level, reorder_level, cost_per_unit = material_info #break down tuple

                    required_amount = quantity_needed * quantity 

                    if stock_level < required_amount:
                        raise ValueError(f"Insufficient {material_name}: need {required_amount}, have {stock_level}")
                        
                    
                    else:
                        print(f"{material_name}: enough stock ({stock_level} available)")

                


                #add to batches
                
                # check if batch_id already exists
                if batch_id is not None:
                    cursor.execute("""
                        SELECT 1 
                        FROM batches 
                        WHERE batch_id = ?
                    """, (batch_id,))
                    if cursor.fetchone():
                        raise ValueError(f"Batch ID {batch_id} already exists.")
                    
                    cursor.execute("""
                        INSERT INTO batches (batch_id, product_name, quantity, date_completed, status, notes)
                        VALUES (?, ?, ?, ?, 'Ready', ?)
                    """, (batch_id, product_name, quantity, date_completed, notes))
                else:
                    cursor.execute("""
                        INSERT INTO batches (product_name, quantity, date_completed, status, notes)
                        VALUES (?, ?, ?, 'Ready', ?)
                    """, (product_name, quantity, date_completed, notes))
                    batch_id = cursor.lastrowid
                conn.commit()
                

                #deduct from raw_materials
                for _, row in recipe_df.iterrows(): #iterate through each row of recipe df
                    material_id_recipe = row['material_id'] #get id
                    material_name = row['material_name'] #get material name
                    quantity_needed = row['quantity_needed'] # needed amount
                    required_amount = quantity_needed * quantity 
                    cursor.execute("""
                    UPDATE raw_materials
                    SET stock_level = stock_level - ?               
                    WHERE material_id = ?   
                                """,(required_amount, material_id_recipe,))
                    print(f'decreased {material_name} by {required_amount}')

                    materials_deducted.append({"material": material_name, "amount deducted": required_amount})

                    cursor.execute("""
                    INSERT INTO batch_materials (batch_id, material_id, quantity_used)
                            VALUES (?, ?, ?)
                        """, (batch_id, material_id, required_amount))
                

                print(f"Added {quantity} units of {product_name} to batches (Batch: {batch_id})")
                print(f"materials deducted from resources:{materials_deducted}")
                return batch_id
            
            
            
                


    except Exception as e:
        # If any error occurs during the process, print it and undo all changes
        print(f"Error adding to batches: {e}")
        conn.rollback()  # Rollback ensures database stays consistent
        return None
    
    finally:
        # Always close the database connection, even if an error occurred
        conn.close()


def get_batches():
    """Gets all batches ready to ship"""
    conn = sqlite3.connect('data/inventory.db')
    
    query = """
    SELECT batch_id, product_name, quantity, date_completed, status, notes
    FROM batches
    WHERE status = 'Ready'
    ORDER BY date_completed
    """
    
    result = pd.read_sql_query(query, conn)
    conn.close()
    return result


def mark_as_shipped(batch_id):
    """Marks a batch as shipped"""
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
        UPDATE batches
        SET status = 'Shipped', date_shipped = ?
        WHERE batch_id = ?
        """, (datetime.now().strftime('%Y-%m-%d'), batch_id))
        
        conn.commit()
        print(f" Marked batch {batch_id} as shipped")
        return True
        
    except Exception as e:
        print(f" Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def delete_batch(batch_id):
    """
    Deletes a batch from batches.
    Optionally reallocates raw materials back into inventory.
    """

    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    try:
        # Get batch info
        cursor.execute("""
            SELECT product_name, quantity
            FROM batches
            WHERE batch_id = ?
        """, (batch_id,))
        row = cursor.fetchone()

        if not row:
            print(f"Batch ID {batch_id} not found in batches.")
            return None

        product_name, batch_quantity = row

        while True:
            user_input = input(
                "Reallocate resources used in this batch back to inventory? (Y/N): "
            ).strip().upper()

            if user_input == "Y":
                recipe_df = get_recipe(product_name)

                if recipe_df is None or recipe_df.empty:
                    raise ValueError(
                        f"No recipe found for product '{product_name}'. Cannot reallocate."
                    )

                materials_added = []

                for _, recipe_row in recipe_df.iterrows():
                    material_id = recipe_row["material_id"]
                    material_name = recipe_row["material_name"]
                    quantity_needed = recipe_row["quantity_needed"]

                    quantity_used = quantity_needed * batch_quantity

                    cursor.execute("""
                        UPDATE raw_materials
                        SET stock_level = stock_level + ?
                        WHERE material_id = ?
                    """, (quantity_used, material_id))

                    materials_added.append({
                        "material": material_name,
                        "quantity_added": quantity_used
                    })

                # Delete batch
                cursor.execute("""
                    DELETE FROM batches
                    WHERE batch_id = ?
                """, (batch_id,))

                conn.commit()

                print(
                    f"Successfully deleted batch {batch_id}.\n"
                    f"Reallocated materials: {materials_added}"
                )
                break

            elif user_input == "N":
                cursor.execute("""
                    DELETE FROM batches
                    WHERE batch_id = ?
                """, (batch_id,))

                conn.commit()
                print(f"Successfully deleted batch {batch_id}.")
                break

            else:
                print("Invalid input. Please enter Y or N.")

    except Exception as e:
        conn.rollback()
        print(f"Error deleting batch: {e}")
        return None

    finally:
        conn.close()



# ========================
# RECIPE FUNCTIONS
# ========================


def get_recipe(product_name):
    """
    Gets recipe from recipes, which refrences recipe materials

    """

    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    try:
        
        cursor.execute("""
        SELECT recipe_id
        FROM recipes
        WHERE product_name = ?   
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
        WHERE r.recipe_id = ?
        ORDER BY rm.material_name ASC
        """)

        df = pd.read_sql_query(query, conn, params= (recipe_id,))

        return df
        




    except Exception as e:
        print(f"Error: {e} \ngetting recipe:{product_name}.")
        return None
    
    finally:
        conn.close()
    


def add_recipe(product_name, materials, notes=None):
     
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

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

        cursor.execute("""
        INSERT INTO recipes (product_name, notes)
        VALUES (?, ?)               
         """,(product_name, notes))
        recipe_id = cursor.lastrowid # get recipe_id, able to add to recipe_materials



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


            cursor.execute("""
            INSERT INTO recipe_materials (
                   recipe_id,
                   material_name,
                   material_id,
                   quantity_needed)
            VALUES (?,?,?,?)                              
              """,(recipe_id, material_name, material_id, quantity_needed))
            

        conn.commit()
        print(f"Recipe '{product_name}' added successfully with {len(materials)} materials.")
        return recipe_id



    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return None
    
    finally:
        conn.close()
     

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
    
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()
    
    try:

        cursor.execute("""
        SELECT recipe_id
        FROM recipes
        WHERE product_name = ?               
               
                       """,(product_name,))
        recipe_id = cursor.fetchone()

        if not recipe_id:
            print(f"No recipe found for {product_name}")
            return None
        recipe_id = recipe_id[0]



        cursor.execute("""
        UPDATE recipes
        SET notes = ?
        WHERE product_name = ?               
                       
                       """,(notes, product_name,))
        

        cursor.execute("""
        DELETE FROM recipe_materials
        WHERE recipe_id = ?               
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


            cursor.execute("""
            INSERT INTO recipe_materials (
            
            recipe_id,
            material_name,
            material_id,
            quantity_needed)
            VALUES (?,?,?,?)                             
                """, (recipe_id, material_name, material_id, quantity_needed))
        
        conn.commit()
        print(f"Recipe '{product_name}' changed successfully with {len(materials)} materials.")
        return recipe_id
        

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return None
    
    finally:
        conn.close()
    

def delete_recipe(product_name):


    "deletes recipe"

    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    try:

        #get id
        cursor.execute("""
        SELECT recipe_id
        FROM recipes
        WHERE product_name = ?         
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
        WHERE recipe_id = ?                             
                       """)
        df = pd.read_sql_query(query, conn, params=(recipe_id,) )

        #clean query for presentation

        df = df.rename(columns={
            'material_name': 'Material',
        'quantity_needed': 'Quantity Needed'
            })
        
        
        #delete recipe from recipes
        cursor.execute("""
        DELETE FROM recipes
        WHERE product_name = ?               
                       """,(product_name,))
        conn.commit()

        
        
        cursor.execute("""
        DELETE FROM recipe_materials
        WHERE recipe_id = ?               
                       """,(recipe_id,))
        
        conn.commit()

        print(f"Deleted {product_name} from recipe log, {product_name}'s recipe:\n{df}")
    
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return None
    
    finally:
        conn.close()



#======================== 
#TESTING
#================


if __name__ == "__main__":
    
    if os.path.exists("data/inventory.db"):
        os.remove("data/inventory.db")
    
    
    
    # Step 1: Create database
    create_database()

    # Step 2: Add raw materials
    add_raw_material("Matcha", "Powder", 1000, "g", 100, 0.05)
    add_raw_material("Milk Powder", "Powder", 5000, "g", 200, 0.02)
    add_raw_material("Sugar", "Powder", 2000, "g", 100, 0.01)

    # Step 3: Add a recipe
    materials = [
        {"material_name": "Matcha", "quantity_needed": 2},   # per unit
        {"material_name": "Milk Powder", "quantity_needed": 30},
        {"material_name": "Sugar", "quantity_needed": 5}
    ]
    add_recipe("Matcha Latte", materials, notes="Classic sweetened")

    # Step 4: Produce a batch
    print("\n--- Produce a batch ---")
    batch_id = add_to_batches("Matcha Latte", 10, notes="Morning batch", batch_id = 67)
    print(f"Batch created: {batch_id}")

    # Step 5: Check tables
    print("\n--- Raw Materials ---")
    print(get_all_materials())

    print("\n--- Ready to Ship ---")
    print(get_batches())

    print("\n--- Recipe ---")
    print(get_recipe("Matcha Latte"))


    #more testing:
    #increase raw_material:
    increase_raw_material('Matcha', 42067, )

    print("\n--- Raw Materials  2 ---")
    print(get_all_materials())