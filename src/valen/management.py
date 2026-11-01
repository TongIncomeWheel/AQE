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


# ---------------------------------------------------------------------------
# PM 2026-11-01 ("build", weather-spec item 6, items 1-2). Both are READINGS plus the handbook quoted as
# doctrine. Neither tells the PM to trim, trail, add or cut -- CLAUDE.md: AQE makes no decisions.
# ---------------------------------------------------------------------------
MANAGE_RULE_DOCTRINE = ("Trade management changes when the 8-day average of net new highs crosses back "
                        "above the 20-day. -- The VIV System (quoted doctrine, not an Aegis rule)")
TRIM_TRAIL_DOCTRINE = {
    "trim": "Trim into strength -- take some profit while the stock is still going up, not after it rolls over. (piece 17)",
    "trail": "Trail the rest -- one moving average, daily closes only. (piece 18)",
    "add": "Adds and pyramids -- add to a winner only when it proves itself again, never to average down. (piece 19)",
}


def manage_note(valen_artifact: dict | None) -> dict:
    """The handbook's one management switch, read from Part 1's own net-high/low row. A READING:
    which side of the switch the market is on today, with the numbers, and the doctrine quoted.
    UNAVAILABLE (with the reason) when the row is not served -- never a silent neutral."""
    br = ((valen_artifact or {}).get("breadth") or {})
    nhnl = br.get("net_high_low") if isinstance(br, dict) else None
    if not isinstance(nhnl, dict):
        return {"status": "UNAVAILABLE", "reason": "net_high_low row not served by Part 1",
                "doctrine": MANAGE_RULE_DOCTRINE, "is_decision": False}
    if nhnl.get("status") != "OK":
        return {"status": "UNAVAILABLE", "reason": nhnl.get("reason") or "net_high_low not OK",
                "doctrine": MANAGE_RULE_DOCTRINE, "is_decision": False}
    green = bool(nhnl.get("green"))
    a8, a20 = nhnl.get("avg8"), nhnl.get("avg20")
    state = "ABOVE" if green else "BELOW"
    note = (f"Net new highs: the 8-day average ({a8}) is {'above' if green else 'below'} the 20-day ({a20}) -- "
            + ("breakouts are being rewarded; the handbook's management switch is on the open-trades-can-run side."
               if green else "breakouts are not being rewarded; the handbook's management switch is on the tighten side.")
            + " A reading on AQE's panel, not a whole-market count.")
    return {"status": "OK", "state": state, "green": green, "avg8": a8, "avg20": a20,
            "latest_net": nhnl.get("latest_net"), "population": nhnl.get("population"),
            "note": note, "doctrine": MANAGE_RULE_DOCTRINE, "is_decision": False}


def trim_trail_facts(held_row: dict, today: date | None = None) -> dict:
    """Per held name: the facts a PM looks at against pieces 17-19, beside the doctrine quoted. Facts only --
    R multiple (approximate, see module docstring), whether the first target has printed, where price sits
    against its 20-day line (the one-average trail the handbook names), the stop distance."""
    f = held_position_facts(held_row, today)
    live, tp1, ma20 = held_row.get("live_px"), held_row.get("held_tp1"), held_row.get("ma_20")
    pct_vs_ma20 = (round((live - ma20) / ma20 * 100, 2) if isinstance(live, (int, float)) and isinstance(ma20, (int, float)) and ma20 else None)
    f.update({
        "tp1": tp1,
        "tp1_printed": (bool(live >= tp1) if isinstance(live, (int, float)) and isinstance(tp1, (int, float)) else None),
        "ma_20": ma20, "pct_vs_ma_20": pct_vs_ma20,
        "above_ma_20": (pct_vs_ma20 > 0 if pct_vs_ma20 is not None else None),
        "r_multiple_2r_or_more": (f["r_multiple"] >= 2.0 if isinstance(f.get("r_multiple"), (int, float)) else None),
        "doctrine": TRIM_TRAIL_DOCTRINE, "is_decision": False,
        "gaps": [k for k, v in (("held_tp1", tp1), ("ma_20", ma20), ("held_sl", held_row.get("held_sl"))) if v is None],
    })
    return f


def trim_trail_rows(held_positions: list[dict], today: date | None = None) -> list[dict]:
    return [trim_trail_facts(h, today) for h in held_positions]
