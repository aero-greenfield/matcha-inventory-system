"""Tests for services/materials.py — material CRUD, duplicate detection, update whitelist,
cascade delete, and the derived stock/sort/pagination in get_all_materials."""

import pytest

from services.materials import (
    add_raw_material, get_raw_material, get_material_by_id, get_material_by_name,
    get_unit_and_dimension, get_material_id, get_material_names,
    update_raw_material, delete_raw_material, get_all_materials, get_low_stock_materials,
)


def test_add_material_returns_id(make_material):
    mid = make_material("Matcha")
    assert isinstance(mid, int)
    row = get_material_by_id(mid)
    # columns: material_id, name, category, unit, reorder_level, is_edible, is_organic, dimension
    assert row[1] == "Matcha"
    assert row[3] == "g"
    assert row[7] == "mass"


def test_duplicate_name_is_rejected_case_insensitively(make_material):
    make_material("Sugar")
    assert add_raw_material("sugar", "Sweetener", "g", 0) == "duplicate"


def test_get_raw_material_is_case_insensitive(make_material):
    mid = make_material("Green Tea")
    found = get_raw_material("GREEN TEA")
    assert found is not None and found[0] == mid


def test_get_material_id_and_by_name(make_material):
    mid = make_material("Houjicha")
    assert get_material_id("houjicha") == mid
    assert get_material_by_name("Houjicha") == ("Houjicha", "g")
    assert get_unit_and_dimension("Houjicha") == ("g", "mass")


def test_get_material_id_missing_returns_none():
    assert get_material_id("does-not-exist") is None


def test_update_material_changes_fields(make_material):
    mid = make_material("Genmaicha", reorder_level=5)
    assert update_raw_material(mid, name="Genmaicha Deluxe", reorder_level=10) is True
    row = get_material_by_id(mid)
    assert row[1] == "Genmaicha Deluxe"
    assert row[4] == 10


def test_update_material_rejects_non_whitelisted_column(make_material):
    mid = make_material("Sencha")
    # stock_level is an accepted *parameter* but is deliberately NOT in _MATERIAL_UPDATABLE_COLS
    # (stock is derived from lots, never written directly), so the allowlist guard must reject it.
    with pytest.raises(ValueError):
        update_raw_material(mid, stock_level=5)


def test_material_names_autocomplete(make_material):
    make_material("Matcha Ceremonial")
    make_material("Matcha Culinary")
    make_material("Sugar")
    names = get_material_names("matcha")
    assert set(names) == {"Matcha Ceremonial", "Matcha Culinary"}


def test_stock_is_summed_from_active_non_expired_lots(make_material, make_lot):
    mid = make_material("Matcha")
    make_lot(mid, 100)
    make_lot(mid, 50)
    make_lot(mid, 999, expiry_date="2000-01-01")  # expired -> excluded
    df, _ = get_all_materials(page=None)
    row = df[df["material_id"] == mid].iloc[0]
    assert row["stock_level"] == 150


def test_total_cost_aggregates_lot_cost(make_material, make_lot):
    mid = make_material("Matcha")
    make_lot(mid, 10, cost_per_unit=2)
    make_lot(mid, 5, cost_per_unit=4)
    df, _ = get_all_materials(page=None)
    row = df[df["material_id"] == mid].iloc[0]
    assert row["total_cost"] == pytest.approx(10 * 2 + 5 * 4)


def test_get_all_materials_pagination_total(make_material):
    for i in range(3):
        make_material(f"Mat{i}")
    df, total = get_all_materials(page=1, per_page=2)
    assert total == 3
    assert len(df) == 2


def test_sort_by_name_desc(make_material):
    make_material("Alpha")
    make_material("Zeta")
    df, _ = get_all_materials(page=None, sort_by="name", sort_dir="desc")
    names = list(df["name"])
    assert names.index("Zeta") < names.index("Alpha")


def test_low_stock_lists_materials_below_reorder(make_material, make_lot):
    low = make_material("LowMat", reorder_level=100)
    make_lot(low, 10)  # 10 <= 100 -> low
    ok = make_material("OkMat", reorder_level=5)
    make_lot(ok, 50)   # 50 > 5 -> not low
    df = get_low_stock_materials()
    listed = set(df["name"])
    assert "LowMat" in listed
    assert "OkMat" not in listed


def test_delete_material_cascades_and_reports_batches(make_material, make_lot):
    mid = make_material("Doomed")
    make_lot(mid, 10)
    result = delete_raw_material(mid)
    assert result["deleted"] is True
    assert result["affected_batches"] == []
    assert get_material_by_id(mid) is None


def test_delete_missing_material_returns_none():
    assert delete_raw_material(999999) is None
