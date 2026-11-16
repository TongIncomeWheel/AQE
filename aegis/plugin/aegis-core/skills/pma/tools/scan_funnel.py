#!/usr/bin/env python3
"""scan_funnel.py -- the funnel strip for the Committee Standard Scan and the Committee AQE Quant Scan (PM 2026-11-16).

The PM wants to see, for each scan, the count at every narrowing stage and, for each stage, the names that fell out with the one-line reason FROM THE TOOL
FILES (never hand-written), each carrying its AQE tag (AQE-listed or not, plus AQE scores), so he can see what the committee cut that AQE had listed and what
it kept that AQE had not. Pure code over files already in the run dir; no model, no network.

  Standard Scan (A):  universe rows -> seven seat screens (union) -> nominated -> in the room -> cross-examination (survivors / dropped / out)
                      -> slated -> ratified (AGREED / CONTESTED / DROPPED) -> QA hold
  AQE Quant Scan (C): universe rows -> quant screen -> aqe-quant nominations -> in the room -> cross-examination -> vote (advance / hold / pass)

The early stages drop hundreds of names, so those print a COUNT and the rule (listing 984 names would hide the story); every stage from "in the room" on
lists each name that fell out, one line each, with the tool file's own reason.

    scan_funnel.py --run-dir . [--export aqe_daily_export_wu.json] [--universe-rows aqe_universe_rows.json] [--report A|C] [--out scan_funnel.json] [--md scan_funnel.md]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aqe_listing as AL  # noqa: E402

CROSS_LEN, OBJ_LEN = 170, 170


def plain_reason(v):
    """The seats' own words made safe for the Cards plain-words gate: field names become English (card_words.no_raw_words), charter codes (C5, R7, (C10, C12)) and
    ALL_CAPS_TOKENS are taken out, a token cut short by the one-line limit is dropped. The brief keeps the full quote; only the Cards page uses this."""
    import re
    from card_words import no_raw_words
    t = no_raw_words(str(v))
    t = re.sub(r"\s*\((?:[RC]\d{1,2}(?:\s*[,;]\s*)?)+\)", "", t)
    t = re.sub(r"\b[RC]\d{1,2}\b", "", t)
    t = re.sub(r"\b[A-Z]{2,}(?:_[A-Z]+)+\b", lambda m: m.group(0).replace("_", " ").lower(), t)
    t = re.sub(r"\b[A-Z]{3,}_[A-Z]?\b", "", t)
    t = t.replace("W/D/H1", "weekly, daily and hourly").replace("%K/%D", "stochastic")
    t = re.sub(r"\bADX\b", "trend strength", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def _j(run, name, default=None):
    p = os.path.join(run, name)
    if not os.path.exists(p):
        return default
    try:
        return json.load(open(p, encoding="utf-8"))
    except ValueError:
        return default


def _cut(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "..."


def _names(x):
    out = []
    for i in x or []:
        out.append(i["ticker"] if isinstance(i, dict) else str(i).split("(")[0])
    return list(dict.fromkeys(out))


def build(run, report="A", export_by=None, universe_by=None):
    """-> {report, method, stages: [{stage, n_in, n_out, rule, dropped: [{ticker, reason}]}], names: [{ticker, outcome, stage, reason, aqe}], notes}."""
    export_by, universe_by = export_by or {}, universe_by or {}
    man = _j(run, "run_manifest.json", {}) or {}
    method = man.get("method") or ("quant_scan" if report == "C" else "aqe_doors")
    notes, stages = [], []
    sets = _j(run, "seat_sets.json") if report == "A" else _j(run, "quant_screen.json")
    tally = _j(run, "tally.json", []) or []
    p4 = _j(run, "phase4.json", {}) or {}
    fun = _j(run, "funnel.json", {}) or {}
    cons = _j(run, "consensus.json", []) or []
    slate = _j(run, "slate.json", {}) or {}
    rec = _j(run, "committee_record.json", {}) or {}

    room = _names(p4.get("deliberation_set"))
    nominated = _names([t["ticker"] for t in tally])
    held = _names(p4.get("held_seated"))
    screened = None
    if isinstance(sets, dict):
        if report == "A":
            screened = _names([x for v in (sets.get("seats") or {}).values() for x in v])
        else:
            screened = _names(sets.get("names") and list((sets.get("why") or {}).keys()) or [])
        n_univ = sets.get("universe_rows")
        stages.append({"stage": "Universe rows scored (market cap $2B+, 10-day volume 1.5M+, NYSE or NASDAQ)", "n_in": n_univ, "n_out": n_univ, "rule": "the whole screened universe, before any AQE gate", "dropped": []})
        rule = (sets.get("rule") or "") if report == "C" else "each seat's own code screen, top 25 names per seat, union of the seven"
        stages.append({"stage": "Seat screens, union" if report == "A" else "AQE quant screen", "n_in": n_univ, "n_out": len(screened), "rule": _cut(rule, 200),
                       "dropped": [], "dropped_count": (n_univ - len(screened)) if isinstance(n_univ, int) else None})
    else:
        notes.append("no seat_sets.json / quant_screen.json in the run dir: the early stages (universe, screens) are not shown for this run")
    if tally or nominated:
        base = screened if screened is not None else None
        stages.append({"stage": "Nominated (any seat, any conviction)" if report == "A" else "Nominated by aqe-quant", "n_in": len(base) if base is not None else None,
                       "n_out": len(nominated), "rule": "a seat names it at round 1 (cap six per seat)" if report == "A" else "aqe-quant names it at round 1 (cap six)",
                       "dropped": [], "dropped_count": (len(base) - len(nominated)) if base is not None else None})
    cut_mach = _names(p4.get("nominations_cut_by_machinery"))
    off_uni = _names(p4.get("nominations_off_universe"))
    drop_room = [{"ticker": t, "reason": "cut by the ranking machinery"} for t in cut_mach] + [{"ticker": t, "reason": "off the served universe"} for t in off_uni]
    stages.append({"stage": "In the room (nominated plus the held book)", "short": "the room", "n_in": len(nominated), "n_out": len(room), "rule": "every nomination is seated; the held book is always seated; no AQE door adds a name",
                   "dropped": drop_room, "added_held": held})

    # cross-examination (funnel.json)
    surv, dropped, out = _names(fun.get("survivors")), _names(fun.get("dropped")), _names(fun.get("out"))
    fnames = fun.get("names") or {}
    cross_drop = []
    for t in dropped:
        reason = "refuting evidence"
        for c in (fnames.get(t) or {}).get("claims") or []:
            for r in c.get("rulings") or []:
                if r.get("ruling") == "REFUTE":
                    reason = f"{r.get('reviewer')}: {_cut(r.get('evidence'), CROSS_LEN)}"
                    break
            else:
                continue
            break
        cross_drop.append({"ticker": t, "reason": reason})
    for t in out:
        cross_drop.append({"ticker": t, "reason": (fun.get("rule") or {}).get("out") or "no SUPPORT vote at the blind vote"})
    if fun:
        stages.append({"stage": "Cross-examination (survivors move on)", "short": "cross-examination", "n_in": len(room), "n_out": len(surv), "rule": _cut((fun.get("rule") or {}).get("survives"), 160), "dropped": cross_drop})
    else:
        notes.append("no funnel.json: the cross-examination stage is not shown for this run")

    by = {c["ticker"]: c for c in cons}
    if report == "A":
        slated = _names([x["ticker"] for x in slate.get("tickets") or []])
        not_slated = [{"ticker": t, "reason": "not slated: " + _cut(next((o.get("objection") for o in ((by.get(t) or {}).get("objections") or [])), "the room did not carry it to the slate"), OBJ_LEN)}
                      for t in surv if t not in slated]
        stages.append({"stage": "Slated", "short": "not slated", "n_in": len(surv), "n_out": len(slated), "rule": "the Chair's slate by code from the seats' own tier-2 forms", "dropped": not_slated})
        rat = [c for c in cons if c.get("ticker") in slated]
        agreed = [c["ticker"] for c in rat if c.get("status") == "AGREED"]
        contested = [c["ticker"] for c in rat if c.get("status") == "CONTESTED"]
        dropped_r = [c for c in rat if c.get("status") == "DROPPED"]
        stages.append({"stage": "Ratified (AGREED / CONTESTED / DROPPED)", "short": "ratified", "n_in": len(slated), "n_out": len(agreed) + len(contested),
                       "rule": f"{len(agreed)} AGREED, {len(contested)} CONTESTED, {len(dropped_r)} DROPPED by the committee's objections",
                       "dropped": [{"ticker": c["ticker"], "reason": "dropped: " + (_cut(f"{(c.get('objections') or [{}])[0].get('voice')}: {(c.get('objections') or [{}])[0].get('objection')}", OBJ_LEN) if c.get("objections") else "objections on file")} for c in dropped_r]})
        holds = [h for h in (rec.get("qa") or {}).get("holds") or []]
        stages.append({"stage": "QA hold", "short": "QA hold", "n_in": len(agreed) + len(contested), "n_out": len(agreed) + len(contested) - len(holds), "rule": "the QA seat holds a ticket whose ratifiers' objections it cannot see answered",
                       "dropped": [{"ticker": h.get("ticker"), "reason": "held: " + _cut(h.get("question"), OBJ_LEN)} for h in holds]})
    else:
        adv = [c["ticker"] for c in cons if c.get("verdict") == "ADVANCE"]
        hold = [c["ticker"] for c in cons if c.get("verdict") == "HOLD-FOR-CONDITIONS"]
        pas = [c for c in cons if c.get("verdict") == "PASS"]
        stages.append({"stage": "Vote by all eight seats (ADVANCE / HOLD / PASS)", "short": "vote", "n_in": len(surv) or len(room), "n_out": len(adv) + len(hold),
                       "rule": f"{len(adv)} ADVANCE, {len(hold)} HOLD-FOR-CONDITIONS, {len(pas)} PASS",
                       "dropped": [{"ticker": c["ticker"], "reason": "passed: " + (_cut(f"{(c.get('objections') or [{}])[0].get('voice')}: {(c.get('objections') or [{}])[0].get('objection')}", OBJ_LEN) if c.get("objections") else "no support at the vote")} for c in pas]})

    # per-name table: every name that reached the room, with its outcome and AQE tag
    dropped_at = {}
    for st in stages:
        for d in st.get("dropped") or []:
            dropped_at.setdefault(d["ticker"], (st.get("short") or st["stage"], d["reason"]))
    names = []
    for t in room:
        if t in dropped_at:
            stage, reason = dropped_at[t]
            outcome = "fell out"
        else:
            c = by.get(t) or {}
            stage = "reached the end"
            outcome = c.get("verdict") or "in the room"
            reason = c.get("status") or ""
        x = AL.listing(t, export_by, universe_by)
        names.append({"ticker": t, "outcome": outcome, "stage": stage, "reason": reason, "aqe_listed": x["aqe_listed"], "aqe_lists": x["aqe_lists"],
                      "aqe_line": x["line"], "aqe_plain": x["plain_line"]})
    return {"report": report, "method": method, "stages": stages, "names": names, "notes": notes, "disclosure": AL.DISCLOSURE if method == "whole_universe" else None}


def render_md(f):
    def cell(v):
        return "n/a" if v is None else f"{v:,}"
    L = [f"### Funnel: {'Committee Standard Scan' if f['report'] == 'A' else 'Committee AQE Quant Scan'}", "",
         "| Stage | In | Out | What fell out |", "|---|---|---|---|"]
    for s in f["stages"]:
        fell = (f"{s['dropped_count']:,} names (count only: the rule is {s['rule']})" if s.get("dropped_count") is not None
                else (", ".join(f"**{d['ticker']}**" for d in s["dropped"]) or "none") if s.get("dropped") is not None else "none")
        L.append(f"| {s['stage']} | {cell(s['n_in'])} | {cell(s['n_out'])} | {fell} |")
    L += ["", "| Ticker | Result | Where and why (from the tool files) | AQE-listed and AQE scores |", "|---|---|---|---|"]
    for n in f["names"]:
        where = f"{n['stage']}: {n['reason']}" if n["outcome"] == "fell out" else f"{n['outcome']} ({n['reason']})"
        L.append(f"| **{n['ticker']}** | {n['outcome']} | {where.replace('|', '/')} | {n['aqe_line']} |")
    for note in f["notes"]:
        L += ["", f"> {note}"]
    if f.get("disclosure"):
        L += ["", f["disclosure"]]
    return "\n".join(L) + "\n"


def html_tables(f):
    """Two plain tables for a Cards-style page (the compact B/C page): the stage strip and one line per name. Every text is passed through plain_reason()."""
    import html
    E = lambda x: html.escape(str(x), quote=True)
    cell = lambda v: "n/a" if v is None else f"{v:,}"
    strip = "".join(
        f"<tr><td>{E(plain_reason(st['stage']))}</td><td>{cell(st['n_in'])}</td><td>{cell(st['n_out'])}</td><td>"
        + (f"{st['dropped_count']:,} names (count only)" if st.get("dropped_count") is not None else (", ".join(f"<b>{E(d['ticker'])}</b>" for d in st["dropped"]) or "none")) + "</td></tr>"
        for st in f["stages"])
    rows = "".join(
        f"<tr><td><b>{E(n['ticker'])}</b></td><td>{E(plain_reason(n['outcome']).lower())}</td><td>"
        + E(plain_reason(f"{n['stage']}: {n['reason']}" if n["outcome"] == "fell out" else f"{n['outcome']} ({n['reason']})")) + f"</td><td>{E(plain_reason(n['aqe_plain']))}</td></tr>"
        for n in f["names"])
    return ('<table><thead><tr><th>Stage</th><th>In</th><th>Out</th><th>What fell out</th></tr></thead><tbody>' + strip + "</tbody></table>"
            '<table><thead><tr><th>Name</th><th>Result</th><th>Where it fell out and why, from the tool files</th><th>AQE-listed and AQE scores</th></tr></thead><tbody>' + rows + "</tbody></table>")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", default=".")
    ap.add_argument("--report", default=None, help="A or C (default: the run manifest's report, else A)")
    ap.add_argument("--export", default=None)
    ap.add_argument("--universe-rows", default=None)
    ap.add_argument("--out", default="scan_funnel.json")
    ap.add_argument("--md", default="scan_funnel.md")
    a = ap.parse_args(argv)
    man = _j(a.run_dir, "run_manifest.json", {}) or {}
    report = (a.report or man.get("report") or "A").upper()
    exp = a.export or next((os.path.join(a.run_dir, n) for n in ("aqe_daily_export_wu.json", "aqe_daily_export.json") if os.path.exists(os.path.join(a.run_dir, n))), None)
    eb, ub = AL.load_rows(exp, a.universe_rows) if exp else ({}, {})
    f = build(a.run_dir, report, eb, ub)
    json.dump(f, open(a.out, "w", encoding="utf-8"), indent=1)
    md = render_md(f)
    open(a.md, "w", encoding="utf-8").write(md)
    print(md)
    print(f"receipt: scan_funnel: {len(f['stages'])} stages, {len(f['names'])} names in the room")
    return 0


if __name__ == "__main__":
    sys.exit(main())
