"""Tests for config.py's business_today()/business_now() — the fix for the server-timezone-vs-
business-timezone bug (Render runs UTC, Botaniks runs Pacific).

The regression these guard: a bare `datetime.now().date()` returns the SERVER's calendar date.
For several hours every evening Pacific time, UTC has already rolled over to the next calendar
day, so a naive comparison reports "today" as already tomorrow. business_today()/business_now()
must return Pacific's actual day regardless of what timezone the process happens to run in.

Uses the shared `freeze_business_time` fixture (conftest.py) rather than its own frozen-clock
class, so every test file that needs to exercise this bug freezes time the same way.
"""

from datetime import datetime, date
from zoneinfo import ZoneInfo

import config


def test_business_today_uses_pacific_day_not_utc_day(freeze_business_time):
    # 2026-01-02 06:00 UTC = 2026-01-01 22:00 PST (Pacific is UTC-8 in January, no DST).
    # A bare datetime.now().date() at this instant would report 2026-01-02 (UTC's day) —
    # exactly the bug: Pacific's evening of Jan 1 read as if it were already Jan 2.
    freeze_business_time(datetime(2026, 1, 2, 6, 0, 0, tzinfo=ZoneInfo("UTC")))
    assert config.business_today() == date(2026, 1, 1)


def test_business_today_matches_utc_day_when_they_agree(freeze_business_time):
    # Midday UTC is evening-before in Pacific by less than a day, so the calendar day still
    # matches — sanity check that the fix doesn't shift dates when there's no discrepancy.
    freeze_business_time(datetime(2026, 1, 1, 20, 0, 0, tzinfo=ZoneInfo("UTC")))
    assert config.business_today() == date(2026, 1, 1)


def test_business_now_is_naive_and_in_pacific_time(freeze_business_time):
    freeze_business_time(datetime(2026, 1, 2, 6, 30, 0, tzinfo=ZoneInfo("UTC")))
    now = config.business_now()
    assert now.tzinfo is None
    assert (now.year, now.month, now.day, now.hour, now.minute) == (2026, 1, 1, 22, 30)


def test_business_tz_is_pacific():
    assert config.BUSINESS_TZ.key == "America/Los_Angeles"
