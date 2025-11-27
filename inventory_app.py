"""
Matcha Inventory Management System
Core functions for database operations and queries
"""

import sqlite3
import pandas as pd
from datetime import datetime

# ========================
# DATABASE SETUP
# ========================


def creat_databases():
    """Creates database with raw_materials, recipes, and ready_to_ship tables"""
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    #Raw Materials 

    cursor.execute("""
    CREATE TABLE IN NOT EXISTS raw_materials(
                   material_id INTEGER PRIMARY KEY AUTOINCRIMENT,
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
    CREATE TABLE IF NOT EXIST recipes(
                   recipe_id INTEGER PRIMARY KEY AUTOINCRIMENT,
                   name TEXT NOT NULL UNIQUE,
                   category TEXT
                   
                   )
                   """)
    #recipes ingredients, references recipes
    #each row = one ingredient in one recipe
    #one recipe has a recipe_id, and each ingredient under that recipe shares the same recipe_id
    cursor.execute("""
    CREATE TABLE IN NOT EXIST recipe_ingredients(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   recipe_id INTEGER NOT NULL,
                   material_id INTEGER NOT NULL,
                   ammount_needed REAL NOT NULL,
                   unit TEXT NOT NULL,
                   FOREIGN KEY (recipe_id) REFERENCES recipes(recipe_id),
                   FOREIGN KEY (material_id) REFERENCES raw_materials(material_id)
                   """)
    
    # Ready to ship
    cursor.execute("""
    CREATE TABLE IN NOT EXIST ready_to_ship(
                    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    quantity INTEGER,
                    date_completed TEXT,
                    status TEXT DEFAULT 'Ready',
                    notes TEXT,
                    date_shipped TEXT
                
                   )
                   """)
    
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
        cursor.excecute("""
            INSERT INTO raw_materials (name, category, stock_level, unit, reorder_level, cost_per_unit, supplier)
            VALUES (?,?,?,?,?,?,?)
                        
                        """, (name, category, stock_level, unit, reorder_level, cost_per_unit, supplier))
        
        conn.commit
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

    try:

        cursor.execute("""
                    
        SELECT name, category, stock_level, reorder_level, unit
        FROM raw_materials
        WHERE stock_level <= reorder_level
        ORDER BY (stock_level / reorder_level)         
        """)
        rows = cursor.fetchall() 

        
        print("Low of following materials:")
        for row in rows:
            print(row)
        
    except Exception as e:
        print(f'Error:{e} when trying to find low stock levels.')


    finally:
        conn.close()


def get_all_materials():
    "Returns all materials"
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()



    try:
        cursor.execute("""
                     
        SELECT name, category, stock_level, unit, reorder_level, cost_per_unit, supplier
        FROM raw_materials
        ORDER BY category, name
                     """)
   
        rows = cursor.fetchall()

        print(f'Current materials in inventory:')
        for row in rows:
            print(row)
    

    except Exception as e:
        print(f"Error:{e} when finding all materals")

    
    
    
    finally:
        conn.close()
    




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
        SET stock_level + ?
        WHERE material_id = ?
        
        """, (increase_amount, material_id) )
        

        #get new stock level
        cursor.execute("""
        SELECT stock_level
        FROM raw_materials
        WHERE material_id = ?
                       
         """, (material_id))
        
        new_stock_level = cursor.fetchone()[0] # fetchone() returns a tuple, so get the first and only value in tuple instead of tuple
        conn.close()
        print(f"Succesfully added, {name} is now at {new_stock_level}")

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
# RECIPE FUNCTIONS
# ========================

def get_recipe(name):
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    try:
        #get recipe id
        cursor.execute("""
                       
        SELECT recipe_id
        FROM recipes
        WHERE name = ?""", (name,))

        result = cursor.fetchone()

        if not result:
            print(f'Recipe:{name}, not found')
        
        recipe_id = result[0]
        #get all ingredients from recipe
        
        cursor.execute("""
            SELECT rm.material_id, rm.name, ri.amount_needed, ri.unit
            FROM recipe_ingredients ri
            JOIN raw_materials rm ON ri.material_id = rm.material_id
            WHERE ri.recipe_id = ?         
                       
                       """,(recipe_id,))
        rows = cursor.fetchall()

        materials = []
        for row in rows:
            material_id, material_name, amount_needed, unit = row
            materials.append({"material_id": material_id, "name": material_name, "amount_needed": amount_needed, "unit": unit})

        return materials
    
    except Exception as e:
        print(f'Error:{e} when fetching recipe.')

    

    finally:
        conn.close()






 
# ========================
# READY TO SHIP FUNCTIONS
# ========================


def get_ready_to_ship():

    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()
    try:
        
        cursor.execute("""
                       
        SELECT * 
        FROM ready_to_ship
        ORDER BY category, name
                       """)
    
        rows =  cursor.fetchall()

        print("Ready to ship products:")
        for row in rows:
            print(row)




    except Exception as e:
        print(f"Error:{e} when retreiving ready to ship products")

    finally:
        conn.close()





def add_to_ready_to_ship(product_name, quantity, notes=None):
    """
    Adds a product to ready_to_ship table and automatically deducts raw materials
    from raw_materials table based on the product's recipe
    

    1. Looks up the recipe for the product in the recipes table
    2. finds the recipe materials from recipe_id in recipe_ingredients
    3. Checks if there are enough raw materials in stock
    4. deducts the required materials from raw_materials table
    5. Adds the product batch to ready_to_ship table
    
    """
    
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()
    
    try:
        
        recipe = get_recipe(product_name)
        if not recipe:
            print(f"No recipe found for '{product_name}'")
            return None
        

        
        insufficient_materials = []  

        for ingredient in recipe:
            required = ingredient["amount_needed"] * quantity
            
        
       
        for material_id, quantity_per_unit in recipe_items:
            
            cursor.execute("""
            SELECT name, stock_level, unit
            FROM raw_materials
            WHERE material_id = ?
            """, (material_id,))
            
            material_info = cursor.fetchone()
            
            #saftey check
            if not material_info:
                print(f"Error: Material with ID {material_id} not found")
                conn.rollback()
                return None
            
            # unpack material information
            material_name, current_stock, unit = material_info
            
            
            required_amount = quantity_per_unit * quantity
            
           
            if current_stock < required_amount:
                

                insufficient_materials.append({
                    'name': material_name,

                    'required': required_amount,
                    'available': current_stock,
                    'unit': unit
                })
        
        
        #if insufficient materials, abort and report
        
        
        if insufficient_materials:
            print(f"Error: Insufficient raw materials to produce {quantity} units of {product_name}:")
            

            for mat in insufficient_materials:
                print(f"  - {mat['name']}: Need {mat['required']} {mat['unit']}, but only {mat['available']} {mat['unit']} available")
            conn.rollback()  
            return None
        
        



        # all good for required amount:
        # procede to incrase to ready to ship and decrease from raw materials

        for material_id, quantity_per_unit in recipe_items:
            

            required_amount = quantity_per_unit * quantity
            
            
            cursor.execute("""
            SELECT name, unit
            FROM raw_materials
            WHERE material_id = ?
            """, (material_id,))
            material_name, unit = cursor.fetchone()
            
            #deduct the required amount from the materials stock level
            cursor.execute("""
            UPDATE raw_materials
            SET stock_level = stock_level - ?
            WHERE material_id = ?
            """, (required_amount, material_id))
            
            # log what was deducted 
            print(f"Deducted {required_amount} {unit} of {material_name}")
        
       
        date_completed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # insert the new batch into ready_to_ship table
        cursor.execute("""
        INSERT INTO ready_to_ship (product_name, quantity, date_completed, status, notes)
        VALUES (?, ?, ?, 'Ready', ?)
        """, (product_name, quantity, date_completed, notes))
        
        # get the batch_id that was automatically generated
        batch_id = cursor.lastrowid
        
    
        conn.commit()
        
        # success message with batch ID 
        print(f"Successfully added {quantity} units of {product_name} to ready_to_ship (Batch ID: {batch_id})")
        return batch_id
        
    except Exception as e:
        
        print(f"Error adding to ready_to_ship: {e}")
        conn.rollback()  
        return None
    
    finally:
        conn.close()
    
                    
                    
                  

