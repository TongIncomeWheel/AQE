"""Earnings calendar — pull next earnings dates from FMP.

Pulls the FMP /stable/earnings-calendar endpoint, builds a JSON lookup
mapping ticker -> next earnings date. Used by Structure engine to compute
the earnings proximity score (Component 3G).

Scoring (from spec):
    <=5 days  -> 0.0  (EARNINGS WARNING)
    <=10 days -> 4.0
    <=20 days -> 7.0
    >20 days  -> 10.0  (or unknown)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from .fmp_client import FMPClient
from .paths import DATA_DIR, PROJECT_ROOT

EARNINGS_PATH = DATA_DIR / "earnings_calendar.json"

FMP_STABLE = "https://financialmodelingprep.com/stable"


def pull_earnings_calendar(
    client: FMPClient | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, str]:
    """Pull upcoming earnings dates from FMP. Returns {ticker: "YYYY-MM-DD"}.

    Uses 2 API calls: one for the next ~45 days and one for the 45 days after.
    This gives ~90 days of forward coverage with just 2 calls.
    """
    if client is None:
        client = FMPClient()

    today = date.today()
    if from_date is None:
        from_date = today
    if to_date is None:
        to_date = today + timedelta(days=90)

    url = f"{FMP_STABLE}/earnings-calendar"

    mid = from_date + timedelta(days=45)
    all_entries = []

    for start, end in [(from_date, mid), (mid + timedelta(days=1), to_date)]:
        params = {
            "from": start.strftime("%Y-%m-%d"),
            "to": end.strftime("%Y-%m-%d"),
            "apikey": client.config.api_key,
        }
        # 2026-09-05 bug fix: this used to call client._session.get() directly
        # and silently drop a non-2xx response (`if resp.ok:` with no else) --
        # no retry, no exception, no log line. A single transient 404/network
        # blip therefore made next_earnings_date/days_to_earnings null FOREVER
        # for that run with no trace of why. _get_json() is the same wrapper
        # every other FMP call in this codebase goes through: it retries
        # network errors, backs off on 429, and raises FMPError loudly on a
        # real failure -- "a failed data fetch must be LOUD" (CLAUDE.md).
        data = client._get_json(url, params=params)
        if isinstance(data, list):
            all_entries.extend(data)

    universe = _load_universe()

    result: dict[str, str] = {}
    for entry in all_entries:
        sym = entry.get("symbol", "")
        earn_date = entry.get("date", "")
        if sym not in universe or not earn_date:
            continue
        if sym not in result or earn_date < result[sym]:
            result[sym] = earn_date

    return result


def save_earnings(cal: dict[str, str]) -> Path:
    """Save earnings calendar to JSON."""
    payload = {
        "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(cal),
        "earnings": cal,
    }
    EARNINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EARNINGS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return EARNINGS_PATH


def load_earnings() -> dict[str, str]:
    """Load cached earnings calendar. Returns {ticker: "YYYY-MM-DD"}."""
    if not EARNINGS_PATH.exists():
        return {}
    data = json.loads(EARNINGS_PATH.read_text(encoding="utf-8"))
    return data.get("earnings", {})


def next_earnings_date(ticker: str, cal: dict[str, str]) -> str | None:
    """The raw "YYYY-MM-DD" next earnings date for a ticker, or None if
    unknown. `earn_score`/`days_to_earnings` only ever exposed the DERIVED
    proximity bucket/day-count -- every card's event window and catalyst rule
    needs the actual date (spec: docs/specs/aqe_voice_packet_spec_2026-09-05.md)."""
    return cal.get(ticker) or None


def days_to_earnings(ticker: str, as_of: date, cal: dict[str, str]) -> float | None:
    """Days until next earnings for a ticker. Returns None if unknown."""
    earn_str = cal.get(ticker)
    if not earn_str:
        return None
    try:
        earn_date = datetime.strptime(earn_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    delta = (earn_date - as_of).days
    if delta < 0:
        return None
    return float(delta)


def business_days_to_earnings(ticker: str, as_of: date, cal: dict[str, str]) -> int | None:
    """BUSINESS days (weekends excluded) to next earnings -- the export field
    `days_to_earnings` (spec: docs/specs/aqe_voice_packet_spec_2026-09-05.md).

    Deliberately separate from `days_to_earnings()` above: that one is
    CALENDAR days and feeds earn_proximity_score()'s frozen thresholds --
    changing its unit would silently re-rate every existing score."""
    import numpy as np

    earn_str = cal.get(ticker)
    if not earn_str:
        return None
    try:
        earn_date = datetime.strptime(earn_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    if earn_date < as_of:
        return None
    return int(np.busday_count(as_of, earn_date))


def earn_proximity_score(days: float | None) -> float:
    """Earnings proximity score (Component 3G). Max 10.0."""
    if days is None:
        return 10.0
    if days <= 5:
        return 0.0
    if days <= 10:
        return 4.0
    if days <= 20:
        return 7.0
    return 10.0


def build_earnings_series(
    dates: pd.Series,
    ticker: str,
    cal: dict[str, str],
) -> pd.Series:
    """Build a Series of earn_score values aligned to a date index."""
    scores = []
    for d in dates:
        if isinstance(d, pd.Timestamp):
            d = d.date()
        days = days_to_earnings(ticker, d, cal)
        scores.append(earn_proximity_score(days))
    return pd.Series(scores, index=dates.index, dtype=float)


def _load_universe() -> set[str]:
    """Load universe tickers for filtering (strips comments and blanks)."""
    path = DATA_DIR / "universe.txt"
    if not path.exists():
        return set()
    tickers: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            tickers.add(line.upper())
    return tickers


if __name__ == "__main__":
    print("Pulling earnings calendar from FMP...")
    cal = pull_earnings_calendar()
    path = save_earnings(cal)
    print(f"Saved {len(cal)} tickers to {path}")
    for ticker in ["NVDA", "AAPL", "MSFT", "TSLA", "META"]:
        earn = cal.get(ticker, "unknown")
        today = date.today()
        if earn != "unknown":
            days = days_to_earnings(ticker, today, cal)
            score = earn_proximity_score(days)
            print(f"  {ticker}: {earn} ({days:.0f} days away, score={score:.1f})")
        else:
            print(f"  {ticker}: no earnings date found")
