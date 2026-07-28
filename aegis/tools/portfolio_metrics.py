#!/usr/bin/env python3
"""Portfolio metrics snap (D-85) — the real computation behind post-market's old aspirational
"metrics file" line. Fills the journal's existing (previously-unused) `metrics` key: exposure,
leverage, NAV-beta, VaR, sector concentration.

WHY IT LIVES IN THE JOURNAL, NOT A SEPARATE FILE (PM: "the portfolio check figures should be
inside the journal so that's a proper snapshot of the portfolio, not just list of positions"):
`contracts/journal.schema.json` already had a required `metrics` object — this tool is what
finally writes something real into it, in place, on the SAME journal file post-market already
wrote this run. No second file to keep in sync.

RISK-STAT SOURCING (PM ruling, this pass): per-position beta and annualised volatility are NOT
read from the AQE snapshot. They are computed independently from FMP price history via
tools/historical_store.py — beta(ticker) and stats(ticker), the SAME source and method already
used for the market-factor volatility inside var_parametric.py. Before this pass, beta/vol came
from AQE's own published fields while the market factor came from FMP — a mixed-source risk
number. Now the whole calculation is one consistent source: AQE is only read here for `sector` (a
classification, not a computed statistic — reading that verbatim is fine). A name with no FMP
history yet (not seeded, or under the 12-month floor) is flagged `missing_beta_or_vol` and
omitted from the risk numbers rather than guessed — same "excluded, named, never zero" rule as
everything else in this file.

CONFIRMED-ONLY BY DEFAULT: a position pulled in as `aegis_status: pending_review` (an unmatched
broker fill, conservatively risk-managed but not yet PM-confirmed as an Aegis trade — see
tools/held_book_refresh.py classify_aegis_status) is EXCLUDED from every number here, named in
`excluded_pending_review`, until the PM confirms it. The default read of this book is always
"what Aegis actually owns and has confirmed," never inflated by an unresolved fill.

WHAT IT NEEDS THAT ONLY THE HELD-BOOK LOOP CAN SUPPLY: exposure/leverage/sector need per-position
sector from AQE (see tools/held_book_refresh.py) — usually refreshed at yesterday's premarket, not
today's, because post-market runs BEFORE premarket pulls AQE each day. That is by design, not a
bug: `computed_from_aqe_dated` and `mixed_vintage` say so explicitly rather than pretending the
sector data is same-day. Beta/vol, sourced from historical_store instead, don't carry this same
lag — the store refreshes monthly, independent of the daily AQE cycle.

NO SKIP-IF-NO-CHANGE (PM: "since it is python and has no LLM tokens, it can just recalculate for
all I care since no impact"): this recomputes in full every time it's called, unconditionally. A
deterministic python function with no model or network call has nothing to save by skipping —
skipping would only ever risk showing a stale number for zero benefit.

STOP AUDIT REMOVED (PM: "you dont need to do a stop audit as its already done previous
premarket"): a stop-match tally computed here would just be re-counting values set by
YESTERDAY's premarket, stale by definition at this point in the day. The only place that
comparison is fresh is premarket's own stop-update step, right after the new floor is written —
see tools/held_book_refresh.py stop_update / skills/print-trade-journal/SKILL.md Operation 5.

Reuses tools/calculators/var_parametric.py for the VaR math (net_beta_dollar and
gross_exposure_usd come straight out of that call) — no second implementation of the same
single-factor model.

Deterministic (law 4) — no model, no network at call time (historical_store reads its own
pre-seeded local files here; it does not call FMP itself in this path).

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
import historical_store  # noqa: E402 — reuse, single source for beta/vol (FMP-backed)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from held_book_refresh import snapshot_get  # noqa: E402 — one reader for both snapshot vintages


def build_positions(open_positions, beta_fn=None, stats_fn=None):
    """Split held positions into (usable, excluded_no_aqe_data, excluded_pending_review).
    usable = aegis_status confirmed (or unset, for positions written before this field existed)
    AND has an aqe_snapshot (needed for sector — see module docstring on sourcing). Beta and
    ann_vol_pct come from beta_fn/stats_fn, which default to historical_store.beta /
    historical_store.stats and are overridable so selftest can inject fixed values without disk
    or FMP access. exposure_usd uses mark_price when available, else falls back to entry cost
    basis, flagged `unmarked` so a reader knows it is a cost-basis proxy, not a live mark."""
    beta_fn = beta_fn or historical_store.beta
    stats_fn = stats_fn or historical_store.stats
    usable, excluded_no_aqe_data, excluded_pending_review = [], [], []
    for p in open_positions or []:
        ticker = p.get("ticker")
        if p.get("aegis_status") == "pending_review":
            excluded_pending_review.append(ticker)
            continue
        snap = p.get("aqe_snapshot")
        if not snap:
            excluded_no_aqe_data.append(ticker)
            continue
        qty = float(p.get("qty", 0) or 0)
        price = p.get("mark_price")
        unmarked = price is None
        if price is None:
            price = p.get("entry", 0)
        st = stats_fn(ticker) or {}
        usable.append({
            "ticker": ticker,
            "exposure_usd": qty * float(price or 0),
            "beta": beta_fn(ticker),
            "ann_vol_pct": st.get("ann_vol_pct"),
            # D-91: read through snapshot_get. The snapshot key is `gics_sector` (the name AQE
            # actually uses); `sector` was the name this line asked for and no writer ever
            # produced it, so every sector_concentration figure this module has ever emitted was
            # 100% "UNKNOWN" — one bucket, concentration trivially maxed, gate meaningless.
            # snapshot_get resolves either spelling so journals written before the fix still read.
            "sector": snapshot_get(snap, "gics_sector") or "UNKNOWN",
            "as_of": p.get("aqe_snapshot_as_of"),
            "unmarked": unmarked,
        })
    return usable, excluded_no_aqe_data, excluded_pending_review


def sector_concentration(usable, gross_exposure):
    by_sector = {}
    for p in usable:
        by_sector[p["sector"]] = by_sector.get(p["sector"], 0.0) + abs(p["exposure_usd"])
    if not gross_exposure:
        return {s: 0.0 for s in by_sector}
    return {s: round(100.0 * v / gross_exposure, 2) for s, v in by_sector.items()}


def compute(journal, beta_fn=None, stats_fn=None):
    dyncap = (journal.get("dyncap") or {}).get("value")
    open_positions = journal.get("open_positions", []) or []
    usable, excluded_no_aqe_data, excluded_pending_review = build_positions(
        open_positions, beta_fn=beta_fn, stats_fn=stats_fn)

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
        "var": var_result,
        "computed_from_aqe_dated": as_of_dates[-1] if len(as_of_dates) == 1 else as_of_dates,
        "mixed_vintage": len(as_of_dates) > 1,
        "excluded_no_aqe_data": excluded_no_aqe_data,
        "excluded_pending_review": excluded_pending_review,
        "missing_beta_or_vol": missing_beta_or_vol,
        "unmarked_cost_basis_proxy": unmarked_tickers,
        "note": "positions in excluded_no_aqe_data/excluded_pending_review/missing_beta_or_vol "
                "are OMITTED from leverage/nav_beta/sector/VaR, not defaulted to zero. Beta/vol "
                "come from historical_store.py (FMP), sector from the AQE snapshot — see module "
                "docstring. Stop audit is NOT computed here — see premarket's stop-update, the "
                "only place the comparison is fresh.",
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
    # Fixed beta/vol stubs — no disk or FMP dependency in the selftest, but the same code path
    # production uses (build_positions/compute take beta_fn/stats_fn with historical_store as
    # the real default; only the test injects stand-ins).
    fake_beta = {"AAA": 1.2, "BBB": 0.8}
    fake_stats = {"AAA": {"ann_vol_pct": 35.0}, "BBB": {"ann_vol_pct": 25.0}}
    beta_fn = lambda t: fake_beta.get(t)
    stats_fn = lambda t: fake_stats.get(t)

    journal = {
        "date": "2026-07-28",
        "dyncap": {"value": 100000, "one_r": 1000},
        "open_positions": [
            {"ticker": "AAA", "qty": 100, "entry": 50.0, "mark_price": 55.0,
             "aqe_snapshot": {"sector": "Tech"}, "aqe_snapshot_as_of": "2026-07-27",
             "aegis_status": "confirmed"},
            {"ticker": "BBB", "qty": 50, "entry": 20.0,   # no mark_price -> unmarked
             "aqe_snapshot": {"sector": "Tech"}, "aqe_snapshot_as_of": "2026-07-27",
             "aegis_status": "confirmed"},
            {"ticker": "CCC", "qty": 30, "entry": 100.0,
             "aqe_snapshot": None, "aegis_status": "confirmed"},   # never refreshed -> excluded
            {"ticker": "DDD", "qty": 10, "entry": 10.0,
             "aqe_snapshot": {"sector": "Energy"}, "aqe_snapshot_as_of": "2026-07-27",
             "aegis_status": "pending_review"},   # unconfirmed fill -> excluded regardless of AQE
        ],
        "closed_trades": [], "metrics": {},
    }
    m = compute(journal, beta_fn=beta_fn, stats_fn=stats_fn)
    assert m["excluded_no_aqe_data"] == ["CCC"], m
    assert m["excluded_pending_review"] == ["DDD"], m
    assert m["unmarked_cost_basis_proxy"] == ["BBB"], m
    assert "stop_audit" not in m, "stop audit was removed — premarket's stop-update is the only fresh check"
    assert m["sector_concentration_pct"]["Tech"] == 100.0, m["sector_concentration_pct"]
    assert m["leverage"] is not None and m["leverage"] > 0
    assert m["computed_from_aqe_dated"] == "2026-07-27"
    assert m["mixed_vintage"] is False
    assert "var_95_1m_usd" in m["var"], m["var"]

    # mixed vintage: BBB refreshed a different day -> flagged, not hidden
    journal["open_positions"][1]["aqe_snapshot_as_of"] = "2026-07-20"
    m2 = compute(journal, beta_fn=beta_fn, stats_fn=stats_fn)
    assert m2["mixed_vintage"] is True
    assert m2["computed_from_aqe_dated"] == ["2026-07-20", "2026-07-27"]

    # missing beta/vol (not seeded in historical_store) -> flagged, excluded from VaR, not guessed
    m3 = compute(journal, beta_fn=lambda t: None, stats_fn=lambda t: None)
    assert set(m3["missing_beta_or_vol"]) == {"AAA", "BBB"}, m3["missing_beta_or_vol"]

    # dyncap unset -> fail-closed, no fabricated leverage/VaR
    journal["dyncap"]["value"] = None
    m4 = compute(journal, beta_fn=beta_fn, stats_fn=stats_fn)
    assert m4["leverage"] is None and m4["nav_beta"] is None
    assert "note" in m4["var"]

    print("portfolio_metrics selftest OK — excludes positions with no AQE snapshot AND positions "
          "still pending_review, rather than guessing or inflating the book; beta/vol sourced via "
          "injectable beta_fn/stats_fn (historical_store.py/FMP in production); stop audit removed "
          "(now premarket-only); flags cost-basis-proxy exposure when unmarked, flags mixed-vintage "
          "AQE sector data instead of hiding it; VaR reused from var_parametric.py, fail-closed "
          "with no dynCap.")


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
