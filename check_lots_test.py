import sqlite3
conn = sqlite3.connect('data/inventory.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM raw_material_lots")
print(cursor.fetchall())
conn.close()