"""VALEN card renderer — from the artifact alone.

No data libraries, no file access, no engine imports. Renders ONLY from the
dict this module is handed (the same `valen` block that ships in the export
JSON), so every claim the card makes is reconstructible from that one file —
the same rule tests/test_qs_card.py enforces on qs_card.py. Streamlit pages
call these functions; they do not compute anything themselves either.
"""

from __future__ import annotations

from . import spec as S


def stance_banner(valen: dict) -> dict:
    stance = (valen.get("stance") or {})
    word = stance.get("stance") or "—"
    return {
        "word": word.replace("_", " "),
        "status": stance.get("status", "UNAVAILABLE"),
        "reason": stance.get("reason"),
    }


def headline(valen: dict) -> str:
    return (valen.get("plain_english") or {}).get("headline") or "No read available."


def trend_rows(valen: dict) -> list[dict]:
    trend = valen.get("trend") or {}
    rows = (trend.get("rows") or {})
    out = []
    for sym in ("SPY", "QQQ"):
        r = rows.get(sym) or {}
        out.append({
            "symbol": sym,
            "last_price": r.get("last_price"),
            "daily_buy_signal": r.get("daily_buy_signal"),
            "weekly_buy_signal": r.get("weekly_buy_signal"),
            "above_rising_5d": r.get("above_rising_5d"),
            "basis": r.get("basis", "unavailable"),
        })
    return out


def regime_word(valen: dict) -> str:
    return (valen.get("trend") or {}).get("regime") or "UNKNOWN"


def extension_rows(valen: dict) -> list[dict]:
    """`kind` tells the page which gauge shape to draw — a continuous scale
    with the handbook's own frozen band thresholds, never invented ones."""
    ext = valen.get("extension") or {}
    idx = ext.get("index_atr") or {}
    rows = []
    for sym in ("SPY", "QQQ"):
        r = idx.get(sym) or {}
        rows.append({"label": f"{sym} ATRs above 50-day", "kind": "atr_multiple",
                     "value": r.get("atr_multiple_from_50d"),
                     "flag": r.get("stretched")})
    vv = ext.get("vix_vix3m") or {}
    rows.append({"label": "VIX / VIX3M", "kind": "vix_vix3m",
                 "value": vv.get("ratio"), "flag": vv.get("uncertainty")})
    return rows


def breadth_rows(valen: dict) -> list[dict]:
    """Every row is either a real reading or the honest UNAVAILABLE shape —
    never silently dropped, so a reader can tell "not computed" from "zero".

    `section` separates the handbook's two distinct pieces that both read
    from `breadth`: "checklist" is the six yes/or-no rows (piece 01's pass/
    fail lights), "instrument" is the four tracked values (T2108, the 5-day/
    10-day count, Net High/Low, big movers) — they overlap on purpose (the
    5-day count is legitimately both a checklist line AND its own tracked
    instrument in the handbook, page 6). Rendered as LEDs vs gauges
    respectively — never merged into one list of flat text rows again."""
    breadth = valen.get("breadth") or {}

    def _get(key):
        return breadth.get(key) or {"status": "UNAVAILABLE", "reason": "not computed"}

    out = []

    daily = _get("daily_count_green")
    out.append({"label": "Today's count green", "section": "checklist", "kind": "bool",
               "status": daily.get("status"),
               "value": daily.get("value") if daily.get("status") == "OK" else None,
               "reason": daily.get("reason")})

    five = _get("five_day_count")
    five_ok = five.get("status") == "OK"
    out.append({"label": "5-day count (1.00+ to pass)", "section": "checklist",
               "kind": "ratio_led", "status": five.get("status"),
               "value": five.get("value") if five_ok else None,
               "flag": (five.get("value") or 0) >= S.CHECKLIST_5D_COUNT_MIN if five_ok else None,
               "reason": five.get("reason")})

    month = _get("monthly_risers")
    out.append({"label": "Monthly big risers (25%+ up-count)", "section": "checklist",
               "kind": "count", "status": month.get("status"),
               "value": month.get("value") if month.get("status") == "OK" else None,
               "reason": month.get("reason")})

    nhnl = _get("net_high_low")
    nhnl_ok = nhnl.get("status") == "OK"
    out.append({"label": "Net High/Net Low (8d vs 20d)", "section": "checklist",
               "kind": "bool", "status": nhnl.get("status"),
               "value": nhnl.get("green") if nhnl_ok else None,
               "display": (f"{nhnl['avg8']} vs {nhnl['avg20']}" if nhnl_ok else None),
               "reason": nhnl.get("reason")})

    # The four instruments (gauges) -- T2108 and the 5-day/10-day ratios
    # again, this time as their own tracked values, not pass/fail lines.
    t2108 = _get("pct_above_40d")
    out.append({"label": "T2108 — stocks above their 40-day line",
               "section": "instrument", "kind": "pct_0_100", "status": t2108.get("status"),
               "value": t2108.get("value") if t2108.get("status") == "OK" else None,
               "reason": t2108.get("reason")})
    out.append({"label": "5-day up/down 4% count", "section": "instrument",
               "kind": "mover_ratio", "status": five.get("status"),
               "value": five.get("value") if five_ok else None,
               "reason": five.get("reason")})
    ten = _get("ten_day_count")
    out.append({"label": "10-day up/down 4% count", "section": "instrument",
               "kind": "mover_ratio", "status": ten.get("status"),
               "value": ten.get("value") if ten.get("status") == "OK" else None,
               "reason": ten.get("reason")})
    return out


def watch_for_lines(valen: dict) -> list[str]:
    return (valen.get("plain_english") or {}).get("watch_for") or []


def caveats(valen: dict) -> list[str]:
    return (valen.get("plain_english") or {}).get("caveats") or []


def neighbourhood_lines(valen: dict) -> list[str]:
    """The Neighbourhood column's bullets — piece 02's own reading rules
    applied to the ranked groups: real leadership (on both the week and
    month lists), leading from highs vs merely bouncing off lows."""
    groups = valen.get("groups") or {}
    if groups.get("status") != "OK":
        return []
    by_name = {g["name"]: g for g in (groups.get("groups") or [])}
    tl = groups.get("theme_leaders") or {}
    week, month = tl.get("one_week") or [], tl.get("one_month") or []
    both = [by_name[g]["display_name"] for g in week if g in month][:5]
    rotation = groups.get("rotation") or []
    leading = [g["display_name"] for g in rotation
              if g.get("rotation_state") == "LEADING"][:5]
    off_floor = [g["display_name"] for g in rotation
                 if g.get("rotation_state") == "OFF_THE_FLOOR"][:5]
    lines = []
    if both:
        lines.append("On both the week and month lists (real leadership): "
                     + ", ".join(both))
    if leading:
        lines.append("Leading from their own highs, not just bouncing: "
                     + ", ".join(leading))
    if off_floor:
        lines.append("Strong numbers but still well off their highs "
                     "(a bounce, not leadership yet): " + ", ".join(off_floor))
    return lines


def theme_leaders_table(valen: dict) -> list[dict]:
    """Every group, ranked three ways at once — Since Open / 1 Week /
    1 Month. Plain rows; the page builds whatever table it wants from them."""
    return (valen.get("groups") or {}).get("groups") or []


def rotation_table(valen: dict) -> list[dict]:
    """Same rows, sorted by thrust (this week's push) — the map between
    the market and the stock, per piece 03."""
    return (valen.get("groups") or {}).get("rotation") or []


def freshness(valen: dict) -> dict:
    return {"as_of": (valen.get("plain_english") or {}).get("as_of"),
            "basis": valen.get("basis", "eod")}
