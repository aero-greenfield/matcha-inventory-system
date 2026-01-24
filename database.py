""" 
Database Connection Abstraction Layer 
 
PURPOSE: 
- Makes app work with BOTH SQLite (local) and PostgreSQL (cloud) 
- Automatically detects which database to use based on environment 
- No code changes needed when deploying! 
 
HOW IT WORKS: 
- Local dev: Uses SQLite (data/inventory.db) 
- Cloud (Railway): Uses PostgreSQL (from DATABASE_URL env variable) 
""" 
 
import os 
import sqlite3 

# Try to import psycopg2 (only available when installed)
# This prevents import warnings in your IDE
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    # psycopg2 not installed (local development)
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
 
# Check if we're running in cloud 
# Railway automatically sets DATABASE_URL environment variable 
DATABASE_URL = os.getenv('DATABASE_URL')

print(f"🔍 database.py: DATABASE_URL = {DATABASE_URL[:50] if DATABASE_URL else 'None'}...")
print(f"🔍 database.py: PSYCOPG2_AVAILABLE = {PSYCOPG2_AVAILABLE}")
 
 
def get_connection(): 
   """ 
   Returns database connection based on environment.     
   Returns: 
     Connection object (sqlite3.Connection or psycopg2.Connection) 
    
   Example usage: 
       conn = get_connection() 
       cursor = conn.cursor() 
       cursor.execute("SELECT * FROM materials") 
       conn.close() 
    
   How it decides: 
   - If DATABASE_URL exists → PostgreSQL (we're in cloud) 
   - If DATABASE_URL is None → SQLite (we're local) 
   """ 
    
   if DATABASE_URL: 
       # ======================================== 
       # CLOUD MODE: Use PostgreSQL 
       # ======================================== 
       print("🔍 get_connection: Using PostgreSQL")
       
       if not PSYCOPG2_AVAILABLE:
           raise ImportError(
               "DATABASE_URL is set but psycopg2 is not installed. "
               "Install it with: pip install psycopg2-binary"
           )
        
       # Railway gives URL like: postgres://user:pass@host/db 
       # psycopg2 expects: postgresql://user:pass@host/db 
       # Fix: Replace "postgres://" with "postgresql://" 
       connection_string = DATABASE_URL.replace('postgres://', 'postgresql://', 1) 
       
       print(f"🔍 get_connection: Connecting to {connection_string[:50]}...")
        
       # Connect to PostgreSQL 
       return psycopg2.connect(connection_string) 
    
   else: 
       # ======================================== 
       # LOCAL MODE: Use SQLite 
       # ======================================== 
       print("🔍 get_connection: Using SQLite (data/inventory.db)")
       return sqlite3.connect('data/inventory.db')