#!/usr/bin/env python3
"""pma_conditions.py -- compile the committee's conditions for AQE (D123, PM 2026-10-02).

"There is NO CHANGE to what committee looks at and lands at as recommend or advance. It is simply
printing it in a format AQE alert can pick it up."

So this tool decides nothing. It reads the verdicts (consensus.json, computed exactly as before) and
each analyst's `conditions` block from their round-2 ballot, puts the numbers on every named level
from the stamped export, and writes:

  conditions.json   per name: every analyst's own buy / confirm / wrong / wait / chase, resolved;
                    what the supporters SHARE (a word held by 2+ counting supporters); and every
                    analyst's exit line, highest first. pma_levels.py attaches it to the alert file.
  conditions.md     the plain-English ledger for the brief
  conditions.html   the same ledger as a phone-safe block per card for the report

    pma_conditions.py compile --consensus consensus.json --forms 'forms/r2/*.json' \
        --export aqe_daily_export.json [--candidates candidate_set.json] --date 2026-10-02 \
        --out conditions.json --md conditions.md --html conditions.html
"""
import argparse, glob, html, json, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conditions as C

SCHEMA = "pma_conditions.v1"
CLUSTER_ATR = 0.5          # two analysts' levels within half an ATR are the same line
LIVE_VERDICTS = ("ADVANCE", "HOLD-FOR-CONDITIONS")


def _rows(export_path, candidates_path=None):
    e = json.load(open(export_path))
    rows = {}
    for key in ("daily_list", "_radar_pool"):
        for r in e.get(key) or []:
            rows.setdefault(r["ticker"], r)
    if candidates_path and os.path.exists(candidates_path):
        for r in json.load(open(candidates_path)).get("universe") or []:
            base = rows.setdefault(r["ticker"], {})
            for k, v in r.items():
                base.setdefault(k, v)
            hb = r.get("held_book") or {}
            for k, v in hb.items():
                base.setdefault(k, v)
    return rows


def _ballots(pattern):
    out = {}
    for f in sorted(glob.glob(pattern)):
        if re.search(r"\.part\d+of\d+\.json$", f):
            continue                       # merged ballots only; parts are proved by registrar merge
        d = json.load(open(f))
        if d.get("round") != 2 or "votes" not in d:
            continue
        out[d["voice"]] = {v["ticker"]: v for v in d["votes"] if v.get("ticker")}
    return out


def _met_at_close(r, row):
    """Where a word can be judged on yesterday's close, say so. None = only live data can tell."""
    entry = C._row_value(row, "entry")
    L = [l["value"] for l in r["levels"]]
    w = r["w"]
    if w in ("close_above", "close_below") and entry is not None and L and L[0] is not None:
        return entry > L[0] if w == "close_above" else entry < L[0]
    if w in ("elder_le", "elder_ge") and isinstance(row.get("elder"), (int, float)):
        return row["elder"] <= r["x"] if w == "elder_le" else row["elder"] >= r["x"]
    if w == "ma_above" and len(L) == 2 and None not in L:
        return L[0] > L[1]
    if w == "choch_bearish":
        return row.get("choch_state") == "BEARISH"
    return None


def _resolve_list(words, row):
    out = []
    for wd in words or []:
        r = C.resolve(wd, row)
        r["met_at_close"] = _met_at_close(r, row)
        r["plain"] = C.plain(r)
        out.append(r)
    return out


def _shared(analysts, price, atr, min_seats):
    """Group the counting supporters' acts-when words (buy + confirm together -- analysts put volume
    in either list) by word + level; levels within CLUSTER_ATR ATR are one line. price=True groups the
    price triggers, price=False the confirmations (volume, VWAP, strength). A group held by min_seats
    or more is what the supporters share."""
    groups = []
    for a in analysts:
        if not a["counts"] or a["vote"] != "SUPPORT":
            continue
        for r in a["buy"] + a["confirm"]:
            if (r["family"] == "price") != price:
                continue
            v = r["levels"][0]["value"] if r["levels"] else None
            for g in groups:
                if g["w"] != r["w"]:
                    continue
                gv = g["value"]
                same = (v is None and gv is None and g["x"] == r["x"]) or (
                    v is not None and gv is not None and atr and abs(v - gv) <= CLUSTER_ATR * atr) or (
                    v is not None and gv is not None and not atr and v == gv)
                if same and a["seat"] not in g["seats"]:
                    g["seats"].append(a["seat"]); g["words"].append(r["word"]); break
            else:
                groups.append({"w": r["w"], "value": v, "x": r["x"], "seats": [a["seat"]], "words": [r["word"]],
                               "plain": r["plain"], "when": r["when"]})
    return [g for g in sorted(groups, key=lambda g: -len(g["seats"])) if len(g["seats"]) >= min_seats]


def compile_(a):
    cons = json.load(open(a.consensus))
    rows = _rows(a.export, a.candidates)
    ballots = _ballots(a.forms)
    out_rows, unresolved = [], []
    for c in cons:
        t, verdict = c["ticker"], c["verdict"]
        row = rows.get(t, {})
        atr = C._row_value(row, "atr_14d")
        counting = set((c.get("split") or {}).get("support") or [])
        analysts = []
        for seat in sorted(ballots):
            v = ballots[seat].get(t)
            if not v:
                continue
            blk = v.get("conditions")
            a_ = {"seat": seat, "vote": v.get("vote"), "conviction": v.get("conviction"),
                  "counts": seat in counting or v.get("vote") != "SUPPORT",
                  "lane": (blk or {}).get("lane"), "tf": (blk or {}).get("tf"),
                  "non_price": (blk or {}).get("non_price"), "filed": blk is not None,
                  "buy": [], "confirm": [], "wrong": [], "wait": [], "chase": None}
            if blk:
                for k in ("buy", "confirm", "wrong"):
                    try:
                        a_[k] = _resolve_list(blk.get(k), row)
                    except ValueError as e:
                        a_.setdefault("errors", []).append(f"{k}: {e}")
                for f in blk.get("wait") or []:
                    lv = C.parse_level(f)
                    a_["wait"].append({"field": f, "value": C.resolve_level(lv, row) if lv else None})
                if blk.get("chase"):
                    try:
                        ch = C.resolve(blk["chase"], row); ch["plain"] = C.plain(ch); a_["chase"] = ch
                    except ValueError as e:
                        a_.setdefault("errors", []).append(f"chase: {e}")
                for k in ("buy", "confirm", "wrong"):
                    for r in a_[k]:
                        if not r["resolved"]:
                            unresolved.append(f"{t} {seat} {k} {r['word']}")
            analysts.append(a_)
        supporters = [x for x in analysts if x["vote"] == "SUPPORT"]
        counting_sup = [x for x in supporters if x["counts"]]
        shared_buy = _shared(analysts, True, atr, 2)
        half = max(1, (len(counting_sup) + 1) // 2)
        shared_confirm = _shared(analysts, False, atr, max(2, half))
        waits = [w["value"] for x in counting_sup for w in x["wait"] if w["value"] is not None]
        members = sorted({w["field"] for x in counting_sup for w in x["wait"]})
        chases = [x["chase"] for x in counting_sup if x["chase"] and x["chase"]["levels"]
                  and x["chase"]["levels"][0]["value"] is not None]
        # 2026-10-23 fix: a too-late line only means something ABOVE the buy line it belongs to.
        # An analyst whose own buy sits on an older, lower pivot files a chase that can land under the
        # shared buy (ADP 292.45 vs buy 308.63). Taking the lowest chase across analysts then printed
        # "too late past" BELOW "buy above". Such a chase is that analyst saying "already extended":
        # it is reported as a dissent, never used as the shared line.
        # 2026-10-23 (ACN, XOM, RXO): the yardstick is the HIGHER of the shared buy line and the last
        # close. A too-late line under where the stock already trades fires "chased" on today's close by
        # itself -- whether there is no shared buy (ACN) or the shared buy is a dip below the close (XOM).
        _levels = [g["value"] for g in shared_buy if g["value"] is not None] + [C._row_value(row, "entry")]
        entry_line = max((v for v in _levels if isinstance(v, (int, float))), default=None)
        chase_dissent = []
        if entry_line is not None:
            for x in counting_sup:
                ch = x["chase"]
                if ch in chases and ch["levels"][0]["value"] <= entry_line:
                    chase_dissent.append({"seat": x["seat"], "value": ch["levels"][0]["value"],
                                          "plain": ch["plain"], "buy_line": entry_line})
            chases = [ch for ch in chases if ch["levels"][0]["value"] > entry_line]
        exits = defaultdict(list)
        other_wrong = []
        for x in supporters:
            for r in x["wrong"]:
                if r["levels"] and r["levels"][0]["value"] is not None and r["w"] in (
                        "close_below", "h1_close_below", "trade_below"):
                    exits[(r["w"], r["levels"][0]["value"])].append(x["seat"])
                else:
                    other_wrong.append({"seat": x["seat"], "word": r["word"], "plain": r["plain"]})
        out_rows.append({
            "ticker": t, "verdict": verdict, "lane": c.get("lane"), "conviction": c.get("conviction"),
            "ref_close": C._row_value(row, "entry"), "atr_14d": atr,
            "counting_supporters": sorted(counting),
            "filed": sum(1 for x in supporters if x["filed"]), "supporters": len(supporters),
            "shared": {
                "buy": shared_buy, "confirm": shared_confirm,
                "no_shared_buy": bool(counting_sup) and not shared_buy,
                "wait_zone": ({"lo": min(waits), "hi": max(waits), "members": members} if waits else None),
                "chase": (min(chases, key=lambda r: r["levels"][0]["value"]) if chases else None),
                "chase_dissent": chase_dissent,
            },
            "exits": [{"w": w, "value": v, "seats": s, "plain": f"{'closes' if w == 'close_below' else 'an hourly candle closes' if w == 'h1_close_below' else 'trades'} below {v:g}"}
                      for (w, v), s in sorted(exits.items(), key=lambda kv: -kv[0][1])],
            "other_wrong": other_wrong,
            "analysts": analysts,
            "live": verdict in LIVE_VERDICTS,
        })
    doc = {"schema": SCHEMA, "run_date": a.date, "vocab": C.vocab()["schema"],
           "note": "Compiled from the analysts' own ballots. Decides nothing: verdicts come from consensus.json unchanged.",
           "unresolved": unresolved, "rows": out_rows}
    json.dump(doc, open(a.out, "w"), indent=1)
    if a.md:
        open(a.md, "w").write(render_md(doc))
    if a.html:
        open(a.html, "w").write(render_html(doc))
    live = [r for r in out_rows if r["live"]]
    nf = sum(r["supporters"] - r["filed"] for r in live)
    print(f"compiled {len(out_rows)} names ({len(live)} live); supporters without a conditions block: {nf}; "
          f"no shared buy: {[r['ticker'] for r in live if r['shared']['no_shared_buy']]}; unresolved levels: {len(unresolved)}")
    return 0


def _ledger_rows(r):
    out = []
    for x in r["analysts"]:
        if x["vote"] == "ABSTAIN" and not x["filed"]:
            continue
        acts = " and ".join(c["plain"] for c in x["buy"] + x["confirm"]) or ("—" if not x["non_price"] else "not a price call")
        wrong = " or ".join(c["plain"] for c in x["wrong"]) or "—"
        if x["non_price"]:
            wrong += f" · {x['non_price']}"
        tag = "" if x["counts"] or x["vote"] != "SUPPORT" else " (advisory)"
        out.append((f"{x['seat']} {x['vote'].lower()} c{x['conviction'] or '-'}{tag}", acts, wrong))
    return out


def render_md(doc):
    L = [f"## What each analyst said would make them act, and what would prove them wrong — {doc['run_date']}", ""]
    for r in doc["rows"]:
        if not r["live"]:
            continue
        sh = r["shared"]
        L += [f"### {r['ticker']} · {r['verdict']} · {r['lane'] or ''}", ""]
        if sh["buy"]:
            L.append("**Shared by the supporters:** " + "; ".join(f"{g['plain']} ({len(g['seats'])}: {', '.join(g['seats'])})" for g in sh["buy"]))
        elif sh["no_shared_buy"]:
            L.append("**Shared by the supporters:** none — each supporter named a different trigger (see below).")
        if sh["confirm"]:
            L.append("**Confirmed by:** " + "; ".join(g["plain"] for g in sh["confirm"]))
        if sh["wait_zone"]:
            z = sh["wait_zone"]; L.append(f"**Wait-for area:** {z['lo']:g}–{z['hi']:g} ({', '.join(z['members'])})")
        if sh["chase"]:
            L.append(f"**Too late past:** {sh['chase']['plain']}")
        for d in sh.get("chase_dissent") or []:
            L.append(f"**Already past one analyst's too-late line:** {d['seat']} {d['plain']} "
                     f"(below the shared buy line {d['buy_line']:g})")
        if r["exits"]:
            L.append("**Exit lines, highest first:** " + " · ".join(f"{e['value']:g} ({', '.join(e['seats'])})" for e in r["exits"]))
        L += ["", "| Analyst | Acts when | Wrong when |", "|---|---|---|"]
        L += [f"| {a} | {b} | {c} |" for a, b, c in _ledger_rows(r)]
        L.append("")
    if doc["unresolved"]:
        L.append(f"Levels the export does not serve (declared, not guessed): {len(doc['unresolved'])}.")
    return "\n".join(L) + "\n"


def render_html(doc):
    """One block per live name, keyed by ticker, for the card report. Fixed-layout tables that wrap."""
    T = 'style="width:100%;border-collapse:collapse;font-size:11.5px;table-layout:fixed;word-break:break-word"'
    e = html.escape
    blocks = {}
    for r in doc["rows"]:
        if not r["live"]:
            continue
        sh = r["shared"]
        lines = []
        if sh["buy"]:
            lines.append("<b>Shared:</b> " + e("; ".join(f"{g['plain']} ({len(g['seats'])})" for g in sh["buy"])))
        elif sh["no_shared_buy"]:
            lines.append("<b>Shared:</b> none — supporters named different triggers")
        if sh["confirm"]:
            lines.append("<b>Confirmed by:</b> " + e("; ".join(g["plain"] for g in sh["confirm"])))
        if sh["wait_zone"]:
            z = sh["wait_zone"]; lines.append(f"<b>Wait-for area:</b> {z['lo']:g}–{z['hi']:g}")
        if r["exits"]:
            lines.append("<b>Exit lines:</b> " + e(" · ".join(f"{x['value']:g} ({', '.join(x['seats'])})" for x in r["exits"])))
        tbl = (f'<table {T}><tr style="text-align:left;color:var(--muted)"><th style="width:28%">Analyst</th>'
               '<th>Acts when</th><th>Wrong when</th></tr>' +
               "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td><td>{e(c)}</td></tr>" for a, b, c in _ledger_rows(r)) + "</table>")
        blocks[r["ticker"]] = ('<div class="ledger" style="margin-top:6px">' + "<br>".join(lines) + tbl + "</div>")
    return json.dumps(blocks)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compile")
    c.add_argument("--consensus", default="consensus.json")
    c.add_argument("--forms", default="forms/r2/*.json")
    c.add_argument("--export", default="aqe_daily_export.json")
    c.add_argument("--candidates", default="candidate_set.json")
    c.add_argument("--date", required=True)
    c.add_argument("--out", default="conditions.json")
    c.add_argument("--md"); c.add_argument("--html", help="JSON map ticker -> HTML ledger block for the card report")
    a = ap.parse_args(argv)
    return {"compile": compile_}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
