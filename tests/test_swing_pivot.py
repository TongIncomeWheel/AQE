"""Momentum at the pivot (PM 2026-11-05): swing_pivot / swing_atr_dist on every export row, from the panel and mtf.py's own swing code.
The band edge ATR_NEAR lives in card_extras.py only; these tests prove a name inside and a name outside the band are told apart by ATR
(not by percent), that unreadable is None (never a silent False), and that a failure is loud."""
import datetime as dt
import math

import pandas as pd

from src.valen import swing_pivot as SP

RUN = "2027-03-31"


def _bars(n=300, trend=0.1, amp=5.0, end="2027-03-30"):
    """A rising zig-zag on weekdays ending at `end`: higher highs and higher lows on both the daily and the weekly frame."""
    days, d = [], dt.date.fromisoformat(end)
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= dt.timedelta(days=1)
    days.reverse()
    out = []
    for i, d in enumerate(days):
        c = 100 + trend * i + amp * math.sin(i / 6)
        out.append({"date": d.isoformat(), "open": c, "high": c + 0.5, "low": c - 0.5, "close": c, "volume": 1e6})
    return out


def test_the_trend_series_is_weekly_and_daily_hh_hl_and_has_a_swing_high():
    r = SP.read_one(_bars(), 1.0, RUN)
    assert r["swing_weekly"] == "HH/HL" and r["swing_daily"] == "HH/HL"
    assert r["swing_high"] and r["swing_high_date"] and r["swing_atr_dist"] is not None


def test_the_same_distance_is_inside_or_outside_the_band_by_atr_not_by_percent():
    bars = _bars()
    base = SP.read_one(bars, 1.0, RUN)
    dist_price = base["swing_atr_dist"] * 1.0                       # the close minus the swing high, in price (atr 1.0)
    assert abs(dist_price) > 0.05
    calm = SP.read_one(bars, abs(dist_price) * 2.0, RUN)             # 0.5 ATR from the swing high -> at the pivot
    wild = SP.read_one(bars, abs(dist_price) / 3.0, RUN)             # 3 ATR from it -> outside
    assert abs(calm["swing_atr_dist"]) == 0.5 and calm["swing_pivot"] is True
    assert abs(wild["swing_atr_dist"]) == 3.0 and wild["swing_pivot"] is False
    assert calm["swing_high"] == wild["swing_high"]                  # the price distance is identical in both


def test_the_band_edge_is_read_from_card_extras_not_hard_wired(monkeypatch):
    bars = _bars()
    d = abs(SP.read_one(bars, 1.0, RUN)["swing_atr_dist"])
    atr = d / 1.5                                                     # exactly 1.5 ATR away: outside the default 1.0
    assert SP.read_one(bars, atr, RUN)["swing_pivot"] is False
    cx = SP._load("card_extras")
    monkeypatch.setattr(cx, "ATR_NEAR", 2.0)
    assert SP.read_one(bars, atr, RUN)["swing_pivot"] is True


def test_a_downtrend_or_missing_atr_or_short_history_is_not_a_pivot_and_says_so():
    down = [dict(b, high=300 - b["high"], low=300 - b["low"] - 1, close=300 - b["close"]) for b in _bars()]
    r = SP.read_one(down, 1.0, RUN)
    assert r["swing_pivot"] is False                                  # readable, not HH/HL
    assert SP.read_one(_bars(), None, RUN)["swing_pivot"] is None     # no ATR: unreadable, never a silent False
    assert SP.read_one(_bars(), 0, RUN)["swing_pivot"] is None
    short = SP.read_one(_bars(10), 1.0, RUN)
    assert short["swing_pivot"] is None and "bars" in short["swing_note"]


def test_attach_stamps_every_row_and_reports_the_names_at_the_pivot():
    bars = _bars()
    base = SP.read_one(bars, 1.0, RUN)
    d = abs(base["swing_atr_dist"])
    panel = pd.DataFrame([dict(b, ticker=t) for t in ("INSIDE", "OUTSIDE") for b in bars])
    rows = [{"ticker": "INSIDE", "atr_14d": d * 2.0}, {"ticker": "OUTSIDE", "atr_14d": d / 3.0}, {"ticker": "GHOST", "atr_14d": 1.0}]
    st = SP.attach_swing_pivot(rows, None, panel=panel, run_date=RUN)
    assert st["status"] == "live" and st["at_the_pivot_names"] == ["INSIDE"] and st["atr_near"] == 1.0
    assert rows[0]["swing_pivot"] is True and rows[1]["swing_pivot"] is False
    assert rows[2]["swing_pivot"] is None and "panel" in rows[2]["swing_note"]
    assert st["unreadable"] == ["GHOST"]


def test_a_failed_read_is_loud_never_an_empty_column():
    rows = [{"ticker": "X", "atr_14d": 1.0}]
    st = SP.attach_swing_pivot(rows, None, panel="not a dataframe", run_date=RUN)
    assert st["status"] == "error" and st["reason"] and st["stamped"] == 0
