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

DEFAULT_CLASS = {"longlist": "AQE_LONGLIST", "elder": "AQE_ELDER"}
_SUFFIX = " (AQE default)"


def _n(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _sources() -> set[str]:
    return {s.strip().lower() for s in (C.CONDITION_DEFAULT_SOURCES or "").split(",") if s.strip()}


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


def _levels_block(rec: dict, line: float) -> dict | None:
    """stop/targets for the card's Bracket line -- read from the export's
    own bracket block, never recomputed. None when no stop exists."""
    b = rec.get("bracket") or {}
    stop = _n(b.get("stop")) if b.get("valid") else None
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


def build_default_conditions(rec: dict) -> dict | None:
    """The synthesized block for one export row, or None when the row can't
    be armed (no line above the close, or the line is too far away)."""
    line = breakout_line(rec)
    entry = _n(rec.get("entry"))
    if line is None or entry is None:
        return None
    if 100.0 * (line / entry - 1.0) > C.CONDITION_DEFAULT_MAX_LEVEL_PCT:
        return None
    chase = round(line * (1.0 + C.CONDITION_DEFAULT_CHASE_PCT / 100.0), 2)
    vol_x = C.CONDITION_DEFAULT_VOL_X
    return {
        "shared": {
            "buy": [{"w": "h1_close_above", "level": round(line, 2),
                     "plain": f"an hourly candle closes above {line:.2f}{_SUFFIX}"}],
            "confirm": [{"w": "vol_x_ge", "x": vol_x,
                         "plain": f"volume at least {vol_x:g}x normal for the time of day{_SUFFIX}"}],
            "no_shared_buy": False,
            "chase": {"w": "close_above", "level": chase,
                      "plain": f"closes above the line +{C.CONDITION_DEFAULT_CHASE_PCT:g}% {chase:.2f}{_SUFFIX}"},
        },
        "exits": [],
        "analysts": [],
    }


def _as_row(rec: dict, klass: str, conditions: dict) -> dict:
    line = _n(conditions["shared"]["buy"][0]["level"])
    row = {"ticker": rec["ticker"], "class": klass, "atr_14d": rec.get("atr_14d"),
           "conditions": conditions, "aqe_default": True}
    levels = _levels_block(rec, line) if line is not None else None
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
    for r in (pma_doc or {}).get("rows") or []:
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

    # 2. Longlist / Elder names outside the committee book
    want = _sources()
    pma_tickers = {r.get("ticker") for r in (pma_doc or {}).get("rows") or []}
    for tk, rec in by_ticker.items():
        if tk in covered or tk in pma_tickers or tk in held or rec.get("held"):
            continue
        src = ("longlist" if rec.get("on_longlist") and "longlist" in want
               else "elder" if rec.get("on_elder") and "elder" in want else None)
        if not src:
            continue
        cond = build_default_conditions(rec)
        if cond:
            out.append(_as_row(rec, DEFAULT_CLASS[src], cond))
            covered.add(tk)
        if len(out) >= C.CONDITION_MAX_WATCHED:
            break
    return out


def default_tickers(export: dict | None, pma_doc: dict | None) -> set[str]:
    """Just the tickers -- so engine.py can add them to the quote fetch
    before the cycle runs (the strength gate in monitored() would otherwise
    leave single-lens names without a quote)."""
    return {r["ticker"] for r in synthesize_rows(export, pma_doc)}
