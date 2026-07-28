#!/usr/bin/env python3
"""Portfolio metrics snap (D-85) — the real computation behind post-market's old aspirational
"metrics file" line. Fills the journal's existing (previously-unused) `metrics` key: exposure,
leverage, NAV-beta, VaR, sector concentration, stop audit.

WHY IT LIVES IN THE JOURNAL, NOT A SEPARATE FILE (PM: "the portfolio check figures should be
inside the journal so that's a proper snapshot of the portfolio, not just list of positions"):
`contracts/journal.schema.json` already had a required `metrics` object — this tool is what
finally writes something real into it, in place, on the SAME journal file post-market already
wrote this run. No second file to keep in sync.

WHAT IT NEEDS THAT ONLY THE HELD-BOOK LOOP CAN SUPPLY: exposure/leverage/beta/sector all need
per-position sector + beta + vol, which come from AQE, not the broker. Post-market runs BEFORE
premarket pulls AQE each day, so this tool ALWAYS computes off whatever `aqe_snapshot` is
currently attached to each position (see tools/held_book_refresh.py) — usually refreshed at
yesterday's premarket, not today's. That is by design, not a bug: `computed_from_aqe_dated`
and `mixed_vintage` say so explicitly rather than pretending the numbers are same-day.

Reuses tools/calculators/var_parametric.py for the VaR math (net_beta_dollar and
gross_exposure_usd come straight out of that call) — no second implementation of the same
single-factor model.

Deterministic (law 4) — no model, no network.

Usage:
  python3 tools/portfolio_metrics.py compute --journal today.json [--out today.json]
  python3 tools/portfolio_metrics.py selftest
"""
import json
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "calculators"))
import var_parametric  # noqa: E402 — reuse, do not reimplement the VaR model


def build_positions(open_positions):
    """Split held positions into (usable, excluded). Usable = has an aqe_snapshot (so beta/sector
    are real, not guessed). exposure_usd uses mark_price when available, else falls back to entry
    cost basis, flagged `unmarked` so a reader knows it is a cost-basis proxy, not a live mark."""
    usable, excluded = [], []
    for p in open_positions or []:
        snap = p.get("aqe_snapshot")
        if not snap:
            excluded.append(p.get("ticker"))
            continue
        qty = float(p.get("qty", 0) or 0)
        price = p.get("mark_price")
        unmarked = price is None
        if price is None:
            price = p.get("entry", 0)
        usable.append({
            "ticker": p.get("ticker"),
            "exposure_usd": qty * float(price or 0),
            "beta": snap.get("beta"),
            "ann_vol_pct": snap.get("ann_vol_pct"),
            "sector": snap.get("sector") or "UNKNOWN",
            "as_of": p.get("aqe_snapshot_as_of"),
            "unmarked": unmarked,
        })
    return usable, excluded


def stop_audit(open_positions):
    tally = {"MATCH": 0, "MISMATCH": 0, "MISSING": 0}
    for p in open_positions or []:
        m = p.get("stop_match")
        if m in tally:
            tally[m] += 1
        else:
            tally["MISSING"] += 1
    return tally


def sector_concentration(usable, gross_exposure):
    by_sector = {}
    for p in usable:
        by_sector[p["sector"]] = by_sector.get(p["sector"], 0.0) + abs(p["exposure_usd"])
    if not gross_exposure:
        return {s: 0.0 for s in by_sector}
    return {s: round(100.0 * v / gross_exposure, 2) for s, v in by_sector.items()}


def compute(journal):
    dyncap = (journal.get("dyncap") or {}).get("value")
    open_positions = journal.get("open_positions", []) or []
    usable, excluded_no_aqe_data = build_positions(open_positions)

    var_positions = [{"ticker": p["ticker"], "exposure_usd": p["exposure_usd"],
                       "beta": p["beta"] or 0, "ann_vol_pct": p["ann_vol_pct"] or 0}
                      for p in usable if p["beta"] is not None and p["ann_vol_pct"] is not None]
    missing_beta_or_vol = [p["ticker"] for p in usable
                           if p["beta"] is None or p["ann_vol_pct"] is None]
    var_result = var_parametric.parametric_var(var_positions, dyncap=dyncap) if dyncap else \
        {"note": "dyncap unset — VaR not computed (BL-030 fail-closed, same rule as sizing)"}

    gross = var_result.get("gross_exposure_usd", sum(abs(p["exposure_usd"]) for p in var_positions))
    net_beta_dollar = var_result.get("net_beta_dollar", 0.0)
    leverage = round(gross / dyncap, 3) if dyncap else None
    nav_beta = round(net_beta_dollar / dyncap, 3) if dyncap else None

    as_of_dates = sorted({p["as_of"] for p in usable if p["as_of"]})
    unmarked_tickers = [p["ticker"] for p in usable if p["unmarked"]]

    return {
        "as_of": journal.get("date"),
        "gross_exposure_usd": round(gross, 2),
        "leverage": leverage,
        "net_beta_dollar": round(net_beta_dollar, 2) if net_beta_dollar is not None else None,
        "nav_beta": nav_beta,
        "sector_concentration_pct": sector_concentration(usable, gross),
        "stop_audit": stop_audit(open_positions),
        "var": var_result,
        "computed_from_aqe_dated": as_of_dates[-1] if len(as_of_dates) == 1 else as_of_dates,
        "mixed_vintage": len(as_of_dates) > 1,
        "excluded_no_aqe_data": excluded_no_aqe_data,
        "missing_beta_or_vol": missing_beta_or_vol,
        "unmarked_cost_basis_proxy": unmarked_tickers,
        "note": "positions in excluded_no_aqe_data/missing_beta_or_vol are OMITTED from "
                "leverage/nav_beta/sector/VaR, not defaulted to zero — see held_book_refresh.py",
    }


# --------------------------------------------------------------------------- CLI
def cmd_compute(args):
    with open(args.journal) as fh:
        journal = json.load(fh)
    journal["metrics"] = compute(journal)
    out = args.out or args.journal
    with open(out, "w") as fh:
        json.dump(journal, fh, indent=1)
    print(json.dumps(journal["metrics"], indent=1))


def selftest(_args=None):
    journal = {
        "date": "2026-07-28",
        "dyncap": {"value": 100000, "one_r": 1000},
        "open_positions": [
            {"ticker": "AAA", "qty": 100, "entry": 50.0, "mark_price": 55.0, "stop_match": "MATCH",
             "aqe_snapshot": {"sector": "Tech", "beta": 1.2, "ann_vol_pct": 35.0},
             "aqe_snapshot_as_of": "2026-07-27"},
            {"ticker": "BBB", "qty": 50, "entry": 20.0, "stop_match": "MISMATCH",   # no mark_price -> unmarked
             "aqe_snapshot": {"sector": "Tech", "beta": 0.8, "ann_vol_pct": 25.0},
             "aqe_snapshot_as_of": "2026-07-27"},
            {"ticker": "CCC", "qty": 30, "entry": 100.0, "stop_match": "MISSING",
             "aqe_snapshot": None},   # never refreshed -> excluded
        ],
        "closed_trades": [], "metrics": {},
    }
    m = compute(journal)
    # AAA: 100*55=5500, BBB unmarked -> 50*20=1000 (cost-basis proxy). Gross ~6500 depending on var_parametric rounding.
    assert m["excluded_no_aqe_data"] == ["CCC"], m
    assert m["unmarked_cost_basis_proxy"] == ["BBB"], m
    assert m["stop_audit"] == {"MATCH": 1, "MISMATCH": 1, "MISSING": 1}, m["stop_audit"]
    assert m["sector_concentration_pct"]["Tech"] == 100.0, m["sector_concentration_pct"]
    assert m["leverage"] is not None and m["leverage"] > 0
    assert m["computed_from_aqe_dated"] == "2026-07-27"
    assert m["mixed_vintage"] is False
    assert "var_95_1m_usd" in m["var"], m["var"]

    # mixed vintage: BBB refreshed a different day -> flagged, not hidden
    journal["open_positions"][1]["aqe_snapshot_as_of"] = "2026-07-20"
    m2 = compute(journal)
    assert m2["mixed_vintage"] is True
    assert m2["computed_from_aqe_dated"] == ["2026-07-20", "2026-07-27"]

    # dyncap unset -> fail-closed, no fabricated leverage/VaR
    journal["dyncap"]["value"] = None
    m3 = compute(journal)
    assert m3["leverage"] is None and m3["nav_beta"] is None
    assert "note" in m3["var"]

    print("portfolio_metrics selftest OK — excludes positions with no AQE snapshot rather than "
          "guessing, flags cost-basis-proxy exposure when unmarked, flags mixed-vintage AQE data "
          "instead of hiding it, VaR reused from var_parametric.py, fail-closed with no dynCap.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Portfolio metrics snap (D-85, deterministic)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compute")
    c.add_argument("--journal", required=True)
    c.add_argument("--out")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        selftest()
    elif a.cmd == "compute":
        cmd_compute(a)


if __name__ == "__main__":
    main()
