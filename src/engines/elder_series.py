"""Elder data pack - the eight series fields that switch on elder-lens recognisers R1-R6.

Signed off by the PM 2026-11-03 ("Yes build the Elder pack"); definition in docs/ELDER_DATA_PACK_SPEC.md.
Pure pandas on the daily OHLCV bars every other engine reads. DATA ONLY: never a gate, never sizing.
Every constant below is one line to change if the signer prefers another setting.

Fields (all None when there is too little history - never a fabricated value):
  impulse_colour_last_bar / impulse_colour_prior_bar   GREEN | RED | BLUE
      GREEN = EMA13(close) rose AND MACD-histogram(12,26,9) rose vs the bar before; RED = both fell; else BLUE.
  force_index_ema_2, force_index_ema_13   EMA(2) / EMA(13) of Force Index = (close - prior close) * volume
  price_ema_slope                         EMA13(close) last bar minus prior bar (R3 reads the sign)
  channel_upper, channel_lower            EMA(22) * (1 +/- k); k = 95th percentile over the last 100 bars of
                                          max(|high-EMA|, |low-EMA|)/EMA - the narrowest symmetric percentage channel
                                          holding 95% of the last 100 bars' highs and lows
  weekly_trend_direction                  UP | DOWN | FLAT from EMA13 of ISO-week closes (this week's bar is the
                                          latest close so far); read before the daily
"""
from __future__ import annotations

import numpy as np
import pandas as pd

IMPULSE_EMA = 13
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
FORCE_FAST, FORCE_SLOW = 2, 13
CHANNEL_EMA = 22
CHANNEL_COVERAGE = 0.95
CHANNEL_BARS = 100
WEEKLY_EMA = 13

MIN_BARS_IMPULSE = MACD_SLOW + MACD_SIGNAL + 2      # 37: the histogram needs its signal line warmed up
MIN_BARS_FORCE = FORCE_SLOW + 2
MIN_WEEKS = WEEKLY_EMA + 2


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _colour(ema13: pd.Series, hist: pd.Series, i: int) -> str:
    de, dh = ema13.iloc[i] - ema13.iloc[i - 1], hist.iloc[i] - hist.iloc[i - 1]
    if de > 0 and dh > 0:
        return "GREEN"
    if de < 0 and dh < 0:
        return "RED"
    return "BLUE"


def compute_elder_series(df: pd.DataFrame) -> dict:
    out = {"impulse_colour_last_bar": None, "impulse_colour_prior_bar": None,
           "force_index_ema_2": None, "force_index_ema_13": None, "price_ema_slope": None,
           "channel_upper": None, "channel_lower": None, "weekly_trend_direction": None}
    if df is None or df.empty:
        return out
    c = df["close"].astype(float).reset_index(drop=True)
    h = df["high"].astype(float).reset_index(drop=True)
    l = df["low"].astype(float).reset_index(drop=True)
    v = df["volume"].astype(float).reset_index(drop=True)
    n = len(c)
    try:
        if n >= MIN_BARS_IMPULSE:
            ema13 = _ema(c, IMPULSE_EMA)
            macd = _ema(c, MACD_FAST) - _ema(c, MACD_SLOW)
            hist = macd - _ema(macd, MACD_SIGNAL)
            out["impulse_colour_last_bar"] = _colour(ema13, hist, n - 1)
            out["impulse_colour_prior_bar"] = _colour(ema13, hist, n - 2)
            out["price_ema_slope"] = round(float(ema13.iloc[-1] - ema13.iloc[-2]), 4)
        if n >= MIN_BARS_FORCE:
            fi = (c.diff() * v).iloc[1:]
            out["force_index_ema_2"] = round(float(_ema(fi, FORCE_FAST).iloc[-1]), 2)
            out["force_index_ema_13"] = round(float(_ema(fi, FORCE_SLOW).iloc[-1]), 2)
        if n >= CHANNEL_BARS:
            val = _ema(c, CHANNEL_EMA)
            exc = (pd.concat([(h - val).abs(), (l - val).abs()], axis=1).max(axis=1) / val).iloc[-CHANNEL_BARS:]
            k = float(np.percentile(exc.to_numpy(), CHANNEL_COVERAGE * 100))
            out["channel_upper"] = round(float(val.iloc[-1]) * (1 + k), 2)
            out["channel_lower"] = round(float(val.iloc[-1]) * (1 - k), 2)
        if "date" in df.columns:
            d = pd.to_datetime(df["date"]).reset_index(drop=True)
            iso = d.dt.isocalendar()
            wk = c.groupby([iso["year"].to_numpy(), iso["week"].to_numpy()], sort=True).last()
            if len(wk) >= MIN_WEEKS:
                w = _ema(wk.reset_index(drop=True), WEEKLY_EMA)
                diff = float(w.iloc[-1] - w.iloc[-2])
                out["weekly_trend_direction"] = "UP" if diff > 0 else ("DOWN" if diff < 0 else "FLAT")
    except Exception:  # noqa: BLE001 - additive, never blocks the export
        pass
    return out
