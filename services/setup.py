# ADDED: create_database() was in inventory_app.py but has nothing to do with
#        runtime inventory logic — it's a one-time SQLite schema initializer used
#        only in local dev. Moved here so the domain service files stay clean.


# NOTE: This function only for local SQLite - use init_db.py for PostgreSQL
def create_database():
    """Creates database with raw_materials, recipes, and ready_to_ship tables"""
    import sqlite3
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()

    #Raw Materials

    #edits for lot number: deleted cost_per, quantity (will be gotten from SUM lot number)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_materials(
                   material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL UNIQUE,
                   category TEXT,
                   unit TEXT,
                   reorder_level REAL,
                   is_housemade BOOLEAN DEFAULT FALSE,
                   is_edible BOOLEAN DEFAULT TRUE,
                   is_organic BOOLEAN DEFAULT FALSE

                   )
                   """)

    # ADDED: organic feature — additive migration for pre-existing local SQLite DBs.
    #        The CREATE TABLE above only fires for brand-new DBs (IF NOT EXISTS), so existing
    #        installs need the new columns backfilled. SQLite has no ADD COLUMN IF NOT EXISTS,
    #        so we check PRAGMA table_info first and only ALTER when the column is missing.
    cursor.execute("PRAGMA table_info(raw_materials)")
    _rm_cols = {row[1] for row in cursor.fetchall()}
    if "is_edible" not in _rm_cols:
        cursor.execute("ALTER TABLE raw_materials ADD COLUMN is_edible BOOLEAN DEFAULT TRUE")
    if "is_organic" not in _rm_cols:
        cursor.execute("ALTER TABLE raw_materials ADD COLUMN is_organic BOOLEAN DEFAULT FALSE")

    # Shipments migration — add shipment_id FK to existing batches tables.
    cursor.execute("PRAGMA table_info(batches)")
    _b_cols = {row[1] for row in cursor.fetchall()}
    if "shipment_id" not in _b_cols:
        cursor.execute("ALTER TABLE batches ADD COLUMN shipment_id INTEGER DEFAULT NULL REFERENCES shipments(shipment_id)")

    #raw material lots.

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_material_lots(
                   lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   material_id INTEGER,
                   lot_number TEXT,
                   quantity REAL,
                   received_date TEXT,
                   expiration_date TEXT,
                   status TEXT DEFAULT 'active',
                   supplier TEXT,
                   location TEXT,
                   cost_per_unit REAL,
                   FOREIGN KEY (material_id) REFERENCES raw_materials(material_id)
                   )
                   """)


    #Recipes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recipes(
                   recipe_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   product_name TEXT NOT NULL,
                   notes TEXT


                   )
                   """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recipe_materials(
                   recipe_material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   recipe_id INTEGER,
                   material_id INTEGER,
                   material_name TEXT,
                   quantity_needed REAL,
                   FOREIGN KEY (material_id) REFERENCES raw_materials(material_id),
                   FOREIGN KEY (recipe_id) REFERENCES recipes(recipe_id)

                   )
                   """)

    # Shipments (must come before batches FK reference)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shipments(
                    shipment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                    shipment_number TEXT NOT NULL UNIQUE,
                    date_shipped    TEXT NOT NULL,
                    destination     TEXT,
                    notes           TEXT
                   )
                   """)

    # Ready to ship
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batches(
                    batch_id INTEGER PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    quantity INTEGER,
                    date_completed TEXT,
                    status TEXT DEFAULT 'Ready',
                    notes TEXT,
                    batch_number TEXT,
                    date_shipped TEXT,
                    expiration_date TEXT,
                    planned_completion_date TEXT,
                    batch_type TEXT DEFAULT 'standard',
                    planned_lot_selections TEXT,
                    promotion_failure_reason TEXT,
                    mix_lot_id INTEGER DEFAULT NULL REFERENCES raw_material_lots(lot_id),
                    shipment_id INTEGER DEFAULT NULL REFERENCES shipments(shipment_id)



                   )
                   """)


    #Batch_materials
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batch_materials(
                   batch_material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   batch_id INTEGER,
                   material_id INTEGER,
                   lot_id INTEGER,
                   quantity_used REAL,
                   cost_per_unit REAL, 
                   FOREIGN KEY (material_id) REFERENCES raw_materials(material_id),
                   FOREIGN KEY (batch_id) REFERENCES batches(batch_id),
                   FOREIGN KEY(lot_id) REFERENCES raw_material_lots(lot_id)


                   ) """)

    #Audit Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log(
                   log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   action TEXT NOT NULL,
                   details TEXT,
                   timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                   )""")




    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rml_material_id  ON raw_material_lots(material_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rm_name_lower     ON raw_materials(LOWER(name))")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipe_mat_recipe ON recipe_materials(recipe_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bm_lot_id         ON batch_materials(lot_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bm_material_id    ON batch_materials(material_id)")

    # Save all table creations to the database
    conn.commit()
    conn.close()
    print(" Database created")
    upgrade_schema()


def upgrade_schema():
    """Adds indexes and missing columns to an existing SQLite database. Safe to run on a fresh DB."""
    import sqlite3
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rml_material_id  ON raw_material_lots(material_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rm_name_lower     ON raw_materials(LOWER(name))")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipe_mat_recipe ON recipe_materials(recipe_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bm_lot_id         ON batch_materials(lot_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bm_material_id    ON batch_materials(material_id)")
    try:
        cursor.execute("ALTER TABLE batches ADD COLUMN shipment_id INTEGER DEFAULT NULL REFERENCES shipments(shipment_id)")
        conn.commit()
    except Exception:
        conn.rollback()  # column already exists
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shipments_date        ON shipments(date_shipped)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_shipment_id   ON batches(shipment_id)")
    conn.commit()
    conn.close()
