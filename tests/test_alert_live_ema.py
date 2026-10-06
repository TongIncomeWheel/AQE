"""EMA8 / EMA20 figures on the condition cards (live_ema.py). Figures only:
a test also pins that nothing here can reach the buy decision."""

from __future__ import annotations

import pandas as pd
import pytest

from src.alerts import condition_data as CD
from src.alerts import condition_evaluator as CE
from src.alerts import emailer as E
from src.alerts import live_ema as LE


def _bars(day, closes, start_min=9 * 60 + 30):
    out = []
    for i, c in enumerate(closes):
        hh, mm = divmod(start_min + i * 15, 60)
        out.append({"date": f"{day} {hh:02d}:{mm:02d}:00", "open": c, "high": c,
                    "low": c, "close": c, "volume": 1000})
    return out


def test_read_matches_a_plain_standard_ema():
    closes = [100 + 0.1 * i for i in range(80)]
    r = LE.read(closes, price=closes[-1], min_bars=60)
    s = pd.Series(closes)
    assert r["ema8"] == round(float(s.ewm(span=8, adjust=False).mean().iloc[-1]), 2)
    assert r["ema20"] == round(float(s.ewm(span=20, adjust=False).mean().iloc[-1]), 2)
    assert r["stack"] == "above" and r["slope8"] == "rising" and r["slope20"] == "rising"
    assert r["spot_vs_8_pct"] > 0 and r["spot_vs_20_pct"] > r["spot_vs_8_pct"]


def test_falling_series_reads_below_and_falling():
    closes = [200 - 0.2 * i for i in range(80)]
    r = LE.read(closes, price=closes[-1], min_bars=60)
    assert r["stack"] == "below" and r["slope8"] == "falling" and r["slope20"] == "falling"
    assert r["spot_vs_20_pct"] < 0


def test_short_history_gives_none_not_a_cold_start_number():
    assert LE.read([100.0] * 30, 100.0, min_bars=60) is None
    assert LE.read([100.0] * 80, None, min_bars=60) is None


def test_session_closes_keeps_regular_session_only_and_excludes_today_from_the_seed():
    bars = (_bars("2026-10-01", [10, 11], start_min=8 * 60)            # pre-market: dropped
            + _bars("2026-10-01", [20, 21, 22])                        # regular session
            + _bars("2026-10-02", [30, 31]))                           # "today"
    assert LE.session_closes(bars) == [20, 21, 22, 30, 31]
    assert LE.session_closes(bars, before_date="2026-10-02") == [20, 21, 22]


def test_build_runs_both_timeframes_and_appends_the_live_price_to_daily():
    seed = [100 + 0.05 * i for i in range(120)]
    today = _bars("2026-10-02", [106.0, 106.2, 106.4])
    daily = [{"close": 90 + 0.1 * i} for i in range(100)]
    out = LE.build(seed, today, daily, price=107.0)
    assert out["m15"]["n_bars"] == 123
    assert out["daily"]["n_bars"] == 101          # 100 completed sessions + live price
    assert out["m15"]["stack"] == "above"


def test_build_never_raises_and_degrades_per_timeframe():
    out = LE.build(None, None, None, price=50.0)
    assert out == {"m15": None, "daily": None}
    out = LE.build([100.0] * 80, [], None, price=100.0)
    assert out["m15"] is not None and out["daily"] is None


def test_card_shows_ema_lines_for_each_available_timeframe():
    live = {"price": 71.5, "ema": {
        "m15": {"ema8": 71.20, "ema20": 70.45, "spot_vs_8_pct": 0.42, "spot_vs_20_pct": 1.48,
                "stack": "above", "slope8": "rising", "slope20": "rising", "n_bars": 200},
        "daily": None}}
    lines = E._ema_lines(live)
    assert lines == ["EMA 15-min: EMA8 71.20 (spot +0.4%) · EMA20 70.45 (spot +1.5%) · "
                     "8 above 20 · EMA8 rising, EMA20 rising"]
    assert E._ema_lines({}) == []


def test_ema_never_reaches_the_buy_decision():
    # figures only: the evaluator must not so much as read an ema key
    row = {"conditions": {"shared": {"buy": [{"w": "h1_close_above", "level": 100.0}],
                                     "confirm": [{"w": "vol_x_ge", "x": 1.0}]},
                          "exits": [], "analysts": []}}
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime(2026, 10, 6, 11, 5, tzinfo=ZoneInfo("America/New_York"))
    base = {"last_hourly_close": 100.6, "price": 100.4, "vol_x": {"so_far": 1.5}}
    bear = {"m15": {"stack": "below", "slope8": "falling", "slope20": "falling"}}
    a = CE.evaluate_conditions(row, dict(base), now)
    b = CE.evaluate_conditions(row, {**base, "ema": bear}, now)
    assert a["buy_met"] is True and b["buy_met"] is True


def test_seed_cache_is_built_from_the_same_pull_as_the_volume_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(CD, "VOLUME_PROFILE_DIR", tmp_path / "vp")
    monkeypatch.setattr(CD, "INTRADAY_SEED_DIR", tmp_path / "seed")
    calls = []

    class Client:
        def get_intraday_bars(self, tk, interval="15min", from_date=None, to_date=None):
            calls.append(tk)
            return (_bars("2026-09-30", [50.0 + i for i in range(26)])
                    + _bars("2026-10-02", [99.0, 99.5]))        # today's bars: excluded

    from datetime import date
    CD.ensure_volume_profiles(Client(), ["AAA"], date(2026, 10, 2))
    seeds = CD.load_cached_seeds("2026-10-02")
    assert len(seeds["AAA"]) == 26 and seeds["AAA"][0] == 50.0
    CD.ensure_volume_profiles(Client(), ["AAA"], date(2026, 10, 2))
    assert calls == ["AAA"], "second cycle must not re-pull"


def test_daily_figures_match_a_hand_computed_ema_on_real_panel_data():
    from src.data.paths import PANEL_DAILY
    if not PANEL_DAILY.exists():
        pytest.skip("no panel in this checkout")
    pan = pd.read_parquet(PANEL_DAILY, columns=["ticker", "date", "close"])
    g = pan[pan["ticker"] == "AAPL"].sort_values("date").tail(250)
    if len(g) < 100:
        pytest.skip("AAPL history too short")
    closes = [float(c) for c in g["close"]]
    r = LE.read(closes, closes[-1], 60)
    # independent recursion: ema_t = a*c_t + (1-a)*ema_{t-1}, a = 2/(n+1)
    def ema(n):
        a, e = 2.0 / (n + 1), closes[0]
        for c in closes[1:]:
            e = a * c + (1 - a) * e
        return e
    assert r["ema8"] == pytest.approx(ema(8), abs=0.011)
    assert r["ema20"] == pytest.approx(ema(20), abs=0.011)


def test_ema_matches_a_hand_computed_recursion_on_a_random_walk():
    import random
    rnd = random.Random(7)
    closes, c = [], 100.0
    for _ in range(300):
        c *= 1 + rnd.uniform(-0.02, 0.02)
        closes.append(c)
    r = LE.read(closes, closes[-1], 60)

    def ema(n):
        a, e = 2.0 / (n + 1), closes[0]
        for x in closes[1:]:
            e = a * x + (1 - a) * e
        return e
    assert r["ema8"] == pytest.approx(ema(8), abs=0.006)
    assert r["ema20"] == pytest.approx(ema(20), abs=0.006)


# --- U&R intraday reference figures: opening range, low of day, VWAP reclaim --

from src.alerts import live_measures as LM


def test_opening_range_is_the_first_session_bar_only():
    bars = [{"date": "2026-10-06 09:30:00", "high": 62.4, "low": 61.5, "close": 62.0},
            {"date": "2026-10-06 09:45:00", "high": 63.9, "low": 61.9, "close": 63.5}]
    assert LM.opening_range(bars) == {"high": 62.4, "low": 61.5}
    assert LM.opening_range([bars[1]]) is None
    assert LM.opening_range([]) is None


def test_session_lines_read_spot_against_orb_low_of_day_and_vwap():
    live = {"price": 63.0, "opening_range": {"high": 62.4, "low": 61.5},
            "day_low": 61.2, "day_high": 63.5,
            "vwap": {"vwap": 62.0, "provisional": False},
            "hourly_closes": [61.5, 61.8, 62.6]}
    lines = E._session_lines(live)
    assert lines[0] == ("Opening range (first 15 min): high 62.40 · low 61.50 — "
                        "spot 1.0% above the opening-range high")
    assert lines[1] == "Low of day 61.20 · high of day 63.50 — spot 2.9% above the low of day"
    assert lines[2].startswith("VWAP 62.00: reclaimed")


def test_vwap_lost_holding_and_no_line_cases():
    base = {"price": 61.0, "vwap": {"vwap": 62.0, "provisional": False}}
    assert E._session_lines({**base, "hourly_closes": [62.5, 61.4]})[-1].startswith("VWAP 62.00: lost")
    assert E._session_lines({**base, "hourly_closes": [61.0, 62.5, 62.8]})[-1].startswith(
        "VWAP 62.00: holding above after an earlier close below")
    assert E._session_lines({**base, "hourly_closes": [62.5, 62.8]}) == []      # nothing new
    assert E._session_lines({**base, "vwap": {"vwap": 62.0, "provisional": True},
                             "hourly_closes": [61, 63]}) == []


def test_spot_inside_or_below_the_opening_range_is_said_so():
    inside = E._session_lines({"price": 62.0, "opening_range": {"high": 62.4, "low": 61.5}})
    below = E._session_lines({"price": 61.0, "opening_range": {"high": 62.4, "low": 61.5}})
    assert inside[0].endswith("spot inside the opening range")
    assert "below the opening-range low" in below[0]
    assert E._session_lines({}) == []


def test_session_figures_never_reach_the_buy_decision():
    row = {"conditions": {"shared": {"buy": [{"w": "h1_close_above", "level": 100.0}],
                                     "confirm": [{"w": "vol_x_ge", "x": 1.0}]},
                          "exits": [], "analysts": []}}
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime(2026, 10, 6, 11, 5, tzinfo=ZoneInfo("America/New_York"))
    base = {"last_hourly_close": 100.6, "price": 100.4, "vol_x": {"so_far": 1.5}}
    hostile = {"opening_range": {"high": 120.0, "low": 119.0}, "day_low": 100.3,
               "ema": {"m15": {"stack": "below"}}}
    assert CE.evaluate_conditions(row, dict(base), now)["buy_met"] is True
    assert CE.evaluate_conditions(row, {**base, **hostile}, now)["buy_met"] is True
