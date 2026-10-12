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
    try:
        unr = unr_last_day(panel, rows)
        for r in rows:
            if r.get("ticker") in unr:
                r.update(unr[r["ticker"]])
    except Exception:  # noqa: BLE001 -- the column must never take the setups grading down
        unr = {}
    missing = sorted({r.get("ticker") for r in rows if r.get("ticker")} - set(grades))
    return {"status": "live", "graded": len(grades), "unr_graded": len(unr),
            "not_graded": missing,
            "earnings_history": bool(earnings),
            "in_theme": in_theme_tickers(valen) is not None}


def unr_last_day(panel, rows: list[dict]) -> dict[str, dict]:
    """The U&R COLUMN (PM 2026-10-12): for each name, did an undercut and rally
    happen on the LAST completed trading day? Same Valen levels and same flush
    rule as the live alert (src/alerts/live_unr.py), evaluated on the last bar.

      MET    a support level was undercut and the last session CLOSED back above
             it (that is the reclaim day), shallow dip, EMA21 rising.
      SETUP  a level was undercut within the last 3 sessions and the name closed
             the last session still under it: the reclaim day is the NEXT session.
      NO     no shallow dip under a support level.
      NA     not enough price history to judge (never a silent NO).

    Returns {ticker: {unr_status, unr_note, unr_as_of, unr_level}}; a ticker
    absent from the panel is absent here, not 'NO'."""
    from src.alerts import live_unr as LU
    want = {r.get("ticker") for r in rows if r.get("ticker")}
    out: dict[str, dict] = {}
    cols = ["date", "open", "high", "low", "close", "volume"]
    for tk, df in panel[panel["ticker"].isin(want)].groupby("ticker", sort=False):
        df = df.sort_values("date").tail(400)
        as_of = str(df["date"].iloc[-1])[:10]
        if len(df) < LU.MIN_HISTORY + 1:
            out[tk] = {"unr_status": "NA", "unr_note": "not enough daily price history",
                       "unr_as_of": as_of, "unr_level": None}
            continue
        last = df.iloc[-1]
        r = LU.evaluate(df.iloc[:-1][cols].to_dict("records"), spot=float(last["close"]),
                        day_low=float(last["low"]))
        st = r["status"]
        if st == LU.ARMED:
            hit = next((a for a in r["armed"] if a.get("reclaimed")), None)
            a0 = hit or r["armed"][0]
            nm = LU.PLAIN_LEVEL.get(a0["name"], a0["name"])
            when = "on the last session" if a0["when"] == "today" else a0["when"]
            if hit:
                note = (f"Dipped below the {nm} ({a0['level']:.2f}) {when} and closed back "
                        f"above it. Reclaim day.")
                status = "MET"
            else:
                note = (f"Dipped below the {nm} ({a0['level']:.2f}) {when} and closed "
                        f"{abs(a0['spot_pct']):.1f}% under it. The reclaim day is the next session.")
                status = "SETUP"
            out[tk] = {"unr_status": status, "unr_note": note, "unr_as_of": as_of,
                       "unr_level": a0["level"]}
        elif st == LU.NOT_MET:
            out[tk] = {"unr_status": "NO",
                       "unr_note": LU.PLAIN_REASON.get(r.get("reason"), r.get("reason") or "no setup"),
                       "unr_as_of": as_of, "unr_level": None}
        else:
            out[tk] = {"unr_status": "NA",
                       "unr_note": LU.PLAIN_REASON.get(r.get("reason"), r.get("reason") or "no data"),
                       "unr_as_of": as_of, "unr_level": None}
    return out


def unr_summary(daily_list: list[dict]) -> dict:
    """Longlist + Elder names by U&R status on the last completed trading day."""
    lists = [r for r in daily_list if r.get("on_longlist") or r.get("on_elder")]
    names = lambda st: sorted(r["ticker"] for r in lists if r.get("unr_status") == st)  # noqa: E731
    as_of = max((r.get("unr_as_of") for r in daily_list if r.get("unr_as_of")), default=None)
    return {"as_of": as_of, "basis": "last completed trading day, Longlist + Elder names",
            "met": names("MET"), "setup": names("SETUP"),
            "n_checked": sum(1 for r in lists if r.get("unr_status") in ("MET", "SETUP", "NO")),
            "n_not_checked": sum(1 for r in lists if r.get("unr_status") == "NA")}
