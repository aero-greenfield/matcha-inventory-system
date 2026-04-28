import os
import sys
import sqlite3
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database

# Force SQLite mode before inventory_app is imported so DatabaseConnection.is_postgres = False
database.DATABASE_URL = None

import inventory_app as inv

TEST_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'test_inventory.db'
)


def _create_test_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS raw_materials (
            material_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL UNIQUE,
            category      TEXT,
            stock_level   REAL,
            unit          TEXT,
            reorder_level REAL,
            cost_per_unit REAL,
            supplier      TEXT,
            is_housemade  BOOLEAN DEFAULT FALSE
        );
        CREATE TABLE IF NOT EXISTS raw_material_lots (
            lot_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id     INTEGER,
            lot_number      TEXT,
            quantity        REAL,
            received_date   TEXT,
            expiration_date TEXT,
            status          TEXT DEFAULT 'active',
            supplier        TEXT,
            location        TEXT,
            cost_per_unit   REAL,
            FOREIGN KEY (material_id) REFERENCES raw_materials(material_id)
        );
        CREATE TABLE IF NOT EXISTS recipes (
            recipe_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            notes        TEXT
        );
        CREATE TABLE IF NOT EXISTS recipe_materials (
            recipe_material_id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id          INTEGER,
            material_id        INTEGER,
            material_name      TEXT,
            quantity_needed    REAL,
            FOREIGN KEY (recipe_id)   REFERENCES recipes(recipe_id),
            FOREIGN KEY (material_id) REFERENCES raw_materials(material_id)
        );
        CREATE TABLE IF NOT EXISTS batches (
            batch_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name             TEXT NOT NULL,
            quantity                 INTEGER,
            date_completed           TEXT,
            status                   TEXT DEFAULT 'Ready',
            notes                    TEXT,
            batch_number             TEXT,
            date_shipped             TEXT,
            expiration_date          TEXT,
            planned_completion_date  TEXT,
            batch_type               TEXT DEFAULT 'standard',
            planned_lot_selections   TEXT,
            promotion_failure_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS batch_materials (
            batch_material_id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id          INTEGER,
            material_id       INTEGER,
            lot_id            INTEGER,
            quantity_used     REAL,
            cost_per_unit     REAL,
            FOREIGN KEY (batch_id)    REFERENCES batches(batch_id),
            FOREIGN KEY (material_id) REFERENCES raw_materials(material_id),
            FOREIGN KEY (lot_id)      REFERENCES raw_material_lots(lot_id)
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            action    TEXT NOT NULL,
            details   TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()


def _batch_status(batch_id):
    """Read batch status + failure_reason directly from the test DB, bypassing promote auto-trigger."""
    conn = sqlite3.connect(TEST_DB_PATH)
    row = conn.execute(
        "SELECT status, promotion_failure_reason FROM batches WHERE batch_id = ?", (batch_id,)
    ).fetchone()
    conn.close()
    return row  # (status, failure_reason)


# ============================================================
# Shared base: fresh isolated SQLite DB for every test method
# ============================================================

class _InventoryTestBase(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        init_conn = sqlite3.connect(TEST_DB_PATH)
        _create_test_schema(init_conn)
        init_conn.close()

        def mock_get_db():
            return database.DatabaseConnection(sqlite3.connect(TEST_DB_PATH))

        # inventory_app does "from database import get_db_connection", so patch the local name
        self._patcher = patch('inventory_app.get_db_connection', side_effect=mock_get_db)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def _setup_material_and_recipe(self, material_name='Matcha', qty_per_batch=100.0):
        mat_id = inv.add_raw_material(material_name, 'Tea', 0, 'g', 0)
        inv.add_recipe(
            'Test Product',
            [{'material_name': material_name, 'quantity_needed': qty_per_batch}]
        )
        return mat_id


# ============================================================
# Suite 1 — add_to_batches lot-selection validation
# ============================================================

class LotSelectionTests(_InventoryTestBase):

    # ------------------------------------------------------------------ #
    # Test 1: valid lot selection — batch created, quantity deducted
    # ------------------------------------------------------------------ #
    def test_valid_lot_selection(self):
        mat_id = self._setup_material_and_recipe()          # recipe: 100 g
        lot_id = inv.receive_lot(mat_id, 'LOT-001', 200, '2026-01-01')

        batch_id = inv.add_to_batches(
            'Test Product', 1,
            lot_selections={mat_id: [{'lot_id': lot_id, 'qty': 100}]}
        )

        self.assertIsNotNone(batch_id, "Batch should be created")
        lots = inv.get_all_lots_for_material(mat_id)
        remaining = lots.loc[lots['lot_id'] == lot_id, 'quantity'].values[0]
        self.assertAlmostEqual(remaining, 100.0, msg="Lot should have 100 g remaining after 100 g deducted")

    # ------------------------------------------------------------------ #
    # Test 2: over-allocation — sum of selected qty > required
    # ------------------------------------------------------------------ #
    def test_over_allocation_raises(self):
        mat_id = self._setup_material_and_recipe()          # recipe: 100 g
        lot_id = inv.receive_lot(mat_id, 'LOT-001', 200, '2026-01-01')

        with self.assertRaises(ValueError, msg="Over-allocation should raise ValueError"):
            inv.add_to_batches(
                'Test Product', 1,
                lot_selections={mat_id: [{'lot_id': lot_id, 'qty': 150}]}  # 150 > 100
            )

    # ------------------------------------------------------------------ #
    # Test 3: under-allocation — sum of selected qty < required
    # ------------------------------------------------------------------ #
    def test_under_allocation_raises(self):
        mat_id = self._setup_material_and_recipe()          # recipe: 100 g
        lot_id = inv.receive_lot(mat_id, 'LOT-001', 200, '2026-01-01')

        with self.assertRaises(ValueError, msg="Under-allocation should raise ValueError"):
            inv.add_to_batches(
                'Test Product', 1,
                lot_selections={mat_id: [{'lot_id': lot_id, 'qty': 50}]}   # 50 < 100
            )

    # ------------------------------------------------------------------ #
    # Test 4: expired lot rejection — lot past its expiry date is rejected
    # ------------------------------------------------------------------ #
    def test_expired_lot_rejection(self):
        mat_id = self._setup_material_and_recipe()
        expired_lot_id = inv.receive_lot(
            mat_id, 'LOT-EXP', 200, '2025-01-01',
            expiry_date='2026-04-27 00:00:00'   # one day before today (2026-04-28)
        )

        with self.assertRaises(ValueError, msg="Expired lot should be rejected"):
            inv.add_to_batches(
                'Test Product', 1,
                lot_selections={mat_id: [{'lot_id': expired_lot_id, 'qty': 100}]}
            )

    # ------------------------------------------------------------------ #
    # Test 5: split-lot deduction — material sourced from two lots
    # ------------------------------------------------------------------ #
    def test_split_lot_deduction(self):
        mat_id = self._setup_material_and_recipe()          # recipe: 100 g
        lot_id_a = inv.receive_lot(mat_id, 'LOT-A', 60, '2026-01-01')
        lot_id_b = inv.receive_lot(mat_id, 'LOT-B', 80, '2026-01-02')

        batch_id = inv.add_to_batches(
            'Test Product', 1,
            lot_selections={mat_id: [
                {'lot_id': lot_id_a, 'qty': 60},   # drains LOT-A completely
                {'lot_id': lot_id_b, 'qty': 40},   # partial draw from LOT-B
            ]}
        )

        self.assertIsNotNone(batch_id, "Batch should be created from split lots")
        lots = inv.get_all_lots_for_material(mat_id)
        qty_a = lots.loc[lots['lot_id'] == lot_id_a, 'quantity'].values[0]
        qty_b = lots.loc[lots['lot_id'] == lot_id_b, 'quantity'].values[0]
        self.assertAlmostEqual(qty_a, 0.0,  msg="LOT-A should be fully drained")
        self.assertAlmostEqual(qty_b, 40.0, msg="LOT-B should have 40 g remaining")


# ============================================================
# Suite 2 — promote_planned_batches
# ============================================================

class PromotePlannedTests(_InventoryTestBase):

    PAST_DATE   = '2026-01-01'  # definitely <= today (2026-04-28)
    FUTURE_DATE = '2026-12-31'  # definitely > today

    # ------------------------------------------------------------------ #
    # Test 6: standard planned batch — flips to Ready on promote
    #   standard batches deduct lots immediately at creation; promote only
    #   changes the status field.
    # ------------------------------------------------------------------ #
    def test_standard_batch_promotes_to_ready(self):
        mat_id = self._setup_material_and_recipe()
        lot_id = inv.receive_lot(mat_id, 'LOT-001', 200, '2026-01-01')

        batch_id = inv.add_to_batches(
            'Test Product', 1,
            batch_type='standard',
            planned_completion_date=self.PAST_DATE,
            lot_selections={mat_id: [{'lot_id': lot_id, 'qty': 100}]}
        )
        self.assertIsNotNone(batch_id)
        self.assertEqual(_batch_status(batch_id)[0], 'Planned', "Should start as Planned")

        inv.promote_planned_batches()

        status, failure = _batch_status(batch_id)
        self.assertEqual(status, 'Ready', "Standard batch should be promoted to Ready")
        self.assertIsNone(failure, "No failure reason expected")

    # ------------------------------------------------------------------ #
    # Test 7: finished planned batch with stored lot selections
    #   Lots are NOT deducted at creation (defer_deduction=True).
    #   promote_planned_batches uses the stored JSON to deduct the exact lots.
    # ------------------------------------------------------------------ #
    def test_finished_batch_promotes_with_stored_lots(self):
        mat_id = self._setup_material_and_recipe()
        lot_id = inv.receive_lot(mat_id, 'LOT-001', 200, '2026-01-01')

        batch_id = inv.add_to_batches(
            'Test Product', 1,
            batch_type='finished',
            planned_completion_date=self.PAST_DATE,
            lot_selections={mat_id: [{'lot_id': lot_id, 'qty': 100}]}
        )
        self.assertIsNotNone(batch_id)

        # Lot should NOT be deducted yet (deduction deferred)
        lots = inv.get_all_lots_for_material(mat_id)
        self.assertAlmostEqual(
            lots.loc[lots['lot_id'] == lot_id, 'quantity'].values[0], 200.0,
            msg="Lot should be untouched before promotion"
        )

        inv.promote_planned_batches()

        status, failure = _batch_status(batch_id)
        self.assertEqual(status, 'Ready', "Finished batch should be promoted to Ready")
        self.assertIsNone(failure)

        lots = inv.get_all_lots_for_material(mat_id)
        self.assertAlmostEqual(
            lots.loc[lots['lot_id'] == lot_id, 'quantity'].values[0], 100.0,
            msg="100 g should be deducted from the lot at promotion time"
        )

    # ------------------------------------------------------------------ #
    # Test 8: finished planned batch with no stored lots → FIFO fallback
    #   promote_planned_batches auto-selects oldest active lots first.
    # ------------------------------------------------------------------ #
    def test_finished_batch_promotes_fifo(self):
        mat_id = self._setup_material_and_recipe()          # recipe: 100 g
        lot_id_a = inv.receive_lot(mat_id, 'LOT-A', 80, '2026-01-01')  # older
        lot_id_b = inv.receive_lot(mat_id, 'LOT-B', 80, '2026-01-02')  # newer

        # No lot_selections → planned_lot_selections stored as NULL
        batch_id = inv.add_to_batches(
            'Test Product', 1,
            batch_type='finished',
            planned_completion_date=self.PAST_DATE,
        )
        self.assertIsNotNone(batch_id)

        inv.promote_planned_batches()

        status, failure = _batch_status(batch_id)
        self.assertEqual(status, 'Ready', "Finished batch should be promoted via FIFO")
        self.assertIsNone(failure)

        lots = inv.get_all_lots_for_material(mat_id)
        qty_a = lots.loc[lots['lot_id'] == lot_id_a, 'quantity'].values[0]
        qty_b = lots.loc[lots['lot_id'] == lot_id_b, 'quantity'].values[0]
        # FIFO: fully drain older LOT-A (80 g) then take 20 g from LOT-B
        self.assertAlmostEqual(qty_a, 0.0,  msg="Older LOT-A should be fully drained by FIFO")
        self.assertAlmostEqual(qty_b, 60.0, msg="LOT-B should have 60 g remaining (only 20 g taken)")

    # ------------------------------------------------------------------ #
    # Test 9: finished batch fails promotion — insufficient stock
    #   When lots can't cover the required amount, the batch stays Planned
    #   and promotion_failure_reason is populated.
    # ------------------------------------------------------------------ #
    def test_finished_batch_fails_insufficient_stock(self):
        mat_id = self._setup_material_and_recipe()          # recipe: 100 g
        inv.receive_lot(mat_id, 'LOT-001', 50, '2026-01-01')  # only 50 g available

        batch_id = inv.add_to_batches(
            'Test Product', 1,
            batch_type='finished',
            planned_completion_date=self.PAST_DATE,
        )
        self.assertIsNotNone(batch_id)

        inv.promote_planned_batches()

        status, failure = _batch_status(batch_id)
        self.assertEqual(status, 'Planned', "Batch should remain Planned when stock is insufficient")
        self.assertIsNotNone(failure, "failure_reason should be set")
        self.assertIn('Insufficient', failure, "failure_reason should mention insufficient stock")

    # ------------------------------------------------------------------ #
    # Test 10: batch not yet due — promote ignores future dates
    # ------------------------------------------------------------------ #
    def test_not_yet_due_batch_stays_planned(self):
        mat_id = self._setup_material_and_recipe()
        lot_id = inv.receive_lot(mat_id, 'LOT-001', 200, '2026-01-01')

        batch_id = inv.add_to_batches(
            'Test Product', 1,
            batch_type='standard',
            planned_completion_date=self.FUTURE_DATE,
            lot_selections={mat_id: [{'lot_id': lot_id, 'qty': 100}]}
        )
        self.assertIsNotNone(batch_id)

        inv.promote_planned_batches()

        status, _ = _batch_status(batch_id)
        self.assertEqual(status, 'Planned', "Future-dated batch should not be promoted yet")


if __name__ == '__main__':
    unittest.main(verbosity=2)
