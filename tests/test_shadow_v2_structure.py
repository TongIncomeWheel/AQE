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
