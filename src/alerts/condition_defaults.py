"""AQE-default conditions — widening the 15-min condition cards beyond the
rows PMA wrote `conditions` for (PM ruling 2026-10-04: universe = the
committee book + AQE Longlist/Elder).

Two kinds of row get a synthesized `conditions` block, in the SAME schema
PMA ships so the evaluator, state machine, ledger and card never know the
difference — except for the `aqe_default: True` tag the card renders:

  1. a committee row (ADVANCE / HOLD-FOR-CONDITIONS; WATCH only behind the
     flag) that arrived with no `conditions`;
  2. a current Longlist/Elder name that is not in the committee book at all.

The default criteria are AQE's own, said so on the card, never dressed up
as committee words:

  buy      an hourly candle closes above the breakout line -- `last_pivot_high`
           if it still sits above the last close, else the prior bar's high
           (so a name already through its pivot needs a NEW intraday break,
           not a card at 09:45 for a move that already happened)
  confirm  volume >= CONDITION_DEFAULT_VOL_X x normal for the time of day
  chase    daily close above the line + CONDITION_DEFAULT_CHASE_PCT
  exits    none on an unheld name -- a watch name's exit line is never a card
           (PM 2026-10-03), so there is nothing to synthesize for it

A name whose line sits more than CONDITION_DEFAULT_MAX_LEVEL_PCT above the
close is skipped: an hourly close 13% away is not something to pull 15-min
bars for every cycle. Nothing here decides or sizes anything.
"""

from __future__ import annotations

from . import config as C

DEFAULT_CLASS = {"longlist": "AQE_LONGLIST", "elder": "AQE_ELDER", "brief_lists": "AQE_LIST"}
LIST_LABEL = "AQE list, not a committee pick"
_SUFFIX = " (AQE default)"


def _n(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _sources() -> set[str]:
    return {s.strip().lower() for s in (C.CONDITION_DEFAULT_SOURCES or "").split(",") if s.strip()}


def brief_list_names(export: dict | None) -> dict[str, list[str]]:
    """{ticker: [list names it is on]} for the brief's lists (Elder, AQE, Detect lens, Swing pivot), in the SAME definitions as section 5b of the brief
    (aegis/output/pma/test_cards/v3/lists_vs_committee.py): Elder top N = on_elder by Elder score then AQE rank; AQE top N
    = by the export `rank`; Detect-lens top N = lens_ranking.ranked in its stored order. Read from the export; no new data."""
    dl = (export or {}).get("daily_list") or []
    rank = lambda r: r.get("rank") if isinstance(r.get("rank"), int) else 10 ** 6
    elder = sorted([r for r in dl if r.get("on_elder")], key=lambda r: (-(r.get("elder") or 0), rank(r)))
    aqe = sorted([r for r in dl if isinstance(r.get("rank"), int)], key=lambda r: r["rank"])
    known = {r.get("ticker") for r in dl}
    lens = [x["ticker"] for x in ((export or {}).get("lens_ranking") or {}).get("ranked") or [] if x.get("ticker") in known]
    # 4th list (PM 2026-11-05, "anything in the brief is bracketed and watched"): names AT their daily swing high in a weekly+daily HH/HL
    # uptrend = the export's swing_pivot true (src/valen/swing_pivot.py), by AQE rank. Absent on an export built before the column existed.
    swing = [r["ticker"] for r in aqe if r.get("swing_pivot") is True]
    out: dict[str, list[str]] = {}
    for name, rows in (("Elder", [r["ticker"] for r in elder[:C.BRIEF_LIST_ELDER_N]]),
                       ("AQE", [r["ticker"] for r in aqe[:C.BRIEF_LIST_AQE_N]]),
                       ("Detect lens", lens[:C.BRIEF_LIST_LENS_N]),
                       ("Swing pivot", swing[:C.BRIEF_LIST_SWING_N])):
        for tk in rows:
            out.setdefault(tk, []).append(name)
    return out


def breakout_line(rec: dict) -> float | None:
    """The level a default buy is judged against, or None when the row has
    nothing usable above its own close."""
    entry = _n(rec.get("entry"))
    if entry is None or entry <= 0:
        return None
    lph = _n((rec.get("last_pivot_high") or {}).get("price"))
    if lph is not None and lph > entry:
        return lph
    pbh = _n(rec.get("prior_bar_high"))
    if pbh is not None and pbh >= entry:
        return pbh
    return None


def _levels_block(rec: dict, line: float, stop_override: float | None = None) -> dict | None:
    """stop/targets for the card's Bracket line -- read from the export's
    own bracket block, never recomputed. None when no stop exists."""
    b = rec.get("bracket") or {}
    stop = _n(b.get("stop")) if b.get("valid") else None
    if stop_override is not None:
        stop = stop_override                       # the lane's own stop (continuation: the extension bracket's)
    if stop is None:
        stop = _n(b.get("atr_fallback_stop"))
    if stop is None:
        return None
    # The bracket's targets IN ITS OWN ORDER (TP1, TP2, TP3), none dropped:
    # the card labels them by position and measures each one's R from the
    # entry line, so filtering "above the line" here would silently turn TP2
    # into "TP1" and break the R:R-to-TP2 yardstick (PM 2026-10-06).
    tps = [_n((t or {}).get("price")) for t in (b.get("targets") or [])][:3]
    return {"stop": round(stop, 2),
            "tp": [round(p, 2) if p is not None else None for p in tps]}


def build_default_conditions(rec: dict, apply_distance_cap: bool = True, line_override: float | None = None,
                             plain_override: str | None = None) -> dict | None:
    """The synthesized block for one export row, or None when the row can't
    be armed (no line above the close, or -- unless `apply_distance_cap` is
    False -- the line is too far away). The brief's list names pass False:
    PM 2026-11-04, the 2-5%-under-the-line coiling names are the ones he wants."""
    line = line_override if line_override is not None else breakout_line(rec)
    entry = _n(rec.get("entry"))
    if line is None or entry is None:
        return None
    if apply_distance_cap and 100.0 * (line / entry - 1.0) > C.CONDITION_DEFAULT_MAX_LEVEL_PCT:
        return None
    chase = round(line * (1.0 + C.CONDITION_DEFAULT_CHASE_PCT / 100.0), 2)
    vol_x = C.CONDITION_DEFAULT_VOL_X
    return {
        "shared": {
            "buy": [{"w": "h1_close_above", "level": round(line, 2),
                     "plain": (plain_override or f"an hourly candle closes above {line:.2f}") + _SUFFIX}],
            "confirm": [{"w": "vol_x_ge", "x": vol_x,
                         "plain": f"volume at least {vol_x:g}x normal for the time of day{_SUFFIX}"}],
            "no_shared_buy": False,
            "chase": {"w": "close_above", "level": chase,
                      "plain": f"closes above the line +{C.CONDITION_DEFAULT_CHASE_PCT:g}% {chase:.2f}{_SUFFIX}"},
        },
        "exits": [],
        "analysts": [],
    }


def build_watch_only_conditions(rec: dict) -> dict | None:
    """A brief-list name already THROUGH its pivot with no line above the close (PM 2026-11-04: it must appear on the
    digest, not vanish). There is NO buy trigger: `no_shared_buy` with no analysts can never read buy-met. The only word is
    the chase line (word trade_above: true from the first cycle, unlike close_above which waits for the final cycle), set at the level the name already traded past (its last confirmed pivot high, else just under the
    close), so the existing EXTENDED card fires once and the card says 'no entry line'. Nothing here decides anything."""
    entry = _n(rec.get("entry"))
    if entry is None or entry <= 0:
        return None
    lph = _n((rec.get("last_pivot_high") or {}).get("price"))
    level = lph if lph is not None and 0 < lph < entry else entry * 0.995
    level = round(level, 2)
    return {
        "shared": {"buy": [], "confirm": [], "no_shared_buy": True,
                   "chase": {"w": "trade_above", "level": level,
                             "plain": f"already traded above {level:.2f}{_SUFFIX}"}},
        "exits": [], "analysts": [],
    }


def apply_deal_pinned(rows: list[dict], export: dict | None) -> list[dict]:
    """R44 (PM 2026-11-04): a name with ma_status PENDING_TARGET never has a buy trigger armed. Any committee ADVANCE / HOLD-FOR-CONDITIONS row
    or AQE-default row for such a name is replaced by a LABEL-ONLY row (no buy word; one card saying it is deal-pinned). HELD rows are left
    alone: a position keeps its exit and stop cards. Rows with no ma_status in the export are untouched (no claim either way)."""
    byt = {r.get("ticker"): r for r in ((export or {}).get("daily_list") or [])}
    out = []
    for r in rows:
        rec = byt.get(r.get("ticker"))
        if rec and rec.get("ma_status") == "PENDING_TARGET" and r.get("class") != "HELD":
            cond = build_watch_only_conditions(rec)
            if cond:
                nr = {k: v for k, v in r.items() if k not in ("conditions", "levels", "lane", "lane_label", "lane_note")}
                nr.update(conditions=cond, deal_pinned=True, watch_only=True, aqe_default=bool(r.get("aqe_default")))
                nr["ma_status"], nr["ma_note"] = rec.get("ma_status"), rec.get("ma_note")
                out.append(nr)
                continue
        out.append(r)
    return out


def _as_row(rec: dict, klass: str, conditions: dict, stop_override: float | None = None) -> dict:
    buy = conditions["shared"]["buy"]
    line = _n(buy[0]["level"]) if buy else None
    row = {"ticker": rec["ticker"], "class": klass, "atr_14d": rec.get("atr_14d"),
           "conditions": conditions, "aqe_default": True}
    if klass == DEFAULT_CLASS["brief_lists"]:
        row["aqe_list"] = True
    if not buy:
        row["watch_only"] = True
    levels = _levels_block(rec, line if line is not None else _n(rec.get("entry")), stop_override) if (line is not None or not buy) else None
    if levels:
        row["levels"] = levels
    return row


def synthesize_rows(export: dict | None, pma_doc: dict | None) -> list[dict]:
    """Rows to watch under AQE-default conditions this session. Never
    mutates `pma_doc`; committee rows that get filled are shallow copies."""
    if not C.CONDITION_DEFAULTS_ENABLED or not export:
        return []
    by_ticker = {r.get("ticker"): r for r in (export.get("daily_list") or []) if r.get("ticker")}
    held = {r.get("ticker") for r in (export.get("held_positions") or [])}
    out: list[dict] = []
    covered: set[str] = set()

    # 1. committee rows that arrived without conditions
    fill_classes = {"ADVANCE", "HOLD_FOR_CONDITIONS"}
    if C.CONDITION_DEFAULTS_INCLUDE_WATCH:
        fill_classes.add("WATCH")
    from . import pma_levels as _PMA
    latest = [r for r in (pma_doc or {}).get("rows") or [] if _PMA.is_latest_run_row(pma_doc, r)]
    for r in latest:
        tk = r.get("ticker")
        if not tk:
            continue
        if r.get("conditions"):
            covered.add(tk)
            continue
        if r.get("class") not in fill_classes or tk in covered:
            continue
        rec = by_ticker.get(tk)
        if not rec:
            continue
        cond = build_default_conditions(rec)
        if cond:
            row = dict(r)
            row["conditions"] = cond
            row["aqe_default"] = True
            row.setdefault("atr_14d", rec.get("atr_14d"))
            if not row.get("levels"):
                lv = _levels_block(rec, _n(cond["shared"]["buy"][0]["level"]))
                if lv:
                    row["levels"] = lv
            out.append(row)
            covered.add(tk)

    # 2. names outside the committee book: the brief's three lists (default) and/or the older whole Longlist / Elder
    want = _sources()
    # A supplemental pass's committee-dropped / unslated names are brief-list watch names (PM 2026-11-05): "anything in the brief is
    # bracketed and watched". They are WATCH rows in the levels file (information only there); here they are watched under AQE defaults.
    bw = {r.get("ticker"): r for r in latest if r.get("class") == "WATCH" and r.get("brief_watch") and r.get("ticker")}
    pma_tickers = {r.get("ticker") for r in latest if r.get("ticker") not in bw}
    on_lists = brief_list_names(export) if "brief_lists" in want else {}
    for _tk in bw:
        on_lists.setdefault(_tk, []).append("Swing pivot")
    for tk, rec in by_ticker.items():
        if tk in covered or tk in pma_tickers or tk in held or rec.get("held"):
            continue
        src = ("brief_lists" if tk in on_lists
               else "longlist" if rec.get("on_longlist") and "longlist" in want
               else "elder" if rec.get("on_elder") and "elder" in want else None)
        if not src:
            continue
        lt = None
        if src == "brief_lists" and C.CONDITION_LANE_TRIGGERS:
            from . import lane_trigger as _LT
            lt = _LT.lane_trigger(rec)
        cond = None
        if lt and lt.get("line") is not None:
            cond = build_default_conditions(rec, apply_distance_cap=False, line_override=lt["line"], plain_override=lt["plain"])
        if not cond:
            cond = build_default_conditions(rec, apply_distance_cap=(src != "brief_lists"))
        if not cond and src == "brief_lists":
            cond = build_watch_only_conditions(rec)          # through its pivot, no line above: watch-only, never silent
        if cond:
            row = _as_row(rec, DEFAULT_CLASS[src], cond, (lt or {}).get("stop") if (lt and lt.get("line") is not None) else None)
            if src == "brief_lists":
                row["on_lists"] = on_lists[tk]
                if tk in bw:
                    row.update(supplemental=True, supplemental_label=bw[tk].get("supplemental_label"), origin_run=bw[tk].get("origin_run"),
                               committee_result=bw[tk].get("committee_result"), committee_objections=bw[tk].get("committee_objections"))
                if lt:
                    row["lane"], row["lane_label"] = lt["lane"], lt["label"]
                    row["lane_note"] = ("trigger is this lane's own line" if lt.get("line") is not None
                                        else lt.get("note") or "generic line")
            out.append(row)
            covered.add(tk)
        if len(out) >= C.CONDITION_MAX_WATCHED:
            break
    return out


def default_tickers(export: dict | None, pma_doc: dict | None) -> set[str]:
    """Just the tickers -- so engine.py can add them to the quote fetch
    before the cycle runs (the strength gate in monitored() would otherwise
    leave single-lens names without a quote)."""
    return {r["ticker"] for r in synthesize_rows(export, pma_doc)}
