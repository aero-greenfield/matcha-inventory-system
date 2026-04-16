import sqlite3
from inventory_app import promote_planned_batches

conn = sqlite3.connect('data/inventory.db')

# Give Matcha Mix enough stock to cover the batch
conn.execute("UPDATE raw_materials SET stock_level = 999 WHERE name = 'Matcha Mix'")
conn.commit()

# Confirm stock before
print('STOCK BEFORE:')
rows = conn.execute("SELECT name, stock_level FROM raw_materials").fetchall()
print(rows)

# Confirm batch state before
print('\nBATCH BEFORE:')
rows = conn.execute("SELECT batch_id, status, date_completed, promotion_failure_reason FROM batches WHERE batch_type = 'finished'").fetchall()
print(rows)
conn.close()

# Run promotion — stock is sufficient so should succeed
promote_planned_batches()

# Check results
conn = sqlite3.connect('data/inventory.db')
print('\nBATCH AFTER:')
rows = conn.execute("SELECT batch_id, status, date_completed, promotion_failure_reason FROM batches WHERE batch_type = 'finished'").fetchall()
print(rows)

print('\nSTOCK AFTER:')
rows = conn.execute("SELECT name, stock_level FROM raw_materials").fetchall()
print(rows)
conn.close()