import sqlite3
from inventory_app import promote_planned_batches

conn = sqlite3.connect('data/inventory.db')

# Set the finished batch to overdue
conn.execute("UPDATE batches SET planned_completion_date = '2026-03-18' WHERE batch_type = 'finished'")
conn.commit()

# Confirm before
print('BEFORE promotion:')
rows = conn.execute("SELECT batch_id, status, planned_completion_date, promotion_failure_reason FROM batches WHERE batch_type = 'finished'").fetchall()
print(rows)
conn.close()

# Run promotion — stock is 0 so should fail
promote_planned_batches()

# Check after
conn = sqlite3.connect('data/inventory.db')
print('\nAFTER promotion:')
rows = conn.execute("SELECT batch_id, status, planned_completion_date, promotion_failure_reason FROM batches WHERE batch_type = 'finished'").fetchall()
print(rows)
conn.close()