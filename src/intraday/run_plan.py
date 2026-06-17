"""CLI runner for the Intraday Momentum & Bracket layer (recommend-only).

The Claude Code `intraday-plan` skill fetches intraday 5-min bars per ticker via
the financial MCP `chart` tool, writes each array to <bars-dir>/<TICKER>.json,
then calls this runner. Keeping the formatting here (not hand-coded by the model)
makes the output deterministic.

    python -m src.intraday.run_plan --bars-dir /tmp/bars [--scope held,top_picks,edge_list]
                                    [--tickers AAPL,MSFT] [--risk 2100]
                                    [--export output/aqe_daily_export.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .plan import intraday_plan, rank_plans
from . import config as C

_TIER_RANK = {"held": 0, "top_picks": 1, "edge_list": 2, "longlist": 3, "watchlist": 4}


def build_rec_lookup(export: dict, scope: list[str]) -> dict[str, dict]:
    """One record per ticker from the requested tiers; richest tier wins."""
    recs: dict[str, dict] = {}
    if "held" in scope:
        for h in (export.get("held_positions") or []):
            tk = h.get("ticker")
            if tk:
                recs[tk] = {**h, "source": "held"}
    for tier in ("top_picks", "edge_list", "longlist", "watchlist"):
        if tier not in scope:
            continue
        for r in (export.get(tier) or []):
            tk = r.get("ticker")
            if not tk:
                continue
            cur = recs.get(tk)
            if cur is None or _TIER_RANK[tier] < _TIER_RANK.get(cur.get("source"), 9):
                recs[tk] = {**r, "source": tier}
    return recs


def _fmt_zone(z: dict) -> str:
    if not z or z.get("kind") == "stand_down":
        return "—"
    lo, hi = z.get("low"), z.get("high")
    kind = z.get("kind")
    return f"{lo}–{hi} ({kind})"


def run(export_path: str, bars_dir: str, scope: list[str],
        tickers: list[str] | None, risk: float) -> int:
    export = json.loads(Path(export_path).read_text(encoding="utf-8"))
    regime = export.get("regime")
    recs = build_rec_lookup(export, scope)
    if tickers:
        recs = {t: recs[t] for t in tickers if t in recs}

    plans = []
    missing = []
    for tk, rec in recs.items():
        bf = Path(bars_dir) / f"{tk}.json"
        if not bf.exists():
            missing.append(tk)
            continue
        try:
            bars = json.loads(bf.read_text(encoding="utf-8"))
        except Exception:
            missing.append(tk)
            continue
        plans.append(intraday_plan(rec, bars, regime=regime, risk_budget=risk))

    plans = rank_plans(plans)

    lvl = regime.get("level") if isinstance(regime, dict) else regime
    print(f"\nAQE Intraday Plan — regime {lvl} · stop ceiling "
          f"{C.regime_stop_ceiling(regime)}% · risk ${risk:,.0f} · "
          f"{len(plans)} names\n")
    hdr = f"{'TICKER':7} {'IMS':>5} {'STATE':16} {'ACTION':10} {'ENTRY ZONE':22} {'STOP':>8} {'R:R':>5} {'SH':>5}"
    print(hdr)
    print("-" * len(hdr))
    for p in plans:
        op = p.get("operative_stop") or {}
        print(f"{p['ticker']:7} {str(p.get('ims') or '—'):>5} {p['state']:16} "
              f"{p['action']:10} {_fmt_zone(p['entry_zone']):22} "
              f"{str(op.get('price') or '—'):>8} {str(p.get('rr') or '—'):>5} "
              f"{p.get('shares', 0):>5}")

    # IBKR bracket specs for actionable names
    specs = [p for p in plans if p.get("ibkr_spec")]
    if specs:
        print("\nIBKR bracket specs (recommend-only — review before transmitting):")
        for p in specs:
            s = p["ibkr_spec"]
            print(f"  {s['symbol']}: BUY {s['quantity']} @ {s['order_type']} "
                  f"{s['entry']} | stop {s['stop']} | TP {s['take_profit']}")

    # Verdicts + an AIC prompt
    print("\nVerdicts:")
    for p in plans:
        print(f"  {p['ticker']}: {p['verdict']}")
    print("\nAIC prompt (paste to the committee):")
    enters = [p for p in plans if p["action"] in ("ENTER", "CAUTION")]
    if enters:
        lines = "; ".join(
            f"{p['ticker']} {p['state']} entry {_fmt_zone(p['entry_zone'])} "
            f"stop {(p.get('operative_stop') or {}).get('price')} R:R {p.get('rr')} "
            f"{p.get('shares')}sh" for p in enters)
        print(f"  Intraday momentum read ({lvl} regime): {lines}. "
              "Recommend entry decision + size per PTRS × regime; AQE makes no call.")
    else:
        print("  No actionable intraday setups — all names stand down.")

    if missing:
        print(f"\n(no bars for: {', '.join(missing)})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AQE intraday momentum + bracket plan")
    ap.add_argument("--export", default="output/aqe_daily_export.json")
    ap.add_argument("--bars-dir", required=True)
    ap.add_argument("--scope", default="held,top_picks,edge_list")
    ap.add_argument("--tickers", default=None)
    ap.add_argument("--risk", type=float, default=C.RISK_BUDGET)
    a = ap.parse_args(argv)
    scope = [s.strip() for s in a.scope.split(",") if s.strip()]
    tickers = [t.strip().upper() for t in a.tickers.split(",")] if a.tickers else None
    return run(a.export, a.bars_dir, scope, tickers, a.risk)


if __name__ == "__main__":
    raise SystemExit(main())
