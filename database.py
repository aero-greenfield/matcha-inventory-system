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
 
# Check if we're running in cloud 
# Railway automatically sets DATABASE_URL environment variable 
DATABASE_URL = os.getenv('DATABASE_URL') 
 
# What is os.getenv()? 
# - Reads environment variable (like a global setting) 
# - Returns None if variable doesn't exist 
# - Railway sets DATABASE_URL = "postgresql://user:pass@host/db" 
# - Locally, DATABASE_URL doesn't exist, so returns None 
 
 
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
       import psycopg2 
        
       # Railway gives URL like: postgres://user:pass@host/db 
       # psycopg2 expects: postgresql://user:pass@host/db 
       # Fix: Replace "postgres://" with "postgresql://" 
       connection_string = DATABASE_URL.replace('postgres://', 'postgresql://', 1) 
        
       # Why replace? 
       # - Railway uses older URL format (postgres://) 
       # - psycopg2 uses newer format (postgresql://) 
       # - They're the same, just different spelling 
       # - replace(old, new, 1) = replace first occurrence only 
        
       # Connect to PostgreSQL 
       return psycopg2.connect(connection_string) 
        
       # What just happened? 
       # - Imported psycopg2 (PostgreSQL driver) 
       # - Fixed URL format 
       # - Connected to cloud database 
       # - Returned connection object 
    
   else: 
       # ======================================== 
       # LOCAL MODE: Use SQLite 
       # ======================================== 
       return sqlite3.connect('data/inventory.db') 
        
       # What just happened? 
       # - Connected to local SQLite file 
       # - No import needed (sqlite3 is built into Python) 
       # - Returned connection object 
 
 
# ============================================================ 
# USAGE EXAMPLE (for your reference) 
# ============================================================ 
# Instead of this (old way): 
#     conn = sqlite3.connect('data/inventory.db') 
# 
# Use this (new way): 
#     from database import get_connection 
#     conn = get_connection() 
# 
# Same code works locally AND in cloud! 
# ============================================================ 
 
 
# ============================================================ 
# WHY THIS MATTERS 
# ============================================================ 
# Without this file: 
# - Would need TWO versions of inventory_app.py 
# - One for local (SQLite) 
# - One for cloud (PostgreSQL) 
# - Hard to maintain! 
# 
# With this file: 
# - ONE version of inventory_app.py 
# - Works everywhere 
# - Automatically adapts to environment 
# ============================================================