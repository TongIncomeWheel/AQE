#!/usr/bin/env python3
"""held_view.py -- ONE view of the held book (PM 2026-11-11), shared by the cards.json strings, the levels file, the brief table and the Cards page.

The BRACKET step skips held names by design, so nothing downstream carried a worked-out stop for the PM's own book. Rule now: for every held name carry AQE's
worked-out stop as a REFERENCE (render-only, never an order, never a size), taken in this order and labelled with its basis:
  1. bracket.stop            when the structural bracket is valid
  2. extension_bracket.stop  when the extension bracket is available
  3. bracket.atr_fallback_stop
A REAL broker stop order, when one exists, replaces the reference. With no stop order at the broker the row status is NO STOP AT BROKER and the action is SET STOP.
P&L in R: R per share = entry - stop used; open R = (mark - entry) / R per share. A second figure divides the dollar P&L by the committee's fixed 1R
(aegis_fund.md one_r_usd, $620), clearly labelled and never a size.

    python3 held_view.py table --export aqe_daily_export.json --broker-stops broker_stops.json [--out held_table.md]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STOP_ORDER = ("bracket", "extension_bracket", "atr_fallback")      # the precedence, one place


def one_r_usd():
    """The committee's fixed 1R, read from aegis_fund.md through fund_config (never retyped)."""
    for d in (HERE, os.path.join(HERE, "..", "..", "..", "tools")):
        p = os.path.join(d, "fund_config.py")
        if os.path.exists(p):
            sys.path.insert(0, d)
            try:
                import fund_config
                v = fund_config.one_r_usd()
                if v:
                    return float(v)
            except Exception:  # noqa: BLE001 - fall through to the declared gap
                pass
            finally:
                sys.path.pop(0)
    return None


def reference_stop(row):
    """-> (stop, basis) from a held export row, or (None, 'no worked-out stop')."""
    b = row.get("bracket") or {}
    e = row.get("extension_bracket") or {}
    for kind in STOP_ORDER:
        if kind == "bracket" and b.get("valid") and b.get("stop") is not None:
            return float(b["stop"]), "structural bracket"
        if kind == "extension_bracket" and e.get("available") and e.get("stop") is not None:
            return float(e["stop"]), "extension bracket, " + ("lower of the continuation-window low and 1 daily range under entry" if not e.get("stop_basis") else "lower of the window low and 1 daily range under entry")
        if kind == "atr_fallback" and b.get("atr_fallback_stop") is not None:
            return float(b["atr_fallback_stop"]), "1 ATR fallback"
    return None, "no worked-out stop"


def held_view(export, broker_stops=None, one_r=None):
    """One dict per held position, in the export's order. Never raises on a missing field: a figure that cannot be computed is None, said so, never a guess."""
    bs = ((broker_stops or {}).get("positions")) or {}
    one_r = one_r if one_r is not None else one_r_usd()
    out = []
    for h in export.get("held_positions") or []:
        t = h.get("ticker")
        hb = h.get("held_book") or {}
        pick = lambda k: hb.get(k) if hb.get(k) is not None else h.get(k)      # candidate-set rows carry the position in held_book (their top-level `entry` is AQE's price); export held rows carry it at the top level
        entry, mark, qty, pnl = pick("entry"), pick("live_px"), pick("qty"), pick("unreal_usd")
        if pnl is None and None not in (entry, mark, qty):
            pnl = round((mark - entry) * qty, 2)
        ref, basis = reference_stop(h)
        b = bs.get(t) or {}
        real = b.get("stop")
        used, used_basis = (real, "broker stop order") if real is not None else (ref, basis)
        r_ps = (entry - used) if (entry is not None and used is not None and entry > used) else None
        open_r = round((mark - entry) / r_ps, 2) if (r_ps and mark is not None) else None
        out.append({"ticker": t, "qty": qty, "entry": entry, "mark": mark, "pnl_usd": pnl,
                    "broker_stop": real, "broker_stop_status": (f"broker stop {real}" if real is not None else "NO STOP AT BROKER"),
                    "reference_stop": ref, "reference_basis": basis, "stop_used": used, "stop_used_basis": used_basis,
                    "r_per_share": round(r_ps, 4) if r_ps else None, "open_r": open_r,
                    "pnl_in_committee_1r": (round(pnl / one_r, 2) if (pnl is not None and one_r) else None), "committee_1r_usd": one_r,
                    "action": ("SET-STOP" if real is None else None)})
    return out


def _f(v, fmt):
    return "n/a" if v is None else fmt.format(v)


def render_table(rows, actions=None):
    """The ONE held-book table (brief sections 3 and 9A, and the Cards 'Your book'): the facts are code-built; the ACTION column is the default (SET-STOP when no stop order
    exists) unless `actions` {ticker: word} carries the committee's own call for a name that already has a stop."""
    actions = actions or {}
    one_r = next((r["committee_1r_usd"] for r in rows if r.get("committee_1r_usd")), None)
    L = ["| Name | Qty | Entry | Mark | P&L $ | P&L in R (own stop) | P&L in committee 1R" + (f" (${one_r:,.0f}, not a size)" if one_r else "") + " | Broker stop status | Worked-out stop (basis) | Action |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        stop = (f"{r['reference_stop']:.2f} ({r['reference_basis']}; reference only)" if r["reference_stop"] is not None else "none worked out")
        if r["broker_stop"] is not None:
            stop = f"{r['broker_stop']:.2f} (broker order); AQE reference " + (f"{r['reference_stop']:.2f}" if r["reference_stop"] is not None else "none")
        act = r["action"] or actions.get(r["ticker"]) or "HOLD"
        L.append("| " + " | ".join([
            f"**{r['ticker']}**", _f(r["qty"], "{:g}"), _f(r["entry"], "{:.2f}"), _f(r["mark"], "{:.2f}"), _f(r["pnl_usd"], "{:+,.2f}"),
            _f(r["open_r"], "{:+.2f}R"), _f(r["pnl_in_committee_1r"], "{:+.2f}"), r["broker_stop_status"], stop, act]) + " |")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("table")
    t.add_argument("--export", required=True); t.add_argument("--broker-stops", default=None); t.add_argument("--out", default=None)
    t.add_argument("--actions", default=None, help="optional JSON {ticker: action word} for names that already have a stop")
    a = ap.parse_args(argv)
    ex = json.load(open(a.export))
    bs = json.load(open(a.broker_stops)) if a.broker_stops and os.path.exists(a.broker_stops) else None
    rows = held_view(ex, bs)
    md = render_table(rows, json.load(open(a.actions)) if a.actions else None) if rows else "The book is FLAT: no positions are held."
    if a.out:
        open(a.out, "w").write(md + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
