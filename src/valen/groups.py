"""VALEN Neighbourhood — pieces 02/03: Theme Leaders + Rotation.

"Money flows into a whole group at once, not one stock at a time." Reuses
AQE's own 35 thematic baskets (src.engines.srm.THEMATIC_BASKETS) as the
"groups" — a closer match to the handbook's ~31 named groups (Bitcoin
Miners, AI, Semiconductors, China Internet, ...) than the 11 broad GICS
sector ETFs, which stay available as each basket's `parent_gics`.

Reuses `srm.grade_thematic_baskets()` for roc5 (1-week)/roc20 (1-month)/
divergence (thrust) rather than reimplementing that math — this module adds
exactly two things SRM doesn't already compute: `since_open` (today's own
push) and `pct_off_52w_high` (the honesty column: separates a group leading
from its highs from one merely bouncing off its lows, per piece 03). Same
equal-weight-index construction SRM already uses, just over a longer window
for the 52-week read (SRM's own basket index is `tail(80)`, plenty for
roc5/roc20 but not a 52-week high).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines.srm import THEMATIC_BASKETS, grade_all_sectors, grade_thematic_baskets

from . import spec as S

_LOOKBACK_52W = 260  # trading days; a little over 252 for a buffer


def _equal_weight_index(panel_daily: pd.DataFrame, tickers: list[str],
                        value_col: str, tail: int) -> pd.Series:
    """Rebase each ticker to its first valid value, mean across columns —
    identical construction to srm.grade_thematic_baskets, generalised to
    any price column and window so it can serve both since_open and the
    52-week read without duplicating SRM's own basket grading."""
    piv = panel_daily.pivot_table(index="date", columns="ticker", values=value_col)
    piv = piv.sort_index()
    present = [t for t in tickers if t in piv.columns]
    if len(present) < 2:
        return pd.Series(dtype=float)
    sub = piv[present].tail(tail)
    if len(sub) < 2:
        return pd.Series(dtype=float)
    base = sub.bfill().iloc[0]
    norm = sub.divide(base.where(base != 0))
    return norm.mean(axis=1, skipna=True).dropna()


def _since_open_pct(panel_daily: pd.DataFrame, constituents: list[str]) -> float | None:
    """Equal-weight (close/open - 1) across the basket's constituents, today's
    bar only — "the move from the opening price ... buyer intent during the
    session vs. the gap"."""
    today = panel_daily["date"].max()
    day = panel_daily[panel_daily["date"] == today]
    day = day[day["ticker"].isin(constituents)]
    if day.empty:
        return None
    o = pd.to_numeric(day["open"], errors="coerce")
    c = pd.to_numeric(day["close"], errors="coerce")
    pct = ((c - o) / o.replace(0, np.nan)) * 100.0
    pct = pct.replace([np.inf, -np.inf], np.nan).dropna()
    if pct.empty:
        return None
    return round(float(pct.mean()), 2)


def _pct_off_52w_high(panel_daily: pd.DataFrame, constituents: list[str]) -> float | None:
    idx = _equal_weight_index(panel_daily, constituents, "close", _LOOKBACK_52W)
    if idx.empty:
        return None
    high = float(idx.max())
    if high <= 0:
        return None
    return round((float(idx.iloc[-1]) / high - 1.0) * 100.0, 2)


def _rotation_state(pct_off_high: float | None) -> str:
    if pct_off_high is None:
        return S.ROTATION_NEITHER
    off = abs(pct_off_high)
    if off <= S.ROTATION_LEADING_MAX_OFF_HIGH_PCT:
        return S.ROTATION_LEADING
    if S.ROTATION_OFF_FLOOR_MIN_OFF_HIGH_PCT <= off <= S.ROTATION_OFF_FLOOR_MAX_OFF_HIGH_PCT:
        return S.ROTATION_OFF_FLOOR
    return S.ROTATION_NEITHER


def compute_groups(panel_daily: pd.DataFrame) -> dict:
    """Returns {status, groups: [{name, parent_gics, since_open_pct,
    ret_1w_pct, ret_1m_pct, thrust, pct_off_52w_high, rotation_state,
    rrg_quadrant, rrg_direction}], theme_leaders: {since_open, one_week,
    one_month} (each a name-ranked list), rotation: [same rows, sorted by
    thrust desc]}.

    Never raises — a basket that can't be read (thin coverage, missing
    constituents) is simply absent from `groups`, same as SRM's own
    NO_DATA handling; `status` names how many of the 35 came back.
    """
    try:
        sector_grades = grade_all_sectors(panel_daily)
        basket_grades = grade_thematic_baskets(panel_daily, sector_grades)
    except Exception as exc:  # noqa: BLE001
        return {"status": "UNAVAILABLE", "reason": str(exc), "groups": [],
                "theme_leaders": {}, "rotation": []}

    groups = []
    for name, g in basket_grades.items():
        if g.get("grade") == "NO_DATA" or g.get("roc5") is None:
            continue
        info = THEMATIC_BASKETS.get(name) or {}
        constituents = g.get("constituents_used") or []
        since_open = _since_open_pct(panel_daily, constituents)
        pct_off_high = _pct_off_52w_high(panel_daily, constituents)
        groups.append({
            "name": name,
            "display_name": name.replace("_", " "),
            "parent_gics": info.get("parent_gics_etf"),
            "since_open_pct": since_open,
            "ret_1w_pct": g.get("roc5"),
            "ret_1m_pct": g.get("roc20"),
            "thrust": g.get("divergence"),
            "pct_off_52w_high": pct_off_high,
            "rotation_state": _rotation_state(pct_off_high),
            "rrg_quadrant": g.get("rrg_quadrant"),
            "rrg_direction": g.get("rrg_direction"),
        })

    if not groups:
        return {"status": "UNAVAILABLE", "reason": "no basket had usable data",
                "groups": [], "theme_leaders": {}, "rotation": []}

    def _ranked(key):
        rows = [g for g in groups if g.get(key) is not None]
        rows.sort(key=lambda g: g[key], reverse=True)
        return [g["name"] for g in rows]

    theme_leaders = {
        "since_open": _ranked("since_open_pct"),
        "one_week": _ranked("ret_1w_pct"),
        "one_month": _ranked("ret_1m_pct"),
    }
    rotation = sorted((g for g in groups if g.get("thrust") is not None),
                      key=lambda g: g["thrust"], reverse=True)

    return {"status": "OK", "reason": None, "groups": groups,
            "theme_leaders": theme_leaders, "rotation": rotation}
