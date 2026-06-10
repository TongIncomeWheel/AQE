"""SRM v3.0 — Sector Rotation Monitor.

Grades each GICS sector based on breadth and momentum of its ETF.
Uses the sector ETF directly (not constituents) for the simplified
backtester implementation.

Grades: DEPLOY / HOLD / TURNING / WATCH / AVOID

For PTRS integration, the grade maps to SH (Sector Health) values:
    DEPLOY  → +3
    HOLD    → 0
    TURNING → -3
    WATCH   → -5
    AVOID   → -8
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


GICS_ETFS = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLRE", "XLU", "XLC", "XLB"]

TICKER_TO_SECTOR = {
    "AAPL": "XLK", "MSFT": "XLK", "NVDA": "XLK", "AVGO": "XLK", "AMD": "XLK",
    "CRWD": "XLK", "PLTR": "XLK", "ANET": "XLK", "NOW": "XLK",
    "AMZN": "XLY", "TSLA": "XLY", "COST": "XLY", "HD": "XLY", "NKE": "XLY",
    "BKNG": "XLY", "ABNB": "XLY",
    "GOOGL": "XLC", "META": "XLC", "NFLX": "XLC", "DIS": "XLC", "SPOT": "XLC",
    "JPM": "XLF", "V": "XLF", "MA": "XLF", "GS": "XLF", "BLK": "XLF",
    "AXP": "XLF", "COIN": "XLF",
    "UNH": "XLV", "LLY": "XLV", "JNJ": "XLV", "ABBV": "XLV", "MRK": "XLV",
    "ISRG": "XLV", "TMO": "XLV",
    "XOM": "XLE", "CVX": "XLE", "COP": "XLE", "SLB": "XLE", "OXY": "XLE",
    "CAT": "XLI", "GE": "XLI", "RTX": "XLI", "HON": "XLI", "DE": "XLI",
    "VRT": "XLI", "UBER": "XLI",
    "PG": "XLP", "KO": "XLP", "PEP": "XLP", "WMT": "XLP", "PM": "XLP",
    "NEE": "XLU", "SO": "XLU", "DUK": "XLU", "CEG": "XLU", "VST": "XLU",
    "AMT": "XLRE", "PLD": "XLRE", "CCI": "XLRE",
    "FCX": "XLB", "LIN": "XLB", "NEM": "XLB",
}

GRADE_TO_SH = {
    "DEPLOY": 3,
    "HOLD": 0,
    "TURNING": -3,
    "WATCH": -5,
    "AVOID": -8,
}

# Action-state labels: each encodes the market condition AND the implied posture
# for a momentum book, so Alfred/committee read a directive, not a raw signal.
# Derived from the two signals SRM already computes — price vs 20D SMA (trend
# direction) and divergence = roc5 − roc20 (momentum accelerating vs decelerating).
TREND_STATE = {
    (True, True):   "Momentum Building — Add",
    (True, False):  "Momentum Fading — Hold, Don't Add",
    (False, True):  "Recovering From Weakness — Watch for Entry",
    (False, False): "Declining — Avoid",
}


def _trend_state(above_sma20: bool, divergence: float) -> str:
    """Map (trend direction, momentum slope) to a directive action-state label."""
    return TREND_STATE[(bool(above_sma20), divergence > 0.0)]



def grade_sector_etf(etf_daily: pd.DataFrame) -> dict:
    """Grade a single sector ETF's daily bars. Returns latest grade + metrics."""
    if etf_daily.empty or len(etf_daily) < 25:
        return {"grade": "WATCH", "roc20": 0.0, "roc5": 0.0, "above_sma20": False,
                "sh": -5, "trend_state": _trend_state(False, 0.0)}

    close = etf_daily["close"].astype(float)
    sma20 = U.sma(close, 20)

    latest = close.iloc[-1]
    roc20 = (latest - close.iloc[-21]) / close.iloc[-21] * 100.0 if len(close) >= 21 else 0.0
    roc5 = (latest - close.iloc[-6]) / close.iloc[-6] * 100.0 if len(close) >= 6 else 0.0
    above_sma20 = bool(latest > sma20.iloc[-1]) if sma20.notna().iloc[-1] else False

    divergence = roc5 - roc20  # positive = 5d momentum recovering vs 20d trend

    # Canonical SRM grading — must match live /SRM output exactly.
    # Evaluate top-to-bottom, first match wins.
    if above_sma20 and roc20 > 5.0:
        grade = "DEPLOY"
    elif above_sma20 and roc20 > 0.0:
        grade = "HOLD"
    elif not above_sma20 and divergence > 0.0:
        grade = "TURNING"
    elif above_sma20 and roc20 <= 0.0:
        grade = "WATCH"
    else:
        grade = "AVOID"

    return {
        "grade": grade,
        "roc20": round(roc20, 2),
        "roc5": round(roc5, 2),
        "divergence": round(divergence, 2),
        "above_sma20": above_sma20,
        "sh": GRADE_TO_SH[grade],
        "trend_state": _trend_state(above_sma20, divergence),
    }


def grade_all_sectors(panel_daily: pd.DataFrame, trend_days: int = 0) -> dict[str, dict]:
    """Grade all GICS sector ETFs present in the panel. Returns {ETF: grade_dict}.

    When trend_days > 0, each ETF's dict also carries `sh_trend` and
    `grade_trend` -- the SRM reading for each of the last `trend_days` trading
    sessions, oldest -> newest -- so consumers see a trend rather than a
    one-day snapshot. Each historical reading is graded only on bars up to
    that day (no look-ahead); the newest trend entry equals the current grade.
    """
    results = {}
    for etf in GICS_ETFS:
        etf_data = (
            panel_daily.loc[panel_daily["ticker"] == etf]
            .sort_values("date").reset_index(drop=True)
        )
        info = grade_sector_etf(etf_data)
        if trend_days > 0 and len(etf_data) >= 25:
            sh_trend: list[float] = []
            grade_trend: list[str] = []
            n = len(etf_data)
            for k in range(max(25, n - trend_days + 1), n + 1):
                g = grade_sector_etf(etf_data.iloc[:k])
                sh_trend.append(g["sh"])
                grade_trend.append(g["grade"])
            info = {**info, "sh_trend": sh_trend, "grade_trend": grade_trend}
        results[etf] = info
    return results


def get_sector_health(ticker: str, sector_grades: dict[str, dict]) -> int:
    """Return the SH value for a given ticker based on its sector ETF grade."""
    sector_etf = TICKER_TO_SECTOR.get(ticker)
    if sector_etf is None:
        sector_etf = _dynamic_sector_lookup(ticker)
    if sector_etf is None or sector_etf not in sector_grades:
        return 0  # unknown sector → neutral
    return sector_grades[sector_etf]["sh"]


def _dynamic_sector_lookup(ticker: str) -> str | None:
    """Check data/sector_map.json for dynamically-mapped sectors."""
    from pathlib import Path
    import json
    map_path = Path(__file__).resolve().parents[2] / "data" / "sector_map.json"
    if not map_path.exists():
        return None
    try:
        with open(map_path) as f:
            mapping = json.load(f)
        return mapping.get(ticker)
    except Exception:
        return None
