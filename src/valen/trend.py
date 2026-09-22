"""VALEN market trend — piece 01. SPY + QQQ, daily and weekly, 10-vs-20.

Reads the SAME panel every other AQE engine reads (`panel_daily.parquet` /
`panel_weekly.parquet`), so this can never disagree with the rest of the
export about what a given day's close was. Accepts an optional live price
per symbol (from an intraday FMP quote) so the read can be refreshed during
market hours without waiting for the nightly panel rebuild — the live price
stands in for "today's still-forming bar" on top of yesterday's cached
closes, and the row says so (`basis: "live"` vs `"eod"`).
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import spec as S


def _closes_for(panel_path, symbol: str) -> pd.Series:
    """date-indexed close series for one symbol, oldest first. Empty Series
    (not an exception) if the panel is missing or the symbol isn't in it —
    callers degrade to UNAVAILABLE rather than crash the whole card."""
    if not panel_path.exists():
        return pd.Series(dtype=float)
    df = pd.read_parquet(panel_path, columns=["date", "ticker", "close"])
    df = df[df["ticker"] == symbol]
    if df.empty:
        return pd.Series(dtype=float)
    df = df.assign(date=pd.to_datetime(df["date"])).sort_values("date")
    return df.set_index("date")["close"].astype(float)


def _sma(closes: pd.Series, window: int) -> float | None:
    if len(closes) < window:
        return None
    v = float(closes.tail(window).mean())
    return v if np.isfinite(v) else None


def _rising(closes: pd.Series, window: int) -> bool | None:
    """The `window`-period SMA today vs one session ago — is it climbing?"""
    if len(closes) < window + 1:
        return None
    sma_today = float(closes.tail(window).mean())
    sma_prev = float(closes.iloc[-(window + 1):-1].mean())
    if not (np.isfinite(sma_today) and np.isfinite(sma_prev)):
        return None
    return sma_today > sma_prev


def _append_live(closes: pd.Series, live_price: float | None) -> pd.Series:
    """Stand today's live price in as the latest (still-forming) bar, ON TOP
    of the cached closes — never replacing the last CLOSED bar. If the panel
    is already current through today (post-close run), this is a no-op."""
    if live_price is None or closes.empty:
        return closes
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    if closes.index[-1].normalize() >= today:
        return closes          # panel already has today's real close
    return pd.concat([closes, pd.Series([float(live_price)], index=[today])])


def _symbol_row(symbol: str, daily: pd.Series, weekly: pd.Series,
                 live_price: float | None) -> dict:
    basis = "eod"
    if live_price is not None and not daily.empty:
        today = pd.Timestamp(datetime.now(timezone.utc).date())
        if daily.index[-1].normalize() < today:
            basis = "live"
    daily = _append_live(daily, live_price)

    if daily.empty:
        return {"symbol": symbol, "basis": "unavailable",
                "daily_buy_signal": None, "weekly_buy_signal": None,
                "above_rising_5d": None, "last_price": None}

    last = float(daily.iloc[-1])
    sma_fast = _sma(daily, S.TREND_SMA_FAST)
    sma_slow = _sma(daily, S.TREND_SMA_SLOW)
    daily_buy = (sma_fast is not None and sma_slow is not None
                 and last > sma_fast and last > sma_slow and sma_fast > sma_slow)

    wk_fast = _sma(weekly, S.TREND_WEEKLY_SMA_FAST)
    wk_slow = _sma(weekly, S.TREND_WEEKLY_SMA_SLOW)
    wk_last = float(weekly.iloc[-1]) if not weekly.empty else None
    weekly_buy = (wk_fast is not None and wk_slow is not None and wk_last is not None
                  and wk_last > wk_fast and wk_last > wk_slow and wk_fast > wk_slow)

    sma5 = _sma(daily, S.TREND_RISING_WINDOW)
    rising5 = _rising(daily, S.TREND_RISING_WINDOW)
    above_rising_5d = (sma5 is not None and rising5 is not None
                        and last > sma5 and rising5)

    return {
        "symbol": symbol,
        "basis": basis,                       # "eod" | "live" | "unavailable"
        "last_price": round(last, 2),
        "sma_10": round(sma_fast, 2) if sma_fast is not None else None,
        "sma_20": round(sma_slow, 2) if sma_slow is not None else None,
        "daily_buy_signal": daily_buy,
        "weekly_sma_10": round(wk_fast, 2) if wk_fast is not None else None,
        "weekly_sma_20": round(wk_slow, 2) if wk_slow is not None else None,
        "weekly_buy_signal": weekly_buy,
        "sma_5": round(sma5, 2) if sma5 is not None else None,
        "above_rising_5d": above_rising_5d,
    }


def _regime(spy_row: dict) -> str | None:
    votes = [spy_row.get("daily_buy_signal"), spy_row.get("weekly_buy_signal"),
             spy_row.get("above_rising_5d")]
    if any(v is None for v in votes):
        return None
    if all(votes):
        return S.REGIME_UPTREND
    if not any(votes):
        return S.REGIME_DOWNTREND
    return S.REGIME_CHOP


def compute_market_trend(panel_daily_path, panel_weekly_path,
                          live_prices: dict[str, float] | None = None) -> dict:
    """Returns {rows: {SPY: {...}, QQQ: {...}}, regime: str|None}.

    `live_prices` (optional) = {"SPY": 601.23, "QQQ": 512.40, ...} from an
    intraday quote pull — see src/valen/live.py. Omit for the nightly batch
    read, where the panel's own last close IS the live price by definition.
    """
    live_prices = live_prices or {}
    rows = {}
    for sym in S.TREND_SYMBOLS:
        daily = _closes_for(panel_daily_path, sym)
        weekly = _closes_for(panel_weekly_path, sym)
        rows[sym] = _symbol_row(sym, daily, weekly, live_prices.get(sym))
    return {"rows": rows, "regime": _regime(rows.get("SPY", {}))}
