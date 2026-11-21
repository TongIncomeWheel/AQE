"""Shadow v2 for Flow (items 1-3) and Energy (item 16). Live columns untouched. Flow and Energy v2 are PINE SPEC CHANGES: PM sign-off before any cutover."""
import numpy as np
import pandas as pd

from src.engines import energy, flow
from src.engines import utils as U


def _ohlcv(n, loc, vol=1e6, price=100.0):
    """Bars whose close sits at fraction `loc[i]` of a fixed 2% range: the A/D flow of each bar is (2*loc-1)*volume."""
    loc = np.asarray(loc, dtype=float)
    low = np.full(n, price * 0.99)
    high = np.full(n, price * 1.01)
    close = low + loc * (high - low)
    return pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=n), "open": close, "high": high, "low": low, "close": close, "volume": vol})


def test_linreg_slope_matches_a_polyfit_and_the_endpoint_regression():
    x = pd.Series(np.random.default_rng(1).normal(size=80).cumsum())
    s = U.linreg_slope(x, 10)
    assert abs(s.iloc[-1] - np.polyfit(np.arange(10), x.iloc[-10:].to_numpy(), 1)[0]) < 1e-9
    assert s.iloc[:9].isna().all()
    e = U.linreg_endpoint(x, 10)
    w = x.iloc[-10:].to_numpy()
    assert abs(e.iloc[-1] - (w.mean() + s.iloc[-1] * (10 - 1 - 4.5))) < 1e-9


def test_item1_a_worsening_distribution_scores_zero_in_v2_and_high_in_the_live_endpoint_form():
    n = 220
    loc = np.linspace(0.45, 0.02, n)                 # the close location sinks every bar: distribution that keeps getting worse, A/D sum negative and falling
    out = flow.compute(_ohlcv(n, loc))
    t = n - 1
    assert out["accum_score"].iloc[t] >= 5.5          # the live defect, documented: thresholds reverse when the A/D sum is negative
    assert out["accum_score_v2"].iloc[t] == 0.0
    up = flow.compute(_ohlcv(n, np.linspace(0.02, 0.98, n)))
    assert up["accum_score_v2"].iloc[t] > 0


def test_item1_a_falling_ad_line_never_scores_above_a_rising_one():
    rng = np.random.default_rng(6)
    n = 400
    d = _ohlcv(n, np.clip(0.5 + np.cumsum(rng.normal(0, 0.03, n)), 0.02, 0.98))
    ad = (((2 * d["close"] - d["low"] - d["high"]) / (d["high"] - d["low"])) * d["volume"]).rolling(60, min_periods=60).sum()
    s = U.linreg_slope(ad, 10)
    o = flow.compute(d)
    ok = o["accum_score_v2"].notna() & s.notna()
    assert (o["accum_score_v2"][ok & (s <= 0)] == 0).all()
    assert (o["accum_score_v2"][ok & (s > 0)] >= 1.5).all()


def test_item2_the_floor_band_needs_both_mfi_and_cmf():
    rng = np.random.default_rng(3)
    n = 500
    close = 100 * np.cumprod(1 + rng.normal(0.0002, 0.015, n))
    d = pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=n), "open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
                      "volume": rng.uniform(5e5, 2e6, n)})
    o = flow.compute(d)
    one_only = ((o["mfi"] > 38) ^ (o["cmf"] > -0.05)) & o["flow_score_v2"].notna()
    assert one_only.sum() > 5
    diff = (o["flow_score"] - o["flow_score_v2"])[one_only]
    assert np.allclose(diff.to_numpy(), 2.5)          # the Pine OR credited 2.5 where only one of the two held
    both = ((o["mfi"] > 38) & (o["cmf"] > -0.05)) | ~((o["mfi"] > 38) | (o["cmf"] > -0.05))
    assert np.allclose((o["flow_score"] - o["flow_score_v2"])[both].to_numpy(), 0.0)


def test_item3_flow_100_v2_divides_by_the_true_raw_maximum():
    assert flow.FLOW_RAW_MAX == 40.5
    rng = np.random.default_rng(8)
    n = 400
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, n))
    d = pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=n), "open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
                      "volume": rng.uniform(5e5, 2e6, n)})
    o = flow.compute(d)
    raw = (o["flow_score_v2"] + o["accum_score_v2"] + o["volume_score"] + o["skew_score"] + o["ext_score"]).clip(lower=0, upper=40.5)
    ok = o["flow_100_v2"].notna()
    assert np.allclose((o["flow_100_v2"][ok] * 40.5 / 100.0).to_numpy(), raw[ok].to_numpy())
    assert o["flow_100_v2"].dropna().between(0, 100).all() and o["flow_100"].dropna().between(0, 100).all()


def test_item16_energy_atr_score_v2_uses_raw_atr5_vs_atr20_and_moves_off_the_one_point_floor():
    rng = np.random.default_rng(12)
    n = 1500
    vol = np.where((np.arange(n) // 60) % 3 == 0, 0.03, 0.008)         # volatility regimes: expansion and contraction
    close = 100 * np.cumprod(1 + rng.normal(0.0003, vol))
    d = pd.DataFrame({"date": pd.bdate_range("2016-01-01", periods=n), "open": close, "high": close * (1 + vol), "low": close * (1 - vol), "close": close,
                      "volume": rng.uniform(5e5, 2e6, n)})
    o = energy.compute(d)
    ok = o["atr_score"].notna() & o["atr_score_v2"].notna()
    live_low = float((o["atr_score"][ok] <= 1.0).mean())
    v2_low = float((o["atr_score_v2"][ok] <= 1.0).mean())
    assert live_low > 0.8 and v2_low < live_low          # the live score sits on the floor; v2 uses the bands
    atr5, atr20 = U.atr(d["high"], d["low"], d["close"], n=5), U.atr(d["high"], d["low"], d["close"], n=20)
    pct = (atr5 - atr20) / atr20 * 100
    hit = ok & (pct >= 20) & (pct <= 80)
    assert hit.sum() > 0 and (o["atr_score_v2"][hit] == 7.0).all()
    assert "energy_100_v2" in o.columns and o["energy_100_v2"].dropna().between(0, 100).all()


def test_score_columns_carry_the_flow_and_energy_shadow_block():
    from src.scanner.score_runner import SCORE_COLUMNS
    for c in ("flow_100_v2", "flow_score_v2", "accum_score_v2", "atr_score_v2", "energy_100_v2"):
        assert c in SCORE_COLUMNS
        assert SCORE_COLUMNS.index(c) > SCORE_COLUMNS.index("ls_volume_confirmed")
