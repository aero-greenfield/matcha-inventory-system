import sqlite3
from inventory_app import receive_lot, get_all_materials, get_lots_for_material, get_all_lots_for_material, get_material_stock_from_lots

conn = sqlite3.connect('data/inventory.db')
cursor = conn.cursor()

# ── SEED DATA ──────────────────────────────────────────────
# Two raw materials
cursor.execute("INSERT INTO raw_materials (name, category, unit, reorder_level, is_housemade) VALUES ('Ceremonial Matcha', 'Powder', 'kg', 10, FALSE)")
matcha_id = cursor.lastrowid

cursor.execute("INSERT INTO raw_materials (name, category, unit, reorder_level, is_housemade) VALUES ('Sugar', 'Ingredient', 'kg', 5, FALSE)")
sugar_id = cursor.lastrowid

conn.commit()
print(f"Seeded materials — matcha_id: {matcha_id}, sugar_id: {sugar_id}")

conn.close()

# ── TESTS ──────────────────────────────────────────────────
print("\n=== receive_lot ===")
lot1 = receive_lot(matcha_id, 'IPP-2026-001', 30.0, '2026-01-10', expiry_date='2026-07-01', location='Warehouse A')
lot2 = receive_lot(matcha_id, 'IPP-2026-031', 25.0, '2026-03-15', expiry_date='2026-09-01', location='Warehouse B')
lot3 = receive_lot(sugar_id, 'SUG-2026-005', 15.0, '2026-02-01', location='Warehouse A')
print(f"Inserted lots: {lot1}, {lot2}, {lot3}")

print("\n=== get_all_materials ===")
print(get_all_materials())

print("\n=== get_material_stock_from_lots (matcha) ===")
print(get_material_stock_from_lots(matcha_id))

print("\n=== get_lots_for_material (matcha) ===")
print(get_lots_for_material(matcha_id))

print("\n=== get_all_lots_for_material (matcha) ===")
print(get_all_lots_for_material(matcha_id))

print("\n=== receive_lot validation — should reject qty 0 ===")
bad = receive_lot(matcha_id, 'BAD-LOT', 0, '2026-01-01')
print(f"Result (should be None): {bad}")