"""HTTP integration tests through the Flask test client (app.py + routes/api.py).

Exercises the form-parse -> validate -> service -> redirect/flash path end to end, plus
auth enforcement and the JSON API. CSRF and rate limiting are disabled by the `client`
fixture so requests are deterministic. Representative coverage, not every route.
"""

import pytest

from services.materials import get_material_id, get_raw_material
from services.lots import get_material_stock_from_lots


# --- auth ----------------------------------------------------------------------------
def test_protected_route_requires_auth(client):
    assert client.get("/inventory").status_code == 401
    assert client.get("/api/materials").status_code == 401


def test_health_is_public_and_reports_db(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "healthy"
    assert body["db"] == "connected"


# --- GET pages render with auth ------------------------------------------------------
GET_PAGES = [
    "/", "/inventory", "/recipes", "/batches", "/low-stock", "/audit-log",
    "/manage-materials", "/manage-lots", "/manage-recipes", "/manage-batches",
    "/manage-shipments", "/shipments", "/shipments/new",
    "/add-material", "/receive-lot", "/create-batch", "/add-recipe",
]


@pytest.mark.parametrize("path", GET_PAGES)
def test_get_pages_render(client, auth, path):
    resp = client.get(path, headers=auth)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}"


# --- JSON API ------------------------------------------------------------------------
def test_api_materials_autocomplete(client, auth, make_material):
    make_material("Matcha Ceremonial")
    make_material("Sugar")
    rows = client.get("/api/materials?q=matcha", headers=auth).get_json()
    assert rows == ["Matcha Ceremonial"]


def test_api_material_unit_lookup(client, auth, make_material):
    make_material("Matcha", unit="g", dimension="mass")
    body = client.get("/api/material-unit?name=Matcha", headers=auth).get_json()
    assert body == {"exists": True, "unit": "g", "dimension": "mass"}


def test_api_material_unit_missing(client, auth):
    body = client.get("/api/material-unit?name=ghost", headers=auth).get_json()
    assert body == {"exists": False}


def test_api_available_lots(client, auth, make_material, make_lot):
    mid = make_material("Matcha")
    make_lot(mid, 25)
    rows = client.get(f"/api/available-lots/{mid}", headers=auth).get_json()
    assert len(rows) == 1
    assert rows[0]["quantity"] == 25


def test_api_available_lots_invalid_id(client, auth):
    resp = client.get("/api/available-lots/abc", headers=auth)
    assert resp.status_code == 400


def test_api_recipe_materials_reports_entry_unit(client, auth, make_material, make_recipe):
    # lot-selection-unit fix: a recipe line entered in lb must tell the create-batch UI to
    # DISPLAY in lb (display_unit) and how to convert stored grams <-> lb (base_per_display),
    # not hardcode grams. quantity_needed stays in grams (the base unit).
    from services import units
    make_material("JasmineMix", is_housemade=True)
    make_recipe(
        "FinishedTea",
        [{"material_name": "JasmineMix", "quantity_needed": float(units.to_base(16, "lb")), "unit": "lb"}],
    )
    rows = client.get("/api/recipe-materials/FinishedTea", headers=auth).get_json()
    assert len(rows) == 1
    row = rows[0]
    assert row["display_unit"] == "lb"
    assert row["base_per_display"] == pytest.approx(453.59237)
    assert row["quantity_needed"] == pytest.approx(float(units.to_base(16, "lb")))


def test_api_recipe_materials_count_uses_material_unit(client, auth, make_material, make_recipe):
    # count materials never convert: display in the material's own unit, factor 1.
    make_material("Tins", unit="tin", dimension="count")
    make_recipe(
        "GiftSet",
        [{"material_name": "Tins", "quantity_needed": 3, "unit": "tin"}],
        product_unit="set", product_dimension="count",
    )
    rows = client.get("/api/recipe-materials/GiftSet", headers=auth).get_json()
    assert rows[0]["display_unit"] == "tin"
    assert rows[0]["base_per_display"] == 1.0


# --- POST /add-material --------------------------------------------------------------
def _material_form(**over):
    form = {
        "name": "Matcha",
        "category": "Tea",
        "unit": "g",
        "material_type": "mass",
        "reorder_level": "5",
        "is_edible": "1",
    }
    form.update(over)
    return form


def test_add_material_success_redirects_and_persists(client, auth):
    resp = client.post("/add-material", data=_material_form(), headers=auth)
    assert resp.status_code == 302
    assert get_material_id("Matcha") is not None


def test_add_material_duplicate_shows_error(client, auth, make_material):
    make_material("Matcha")
    resp = client.post("/add-material", data=_material_form(name="Matcha"), headers=auth)
    assert resp.status_code == 200
    assert b"already exists" in resp.data


def test_add_material_blank_name_400(client, auth):
    resp = client.post("/add-material", data=_material_form(name=""), headers=auth)
    assert resp.status_code == 400


def test_add_material_missing_dimension_400(client, auth):
    resp = client.post("/add-material", data=_material_form(material_type=""), headers=auth)
    assert resp.status_code == 400


def test_add_material_mass_unit_mismatch_400(client, auth):
    # 'tin' is a count label, not a recognized mass unit -> rejected for a Weight material
    resp = client.post("/add-material", data=_material_form(unit="tin", material_type="mass"), headers=auth)
    assert resp.status_code == 400


# --- POST /receive-lot ---------------------------------------------------------------
def _lot_form(**over):
    form = {
        "material_name": "Matcha",
        "lot_number": "L-100",
        "quantity": "50",
        "received_date": "2024-01-01",
        "cost_per_unit": "2",
    }
    form.update(over)
    return form


def test_receive_lot_success_redirects_to_inventory(client, auth, make_material):
    make_material("Matcha", unit="g", dimension="mass")
    resp = client.post("/receive-lot", data=_lot_form(), headers=auth)
    assert resp.status_code == 302
    assert "/inventory" in resp.headers["Location"]
    mid = get_material_id("Matcha")
    assert get_material_stock_from_lots(mid) == 50


def test_receive_lot_unknown_material_redirects_to_add_material(client, auth):
    resp = client.post("/receive-lot", data=_lot_form(material_name="Ghost"), headers=auth)
    assert resp.status_code == 302
    assert "/add-material" in resp.headers["Location"]


def test_receive_lot_non_positive_quantity_400(client, auth, make_material):
    make_material("Matcha")
    resp = client.post("/receive-lot", data=_lot_form(quantity="0"), headers=auth)
    assert resp.status_code == 400


def test_receive_lot_blank_lot_number_400(client, auth, make_material):
    make_material("Matcha")
    resp = client.post("/receive-lot", data=_lot_form(lot_number=""), headers=auth)
    assert resp.status_code == 400
