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





    








 

             
                    
                    
                  

