"""US equity session helpers - the one definition of 'the last COMPLETED session' every freshness guard uses.

A guard that compares a data leg's date to 'today' lets a leg that is one session behind pass (2026-11-03: the whole-market
breadth stamped 30 Oct was read as fresh on the morning that needed 2 Nov). The right yardstick is the last session whose
close has already printed, which depends on the New York clock and the exchange holidays.
"""
from __future__ import annotations

from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

NY = ZoneInfo("America/New_York")
CLOSE_PRINTED_AFTER = dtime(16, 30)      # regular close 16:00 ET; official closes are final shortly after

# NYSE full-day holidays (observed dates). EXTEND EVERY YEAR: a year with no entry here falls back to weekdays only and
# says so (holidays_known() is False), so a missing year is a visible downgrade, never a silent one.
NYSE_HOLIDAYS = {
    2026: ["2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03",
           "2026-09-07", "2026-11-26", "2026-12-25"],
    2027: ["2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05",
           "2027-09-06", "2027-11-25", "2027-12-24"],
}
_ALL = sorted(d for v in NYSE_HOLIDAYS.values() for d in v)


def holidays_known(d: date) -> bool:
    return d.year in NYSE_HOLIDAYS


def is_session(d: date) -> bool:
    return bool(np.is_busday(np.datetime64(d), holidays=_ALL))


def previous_session(d: date) -> date:
    """The last session strictly before d."""
    d = d - timedelta(days=1)
    while not is_session(d):
        d -= timedelta(days=1)
    return d


def last_completed_session(now: datetime | None = None) -> date:
    """The most recent US session whose close has printed, as of `now` (default: the current instant)."""
    now = (now or datetime.now(NY)).astimezone(NY)
    d = now.date()
    if is_session(d) and now.time() >= CLOSE_PRINTED_AFTER:
        return d
    return previous_session(d)
