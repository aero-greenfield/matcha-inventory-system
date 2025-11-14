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
                   recipie_id INTEGER PRIMARY KEY AUTOINCRIMENT,
                   product_name TEXT NOT NULL,
                   material_id INTEGER,
                   quantity_per_unit REAL,
                   FOREIGN KEY (material_id) FROM raw_materials(material_id)
                   
                   )
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
# READY TO SHIP FUNCTIONS
# ========================

def add_to_ready_to_ship(product_name, quantity, notes=None):
    """
    Adds a product to ready_to_ship table and automatically deducts raw materials
    from raw_materials table based on the product's recipe.
    
    This function performs the following steps:
    1. Looks up the recipe for the product in the recipes table
    2. Checks if there are enough raw materials in stock
    3. If sufficient, deducts the required materials from raw_materials table
    4. Adds the product batch to ready_to_ship table
    
    Args:
        product_name: Name of the product to add (must exist in recipes table)
        quantity: Number of units of the product to add
        notes: Optional notes for the batch (e.g., special instructions)
    
    Returns:
        batch_id if successful, None otherwise
    """
    # Connect to the database
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()
    
    try:
        # ============================================
        # STEP 1: Get the recipe for this product
        # ============================================
        # Query the recipes table to find all raw materials needed for this product
        # Each row in recipes represents one material needed for the product
        cursor.execute("""
        SELECT material_id, quantity_per_unit
        FROM recipes
        WHERE product_name = ?
        """, (product_name,))
        
        # Fetch all recipe entries (a product can have multiple materials)
        recipe_items = cursor.fetchall()
        
        # Check if recipe exists - if not, we can't produce this product
        if not recipe_items:
            print(f"Error: No recipe found for product '{product_name}'")
            conn.rollback()  # Undo any changes
            return None
        
        # ============================================
        # STEP 2: Check if we have enough raw materials
        # ============================================
        # Before deducting anything, verify we have sufficient stock
        # This prevents partial deductions if we run out mid-process
        insufficient_materials = []  # List to track any materials we're short on
        
        # Loop through each material in the recipe
        for material_id, quantity_per_unit in recipe_items:
            # Get the material's details (name, current stock, unit) from raw_materials table
            cursor.execute("""
            SELECT name, stock_level, unit
            FROM raw_materials
            WHERE material_id = ?
            """, (material_id,))
            
            material_info = cursor.fetchone()
            # Safety check: make sure the material exists
            if not material_info:
                print(f"Error: Material with ID {material_id} not found")
                conn.rollback()
                return None
            
            # Unpack the material information
            material_name, current_stock, unit = material_info
            
            # Calculate how much of this material we need
            # Example: If recipe says 0.5 kg per unit and we're making 10 units, we need 5 kg
            required_amount = quantity_per_unit * quantity
            
            # Check if we have enough stock
            if current_stock < required_amount:
                # Add to insufficient list for reporting
                insufficient_materials.append({
                    'name': material_name,
                    'required': required_amount,
                    'available': current_stock,
                    'unit': unit
                })
        
        # ============================================
        # STEP 3: If insufficient materials, abort and report
        # ============================================
        # If any materials are insufficient, don't proceed with production
        # This ensures we never partially deduct materials
        if insufficient_materials:
            print(f"Error: Insufficient raw materials to produce {quantity} units of {product_name}:")
            # Print details for each insufficient material
            for mat in insufficient_materials:
                print(f"  - {mat['name']}: Need {mat['required']} {mat['unit']}, but only {mat['available']} {mat['unit']} available")
            conn.rollback()  # Undo any changes
            return None
        
        # ============================================
        # STEP 4: All checks passed - deduct materials
        # ============================================
        # Now that we've verified we have enough materials, deduct them from inventory
        # Loop through each material in the recipe again
        for material_id, quantity_per_unit in recipe_items:
            # Calculate required amount (same calculation as before)
            required_amount = quantity_per_unit * quantity
            
            # Get material name and unit for logging purposes
            cursor.execute("""
            SELECT name, unit
            FROM raw_materials
            WHERE material_id = ?
            """, (material_id,))
            material_name, unit = cursor.fetchone()
            
            # Deduct the required amount from the material's stock level
            cursor.execute("""
            UPDATE raw_materials
            SET stock_level = stock_level - ?
            WHERE material_id = ?
            """, (required_amount, material_id))
            
            # Log what was deducted for transparency
            print(f"Deducted {required_amount} {unit} of {material_name}")
        
        # ============================================
        # STEP 5: Add product to ready_to_ship table
        # ============================================
        # Create a timestamp for when this batch was completed
        date_completed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert the new batch into ready_to_ship table
        cursor.execute("""
        INSERT INTO ready_to_ship (product_name, quantity, date_completed, status, notes)
        VALUES (?, ?, ?, 'Ready', ?)
        """, (product_name, quantity, date_completed, notes))
        
        # Get the batch_id that was automatically generated
        batch_id = cursor.lastrowid
        
        # Commit all changes to the database (both material deductions and batch insertion)
        # This ensures atomicity - either everything succeeds or everything fails
        conn.commit()
        
        # Success message with batch ID for reference
        print(f"Successfully added {quantity} units of {product_name} to ready_to_ship (Batch ID: {batch_id})")
        return batch_id
        
    except Exception as e:
        # If any error occurs during the process, print it and undo all changes
        print(f"Error adding to ready_to_ship: {e}")
        conn.rollback()  # Rollback ensures database stays consistent
        return None
    
    finally:
        # Always close the database connection, even if an error occurred
        conn.close()


# ========================
# RECIPE FUNCTIONS
# ========================



    








 

             
                    
                    
                  

