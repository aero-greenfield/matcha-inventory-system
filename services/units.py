# ADDED: units-conversion-layer feature — this whole module is new for the
#        unit-of-measurement + conversion work. See plan
#        ".claude/plans/what-would-be-the-ethereal-marble.md".
"""Unit-of-measurement conversion layer.

Single source of truth for how the app converts between the units people type
(grams, pounds, ounces, ...) and the canonical base unit each quantity is
*stored* in. Storing in one base unit per dimension is what kills the
float-precision noise: a recipe's "2 g" is an exact short decimal, whereas the
same amount expressed in pounds (0.00440924524...) is a repeating fraction that
float arithmetic mangles.

Two dimensions only (see CLAUDE.md decision: mass + counts, no volume):

- ``mass``  -> base unit ``g`` (grams). lb/oz/kg/mg convert with exact factors.
- ``count`` -> base unit ``each``. Counts never convert across labels: a "tin"
  and a "sachet" are different *materials*, not convertible units, so every
  count conversion is the identity.

All math uses ``decimal.Decimal`` so conversions are exact (the mass factors are
all finite decimals). This module is pure logic — it imports no Flask and
touches no database, matching the rest of ``services/``.
"""

from decimal import Decimal

# ADDED: units-conversion-layer feature — canonical base units per dimension.
MASS_BASE = "g"
COUNT_BASE = "each"

# ADDED: units-conversion-layer feature — canonical mass unit -> exact factor to
# grams. Every factor is a finite decimal, so Decimal multiplication stays exact
# (1 lb == 453.59237 g exactly).
_MASS_FACTORS = {
    "g": Decimal("1"),
    "kg": Decimal("1000"),
    "mg": Decimal("0.001"),
    "lb": Decimal("453.59237"),       # exact by definition
    "oz": Decimal("28.349523125"),    # exact (1 lb / 16)
}

# ADDED: units-conversion-layer feature — spelling variants accepted from forms
# -> canonical key above.
_ALIASES = {
    "gram": "g", "grams": "g", "gr": "g",
    "kilogram": "kg", "kilograms": "kg", "kgs": "kg",
    "milligram": "mg", "milligrams": "mg",
    "lbs": "lb", "pound": "lb", "pounds": "lb", "#": "lb",
    "ounce": "oz", "ounces": "oz",
}

# ADDED: units-conversion-layer feature — mass units offered in entry dropdowns,
# friendliest-first.
MASS_UNITS = ("g", "kg", "lb", "oz", "mg")


# ADDED: units-conversion-layer feature — everything below is new for this feature.
def _canon(unit):
    """Normalize a unit string to its canonical key (lowercased, alias-resolved)."""
    if unit is None:
        raise ValueError("unit is required")
    u = str(unit).strip().lower()
    return _ALIASES.get(u, u)


def _dec(qty):
    """Coerce qty to Decimal without inheriting float noise (route through str)."""
    if isinstance(qty, Decimal):
        return qty
    return Decimal(str(qty))


def dimension_of(unit):
    """'mass' for known mass units (and their aliases), else 'count'.

    Count units are open-ended labels (tin, sachet, ...), so anything not in the
    mass registry is treated as a count unit."""
    return "mass" if _canon(unit) in _MASS_FACTORS else "count"


def to_base(qty, unit):
    """Convert an entered quantity into its stored base unit, as Decimal.

    Mass -> grams; count -> unchanged (identity)."""
    q = _dec(qty)
    if dimension_of(unit) == "mass":
        return q * _MASS_FACTORS[_canon(unit)]
    return q


def from_base(qty, unit):
    """Convert a stored base-unit quantity back into `unit`, as Decimal.

    Mass: grams / factor; count: unchanged. The result may have many decimal
    places (e.g. grams -> lb); callers round for display."""
    q = _dec(qty)
    if dimension_of(unit) == "mass":
        return q / _MASS_FACTORS[_canon(unit)]
    return q


def convert(qty, from_unit, to_unit):
    """Convert between two units of the same dimension. Raises ValueError if the
    dimensions differ (e.g. grams -> tins) — counts are not convertible to mass."""
    from_dim = dimension_of(from_unit)
    to_dim = dimension_of(to_unit)
    if from_dim != to_dim:
        raise ValueError(
            f"cannot convert {from_dim} unit '{from_unit}' to {to_dim} unit '{to_unit}'"
        )
    if from_dim == "count":
        # Counts only "convert" within the same label; treat as identity.
        return _dec(qty)
    return from_base(to_base(qty, from_unit), to_unit)
