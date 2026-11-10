#!/usr/bin/env python3
"""screens_preview.py -- code-only preview of the seven per-seat screens over the scored universe (no model seats, no brief change).

    python3 scripts/screens_preview.py --universe-rows aegis/output/aqe_universe_rows.json --export aegis/output/aqe_daily_export.json --out-dir aegis/output/screens_preview

Per seat: how many tests, the best pass count, how many names pass ALL tests (and which), the top 10, and which of those sit on NO AQE list
(on_longlist / on_elder / on_qs / in_ledger all false). Plus the seat-by-seat overlap of the all-tests-passed names. Read-only."""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "aegis/plugin/aegis-core/skills/pma/tools"))
import seat_screens as S  # noqa: E402

LISTS = ("on_longlist", "on_elder", "on_qs", "in_ledger")


def on_any_list(r):
    return any(bool(r.get(k)) for k in LISTS)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--universe-rows", required=True); ap.add_argument("--out-dir", required=True)
    ap.add_argument("--export", required=True, help="aqe_daily_export.json: the universe rows carry no list flags, daily_list does")
    a = ap.parse_args(argv)
    d = json.load(open(a.universe_rows))
    rows = d["rows"] if isinstance(d, dict) else d
    ex = json.load(open(a.export))
    flags = {r["ticker"]: r for r in ex.get("daily_list", [])}
    by = {r["ticker"]: {**{k: flags.get(r["ticker"], {}).get(k) for k in LISTS}} for r in rows}      # a name absent from daily_list is on no list
    out = {"universe_date": d.get("date") if isinstance(d, dict) else None, "universe_rows": len(rows), "seats": {}, "overlap_all_tests": {}}
    full = {}
    for seat in S.SEATS:
        scored = [(S.score(seat, r), r["ticker"]) for r in rows]
        of = len(S.SCREENS[seat])
        best = max(n for (n, _), _t in scored)
        allp = sorted(t for (n, _), t in scored if n == of)
        top = S.screen(seat, rows, 10)
        dist = {}
        for (n, _), _t in scored:
            dist[n] = dist.get(n, 0) + 1
        full[seat] = set(allp)
        out["seats"][seat] = {"tests": of, "best_pass": best, "pass_all": len(allp), "pass_all_tickers": allp,
                              "pass_all_on_no_aqe_list": [t for t in allp if not on_any_list(by[t])],
                              "top10": [{**x, "on_an_aqe_list": on_any_list(by[x["ticker"]])} for x in top],
                              "distribution_names_by_tests_passed": {str(k): dist[k] for k in sorted(dist, reverse=True)}}
    seats = list(full)
    for i, s in enumerate(seats):
        for t in seats[i + 1:]:
            out["overlap_all_tests"][f"{s}|{t}"] = len(full[s] & full[t])
    out["names_passing_all_tests_for_2plus_seats"] = sorted(t for t in set().union(*full.values()) if sum(t in v for v in full.values()) >= 2)
    out["lists_tested"] = list(LISTS)
    od = Path(a.out_dir); od.mkdir(parents=True, exist_ok=True)
    (od / "screens_preview.json").write_text(json.dumps(out, indent=1))
    md = [f"# Seven screens on the scored universe ({out['universe_rows']} rows, {out['universe_date']}) -- code only, no model seats", "",
          "| seat | tests | best pass | pass ALL | pass ALL, on no AQE list |", "|---|---|---|---|---|"]
    for s, v in out["seats"].items():
        md.append(f"| {s} | {v['tests']} | {v['best_pass']} | {v['pass_all']} | {len(v['pass_all_on_no_aqe_list'])} |")
    md += ["", "## Names passing every test, per seat", ""]
    for s, v in out["seats"].items():
        md.append(f"- **{s}** ({v['pass_all']}): {', '.join(v['pass_all_tickers']) or 'none'}")
        md.append(f"  - on no AQE list ({len(v['pass_all_on_no_aqe_list'])}): {', '.join(v['pass_all_on_no_aqe_list']) or 'none'}")
    md += ["", "## Overlap of the pass-all sets (names in both)", ""] + [f"- {k}: {n}" for k, n in out["overlap_all_tests"].items()]
    md += ["", f"Names passing all tests for two or more seats: {', '.join(out['names_passing_all_tests_for_2plus_seats']) or 'none'}"]
    (od / "screens_preview.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:14]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
