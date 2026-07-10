"""
Single source of truth for values that must not vary by where this process happens to run.

BUG THIS FIXES: Render runs the server in UTC; Botaniks operates in US/Pacific. Every place in the
app that decided whether a Planned batch's date was "today", "the past", or "overdue" used to
compare the browser's plain, timezone-less YYYY-MM-DD date input against the SERVER's
datetime.now() — i.e. UTC. Pacific is 7-8 hours behind UTC, so for several hours every evening the
server's UTC calendar date was already a day ahead of Pacific's, causing two bugs: submitting
"today" (Pacific) was rejected as being in the past, and submitting "tomorrow" (Pacific) caused a
Planned batch to promote to Ready immediately, because the server's UTC clock already considered
that date to be today-or-earlier.

Use business_today()/business_now() everywhere a date is judged against "today" (planned-batch
validation, promotion overdue cutoff, lot-expiration checks) instead of bare datetime.now().
"""

from datetime import datetime
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo("America/Los_Angeles")


def business_today():
    """Today's calendar date where Botaniks operates — not the server's."""
    return datetime.now(BUSINESS_TZ).date()


def business_now():
    """Business-timezone 'now' as a naive datetime, for building 'YYYY-MM-DD HH:MM:SS' strings
    the same way the rest of the app already does (see module docstring for why)."""
    return datetime.now(BUSINESS_TZ).replace(tzinfo=None)
