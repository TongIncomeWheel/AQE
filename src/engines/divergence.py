"""Regular Divergence Detector — price vs. 5 oscillators, confirmed pivots only.

Detects REGULAR divergence (the classic reversal-warning kind, not "hidden"
continuation divergence) between price and five oscillators — RSI(14),
MFI(14), CMF(20), MACD line (12/26), and OBV — at CONFIRMED pivots only.

A pivot is "confirmed" when `pivot_right` bars have already printed after it
(the standard `left`/`right` fractal test: the pivot bar's low/high is the
strict extreme of the `[i-left, i+right]` window). Because a pivot only
exists once its right-side bars are in the data, this detector NEVER
repaints: a divergence flagged on a given run will still be true on every
later run that includes those same bars.

Algorithm (regular divergence, non-repainting):
    1. Find all confirmed pivot lows (on `low`) and pivot highs (on `high`)
       in the trailing window via the strict `left`/`right` fractal test.
    2. BULLISH: take the two most recent confirmed pivot lows p1 (older),
       p2 (newer). If their bar-index span is within [min_span, max_span]
       AND price makes a LOWER low (low[p2] < low[p1]) AND an oscillator
       makes a HIGHER low (osc[p2] > osc[p1]), that oscillator fires
       bullish divergence.
    3. BEARISH is the mirror on confirmed pivot highs: price makes a HIGHER
       high while the oscillator makes a LOWER high.
    4. FRESHNESS gate: a fired divergence only counts if its anchor pivot
       p2 is within `fresh_bars + pivot_right` bars of the last bar in the
       frame. This keeps a divergence found weeks ago (and never acted on)
       from silently continuing to fire in the export forever — once it
       ages out it just disappears from the signal.

Pure and deterministic: same input frame always produces the same output.
Never raises — any malformed input or an insufficient bar count degrades to
the empty/NONE result.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U

_REQUIRED_COLS = {"date", "open", "high", "low", "close", "volume"}
_MIN_BARS = 40
_TAIL_BARS = 150

_OSC_ORDER = ("rsi", "mfi", "cmf", "macd", "obv")


def _empty_result() -> dict:
    return {
        "div_state": "NONE",
        "div_bull_count": 0,
        "div_bear_count": 0,
        "div_oscs": None,
        "div_date": None,
    }


def compute_divergence(
    daily,
    *,
    pivot_left: int = 5,
    pivot_right: int = 5,
    max_span: int = 60,
    min_span: int = 5,
    fresh_bars: int = 10,
) -> dict:
    """Detect regular price/oscillator divergence on confirmed pivots.

    `daily`: pd.DataFrame with columns date, open, high, low, close, volume
    (single ticker, ascending date order). Only the trailing `_TAIL_BARS`
    bars are used for speed; the return is a flat, export/parquet-friendly
    dict (see `_empty_result` for the shape). Never raises.
    """
    try:
        if daily is None or len(daily) < _MIN_BARS:
            return _empty_result()
        if not _REQUIRED_COLS.issubset(set(daily.columns)):
            return _empty_result()

        d = daily.tail(_TAIL_BARS).reset_index(drop=True).copy()
        if len(d) < _MIN_BARS:
            return _empty_result()

        high = d["high"].astype(float)
        low = d["low"].astype(float)
        close = d["close"].astype(float)
        volume = d["volume"].astype(float)
        n = len(d)

        oscillators = {
            "rsi": U.rsi(close, 14),
            "mfi": _mfi(high, low, close, volume, 14),
            "cmf": _cmf(high, low, close, volume, 20),
            "macd": U.ema(close, 12) - U.ema(close, 26),
            "obv": U.obv(close, volume),
        }

        pivot_lows = _confirmed_pivots(low, pivot_left, pivot_right, mode="low")
        pivot_highs = _confirmed_pivots(high, pivot_left, pivot_right, mode="high")

        bull_names: list[str] = []
        bear_names: list[str] = []
        bull_date = None
        bear_date = None

        if len(pivot_lows) >= 2:
            p1, p2 = pivot_lows[-2], pivot_lows[-1]
            span = p2 - p1
            fresh = (n - 1 - p2) <= (fresh_bars + pivot_right)
            if min_span <= span <= max_span and fresh and low.iloc[p2] < low.iloc[p1]:
                for name in _OSC_ORDER:
                    osc = oscillators[name]
                    ov1, ov2 = osc.iloc[p1], osc.iloc[p2]
                    if pd.notna(ov1) and pd.notna(ov2) and ov2 > ov1:
                        bull_names.append(name)
                if bull_names:
                    bull_date = d["date"].iloc[p2]

        if len(pivot_highs) >= 2:
            p1, p2 = pivot_highs[-2], pivot_highs[-1]
            span = p2 - p1
            fresh = (n - 1 - p2) <= (fresh_bars + pivot_right)
            if min_span <= span <= max_span and fresh and high.iloc[p2] > high.iloc[p1]:
                for name in _OSC_ORDER:
                    osc = oscillators[name]
                    ov1, ov2 = osc.iloc[p1], osc.iloc[p2]
                    if pd.notna(ov1) and pd.notna(ov2) and ov2 < ov1:
                        bear_names.append(name)
                if bear_names:
                    bear_date = d["date"].iloc[p2]

        bull_count = len(bull_names)
        bear_count = len(bear_names)

        if bull_count > 0 and bear_count == 0:
            state = "BULLISH"
        elif bear_count > 0 and bull_count == 0:
            state = "BEARISH"
        elif bull_count > 0 and bear_count > 0:
            state = "MIXED"
        else:
            state = "NONE"

        parts = list(bull_names) + [f"-{nm}" for nm in bear_names]
        div_oscs = ",".join(parts) if parts else None

        div_date = None
        anchor = None
        if bull_count == 0 and bear_count == 0:
            anchor = None
        elif bull_count >= bear_count:
            anchor = bull_date
        else:
            anchor = bear_date
        if anchor is not None:
            div_date = pd.Timestamp(anchor).strftime("%Y-%m-%d")

        return {
            "div_state": state,
            "div_bull_count": bull_count,
            "div_bear_count": bear_count,
            "div_oscs": div_oscs,
            "div_date": div_date,
        }
    except Exception:
        return _empty_result()


# ---------- helpers ----------


def _confirmed_pivots(series: pd.Series, left: int, right: int, mode: str) -> list[int]:
    """Confirmed strict-extreme fractal pivots on `series`.

    Index i is a confirmed pivot LOW (mode="low") iff series[i] is the
    strict minimum of series[i-left : i+right+1]; mirror for "high". Only
    indices with `right` bars already printed after them (i <= len-1-right)
    are ever considered, so a pivot never repaints.
    """
    n = len(series)
    if n < left + right + 1:
        return []
    arr = series.to_numpy(dtype=float)
    pivots: list[int] = []
    for i in range(left, n - right):
        window = arr[i - left : i + right + 1]
        if np.isnan(window).any():
            continue
        center = arr[i]
        if mode == "low":
            is_extreme = center <= window.min()
        else:
            is_extreme = center >= window.max()
        if not is_extreme:
            continue
        # strict: center must be the UNIQUE extreme in the window
        if np.sum(window == center) == 1:
            pivots.append(i)
    return pivots


def _mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, n: int = 14) -> pd.Series:
    """Money Flow Index — RSI applied to typical-price money flow (SMA-windowed)."""
    typical = (high + low + close) / 3.0
    mf = typical * volume
    delta = typical.diff()
    pos_mf = mf.where(delta > 0, 0.0).rolling(n, min_periods=n).sum()
    neg_mf = mf.where(delta <= 0, 0.0).rolling(n, min_periods=n).sum()
    ratio = (pos_mf / neg_mf.replace(0.0, np.nan)).fillna(1.0)
    return 100.0 - 100.0 / (1.0 + ratio)


def _cmf(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, n: int = 20) -> pd.Series:
    """Chaikin Money Flow: sum(MFV, n) / sum(volume, n), MFV = ((c-l)-(h-c))/(h-l)*vol."""
    rng = (high - low).replace(0.0, np.nan)
    mfm = (((close - low) - (high - close)) / rng).fillna(0.0)
    mfv = mfm * volume
    vol_sum = volume.rolling(n, min_periods=n).sum().replace(0.0, np.nan)
    return (mfv.rolling(n, min_periods=n).sum() / vol_sum).fillna(0.0)
