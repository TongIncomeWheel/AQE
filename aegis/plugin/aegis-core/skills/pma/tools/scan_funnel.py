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


SHORT_WORDS = 12


def _words(t, n=SHORT_WORDS):
    """At most n words, cut on a word and ended with a full stop mark of '...' only when something was dropped."""
    w = " ".join(str(t or "").split()).split(" ")
    return " ".join(w) if len(w) <= n else " ".join(w[:n]).rstrip(",;:") + "..."


def _voice(v):
    return str(v or "a seat").replace("-", " ")


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
    notes, stages, near = [], [], []
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
    drop_room = [{"ticker": t, "reason": "cut by the ranking machinery", "short": "cut by the ranking machinery before the room"} for t in cut_mach] + [{"ticker": t, "reason": "off the served universe", "short": "not in the served universe"} for t in off_uni]
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
        who = None
        for c in (fnames.get(t) or {}).get("claims") or []:
            for r in c.get("rulings") or []:
                if r.get("ruling") == "REFUTE":
                    who = r.get("reviewer")
                    break
            if who:
                break
        cross_drop.append({"ticker": t, "reason": reason, "short": _words(f"cross-examined: refuted by {_voice(who)}" if who else "cross-examined: refuted by the evidence")})
    for t in out:
        cross_drop.append({"ticker": t, "reason": (fun.get("rule") or {}).get("out") or "no SUPPORT vote at the blind vote", "short": "cross-examined: no seat supported it at the blind vote"})
    if fun:
        stages.append({"stage": "Cross-examination (survivors move on)", "short": "cross-examination", "n_in": len(room), "n_out": len(surv), "rule": _cut((fun.get("rule") or {}).get("survives"), 160), "dropped": cross_drop})
    else:
        notes.append("no funnel.json: the cross-examination stage is not shown for this run")

    by = {c["ticker"]: c for c in cons}
    if report == "A":
        slated = _names([x["ticker"] for x in slate.get("tickets") or []])
        sup = lambda t: len(((by.get(t) or {}).get("split") or {}).get("support") or [])          # noqa: E731
        floor = min((sup(t) for t in slated if t in by), default=None)                             # the fewest supporters of any slated name
        def _ns_short(t):
            n = sup(t)
            return f"not slated: {n} seat{'s' if n != 1 else ''} supported it" + (f", the lowest slated had {floor}" if floor is not None else "")
        not_slated = [{"ticker": t, "reason": "not slated: " + _cut(next((o.get("objection") for o in ((by.get(t) or {}).get("objections") or [])), "the room did not carry it to the slate"), OBJ_LEN),
                       "short": _ns_short(t)} for t in surv if t not in slated]
        for d_ in not_slated:                                                                   # a CIO can act on a name within ONE seat of the slate floor
            n = sup(d_["ticker"])
            if floor is not None and n >= floor - 1:
                near.append({"ticker": d_["ticker"], "where": "not slated", "what": f"{n} of the seats supported it; the lowest slated name had {floor}",
                             "clears": "one more seat's support, or a seat moving it to conviction"})
        stages.append({"stage": "Slated", "short": "not slated", "n_in": len(surv), "n_out": len(slated), "rule": "the Chair's slate by code from the seats' own tier-2 forms", "dropped": not_slated})
        rat = [c for c in cons if c.get("ticker") in slated]
        agreed = [c["ticker"] for c in rat if c.get("status") == "AGREED"]
        contested = [c["ticker"] for c in rat if c.get("status") == "CONTESTED"]
        dropped_r = [c for c in rat if c.get("status") == "DROPPED"]
        stages.append({"stage": "Ratified (AGREED / CONTESTED / DROPPED)", "short": "ratified", "n_in": len(slated), "n_out": len(agreed) + len(contested),
                       "rule": f"{len(agreed)} AGREED, {len(contested)} CONTESTED, {len(dropped_r)} DROPPED by the committee's objections",
                       "dropped": [{"ticker": c["ticker"], "reason": "dropped: " + (_cut(f"{(c.get('objections') or [{}])[0].get('voice')}: {(c.get('objections') or [{}])[0].get('objection')}", OBJ_LEN) if c.get("objections") else "objections on file"),
                                    "short": _words(f"dropped at ratification: {_voice((c.get('objections') or [{}])[0].get('voice'))} objected" if c.get("objections") else "dropped at ratification")} for c in dropped_r]})
        holds = [h for h in (rec.get("qa") or {}).get("holds") or []]
        stages.append({"stage": "QA hold", "short": "QA hold", "n_in": len(agreed) + len(contested), "n_out": len(agreed) + len(contested) - len(holds), "rule": "the QA seat holds a ticket whose ratifiers' objections it cannot see answered",
                       "dropped": [{"ticker": h.get("ticker"), "reason": "held: " + _cut(h.get("question"), OBJ_LEN), "short": _words("held by QA: " + str(h.get("question") or "a question is open"))} for h in holds]})
        for h in holds:
            near.append({"ticker": h.get("ticker"), "where": "QA hold", "what": _words("QA asks: " + str(h.get("question") or "a question is open"), 20),
                         "clears": "an answer to that question"})
    else:
        adv = [c["ticker"] for c in cons if c.get("verdict") == "ADVANCE"]
        hold = [c["ticker"] for c in cons if c.get("verdict") == "HOLD-FOR-CONDITIONS"]
        pas = [c for c in cons if c.get("verdict") == "PASS"]
        stages.append({"stage": "Vote by all eight seats (ADVANCE / HOLD / PASS)", "short": "vote", "n_in": len(surv) or len(room), "n_out": len(adv) + len(hold),
                       "rule": f"{len(adv)} ADVANCE, {len(hold)} HOLD-FOR-CONDITIONS, {len(pas)} PASS",
                       "dropped": [{"ticker": c["ticker"], "reason": "passed: " + (_cut(f"{(c.get('objections') or [{}])[0].get('voice')}: {(c.get('objections') or [{}])[0].get('objection')}", OBJ_LEN) if c.get("objections") else "no support at the vote"),
                                    "short": _words(f"passed at the vote: {_voice((c.get('objections') or [{}])[0].get('voice'))} objected" if c.get("objections") else "passed at the vote: no support")} for c in pas]})

    # per-name table: every name that reached the room, with its outcome and AQE tag
    dropped_at, short_at = {}, {}
    for st in stages:
        for d in st.get("dropped") or []:
            dropped_at.setdefault(d["ticker"], (st.get("short") or st["stage"], d["reason"]))
            short_at.setdefault(d["ticker"], d.get("short") or _words(d["reason"]))
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
        names.append({"ticker": t, "outcome": outcome, "stage": stage, "reason": reason, "short": short_at.get(t) or _words(reason), "aqe_listed": x["aqe_listed"], "aqe_lists": x["aqe_lists"],
                      "aqe_line": x["line"], "aqe_plain": x["plain_line"]})
    for i, st in enumerate(stages):
        st["step"] = i + 1
        st["label"] = _label(st["stage"], report)
    for n in names:
        n["step"] = next((st["step"] for st in stages if (st.get("short") or st["stage"]) == n["stage"]), None)
        n["step_label"] = next((st["label"] for st in stages if st["step"] == n["step"]), None)
    for nm in near:                                                                                 # tag every near miss with its AQE listing too
        x = AL.listing(nm["ticker"], export_by, universe_by)
        nm["aqe_lists"] = x["aqe_lists"]
    return {"report": report, "method": method, "stages": stages, "names": names, "near_misses": near, "notes": notes, "disclosure": None}


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


def _tbl(head, rows):
    return '<div class="tbl"><table><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>"


def html_actionable(f, fx=None):
    """PM 2026-11-17 ("What's the purpose of showing me the nominated 82 names with full of prose ... how is it actionable"): ACTIONABLE FIRST, AUDIT BEHIND A CLICK.
    Order: the numbered strip with its counts; one line per count-only step saying plainly that those names are counted, NOT listed; the near misses a CIO can act on (a name within one seat of the slate
    floor, a name the QA hold stopped, each with what would clear it) as a short table that stays visible; then a CLOSED details block 'Audit: names that fell out (N)' with ONE short reason per name
    (at most 12 words, built by code from the stage rule). The full seat prose stays in the brief (scan_funnel.md) and the run files. Every text passes through `fx` (the plain-words filter)."""
    import html
    E = lambda x: html.escape(str(x), quote=True)
    fx = fx or plain_reason
    cell = lambda v: "n/a" if v is None else f"{v:,}"
    cs = strip_cells(f)
    strip = ("<table><thead><tr>" + "".join(f"<th>{i}. {E(fx(lab))}</th>" for i, lab, _ in cs) + "</tr></thead><tbody><tr>"
             + "".join(f"<td><b>{cell(c)}</b></td>" for _, _, c in cs) + "</tr></tbody></table>")
    does = f"<p>What each step does: {E(fx('; '.join(str(st['step']) + '. ' + st['label'] + ': ' + str(st['rule']) for st in f['stages'])))}</p>"
    counted = "".join(f"<p>{E(fx(st['label']))}: {st['dropped_count']:,} names were not carried forward. They are counted here, not listed.</p>"
                      for st in f["stages"] if st.get("dropped_count") is not None)
    near = f.get("near_misses") or []
    if near:
        nm = ("<p><b>Near misses a CIO can act on</b></p>"
              + _tbl(["Name", "Where it stopped", "What happened", "What would clear it", "AQE list"],
                     [[f"<b>{E(n['ticker'])}</b>", E(fx(n["where"])), E(fx(n["what"])), E(fx(n["clears"])), E(fx(_aqe_short(n.get("aqe_lists"))))] for n in near]))
    else:
        nm = "<p><b>Near misses:</b> none. No name came within one seat of the slate floor and the QA hold stopped none.</p>"
    rows = [[E(fx(n.get("step_label") or "end")), f"<b>{E(n['ticker'])}</b>", E(fx(n.get("short") or _words(n["reason"]))), E(fx(_aqe_short(n.get("aqe_lists"))))]
            for n in fell_rows(f) if n["outcome"] == "fell out"]
    audit = (f"<details><summary>Audit: names that fell out ({len(rows)})</summary>"
             + _tbl(["Step", "Name", "Why it fell out", "AQE list"], rows) + "</details>")
    reached = [n for n in f["names"] if n["outcome"] != "fell out"]
    end = (f"<p><b>Reached the end ({len(reached)}):</b> " + ", ".join(f"<b>{E(n['ticker'])}</b> {E(fx(str(n['outcome']).lower().replace('-', ' ')))}" for n in reached) + ".</p>") if reached else ""
    return strip + does + counted + end + nm + audit


def _aqe_short(lists):
    return "not on an AQE list" if not lists or lists == "none" else "AQE: " + str(lists).replace("|", ", ")


def html_tables(f):
    """The compact report page: the same actionable-first block the Cards use."""
    return html_actionable(f)


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
