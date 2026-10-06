"""VALEN House — the VIV handbook's Part 3 (pieces 08-12), the five setups.

2026-10-05 (PM sign-off on docs/AQE_VALEN_HOUSE_SETUPS_PROPOSAL.md): the
2026-09-30 version relabelled DETECT fields as setups (mover_subtype as a
"momentum breakout", a 5-day/20-day range ratio as a "VCP", ...). Measured
against the handbook those proxies broke its own "common mistakes" lists --
98 of 130 names tagged as momentum breakouts. They are RETIRED. The DETECT
fields still ride on daily_list as context; they are no longer called setups.

Now:
  * src/valen/setups_daily.attach_setup_grades() runs inside the export
    build (drive_sync), so every daily_list row and held position carries
    its own `setups` list -- the checklist-graded output of setups.py. The
    committee, the alert cards and this page read the SAME grades.
  * `house_setups()` is the page's reader: rows with at least one grade,
    ordered by status. Pure; reads only what the export carries.
"""

from __future__ import annotations

from .setups import STATUS_ORDER


def house_setups(daily_list: list[dict], held_positions: list[dict] | None = None) -> list[dict]:
    """Every name carrying at least one grade, best status first. Held
    positions are included (piece 12's warnings exist for them)."""
    held_positions = held_positions or []
    held_tk = {h.get("ticker") for h in held_positions}
    seen: dict[str, dict] = {}
    for r in list(daily_list) + list(held_positions):
        tk = r.get("ticker")
        if not tk or tk in seen or not r.get("setups"):
            continue
        seen[tk] = {"ticker": tk, "held": tk in held_tk or bool(r.get("held")),
                    "on_longlist": bool(r.get("on_longlist")),
                    "on_elder": bool(r.get("on_elder")),
                    "on_qs": bool(r.get("on_qs")), "grades": r["setups"]}

    def _rank(row):
        best = min((STATUS_ORDER.index(g["status"]) for g in row["grades"]
                    if g.get("status") in STATUS_ORDER), default=99)
        return (best, row["ticker"])
    return sorted(seen.values(), key=_rank)
