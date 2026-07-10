"""
One-off repair for the planned-batch double-promotion bug.

THE BUG (fixed in services/batches.py by _claim_batch): promote_planned_batches read the overdue
batches with an unprotected SELECT and then deducted, flipping status with an unconditional UPDATE.
Two concurrent promotes could both act on the same batch, so a promoted batch could end up with:

  1. duplicate `batch_materials` rows        -> its lots were deducted twice (stock too low)
  2. duplicate `MIX-BATCH-<batch_number>` lots -> phantom house-made stock (stock too high)

This script finds and repairs both. It is idempotent: running it twice changes nothing the second
time. It goes through database.get_db_connection(), so it repairs SQLite or PostgreSQL unchanged —
set DATABASE_URL to point it at production.

Usage:
    python scripts/repair_double_promotion.py              # dry run: report only, no writes
    python scripts/repair_double_promotion.py --apply      # perform the repair

Back up the database before running with --apply.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection
from services.lots import LOT_EXHAUST_THRESHOLD


def find_duplicate_materials(db, cursor):
    """
    Groups of identical batch_materials rows: same batch, material, lot AND quantity.

    A batch can never legitimately consume the same lot for the same material across two rows —
    the lot picker rejects a duplicate lot within a material, and both the create and promote paths
    write exactly one row per (material, lot). So an exact-duplicate group is always this bug.
    Requiring quantity_used to match too keeps a hand-adjusted row from being mistaken for a dupe.
    """
    db.execute(cursor, """
        SELECT batch_id, material_id, lot_id, quantity_used, COUNT(*), MIN(batch_material_id)
        FROM batch_materials
        GROUP BY batch_id, material_id, lot_id, quantity_used
        HAVING COUNT(*) > 1
        ORDER BY batch_id, material_id
    """)
    return cursor.fetchall()


def find_duplicate_mix_lots(db, cursor):
    """
    House-made output lots sharing a lot_number. _create_housemade_lot writes exactly one
    MIX-BATCH-<batch_number> lot per mix batch, so more than one is always a duplicate promotion.
    """
    # The pattern is a bound parameter, not inlined: db.execute rewrites %s -> ? for SQLite, so a
    # literal '%' in the SQL would have to be escaped differently per backend.
    db.execute(cursor, """
        SELECT lot_number, COUNT(*)
        FROM raw_material_lots
        WHERE lot_number LIKE %s
        GROUP BY lot_number
        HAVING COUNT(*) > 1
        ORDER BY lot_number
    """, ('MIX-BATCH-%',))
    return cursor.fetchall()


def repair_duplicate_materials(db, cursor, groups, apply_changes):
    """Delete the surplus rows and give each over-deducted lot its quantity back."""
    for batch_id, material_id, lot_id, quantity_used, count, keep_id in groups:
        surplus = count - 1
        restore = float(quantity_used) * surplus

        db.execute(cursor, "SELECT quantity, status FROM raw_material_lots WHERE lot_id = %s", (lot_id,))
        lot = cursor.fetchone()
        if not lot:
            print(f"  ! batch {batch_id}: lot {lot_id} no longer exists — deleting {surplus} "
                  f"duplicate row(s), cannot restore {restore}")
            current_qty, status = None, None
        else:
            current_qty, status = float(lot[0]), lot[1]
            new_qty = current_qty + restore
            print(f"  batch {batch_id}, material {material_id}, lot {lot_id}: "
                  f"drop {surplus} duplicate row(s), lot {current_qty} -> {new_qty}"
                  + ("  [reactivate]" if status != 'active' and new_qty >= LOT_EXHAUST_THRESHOLD else ""))

        if not apply_changes:
            continue

        db.execute(cursor, """
            DELETE FROM batch_materials
            WHERE batch_id = %s AND material_id = %s AND lot_id = %s AND quantity_used = %s
              AND batch_material_id <> %s
        """, (batch_id, material_id, lot_id, quantity_used, keep_id))

        if current_qty is None:
            continue

        # The over-deduction may have driven the lot to 0/inactive via exhaust_lot_if_depleted.
        # Restoring the quantity must restore its usability too, or the stock stays invisible.
        new_qty = current_qty + restore
        if status != 'active' and new_qty >= LOT_EXHAUST_THRESHOLD:
            db.execute(cursor, "UPDATE raw_material_lots SET quantity = %s, status = 'active' WHERE lot_id = %s",
                       (new_qty, lot_id))
        else:
            db.execute(cursor, "UPDATE raw_material_lots SET quantity = %s WHERE lot_id = %s",
                       (new_qty, lot_id))


def repair_duplicate_mix_lots(db, cursor, dupes, apply_changes):
    """
    Keep the lot the batch actually points at (batches.mix_lot_id); delete the phantom copies.

    A phantom that something has already consumed is NOT deleted — removing it would orphan a real
    batch_materials row and silently destroy that consumption record. Those are reported instead.
    """
    for lot_number, count in dupes:
        batch_number = lot_number[len("MIX-BATCH-"):]
        db.execute(cursor, "SELECT mix_lot_id FROM batches WHERE batch_number = %s", (batch_number,))
        row = cursor.fetchone()
        keeper = row[0] if row else None

        db.execute(cursor, "SELECT lot_id, quantity FROM raw_material_lots WHERE lot_number = %s ORDER BY lot_id",
                   (lot_number,))
        lots = cursor.fetchall()

        if keeper is None:
            keeper = lots[0][0]  # batch is gone or never recorded one — keep the oldest
            print(f"  {lot_number}: no mix_lot_id on the batch; keeping oldest lot {keeper}")

        for lot_id, quantity in lots:
            if lot_id == keeper:
                continue
            db.execute(cursor, "SELECT COUNT(*) FROM batch_materials WHERE lot_id = %s", (lot_id,))
            used = cursor.fetchone()[0]
            if used:
                print(f"  ! {lot_number}: phantom lot {lot_id} has been CONSUMED by {used} batch "
                      f"material row(s) — left in place, review by hand")
                continue
            print(f"  {lot_number}: delete phantom lot {lot_id} (qty {quantity}), keeping {keeper}")
            if apply_changes:
                db.execute(cursor, "DELETE FROM raw_material_lots WHERE lot_id = %s", (lot_id,))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="perform the repair (default is a dry run that only reports)")
    args = parser.parse_args()

    target = "PostgreSQL" if os.getenv("DATABASE_URL") else f"SQLite ({os.getenv('SQLITE_PATH', 'data/inventory.db')})"
    mode = "APPLY" if args.apply else "DRY RUN — no changes will be written"
    print(f"Target: {target}\nMode:   {mode}\n")

    db = get_db_connection()
    cursor = db.cursor()
    try:
        groups = find_duplicate_materials(db, cursor)
        print(f"Duplicate batch_materials groups: {len(groups)}")
        if groups:
            repair_duplicate_materials(db, cursor, groups, args.apply)

        dupes = find_duplicate_mix_lots(db, cursor)
        print(f"\nDuplicate MIX-BATCH lot numbers: {len(dupes)}")
        if dupes:
            repair_duplicate_mix_lots(db, cursor, dupes, args.apply)

        if args.apply:
            db.commit()
            print("\nRepair committed.")
        else:
            db.rollback()
            print("\nDry run complete. Re-run with --apply to write these changes.")

        if not groups and not dupes:
            print("\nNothing to repair.")

    except Exception as e:
        db.rollback()
        print(f"\nFAILED, rolled back: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
