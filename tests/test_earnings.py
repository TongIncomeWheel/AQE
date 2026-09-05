"""Tests for src/data/earnings.py.

2026-09-05 incident (docs/specs/aqe_voice_packet_spec_2026-09-05.md §2):
pull_earnings_calendar() used to call client._session.get() directly and
silently drop a non-2xx response (`if resp.ok:` with no else) -- no retry, no
exception, no log line. A single transient network blip made
next_earnings_date/days_to_earnings null FOREVER for that day's run with no
trace of why. It must now go through client._get_json() -- the same retrying,
loudly-failing wrapper every other FMP call in this codebase uses."""

from __future__ import annotations

from datetime import date

import pytest

from src.data import earnings as E


# ── pull_earnings_calendar — must use the shared retrying/loud FMP wrapper ──

class _FakeConfig:
    api_key = "test-key"


class _FakeClient:
    def __init__(self, pages):
        self.config = _FakeConfig()
        self._pages = pages
        self.calls = []

    def _get_json(self, url, params):
        self.calls.append((url, params))
        return self._pages.pop(0)


def test_pull_earnings_calendar_uses_get_json_not_raw_session(monkeypatch):
    """The fix: two _get_json calls (one per 45-day half), not client._session.get."""
    monkeypatch.setattr(E, "_load_universe", lambda: {"AAPL", "MSFT"})
    client = _FakeClient([
        [{"symbol": "AAPL", "date": "2026-09-10"}],
        [{"symbol": "MSFT", "date": "2026-09-20"}],
    ])
    result = E.pull_earnings_calendar(client=client)
    assert result == {"AAPL": "2026-09-10", "MSFT": "2026-09-20"}
    assert len(client.calls) == 2
    assert client.calls[0][0] == f"{E.FMP_STABLE}/earnings-calendar"


def test_pull_earnings_calendar_propagates_a_failure_loudly(monkeypatch):
    """A failed fetch must be LOUD (CLAUDE.md), never silently empty. Since
    _get_json() raises FMPError on a real failure, that exception must reach
    the caller -- daily_orchestrator's own try/except is what turns this into
    a WARN + fallback to the last cached calendar, not this function."""
    from src.data.fmp_client import FMPError

    class _BoomClient:
        config = _FakeConfig()

        def _get_json(self, url, params):
            raise FMPError("FMP HTTP 404 for .../earnings-calendar: not found")

    monkeypatch.setattr(E, "_load_universe", lambda: {"AAPL"})
    with pytest.raises(FMPError):
        E.pull_earnings_calendar(client=_BoomClient())


def test_pull_earnings_calendar_filters_to_the_universe_and_keeps_earliest_date(monkeypatch):
    monkeypatch.setattr(E, "_load_universe", lambda: {"AAPL"})
    client = _FakeClient([
        [{"symbol": "AAPL", "date": "2026-09-20"}, {"symbol": "TSLA", "date": "2026-09-05"}],
        [{"symbol": "AAPL", "date": "2026-09-10"}],
    ])
    result = E.pull_earnings_calendar(client=client)
    assert result == {"AAPL": "2026-09-10"}, "TSLA (not in universe) excluded; earliest AAPL date kept"


# ── next_earnings_date ──────────────────────────────────────────────────────

def test_next_earnings_date_returns_the_cached_raw_date():
    cal = {"AAPL": "2026-09-10"}
    assert E.next_earnings_date("AAPL", cal) == "2026-09-10"


def test_next_earnings_date_is_none_for_an_unknown_ticker():
    assert E.next_earnings_date("ZZZZ", {}) is None


# ── business_days_to_earnings (the export's days_to_earnings field) ────────

def test_business_days_to_earnings_excludes_weekends():
    cal = {"AAPL": "2026-09-10"}   # a Thursday
    got = E.business_days_to_earnings("AAPL", date(2026, 9, 5), cal)  # a Saturday
    import numpy as np
    expected = int(np.busday_count(date(2026, 9, 5), date(2026, 9, 10)))
    assert got == expected


def test_business_days_to_earnings_is_none_for_a_past_date():
    """A stale cached date must never read as 'next' -- None, not a negative
    count."""
    cal = {"AAPL": "2026-05-28"}
    assert E.business_days_to_earnings("AAPL", date(2026, 9, 5), cal) is None


def test_business_days_to_earnings_is_none_for_an_unknown_ticker():
    assert E.business_days_to_earnings("ZZZZ", date(2026, 9, 5), {}) is None


def test_business_days_to_earnings_is_a_different_unit_from_the_calendar_day_version():
    """days_to_earnings() (calendar days, feeds earn_proximity_score's frozen
    thresholds) and business_days_to_earnings() (the new export field) must
    stay independently computable -- changing one's unit must never silently
    reach the other."""
    cal = {"AAPL": "2026-09-14"}   # a Monday, 9 calendar days from Sat 9/5
    as_of = date(2026, 9, 5)
    calendar_days = E.days_to_earnings("AAPL", as_of, cal)
    business_days = E.business_days_to_earnings("AAPL", as_of, cal)
    assert calendar_days == 9.0
    assert business_days != calendar_days
    assert business_days == 5   # two weekends (9/6-9/7, 9/12-9/13) excluded
