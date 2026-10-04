"""Builds a standalone demo database with realistic Botaniks data for README screenshots /
live demos. Writes to its OWN SQLite file (data/demo_inventory.db by default) — never touches
the real dev DB (data/inventory.db). Safe to re-run: deletes and rebuilds the demo file each time.

Usage:
    python scripts/seed_demo_data.py


    just run ts: 
    
python scripts/seed_demo_data.py   # rebuilds data/demo_inventory.db (safe to re-run)
$env:SQLITE_PATH="data/demo_inventory.db"; $env:PORT="8001"; python app.py


Then run a second app instance against it (keep your normal :8000 dev server running):
    # PowerShell
    $env:SQLITE_PATH="data/demo_inventory.db"; $env:PORT="8001"; python app.py
    # bash
    SQLITE_PATH=data/demo_inventory.db PORT=8001 python app.py

Auth for the demo instance is whatever AUTH_USERNAME/AUTH_PASSWORD are in your .env (unchanged).
"""

import os
import sys
from datetime import datetime, timedelta

# --- env must be set before importing anything that touches the DB (same rule as conftest.py) ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ.pop("DATABASE_URL", None)  # force SQLite mode regardless of .env
_DEMO_PATH = os.path.join(_PROJECT_ROOT, "data", "demo_inventory.db")
os.environ["SQLITE_PATH"] = _DEMO_PATH

if os.path.exists(_DEMO_PATH):
    os.remove(_DEMO_PATH)

from services.setup import create_database
from services.materials import add_raw_material, get_material_id
from services.lots import receive_lot, get_lots_for_material
from services.recipes import add_recipe
from services.batches import add_to_batches, promote_planned_batches
from services.shipments import create_shipment

create_database()

TODAY = datetime.now()


def d(days_ago):
    """Date string `days_ago` days before today (negative = in the future)."""
    return (TODAY - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def fifo_lot_selections(recipe_materials, quantity):
    """Greedily builds the {material_id: [{'lot_id', 'qty'}, ...]} structure add_to_batches
    expects, drawing oldest-lot-first — mirrors what the autocomplete UI auto-fills."""
    selections = {}
    for material_id, qty_per_unit in recipe_materials:
        needed = qty_per_unit * quantity
        df = get_lots_for_material(material_id)
        picks = []
        for _, row in df.iterrows():
            if needed <= 1e-9:
                break
            take = min(row["quantity"], needed)
            picks.append({"lot_id": int(row["lot_id"]), "qty": take})
            needed -= take
        if needed > 1e-6:
            raise RuntimeError(f"Not enough stock for material_id {material_id}: short by {needed}")
        selections[material_id] = picks
    return selections


# ---------------------------------------------------------------------------
# Raw materials
# ---------------------------------------------------------------------------
mat = {}
mat["ceremonial_leaf"] = add_raw_material(
    "Ceremonial Matcha Leaf", "Tea", "kg", reorder_level=3000,
    is_edible=True, is_organic=True, dimension="mass",
)
mat["culinary_leaf"] = add_raw_material(
    "Culinary Matcha Leaf", "Tea", "kg", reorder_level=5000,
    is_edible=True, is_organic=False, dimension="mass",
)
mat["cane_sugar"] = add_raw_material(
    "Cane Sugar", "Ingredient", "kg", reorder_level=2000,
    is_edible=True, is_organic=False, dimension="mass",
)
mat["tin_30g"] = add_raw_material(
    "30g Tin", "Packaging", "each", reorder_level=150,
    is_edible=False, is_organic=False, dimension="count",
)
mat["pouch_100g"] = add_raw_material(
    "100g Pouch", "Packaging", "each", reorder_level=100,
    is_edible=False, is_organic=False, dimension="count",
)
mat["pouch_200g"] = add_raw_material(
    "200g Pouch", "Packaging", "each", reorder_level=80,
    is_edible=False, is_organic=False, dimension="count",
)
mat["tin_label"] = add_raw_material(
    "Tin Label", "Packaging", "each", reorder_level=200,
    is_edible=False, is_organic=False, dimension="count",
)
mat["pouch_label"] = add_raw_material(
    "Pouch Label", "Packaging", "each", reorder_level=200,
    is_edible=False, is_organic=False, dimension="count",
)
mat["shipping_box"] = add_raw_material(
    "Shipping Box", "Packaging", "each", reorder_level=40,
    is_edible=False, is_organic=False, dimension="count",
)

for name, mid in mat.items():
    if not isinstance(mid, int):
        raise RuntimeError(f"Failed to create material {name!r}: {mid!r}")

# ---------------------------------------------------------------------------
# Lots (quantities in base units: grams for mass, each for count)
# ---------------------------------------------------------------------------
receive_lot(mat["ceremonial_leaf"], "CL-2501", 4000, d(42), expiry_date=d(-180), supplier="Uji Tea Gardens", location="Cold Storage A", cost_per_unit=0.062)
receive_lot(mat["ceremonial_leaf"], "CL-2512", 3000, d(12), expiry_date=d(-15), supplier="Uji Tea Gardens", location="Cold Storage A", cost_per_unit=0.065)

receive_lot(mat["culinary_leaf"], "CU-2488", 7000, d(50), expiry_date=d(-220), supplier="Nishio Farms", location="Cold Storage B", cost_per_unit=0.024)
receive_lot(mat["culinary_leaf"], "CU-2503", 4000, d(22), expiry_date=d(-200), supplier="Nishio Farms", location="Cold Storage B", cost_per_unit=0.026)
receive_lot(mat["culinary_leaf"], "CU-2519", 1500, d(5), expiry_date=d(-210), supplier="Nishio Farms", location="Cold Storage B", cost_per_unit=0.025)

receive_lot(mat["cane_sugar"], "SG-900", 10000, d(30), supplier="Pacific Sugar Co.", location="Dry Storage", cost_per_unit=0.003)

receive_lot(mat["tin_30g"], "PK-TIN-14", 300, d(40), supplier="Cascade Packaging", location="Shelf A1", cost_per_unit=0.45)
receive_lot(mat["tin_30g"], "PK-TIN-19", 200, d(9), supplier="Cascade Packaging", location="Shelf A1", cost_per_unit=0.47)

receive_lot(mat["pouch_100g"], "PK-P100-11", 180, d(26), supplier="Cascade Packaging", location="Shelf A2", cost_per_unit=0.30)

receive_lot(mat["pouch_200g"], "PK-P200-07", 90, d(26), supplier="Cascade Packaging", location="Shelf A2", cost_per_unit=0.35)

receive_lot(mat["tin_label"], "LBL-TIN-03", 500, d(40), supplier="Evergreen Print Co.", location="Shelf B1", cost_per_unit=0.08)
receive_lot(mat["pouch_label"], "LBL-PCH-03", 500, d(40), supplier="Evergreen Print Co.", location="Shelf B1", cost_per_unit=0.08)

receive_lot(mat["shipping_box"], "BOX-22", 25, d(40), supplier="Cascade Packaging", location="Shelf C1", cost_per_unit=0.60)

# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------
add_recipe(
    "Ceremonial Matcha 30g Tin",
    [
        {"material_name": "Ceremonial Matcha Leaf", "quantity_needed": 30, "unit": "g"},
        {"material_name": "30g Tin", "quantity_needed": 1, "unit": "each"},
        {"material_name": "Tin Label", "quantity_needed": 1, "unit": "each"},
    ],
    notes="Ceremonial grade, hand-sieved. Single-origin Uji leaf.",
    product_unit="each", product_dimension="count", batch_type="finished",
)

add_recipe(
    "Culinary Matcha 100g Pouch",
    [
        {"material_name": "Culinary Matcha Leaf", "quantity_needed": 100, "unit": "g"},
        {"material_name": "100g Pouch", "quantity_needed": 1, "unit": "each"},
        {"material_name": "Pouch Label", "quantity_needed": 1, "unit": "each"},
    ],
    notes="For lattes, baking, culinary use.",
    product_unit="each", product_dimension="count", batch_type="finished",
)

add_recipe(
    "Matcha Latte Mix",
    [
        {"material_name": "Culinary Matcha Leaf", "quantity_needed": 0.3, "unit": "g"},
        {"material_name": "Cane Sugar", "quantity_needed": 0.7, "unit": "g"},
    ],
    notes="House-made intermediate: 30/70 matcha-to-sugar blend, by weight.",
    product_unit="g", product_dimension="mass", batch_type="mix",
)

# ---------------------------------------------------------------------------
# Batches — standard production history (Ready, immediate deduction)
# ---------------------------------------------------------------------------
recipe_ceremonial = [(mat["ceremonial_leaf"], 30), (mat["tin_30g"], 1), (mat["tin_label"], 1)]
recipe_culinary = [(mat["culinary_leaf"], 100), (mat["pouch_100g"], 1), (mat["pouch_label"], 1)]
recipe_mix = [(mat["culinary_leaf"], 0.3), (mat["cane_sugar"], 0.7)]

b1_qty = 120
add_to_batches(
    "Ceremonial Matcha 30g Tin", b1_qty, batch_number="B-0001",
    batch_type="finished", deduct_resources=True,
    lot_selections=fifo_lot_selections(recipe_ceremonial, b1_qty),
    expiration_date=d(-180),
)

b2_qty = 60
add_to_batches(
    "Culinary Matcha 100g Pouch", b2_qty, batch_number="B-0002",
    batch_type="finished", deduct_resources=True,
    lot_selections=fifo_lot_selections(recipe_culinary, b2_qty),
    expiration_date=d(-170),
)

b3_qty = 5000  # grams of mix produced
mix_batch_id = add_to_batches(
    "Matcha Latte Mix", b3_qty, batch_number="B-0003",
    batch_type="mix", deduct_resources=True,
    lot_selections=fifo_lot_selections(recipe_mix, b3_qty),
)

# Now that the mix exists as a house-made raw material, a finished recipe can consume it.
mix_material_id = get_material_id("Matcha Latte Mix")
add_recipe(
    "Matcha Latte 200g Pouch",
    [
        {"material_name": "Matcha Latte Mix", "quantity_needed": 200, "unit": "g"},
        {"material_name": "200g Pouch", "quantity_needed": 1, "unit": "each"},
        {"material_name": "Pouch Label", "quantity_needed": 1, "unit": "each"},
    ],
    notes="Pre-blended sweetened matcha for iced/hot lattes.",
    product_unit="each", product_dimension="count", batch_type="finished",
)
recipe_latte = [(mix_material_id, 200), (mat["pouch_200g"], 1), (mat["pouch_label"], 1)]

b4_qty = 15
add_to_batches(
    "Matcha Latte 200g Pouch", b4_qty, batch_number="B-0004",
    batch_type="finished", deduct_resources=True,
    lot_selections=fifo_lot_selections(recipe_latte, b4_qty),
    expiration_date=d(-150),
)

b5_qty = 60
add_to_batches(
    "Ceremonial Matcha 30g Tin", b5_qty, batch_number="B-0005",
    batch_type="finished", deduct_resources=True,
    lot_selections=fifo_lot_selections(recipe_ceremonial, b5_qty),
    expiration_date=d(-173),
)

b6_qty = 25  # pushes 100g Pouch stock below its reorder level -> demonstrates Low badge
add_to_batches(
    "Culinary Matcha 100g Pouch", b6_qty, batch_number="B-0006",
    batch_type="finished", deduct_resources=True,
    lot_selections=fifo_lot_selections(recipe_culinary, b6_qty),
    expiration_date=d(-165),
)

# ---------------------------------------------------------------------------
# Planned batches — demonstrates the Planned -> Ready promotion lifecycle
# ---------------------------------------------------------------------------
# Upcoming (not due yet): deferred deduction — materials are reserved, not yet consumed.
add_to_batches(
    "Culinary Matcha 100g Pouch", 40, batch_number="B-0007",
    batch_type="finished", deduct_resources=True,
    planned_completion_date=d(-10), deduction_mode="deferred",
    lot_selections=None,
)

# Overdue, already deducted at creation (immediate mode) -> promote_planned_batches() below
# will flip it Planned -> Ready, mirroring what runs automatically in production.
b8_qty = 40
add_to_batches(
    "Ceremonial Matcha 30g Tin", b8_qty, batch_number="B-0008",
    batch_type="finished", deduct_resources=True,
    lot_selections=fifo_lot_selections(recipe_ceremonial, b8_qty),
    planned_completion_date=d(3), deduction_mode="immediate",
    expiration_date=d(-177),
)

promote_planned_batches()

# ---------------------------------------------------------------------------
# Shipments
# ---------------------------------------------------------------------------
import database as _db
_conn = _db.get_db_connection()
_cur = _conn.cursor()
_conn.execute(_cur, "SELECT batch_number, batch_id FROM batches")
batch_ids = dict(_cur.fetchall())
_conn.close()

create_shipment(
    {batch_ids["B-0001"]: 70},
    destination="Verdant Leaf Cafe, Portland OR",
    notes="Monthly ceremonial restock.",
    category="Wholesale",
    date_shipped=d(25),
)

create_shipment(
    {batch_ids["B-0002"]: 40, batch_ids["B-0004"]: 10},
    destination="Market & Rye, Seattle WA",
    notes="First latte-mix pouch order.",
    category="Wholesale",
    date_shipped=d(13),
)

create_shipment(
    {batch_ids["B-0001"]: 50, batch_ids["B-0005"]: 20},
    destination="botaniks.com Online Orders",
    notes="Weekly DTC fulfillment batch.",
    category="Direct-to-Consumer",
    date_shipped=d(2),
)

print(f"\nDemo database ready: {_DEMO_PATH}")
print("Run a second instance against it, e.g.:")
print('  $env:SQLITE_PATH="data/demo_inventory.db"; $env:PORT="8001"; python app.py')
