"""
Standalone verification for partial-batch shipments (the shipment_batches junction model).

Runs directly against the local SQLite DB — no server needed. Creates its own Test* rows and
cleans them up at the end. Drives the services layer (not the stale inventory_app the other
test_scripts import). Prints a PASS/FAIL summary and exits non-zero on any failure.

Run: python test_scripts/test_partial_shipments.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.setup import create_database
from services.shipments import (
    create_shipment, get_shipment_by_id, get_all_shipments,
    update_shipment, delete_shipment, _batch_remaining,
)
from database import get_db_connection

_results = []


def check(label, ok, extra=""):
    _results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + extra) if extra else ''}")


def _make_batch(name, qty):
    db = get_db_connection()
    cur = db.cursor()
    db.execute(cur, """
        INSERT INTO batches (product_name, quantity, status, batch_number, batch_type)
        VALUES (%s, %s, 'Ready', %s, 'standard')
    """, (name, qty, name))
    bid = db.get_last_insert_id(cur)
    db.commit()
    db.close()
    return bid


def _status(batch_id):
    db = get_db_connection()
    cur = db.cursor()
    db.execute(cur, "SELECT status FROM batches WHERE batch_id = %s", (batch_id,))
    row = cur.fetchone()
    db.close()
    return row[0] if row else None


def _remaining(batch_id):
    db = get_db_connection()
    cur = db.cursor()
    rem = _batch_remaining(cur, db, batch_id)
    db.close()
    return rem


def main():
    create_database()  # ensure shipment_batches exists locally

    created_shipments = []
    a = _make_batch("TestPartialA", 100)
    b = _make_batch("TestPartialB", 50)
    try:
        # 1. Partial allocation: ship 30 of A -> Partially Shipped, remaining 70.
        s1 = create_shipment({a: 30}, destination="TestDest1")
        created_shipments.append(s1)
        check("partial allocation deducts remaining", _remaining(a) == 70, f"remaining={_remaining(a)}")
        check("partial allocation sets 'Partially Shipped'", _status(a) == "Partially Shipped", _status(a))

        # 2. Split across a second shipment + combine with B in one shipment.
        s2 = create_shipment({a: 70, b: 20}, destination="TestDest2")
        created_shipments.append(s2)
        check("A fully allocated across two shipments -> 'Shipped'", _status(a) == "Shipped", _status(a))
        check("A remaining is 0", abs(_remaining(a)) < 1e-9, f"remaining={_remaining(a)}")
        check("B partially shipped via multi-batch shipment", _status(b) == "Partially Shipped", _status(b))
        check("B remaining is 30", _remaining(b) == 30, f"remaining={_remaining(b)}")

        # 3. Over-allocation is rejected.
        over_ok = False
        try:
            create_shipment({b: 9999})
        except ValueError:
            over_ok = True
        check("over-allocation raises ValueError", over_ok)

        # 4. get_shipment_by_id returns per-line shipped quantity + batch total.
        detail = get_shipment_by_id(s2)
        line_a = next((x for x in detail['batches'] if x['batch_id'] == a), None)
        check("shipment detail carries per-line shipped qty", line_a and line_a['quantity'] == 70,
              str(line_a['quantity']) if line_a else "missing")
        check("shipment detail carries batch produced total", line_a and line_a['batch_quantity'] == 100,
              str(line_a['batch_quantity']) if line_a else "missing")

        # 5. Editing lines: drop A from s2, raise B's line to 40 (B remaining excl. s2 was 30, +current 20 = 50 cap).
        update_shipment(s2, lines={b: 40})
        d2 = get_shipment_by_id(s2)
        has_a = any(x['batch_id'] == a for x in d2['batches'])
        line_b = next((x for x in d2['batches'] if x['batch_id'] == b), None)
        check("edit removed A from shipment", not has_a)
        check("edit adjusted B line to 40", line_b and line_b['quantity'] == 40, str(line_b['quantity']) if line_b else "missing")
        # A still has its 30 on s1, so removing it from s2 leaves it Partially Shipped with remaining 70.
        check("removing A's s2 line leaves A 'Partially Shipped' (still on s1)", _status(a) == "Partially Shipped", _status(a))
        check("A remaining is 70 (30 still on s1)", _remaining(a) == 70, f"remaining={_remaining(a)}")
        check("B remaining now 10 (50 - 40)", _remaining(b) == 10, f"remaining={_remaining(b)}")

        # 6. Edit over-allocation is rejected (B cap is 50).
        edit_over_ok = False
        try:
            update_shipment(s2, lines={b: 60})
        except ValueError:
            edit_over_ok = True
        check("edit over-allocation raises ValueError", edit_over_ok)

        # 7. Delete recomputes remaining/status.
        delete_shipment(s2)
        created_shipments.remove(s2)
        check("delete returns B to 'Ready'", _status(b) == "Ready", _status(b))
        check("delete restores B remaining to 50", _remaining(b) == 50, f"remaining={_remaining(b)}")

        # 8. get_all_shipments counts lines from the junction.
        df, _ = get_all_shipments(page=None)
        check("get_all_shipments returns rows", not df.empty)

    finally:
        # Cleanup — remove all Test* shipments, their junction rows, and the test batches.
        db = get_db_connection()
        cur = db.cursor()
        for sid in created_shipments:
            db.execute(cur, "DELETE FROM shipment_batches WHERE shipment_id = %s", (sid,))
            db.execute(cur, "DELETE FROM shipments WHERE shipment_id = %s", (sid,))
        for bid in (a, b):
            db.execute(cur, "DELETE FROM shipment_batches WHERE batch_id = %s", (bid,))
            db.execute(cur, "DELETE FROM batches WHERE batch_id = %s", (bid,))
        # also clear any stray TestDest shipments created during over-allocation attempts
        db.commit()
        db.close()

    passed = sum(1 for r in _results if r)
    print(f"\n{passed}/{len(_results)} checks passed")
    sys.exit(0 if passed == len(_results) else 1)


if __name__ == "__main__":
    main()
