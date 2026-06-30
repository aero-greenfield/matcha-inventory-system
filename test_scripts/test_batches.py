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
    get_batch_by_id, get_batches, get_batches_planned, get_all_batches_with_id,
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


def test_mix_lot_stored_full_precision(make_material, make_lot, make_recipe, db):
    # lot-selection-unit fix: the produced mix lot must be stored at FULL precision grams, not
    # round()ed to 4 dp. Rounding 1 lb (453.59237 g) to 4 dp gave 453.5924 g, which then read as
    # "insufficient" for a recipe needing the exact produced amount.
    from services import units
    mid = make_material("Matcha")
    lid = make_lot(mid, 1000)
    make_recipe("Component", [{"material_name": "Matcha", "quantity_needed": 10}],
                batch_type="mix", product_unit="lb", product_dimension="mass")
    add_to_batches("Component", 1, batch_number="MX1", batch_type="mix",
                   lot_selections={mid: [{"lot_id": lid, "qty": 10}]})
    cur = db.cursor()
    db.execute(cur, "SELECT quantity FROM raw_material_lots WHERE lot_number = %s", ("MIX-BATCH-MX1",))
    stored = cur.fetchone()[0]
    assert abs(float(stored) - float(units.to_base(1, "lb"))) < 1e-9  # 453.59237, not 453.5924


def test_exactly_enough_mix_covers_requirement(make_material, make_lot, make_recipe, db):
    # Regression for the reported bug: 176 lb of housemade mix on hand, a finished product needing
    # 16 lb x 11 batches = 176 lb. The stored grams (rounded to 4 dp, as the old mix path wrote
    # them) and the required grams differ by ~0.00002 g — below the 0.1 mg storage resolution but
    # ABOVE the old 1e-6 comparison tolerance, so the batch was wrongly refused. With the aligned
    # tolerance it now builds.
    from services import units
    def lb(x):
        return float(units.to_base(x, "lb"))
    mix = make_material("JasmineMix", is_housemade=True)
    # the mix lot as the OLD code stored it: full grams rounded to 4 dp
    lot = make_lot(mix, round(lb(176), 4))
    make_recipe("FinishedTea",
                [{"material_name": "JasmineMix", "quantity_needed": lb(16), "unit": "lb"}])
    bid = add_to_batches("FinishedTea", 11, batch_number="F1",
                         lot_selections={mix: [{"lot_id": lot, "qty": lb(16) * 11}]})
    assert isinstance(bid, int)
    # lot is driven to ~0 and exhausted (the tiny residual is below the exhaust threshold)
    qty, status = _lot_qty(db, lot)
    assert qty == 0 and status == "inactive"


# --- organic propagation through a mix -----------------------------------------------
def _material_flags(db, name):
    cur = db.cursor()
    db.execute(cur, "SELECT is_edible, is_organic FROM raw_materials WHERE name = %s", (name,))
    row = cur.fetchone()
    return (bool(row[0]), bool(row[1]))


def _mix_lot_for(db, material_name):
    cur = db.cursor()
    db.execute(cur, """SELECT l.lot_id FROM raw_material_lots l
                       JOIN raw_materials m ON l.material_id = m.material_id
                       WHERE m.name = %s""", (material_name,))
    return cur.fetchone()[0]


def test_organic_mix_material_is_edible_and_organic(make_material, make_lot, make_recipe, db):
    # (a) A Component made from an organic, edible input must yield a house-made material that is
    #     BOTH edible and organic, so it shows the Organic tag on the inventory page.
    mid = make_material("Matcha", is_organic=True, is_edible=True)
    lid = make_lot(mid, 100)
    make_recipe("OrgMix", [{"material_name": "Matcha", "quantity_needed": 10}],
                batch_type="mix", product_unit="g", product_dimension="mass")
    add_to_batches("OrgMix", 2, batch_number="OM1", batch_type="mix",
                   lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    is_edible, is_organic = _material_flags(db, "OrgMix")
    assert is_organic is True
    assert is_edible is True


def test_finished_batch_organic_when_only_input_is_organic_mix(make_material, make_lot, make_recipe, db):
    # (b) A finished batch whose only edible input is an organic mix must itself read as organic.
    mid = make_material("Matcha", is_organic=True, is_edible=True)
    lid = make_lot(mid, 1000)
    make_recipe("OrgMix", [{"material_name": "Matcha", "quantity_needed": 1}],
                batch_type="mix", product_unit="g", product_dimension="mass")
    add_to_batches("OrgMix", 100, batch_number="OM2", batch_type="mix",
                   lot_selections={mid: [{"lot_id": lid, "qty": 100}]})
    mix_lot = _mix_lot_for(db, "OrgMix")
    mix_mid = get_raw_material("OrgMix")[0]
    make_recipe("FinishedTea", [{"material_name": "OrgMix", "quantity_needed": 10, "unit": "g"}])
    fid = add_to_batches("FinishedTea", 1, batch_number="FT1",
                         lot_selections={mix_mid: [{"lot_id": mix_lot, "qty": 10}]})
    df, _ = get_batches(page=1, per_page=50)
    row = df[df["batch_id"] == fid].iloc[0]
    assert int(row["is_organic"]) == 1


def test_get_batches_reports_mix_remaining_and_consumed_count(make_material, make_lot, make_recipe, db):
    # mix-usage feature: after a finished batch draws from a Component's output lot, get_batches
    # must report the lot's remaining quantity (base units) and how many batches consumed it.
    mid = make_material("Matcha", is_organic=True, is_edible=True)
    lid = make_lot(mid, 1000)
    make_recipe("OrgMix", [{"material_name": "Matcha", "quantity_needed": 1}],
                batch_type="mix", product_unit="g", product_dimension="mass")
    mix_bid = add_to_batches("OrgMix", 100, batch_number="OM3", batch_type="mix",
                             lot_selections={mid: [{"lot_id": lid, "qty": 100}]})
    mix_lot = _mix_lot_for(db, "OrgMix")
    mix_mid = get_raw_material("OrgMix")[0]
    make_recipe("FinishedTea", [{"material_name": "OrgMix", "quantity_needed": 10, "unit": "g"}])
    add_to_batches("FinishedTea", 1, batch_number="FT2",
                   lot_selections={mix_mid: [{"lot_id": mix_lot, "qty": 10}]})
    df, _ = get_batches(page=1, per_page=50)
    mix_row = df[df["batch_id"] == mix_bid].iloc[0]
    assert mix_row["mix_remaining"] == 90        # 100 g produced - 10 g consumed
    assert mix_row["mix_consumed_count"] == 1


def test_finished_batch_cost_includes_component_cost(make_material, make_lot, make_recipe, db):
    # cost-of-component: a finished batch consuming a Component (mix) must include the mix's own
    # production cost. The mix output lot is given cost_per_unit = (input cost) / produced qty, which
    # the finished batch records into batch_materials and rolls into batch_cost. Previously the mix
    # lot had a NULL cost, so the component contributed $0.
    mid = make_material("Matcha")
    lid = make_lot(mid, 1000, cost_per_unit=3)
    make_recipe("Mix", [{"material_name": "Matcha", "quantity_needed": 1}],
                batch_type="mix", product_unit="g", product_dimension="mass")
    # 100 units consumes 100 g @ $3 = $300 to produce 100 g of mix -> $3/g on the output lot
    add_to_batches("Mix", 100, batch_number="MC1", batch_type="mix",
                   lot_selections={mid: [{"lot_id": lid, "qty": 100}]})
    mix_lot = _mix_lot_for(db, "Mix")
    mix_mid = get_raw_material("Mix")[0]
    make_recipe("FinishedTea", [{"material_name": "Mix", "quantity_needed": 10, "unit": "g"}])
    fid = add_to_batches("FinishedTea", 1, batch_number="FC1",
                         lot_selections={mix_mid: [{"lot_id": mix_lot, "qty": 10}]})
    df, _ = get_batches(page=1, per_page=50)
    row = df[df["batch_id"] == fid].iloc[0]
    assert row["batch_cost"] == pytest.approx(10 * 3)  # 10 g of mix @ $3/g = $30


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


def test_planned_promotion_failure_reports_insufficient_not_missing_selection(
    make_material, make_lot, make_recipe, db
):
    # Regression: a planned batch can store lot selections that OMIT a material the
    # create-batch UI couldn't auto-fill (no/insufficient active lots at creation). At
    # promotion that material has no stored entry, so it must fall back to FIFO and report
    # the REAL "Insufficient lot stock" reason — not the misleading "No stored lot selection".
    mid = make_material("Matcha")
    make_lot(mid, 5)  # only 5 g on hand, recipe needs 10
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    # non-None but empty: stored_lot_selections is a dict that doesn't contain `mid`
    bid = add_to_batches("Latte", 1, batch_number="P4", planned_completion_date=PAST,
                         batch_type="finished", lot_selections={})
    promote_planned_batches()
    status, reason = _batch_status(db, bid)
    assert status == "Planned"
    assert reason
    assert "Insufficient" in reason
    assert "no stored lot selection" not in reason.lower()


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


def test_delete_batch_reallocation_reactivates_exhausted_lot(make_material, make_lot, make_recipe, db):
    # A batch that fully depletes a lot leaves it quantity=0, status='inactive'.
    # Deleting with reallocation must restore the quantity AND reactivate the lot,
    # otherwise the stock counts but the lot is unusable in dropdowns/deduction.
    mid = make_material("Matcha")
    lid = make_lot(mid, 20)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 20}])
    bid = add_to_batches("Latte", 1, batch_number="D3",
                         lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    assert _lot_qty(db, lid) == (0, "inactive")  # exhausted

    realloc = get_batch_materials_for_reallocation(bid)
    assert delete_batch(bid, materials_to_reallocate=realloc, reallocate=True) is True
    assert _lot_qty(db, lid) == (20, "active")  # restored and reactivated


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


# --- list / read queries (the per-page rendering paths) ------------------------------
def test_get_batches_exposes_derived_columns(make_material, make_lot, make_recipe):
    mid = make_material("Matcha", is_organic=True, is_edible=True)
    lid = make_lot(mid, 100, cost_per_unit=3)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}], product_unit="g")
    bid = add_to_batches("Latte", 2, batch_number="L1",
                         lot_selections={mid: [{"lot_id": lid, "qty": 20}]})
    df, total = get_batches(page=1, per_page=50)
    row = df[df["batch_id"] == bid].iloc[0]
    assert total == 1
    assert row["batch_cost"] == pytest.approx(20 * 3)   # quantity_used * cost_per_unit
    assert row["remaining"] == 2                          # produced, nothing shipped yet
    assert row["product_unit"] == "g"
    assert int(row["is_organic"]) == 1                    # only organic edible material used


def test_get_batches_planned_includes_failure_reason(make_material, make_lot, make_recipe):
    mid = make_material("Matcha")
    make_lot(mid, 5)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    bid = add_to_batches("Latte", 1, batch_number="L2", planned_completion_date=PAST,
                         batch_type="finished", lot_selections=None)
    promote_planned_batches()  # fails -> stays planned with a reason
    df, total = get_batches_planned(page=1, per_page=50)
    row = df[df["batch_id"] == bid].iloc[0]
    assert total == 1
    assert row["promotion_failure_reason"]


def test_get_all_batches_with_id_lists_every_status(make_material, make_lot, make_recipe):
    mid = make_material("Matcha")
    lid = make_lot(mid, 100)
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    add_to_batches("Latte", 1, batch_number="R1",
                   lot_selections={mid: [{"lot_id": lid, "qty": 10}]})
    add_to_batches("Latte", 1, batch_number="PL1", planned_completion_date="2999-01-01",
                   batch_type="finished", lot_selections=None)
    df, total = get_all_batches_with_id(page=1, per_page=50)
    assert total == 2
    assert set(df["batch_number"]) == {"R1", "PL1"}
