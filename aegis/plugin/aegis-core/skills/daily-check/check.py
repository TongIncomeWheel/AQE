#!/usr/bin/env python3
"""daily-check — the Checker (operating model E1, PM 2026-10-30). READ-ONLY. Prints `Healthy` or what broke.

  check.py ready --last-run aegis/output/aqe_last_run.json [--today YYYY-MM-DD]
  check.py chain --run-dir aegis/output/pma/run/<date> --date <date> [--levels pma_levels.json]
                 [--run-yaml <RUN.yaml>] [--ceiling-tokens 1357500]
  check.py all   (both)

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
KNOWN_STEPS = ["INBOX-CLEAN", "GATHER", "PREPARE", "NOMINATE", "RANK", "PM-LENS", "CHALLENGE", "VOTE", "FLOOR",
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
            est += int(c.get("est_tokens") or row.get("tokens") or 0)
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
    a_ = sub.add_parser("all"); a_.add_argument("--last-run", required=True); a_.add_argument("--today", default=None)
    a_.add_argument("--run-dir", required=True); a_.add_argument("--date", required=True); a_.add_argument("--levels", default=None)
    a_.add_argument("--run-yaml", default=DEFAULT_RUN_YAML); a_.add_argument("--ceiling-tokens", type=int, default=DEFAULT_CEILING)
    a = ap.parse_args(argv)
    rc = 0
    if a.cmd in ("ready", "all"):
        f, n = check_ready(a.last_run, a.today); rc |= _report("READY", f, n)
    if a.cmd in ("chain", "all"):
        f, n = check_chain(a.run_dir, a.date, a.levels, a.run_yaml, a.ceiling_tokens); rc |= _report("CHAIN", f, n)
    return rc


if __name__ == "__main__":
    sys.exit(main())
