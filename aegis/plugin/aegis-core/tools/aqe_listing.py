#!/usr/bin/env python3
"""aqe_listing.py -- "is this name AQE-listed, and what are its AQE scores" (PM 2026-11-16, Standard Scan).

The PM wants to prove whether the committee WITHOUT the AQE gate has more edge than AQE. Every name the committee names has to be
read against AQE in the same words, everywhere (brief, Cards, levels, ledger):

    AQE-listed: Longlist, Elder . SC_MOMENTUM 85.7 . Flow 90 . Energy 70 . Structure 64 . MP 71 . Elder 10 . Pipeline rank 12 . QS odds 52%
    AQE-listed: none (not on the Longlist, Elder or QS list) . SC_MOMENTUM 61.0 . ...
    AQE score not available (not in the export, not in the universe rows)

A name outside the export is read from the universe rows (a full scored record for every universe name, before any AQE gate). A name in
neither prints "AQE score not available" LOUDLY, never blank. PTRS is not an export field, so it is never claimed (the line says nothing
about it; `NOT_IN_EXPORT` names it for the write-up). Pure functions: no network, no model, no file access except `load_rows`.
"""
import json
import os
import sys

DISCLOSURE = ("Seat screens use AQE structure and momentum-phase fields, not AQE list membership or scores.")
LISTS = (("on_longlist", "Longlist"), ("on_elder", "Elder"), ("on_qs", "QS"))
SCORES = (("sc_momentum", "SC_MOMENTUM"), ("flow", "Flow"), ("energy", "Energy"), ("structure", "Structure"), ("mp", "MP"),
          ("elder", "Elder score"), ("pipe_rank", "Pipeline rank"))
NOT_IN_EXPORT = ("ptrs",)
PLAIN = {"SC_MOMENTUM": "AQE momentum score", "Flow": "Flow", "Energy": "Energy", "Structure": "Structure", "MP": "Momentum phase score", "Elder score": "Elder score", "Pipeline rank": "AQE rank"}


def _num(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def qs_odds(row):
    """QS probability of touching +2 ATR14 within 20 sessions, or None when QS did not score the name."""
    o = ((row or {}).get("qs") or {}).get("odds") if isinstance((row or {}).get("qs"), dict) else None
    return _num((o or {}).get("p")) if isinstance(o, dict) else None


def listing(ticker, export_by_ticker, universe_by_ticker=None):
    """-> {ticker, aqe_listed, aqe_lists, in_daily_list, scores, qs_odds, source, line}. `export_by_ticker` is {ticker: daily_list row}."""
    r = (export_by_ticker or {}).get(ticker)
    src = "export"
    if r is None:
        r = (universe_by_ticker or {}).get(ticker)
        src = "universe_rows"
    if r is None:
        return {"ticker": ticker, "aqe_listed": None, "aqe_lists": None, "in_daily_list": False, "scores": {}, "qs_odds": None,
                "source": "unavailable", "line": "AQE score not available (the name is not in the export and not in the universe rows)",
                "plain_line": "AQE score not available (the name is not in the export and not in the universe rows)"}
    in_dl = ticker in (export_by_ticker or {}) and not bool((r or {}).get("universe_only"))
    lists = [w for k, w in LISTS if r.get(k)]
    scores = {w: _num(r.get(k)) for k, w in SCORES if _num(r.get(k)) is not None}
    odds = qs_odds(r)
    head = ("AQE-listed: " + ", ".join(lists)) if lists else ("AQE-listed: none (" + ("on the AQE daily list but on no Longlist, Elder or QS list" if in_dl
                                                                               else "below the AQE shortlist gate") + ")")
    bits = [head] + [f"{w} {v:g}" for w, v in scores.items()] + [f"QS odds {odds * 100:.0f}%" if odds is not None else "QS: not scored"]
    if not scores:
        bits.append("AQE score not available (the record carries no AQE scores)")
    # the same facts in plain words for the Cards page (its plain-words gate rejects raw engine names such as SC_MOMENTUM and QS)
    phead = head.replace("QS", "Quiet Strength")
    pbits = [phead] + [f"{PLAIN.get(w, w)} {v:g}" for w, v in scores.items()] + [f"Quiet Strength odds {odds * 100:.0f}%" if odds is not None else "Quiet Strength: not scored"]
    if not scores:
        pbits.append("AQE score not available (the record carries no AQE scores)")
    return {"ticker": ticker, "aqe_listed": bool(lists), "aqe_lists": "|".join(lists) if lists else "none", "in_daily_list": in_dl,
            "scores": scores, "qs_odds": odds, "source": src, "line": " . ".join(bits), "plain_line": " . ".join(pbits)}


def load_rows(export_path, universe_path=None):
    """-> (export_by_ticker, universe_by_ticker). The export carries daily_list + held_positions; the universe file is optional."""
    ex = json.load(open(export_path, encoding="utf-8"))
    by = {r["ticker"]: r for r in (ex.get("daily_list") or []) if r.get("ticker")}
    for h in ex.get("held_positions") or []:
        by.setdefault(h.get("ticker"), h)
    ub = {}
    if universe_path and os.path.exists(universe_path):
        u = json.load(open(universe_path, encoding="utf-8"))
        ub = {r["ticker"]: r for r in (u["rows"] if isinstance(u, dict) else u) if r.get("ticker")}
    return by, ub


def table_md(tickers, export_by_ticker, universe_by_ticker=None):
    """The code-built markdown table every brief/Cards write-up pastes: Ticker | AQE-listed | scores."""
    L = ["| Ticker | AQE-listed | AQE scores |", "|---|---|---|"]
    for t in tickers:
        x = listing(t, export_by_ticker, universe_by_ticker)
        if x["source"] == "unavailable":
            L.append(f"| **{t}** | AQE score not available | not in the export or the universe rows |")
            continue
        head, _, rest = x["line"].partition(" . ")
        L.append(f"| **{t}** | {head.replace('AQE-listed: ', '')} | {rest or 'AQE score not available'} |")
    return "\n".join(L)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--export", required=True)
    ap.add_argument("--universe-rows", default=None)
    ap.add_argument("--consensus", default=None, help="consensus.json: every name in it gets a row (default: --tickers)")
    ap.add_argument("--tickers", default=None, help="comma list")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    by, ub = load_rows(a.export, a.universe_rows)
    if a.consensus:
        tk = [c["ticker"] for c in json.load(open(a.consensus, encoding="utf-8"))]
    else:
        tk = [t for t in (a.tickers or "").split(",") if t]
    md = table_md(tk, by, ub) + "\n\n" + DISCLOSURE + "\n"
    if a.out:
        open(a.out, "w", encoding="utf-8").write(md)
    print(md)
    miss = [t for t in tk if listing(t, by, ub)["source"] == "unavailable"]
    if miss:
        print(f"WARNING: AQE score not available for {', '.join(miss)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
