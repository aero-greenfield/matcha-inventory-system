"""Tests for the unit-of-measurement conversion layer (services/units.py).

Pure logic, no DB. This is the highest-leverage module to pin: the whole point of the
units-conversion-layer work is exact Decimal arithmetic with no float spew.
"""

from decimal import Decimal

import pytest

from services import units


# --- dimension classification --------------------------------------------------------
@pytest.mark.parametrize("unit", ["g", "kg", "lb", "oz", "mg"])
def test_canonical_mass_units_are_mass(unit):
    assert units.dimension_of(unit) == "mass"


@pytest.mark.parametrize("unit", ["lbs", "grams", "pounds", "kgs", "ounce", "milligram"])
def test_mass_aliases_resolve_to_mass(unit):
    assert units.dimension_of(unit) == "mass"


@pytest.mark.parametrize("unit", ["tin", "sachet", "each", "unit", "box"])
def test_unknown_labels_are_count(unit):
    assert units.dimension_of(unit) == "count"


def test_classification_ignores_case_and_whitespace():
    assert units.dimension_of("  LB ") == "mass"


def test_dimension_of_none_raises():
    with pytest.raises(ValueError):
        units.dimension_of(None)


# --- to_base (entry -> grams) is exact ----------------------------------------------
def test_to_base_grams_identity():
    assert units.to_base(2, "g") == Decimal("2")


def test_to_base_pound_is_exact():
    assert units.to_base(1, "lb") == Decimal("453.59237")


def test_to_base_kilogram():
    assert units.to_base(1, "kg") == Decimal("1000")


def test_sixteen_oz_equals_one_pound():
    assert units.to_base(16, "oz") == units.to_base(1, "lb")


def test_to_base_count_is_identity():
    assert units.to_base(12, "tin") == Decimal("12")


def test_float_input_does_not_leak_binary_noise():
    # Decimal(str(0.1)) == 0.1 exactly, unlike Decimal(0.1).
    assert units.to_base(0.1, "g") == Decimal("0.1")


# --- from_base (grams -> display) ----------------------------------------------------
def test_from_base_pound_round():
    assert units.from_base(Decimal("453.59237"), "lb") == Decimal("1")


def test_from_base_kilogram():
    assert units.from_base(Decimal("1000"), "kg") == Decimal("1")


def test_from_base_count_identity():
    assert units.from_base(Decimal("7"), "sachet") == Decimal("7")


@pytest.mark.parametrize("amount,unit", [(2, "g"), (3.5, "lb"), (0.25, "kg"), (8, "oz")])
def test_round_trip_returns_original(amount, unit):
    base = units.to_base(amount, unit)
    assert units.from_base(base, unit) == Decimal(str(amount))


# --- convert -------------------------------------------------------------------------
def test_convert_grams_to_kg():
    assert units.convert(1000, "g", "kg") == Decimal("1")


def test_convert_pound_to_grams():
    assert units.convert(1, "lb", "g") == Decimal("453.59237")


def test_convert_count_identity():
    assert units.convert(5, "tin", "tin") == Decimal("5")


def test_convert_across_dimensions_raises():
    with pytest.raises(ValueError):
        units.convert(5, "g", "tin")


# --- the precision bug this feature fixes -------------------------------------------
def test_gram_based_deduction_stays_exact():
    remaining = units.to_base(1, "lb") - units.to_base(2, "g")
    assert remaining == Decimal("451.59237")
