# ADDED: units-conversion-layer feature — new test file covering services/units.py.
#        Pure logic, no DB/server needed. Run directly: python test_scripts/test_units.py
"""Tests for the unit-of-measurement conversion layer (services/units.py)."""

import os
import sys
from decimal import Decimal

# Make the project root importable when run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import units

passed = 0
failed = 0
failures = []


def check(label, ok, msg=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS     {label}")
    else:
        failed += 1
        failures.append(label)
        print(f"  FAIL     {label}: {msg}")


print("\n" + "=" * 60)
print("UNIT CONVERSION TESTS")
print("=" * 60)

# ── dimension classification ────────────────────────────────────────────────
check("g/kg/lb/oz/mg are mass",
      all(units.dimension_of(u) == "mass" for u in ("g", "kg", "lb", "oz", "mg")))
check("aliases (lbs, grams, pounds) resolve to mass",
      all(units.dimension_of(u) == "mass" for u in ("lbs", "grams", "pounds", "kgs")))
check("unknown labels (tin, sachet, each) are count",
      all(units.dimension_of(u) == "count" for u in ("tin", "sachet", "each", "unit")))
check("classification ignores case/whitespace",
      units.dimension_of("  LB ") == "mass")

# ── to_base (entry -> grams) is exact ───────────────────────────────────────
check("2 g -> 2 g", units.to_base(2, "g") == Decimal("2"))
check("1 lb -> 453.59237 g (exact)", units.to_base(1, "lb") == Decimal("453.59237"))
check("1 kg -> 1000 g", units.to_base(1, "kg") == Decimal("1000"))
check("16 oz -> 1 lb worth of grams", units.to_base(16, "oz") == units.to_base(1, "lb"))
check("to_base on a count unit is identity", units.to_base(12, "tin") == Decimal("12"))
check("float input does not leak noise (0.1 g)",
      units.to_base(0.1, "g") == Decimal("0.1"))

# ── from_base (grams -> display) round-trips ────────────────────────────────
check("453.59237 g -> 1 lb", units.from_base(Decimal("453.59237"), "lb") == Decimal("1"))
check("1000 g -> 1 kg", units.from_base(Decimal("1000"), "kg") == Decimal("1"))
check("from_base count identity", units.from_base(Decimal("7"), "sachet") == Decimal("7"))

# ── round-trip: enter -> base -> display returns the original ───────────────
for amount, unit in [(2, "g"), (3.5, "lb"), (0.25, "kg"), (8, "oz")]:
    base = units.to_base(amount, unit)
    back = units.from_base(base, unit)
    check(f"round-trip {amount} {unit}", back == Decimal(str(amount)),
          f"got {back}")

# ── convert across same dimension; reject across dimensions ─────────────────
check("convert 1000 g -> 1 kg", units.convert(1000, "g", "kg") == Decimal("1"))
check("convert 1 lb -> 453.59237 g", units.convert(1, "lb", "g") == Decimal("453.59237"))

raised = False
try:
    units.convert(5, "g", "tin")  # mass -> count must fail
except ValueError:
    raised = True
check("convert across dimensions raises ValueError", raised)

# ── precision: the bug this feature fixes ──────────────────────────────────
# Old pain: storing in lb made "2 g" become 0.00440924524 lb, then 50 lb - that
# spewed float noise. In grams everything is exact.
remaining = units.to_base(1, "lb") - units.to_base(2, "g")  # 453.59237 - 2
check("gram-based deduction stays exact (no float spew)",
      remaining == Decimal("451.59237"), f"got {remaining}")

# ── SUMMARY ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
total = passed + failed
print(f"  PASSED: {passed} / {total}")
print(f"  FAILED: {failed} / {total}")
if failures:
    print("\n  FAILURES:")
    for f in failures:
        print(f"    - {f}")
    sys.exit(1)
else:
    print("\n  All unit-conversion tests passed.")
