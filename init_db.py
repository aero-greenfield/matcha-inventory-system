
""" 
Database Initialization Script 
 
PURPOSE: 
- Creates all tables in PostgreSQL when first deploying 
- Migrates schema from SQLite to PostgreSQL 
- Run this ONCE when setting up Railway 
 
WHEN TO RUN: 
- First Railway deployment (PostgreSQL is empty) 
- After adding new tables 
- To reset database (careful - deletes all data!) 
 
HOW TO RUN: using railway posgresql database
- Railway dashboard → Settings → Start Command → python init_db.py 
- Or locally: python init_db.py 


HOW TO RUN using subapase postgresql database
- Make sure you have python-dotenv installed: pip install python-dotenv
- Run locally: python init_db.py

""" 

##################new try except block for new load env variable#####################
## this is for SUPABASE POSTGRESQL DATABASE CONNECTION ## (new main database)
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("🔍 Loaded environment variables from .env file")

except ImportError:
    print("🔍 python-dotenv not installed, skipping .env loading")
    pass 
 
from database import get_connection 
 
def init_database(): 
   """ 
  Creates all database tables. 
    
   IMPORTANT DIFFERENCE FROM SQLite: 
   - SQLite uses: INTEGER PRIMARY KEY AUTOINCREMENT 
   - PostgreSQL uses: SERIAL PRIMARY KEY 
   - SERIAL = auto-incrementing integer in PostgreSQL 
   """ 
    
   print("🔧 Connecting to database...") 
   conn = get_connection() 
   cursor = conn.cursor() 
    
   print("📋 Creating tables...") 
    
   # ======================================== 
   # TABLE 1: raw_materials 
   # ======================================== 
   cursor.execute(""" 
   CREATE TABLE IF NOT EXISTS raw_materials( 
       material_id SERIAL PRIMARY KEY, 
       name TEXT NOT NULL, 
       category TEXT,   
       stock_level REAL, 
       unit TEXT, 
       reorder_level REAL,  
       cost_per_unit REAL, 
       supplier TEXT 
   ) 
   """) 
    
   # What changed from SQLite? 
   # OLD: material_id INTEGER PRIMARY KEY AUTOINCREMENT 
   # NEW: material_id SERIAL PRIMARY KEY 
   # SERIAL = PostgreSQL's auto-increment 
   # Same functionality, different syntax 
    
   print("  ✅ raw_materials table created") 
    
   # ======================================== 
   # TABLE 2: recipes 
   # ======================================== 
   cursor.execute(""" 
   CREATE TABLE IF NOT EXISTS recipes( 
       recipe_id SERIAL PRIMARY KEY, 
       product_name TEXT NOT NULL, 
       notes TEXT 
   ) 
   """) 
    
   print("  ✅ recipes table created") 
    
   # ======================================== 
   # TABLE 3: recipe_materials 
   # ======================================== 
   cursor.execute(""" 
   CREATE TABLE IF NOT EXISTS recipe_materials( 
       recipe_material_id SERIAL PRIMARY KEY, 
       recipe_id INTEGER, 
       material_id INTEGER, 
       material_name TEXT, 
       quantity_needed REAL, 
       FOREIGN KEY (material_id) REFERENCES raw_materials(material_id), 
       FOREIGN KEY (recipe_id) REFERENCES recipes(recipe_id) 
   ) 
   """) 
    
   print("  ✅ recipe_materials table created") 
    
   # ======================================== 
   # TABLE 4: batches 
   # ======================================== 
   cursor.execute(""" 
   CREATE TABLE IF NOT EXISTS batches( 
       batch_id SERIAL PRIMARY KEY, 
       product_name TEXT NOT NULL, 
       quantity INTEGER, 
       date_completed TEXT, 
       status TEXT DEFAULT 'Ready', 
       notes TEXT, 
       date_shipped TEXT 
   ) 
   """) 
    
   print("  ✅ batches table created") 
    
   # ======================================== 
   # TABLE 5: batch_materials 
   # ======================================== 
   cursor.execute(""" 
   CREATE TABLE IF NOT EXISTS batch_materials( 
       batch_material_id SERIAL PRIMARY KEY, 
       batch_id INTEGER, 
       material_id INTEGER, 
       quantity_used REAL, 
       FOREIGN KEY (material_id) REFERENCES raw_materials(material_id), 
       FOREIGN KEY (batch_id) REFERENCES batches(batch_id) 
   ) 
   """) 
    
   print("  ✅ batch_materials table created") 
    
   # ======================================== 
   # Save all changes 
   # ======================================== 
   conn.commit() 
   conn.close() 
    
   print("\n🎉 Database initialized successfully!") 
   print("📊 All tables created and ready to use") 
 
 
# ============================================================ 
# RUN THIS SCRIPT 
# ============================================================ 
if __name__ == "__main__":
 
    init_database()
    