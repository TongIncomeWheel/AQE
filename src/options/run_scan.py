"""CLI runner for the AQE Options scanner + calculator (recommend-only).

The `aqe-option-scanner` skill fetches option chains from the IBKR MCP (spot +
strike + expiry + IV + bid/ask + OI per contract), writes them to a contracts JSON,
then calls this runner. Keeping the formatting here (not hand-typed by the model)
makes the output deterministic.

    python -m src.options.run_scan --contracts /tmp/puts.json --mode scan [--top 15]
    python -m src.options.run_scan --contracts /tmp/puts.json --mode spreads [--width 5]
    python -m src.options.run_scan --contracts /tmp/puts.json --mode calc \
                                   --ticker AAPL --strike 310

Contracts JSON = a list of {ticker, spot, strike, dte, iv, bid, ask, oi, volume,
right} (right defaults to PUT), or an object {contracts:[...], r:.., q:..}.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config as C
from . import scanner as SC


def _load(path: str):
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(obj, dict):
        return obj.get("contracts", []), obj.get("r"), obj.get("q")
    return obj, None, None


def _f(x, nd=2, dash="—"):
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else dash


def _pct(x, nd=1, dash="—"):
    return f"{x*100:.{nd}f}%" if isinstance(x, (int, float)) else dash


def _print_scan(rows, top, rejected_n):
    print(f"\nCSP theta scan — {len(rows)} pass the wheel filters "
          f"({rejected_n} rejected). Ranked by {C.SCAN_RANK_KEY}, top {top}:\n")
    hdr = (f"{'TICKER':7} {'STRIKE':>7} {'DTE':>4} {'DELTA':>6} {'DIST':>6} {'CREDIT':>7} "
           f"{'ANN.YLD':>8} {'POP':>6} {'CUSH':>6} {'θ/day':>7} {'EDGE':>7} {'CONTR':>5}")
    print(hdr)
    print("-" * len(hdr))
    for m in rows[:top]:
        print(f"{str(m.get('ticker')):7} {_f(m.get('strike')):>7} {str(m.get('dte')):>4} "
              f"{_f(m.get('abs_delta'), 3):>6} {_pct(m.get('distance_to_strike_pct')):>6} "
              f"{_f(m.get('credit_per_contract')):>7} "
              f"{_pct(m.get('annual_yield')):>8} {_pct(m.get('pop')):>6} "
              f"{_pct(m.get('downside_cushion')):>6} {_f(m.get('theta_credit_day')):>7} "
              f"{_f(m.get('edge_vs_model')):>7} {str(m.get('max_contracts')):>5}")
    b = SC.best(rows)
    if b:
        print(f"\nBest wheel entry: SELL {b['ticker']} {_f(b['strike'])}P {b['dte']}DTE "
              f"— collect ${_f(b.get('credit_per_contract'))}/contract, "
              f"{_pct(b.get('annual_yield'))} annualised on ${_f(b.get('collateral'))} "
              f"collateral, {_pct(b.get('pop_not_assigned'))} not-assigned, "
              f"breakeven {_f(b.get('breakeven'))}.")


def _print_spreads(rows, top):
    print(f"\nPut credit spreads — {len(rows)} clear min RRR. "
          f"Ranked by annualised yield, top {top}:\n")
    hdr = (f"{'TICKER':7} {'SHORT':>7} {'LONG':>7} {'DTE':>4} {'CREDIT':>7} "
           f"{'MAXLOSS':>8} {'RRR':>6} {'ANN.YLD':>8} {'POP':>6} {'CONTR':>5}")
    print(hdr)
    print("-" * len(hdr))
    for s in rows[:top]:
        print(f"{str(s.get('ticker')):7} {_f(s.get('short_strike')):>7} "
              f"{_f(s.get('long_strike')):>7} {str(s.get('dte')):>4} "
              f"{_f(s.get('net_credit')):>7} {_f(s.get('max_loss')):>8} "
              f"{_f(s.get('rrr'), 2):>6} {_pct(s.get('annual_yield')):>8} "
              f"{_pct(s.get('pop')):>6} {str(s.get('max_contracts')):>5}")
    b = SC.best(rows, "rrr")
    if b:
        print(f"\nBest R:R combo: {b['ticker']} {_f(b['short_strike'])}/"
              f"{_f(b['long_strike'])}P {b['dte']}DTE — "
              f"${_f(b.get('max_profit'))} profit vs ${_f(b.get('max_loss'))} risk "
              f"(R:R {_f(b.get('rrr'),2)}), {_pct(b.get('pop'))} POP.")


def _print_calc(detail):
    g = detail.get("greeks", {})
    csp = detail.get("csp", {})
    print(f"\nCalculator — {detail.get('ticker')} {detail.get('right')} "
          f"(IV {_pct(detail.get('iv_used'), 1)})\n")
    print(f"  BS fair value   : {_f(detail.get('fair_value'))}"
          f"   market mid: {_f(detail.get('market_mid'))}")
    print(f"  Greeks          : Δ {_f(g.get('delta'),3)}  Γ {_f(g.get('gamma'),4)}  "
          f"Θ/day {_f(g.get('theta_day'),3)}  ν {_f(g.get('vega'),3)}  ρ {_f(g.get('rho'),3)}")
    if csp.get("valid"):
        print(f"\n  Cash-secured put economics:")
        print(f"    credit/contract : ${_f(csp.get('credit_per_contract'))}   "
              f"collateral: ${_f(csp.get('collateral'))}")
        print(f"    static yield    : {_pct(csp.get('static_yield'))}   "
              f"annualised: {_pct(csp.get('annual_yield'))}")
        print(f"    breakeven       : {_f(csp.get('breakeven'))}   "
              f"downside cushion: {_pct(csp.get('downside_cushion'))}")
        print(f"    POP (above BE)  : {_pct(csp.get('pop'))}   "
              f"not assigned: {_pct(csp.get('pop_not_assigned'))}")
        print(f"    theta credit/day: ${_f(csp.get('theta_credit_day'))}   "
              f"edge vs model: ${_f(csp.get('edge_vs_model'))}")


def run(contracts_path, mode, top, ticker, strike, width, fill, r, q, overrides):
    contracts, jr, jq = _load(contracts_path)
    r = jr if r is None else r
    q = jq if q is None else q
    # default right = PUT
    for c in contracts:
        c.setdefault("right", "PUT")

    if mode == "calc":
        pick = None
        for c in contracts:
            if (ticker is None or (c.get("ticker") or "").upper() == ticker) and \
               (strike is None or abs((c.get("strike") or -1) - strike) < 1e-6):
                pick = c
                break
        if pick is None:
            print("No matching contract for --ticker/--strike.")
            return 1
        _print_calc(SC.calculator(pick, r=r, q=q, fill=fill))
        return 0

    if mode == "spreads":
        rows = SC.build_put_spreads(contracts, width=width, r=r, q=q, fill=fill)
        _print_spreads(rows, top)
        return 0

    # default: CSP theta scan
    res = SC.scan_csps(contracts, r=r, q=q, fill=fill, **overrides)
    _print_scan(res["passed"], top, len(res["rejected"]))
    print("\nRecommend-only — sizing/decision is the AIC's; AQE computes the numbers.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AQE options scanner + calculator")
    ap.add_argument("--contracts", required=True, help="contracts JSON (from IBKR MCP)")
    ap.add_argument("--mode", default="scan", choices=["scan", "spreads", "calc"])
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--ticker", default=None)
    ap.add_argument("--strike", type=float, default=None)
    ap.add_argument("--width", type=float, default=C.SPREAD_DEFAULT_WIDTH)
    ap.add_argument("--fill", default="mid", choices=["mid", "bid", "fair"])
    ap.add_argument("--r", type=float, default=None, help="risk-free override")
    ap.add_argument("--q", type=float, default=None, help="dividend yield override")
    # scan-filter overrides (optional)
    ap.add_argument("--delta-min", type=float, default=None)
    ap.add_argument("--delta-max", type=float, default=None)
    ap.add_argument("--dte-min", type=int, default=None)
    ap.add_argument("--dte-max", type=int, default=None)
    ap.add_argument("--min-pop", type=float, default=None)
    ap.add_argument("--min-annual-yield", type=float, default=None)
    a = ap.parse_args(argv)

    overrides = {k: v for k, v in {
        "delta_min": a.delta_min, "delta_max": a.delta_max,
        "dte_min": a.dte_min, "dte_max": a.dte_max,
        "min_pop": a.min_pop, "min_annual_yield": a.min_annual_yield,
    }.items() if v is not None}

    return run(a.contracts, a.mode, a.top, (a.ticker or None) and a.ticker.upper(),
               a.strike, a.width, a.fill, a.r, a.q, overrides)


if __name__ == "__main__":
    raise SystemExit(main())
