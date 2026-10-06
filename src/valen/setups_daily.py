"""VALEN Part 3 -- the impure glue: load the panel, past earnings dates
and today's in-theme groups, grade every export row with src/valen/setups.py,
stamp `setups` onto the rows. Called from the export build (drive_sync) so
the committee, the alert cards and the VALEN page read the same grades.
Kept out of house.py, which stays a pure reader (no file access).
"""

from __future__ import annotations

from . import setups as SU


def in_theme_tickers(valen: dict | None) -> set[str] | None:
    """Tickers whose group is in-theme today (piece 02: top 5 on the 1-week
    or the 1-month list). None when the group read is unavailable -- the
    UnR "group still being bought" check then reads INFO, never a guess."""
    if not valen or (valen.get("groups") or {}).get("status") != "OK":
        return None
    try:
        from src.engines.srm import THEMATIC_BASKETS
        from . import card
        rows = card.theme_reads(card.theme_leaders_table(valen))
    except Exception:  # noqa: BLE001
        return None
    out: set[str] = set()
    for r in rows:
        if r.get("theme_read") != card.THEME_READ_NONE:
            basket = THEMATIC_BASKETS.get(r.get("name")) or {}
            out.update(basket.get("constituents") or [])
    return out


def attach_setup_grades(daily_list: list[dict], held_positions: list[dict] | None = None, *,
                        panel=None, valen: dict | None = None,
                        earnings: dict | None = None) -> dict:
    """Stamp `setups` onto every daily_list row and held position.

    Returns the status block for the export (`setups_status`). A name
    missing from the price panel gets NO `setups` key (could not be graded)
    -- different from `setups: []` (graded, no setup present). On any
    failure every row is left untouched and the status says why: a failed
    grade is LOUD, never an empty list that reads like a quiet market."""
    held_positions = held_positions or []
    try:
        if panel is None:
            import pandas as pd
            from src.data.paths import PANEL_DAILY
            panel = pd.read_parquet(PANEL_DAILY, columns=[
                "ticker", "date", "open", "high", "low", "close", "volume"])
        if earnings is None:
            from src.data.earnings import load_earnings_history
            earnings = load_earnings_history()
        if valen is None:
            from .daily import load_valen
            valen = load_valen()
        spy = panel[panel["ticker"] == "SPY"].set_index("date")["close"]
        rows = list(daily_list) + list(held_positions)
        grades = SU.grade_universe(panel, rows, earnings=earnings,
                                   in_theme_tickers=in_theme_tickers(valen),
                                   spy_close=spy if len(spy) else None)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": str(exc), "graded": 0}
    for r in rows:
        tk = r.get("ticker")
        if tk in grades:
            r["setups"] = grades[tk]
    missing = sorted({r.get("ticker") for r in rows if r.get("ticker")} - set(grades))
    return {"status": "live", "graded": len(grades),
            "not_graded": missing,
            "earnings_history": bool(earnings),
            "in_theme": in_theme_tickers(valen) is not None}
