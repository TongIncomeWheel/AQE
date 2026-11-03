"""Elder data pack (PM 2026-11-03): the eight series fields behind elder-lens R1-R6."""
import numpy as np
import pandas as pd

from src.engines.elder_series import compute_elder_series, MIN_BARS_IMPULSE


def _bars(n, drift=0.5, seed=1):
    rng = np.random.default_rng(seed)
    c = 100 + np.cumsum(rng.normal(drift, 1.0, n))
    return pd.DataFrame({"date": pd.bdate_range("2025-01-01", periods=n), "open": c, "high": c + 1.0,
                         "low": c - 1.0, "close": c, "volume": rng.integers(1_000_000, 2_000_000, n).astype(float)})


def test_all_eight_fields_on_enough_history():
    o = compute_elder_series(_bars(300))
    assert o["impulse_colour_last_bar"] in {"GREEN", "RED", "BLUE"} and o["impulse_colour_prior_bar"] in {"GREEN", "RED", "BLUE"}
    assert all(o[k] is not None for k in ("force_index_ema_2", "force_index_ema_13", "price_ema_slope", "channel_upper", "channel_lower"))
    assert o["weekly_trend_direction"] in {"UP", "DOWN", "FLAT"}
    assert o["channel_upper"] > o["channel_lower"]


def test_steady_uptrend_reads_up_and_green_not_red():
    d = _bars(300, drift=0.0)
    d["close"] = np.linspace(100, 400, 300) ** 1.0
    d["high"], d["low"] = d["close"] + 1, d["close"] - 1
    o = compute_elder_series(d)
    assert o["weekly_trend_direction"] == "UP" and o["price_ema_slope"] > 0 and o["impulse_colour_last_bar"] != "RED"


def test_steady_downtrend_reads_down():
    d = _bars(300)
    d["close"] = np.linspace(400, 100, 300)
    d["high"], d["low"] = d["close"] + 1, d["close"] - 1
    o = compute_elder_series(d)
    assert o["weekly_trend_direction"] == "DOWN" and o["price_ema_slope"] < 0


def test_channel_holds_95_percent_of_the_last_100_bars():
    d = _bars(300)
    o = compute_elder_series(d)
    # the channel is symmetric around EMA22 at the last bar: the last 100 bars' extremes sit inside it ~95% of the time
    val = d["close"].ewm(span=22, adjust=False).mean()
    k = (o["channel_upper"] / float(val.iloc[-1])) - 1
    exc = pd.concat([(d["high"] - val).abs(), (d["low"] - val).abs()], axis=1).max(axis=1) / val
    assert abs((exc.iloc[-100:] <= k + 1e-6).mean() - 0.95) <= 0.03


def test_force_index_zero_cross_signs():
    d = _bars(60)
    d.loc[d.index[-1], "close"] = d["close"].iloc[-2] - 10     # a hard down bar on volume
    o = compute_elder_series(d)
    assert o["force_index_ema_2"] < o["force_index_ema_13"]


def test_too_little_history_is_none_never_invented():
    o = compute_elder_series(_bars(MIN_BARS_IMPULSE - 1))
    assert o["impulse_colour_last_bar"] is None and o["channel_upper"] is None and o["weekly_trend_direction"] is None
    assert all(v is None for v in compute_elder_series(None).values())


def test_colour_rule_is_both_slopes():
    """GREEN only when EMA13 and the MACD-histogram BOTH rose; RED only when both fell; else BLUE (checked on 40 random series)."""
    for seed in range(40):
        d = _bars(120, drift=0.0, seed=seed)
        c = d["close"]
        ema13 = c.ewm(span=13, adjust=False).mean()
        macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
        hist = macd - macd.ewm(span=9, adjust=False).mean()
        de, dh = ema13.iloc[-1] - ema13.iloc[-2], hist.iloc[-1] - hist.iloc[-2]
        want = "GREEN" if de > 0 and dh > 0 else ("RED" if de < 0 and dh < 0 else "BLUE")
        assert compute_elder_series(d)["impulse_colour_last_bar"] == want
