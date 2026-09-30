"""VALEN Management — the VIV handbook's Part 5 ("After you move in":
pieces 17-19, trim/trail/adds) and the factual half of Part 6 ("Keeping
the roof on": piece 20's streak context). This module computes NO
decision anywhere — CLAUDE.md's "AQE makes no decisions, no sizing" rules
out trim/trail/add/cut-size recommendations entirely. What it surfaces is
the raw facts a PM/AIC would actually look at to make that call
themselves: unrealised P&L, an approximate R-multiple, distance from the
current stop, days held, and (piece 20) the closed-trade win/loss streak.
The handbook's own sizing rule for piece 20, and all of pieces 14/15,
ship as quoted doctrine text in the UI instead of a computed number.

Piece 21 ("progress over perfection") is not represented here at all —
it is the PM's own practice, not something a scanner can compute or
display as a reading.

R-MULTIPLE CAVEAT: AQE has no persisted, frozen entry-time risk (entry
price minus the ORIGINAL stop at the moment of entry) — bracket_engine
recomputes the stop fresh against today's price every run. The
`r_multiple` this module returns is therefore an APPROXIMATION using the
position's CURRENT stop as the risk denominator, not the handbook's own
"take profit as a multiple of your original risk" definition. It is
always returned with `r_multiple_is_approx: True` so no reader mistakes
it for the real thing.

Pure functions of already-loaded held_positions rows — no file access,
no engine imports."""

from __future__ import annotations

from datetime import date, datetime


def _days_held(trade_date_str: str | None, today: date | None = None) -> int | None:
    if not trade_date_str:
        return None
    try:
        d0 = datetime.strptime(trade_date_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    d1 = today or date.today()
    return max(0, (d1 - d0).days)


def held_position_facts(held_row: dict, today: date | None = None) -> dict:
    entry = held_row.get("entry")
    live = held_row.get("live_px")
    sl = held_row.get("held_sl")

    r_multiple = None
    if entry is not None and sl is not None and live is not None:
        risk_per_share = abs(entry - sl)
        if risk_per_share > 0:
            r_multiple = round((live - entry) / risk_per_share, 2)

    dist_from_stop_pct = None
    if live is not None and sl is not None and live != 0:
        dist_from_stop_pct = round((live - sl) / live * 100, 2)

    return {
        "ticker": held_row.get("ticker"),
        "entry": entry,
        "live_px": live,
        "held_sl": sl,
        "qty": held_row.get("qty"),
        "unreal_usd": held_row.get("unreal_usd"),
        "days_held": _days_held(held_row.get("trade_date"), today),
        "r_multiple": r_multiple,
        "r_multiple_is_approx": r_multiple is not None,
        "dist_from_stop_pct": dist_from_stop_pct,
        "structure_shift": held_row.get("structure_shift"),
    }


def held_book_facts(held_positions: list[dict], today: date | None = None) -> list[dict]:
    return [held_position_facts(h, today) for h in held_positions]
