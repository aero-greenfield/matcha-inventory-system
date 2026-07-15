"""Smoke test: confirm the app actually boots and /health responds.

Catches import-time failures (bad syntax in a route, a broken top-level import) that the
pytest suite's fixtures can mask because they run through an already-working app. Run manually
with `python scripts/smoke_test.py`, or via the pre-push hook in hooks/pre-push.

Uses the same isolation model as test_scripts/conftest.py: a throwaway SQLite file in a temp
dir, never data/inventory.db. Env vars must be set before `app` (or anything under services/)
is imported, since those modules read them at import time.
"""

import os
import sys
import tempfile

os.environ.setdefault("SECRET_KEY", "smoke-test-secret-key")
os.environ["AUTH_USERNAME"] = "smoketest"
os.environ["AUTH_PASSWORD"] = "smoketest"
os.environ.pop("DATABASE_URL", None)  # force SQLite mode

_tmp_dir = tempfile.mkdtemp(prefix="matcha-smoke-")
os.environ["SQLITE_PATH"] = os.path.join(_tmp_dir, "smoke_inventory.db")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def main():
    try:
        import app as app_module
    except Exception as exc:
        print(f"[SMOKE TEST FAILED] app failed to import: {exc}")
        return 1

    client = app_module.app.test_client()
    response = client.get("/health")
    if response.status_code != 200:
        print(f"[SMOKE TEST FAILED] /health returned {response.status_code}: {response.get_data(as_text=True)}")
        return 1

    print("[SMOKE TEST PASSED] app imports cleanly and /health returns 200")
    return 0


if __name__ == "__main__":
    sys.exit(main())
