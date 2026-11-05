#!/usr/bin/env python3
"""Report B / C cards (PM 2026-11-05): the compact page. Only the ticker section and the scorecard line -- no weather, macro, sector or book
sections (those are Report A's, and B/C reuse A's), and NO levels: B and C are scored only, never bracketed, never watched by the alerts.

  pma_cards_report.py --report C --date 2026-11-06 [--run-dir .] [--out pma_cards_<date>-C.html]
Reads consensus.json (+ report_lines.json when present). Writes one phone-safe HTML page and nothing else."""
import argparse, datetime, html, json, os, sys

NAME = {"B": "Report B -- the whole screened market", "C": "Report C -- the committee plus the AQE-quant voice"}
WHAT = {"B": "The same seven voices, each reading the whole daily screened universe with its own method, before any AQE score gate.",
        "C": "The seven voices plus one that argues only from AQE's own scores and the parts behind them."}


def E(x):
    return html.escape(str(x), quote=True)


def render(report, date, consensus, lines=None):
    rows = [r for r in consensus if r.get("verdict") in ("ADVANCE", "HOLD-FOR-CONDITIONS")]
    rows.sort(key=lambda r: (r["verdict"] != "ADVANCE", -(r.get("conviction") or 0), r["ticker"]))
    n_all = len(consensus)
    body = []
    for r in rows:
        sp = r.get("split") or {}
        s, o, a = len(sp.get("support") or []), len(sp.get("oppose") or []), len(sp.get("abstain") or [])
        total = s + o + a
        word = "Advance" if r["verdict"] == "ADVANCE" else "Hold for conditions"
        body.append(f'<tr><td><b>{E(r["ticker"])}</b></td><td>{word}</td><td>{s} of {total} voices support, {o} oppose</td>'
                    f'<td>conviction {E(r.get("conviction") if r.get("conviction") is not None else "not available")}</td></tr>')
    ln = (lines or {}).get(report)
    score = (f'<p>{E(ln)}</p>' if ln else '<p>No graded result yet: the first five-session result arrives a week after the first run.</p>')
    d = datetime.date.fromisoformat(date)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aegis Daily Cards {E(report)}</title><style>
body{{font:16px/1.5 system-ui,sans-serif;margin:0;padding:16px;background:#fff;color:#111}}
@media (prefers-color-scheme:dark){{body{{background:#111;color:#eee}}}}
.wrap{{max-width:760px;margin:0 auto}} table{{border-collapse:collapse;width:100%}} td{{padding:8px 6px;border-bottom:1px solid #8884;vertical-align:top}}
.meta{{font-size:13px;opacity:.7}}
</style></head><body><div class="wrap">
<div class="meta">Aegis committee cards &middot; {d:%a} {d.day} {d:%b %Y} &middot; to the PM &middot; scored only, not live</div>
<h1>{E(NAME[report])}</h1><p>{E(WHAT[report])}</p>
<h2>1 &middot; The tickers</h2>
<p>{len(rows)} of {n_all} names advance or hold for conditions. No price levels are published for this report; it is graded on what the names do next.</p>
<table>{"".join(body) or '<tr><td>No name reached an advance or hold verdict.</td></tr>'}</table>
<h2>2 &middot; Scorecard</h2>{score}
<p class="meta">Draft for the PM. Nothing is staged, armed or placed; sizing and the trade call are yours.</p>
</div></body></html>"""


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--report", required=True, choices=["B", "C"])
    p.add_argument("--date", required=True)
    p.add_argument("--run-dir", default=".")
    p.add_argument("--out")
    a = p.parse_args(argv)
    cpath = os.path.join(a.run_dir, "consensus.json")
    if not os.path.exists(cpath):
        print(f"FATAL: {cpath} not found -- a report page needs the committee's verdicts", file=sys.stderr)
        return 2
    lpath = os.path.join(a.run_dir, "report_lines.json")
    lines = json.load(open(lpath)) if os.path.exists(lpath) else None
    out = a.out or os.path.join(a.run_dir, f"pma_cards_{a.date}-{a.report}.html")
    open(out, "w").write(render(a.report, a.date, json.load(open(cpath)), lines))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
