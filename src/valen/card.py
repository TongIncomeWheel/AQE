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


THEME_READ_BOTH = "BOTH_LISTS"
THEME_READ_WEEK = "WEEK_ONLY"
THEME_READ_MONTH = "MONTH_ONLY"
THEME_READ_NONE = "NOT_IN_THEME"

THEME_READ_TEXT = {
    THEME_READ_BOTH: "In-theme: top 5 this week AND this month",
    THEME_READ_WEEK: "In-theme: top 5 this week only (new money arriving)",
    THEME_READ_MONTH: "In-theme: top 5 this month only (resting or fading)",
    THEME_READ_NONE: "Not in-theme",
}
_THEME_READ_ORDER = [THEME_READ_BOTH, THEME_READ_WEEK, THEME_READ_MONTH, THEME_READ_NONE]


def theme_reads(rows: list[dict], top_n: int = S.THEME_TOP_N) -> list[dict]:
    """Piece 02's written rule applied to every group: rank on the 1-week
    list and the 1-month list separately, mark the top `top_n` on each.
    A group on either list is in-theme; which list(s) it is on is the
    read (both = real leadership, week only = new money, month only = a
    leader resting or ending). Returns new dicts with `rank_1w`,
    `rank_1m`, `theme_read`, `theme_read_text`, ordered both-lists first,
    then week-only, month-only, the rest -- each block by 1-week return.
    A group missing a return gets no rank on that list, never a guess."""
    def _ranks(key):
        have = sorted((r for r in rows if r.get(key) is not None),
                      key=lambda r: r[key], reverse=True)
        return {id(r): i for i, r in enumerate(have, 1)}
    r1w, r1m = _ranks("ret_1w_pct"), _ranks("ret_1m_pct")
    out = []
    for r in rows:
        w, m = r1w.get(id(r)), r1m.get(id(r))
        in_w = w is not None and w <= top_n
        in_m = m is not None and m <= top_n
        read = (THEME_READ_BOTH if in_w and in_m else THEME_READ_WEEK if in_w
                else THEME_READ_MONTH if in_m else THEME_READ_NONE)
        out.append({**r, "rank_1w": w, "rank_1m": m, "theme_read": read,
                    "theme_read_text": THEME_READ_TEXT[read]})
    out.sort(key=lambda r: (_THEME_READ_ORDER.index(r["theme_read"]),
                            -(r.get("ret_1w_pct") if r.get("ret_1w_pct") is not None
                              else float("-inf"))))
    return out


def rotation_table(valen: dict) -> list[dict]:
    """Same rows, sorted by thrust (this week's push) — the map between
    the market and the stock, per piece 03."""
    return (valen.get("groups") or {}).get("rotation") or []


def history_rows(valen: dict) -> list[dict]:
    """Current vs 5-sessions-ago (~1wk) vs 21-sessions-ago (~1mo) — the
    turning-point read (piece 01). Every value here is independently
    recomputed from price history (src/valen/history.py), never a stored
    snapshot, so it is available from the day this ships, no backfill
    wait. GEX is left out on purpose: its gamma read is a snapshot of
    TODAY's options open interest, with no panel to recompute against."""
    hist = valen.get("history") or {}
    d5, d1m = hist.get("5d_ago") or {}, hist.get("1mo_ago") or {}
    vv = (valen.get("extension") or {}).get("vix_vix3m") or {}
    t2108 = (valen.get("breadth") or {}).get("pct_above_40d") or {}
    spy_atr = ((valen.get("extension") or {}).get("index_atr") or {}).get("SPY") or {}

    def _row(label, now_val, key, kind):
        return {"label": label, "kind": kind, "now": now_val,
               "5d_ago": d5.get(key), "1mo_ago": d1m.get(key)}

    return [
        _row("Stance", (valen.get("stance") or {}).get("stance"), "stance", "word"),
        _row("Trend regime", (valen.get("trend") or {}).get("regime"), "regime", "word"),
        _row("VIX / VIX3M", vv.get("ratio"), "vix_vix3m", "number"),
        _row("T2108", t2108.get("value") if t2108.get("status") == "OK" else None,
            "t2108", "number"),
        _row("SPY ATRs above 50-day", spy_atr.get("atr_multiple_from_50d"),
            "spy_atr_mult", "number"),
    ]


def dial_history_dots(valen: dict) -> list[dict]:
    """Where the stance dial sat 1 and 5 sessions ago — a PM ask
    (2026-10-02) to compare today's needle against recent history at a
    glance, right on the dial, rather than reading a separate table. Reuses
    `history` (src/valen/history.py) — same independently-recomputed-each-
    time, no-backfill-wait property as history_rows() above. Skips a
    lookback whose stance read is missing (DEGRADED/UNAVAILABLE) rather
    than placing a dot for a reading that doesn't exist."""
    hist = valen.get("history") or {}
    out = []
    for tag, label, key in (("1D", "1D ago", "1d_ago"), ("5D", "5D ago", "5d_ago")):
        stance = (hist.get(key) or {}).get("stance")
        if stance:
            out.append({"tag": tag, "label": label, "stance": stance})
    return out


def freshness(valen: dict) -> dict:
    return {"as_of": (valen.get("plain_english") or {}).get("as_of"),
            "basis": valen.get("basis", "eod")}


# ---------------------------------------------------------------------------
# Parts 2-6 (pieces 04-20) — plain pass-throughs with safe defaults, same
# "render from the artifact alone" rule. `run_playbook()` (daily.py) writes
# these keys AFTER Part 1's own write; a page reading an artifact from
# between those two writes (or an older one predating this pass) gets a
# clean empty shape here, never a KeyError.
# ---------------------------------------------------------------------------

def selection_block(valen: dict) -> dict:
    sel = valen.get("selection") or {}
    return {"relative_strength": sel.get("relative_strength") or [],
           "funnel": sel.get("funnel") or [],
           "no_buy_list": sel.get("no_buy_list") or []}


def playbook_missing_reason(valen: dict) -> str | None:
    """None when Parts 2-6 were computed for this artifact; otherwise the
    reason, so the page says "not computed" instead of rendering empty
    lists that read like a quiet market (CLAUDE.md: a failed read must be
    LOUD, never silently empty)."""
    st = valen.get("playbook_status") or {}
    if st.get("status") == "OK" or ("house" in valen and not st):
        return None
    if st.get("reason"):
        return st["reason"]
    return ("this saved read has Part 1 only. Parts 2-6 need the finished "
            "daily export and are added by the nightly pipeline (Step 8a-1b)")


def house_block(valen: dict) -> dict:
    h = valen.get("house") or {}
    status = h.get("status") or {}
    graded = status.get("status") == "live"
    return {"setups": h.get("setups") or [],
            "computed": playbook_missing_reason(valen) is None,
            "graded": graded,
            "grade_reason": None if graded else (status.get("reason")
                                                or "setups were not graded for this read"),
            "not_graded": status.get("not_graded") or [],
            "earnings_history": status.get("earnings_history"),
            "in_theme": status.get("in_theme")}


def execution_block(valen: dict) -> dict:
    ex = valen.get("execution") or {}
    return {"entries": ex.get("entries") or [],
           "stop_breaches": ex.get("stop_breaches") or []}


def gex_block(valen: dict) -> dict:
    return valen.get("gex") or {"status": "UNAVAILABLE", "reason": "not computed"}


def crown_cockpit_block(valen: dict) -> dict:
    """The five Crown-sourced cockpit readings (crown_cockpit.py) — same
    pass-through shape as gex_block() above, one entry per widget, each
    independently OK/UNAVAILABLE."""
    cc = valen.get("crown_cockpit") or {}
    default = {"status": "UNAVAILABLE", "reason": "not computed"}
    return {k: cc.get(k) or default for k in
           ("breadth_range", "cta_crowding", "dispersion", "divergence", "cot")}


def _cockpit_tag(reading: dict, key: str) -> str | None:
    if reading.get("status") != "OK":
        return None
    v = reading.get(key)
    return str(v).replace("_", " ").title() if v else None


def crown_cockpit_gauge_rows(valen: dict) -> list[dict]:
    """Breadth range / CTA crowding / dispersion as bulb traffic lights — the
    SAME `_bulb_gauge_html` primitive VALEN's own Part 1 instruments
    already use (theme.py), just three more `kind`s. `tag` carries the
    run's own category word (regime/bias/state) next to a label that
    otherwise stays fixed, so the `kind`-keyed explainer still applies."""
    cc = crown_cockpit_block(valen)
    br, cta, disp = cc["breadth_range"], cc["cta_crowding"], cc["dispersion"]
    return [
        {"label": "Breadth — 12mo range position", "kind": "breadth_range_pct",
         "value": br.get("range_pct"), "tag": _cockpit_tag(br, "regime")},
        {"label": "Trend-fund crowding", "kind": "cta_crowding_pct",
         "value": cta.get("flip_risk_pct"), "tag": _cockpit_tag(cta, "bias")},
        {"label": "Dispersion", "kind": "dispersion_pct",
         "value": disp.get("percentile_pct"), "tag": _cockpit_tag(disp, "state")},
    ]


def crown_divergence_row(valen: dict) -> dict:
    """How many of Crown's 8 named divergence checks are lit, plus which
    ones — theme.py renders this as a stat tile with tag pills, not a
    gauge (there is no meaningful 0-100 scale for a small fixed count)."""
    return crown_cockpit_block(valen)["divergence"]


def crown_cot_row(valen: dict) -> dict:
    """Which futures markets large speculators are crowded into (COT,
    straight from cftc.gov) — theme.py renders this as tag pills."""
    return crown_cockpit_block(valen)["cot"]


def management_block(valen: dict) -> dict:
    mg = valen.get("management") or {}
    return {"held_facts": mg.get("held_facts") or [],
           "streak": mg.get("streak") or {"status": "UNAVAILABLE",
                                          "reason": "not computed"}}
