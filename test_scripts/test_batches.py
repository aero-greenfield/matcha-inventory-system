"""Tests for services/batches.py — the most complex logic in the app.

Covers: standard immediate deduction, lot coverage/over-allocation validation, expired/
insufficient lot rejection, multi-lot deduction + exhaustion, allow_negative override,
mix (housemade) output-lot creation, planned-batch promotion (stored-lot and FIFO paths),
promotion failure recording, delete-with-reallocation, and adjust/check batch materials.

lot_selections shape (per add_to_batches docstring): {material_id: [{'lot_id', 'qty'}, ...]}.
"""

import pytest

from services.batches import (
    add_to_batches, promote_planned_batches, delete_batch, get_batch_materials,
    get_batch_materials_for_reallocation, adjust_batch_material, check_batch_materials_stock,
    get_batch_by_id,
)
from services.lots import get_material_stock_from_lots
from services.materials import get_raw_material


PAST = "2020-01-01"  # always overdue, so promote_planned_batches picks it up


def _lot_qty(db, lot_id):
    cur = db.cursor()
    db.execute(cur, "SELECT quantity, status FROM raw_material_lots WHERE lot_id = %s", (lot_id,))
    return cur.fetchone()


def _batch_status(db, batch_id):
    cur = db.cursor()
    db.execute(cur, "SELECT status, promotion_failure_reason FROM batches WHERE batch_id = %s", (batch_id,))
    return cur.fetchone()


# --- standard immediate deduction ----------------------------------------------------
def test_standard_batch_deducts_from_lot(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    lid = make_lot(mid, 100)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])

    bid = add_to_batches("Latte", 2, batch_number="B1",
                         lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    assert isinstance(bid, int)
    assert _lot_qty(db, lid)[0] == 80
    mats = get_batch_materials(bid)
    assert len(mats) == 1 and mats[0][1] == 20  # quantity_used


def test_over_allocation_sum_mismatch_raises(make_material, make_lot, make_recipe):
    mid = make_material("Matcha")
    lid = make_lot(mid, 100)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    # required is 20 but only 5 selected -> coverage check fails before any write
    with pytest.raises(ValueError):
        add_to_batches("Latte", 2, batch_number="B2",
                       lot_selections={mid: [{"lot_id": lid, "qty": 5}]})


def test_insufficient_lot_quantity_raises(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    lid = make_lot(mid, 5)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 20}])
    # sum (20) matches required (20), but the lot only holds 5 -> per-lot check fails
    with pytest.raises(ValueError):
        add_to_batches("Latte", 1, batch_number="B3",
                       lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    # rolled back: lot untouched
    assert _lot_qty(db, lid)[0] == 5


def test_missing_lot_selection_for_material_raises(make_material, make_lot, make_recipe):
    mid = make_material("Matcha")
    make_lot(mid, 100)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    with pytest.raises(ValueError):
        add_to_batches("Latte", 1, batch_number="B4", lot_selections={})


def test_none_lot_selections_raises(make_material, make_lot, make_recipe):
    mid = make_material("Matcha")
    make_lot(mid, 100)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    with pytest.raises(ValueError):
        add_to_batches("Latte", 1, batch_number="B5", lot_selections=None)


def test_recipe_with_no_materials_raises(make_material):
    # no recipe rows at all -> get_recipe returns empty
    with pytest.raises(ValueError):
        add_to_batches("ghost-product", 1, batch_number="B6",
                       lot_selections={1: [{"lot_id": 1, "qty": 1}]})


def test_deduction_spans_two_lots_and_exhausts(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    old = make_lot(mid, 20, received_date="2024-01-01", lot_number="OLD")
    new = make_lot(mid, 20, received_date="2024-03-01", lot_number="NEW")
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 30}])
    # take all of OLD (20) and 10 of NEW
    bid = add_to_batches("Latte", 1, batch_number="B7",
                         lot_selections={mid: [{"lot_id": old, "qty": 20}, {"lot_id": new, "qty": 10}]})
    assert isinstance(bid, int)
    old_qty, old_status = _lot_qty(db, old)
    assert old_qty == 0 and old_status == "inactive"  # exhausted
    assert _lot_qty(db, new)[0] == 10


def test_expired_lot_is_rejected(make_material, make_lot, make_recipe):
    mid = make_material("Matcha")
    lid = make_lot(mid, 100, expiry_date="2000-01-01")
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    with pytest.raises(ValueError):
        add_to_batches("Latte", 1, batch_number="B8",
                       lot_selections={mid: [{"lot_id": lid, "qty": 10}]})


def test_allow_negative_override_creates_batch(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    lid = make_lot(mid, 5)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 20}])
    bid = add_to_batches("Latte", 1, batch_number="B9", allow_negative=True,
                         lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    # batch is created despite the lot not covering the recipe (coverage/per-lot checks bypassed)
    assert isinstance(bid, int)
    assert get_batch_materials(bid)[0][1] == 20  # full requested amount recorded as used
    # the deduction drives the lot to -15, which is below the exhaust threshold, so it is
    # zeroed and deactivated rather than left showing a negative quantity.
    qty, status = _lot_qty(db, lid)
    assert qty == 0 and status == "inactive"


# --- mix / housemade -----------------------------------------------------------------
def test_mix_batch_creates_housemade_material_and_lot(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    lid = make_lot(mid, 100)
    make_recipe("Component", [{"material_name": "Matcha", "quantity_needed": 10}],
                batch_type="mix", product_unit="g", product_dimension="mass")
    bid = add_to_batches("Component", 2, batch_number="C1", batch_type="mix",
                         lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    assert isinstance(bid, int)
    # input deducted
    assert _lot_qty(db, lid)[0] == 80
    # housemade material now exists and has a MIX-BATCH lot of 2 g (to_base(2,'g'))
    hm = get_raw_material("Component")
    assert hm is not None
    cur = db.cursor()
    db.execute(cur, """SELECT quantity FROM raw_material_lots
                       WHERE lot_number = %s""", ("MIX-BATCH-C1",))
    assert cur.fetchone()[0] == 2


# --- planned promotion: stored lots --------------------------------------------------
def test_planned_finished_defers_then_promotes_stored_lots(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    lid = make_lot(mid, 100)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    bid = add_to_batches("Latte", 2, batch_number="P1", planned_completion_date=PAST,
                         batch_type="finished",
                         lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    assert isinstance(bid, int)
    # deferred: nothing deducted yet, batch is Planned
    assert _lot_qty(db, lid)[0] == 100
    assert _batch_status(db, bid)[0] == "Planned"

    promote_planned_batches()
    assert _lot_qty(db, lid)[0] == 80
    assert _batch_status(db, bid)[0] == "Ready"


# --- planned promotion: FIFO fallback ------------------------------------------------
def test_planned_promotes_via_fifo_when_no_stored_lots(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    old = make_lot(mid, 20, received_date="2024-01-01", lot_number="OLD")
    new = make_lot(mid, 20, received_date="2024-03-01", lot_number="NEW")
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 30}])
    bid = add_to_batches("Latte", 1, batch_number="P2", planned_completion_date=PAST,
                         batch_type="finished", lot_selections=None)
    assert isinstance(bid, int)
    promote_planned_batches()
    # FIFO drained OLD first (oldest), then 10 of NEW
    assert _lot_qty(db, old)[0] == 0
    assert _lot_qty(db, new)[0] == 10
    assert _batch_status(db, bid)[0] == "Ready"


def test_planned_promotion_failure_keeps_planned_with_reason(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    make_lot(mid, 5)  # not enough for need of 10
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    bid = add_to_batches("Latte", 1, batch_number="P3", planned_completion_date=PAST,
                         batch_type="finished", lot_selections=None)
    promote_planned_batches()
    status, reason = _batch_status(db, bid)
    assert status == "Planned"
    assert reason and "Insufficient" in reason


# --- delete with reallocation --------------------------------------------------------
def test_delete_batch_reallocates_stock(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    lid = make_lot(mid, 100)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    bid = add_to_batches("Latte", 2, batch_number="D1",
                         lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    assert _lot_qty(db, lid)[0] == 80

    realloc = get_batch_materials_for_reallocation(bid)
    assert delete_batch(bid, materials_to_reallocate=realloc, reallocate=True) is True
    # stock returned to the original lot
    assert _lot_qty(db, lid)[0] == 100
    assert get_batch_by_id(bid) is None


def test_delete_batch_without_reallocation_leaves_stock_deducted(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    lid = make_lot(mid, 100)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    bid = add_to_batches("Latte", 2, batch_number="D2",
                         lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    assert delete_batch(bid) is True
    assert _lot_qty(db, lid)[0] == 80  # NOT restored
    assert get_batch_by_id(bid) is None


# --- adjust / check batch materials --------------------------------------------------
def test_adjust_batch_material_increase_then_decrease(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    lid = make_lot(mid, 100)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    bid = add_to_batches("Latte", 2, batch_number="A1",
                         lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    assert _lot_qty(db, lid)[0] == 80

    # increase usage to 25 -> deduct 5 more
    assert adjust_batch_material(bid, {mid: 25}) is True
    assert _lot_qty(db, lid)[0] == 75

    # decrease usage to 10 -> return 15
    assert adjust_batch_material(bid, {mid: 10}) is True
    assert _lot_qty(db, lid)[0] == 90


def test_adjust_batch_material_insufficient_stock_aborts(make_material, make_lot, make_recipe, db):
    mid = make_material("Matcha")
    lid = make_lot(mid, 20)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    bid = add_to_batches("Latte", 1, batch_number="A2",
                         lot_selections={mid: [{"lot_id": lid, "qty": 10}]})
    # lot now has 10 left; asking to use 1000 would need 990 more -> abort, no change
    assert adjust_batch_material(bid, {mid: 1000}) is None
    assert _lot_qty(db, lid)[0] == 10


def test_check_batch_materials_stock_dry_run(make_material, make_lot, make_recipe):
    mid = make_material("Matcha")
    lid = make_lot(mid, 20)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    bid = add_to_batches("Latte", 1, batch_number="A3",
                         lot_selections={mid: [{"lot_id": lid, "qty": 10}]})
    # 10 left in lot: bumping usage to 15 (needs 5 more) is fine; to 1000 is not
    assert check_batch_materials_stock(bid, {mid: 15}) is True
    assert check_batch_materials_stock(bid, {mid: 1000}) is False
