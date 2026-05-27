"""Capacity check — Chan EC-5.

Flags tickers where your position would represent >1% of daily dollar volume.
At $70-100K capital with $5-12K positions, this mainly affects small-caps
and low-volume names in the fishing net.

Rule: if position_value / daily_dollar_volume > 0.01, flag CAPACITY_WARNING.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


PARTICIPATION_LIMIT = 0.01  # 1% of daily dollar volume


def check_capacity(
    ticker: str,
    position_value: float,
    avg_volume_20d: float,
    avg_price: float,
) -> dict:
    """Check if a position is too large relative to daily volume.

    Returns: status (OK/WARNING/CRITICAL), participation_rate, daily_dollar_volume.
    """
    daily_dollar_vol = avg_volume_20d * avg_price
    if daily_dollar_vol <= 0:
        return {
            "ticker": ticker,
            "status": "NO_DATA",
            "participation_pct": 0.0,
            "daily_dollar_vol": 0.0,
        }

    participation = position_value / daily_dollar_vol

    if participation > 0.05:
        status = "CRITICAL"  # >5% of daily volume — will move the price
    elif participation > PARTICIPATION_LIMIT:
        status = "WARNING"   # >1% — noticeable impact
    else:
        status = "OK"

    return {
        "ticker": ticker,
        "status": status,
        "participation_pct": round(participation * 100, 3),
        "daily_dollar_vol": round(daily_dollar_vol, 0),
    }


def batch_capacity_check(
    panel: pd.DataFrame,
    capital: float = 100_000.0,
    position_pct: float = 0.10,
    volume_lookback: int = 20,
) -> pd.DataFrame:
    """Check capacity for all tickers in the universe.

    Assumes a typical position = capital × position_pct.
    Uses the last `volume_lookback` bars to estimate avg volume.

    Returns DataFrame with: ticker, avg_volume, avg_price, daily_dollar_vol,
                           participation_pct, status.
    """
    typical_position = capital * position_pct
    results = []

    for ticker, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date").tail(volume_lookback)
        if grp.empty:
            continue

        avg_vol = float(grp["volume"].mean())
        avg_price = float(grp["close"].mean())
        check = check_capacity(ticker, typical_position, avg_vol, avg_price)
        check["avg_volume_20d"] = round(avg_vol, 0)
        check["avg_price"] = round(avg_price, 2)
        results.append(check)

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values("participation_pct", ascending=False).reset_index(drop=True)
    return df
