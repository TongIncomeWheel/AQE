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


LABELS = (("universe", "Universe"), ("seat screens", "Screens"), ("aqe's own scored", "AQE list"), ("nominated", "Nominated"), ("in the room", "In the room"),
          ("cross-exam", "Cross-examined"), ("slated", "Slated"), ("ratified", "Ratified"), ("qa hold", "After QA"), ("vote", "Voted"))


def _label(stage, report):
    """One short plain word per stage for the strip (PM 2026-11-17: the Valen funnel's shape: one clean chronological strip)."""
    low = stage.lower()
    return next((w for k, w in LABELS if low.startswith(k)), stage.split(" (")[0])


def _ensure(f):
    """Older scan_funnel.json files and hand-built dicts carry no step/label: fill them in place, in stage order."""
    for i, st in enumerate(f["stages"]):
        st.setdefault("step", i + 1)
        st.setdefault("label", _label(st["stage"], f.get("report")))
    for n in f["names"]:
        if "step" not in n:
            n["step"] = next((st["step"] for st in f["stages"] if (st.get("short") or st["stage"]) == n.get("stage")), None)
            n["step_label"] = next((st["label"] for st in f["stages"] if st["step"] == n["step"]), None)
    return f


def strip_cells(f):
    """-> [(step, label, count)] strictly in the order the stages happen; the count is what moved ON from that stage."""
    _ensure(f)
    return [(st["step"], st["label"], st["n_out"]) for st in f["stages"]]


def strip_text(f):
    """The strip as one line: 'Universe 1,066 > Screens 175 > Nominated 38 > ...' (plain, no codes)."""
    return " > ".join(f"{lab} {'n/a' if c is None else format(c, ',')}" for _, lab, c in strip_cells(f))


def fell_rows(f):
    """Per-name table rows in the SAME order as the strip: names that fell out at step 1.., then the names that reached the end. -> list of names."""
    _ensure(f)
    end = len(f["stages"]) + 1
    return sorted(f["names"], key=lambda n: ((n.get("step") or end) if n["outcome"] == "fell out" else end + 1, n["ticker"]))


def build(run, report="A", export_by=None, universe_by=None):
    """-> {report, method, stages: [{stage, n_in, n_out, rule, dropped: [{ticker, reason}]}], names: [{ticker, outcome, stage, reason, aqe}], notes}."""
    export_by, universe_by = export_by or {}, universe_by or {}
    man = _j(run, "run_manifest.json", {}) or {}
    method = man.get("method") or ("quant_scan" if report == "C" else "aqe_doors")
    notes, stages = [], []
    sets = _j(run, "seat_sets.json") if report == "A" else None
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
    if report == "A" and isinstance(sets, dict):
        screened = _names([x for v in (sets.get("seats") or {}).values() for x in v])
        n_univ = sets.get("universe_rows")
        stages.append({"stage": "Universe rows scored (market cap $2B+, 10-day volume 500K+, NYSE or NASDAQ)", "n_in": n_univ, "n_out": n_univ, "rule": "the whole screened universe, before any AQE gate", "dropped": []})
        stages.append({"stage": "Seat screens, union", "n_in": n_univ, "n_out": len(screened), "rule": "each seat's own code screen, top 25 names per seat, union of the seven",
                       "dropped": [], "dropped_count": (n_univ - len(screened)) if isinstance(n_univ, int) else None})
    elif report == "C":
        # PM 2026-11-16: the AQE Quant Scan's universe is AQE's OWN scored list (daily_list), nothing from the Standard Scan
        cs = _j(run, "candidate_set.json", {}) or {}
        aqe_list = _names([r.get("ticker") for r in (cs.get("universe") or []) if r.get("source") != "held_book"])
        screened = aqe_list
        if aqe_list:
            stages.append({"stage": "AQE's own scored list (the AQE universe for this scan)", "n_in": len(aqe_list), "n_out": len(aqe_list), "rule": "every name on AQE's daily list, read by aqe-quant with the AQE indicator files", "dropped": []})
    else:
        notes.append("no seat_sets.json in the run dir: the early stages (universe, screens) are not shown for this run")
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
    for i, st in enumerate(stages):
        st["step"] = i + 1
        st["label"] = _label(st["stage"], report)
    for n in names:
        n["step"] = next((st["step"] for st in stages if (st.get("short") or st["stage"]) == n["stage"]), None)
        n["step_label"] = next((st["label"] for st in stages if st["step"] == n["step"]), None)
    return {"report": report, "method": method, "stages": stages, "names": names, "notes": notes, "disclosure": None}


def render_md(f):
    """PM 2026-11-17 (Valen funnel shape): ONE strip, strictly chronological left to right with a count on each stage, then the per-name table in the same stage order."""
    cell = lambda v: "n/a" if v is None else f"{v:,}"
    cs = strip_cells(f)
    L = [f"### Funnel: {'Committee Standard Scan' if f['report'] == 'A' else 'Committee AQE Quant Scan'}", "",
         "| " + " | ".join(f"{i}. {lab}" for i, lab, _ in cs) + " |", "|" + "---|" * len(cs), "| " + " | ".join(cell(c) for _, _, c in cs) + " |", "",
         "What each step does: " + "; ".join(f"{i}. {s['label']}: {s['rule']}" for i, s in zip((c[0] for c in cs), f["stages"])), "",
         "| Step | Ticker | Result | Why (from the tool files) | AQE-listed and AQE scores |", "|---|---|---|---|---|"]
    for n in fell_rows(f):
        fell = n["outcome"] == "fell out"
        L.append(f"| {n.get('step_label') or 'end'} | **{n['ticker']}** | {'fell out' if fell else n['outcome']} | {(n['reason'] if fell else n['reason'] or 'reached the end').replace('|', '/')} | {n['aqe_line']} |")
    for st in f["stages"]:
        if st.get("dropped_count") is not None:
            L.append(f"\n{st['label']}: {st['dropped_count']:,} names left out by the rule above (count only).")
    for note in f["notes"]:
        L += ["", f"> {note}"]
    if f.get("disclosure"):
        L += ["", f["disclosure"]]
    return "\n".join(L) + "\n"


def html_tables(f):
    """Cards-style page: the one-row strip (steps in order, a count under each) and the per-name table in the same order. Every text passes through plain_reason()."""
    import html
    E = lambda x: html.escape(str(x), quote=True)
    cell = lambda v: "n/a" if v is None else f"{v:,}"
    cs = strip_cells(f)
    strip = ("<table><thead><tr>" + "".join(f"<th>{i}. {E(plain_reason(lab))}</th>" for i, lab, _ in cs) + "</tr></thead><tbody><tr>"
             + "".join(f"<td><b>{cell(c)}</b></td>" for _, _, c in cs) + "</tr></tbody></table>")
    counts = (f"<p>What each step does: {E(plain_reason('; '.join(str(st['step']) + '. ' + st['label'] + ': ' + str(st['rule']) for st in f['stages'])))}</p>"
              + "".join(f"<p>{E(plain_reason(st['label']))}: {st['dropped_count']:,} names left out (count only).</p>" for st in f["stages"] if st.get("dropped_count") is not None))
    rows = "".join(
        f"<tr><td>{E(plain_reason(n.get('step_label') or 'end'))}</td><td><b>{E(n['ticker'])}</b></td><td>{E(plain_reason('fell out' if n['outcome'] == 'fell out' else n['outcome']).lower())}</td><td>"
        + E(plain_reason(n["reason"] or "reached the end")) + f"</td><td>{E(plain_reason(n['aqe_plain']))}</td></tr>"
        for n in fell_rows(f))
    return (strip + counts + '<table><thead><tr><th>Step</th><th>Name</th><th>Result</th><th>Why, from the tool files</th><th>AQE-listed and AQE scores</th></tr></thead><tbody>' + rows + "</tbody></table>")


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
