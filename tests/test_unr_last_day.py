"""The U&R COLUMN on the daily AQE export (PM 2026-10-12): for each Longlist /
Elder name, did an undercut and rally happen on the last completed trading day?"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.valen import setups_daily as SD


def _panel(ticker, n=170, last=None, a=40.0, b=100.0):
    """Rising chart; `last` overrides the final bar as fractions of the EMA21 as of
    the bar before it: (low_frac, close_frac)."""
    c = np.geomspace(a, b, n)
    rows = []
    for i in range(n):
        rows.append({"ticker": ticker, "date": pd.Timestamp(date(2026, 10, 9) - timedelta(days=n - 1 - i)),
                     "open": c[i] * 0.998, "high": c[i] * 1.006, "low": c[i] * 0.994,
                     "close": float(c[i]), "volume": 1e6})
    df = pd.DataFrame(rows)
    if last:
        e = float(df["close"].iloc[:-1].ewm(span=21, adjust=False).mean().iloc[-1])
        df.loc[df.index[-1], ["low", "close", "high"]] = [e * last[0], e * last[1], e * max(last[1], 1.0) * 1.003]
    return df


def _rows(*names, longlist=True):
    return [{"ticker": n, "on_longlist": longlist, "on_elder": False} for n in names]


def test_met_when_the_last_session_undercut_a_level_and_closed_back_above():
    out = SD.unr_last_day(_panel("MET", last=(0.985, 1.012)), _rows("MET"))["MET"]
    assert out["unr_status"] == "MET" and out["unr_level"] is not None
    assert "closed back above it. Reclaim day." in out["unr_note"]
    assert out["unr_as_of"] == "2026-10-09"


def test_setup_when_it_closed_the_last_session_still_under_the_level():
    out = SD.unr_last_day(_panel("SET", last=(0.985, 0.995)), _rows("SET"))["SET"]
    assert out["unr_status"] == "SETUP"
    assert "The reclaim day is the next session." in out["unr_note"]


def test_no_when_nothing_was_undercut():
    out = SD.unr_last_day(_panel("NO", last=(1.06, 1.08)), _rows("NO"))["NO"]
    assert out["unr_status"] == "NO" and out["unr_level"] is None


def test_na_never_a_silent_no_when_there_is_too_little_history():
    out = SD.unr_last_day(_panel("NA", n=40), _rows("NA"))["NA"]
    assert out["unr_status"] == "NA" and "not enough daily price history" in out["unr_note"]


def test_a_breakdown_is_not_met():
    out = SD.unr_last_day(_panel("BRK", last=(0.90, 1.01)), _rows("BRK"))["BRK"]
    assert out["unr_status"] == "NO"                     # a 10% flush is not a shallow dip


def test_a_ticker_absent_from_the_panel_is_absent_not_no():
    assert "ZZZ" not in SD.unr_last_day(_panel("AAA"), _rows("AAA", "ZZZ"))


def test_summary_counts_longlist_and_elder_names_only():
    rows = [{"ticker": "A", "on_longlist": True, "unr_status": "MET", "unr_as_of": "2026-10-09"},
            {"ticker": "B", "on_elder": True, "unr_status": "SETUP", "unr_as_of": "2026-10-09"},
            {"ticker": "C", "on_longlist": True, "unr_status": "NO", "unr_as_of": "2026-10-09"},
            {"ticker": "D", "on_longlist": True, "unr_status": "NA", "unr_as_of": "2026-10-09"},
            {"ticker": "E", "unr_status": "MET", "unr_as_of": "2026-10-09"}]      # on neither list
    s = SD.unr_summary(rows)
    assert s == {"as_of": "2026-10-09",
                 "basis": "last completed trading day, Longlist + Elder names",
                 "met": ["A"], "setup": ["B"], "n_checked": 3, "n_not_checked": 1}


def test_attach_stamps_the_columns_on_rows_and_held_and_reports_how_many():
    panel = pd.concat([_panel("MET", last=(0.985, 1.012)), _panel("NO", last=(1.06, 1.08))])
    dl = _rows("MET", "NO")
    held = [{"ticker": "MET"}]
    status = SD.attach_setup_grades(dl, held, panel=panel, valen={}, earnings={})
    assert status["status"] == "live" and status["unr_graded"] == 2
    assert dl[0]["unr_status"] == "MET" and dl[1]["unr_status"] == "NO"
    assert held[0]["unr_status"] == "MET"
    assert {"unr_status", "unr_note", "unr_as_of", "unr_level"} <= set(dl[0])


def test_a_failure_in_the_column_never_takes_the_setups_down(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(SD, "unr_last_day", boom)
    dl = _rows("MET")
    status = SD.attach_setup_grades(dl, [], panel=_panel("MET", last=(0.985, 1.012)),
                                    valen={}, earnings={})
    assert status["status"] == "live" and "unr_status" not in dl[0]
