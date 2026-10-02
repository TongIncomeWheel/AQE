"""VALEN "as of N sessions ago" recompute — turning-point reads.

A PM ask (2026-10-01): the dashboard shows today's weather but not whether
it is TURNING — was the stance different 5 trading sessions (~1 week) or
21 sessions (~1 month) ago? trend.py/extension.py/breadth.py are each a
pure function of a price panel that already carries full history, and
stance.compute_stance() is itself a pure function of those three dicts' —
so a historical reading needs no new storage, no backfill job, and no
cold-start gap: it is the exact same compute path, run once more against
a truncated copy of the SAME panel already read for today's number.

GEX is the one Weather instrument this CANNOT cover: Crown's gamma read is
a snapshot of TODAY's options open interest, which is not retained day to
day, so there is no panel to truncate. GEX is left out of history on
purpose (see daily.py) rather than faked from something that isn't there.
"""

from __future__ import annotations

import pandas as pd

SESSIONS_AGO = {"1d_ago": 1, "5d_ago": 5, "1mo_ago": 21}


def truncate_series(closes: pd.Series, sessions_ago: int) -> pd.Series:
    """Drop the most recent `sessions_ago` bars from a date-sorted series
    (oldest first, as trend.py's `_closes_for` returns). Empty (not an
    exception) when there isn't enough history for the cut — callers
    already degrade an empty series to UNAVAILABLE."""
    if closes is None or sessions_ago <= 0:
        return closes
    if len(closes) <= sessions_ago:
        return closes.iloc[0:0]
    return closes.iloc[:-sessions_ago]


def truncate_panel(panel: pd.DataFrame | None, sessions_ago: int,
                   date_col: str = "date") -> pd.DataFrame | None:
    """Rows as of `sessions_ago` trading sessions before the panel's own
    latest date — i.e. drop the most recent `sessions_ago` distinct dates
    across every ticker in the panel at once. None when there isn't enough
    history for the cut, same "honest absence" convention every compute_*
    function here already uses for a too-short panel."""
    if panel is None or panel.empty or sessions_ago <= 0:
        return panel
    dates = pd.to_datetime(panel[date_col]).drop_duplicates().sort_values()
    if len(dates) <= sessions_ago:
        return None
    cutoff = dates.iloc[-(sessions_ago + 1)]
    df = panel.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    return df[df[date_col] <= cutoff]
