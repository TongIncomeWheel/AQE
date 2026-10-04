"""Tests for the live (provisional) Elder read -- src/alerts/live_elder.py
and condition_data.ensure_daily_history (PM ask 2026-10-04)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.alerts import condition_data as CD
from src.alerts import live_elder as LE
from src.engines import elder as EL


def _series(n=120, drift=0.004, seed=1):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.cumprod(1 + drift + rng.normal(0, 0.01, n))
    dates = pd.bdate_range("2026-01-02", periods=n)
    return pd.DataFrame({"date": dates, "open": close, "high": close * 1.01,
                         "low": close * 0.99, "close": close, "volume": 1e6})


def test_live_price_equal_to_the_close_reproduces_the_nightly_score():
    """The identity that makes this honest: with no price change the live
    read IS the nightly engine's own number."""
    d = _series()
    hist, last = d.iloc[:-1], d.iloc[-1]
    truth = EL.compute(d)["elder_score"].iloc[-1]
    live = LE.elder_live(hist, float(last["close"]), last["date"])
    assert live["elder_live"] == int(round(truth))
    assert live["impulse_live"] in ("GREEN", "NEUTRAL", "RED")


def test_a_higher_live_price_never_reads_lower_than_a_lower_one():
    d = _series(drift=0.0, seed=3)
    hist, last = d.iloc[:-1], d.iloc[-1]
    lo = LE.elder_live(hist, float(last["close"]) * 0.96, last["date"])["elder_live"]
    hi = LE.elder_live(hist, float(last["close"]) * 1.04, last["date"])["elder_live"]
    assert hi >= lo


def test_prev_is_the_last_completed_session_from_the_same_series():
    d = _series()
    hist, last = d.iloc[:-1], d.iloc[-1]
    live = LE.elder_live(hist, float(last["close"]), last["date"])
    assert live["elder_prev"] == int(round(EL.compute(hist)["elder_score"].iloc[-1]))


def test_history_already_ending_today_is_replaced_not_duplicated():
    d = _series()
    today = d["date"].iloc[-1]
    frame = LE.provisional_frame(d, 999.0, today)
    assert len(frame) == len(d)
    assert frame["close"].iloc[-1] == 999.0


def test_short_history_or_missing_price_is_null_not_a_guess():
    d = _series(n=20)
    assert LE.elder_live(d, 100.0, d["date"].iloc[-1])["elder_live"] is None
    assert LE.elder_live(_series(), None, date(2026, 6, 1))["elder_live"] is None
    assert LE.elder_live(None, 100.0, date(2026, 6, 1))["elder_live"] is None


# ---------------------------------------------- ensure_daily_history

class _Client:
    def __init__(self):
        self.calls = []

    def get_daily_bars(self, ticker, from_date=None, to_date=None):
        self.calls.append(ticker)
        return _series(n=60)


def test_daily_history_is_pulled_once_then_served_from_the_day_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(CD, "DAILY_HISTORY_DIR", tmp_path / "dh")
    monkeypatch.setattr(CD, "_panel_history", lambda tickers, today: {})   # stale/absent panel
    c = _Client()
    out = CD.ensure_daily_history(c, ["AAA", "BBB"], date(2026, 10, 2))
    assert set(out) == {"AAA", "BBB"} and len(out["AAA"]) == 60
    assert c.calls == ["AAA", "BBB"]
    out2 = CD.ensure_daily_history(c, ["AAA", "BBB"], date(2026, 10, 2))
    assert c.calls == ["AAA", "BBB"]          # no second pull
    assert out2 == out


def test_a_fresh_panel_is_used_and_fmp_is_not_called(tmp_path, monkeypatch):
    monkeypatch.setattr(CD, "DAILY_HISTORY_DIR", tmp_path / "dh")
    monkeypatch.setattr(CD, "_panel_history",
                        lambda tickers, today: {t: [{"date": "2026-10-01", "open": 1, "high": 1,
                                                     "low": 1, "close": 1, "volume": 1}]
                                                for t in tickers})
    c = _Client()
    out = CD.ensure_daily_history(c, ["AAA"], date(2026, 10, 2))
    assert out["AAA"][0]["date"] == "2026-10-01"
    assert c.calls == []


def test_a_stale_panel_is_rejected_on_recency_not_length(monkeypatch, tmp_path):
    """A panel that stopped a month ago still has thousands of rows -- it
    must lose to the network on recency, the heartbeat lesson."""
    import pandas as pd
    stale = pd.DataFrame({"ticker": ["AAA"] * 300,
                          "date": pd.bdate_range("2025-06-01", periods=300),
                          "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0})
    p = tmp_path / "panel.parquet"
    stale.to_parquet(p)
    import src.data.paths as P
    monkeypatch.setattr(P, "PANEL_DAILY", p)
    assert CD._panel_history(["AAA"], date(2026, 10, 2)) == {}


def test_a_failed_pull_caches_empty_rather_than_retrying_every_cycle(tmp_path, monkeypatch):
    monkeypatch.setattr(CD, "DAILY_HISTORY_DIR", tmp_path / "dh")
    monkeypatch.setattr(CD, "_panel_history", lambda tickers, today: {})

    class _Boom:
        def __init__(self): self.calls = 0
        def get_daily_bars(self, *a, **k):
            self.calls += 1
            raise RuntimeError("down")
    c = _Boom()
    assert CD.ensure_daily_history(c, ["AAA"], date(2026, 10, 2)) == {"AAA": []}
    CD.ensure_daily_history(c, ["AAA"], date(2026, 10, 2))
    assert c.calls == 1
