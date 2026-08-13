"""Bollinger Squeeze Breakout + Volume — pattern detector.

Port of the deterministic parts of "Bollinger Squeeze Breakout + Volume"
(Pine v6, AIScripts). Reuses AQE's own squeeze test (Bollinger(20,2) inside
Keltner(20, ATR x1.5) — `utils.bollinger_keltner_squeeze`, the same test
energy.py's squeeze_score is built on) rather than recomputing a second,
looser one: the source strategy's own squeeze rule (BB width < 0.8x its
50-bar average) is a strict subset of AQE's stricter BB-inside-KC test, so
nothing is lost by sharing it, and there is exactly one squeeze definition
in the codebase instead of two that can silently drift apart.

What this adds beyond squeeze_score (a continuous 0-12.5 Energy sub-score):
a DISCRETE last-bar event — was the market squeezed on the bar BEFORE this
one, and did price just cross a Bollinger Band THIS bar, on above-average
volume. Context only, like every other DETECT-layer read — never a gate,
never sizing.
"""

from __future__ import annotations

import pandas as pd

from src.engines import utils as U

_REQUIRED_COLS = {"date", "high", "low", "close", "volume"}
_MIN_BARS = 71  # 50-bar width percentile + 20-bar squeeze/volume lookback, +1 for prior-bar state

_NULL = {
    "squeeze_breakout_state": "NONE",
    "squeeze_breakout_date": None,
    "squeeze_breakout_volume_confirmed": False,
    "was_squeezed": False,
}


def compute_squeeze_breakout(daily: pd.DataFrame, *, vol_len: int = 20) -> dict:
    """Squeeze-breakout read on the LAST closed bar of `daily`.

    Returns (always present, never raises):
        squeeze_breakout_state: "BREAKOUT_UP" | "BREAKOUT_DOWN" | "NONE" —
            price crossed a Bollinger Band THIS bar, having been squeezed
            (BB inside KC) on the PRIOR bar.
        squeeze_breakout_date: date of that breakout (None if NONE).
        squeeze_breakout_volume_confirmed: bool — was volume above its own
            20-bar average on the breakout bar. Never filters the state
            itself, so a low-volume breakout is visible, not hidden.
        was_squeezed: bool — is the LAST bar itself currently squeezed,
            independent of whether a breakout just fired.
    """
    try:
        if daily is None or len(daily) < _MIN_BARS:
            return dict(_NULL)
        if not _REQUIRED_COLS.issubset(daily.columns):
            return dict(_NULL)

        d = daily.tail(_MIN_BARS).reset_index(drop=True)
        high = d["high"].astype(float)
        low = d["low"].astype(float)
        close = d["close"].astype(float)
        volume = d["volume"].astype(float)

        sqz = U.bollinger_keltner_squeeze(high, low, close)
        bu, bl, squeeze = sqz["bb_upper"], sqz["bb_lower"], sqz["squeeze"]
        vol_pass = volume > U.sma(volume, vol_len)

        was_squeezed_prior = squeeze.shift(1).fillna(False)
        up = U.crossover(close, bu) & was_squeezed_prior
        down = U.crossunder(close, bl) & was_squeezed_prior

        out = dict(_NULL)
        out["was_squeezed"] = bool(squeeze.iloc[-1])
        if bool(up.iloc[-1]):
            out["squeeze_breakout_state"] = "BREAKOUT_UP"
        elif bool(down.iloc[-1]):
            out["squeeze_breakout_state"] = "BREAKOUT_DOWN"
        if out["squeeze_breakout_state"] != "NONE":
            out["squeeze_breakout_date"] = str(pd.Timestamp(d["date"].iloc[-1]).date())
            out["squeeze_breakout_volume_confirmed"] = bool(vol_pass.iloc[-1])
        return out
    except Exception:  # noqa: BLE001 — pure pattern read, never blocks the caller
        return dict(_NULL)
