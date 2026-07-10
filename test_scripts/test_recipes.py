"""Tests for services/recipes.py — recipe CRUD, material-not-found rejection,
check_negative_stock math, and LEFT-JOIN handling of orphaned/empty recipes."""

import pytest

from services.recipes import (
    add_recipe, update_recipe, get_recipe, get_recipe_by_id, get_recipe_unit,
    get_recipe_batch_type, get_recipe_unit_and_dimension, get_recipe_names,
    check_negative_stock, get_all_recipes, get_all_recipes_with_id, delete_recipe_by_id,
)


def test_add_recipe_with_materials(make_material, make_recipe):
    make_material("Matcha")
    make_material("Sugar")
    rid = make_recipe("Latte Mix", [
        {"material_name": "Matcha", "quantity_needed": 10, "unit": "g"},
        {"material_name": "Sugar", "quantity_needed": 20, "unit": "g"},
    ])
    df = get_recipe("Latte Mix")
    assert set(df["material_name"]) == {"Matcha", "Sugar"}
    assert get_recipe_unit("Latte Mix") == "g"


def test_add_recipe_unknown_material_returns_none(make_material):
    # add_recipe swallows the ValueError and returns None after rollback.
    rid = add_recipe("Bad", [{"material_name": "Ghost", "quantity_needed": 1}])
    assert rid is None
    # nothing should have been persisted
    assert get_recipe("Bad") is None or get_recipe("Bad").empty


def test_recipe_batch_type_and_dimension(make_material, make_recipe):
    make_material("Matcha")
    make_recipe("Component A", [{"material_name": "Matcha", "quantity_needed": 5}],
                batch_type="mix", product_unit="g", product_dimension="mass")
    assert get_recipe_batch_type("Component A") == "mix"
    assert get_recipe_unit_and_dimension("Component A") == ("g", "mass")


def test_recipe_names_autocomplete_with_badge(make_material, make_recipe):
    make_material("Matcha")
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 1}], batch_type="finished")
    rows = get_recipe_names("lat")
    assert rows == [{"name": "Latte", "batch_type": "finished"}]


def test_check_negative_stock_flags_shortfall(make_material, make_lot, make_recipe):
    mid = make_material("Matcha")
    make_lot(mid, 5)
    make_recipe("Big Batch", [{"material_name": "Matcha", "quantity_needed": 10}])
    # need 10 * 2 = 20, have 5 -> short by 15
    neg = check_negative_stock("Big Batch", 2)
    assert len(neg) == 1
    row = neg[0]
    assert row["material_name"] == "Matcha"
    assert row["current_stock"] == 5
    assert row["required_amount"] == 20
    assert row["resulting_stock"] == -15


# --- server-timezone-vs-business-timezone fix -----------------------------------------
def test_check_negative_stock_counts_lot_expiring_pacific_tomorrow_during_utc_evening(
    freeze_business_time, make_material, make_lot, make_recipe
):
    # Render runs UTC; Botaniks runs Pacific. Frozen instant: 2026-01-02 06:00 UTC =
    # 2026-01-01 22:00 PST — Pacific's evening of Jan 1, but UTC's calendar date has already
    # rolled to Jan 2. A lot expiring on Pacific's actual tomorrow (Jan 2) must still count as
    # available stock here: it was being excluded a day early whenever "now" came from the
    # server's UTC clock instead of Botaniks' actual Pacific evening.
    from datetime import datetime
    from zoneinfo import ZoneInfo
    freeze_business_time(datetime(2026, 1, 2, 6, 0, 0, tzinfo=ZoneInfo("UTC")))

    mid = make_material("Matcha")
    make_lot(mid, 100, expiry_date="2026-01-02")
    make_recipe("Latte", [{"material_name": "Matcha", "quantity_needed": 10}])
    assert check_negative_stock("Latte", 1) == []  # need 10, have 100 -> no shortfall


def test_check_negative_stock_empty_when_sufficient(make_material, make_lot, make_recipe):
    mid = make_material("Matcha")
    make_lot(mid, 100)
    make_recipe("Small Batch", [{"material_name": "Matcha", "quantity_needed": 10}])
    assert check_negative_stock("Small Batch", 2) == []


def test_check_negative_stock_missing_recipe():
    assert check_negative_stock("nope", 1) == []


def test_update_recipe_replaces_materials(make_material, make_recipe):
    make_material("Matcha")
    make_material("Sugar")
    rid = make_recipe("R", [{"material_name": "Matcha", "quantity_needed": 5}])
    assert update_recipe(rid, materials=[{"material_name": "Sugar", "quantity_needed": 9, "unit": "g"}],
                         product_unit="g", product_dimension="mass", batch_type="finished") == rid
    df = get_recipe("R")
    assert list(df["material_name"]) == ["Sugar"]


def test_update_recipe_unknown_material_rolls_back(make_material, make_recipe):
    make_material("Matcha")
    rid = make_recipe("R", [{"material_name": "Matcha", "quantity_needed": 5}])
    # bad edit returns None and rolls back, leaving the original recipe intact
    assert update_recipe(rid, materials=[{"material_name": "Ghost", "quantity_needed": 1}]) is None
    df = get_recipe("R")
    assert list(df["material_name"]) == ["Matcha"]


def test_empty_recipe_still_appears_via_left_join(make_recipe):
    # a recipe with no materials must still be listed (LEFT JOIN), not silently dropped
    rid = add_recipe("Skeleton", [], product_unit="g", product_dimension="mass")
    assert isinstance(rid, int)
    df, total = get_all_recipes(page=None)
    assert "Skeleton" in set(df["recipe_product_name"])
    with_id, _ = get_all_recipes_with_id(page=None)
    assert "Skeleton" in set(with_id["product_name"])


def test_delete_recipe(make_material, make_recipe):
    make_material("Matcha")
    rid = make_recipe("Doomed", [{"material_name": "Matcha", "quantity_needed": 1}])
    assert delete_recipe_by_id(rid) is True
    assert get_recipe("Doomed") is None or get_recipe("Doomed").empty


def test_delete_missing_recipe_returns_none():
    assert delete_recipe_by_id(999999) is None
