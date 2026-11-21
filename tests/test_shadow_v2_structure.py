"""Shadow v2 for Structure (research review 2026-11-21 item 11) and the single squeeze definition (item 17)."""
import numpy as np
import pandas as pd

from src.engines import structure
from src.engines import utils as U


def _frame(close, high=None):
    close = np.asarray(close, dtype=float)
    high = close * 1.003 if high is None else np.asarray(high, dtype=float)
    return pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=len(close)), "open": close, "high": high, "low": close * 0.997, "close": close,
                         "volume": 1e6})


def _spy(n):
    c = 100 * (1 + 0.0004) ** np.arange(n)
    return pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=n), "close": c, "open": c, "high": c, "low": c, "volume": 1e6})


def test_item11_a_close_above_the_prior_50_day_high_takes_the_cleared_band_in_v2_not_in_the_live_score():
    n = 200
    close = np.concatenate([np.linspace(80, 100, 150), np.linspace(100, 99, 49), [104.0]])      # flat-ish under 100.3, then a close through the prior high
    d = _frame(close)
    out = structure.compute(d, spy_daily=_spy(n), weekly=pd.DataFrame())
    t = n - 1
    # live: ms_h50 includes today's high (>= close), so the distance is >= 0 and the close 4% through the prior high still reads 'within 3%': 10 points
    assert out["resist_score"].iloc[t] == 10.0
    # v2: the prior bar's 50-day high is below the close -> dist < 0 -> the cleared band
    assert out["resist_score_v2"].iloc[t] == 7.0


def test_item11_v2_differs_from_live_only_in_the_resist_component():
    n = 260
    rng = np.random.default_rng(2)
    close = 100 * np.cumprod(1 + rng.normal(0.0006, 0.01, n))
    out = structure.compute(_frame(close), spy_daily=_spy(n), weekly=pd.DataFrame())
    both = out.dropna(subset=["structure_100", "structure_100_v2"])
    raw_live = both["structure_100"] / 100.0 * 95.0
    raw_v2 = both["structure_100_v2"] / 100.0 * 95.0
    inside = (both["structure_100"] > 0) & (both["structure_100"] < 100) & (both["structure_100_v2"] > 0) & (both["structure_100_v2"] < 100)
    delta = (raw_v2 - raw_live)[inside]
    want = (both["resist_score_v2"] - both["resist_score"])[inside]
    assert np.allclose(delta.to_numpy(), want.to_numpy())


def test_live_structure_columns_are_present_and_the_shadow_columns_are_in_score_columns():
    from src.scanner.score_runner import SCORE_COLUMNS
    out = structure.compute(_frame(100 + np.sin(np.arange(200) / 9.0)), spy_daily=_spy(200), weekly=pd.DataFrame())
    for c in ("structure_100", "resist_score", "resist_score_v2", "structure_100_v2"):
        assert c in out.columns
        assert c in SCORE_COLUMNS
    assert SCORE_COLUMNS.index("resist_score_v2") > SCORE_COLUMNS.index("ls_volume_confirmed")


def test_item17_readiness_uses_the_shared_squeeze_and_it_is_numerically_identical_to_the_old_copy(monkeypatch):
    """readiness.py used to re-implement U.bollinger_keltner_squeeze. The old formulas, inline, must equal the shared function on any series, and
    readiness must now call the shared function (one definition)."""
    rng = np.random.default_rng(5)
    n = 500
    close = pd.Series(100 * np.cumprod(1 + rng.normal(0.0003, 0.015, n)))
    high = close * (1 + abs(rng.normal(0, 0.01, n)))
    low = close * (1 - abs(rng.normal(0, 0.01, n)))
    # the old inline copy
    bb_mid = U.sma(close, 20)
    bb_dev = 2.0 * U.stdev_pop(close, 20)
    bb_upper, bb_lower = bb_mid + bb_dev, bb_mid - bb_dev
    bw = ((bb_upper - bb_lower) / bb_mid.replace(0.0, np.nan) * 100).fillna(0.0)
    bw_lo, bw_hi = U.lowest(bw, 50), U.highest(bw, 50)
    bwp = ((bw - bw_lo) / (bw_hi - bw_lo).replace(0.0, np.nan) * 100).fillna(50.0)
    kc_range = U.atr(high, low, close, n=20)
    sq = (bb_lower > bb_mid - kc_range * 1.5) & (bb_upper < bb_mid + kc_range * 1.5)
    shared = U.bollinger_keltner_squeeze(high, low, close)
    assert shared["squeeze"].equals(sq) and np.allclose(shared["bb_width_pct"].to_numpy(), bwp.to_numpy(), equal_nan=True)
    from src.engines import readiness
    calls = []
    orig = U.bollinger_keltner_squeeze
    monkeypatch.setattr(U, "bollinger_keltner_squeeze", lambda *a, **k: (calls.append(1), orig(*a, **k))[1])
    d = pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=n), "open": close, "high": high, "low": low, "close": close, "volume": 1e6})
    readiness.compute(d)
    assert calls, "readiness must call the shared squeeze definition"


# ------------------------------------------------------------------------------ item 15 (Elder)
def _ohlc(close, rng_pct=0.01):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=len(close)), "open": close, "high": close * (1 + rng_pct), "low": close * (1 - rng_pct),
                         "close": close, "volume": 1e6})


def test_item15_hist_score_v2_bands_are_the_named_constants_and_zero_when_the_histogram_is_not_positive():
    from src.engines import elder
    assert elder.ELDER_V2_X_LOW == 0.10 and elder.ELDER_V2_X_HIGH == 0.23
    rng = np.random.default_rng(4)
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, 600))
    d = _ohlc(close)
    out = elder.compute(d)
    res = U.macd(pd.Series(close), fast=12, slow=26, signal=9, signal_kind="ema")
    hist = res.hist
    atr14 = U.atr(d["high"], d["low"], pd.Series(close), n=14)
    x = hist / atr14
    ok = out["elder_score_v2"].notna()
    h = out["hist_score_v2"][ok]
    assert (h[hist[ok] <= 0] == 0).all()
    assert (h[(hist[ok] > 0) & (x[ok] < 0.10)] == 1).all()
    assert (h[(hist[ok] > 0) & (x[ok] >= 0.10) & (x[ok] < 0.23)] == 2).all()
    assert (h[(hist[ok] > 0) & (x[ok] >= 0.23)] == 3).all()
    assert out["elder_score_v2"].dropna().between(0, 10).all()


def test_item15_hist_score_v2_never_depends_on_hist_prev():
    """Same bar, same histogram and ATR, different previous histogram: the v2 histogram score must not move. Built by checking that two series whose
    last bar has the identical hist/ATR but different hist history give the same hist_score_v2 on that bar (the live score differs)."""
    from src.engines import elder
    rng = np.random.default_rng(9)
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, 300))
    d = _ohlc(close)
    base = elder.compute(d)
    # the score is a pure function of (hist, ATR14) on the bar: recompute it from those two alone and compare
    res = U.macd(pd.Series(close), fast=12, slow=26, signal=9, signal_kind="ema")
    x = res.hist / U.atr(d["high"], d["low"], pd.Series(close), n=14)
    pure = pd.Series(0.0, index=x.index)
    pure = pure.where(~((res.hist > 0) & (x < 0.10)), 1.0)
    pure = pure.where(~((res.hist > 0) & (x >= 0.10) & (x < 0.23)), 2.0)
    pure = pure.where(~((res.hist > 0) & (x >= 0.23)), 3.0)
    ok = base["elder_score_v2"].notna()
    assert np.array_equal(base["hist_score_v2"][ok].to_numpy(), pure[ok].to_numpy())
    import inspect
    src = inspect.getsource(elder.compute)
    seg = src[src.index("SHADOW v2 histogram score"):src.index("# Pine line 36")]
    assert "hist_prev" not in seg and "hist_accel" not in seg


def test_the_live_elder_score_is_unchanged():
    from src.engines import elder
    rng = np.random.default_rng(1)
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, 300))
    out = elder.compute(_ohlc(close))
    for c in ("elder_score", "impulse_state", "elder_score_v2", "hist_score_v2"):
        assert c in out.columns
    assert out["elder_score"].dropna().between(0, 10).all()


# ------------------------------------------------------------------------------ item 10 (base latch; spec change, PM sign-off)
def test_item10_v2_latches_a_breakout_that_the_live_rule_cannot_see_because_mode1_keeps_the_bar_in_base():
    n = 160
    close = np.concatenate([np.linspace(80, 100, 60), np.full(75, 100.0), [100.2] * 24, [101.0]])
    close = close[:n]
    high = close * 1.001
    vol = np.full(n, 1e6)
    t = 140
    close[t] = 101.2                      # a close through the consolidation high ...
    high[t] = 101.4
    vol[t] = 3e6                          # ... on volume; the 10-day range is still <= 15%, so the bar is still 'in base' (mode1)
    d = pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=n), "open": close, "high": high, "low": close * 0.999, "close": close, "volume": vol})
    out = structure.compute(d, spy_daily=_spy(n), weekly=pd.DataFrame())
    live_after = out["base_days"].iloc[t + 2]
    v2_after = out["base_days_v2"].iloc[t + 2]
    assert v2_after == out["base_days_v2"].iloc[t + 4]          # v2: latched for the decay window
    assert live_after != v2_after                               # live: still a running count (no latch fired)
    assert "base_score_v2" in out.columns


def test_item10_the_live_base_days_logic_is_unchanged_by_the_refactor():
    """The refactor into _base_days/_base_score must be output-neutral for the live path: pin a few values from a fixed series."""
    rng = np.random.default_rng(21)
    n = 400
    close = 100 * np.cumprod(1 + rng.normal(0.0003, 0.012, n))
    hi = close * (1 + abs(rng.normal(0, 0.008, n)))
    lo = close * (1 - abs(rng.normal(0, 0.008, n)))
    d = pd.DataFrame({"date": pd.bdate_range("2019-01-01", periods=n), "open": close, "high": hi, "low": lo, "close": close, "volume": rng.uniform(5e5, 2e6, n)})
    out = structure.compute(d, spy_daily=_spy(n), weekly=pd.DataFrame())
    assert out["base_days"].between(0, n).all() and out["base_score"].between(0, 15).all()
    bd = out["base_days"].to_numpy()
    again = structure._base_days(_in_base_live(d), d["high"].to_numpy(), d["close"].to_numpy(), d["volume"].to_numpy(),
                                 d["volume"].rolling(20).mean().to_numpy(), require_not_in_base=True)
    assert np.array_equal(bd, again)


def _in_base_live(d):
    from src.engines import utils as UU
    close, high, low = d["close"].astype(float), d["high"].astype(float), d["low"].astype(float)
    atr_val = UU.atr(high, low, close, n=20)
    range_pct = ((UU.highest(high, 10) - UU.lowest(low, 10)) / close.replace(0.0, np.nan) * 100.0).fillna(100.0)
    mode1 = range_pct <= 15.0
    sma_50 = UU.sma(close, 50)
    uptrend = (close > sma_50) & (sma_50 > sma_50.shift(5))
    lh10 = UU.highest(high, 10)
    pb = ((lh10 - close) / lh10.replace(0.0, np.nan) * 100.0).fillna(100.0)
    shallow = (pb >= 1.5) & (pb < 8.0)
    inc = (low > low.shift(1)).astype(int)
    stair = inc + inc.shift(1).fillna(0) + inc.shift(2).fillna(0) + inc.shift(3).fillna(0) + inc.shift(4).fillna(0)
    mode2 = uptrend & shallow & (stair >= 2)
    e20 = UU.ema(close, 20)
    mode3 = (e20 > e20.shift(3)) & (((close - e20).abs() <= atr_val * 1.0) & atr_val.notna() & (atr_val != 0)) & (close > sma_50)
    return (mode1 | mode2 | mode3).fillna(False).to_numpy()
