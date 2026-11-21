"""Elder Impulse Score — port of `sources/Elder Impulse.txt`.

Output: a single `elder_score` series in the range [0, 10].

Components (Pine lines 24-36):
    state_score   ∈ {0, 2, 4}   ← impulse colour (green/blue/red)
    slope_score   ∈ {0, 1, 2, 3} ← 3-bar EMA slope %
    hist_score    ∈ {0, 1, 2, 3} ← MACD histogram trend
    elder_score = state_score + slope_score + hist_score
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U

# SHADOW v2 (research review 2026-11-21, item 15; spec from the BACKTEST REVIEW session, PM: "Fix the indicator calculations").
# hist_score_v2 scores the MACD histogram on SIGN and a volatility-normalised MAGNITUDE only: x = hist / ATR14, no acceleration term (the live hist_accel > 0 is
# the same fact as hist_rising, which the green impulse state already requires, so it was counted twice). The two band edges are the terciles of positive x
# measured on panel_daily 2021-03..2026-11 (0.102 and 0.229; 51.1% of bars have hist > 0): SCALE CONSTANTS frozen in code, NOT fitted to returns.
ELDER_V2_X_LOW = 0.10
ELDER_V2_X_HIGH = 0.23


def compute(
    daily: pd.DataFrame,
    *,
    ema_length: int = 13,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal_len: int = 9,
    macd_signal_kind: str = "ema",  # Pine `ta.macd` default
) -> pd.DataFrame:
    """Return a DataFrame with columns [date, elder_score, impulse_state].

    `daily` must have columns [date, open, high, low, close, volume] in ascending
    date order for a single ticker.
    """
    close = daily["close"].astype(float).reset_index(drop=True)
    dates = daily["date"].reset_index(drop=True)

    # Pine line 11
    ema_val = U.ema(close, ema_length)
    ema_prev1 = ema_val.shift(1)
    ema_prev3 = ema_val.shift(3)

    # Pine lines 12-13
    ema_rising = ema_val > ema_prev1
    ema_falling = ema_val < ema_prev1

    # Pine line 15
    res = U.macd(close, fast=macd_fast, slow=macd_slow, signal=macd_signal_len, signal_kind=macd_signal_kind)
    hist = res.hist
    hist_prev = hist.shift(1)

    # Pine lines 16-17
    hist_rising = hist > hist_prev
    hist_falling = hist < hist_prev

    # Pine lines 20-22
    impulse_green = ema_rising & hist_rising
    impulse_red = ema_falling & hist_falling
    impulse_blue = ~impulse_green & ~impulse_red

    # Pine line 25
    state_score = pd.Series(0.0, index=close.index)
    state_score = state_score.where(~impulse_green, 4.0)
    state_score = state_score.where(~(impulse_blue & ~impulse_green), 2.0)
    # impulse_red stays at 0.0 — exactly as Pine's ternary chain dictates.

    # Pine line 28
    ema_slope = ((ema_val - ema_prev3) / ema_val.replace(0.0, pd.NA) * 100.0).astype(float)
    ema_slope = ema_slope.fillna(0.0)

    # Pine line 29
    slope_score = pd.Series(0.0, index=close.index)
    slope_score = slope_score.where(~(ema_slope > 0.0), 1.0)
    slope_score = slope_score.where(~(ema_slope > 0.3), 2.0)
    slope_score = slope_score.where(~(ema_slope > 1.0), 3.0)

    # Pine line 32-33
    hist_accel = hist - hist_prev
    hist_score = pd.Series(0.0, index=close.index)
    hist_score = hist_score.where(~((hist > 0) & ~(hist_accel > 0)), 2.0)
    hist_score = hist_score.where(~(~(hist > 0) & (hist_accel > 0)), 1.0)
    hist_score = hist_score.where(~((hist > 0) & (hist_accel > 0)), 3.0)

    # SHADOW v2 histogram score: sign + ATR-normalised magnitude, no previous-bar term.
    atr14 = U.atr(daily["high"].astype(float).reset_index(drop=True), daily["low"].astype(float).reset_index(drop=True), close, n=14)
    x_hist = hist / atr14.replace(0.0, np.nan)
    hist_score_v2 = pd.Series(0.0, index=close.index)
    hist_score_v2 = hist_score_v2.where(~((hist > 0) & (x_hist < ELDER_V2_X_LOW)), 1.0)
    hist_score_v2 = hist_score_v2.where(~((hist > 0) & (x_hist >= ELDER_V2_X_LOW) & (x_hist < ELDER_V2_X_HIGH)), 2.0)
    hist_score_v2 = hist_score_v2.where(~((hist > 0) & (x_hist >= ELDER_V2_X_HIGH)), 3.0)
    elder_score_v2 = (state_score + slope_score + hist_score_v2).clip(lower=0.0, upper=10.0)

    # Pine line 36
    elder_score = (state_score + slope_score + hist_score).clip(lower=0.0, upper=10.0)
    # Mark warmup as NaN so the composite can detect it. EMA(26) for MACD is the
    # longest lookback; require both EMAs of MACD to be defined + a 3-bar lag.
    warm = res.macd.notna() & res.signal.notna() & ema_prev3.notna()
    elder_score = elder_score.where(warm, np.nan)
    elder_score_v2 = elder_score_v2.where(warm & atr14.notna(), np.nan)

    impulse_state = pd.Series("NEUTRAL", index=close.index, dtype="object")
    impulse_state = impulse_state.where(~impulse_green, "GREEN")
    impulse_state = impulse_state.where(~impulse_red, "RED")

    return pd.DataFrame({
        "date": dates,
        "elder_score": elder_score,
        "elder_score_v2": elder_score_v2,
        "hist_score_v2": hist_score_v2,
        "impulse_state": impulse_state,
    })
