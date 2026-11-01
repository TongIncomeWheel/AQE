#!/usr/bin/env python3
"""pma_scorecard.py -- D122.1: grade the committee against the right bar.

Raw SPY is the wrong yardstick on its own. The committee is handed a list (the AQE
daily list) whose median 30-day beta is ~1.4, so in a falling tape every bucket will
"lose to SPY" before a single judgment is made. This tool separates the three things
that get blurred together:

  1. the LIST      -- did the AQE list itself beat SPY?            (universe vs SPY)
  2. the JUDGMENT  -- did the committee's picks beat the list?      (pick vs universe)
  3. the RISK      -- was the result just beta?                     (pick - beta x SPY)

and reports median and share-that-beat alongside the mean, so one name cannot carry
or sink a bucket unseen (the "drag" block names the names that did).

Pure arithmetic over files already on disk. No network, no model, no orders.

    pma_scorecard.py grade --ledger verdict_ledger.json --closes closes.json \
        --export 2026-09-30=run30/aqe_daily_export.json [--export ...] \
        [--asof 2026-09-30] [--horizon 5] [--from 2026-09-21] [--to 2026-09-30] \
        [--beta-cap 2.5] --out scorecard.json [--md scorecard.md]
"""
import argparse, json, statistics, sys

BUCKETS = ["ADVANCE", "HOLD-FOR-CONDITIONS", "PASS", "NEAR-MISS"]
SHORT = {"ADVANCE": "Advance", "HOLD-FOR-CONDITIONS": "Hold", "PASS": "Pass", "NEAR-MISS": "Near-miss"}
REF_TOL = 0.005   # ledger ref_price must agree with the base close to 0.5% or the row is refused


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def load_export_meta(path):
    """ticker -> {beta, sector} from one AQE export; the daily list defines the universe."""
    e = json.load(open(path))
    universe, meta = [], {}
    for row in e.get("daily_list", []):
        universe.append(row["ticker"])
        meta[row["ticker"]] = row
    for key in ("_radar_pool", "held_positions"):
        for row in e.get(key, []) or []:
            meta.setdefault(row["ticker"], row)
    out = {}
    for t, row in meta.items():
        b = row.get("beta_30d")
        out[t] = {"beta": b if _num(b) else None, "sector": row.get("gics_sector") or row.get("ptj_sector")}
    return universe, out


def calendar(closes, bench):
    days = sorted(d for d, v in closes.get(bench, {}).items() if _num(v))
    if not days:
        raise SystemExit(f"FATAL: no closes for benchmark {bench}")
    return days


def window(days, run_date, asof, horizon):
    """base = last session before the run; end = base + horizon sessions, capped at asof."""
    prior = [d for d in days if d < run_date]
    if not prior:
        return None
    base = prior[-1]
    after = [d for d in days if base < d <= asof]
    if not after:
        return None
    full = len(after) >= horizon
    end = after[horizon - 1] if full else after[-1]
    return base, end, len(after[:horizon]), full


def ret(closes, t, a, b):
    c = closes.get(t, {})
    if _num(c.get(a)) and _num(c.get(b)) and c[a] > 0:
        return (c[b] / c[a] - 1.0) * 100.0
    return None


def summarise(rows, beta_cap=None):
    def block(rs):
        if not rs:
            return {"n": 0}
        r = [x["ret"] for x in rs]
        es = [x["vs_spy"] for x in rs]
        eu = [x["vs_universe"] for x in rs if x["vs_universe"] is not None]
        ba = [x["beta_adj"] for x in rs if x["beta_adj"] is not None]
        bt = [x["beta"] for x in rs if x["beta"] is not None]
        return {
            "n": len(rs),
            "mean": round(statistics.mean(r), 2),
            "median": round(statistics.median(r), 2),
            "vs_spy_mean": round(statistics.mean(es), 2),
            "vs_spy_median": round(statistics.median(es), 2),
            "beat_spy": sum(1 for x in es if x > 0),
            "vs_universe_mean": round(statistics.mean(eu), 2) if eu else None,
            "beat_universe": sum(1 for x in eu if x > 0),
            "n_universe": len(eu),
            "beta_adj_mean": round(statistics.mean(ba), 2) if ba else None,
            "n_beta": len(ba),
            "beta_mean": round(statistics.mean(bt), 2) if bt else None,
        }
    out = {}
    for b in BUCKETS:
        rs = [x for x in rows if x["verdict"] == b]
        blk = block(rs)
        if rs:
            # drag: the names that moved the bucket mean most, by contribution to vs_spy
            srt = sorted(rs, key=lambda x: x["vs_spy"])
            blk["worst"] = [{k: x[k] for k in ("run", "ticker", "vs_spy", "beta")} for x in srt[:3]]
            blk["best"] = [{k: x[k] for k in ("run", "ticker", "vs_spy", "beta")} for x in srt[::-1][:3]]
            if beta_cap is not None:
                hi = [x for x in rs if x["beta"] is not None and x["beta"] >= beta_cap]
                lo = [x for x in rs if x["beta"] is not None and x["beta"] < beta_cap]
                blk["beta_split"] = {"cap": beta_cap, "at_or_above": block(hi), "below": block(lo),
                                     "no_beta": sum(1 for x in rs if x["beta"] is None)}
        out[b] = blk
    return out


def cmd_grade(a):
    ledger = json.load(open(a.ledger))
    rows_in = ledger["rows"] if isinstance(ledger, dict) else ledger
    closes = json.load(open(a.closes))
    closes.pop("_missing", None)
    days = calendar(closes, a.bench)
    asof = a.asof or days[-1]
    exports = {}
    for spec in a.export or []:
        d, p = spec.split("=", 1)
        exports[d] = load_export_meta(p)

    graded, refused, ungraded = [], [], []
    runs = {}
    for r in rows_in:
        d = r.get("date")
        if r.get("verdict") not in BUCKETS or not d:
            continue
        if (a.date_from and d < a.date_from) or (a.date_to and d > a.date_to):
            continue
        w = window(days, d, asof, a.horizon)
        if w is None:
            ungraded.append({"run": d, "ticker": r["ticker"], "why": "no session after the run yet"})
            continue
        base, end, sessions, full = w
        if d not in exports:
            ungraded.append({"run": d, "ticker": r["ticker"], "why": "no AQE export supplied for this run (universe/beta unknown)"})
            continue
        t = r["ticker"]
        x = ret(closes, t, base, end)
        if x is None:
            ungraded.append({"run": d, "ticker": t, "why": f"no close for {base} or {end}"})
            continue
        ref = r.get("ref_price")
        if _num(ref) and ref > 0 and abs(closes[t][base] / ref - 1) > REF_TOL:
            refused.append({"run": d, "ticker": t, "ref_price": ref, "base_close": closes[t][base]})
            continue
        if d not in runs:
            uni, meta = exports[d]
            ur = [v for v in (ret(closes, u, base, end) for u in uni) if v is not None]
            runs[d] = {"base": base, "end": end, "sessions": sessions, "full_horizon": full,
                       "spy": round(ret(closes, a.bench, base, end), 2),
                       "universe_mean": round(statistics.mean(ur), 2) if ur else None,
                       "universe_n": len(ur), "universe_size": len(uni),
                       "universe_beat_spy": sum(1 for v in ur if v > ret(closes, a.bench, base, end)),
                       "_meta": meta}
        R = runs[d]
        spy = ret(closes, a.bench, base, end)
        beta = R["_meta"].get(t, {}).get("beta")
        graded.append({
            "run": d, "ticker": t, "verdict": r["verdict"], "full_horizon": full,
            "ret": round(x, 2), "vs_spy": round(x - spy, 2),
            "vs_universe": round(x - R["universe_mean"], 2) if R["universe_mean"] is not None else None,
            "beta": beta, "beta_adj": round(x - beta * spy, 2) if beta is not None else None,
        })

    for R in runs.values():
        R.pop("_meta", None)
    full_rows = [g for g in graded if g["full_horizon"]]
    out = {
        "schema": "pma_scorecard/1",
        "asof": asof, "horizon_sessions": a.horizon, "bench": a.bench,
        "method": "base = last close before the run (checked against ledger ref_price, 0.5% tolerance); "
                  "universe = equal-weight AQE daily list for that run over the same window; "
                  "beta_adj = return - beta_30d x SPY return.",
        "runs": dict(sorted(runs.items())),
        "pooled_all": summarise(graded, a.beta_cap),
        "pooled_full_horizon": summarise(full_rows, a.beta_cap),
        "by_run": {d: summarise([g for g in graded if g["run"] == d]) for d in sorted(runs)},
        "rows": graded,
        "refused_ref_mismatch": refused,
        "ungraded": ungraded,
    }
    json.dump(out, open(a.out, "w"), indent=1)
    if a.md:
        open(a.md, "w").write(render_md(out))
    if a.html:
        open(a.html, "w").write(render_html(out, read_log(a.log) if a.log else []))
    if a.log:
        rows = [r for r in read_log(a.log) if r.get("asof") != asof]   # one row per close: a re-run replaces, never duplicates
        rows.append(log_row(out))
        rows.sort(key=lambda r: r["asof"])
        open(a.log, "w").write("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
        if a.html:   # re-render so today's row is in the trend
            open(a.html, "w").write(render_html(out, rows))
    p = out["pooled_all"]
    print(f"graded {len(graded)} rows over {len(runs)} runs (asof {asof}); refused {len(refused)}; ungraded {len(ungraded)}")
    for b in BUCKETS:
        s = p[b]
        if s.get("n"):
            print(f"  {SHORT[b]:9s} n={s['n']:3d} mean {s['mean']:+.2f} med {s['median']:+.2f} "
                  f"vsSPY {s['vs_spy_mean']:+.2f} (med {s['vs_spy_median']:+.2f}, beat {s['beat_spy']}/{s['n']}) "
                  f"vsList {s['vs_universe_mean']:+.2f} beta-adj {s['beta_adj_mean']}")
    return 0 if not refused else 3


def read_log(path):
    try:
        return [json.loads(l) for l in open(path) if l.strip()]
    except FileNotFoundError:
        return []


def log_row(o):
    """The monitored line: one per close, so the two-week review reads a trend, not a snapshot."""
    def slim(blk):
        return {b: {k: blk[b].get(k) for k in ("n", "vs_spy_mean", "vs_spy_median", "beat_spy",
                                                "vs_universe_mean", "beta_adj_mean")}
                for b in BUCKETS if blk[b].get("n")}
    adv = o["pooled_all"]["ADVANCE"]
    return {"asof": o["asof"], "horizon": o["horizon_sessions"],
            "runs_graded": len(o["runs"]), "calls_graded": len(o["rows"]),
            "mature_runs": sum(1 for R in o["runs"].values() if R["full_horizon"]),
            "all": slim(o["pooled_all"]), "mature": slim(o["pooled_full_horizon"]),
            "advance_beta_split": {k: adv["beta_split"][k].get("vs_spy_mean") for k in ("at_or_above", "below")}
                                  if adv.get("beta_split") else None,
            "advances_per_run": {d: b["ADVANCE"].get("n", 0) for d, b in o["by_run"].items()},
            "refused": len(o["refused_ref_mismatch"])}


def cmd_trend(a):
    rows = read_log(a.log)
    if not rows:
        print("no scorecard log yet"); return 1
    print(render_trend_md(rows)); return 0


def render_trend_md(rows):
    L = ["| As of | Runs (mature) | Advance vs SPY (mature) | Beat SPY | Advance vs list | Pass vs SPY (mature) | Spread adv−pass |",
         "|---|---|---|---|---|---|---|"]
    for r in rows:
        am, pm = r["mature"].get("ADVANCE", {}), r["mature"].get("PASS", {})
        spread = (am.get("vs_spy_mean") - pm.get("vs_spy_mean")) if am.get("n") and pm.get("n") else None
        L.append(f"| {r['asof']} | {r['runs_graded']} ({r['mature_runs']}) | {_f(am.get('vs_spy_mean'))} | "
                 f"{am.get('beat_spy', '—')}/{am.get('n', '—')} | {_f(am.get('vs_universe_mean'))} | {_f(pm.get('vs_spy_mean'))} | {_f(spread)} |")
    return "\n".join(L) + "\n"


def render_html(o, log_rows):
    """Phone-safe block for the card report: fixed-layout tables that wrap, never scroll sideways."""
    T = 'style="width:100%;border-collapse:collapse;font-size:11.5px;table-layout:fixed;word-break:break-word"'
    td = lambda x, b=False: f"<td>{'<b>' if b else ''}{x}{'</b>' if b else ''}</td>"
    def tbl(key):
        h = f'<table {T}><tr style="text-align:left;color:var(--muted)"><th>Verdict</th><th>n</th><th>vs SPY</th><th>Beat</th><th>vs list</th><th>Net β</th></tr>'
        for b in BUCKETS:
            s = o[key][b]
            if s.get("n"):
                h += "<tr>" + td(SHORT[b], b == "ADVANCE") + td(s["n"]) + td(_f(s["vs_spy_mean"]), b == "ADVANCE") + \
                     td(f"{s['beat_spy']}/{s['n']}") + td(_f(s["vs_universe_mean"])) + td(_f(s["beta_adj_mean"])) + "</tr>"
        return h + "</table>"
    mature = sum(1 for R in o["runs"].values() if R["full_horizon"])
    H = [f'<h2>Committee scorecard · graded to {o["asof"]} close<i></i></h2><div class="panel">',
         f'<p class="note" style="margin:0 0 6px">{len(o["rows"])} calls over {len(o["runs"])} runs. '
         f'vs SPY, vs the AQE list each was picked from, and net of beta. Points, equal weight.</p>',
         f'<p style="margin:6px 0 2px"><b>Mature calls</b> ({o["horizon_sessions"]}-session window, {mature} runs)</p>', tbl("pooled_full_horizon"),
         '<p style="margin:10px 0 2px"><b>All graded calls</b> (includes partial windows)</p>', tbl("pooled_all")]
    if len(log_rows) > 1:
        H.append(f'<p style="margin:10px 0 2px"><b>Trend</b> (one line per close, mature advances)</p><table {T}>'
                 '<tr style="text-align:left;color:var(--muted)"><th>As of</th><th>Adv vs SPY</th><th>Beat</th><th>Pass vs SPY</th></tr>')
        for r in log_rows[-10:]:
            am, pm = r["mature"].get("ADVANCE", {}), r["mature"].get("PASS", {})
            H.append("<tr>" + td(r["asof"][5:]) + td(_f(am.get("vs_spy_mean"))) + td(f"{am.get('beat_spy','—')}/{am.get('n','—')}") + td(_f(pm.get("vs_spy_mean"))) + "</tr>")
        H.append("</table>")
    H.append('<p class="note" style="margin:6px 0 0">Grading only (D122.1). It changes no verdict. Review due 15 Oct.</p></div>')
    return "\n".join(H) + "\n"


def _f(x):
    return "—" if x is None else f"{x:+.2f}"


def render_md(o):
    L = [f"# Committee scorecard — as of {o['asof']} close", "",
         f"Horizon {o['horizon_sessions']} sessions (shorter windows are marked partial). Benchmark {o['bench']}. {o['method']}", "",
         "## 1 · The list vs the market", "",
         "| Run | Base → end | Sessions | SPY | AQE list (EW) | List names beating SPY |", "|---|---|---|---|---|---|"]
    for d, R in o["runs"].items():
        L.append(f"| {d} | {R['base']} → {R['end']} | {R['sessions']}{'' if R['full_horizon'] else ' (partial)'} | "
                 f"{_f(R['spy'])}% | {_f(R['universe_mean'])}% | {R['universe_beat_spy']}/{R['universe_n']} |")
    for title, key in (("## 2 · Every graded call, pooled", "pooled_all"),
                       ("## 3 · Full-horizon calls only", "pooled_full_horizon")):
        L += ["", title, "", "| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |",
              "|---|---|---|---|---|---|---|---|---|"]
        for b in BUCKETS:
            s = o[key][b]
            if not s.get("n"):
                continue
            L.append(f"| {SHORT[b]} | {s['n']} | {_f(s['mean'])}% | {_f(s['median'])}% | {_f(s['vs_spy_mean'])} / {_f(s['vs_spy_median'])} | "
                     f"{s['beat_spy']}/{s['n']} | {_f(s['vs_universe_mean'])} | {_f(s['beta_adj_mean'])} | {s['beta_mean'] if s['beta_mean'] is not None else '—'} |")
    adv = o["pooled_all"]["ADVANCE"]
    if adv.get("n") and adv.get("beta_split"):
        bs = adv["beta_split"]
        L += ["", f"## 4 · Advances split at beta {bs['cap']}", "",
              "| Group | n | Mean | vs SPY | Beat SPY | vs list |", "|---|---|---|---|---|---|"]
        for lab, k in ((f"beta ≥ {bs['cap']}", "at_or_above"), (f"beta < {bs['cap']}", "below")):
            s = bs[k]
            if s.get("n"):
                L.append(f"| {lab} | {s['n']} | {_f(s['mean'])}% | {_f(s['vs_spy_mean'])} | {s['beat_spy']}/{s['n']} | {_f(s['vs_universe_mean'])} |")
        L += ["", "Worst advances: " + ", ".join(f"{w['ticker']} ({w['run'][5:]}) {_f(w['vs_spy'])} β{w['beta']}" for w in adv["worst"])]
    if o["refused_ref_mismatch"]:
        L += ["", f"**Refused (ledger price does not match the close):** {len(o['refused_ref_mismatch'])} rows."]
    if o["ungraded"]:
        L += ["", f"Not graded: {len(o['ungraded'])} rows (reasons in the JSON)."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grade")
    g.add_argument("--ledger", required=True)
    g.add_argument("--closes", required=True)
    g.add_argument("--export", action="append", help="RUN_DATE=path/to/aqe_daily_export.json (repeat)")
    g.add_argument("--asof")
    g.add_argument("--horizon", type=int, default=5)
    g.add_argument("--from", dest="date_from")
    g.add_argument("--to", dest="date_to")
    g.add_argument("--bench", default="SPY")
    g.add_argument("--beta-cap", type=float, default=2.5)
    g.add_argument("--out", required=True)
    g.add_argument("--md")
    g.add_argument("--html", help="phone-safe block for the card report")
    g.add_argument("--log", help="scorecard_log.jsonl -- one line per close, replaced on re-run (the monitored trend)")
    t = sub.add_parser("trend"); t.add_argument("--log", required=True)
    a = ap.parse_args(argv)
    return {"grade": cmd_grade, "trend": cmd_trend}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
