"""Tests for the Bollinger Squeeze Breakout + Volume detector
(src/engines/squeeze_breakout.py)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines.squeeze_breakout import compute_squeeze_breakout, _NULL, _MIN_BARS

_N_FLAT = 70  # enough tight bars ahead of the breakout to force a squeeze


def _flat_then(move: float, *, vol_spike: bool = True) -> pd.DataFrame:
    """`_N_FLAT` very tight bars (forces a squeeze), then one final bar that
    moves `move` points from the last flat close, optionally on a volume spike."""
    rng = np.random.default_rng(1)
    dates = pd.bdate_range("2025-01-01", periods=_N_FLAT + 1)
    flat_close = 100 + np.cumsum(rng.normal(0, 0.05, _N_FLAT))
    flat_high = flat_close + 0.1
    flat_low = flat_close - 0.1
    flat_vol = np.full(_N_FLAT, 1_000_000.0)

    last_close = float(flat_close[-1])
    final_close = last_close + move
    final_high = max(final_close, last_close) + 0.2
    final_low = min(final_close, last_close) - 0.2
    final_vol = 5_000_000.0 if vol_spike else 900_000.0

    close = np.append(flat_close, final_close)
    high = np.append(flat_high, final_high)
    low = np.append(flat_low, final_low)
    vol = np.append(flat_vol, final_vol)
    return pd.DataFrame({"date": dates, "high": high, "low": low, "close": close, "volume": vol})


def test_squeeze_forms_over_a_tight_range():
    """A long tight range with no breakout should read as squeezed, no event."""
    df = _flat_then(0.0, vol_spike=False)
    out = compute_squeeze_breakout(df)
    assert out["was_squeezed"] is True
    assert out["squeeze_breakout_state"] == "NONE"


def test_upward_breakout_after_squeeze():
    df = _flat_then(5.0)
    out = compute_squeeze_breakout(df)
    assert out["squeeze_breakout_state"] == "BREAKOUT_UP"
    assert out["squeeze_breakout_date"] == str(df["date"].iloc[-1].date())


def test_downward_breakout_after_squeeze():
    df = _flat_then(-5.0)
    out = compute_squeeze_breakout(df)
    assert out["squeeze_breakout_state"] == "BREAKOUT_DOWN"


def test_breakout_volume_confirmed_flag_true_on_spike():
    df = _flat_then(5.0, vol_spike=True)
    out = compute_squeeze_breakout(df)
    assert out["squeeze_breakout_volume_confirmed"] is True


def test_breakout_volume_confirmed_flag_false_without_spike():
    df = _flat_then(5.0, vol_spike=False)
    out = compute_squeeze_breakout(df)
    # The breakout itself still fires — volume never gates the state, only
    # annotates it, so a low-volume breakout stays visible rather than hidden.
    assert out["squeeze_breakout_state"] == "BREAKOUT_UP"
    assert out["squeeze_breakout_volume_confirmed"] is False


def test_no_breakout_without_a_prior_squeeze():
    """A crossover that fires without the market having been squeezed the
    bar before must not read as a squeeze breakout."""
    rng = np.random.default_rng(2)
    n = _N_FLAT + 1
    dates = pd.bdate_range("2025-01-01", periods=n)
    # Volatile closes with a NARROW intrabar range: close-to-close jumps
    # dominate true range, so KC (ATR-based) stays wide relative to BB
    # (stdev-of-close-based) — never squeezed.
    close = pd.Series(100 + np.cumsum(rng.normal(0, 3.0, n)))
    high = close + 1.0
    low = close - 1.0
    vol = np.full(n, 2_000_000.0)
    df = pd.DataFrame({"date": dates, "high": high, "low": low, "close": close, "volume": vol})
    out = compute_squeeze_breakout(df)
    assert out["was_squeezed"] is False
    # No claim on squeeze_breakout_state here — a choppy series can cross its
    # own bands by chance. The point of this test is was_squeezed being False.


def test_short_data_degrades_to_null():
    df = _flat_then(5.0).head(_MIN_BARS - 1)
    assert compute_squeeze_breakout(df) == _NULL


def test_none_input_degrades_to_null():
    assert compute_squeeze_breakout(None) == _NULL


def test_empty_frame_degrades_to_null():
    assert compute_squeeze_breakout(pd.DataFrame()) == _NULL


def test_missing_required_column_degrades_to_null():
    df = _flat_then(5.0).drop(columns=["volume"])
    assert compute_squeeze_breakout(df) == _NULL


def test_never_raises_on_malformed_values():
    df = _flat_then(5.0)
    df.loc[df.index[-1], "high"] = float("nan")
    out = compute_squeeze_breakout(df)  # must not raise
    assert out["squeeze_breakout_state"] in ("NONE", "BREAKOUT_UP", "BREAKOUT_DOWN")
