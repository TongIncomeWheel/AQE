#!/usr/bin/env python3
"""report_compare.py -- which of the three daily reports beats the market?  (PM 2026-11-05)

A = the committee as it runs today. B = the same seven seats on the whole screened universe. C = the seven plus the AQE-quant seat.
Each report locks its own verdict ledger (rows tagged `report`). This grades the picks of every report against the SAME two bars --
SPY and the equal-weight list (every name in that day's AQE daily_list) -- at 5 and 20 sessions, and measures how much the reports
overlap, because two reports that pick the same names are not two experiments.

Pure arithmetic over files already on disk; no network, no model, no orders. Reuses pma_scorecard's window and return helpers so the
base/end sessions mean exactly what they mean on A's own scorecard. A pick is a ledger row whose verdict is ADVANCE or HOLD-FOR-CONDITIONS.

    report_compare.py grade --report A=ledgerA.json --report B=runB/verdict_ledger.json --report C=runC/verdict_ledger.json \
        --closes closes.json --export 2026-11-06=export.json [--export ...] [--asof D] [--horizons 5 20] \
        --out report_compare.json [--md report_compare.md] [--lines report_lines.json]
"""
import argparse, itertools, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pma_scorecard as sc   # noqa: E402

PICK_VERDICTS = ("ADVANCE", "HOLD-FOR-CONDITIONS")
REPORTS = ("A", "B", "C")


def _picks(ledger):
    rows = ledger["rows"] if isinstance(ledger, dict) else ledger
    out = {}
    for r in rows:
        if r.get("verdict") in PICK_VERDICTS and r.get("date"):
            out.setdefault(r["date"], []).append(r["ticker"])
    return {d: sorted(set(t)) for d, t in out.items()}


def _list_return(closes, tickers, base, end):
    rs = [sc.ret(closes, t, base, end) for t in tickers]
    rs = [x for x in rs if x is not None]
    return (statistics.mean(rs), len(rs)) if rs else (None, 0)


def grade(reports, closes, exports, asof, horizons, bench="SPY"):
    days = sc.calendar(closes, bench)
    asof = asof or days[-1]
    result = {"asof": asof, "bench": bench, "horizons": horizons, "reports": {}, "overlap": {}, "notes": []}
    picks = {rep: _picks(led) for rep, led in reports.items()}
    for rep in reports:
        per_h = {}
        for h in horizons:
            rows, pending = [], 0
            for d, tickers in sorted(picks[rep].items()):
                w = sc.window(days, d, asof, h)
                if not w or not w[3]:
                    pending += len(tickers)       # horizon not reached yet: counted as pending, never graded early
                    continue
                base, end, _n, _full = w
                spy = sc.ret(closes, bench, base, end)
                lst_tickers = exports.get(d)
                lst, n_lst = _list_return(closes, lst_tickers, base, end) if lst_tickers else (None, 0)
                for t in tickers:
                    r = sc.ret(closes, t, base, end)
                    if r is None or spy is None:
                        continue
                    rows.append({"date": d, "ticker": t, "ret": r, "vs_spy": r - spy,
                                 "vs_list": (r - lst) if lst is not None else None})
            if rows:
                es = [x["vs_spy"] for x in rows]
                el = [x["vs_list"] for x in rows if x["vs_list"] is not None]
                per_h[str(h)] = {"n": len(rows), "pending": pending,
                                 "mean": round(statistics.mean(x["ret"] for x in rows), 2),
                                 "vs_spy_mean": round(statistics.mean(es), 2), "vs_spy_median": round(statistics.median(es), 2),
                                 "beat_spy": sum(1 for x in es if x > 0),
                                 "vs_list_mean": round(statistics.mean(el), 2) if el else None,
                                 "beat_list": sum(1 for x in el if x > 0), "n_list": len(el)}
            else:
                per_h[str(h)] = {"n": 0, "pending": pending}
        result["reports"][rep] = {"picks": sum(len(v) for v in picks[rep].values()), "dates": sorted(picks[rep]), "by_horizon": per_h}
    for a, b in itertools.combinations(sorted(reports), 2):
        dates = sorted(set(picks[a]) & set(picks[b]))
        shared = [(len(set(picks[a][d]) & set(picks[b][d])), len(set(picks[a][d]) | set(picks[b][d]))) for d in dates]
        tot_s, tot_u = sum(s for s, _ in shared), sum(u for _, u in shared)
        result["overlap"][f"{a}-{b}"] = {"dates": len(dates), "shared": tot_s, "union": tot_u,
                                         "jaccard": round(tot_s / tot_u, 2) if tot_u else None}
    if any(len(picks[r]) == 0 for r in reports):
        result["notes"].append("a report with no locked picks is shown with n=0, never dropped")
    return result


def _f(x):
    return "n/a" if x is None else f"{x:+.2f}"


def lines(res):
    """One plain line per report for A's Cards (PM 2026-11-05)."""
    out = {}
    for rep, o in res["reports"].items():
        bits = []
        for h in res["horizons"]:
            b = o["by_horizon"][str(h)]
            if b.get("n"):
                bits.append(f"{h} sessions: {b['n']} picks, {_f(b['mean'])}% average, {_f(b['vs_spy_mean'])} vs SPY, {_f(b['vs_list_mean'])} vs the full list")
            else:
                bits.append(f"{h} sessions: not yet graded ({b.get('pending', 0)} picks waiting)")
        out[rep] = f"Report {rep}: " + "; ".join(bits)
    return out


def render_md(res):
    L = [f"## Which report beats the market (graded to {res['asof']}, against {res['bench']} and the equal-weight list)", ""]
    for rep, line in lines(res).items():
        L.append(f"- {line}")
    L += ["", "Overlap between reports (shared picks / all picks across the dates both ran):"]
    for k, o in res["overlap"].items():
        L.append(f"- {k}: {o['shared']} of {o['union']} ({o['jaccard'] if o['jaccard'] is not None else 'n/a'}) over {o['dates']} day(s)")
    L += ["", "A pick is an ADVANCE or HOLD-FOR-CONDITIONS verdict. Horizons not yet reached are waiting, never graded early. "
          "Reports that pick the same names are one experiment, not two: read the overlap before reading the gap."]
    return "\n".join(L) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grade")
    g.add_argument("--report", action="append", required=True, help="A=path/to/verdict_ledger.json (repeat for B, C)")
    g.add_argument("--closes", required=True)
    g.add_argument("--export", action="append", help="DATE=path/to/aqe_daily_export.json (repeat)")
    g.add_argument("--asof")
    g.add_argument("--horizons", type=int, nargs="+", default=[5, 20])
    g.add_argument("--bench", default="SPY")
    g.add_argument("--out", required=True)
    g.add_argument("--md")
    g.add_argument("--lines")
    a = p.parse_args(argv)
    reports = {}
    for spec in a.report:
        k, path = spec.split("=", 1)
        k = k.strip().upper()
        if k not in REPORTS:
            raise SystemExit(f"--report key must be A, B or C, got {k!r}")
        reports[k] = json.load(open(path))
    closes = json.load(open(a.closes)); closes.pop("_missing", None)
    exports = {}
    for spec in a.export or []:
        d, path = spec.split("=", 1)
        exports[d] = [r["ticker"] for r in json.load(open(path)).get("daily_list", [])]
    res = grade(reports, closes, exports, a.asof, a.horizons, a.bench)
    json.dump(res, open(a.out, "w"), indent=1)
    if a.md: open(a.md, "w").write(render_md(res))
    if a.lines: json.dump(lines(res), open(a.lines, "w"), indent=1)
    print(render_md(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
