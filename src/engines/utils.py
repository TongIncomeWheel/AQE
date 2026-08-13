"""Shared numerical helpers used by the engine ports.

Maps every Pine `ta.*` call we depend on to a pandas/NumPy equivalent. Every
function here is bar-aligned: input is a `pd.Series` indexed sequentially in
date order, output is a `pd.Series` of the same length with NaN in the warmup
region.

Pine ↔ Python correspondence (see docs/plans for the canonical list):

    ta.sma(x, n)            → x.rolling(n).mean()
    ta.ema(x, n)            → x.ewm(span=n, adjust=False).mean()
    ta.rma(x, n)            → wilder_rma(x, n)            ← Wilder smoothing
    ta.stdev(x, n)          → x.rolling(n).std(ddof=0)    ← population stdev
    ta.atr(n)               → atr(high, low, close, n)
    ta.rsi(x, n)            → rsi(x, n)
    ta.macd(...)            → macd(close)                 ← signal = EMA(9)
    ta.linreg(x, n, off=0)  → linreg_endpoint(x, n)
    ta.change(x, n=1)       → x.diff(n)
    ta.crossover(a, b)      → crossover(a, b)
    ta.highest(x, n)        → x.rolling(n).max()
    ta.lowest(x, n)         → x.rolling(n).min()
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# ----- moving averages -----------------------------------------------------


def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False).mean()


def wilder_rma(x: pd.Series, n: int) -> pd.Series:
    """Pine `ta.rma`. Wilder's smoothing.

    Equivalent to `x.ewm(alpha=1/n, adjust=False).mean()` but seeded with the
    first n-1 values as NaN to match Pine's warmup, and seeded with the
    SMA of the first n bars on the n-th bar (which is the standard Wilder
    initialization Pine uses internally).
    """
    if n <= 0:
        raise ValueError("Wilder RMA requires n > 0")
    arr = x.to_numpy(dtype=float)
    out = np.full_like(arr, np.nan, dtype=float)
    if len(arr) < n:
        return pd.Series(out, index=x.index)
    # Seed: SMA of first n bars at index n-1.
    first_window = arr[:n]
    if np.isnan(first_window).any():
        # Some NaNs in warmup; fall back to direct ewm (less Pine-faithful but
        # avoids propagating a NaN seed forever).
        return x.ewm(alpha=1.0 / n, adjust=False).mean()
    out[n - 1] = first_window.mean()
    alpha = 1.0 / n
    for i in range(n, len(arr)):
        prev = out[i - 1]
        cur = arr[i]
        if np.isnan(cur):
            out[i] = prev
        else:
            out[i] = alpha * cur + (1.0 - alpha) * prev
    return pd.Series(out, index=x.index)


def stdev_pop(x: pd.Series, n: int) -> pd.Series:
    """Pine `ta.stdev` — population standard deviation (ddof=0)."""
    return x.rolling(n, min_periods=n).std(ddof=0)


# ----- ATR / RSI -----------------------------------------------------------


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # First bar has no prev_close → TR is just high-low (Pine behaviour).
    tr.iloc[0] = (high.iloc[0] - low.iloc[0]) if len(high) else np.nan
    return tr


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    return wilder_rma(true_range(high, low, close), n)


def rsi(x: pd.Series, n: int = 14) -> pd.Series:
    delta = x.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = wilder_rma(gain, n)
    avg_loss = wilder_rma(loss, n)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    # When avg_loss == 0 and avg_gain > 0, RSI = 100. When both 0, undefined → NaN.
    zero_loss = (avg_loss == 0.0) & (avg_gain > 0.0)
    out = out.where(~zero_loss, 100.0)
    return out


# ----- MACD ----------------------------------------------------------------


@dataclass
class MACDResult:
    macd: pd.Series
    signal: pd.Series
    hist: pd.Series


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    signal_kind: str = "ema",
) -> MACDResult:
    """Pine `ta.macd`. Signal line is EMA(9) by default.

    Pass signal_kind="sma" only when matching a Pine source that explicitly
    uses `ta.sma(macd_line, signal_len)` (e.g., Aegis_Dynamic_SL_v1_4.pine
    line 92).
    """
    macd_line = ema(close, fast) - ema(close, slow)
    if signal_kind == "ema":
        sig = ema(macd_line, signal)
    elif signal_kind == "sma":
        sig = sma(macd_line, signal)
    else:
        raise ValueError(f"unknown signal_kind {signal_kind!r}")
    hist = macd_line - sig
    return MACDResult(macd=macd_line, signal=sig, hist=hist)


# ----- linear regression endpoint ------------------------------------------


def linreg_endpoint(x: pd.Series, n: int) -> pd.Series:
    """Pine `ta.linreg(x, n, 0)` — the value of the linear regression line at
    the most recent bar of a rolling window of length n.
    """
    arr = x.to_numpy(dtype=float)
    out = np.full_like(arr, np.nan, dtype=float)
    if n <= 1 or len(arr) < n:
        return pd.Series(out, index=x.index)
    xs = np.arange(n, dtype=float)
    x_mean = xs.mean()
    x_dev = xs - x_mean
    denom = (x_dev * x_dev).sum()
    for i in range(n - 1, len(arr)):
        window = arr[i - n + 1 : i + 1]
        if np.isnan(window).any():
            continue
        y_mean = window.mean()
        slope = (x_dev * (window - y_mean)).sum() / denom
        intercept = y_mean - slope * x_mean
        out[i] = intercept + slope * (n - 1)
    return pd.Series(out, index=x.index)


# ----- crossover / state helpers ------------------------------------------


def crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    """Pine `ta.crossover(a, b)` — True on the bar where a crosses up through b."""
    a_prev = a.shift(1)
    b_prev = b.shift(1)
    return (a > b) & (a_prev <= b_prev)


def crossunder(a: pd.Series, b: pd.Series) -> pd.Series:
    a_prev = a.shift(1)
    b_prev = b.shift(1)
    return (a < b) & (a_prev >= b_prev)


def highest(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).max()


def lowest(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).min()


def change(x: pd.Series, n: int = 1) -> pd.Series:
    return x.diff(n)


def bollinger_keltner_squeeze(
    high: pd.Series, low: pd.Series, close: pd.Series,
    bb_len: int = 20, bb_mult: float = 2.0,
    kc_len: int = 20, kc_mult: float = 1.5, width_lookback: int = 50,
) -> dict[str, pd.Series]:
    """TTM-style squeeze: Bollinger Bands(bb_len, bb_mult) fully inside
    Keltner Channel(kc_len, ATR x kc_mult). The one squeeze test AQE uses —
    energy.py's squeeze_score and engines/squeeze_breakout.py both call this,
    so there is exactly one place the definition can drift.

    Returns bb_mid/bb_upper/bb_lower, bb_width_pct (BB width's own percentile
    over the last `width_lookback` bars, 0-100), and `squeeze` (bool: BB
    inside KC)."""
    bb_mid = sma(close, bb_len)
    bb_dev = bb_mult * stdev_pop(close, bb_len)
    bb_upper = bb_mid + bb_dev
    bb_lower = bb_mid - bb_dev
    bb_width = ((bb_upper - bb_lower) / bb_mid.replace(0.0, np.nan) * 100.0).fillna(0.0)
    bwl = lowest(bb_width, width_lookback)
    bwh = highest(bb_width, width_lookback)
    bwr = bwh - bwl
    bb_width_pct = ((bb_width - bwl) / bwr.replace(0.0, np.nan) * 100.0).fillna(50.0)
    kc_range = atr(high, low, close, n=kc_len)
    kc_upper = bb_mid + kc_range * kc_mult
    kc_lower = bb_mid - kc_range * kc_mult
    squeeze = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    return {
        "bb_mid": bb_mid, "bb_upper": bb_upper, "bb_lower": bb_lower,
        "bb_width_pct": bb_width_pct, "bb_width_lowest": bwl, "squeeze": squeeze,
    }


# ----- Heikin Ashi ---------------------------------------------------------


@dataclass
class HeikinAshiResult:
    open: pd.Series
    high: pd.Series
    low: pd.Series
    close: pd.Series


def heikin_ashi(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> HeikinAshiResult:
    """Heikin Ashi candles.

    HA_close[t] = (O+H+L+C)/4
    HA_open[t]  = (HA_open[t-1] + HA_close[t-1]) / 2
    HA_open[0]  = (O[0] + C[0]) / 2                     ← Pine seed
    HA_high[t]  = max(H[t], HA_open[t], HA_close[t])
    HA_low[t]   = min(L[t], HA_open[t], HA_close[t])

    Recursive in HA_open → must loop. First ~20 bars may diverge from TV before
    the recursion converges; we use Pine's seed so divergence is bounded.
    """
    n = len(close)
    ha_open = np.full(n, np.nan, dtype=float)
    ha_close = ((open_ + high + low + close) / 4.0).to_numpy(dtype=float)

    if n == 0:
        idx = close.index
        empty = pd.Series([], index=idx, dtype=float)
        return HeikinAshiResult(open=empty, high=empty, low=empty, close=empty)

    ha_open[0] = (open_.iloc[0] + close.iloc[0]) / 2.0
    for i in range(1, n):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0

    ha_open_s = pd.Series(ha_open, index=close.index)
    ha_close_s = pd.Series(ha_close, index=close.index)
    ha_high_s = pd.concat([high, ha_open_s, ha_close_s], axis=1).max(axis=1)
    ha_low_s = pd.concat([low, ha_open_s, ha_close_s], axis=1).min(axis=1)
    return HeikinAshiResult(open=ha_open_s, high=ha_high_s, low=ha_low_s, close=ha_close_s)


# ----- safe arithmetic -----------------------------------------------------


def safe_div(a: pd.Series, b: pd.Series, fill: float = np.nan) -> pd.Series:
    return (a / b.replace(0.0, np.nan)).fillna(fill)


def clip01(x: pd.Series | float) -> pd.Series | float:
    if isinstance(x, pd.Series):
        return x.clip(lower=0.0, upper=1.0)
    return max(0.0, min(1.0, float(x)))


def clip0_100(x: pd.Series | float) -> pd.Series | float:
    if isinstance(x, pd.Series):
        return x.clip(lower=0.0, upper=100.0)
    return max(0.0, min(100.0, float(x)))


# ----- stochastic / OBV ----------------------------------------------------


def stochastic_k(close: pd.Series, high: pd.Series, low: pd.Series, n: int) -> pd.Series:
    """Pine `ta.stoch(close, high, low, n)` — %K (raw, unsmoothed)."""
    lowest_low = lowest(low, n)
    highest_high = highest(high, n)
    rng = (highest_high - lowest_low).replace(0.0, np.nan)
    return ((close - lowest_low) / rng * 100.0).fillna(50.0)


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    sign = np.sign(close.diff()).fillna(0.0)
    return (sign * volume).cumsum()


# ----- weekly join helper --------------------------------------------------


def asof_weekly_value(daily_dates: pd.Series, weekly: pd.DataFrame, column: str) -> pd.Series:
    """For each daily date, return the column value from the most recent weekly
    bar whose date is strictly less than the daily date.

    Look-ahead-safe equivalent of Pine `request.security(sym, "W", x[1])`.
    Assumes daily_dates is already sorted ascending — true for every engine
    call site (we always feed a single-ticker frame in date order).
    """
    if weekly.empty or column not in weekly.columns:
        return pd.Series(np.nan, index=daily_dates.index)
    wk = weekly[["date", column]].dropna(subset=[column]).sort_values("date")
    left = pd.DataFrame({"date": daily_dates.to_numpy()})
    merged = pd.merge_asof(
        left,
        wk,
        on="date",
        direction="backward",
        allow_exact_matches=False,
    )
    return pd.Series(merged[column].to_numpy(), index=daily_dates.index)
