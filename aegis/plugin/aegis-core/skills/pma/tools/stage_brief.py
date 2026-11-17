#!/usr/bin/env python3
"""stage_brief.py -- the Stage 1-4 (Weinstein) read for the committee's write-up: market, group and ticker level (PM 2026-11-17: "Stage 1-4 builds").

Pure code over the export (`stage_market` + the stamped `stage` columns of src/stages); no model, no network. It prints, for the brief and the Cards:
  * MARKET  SPY and QQQ: stage, weeks in it, and the distribution-day count against the O'Neil C2 line (the committee canon's own number: 4 in 25 sessions).
  * GROUP   the 11 GICS sector ETFs, each with its stage.
  * BREADTH the share of single names in Stage 2 and Stage 4 now vs four weeks ago.
  * TICKER  every ADVANCE / HOLD-FOR-CONDITIONS name: its stage, weeks in stage, its group's stage, the market's stage, Trend Template, Stage 2 confirmation.
A missing layer is LOUD: one line "Stage weather unavailable: <reason>", never an empty table. A stage is a READING, never a gate, a size or a disposition.

    stage_brief.py --export aqe_daily_export_wu.json --consensus consensus.json [--out stage_weather.md]
"""
import argparse
import json
import sys

STAGE_WORD = {1: "Basing", 2: "Advancing", 3: "Topping", 4: "Declining"}
VERDICTS = ("ADVANCE", "HOLD-FOR-CONDITIONS")
HEADER = "| Ticker | Stage | Weeks in stage | Group stage | Market stage | Trend Template | Stage 2 confirmed |"
HEADING = "### Stage weather"


def _w(st):
    return f"Stage {st} {STAGE_WORD[st].lower()}" if st in STAGE_WORD else "not read"


def available(ex):
    """(ok, reason). The layer is on when the export carries stage_market with status OK."""
    sm = (ex or {}).get("stage_market")
    if not isinstance(sm, dict):
        return False, "the export carries no stage read (the Stage Weather stamp did not run)"
    if sm.get("status") != "OK":
        return False, str(sm.get("reason") or "the stage read status is " + str(sm.get("status")))
    return True, None


def market_rows(ex):
    out = []
    for sym in ("SPY", "QQQ"):
        m = ((ex.get("stage_market") or {}).get("market") or {}).get(sym) or {}
        dd = m.get("distribution_days") or {}
        if m.get("status") != "OK":
            out.append({"symbol": sym, "stage": None, "weeks": None, "dd": None, "line": None, "note": m.get("reason") or "not read"})
            continue
        n, line = dd.get("count"), dd.get("canon_threshold")
        out.append({"symbol": sym, "stage": m.get("stage"), "weeks": m.get("weeks_in_stage"), "dd": n, "line": line,
                    "window": dd.get("window_sessions"), "at_line": (n is not None and line is not None and n >= line),
                    "change": bool(m.get("candidate") not in (None, m.get("stage")) or m.get("candidate_forming") not in (None, m.get("stage")))})
    return out


def group_rows(ex):
    sec = (ex.get("stage_market") or {}).get("sectors") or {}
    rows = [{"etf": t, "stage": r.get("stage"), "weeks": r.get("weeks_in_stage"), "note": None if r.get("status") == "OK" else (r.get("reason") or "not read")}
            for t, r in sorted(sec.items())]
    return sorted(rows, key=lambda r: (r["stage"] if r["stage"] else 9, r["etf"]))


def breadth_line(ex):
    b = (ex.get("stage_market") or {}).get("breadth") or {}
    if b.get("status") != "OK":
        return None
    n, f = b.get("now") or {}, b.get("four_weeks_ago") or {}
    return (f"Breadth ({n.get('n')} names on AQE's weekly panel): Stage 2 {n.get('stage_2_pct')}% now vs {f.get('stage_2_pct')}% four weeks ago; "
            f"Stage 4 {n.get('stage_4_pct')}% vs {f.get('stage_4_pct')}%.")


def name_rows(ex, tickers):
    by = {r.get("ticker"): r for r in (ex.get("daily_list") or [])}
    for h in ex.get("held_positions") or []:
        by.setdefault(h.get("ticker"), h)
    out = []
    for t in tickers:
        r = by.get(t) or {}
        d = r.get("stage_detail") or {}
        if r.get("stage") is None and not d:
            out.append({"ticker": t, "stage": None, "note": ((d.get("reason")) or "no stage read for this name (no row, or too little weekly history)")})
            continue
        out.append({"ticker": t, "stage": r.get("stage"), "weeks": r.get("stage_weeks"), "group": d.get("sector_stage"), "market": d.get("market_stage"),
                    "trend_template": r.get("trend_template"), "tt_met": r.get("trend_template_met"), "s2c": r.get("stage2_confirmed"),
                    "transition": r.get("stage_transition"), "candidate": r.get("stage_candidate")})
    return out


def picks(consensus):
    return [c["ticker"] for c in (consensus or []) if c.get("verdict") in VERDICTS]


def render_md(ex, consensus=None):
    ok, why = available(ex)
    if not ok:
        return f"{HEADING}\n\n> Stage weather unavailable: {why}\n"
    sm = ex["stage_market"]
    L = [HEADING, ""]
    if sm.get("headline"):
        L += [str(sm["headline"]), ""]
    L += ["| Market | Stage | Weeks in stage | Distribution days (25 sessions) | O'Neil line |", "|---|---|---|---|---|"]
    for m in market_rows(ex):
        if m["stage"] is None:
            L.append(f"| {m['symbol']} | not read | n/a | n/a | {m['note']} |")
            continue
        L.append(f"| {m['symbol']} | {_w(m['stage'])}{' (change in progress)' if m.get('change') else ''} | {m['weeks']} | {m['dd'] if m['dd'] is not None else 'n/a'} | "
                 f"{'at or above the line of ' + str(m['line']) if m.get('at_line') else 'under the line of ' + str(m['line']) if m['line'] is not None else 'n/a'} |")
    L += ["", "| Group (sector ETF) | Stage | Weeks in stage |", "|---|---|---|"]
    for g in group_rows(ex):
        L.append(f"| {g['etf']} | {_w(g['stage']) if g['stage'] else 'not read: ' + str(g['note'])} | {g['weeks'] if g['weeks'] is not None else 'n/a'} |")
    bl = breadth_line(ex)
    if bl:
        L += ["", bl]
    tk = picks(consensus)
    if tk:
        L += ["", HEADER, "|---|---|---|---|---|---|---|"]
        for r in name_rows(ex, tk):
            if r["stage"] is None:
                L.append(f"| **{r['ticker']}** | not read: {r.get('note')} | n/a | n/a | n/a | n/a | n/a |")
                continue
            s2 = {True: "yes", False: "no", None: "n/a"}[r["s2c"]]
            tt = f"{r['trend_template']} ({r['tt_met']} of 8)" if r.get("trend_template") else "n/a"
            L.append(f"| **{r['ticker']}** | {_w(r['stage'])}{' (' + r['transition'].lower() + ' this week)' if r.get('transition') else ''} | {r['weeks'] if r['weeks'] is not None else 'n/a'} | "
                     f"{_w(r['group']) if r.get('group') else 'n/a'} | {_w(r['market']) if r.get('market') else 'n/a'} | {tt} | {s2} |")
    L += ["", "A stage is a reading (Weinstein, weekly bars against the 30-week average), never a gate or a size."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--export", required=True)
    ap.add_argument("--consensus", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    ex = json.load(open(a.export, encoding="utf-8"))
    cons = json.load(open(a.consensus, encoding="utf-8")) if a.consensus else None
    md = render_md(ex, cons)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
