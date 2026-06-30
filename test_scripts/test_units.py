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


# --- property-based: generalize the example tests above across the whole input space --
# These guard the conversion layer (the root of the lot-selection precision bug) against
# *classes* of error — a wrong factor, a broken alias, lost precision at the float boundary —
# rather than the handful of nice values the example tests cover. Hypothesis generates the
# awkward inputs (tiny, huge, many-decimal) automatically.
from hypothesis import given, strategies as st  # noqa: E402

_MASS_UNIT = st.sampled_from(units.MASS_UNITS)  # g, kg, lb, oz, mg
# realistic positive quantities at the app's 4-dp mass resolution, bounded in magnitude
_QTY = st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"),
                   places=4, allow_nan=False, allow_infinity=False)


@given(qty=_QTY, unit=_MASS_UNIT)
def test_mass_round_trip_is_lossless(qty, unit):
    # entry -> base (grams) -> back to entry unit reconstructs the original (within Decimal
    # context rounding). A wrong factor or bad arithmetic would blow this bound wide open.
    rt = units.from_base(units.to_base(qty, unit), unit)
    assert abs(rt - qty) <= (abs(qty) + 1) * Decimal("1e-12")


@given(qty=_QTY, pair=st.sampled_from([
    ("lbs", "lb"), ("pound", "lb"), ("pounds", "lb"), ("#", "lb"),
    ("grams", "g"), ("gram", "g"), ("gr", "g"),
    ("kgs", "kg"), ("kilogram", "kg"),
    ("ounce", "oz"), ("ounces", "oz"), ("milligram", "mg"),
]))
def test_aliases_convert_identically_to_canonical(qty, pair):
    # every spelling variant must resolve to the same grams as its canonical key
    alias, canon = pair
    assert units.to_base(qty, alias) == units.to_base(qty, canon)


@given(qty=_QTY, label=st.sampled_from(["tin", "sachet", "box", "each", "unit", "jar"]))
def test_count_units_are_identity(qty, label):
    # counts never convert: a 'tin' is a 'tin'. to_base/from_base must be the identity.
    assert units.to_base(qty, label) == qty
    assert units.from_base(qty, label) == qty


@given(qty=st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False),
       unit=_MASS_UNIT)
def test_float_storage_round_trip_within_tolerance(qty, unit):
    # Production stores float(to_base(...)) in the DB and reads it back later. Model that
    # float boundary and assert it doesn't drift meaningfully — this is the exact path whose
    # precision mismatch caused the "exactly enough reads as insufficient" bug.
    grams = float(units.to_base(qty, unit))
    back = float(units.from_base(Decimal(str(grams)), unit))
    assert abs(back - qty) <= max(qty, 1.0) * 1e-9
