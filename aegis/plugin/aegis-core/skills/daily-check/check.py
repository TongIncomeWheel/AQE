#!/usr/bin/env python3
"""daily-check — the Checker (operating model E1, PM 2026-10-30). READ-ONLY. Prints `Healthy` or what broke.

  check.py ready --last-run aegis/output/aqe_last_run.json [--today YYYY-MM-DD]
  check.py chain --run-dir aegis/output/pma/run/<date> --date <date> [--levels pma_levels.json]
                 [--run-yaml <RUN.yaml>] [--ceiling-tokens 1357500]
  check.py data  --output-dir aegis/output [--run-yaml <RUN.yaml>]     (the AQE -> voices HANDOFF gate)
  check.py all   (ready + data + chain)

Exit 0 = Healthy. Exit 1 = at least one FAIL line. Exit 2 = could not even read an input (also a failure --
a checker that cannot see is not green). Zero dependencies beyond the standard library; RUN.yaml is read with
the plugin's own mini loader when it is importable, else the step list falls back to the known 22 steps.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUN_YAML = os.path.abspath(os.path.join(HERE, "..", "pma", "RUN.yaml"))
DEFAULT_CEILING = int(1.5 * 905_000)          # 1.5x the measured baseline (DECISIONS s4, design default)
SLATE_CAP = 15
KNOWN_STEPS = ["INBOX-CLEAN", "GATHER", "PREPARE", "NOMINATE", "PM-LENS", "RANK", "CHALLENGE", "VOTE", "FLOOR",
               "SLATE", "RATIFY", "QA", "DECIDE", "CONDITIONS", "REPEAT-WATCH", "BRACKET", "SCORECARD", "WRITE",
               "CHECK", "LEVELS", "REPORT", "PUBLISH"]


def _sgt_today():
    try:
        from zoneinfo import ZoneInfo
        return _dt.datetime.now(ZoneInfo("Asia/Singapore")).date().isoformat()
    except Exception:                               # no tzdata: UTC+8 by hand
        return (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).date().isoformat()


def _load(path, what, fails):
    if not path or not os.path.exists(path):
        fails.append(f"{what}: MISSING ({path})")
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:
        fails.append(f"{what}: unreadable ({e.__class__.__name__})")
        return None


def _steps_from_run_yaml(path):
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(path), "tools"))
        import preflight_run                        # the plugin's own mini loader
        M = preflight_run.mini_yaml(open(path, encoding="utf-8").read())
        names = [s["name"] for s in M.get("steps", []) if isinstance(s, dict) and s.get("name")]
        return names or KNOWN_STEPS
    except Exception:
        return KNOWN_STEPS


def check_ready(last_run_path, today=None):
    """READY = AQE wrote aqe_last_run.json LAST, dated today (SGT), status success."""
    fails, notes = [], []
    today = today or _sgt_today()
    d = _load(last_run_path, "aqe_last_run.json", fails)
    if d is None:
        return fails, notes
    date = d.get("date_sgt") or d.get("date")
    status = str(d.get("status", "")).lower()
    if date != today:
        fails.append(f"AQE run is for {date}, not today {today} -- NOT READY (stale)")
    if status != "success":
        fails.append(f"AQE status is {status!r}, not success" + (" -- export may be current but a tail step failed" if status == "partial" else ""))
    ps = d.get("packets_status")
    if ps and "published" in str(ps).lower() and "/" in str(ps):
        try:
            got, tot = str(ps).split("published:")[1].strip().split()[0].split("/")
            if got != tot:
                fails.append(f"voice packets {got}/{tot} published")
        except Exception:
            notes.append(f"packets_status unparsed: {ps}")
    notes.append(f"AQE run {date} status {status}; started {d.get('started_at') or d.get('started')}, finished {d.get('finished_at') or d.get('finished')}")
    return fails, notes


def check_chain(run_dir, date, levels_path=None, run_yaml=DEFAULT_RUN_YAML, ceiling=DEFAULT_CEILING):
    fails, notes = [], []
    steps = _steps_from_run_yaml(run_yaml)
    M = _load(os.path.join(run_dir, "run_manifest.json"), "run_manifest.json", fails)
    obj = os.path.join(run_dir, "PM_OBJECTION.md")
    if os.path.exists(obj):
        try:
            first = open(obj, encoding="utf-8", errors="replace").read().strip().splitlines()[:2]
        except Exception:
            first = []
        fails.append("PM OBJECTION on file (PM_OBJECTION.md): " + (" / ".join(first) or "(empty file)") + " -- today's levels are NOT confirmed; no default load")
    if M is not None:
        st = M.get("steps") or {}
        for s in steps:
            status = (st.get(s) or {}).get("status", "pending")
            if status not in ("done", "degraded"):
                fails.append(f"step {s}: {status}")
            elif status == "degraded":
                notes.append(f"step {s}: degraded -- " + "; ".join(str(x) for x in (st[s].get("degradations") or st[s].get("notes") or [])[:2]))
        if M.get("date") and date and M["date"] != date:
            fails.append(f"run_manifest.json is for {M['date']}, not {date}")
        est = 0
        for s, row in st.items():
            c = row.get("cost") or {}
            # review finding 5 (2026-11-01): the registrar stores spawns/inlined_bytes/returned_bytes and derives
            # est_tokens only when printing -- mirror registrar._est_tokens (bytes / 4) so the ceiling can trip.
            if c.get("est_tokens"):
                est += int(c["est_tokens"])
            elif c and not c.get("tool_only"):
                est += int((int(c.get("inlined_bytes") or 0) + int(c.get("returned_bytes") or 0)) / 4.0)
            else:
                est += int(row.get("tokens") or 0)
        notes.append(f"spend est {est:,} tokens (ceiling {ceiling:,})")
        if est > ceiling:
            fails.append(f"SPEND OVER CEILING: est {est:,} > {ceiling:,} tokens -- tell the PM")
    C = _load(os.path.join(run_dir, "consensus.json"), "consensus.json", fails)
    if C is not None:
        if not isinstance(C, list) or not C:
            fails.append("consensus.json is empty -- no verdicts")
        else:
            no_status = [c.get("ticker") for c in C if "status" not in c]
            if no_status:
                fails.append(f"consensus.json rows without `status` (the retired rule ran?): {no_status[:6]}")
            by = {}
            for c in C:
                by[c.get("status")] = by.get(c.get("status"), 0) + 1
            notes.append("verdicts: " + ", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda x: str(x[0]))))
    R = _load(os.path.join(run_dir, "committee_record.json"), "committee_record.json", fails)
    if R is not None:
        n_dec = len(R.get("deciders_present") or [])
        rows = R.get("rows") or []
        if n_dec == 0 or not rows:
            fails.append("committee_record.json has no deciders / no rows (R35)")
        else:
            per = len({r.get("ticker") for r in rows})
            if len(rows) != n_dec * per:
                fails.append(f"committee_record.json: {len(rows)} rows != {n_dec} deciders x {per} names")
            notes.append(f"record: {n_dec} deciders x {per} names")
    S = _load(os.path.join(run_dir, "slate.json"), "slate.json", fails)
    if S is not None:
        n = len(S.get("tickets") or [])
        if n > SLATE_CAP:
            fails.append(f"slate.json has {n} tickets > {SLATE_CAP} (R34)")
        notes.append(f"slate {n} tickets")
    F = _load(os.path.join(run_dir, "floor_check.json"), "floor_check.json", fails)
    if F is not None and F.get("ok") is not True:
        fails.append("floor_check.json not ok: " + "; ".join(F.get("errors") or ["(no reason)"])[:300])
    if levels_path:
        L = _load(levels_path, "pma_levels.json", fails)
        if L is not None:
            ld = L.get("run_date") or L.get("date") or (L.get("meta") or {}).get("run_date")
            if date and ld != date:
                fails.append(f"pma_levels.json is for {ld}, not {date} -- today's levels are NOT being watched")
    return fails, notes


PM_ONLY_FIELDS = ("qs_market",)          # R3: PM-only, must never reach a seat packet


def _date_of(v):
    """YYYY-MM-DD of an ISO timestamp (UTC ones are shifted to SGT first) or a date string."""
    if not v:
        return None
    v = str(v)
    try:
        if "T" in v or "+" in v or v.endswith("Z"):
            ts = _dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
            if ts.tzinfo is not None:
                ts = ts.astimezone(_dt.timezone(_dt.timedelta(hours=8)))
            return ts.date().isoformat()
    except Exception:
        pass
    return v[:10]


def _deciders(run_yaml):
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(run_yaml), "tools"))
        import preflight_run
        M = preflight_run.mini_yaml(open(run_yaml, encoding="utf-8").read())
        d = (M.get("parameters") or {}).get("deciders")
        if isinstance(d, list) and d:
            return [str(x) for x in d]
    except Exception:
        pass
    return ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]


def check_data(output_dir, run_yaml=DEFAULT_RUN_YAML):
    """THE HANDOFF GATE (PM 2026-11-01: 'before we run PMA we need the data agent to check data delivery and
    integrity from AQE to voices handoff'). Everything the seats will read, proven consistent with each other
    and with the run that produced them. Read-only; a FAIL line per defect; never 'probably fine'."""
    fails, notes = [], []
    od = output_dir
    LR = _load(os.path.join(od, "aqe_last_run.json"), "aqe_last_run.json", fails)
    EX = _load(os.path.join(od, "aqe_daily_export.json"), "aqe_daily_export.json", fails)
    CS = _load(os.path.join(od, "candidate_set.json"), "candidate_set.json", fails)
    CR = _load(os.path.join(od, "aqe_crown_macro.json"), "aqe_crown_macro.json", fails)
    VA = _load(os.path.join(od, "aqe_valen_dashboard.json"), "aqe_valen_dashboard.json", fails)
    run_date = (LR or {}).get("date_sgt")
    if LR is not None:
        if str(LR.get("status", "")).lower() != "success":
            fails.append(f"aqe_last_run status {LR.get('status')!r} -- the run did not finish clean")
        notes.append(f"run {run_date}: started {LR.get('started_at')}, exported {LR.get('exported_at')}, finished {LR.get('finished_at')}")
    # --- the export ---
    daily = []
    if EX is not None:
        daily = EX.get("daily_list") or []
        if not daily:
            fails.append("export daily_list is EMPTY")
        if run_date and _date_of(EX.get("date")) != run_date:
            same_write = bool(EX.get("exported_at")) and EX.get("exported_at") == LR.get("exported_at")
            fails.append(f"export date {EX.get('date')} != run date {run_date}"
                         + (" -- same write (exported_at matches), so the pipeline stamped the container's UTC day, not SGT (run 127, 2026-11-02)" if same_write else ""))
        dq = EX.get("data_quality") or {}
        if dq.get("flagged_count"):
            fails.append(f"data_quality flagged {dq.get('flagged_count')} record(s) with null core fields: {[f.get('ticker') if isinstance(f, dict) else f for f in (dq.get('flagged') or [])][:8]}")
        hps = EX.get("held_positions_status")
        if hps != "live":
            fails.append(f"held_positions_status is {hps!r}, not live -- the PM's book may be stale or empty (real-money incident class)")
        elif not (EX.get("held_positions") or []):
            notes.append("held book is live but EMPTY (zero positions) -- correct only if the PM holds nothing; confirm")
        if not (EX.get("lens_ranking") or {}).get("ranked"):
            fails.append("export carries no lens_ranking.ranked -- the Detect-lens top 10 cannot render")
        for r in daily:
            if r.get("on_longlist") is None or r.get("on_elder") is None:
                fails.append(f"export row {r.get('ticker')} lacks on_longlist/on_elder flags"); break
        notes.append(f"export: {len(daily)} rows, {len(EX.get('held_positions') or [])} held ({hps}), data_quality flagged {dq.get('flagged_count')}")
    # --- the candidate set the packets are sliced from ---
    uni = {}
    if CS is not None:
        uni = {r.get("ticker"): r for r in CS.get("universe") or []}
        if not uni:
            fails.append("candidate_set universe is EMPTY")
        if not CS.get("run_date"):
            fails.append("candidate_set carries no run_date -- cannot prove it belongs to this run")
        elif run_date and str(CS.get("run_date"))[:10] != run_date:
            fails.append(f"candidate_set run_date {CS.get('run_date')} != run date {run_date}")
        if EX is not None and daily:
            exp_t = {r.get("ticker") for r in daily} | {h.get("ticker") for h in (EX.get("held_positions") or [])}
            stray = sorted(t for t in uni if t not in exp_t)
            if stray:
                fails.append(f"candidate_set carries {len(stray)} ticker(s) not in the export: {stray[:6]}")
            missing_held = sorted(h.get("ticker") for h in (EX.get("held_positions") or []) if h.get("ticker") not in uni)
            if missing_held:
                fails.append(f"held position(s) missing from the candidate set: {missing_held} (R12: the book is an input)")
        notes.append(f"candidate_set: {len(uni)} names")
    # --- the packets: one per decider, non-empty, inside the candidate set, no PM-only field ---
    pk = os.path.join(od, "packets")
    deciders = _deciders(run_yaml)
    if not os.path.isdir(pk):
        fails.append(f"packets dir MISSING ({pk})")
    else:
        present = sorted(f for f in os.listdir(pk) if f.endswith(".tsv"))
        for v in deciders:
            f = os.path.join(pk, f"{v}.tsv")
            if not os.path.exists(f):
                fails.append(f"packet MISSING for decider {v}"); continue
            txt = open(f, encoding="utf-8", errors="replace").read()
            body = [l for l in txt.split("\n") if l and not l.startswith("#")]
            if len(body) < 2:
                fails.append(f"packet {v}.tsv has a header but NO rows"); continue
            hdr = body[0].split("\t")
            if hdr[0] != "ticker":
                fails.append(f"packet {v}.tsv first column is {hdr[0]!r}, not ticker")
            for fld in PM_ONLY_FIELDS:
                if fld in txt:
                    fails.append(f"packet {v}.tsv carries PM-only field {fld!r} (R3 breach)")
            cells = [l.split("\t") for l in body[1:]]
            blank = sum(1 for row in cells for x in row[1:] if x.strip() in ("", "null", "None"))
            total = sum(max(0, len(row) - 1) for row in cells) or 1
            if blank / total > 0.5:
                fails.append(f"packet {v}.tsv is {blank / total:.0%} blank cells -- served columns are empty (review finding 13)")
            if uni:
                tick = {row[0] for row in cells}
                out = sorted(t for t in tick if t not in uni)
                if out:
                    fails.append(f"packet {v}.tsv serves {len(out)} ticker(s) not in the candidate set: {out[:5]}")
                if len(tick) < 0.9 * len(uni):
                    fails.append(f"packet {v}.tsv serves {len(tick)} of {len(uni)} candidate names -- a seat is blind to {len(uni) - len(tick)} (yesterday's packet?)")
            notes.append(f"packet {v}: {len(body) - 1} rows, {len(hdr)} columns, {blank / total:.0%} blank")
        extra = [f for f in present if f[:-4] not in deciders]
        if extra:
            fails.append(f"packets for NON-decider seats present (R31 -- a stray file serves a seat the universe it must not see): {extra}")
        stray_json = [f for f in os.listdir(pk) if f.endswith(".json") and f != "no_technical_coverage.json"]
        if stray_json:
            fails.append(f"stray packet files (retired macro seats or unknown): {stray_json} (R31)")
    # --- the weather files ---
    if CR is not None:
        if run_date and _date_of(CR.get("generated_at")) != run_date:
            fails.append(f"aqe_crown_macro generated {CR.get('generated_at')} is not the run date {run_date}")
        if str(CR.get("status", "")).upper() in ("EARLY_EXIT", "UNAVAILABLE"):
            fails.append(f"Crown status {CR.get('status')} -- the gate stopped the read; the Cards will declare it")
        elif CR.get("status") != "OK":
            notes.append(f"Crown status {CR.get('status')} (degraded input declared, not a block)")
        if not (CR.get("the_call") and CR.get("read_me_first")):
            fails.append("aqe_crown_macro lacks the_call / read_me_first -- the vote packet's weather line would be blank")
    if VA is not None:
        va_as_of = (VA.get("read_me_first") or {}).get("as_of") or VA.get("as_of")
        if run_date and _date_of(va_as_of) != run_date:
            fails.append(f"aqe_valen_dashboard as_of {va_as_of} is not the run date {run_date}")
        if not (VA.get("stance") or {}).get("word") and not (VA.get("stance") or {}).get("stance"):
            fails.append("aqe_valen_dashboard carries no stance word")
    # --- one code tree: the generated runtime copies the packets were sliced with ---
    gen = os.path.join(os.path.dirname(od), "skills", "premarket-analysis", "GENERATED.json")
    if os.path.exists(gen):
        try:
            import hashlib
            man = json.load(open(gen, encoding="utf-8"))
            root = os.path.dirname(os.path.dirname(od))
            for e in man.get("files", []):
                gp = os.path.join(root, e["generated"])
                if os.path.exists(gp) and hashlib.sha256(open(gp, "rb").read()).hexdigest() != e["sha256"]:
                    fails.append(f"generated runtime copy drifted from the plugin: {e['generated']}")
            notes.append(f"plugin versions in GENERATED.json: {man.get('plugin_versions')}")
        except Exception as ex:
            notes.append(f"GENERATED.json unreadable ({ex.__class__.__name__})")
    return fails, notes


def _report(label, fails, notes):
    if fails:
        print(f"{label}: {len(fails)} PROBLEM(S)")
        for f in fails:
            print(f"  FAIL  {f}")
    else:
        print(f"{label}: Healthy")
    for n in notes:
        print(f"  note  {n}")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ready"); r.add_argument("--last-run", required=True); r.add_argument("--today", default=None)
    c = sub.add_parser("chain"); c.add_argument("--run-dir", required=True); c.add_argument("--date", required=True)
    c.add_argument("--levels", default=None); c.add_argument("--run-yaml", default=DEFAULT_RUN_YAML)
    c.add_argument("--ceiling-tokens", type=int, default=DEFAULT_CEILING)
    d_ = sub.add_parser("data"); d_.add_argument("--output-dir", required=True); d_.add_argument("--run-yaml", default=DEFAULT_RUN_YAML)
    a_ = sub.add_parser("all"); a_.add_argument("--last-run", required=True); a_.add_argument("--today", default=None)
    a_.add_argument("--output-dir", default=None)
    a_.add_argument("--run-dir", required=True); a_.add_argument("--date", required=True); a_.add_argument("--levels", default=None)
    a_.add_argument("--run-yaml", default=DEFAULT_RUN_YAML); a_.add_argument("--ceiling-tokens", type=int, default=DEFAULT_CEILING)
    a = ap.parse_args(argv)
    rc = 0
    if a.cmd in ("ready", "all"):
        f, n = check_ready(a.last_run, a.today); rc |= _report("READY", f, n)
    if a.cmd == "data" or (a.cmd == "all" and getattr(a, "output_dir", None)):
        f, n = check_data(a.output_dir, a.run_yaml); rc |= _report("DATA HANDOFF", f, n)
    if a.cmd in ("chain", "all"):
        f, n = check_chain(a.run_dir, a.date, a.levels, a.run_yaml, a.ceiling_tokens); rc |= _report("CHAIN", f, n)
    return rc


if __name__ == "__main__":
    sys.exit(main())
