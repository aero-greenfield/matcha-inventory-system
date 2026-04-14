import sqlite3
conn = sqlite3.connect('data/inventory.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", cursor.fetchall())

cursor.execute("PRAGMA table_info(raw_materials)")
print("\nraw_materials:", cursor.fetchall())

cursor.execute("PRAGMA table_info(raw_material_lots)")
print("\nraw_material_lots:", cursor.fetchall())

cursor.execute("PRAGMA table_info(batch_materials)")
print("\nbatch_materials:", cursor.fetchall())

cursor.execute("PRAGMA table_info(batches)")
print("\nbatches:", cursor.fetchall())

conn.close()