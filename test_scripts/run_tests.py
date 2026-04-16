"""
Batch/Inventory test suite — runs directly against local SQLite DB.
No Flask server needed.
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from inventory_app import (
    add_raw_material,
    add_to_batches,
    add_recipe,
    promote_planned_batches,
    get_raw_material,
)
from database import get_db_connection

# ── helpers ────────────────────────────────────────────────────────────────

passed = 0
failed = 0
warnings = 0
failures_for_demo = []

YESTERDAY = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')


def result(label, ok, msg="", warn=False):
    global passed, failed, warnings
    if warn:
        warnings += 1
        print(f"  WARNING  {label}: {msg}")
    elif ok:
        passed += 1
        print(f"  PASS     {label}")
    else:
        failed += 1
        failures_for_demo.append(label)
        print(f"  FAIL     {label}: {msg}")


def raw_cursor_fetchone(sql):
    """Run a no-param SQL query and return fetchone() — bypasses db.execute wrapper."""
    conn = sqlite3.connect('data/inventory.db')
    row = conn.execute(sql).fetchone()
    conn.close()
    return row


def raw_cursor_fetchall(sql):
    conn = sqlite3.connect('data/inventory.db')
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def get_stock(name):
    row = get_raw_material(name)
    return float(row[2]) if row else None


def get_housemade_flag(name):
    db = get_db_connection()
    cursor = db.cursor()
    db.execute(cursor, "SELECT is_housemade FROM raw_materials WHERE name = %s", (name,))
    row = cursor.fetchone()
    db.close()
    return bool(row[0]) if row else None


def get_batch_row(batch_id):
    db = get_db_connection()
    cursor = db.cursor()
    db.execute(cursor, """
        SELECT batch_id, product_name, quantity, status, batch_type, promotion_failure_reason
        FROM batches WHERE batch_id = %s
    """, (batch_id,))
    row = cursor.fetchone()
    db.close()
    return row


def get_batch_materials_rows(batch_id):
    db = get_db_connection()
    cursor = db.cursor()
    db.execute(cursor,
        "SELECT material_id, quantity_used FROM batch_materials WHERE batch_id = %s",
        (batch_id,))
    rows = cursor.fetchall()
    db.close()
    return rows


def set_stock(name, new_stock):
    db = get_db_connection()
    cursor = db.cursor()
    db.execute(cursor, "UPDATE raw_materials SET stock_level = %s WHERE name = %s",
               (new_stock, name))
    db.commit()
    db.close()


def force_batch_date(batch_id, date_str):
    db = get_db_connection()
    cursor = db.cursor()
    db.execute(cursor,
        "UPDATE batches SET planned_completion_date = %s WHERE batch_id = %s",
        (date_str, batch_id))
    db.commit()
    db.close()


def cleanup_test_data():
    """Remove any Test* rows left over from a previous run."""
    conn = sqlite3.connect('data/inventory.db')
    conn.execute("""
        DELETE FROM batch_materials
        WHERE batch_id IN (SELECT batch_id FROM batches WHERE product_name LIKE 'Test%')
    """)
    conn.execute("DELETE FROM batches WHERE product_name LIKE 'Test%'")
    conn.execute("""
        DELETE FROM recipe_materials
        WHERE recipe_id IN (SELECT recipe_id FROM recipes WHERE product_name LIKE 'Test%')
    """)
    conn.execute("DELETE FROM recipes WHERE product_name LIKE 'Test%'")
    conn.execute("DELETE FROM raw_materials WHERE name LIKE 'Test%'")
    conn.commit()
    conn.close()


# ── PRE-TEST CLEANUP (clear any leftovers from a crashed run) ──────────────

print("\nPre-test cleanup of any leftover Test* data...")
cleanup_test_data()
print("  Done.")


# ── SETUP ──────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("SETUP")
print("="*60)

mat_a_id = add_raw_material("Test Ingredient A", "Test", 500, "units", 0)
mat_b_id = add_raw_material("Test Ingredient B", "Test", 300, "units", 0)
print(f"  Added Test Ingredient A (id={mat_a_id}), Test Ingredient B (id={mat_b_id})")

recipe_mix_id = add_recipe("Test Mix", [
    {"material_name": "Test Ingredient A", "quantity_needed": 50},
    {"material_name": "Test Ingredient B", "quantity_needed": 30},
])
print(f"  Added recipe 'Test Mix' (id={recipe_mix_id})")


# ── BLOCK 1 ────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("BLOCK 1 — Mix Batch (stage 1)")
print("="*60)

# Test 1.1
print("\n--- Test 1.1 — Create mix batch (qty=2) ---")
try:
    b1_id = add_to_batches("Test Mix", 2, batch_type='mix')

    batch_row = get_batch_row(b1_id)
    result("1.1a batch_type='mix'",
           batch_row is not None and batch_row[4] == 'mix',
           f"batch_row={batch_row}")

    stock_a = get_stock("Test Ingredient A")
    result("1.1b Ingredient A stock = 400",
           stock_a == 400,
           f"got {stock_a}")

    stock_b = get_stock("Test Ingredient B")
    result("1.1c Ingredient B stock = 240",
           stock_b == 240,
           f"got {stock_b}")

    hm_flag = get_housemade_flag("Test Mix")
    result("1.1d 'Test Mix' exists in raw_materials with is_housemade=True",
           hm_flag is True,
           f"is_housemade={hm_flag}")

    mix_stock = get_stock("Test Mix")
    result("1.1e 'Test Mix' stock_level = 2",
           mix_stock == 2,
           f"got {mix_stock}")

except Exception as e:
    result("1.1 — unexpected exception", False, str(e))


# Test 1.2
print("\n--- Test 1.2 — Second mix batch (qty=3), stock accumulates ---")
try:
    b2_id = add_to_batches("Test Mix", 3, batch_type='mix')
    mix_stock = get_stock("Test Mix")
    result("1.2 'Test Mix' stock_level = 5 (2+3)",
           mix_stock == 5,
           f"got {mix_stock}")
except Exception as e:
    result("1.2 — unexpected exception", False, str(e))


# Test 1.3
print("\n--- Test 1.3 — Insufficient ingredient for mix ---")
set_stock("Test Ingredient A", 10)
pre_mix_stock = get_stock("Test Mix")
raised_error = False
try:
    add_to_batches("Test Mix", 10, batch_type='mix')
    result("1.3a ValueError raised", False, "no exception raised")
except ValueError as e:
    raised_error = True
    result("1.3a ValueError raised with clear message",
           len(str(e)) > 10,
           str(e))
except Exception as e:
    result("1.3a ValueError raised", False, f"got {type(e).__name__}: {e}")

if raised_error:
    stock_a_after = get_stock("Test Ingredient A")
    result("1.3b Ingredient A stock still = 10 (rollback)",
           stock_a_after == 10,
           f"got {stock_a_after}")

    mix_stock_after = get_stock("Test Mix")
    result("1.3c 'Test Mix' stock_level unchanged",
           mix_stock_after == pre_mix_stock,
           f"before={pre_mix_stock}, after={mix_stock_after}")

    # verify no spurious batch was inserted
    row = raw_cursor_fetchone(
        "SELECT COUNT(*) FROM batches WHERE product_name='Test Mix' AND quantity=10"
    )
    spurious = row[0]
    result("1.3d No batch row created",
           spurious == 0,
           f"found {spurious} rows")


# ── BLOCK 2 ────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("BLOCK 2 — Finished Batch (stage 2, planned)")
print("="*60)

mix_stock_check = get_stock("Test Mix")
print(f"  'Test Mix' stock going into Block 2: {mix_stock_check} (should be 5)")

recipe_fp_id = add_recipe("Test Finished Product", [
    {"material_name": "Test Mix", "quantity_needed": 2},
])
print(f"  Added recipe 'Test Finished Product' (id={recipe_fp_id})")


# Test 2.1
print("\n--- Test 2.1 — Create planned finished batch (future date) ---")
b3_id = None
try:
    b3_id = add_to_batches("Test Finished Product", 1,
                            batch_type='finished',
                            planned_completion_date='2099-12-31')

    batch_row = get_batch_row(b3_id)
    result("2.1a status = 'Planned'",
           batch_row is not None and batch_row[3] == 'Planned',
           f"status={batch_row[3] if batch_row else None}")

    mix_stock = get_stock("Test Mix")
    result("2.1b 'Test Mix' stock_level still = 5 (not deducted yet)",
           mix_stock == 5,
           f"got {mix_stock}")

except Exception as e:
    result("2.1 — unexpected exception", False, str(e))


# Test 2.2
print("\n--- Test 2.2 — Promote overdue finished batch with sufficient stock ---")
if b3_id is not None:
    force_batch_date(b3_id, YESTERDAY)
    try:
        promote_planned_batches()

        batch_row = get_batch_row(b3_id)
        result("2.2a status = 'Ready'",
               batch_row is not None and batch_row[3] == 'Ready',
               f"status={batch_row[3] if batch_row else None}")

        mix_stock = get_stock("Test Mix")
        result("2.2b 'Test Mix' stock_level = 3 (deducted 2)",
               mix_stock == 3,
               f"got {mix_stock}")

        bm_rows = get_batch_materials_rows(b3_id)
        result("2.2c batch_materials row exists",
               len(bm_rows) > 0,
               f"found {len(bm_rows)} rows")

        failure_reason = batch_row[5] if batch_row else "N/A"
        result("2.2d promotion_failure_reason = NULL",
               failure_reason is None,
               f"got: {failure_reason}")

    except Exception as e:
        result("2.2 — unexpected exception", False, str(e))
else:
    result("2.2 skipped — b3_id not set", False, "depends on 2.1")


# Test 2.3
print("\n--- Test 2.3 — Promote overdue finished batch with INSUFFICIENT stock ---")
b4_id = None
try:
    b4_id = add_to_batches("Test Finished Product", 5,   # 5 * 2 = 10 needed, only 3 available
                            batch_type='finished',
                            planned_completion_date='2099-12-31')
    force_batch_date(b4_id, YESTERDAY)
    mix_stock_before = get_stock("Test Mix")

    promote_planned_batches()

    batch_row = get_batch_row(b4_id)
    result("2.3a status still = 'Planned'",
           batch_row is not None and batch_row[3] == 'Planned',
           f"status={batch_row[3] if batch_row else None}")

    mix_stock_after = get_stock("Test Mix")
    result("2.3b 'Test Mix' stock_level still = 3 (nothing deducted)",
           mix_stock_after == mix_stock_before,
           f"before={mix_stock_before}, after={mix_stock_after}")

    failure_reason = batch_row[5] if batch_row else None
    result("2.3c promotion_failure_reason contains human-readable message",
           failure_reason is not None and len(failure_reason) > 5,
           f"got: {failure_reason}")

except Exception as e:
    result("2.3 — unexpected exception", False, str(e))


# ── BLOCK 3 ────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("BLOCK 3 — Cross-reference accuracy")
print("="*60)

# Test 3.1
print("\n--- Test 3.1 — Batch history completeness ---")
mix_count    = raw_cursor_fetchone("SELECT COUNT(*) FROM batches WHERE batch_type='mix'")[0]
finished_count = raw_cursor_fetchone("SELECT COUNT(*) FROM batches WHERE batch_type='finished'")[0]
print(f"  mix batches:      {mix_count}")
print(f"  finished batches: {finished_count}")
result("3.1 batch counts printed (informational)", True)


# Test 3.2
print("\n--- Test 3.2 — Stock math audit ---")
rows_32 = raw_cursor_fetchall("""
    SELECT rm.name, rm.stock_level,
           COALESCE(SUM(bm.quantity_used), 0) AS total_used
    FROM raw_materials rm
    LEFT JOIN batch_materials bm ON rm.material_id = bm.material_id
    GROUP BY rm.material_id, rm.name, rm.stock_level
""")
print(f"  {'Name':<35} {'stock_level':>12} {'total_used':>12}  flag")
any_negative = False
for name, stock, used in rows_32:
    flag = " <<< NEGATIVE" if stock < 0 else ""
    if stock < 0:
        any_negative = True
    print(f"  {name:<35} {float(stock):>12.2f} {float(used):>12.2f}{flag}")
result("3.2 no negative stock_levels", not any_negative,
       "one or more materials have stock_level < 0")


# Test 3.3
print("\n--- Test 3.3 — Orphaned batch_materials ---")
orphans = raw_cursor_fetchall("""
    SELECT bm.batch_id FROM batch_materials bm
    LEFT JOIN batches b ON bm.batch_id = b.batch_id
    WHERE b.batch_id IS NULL
""")
result("3.3 no orphaned batch_materials rows",
       len(orphans) == 0,
       f"found {len(orphans)} orphaned rows: {orphans}")


# ── CLEANUP ────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("CLEANUP")
print("="*60)

cleanup_test_data()

mat_count   = raw_cursor_fetchone("SELECT COUNT(*) FROM raw_materials")[0]
batch_count = raw_cursor_fetchone("SELECT COUNT(*) FROM batches")[0]
print(f"  Test data removed.")
print(f"\n  Final DB state — materials: {mat_count} | batches: {batch_count}")


# ── SUMMARY ────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
total = passed + failed + warnings
print(f"  PASSED:   {passed} / {total}")
print(f"  FAILED:   {failed} / {total}")
print(f"  WARNINGS: {warnings} / {total}")

if failures_for_demo:
    print("\n  MUST FIX BEFORE DEMO:")
    for f in failures_for_demo:
        print(f"    - {f}")
else:
    print("\n  All tests passed — nothing to fix before demo.")
