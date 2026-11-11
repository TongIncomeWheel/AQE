#!/usr/bin/env python3
"""daily-check — the Checker (operating model E1, PM 2026-10-30). READ-ONLY. Prints `Healthy` or what broke.

  check.py ready --last-run aegis/output/aqe_last_run.json [--today YYYY-MM-DD]
  check.py chain --run-dir aegis/output/pma/run/<date> --date <date> [--levels pma_levels.json]
                 [--run-yaml <RUN.yaml>] [--ceiling-tokens 2500000]
  check.py data  --output-dir aegis/output [--run-yaml <RUN.yaml>]     (the AQE -> voices HANDOFF gate)
                 [--journal-dir aegis/data/journal] [--broker-stops <run-dir>/broker_stops.json]
                 (also the book + stops: the close's journal, the export, a live broker read; and the committee's FMP
                  inputs the daily run fetched: <output>/committee_data/ - manifest, sha256s, coverage, freshness)
  check.py coverage --packets-dir aegis/output/packets --export aegis/output/aqe_daily_export.json [--phase4 phase4.json] [--out coverage.json]
                 (per-voice data coverage: each charter's required fields vs its packet; run BEFORE the vote)
  check.py all   (ready + data + chain)

Exit 0 = Healthy. Exit 1 = at least one FAIL line. Exit 2 = could not even read an input (also a failure --
a checker that cannot see is not green). Zero dependencies beyond the standard library; RUN.yaml is read with
the plugin's own mini loader when it is importable, else the step list falls back to KNOWN_STEPS (RUN.yaml's
list as of the 2 Nov 2026 redesign).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUN_YAML = os.path.abspath(os.path.join(HERE, "..", "pma", "RUN.yaml"))
# DECISIONS_2026-11-02 (tool fixes): spend ceiling raised to 2,500,000 on the registrar's byte basis -- the 1,357,500
# figure (1.5x the 905k baseline) predates the 7-seat, 39-name design and tripped before FLOOR on 2 Nov.
# Optimisation is a later PM decision.
DEFAULT_CEILING = 2_500_000
def _slate_cap_from_run_yaml(default=25):
    """ONE source (conductor 2026-11-04): parameters.slate_cap in RUN.yaml. The literal below is only the fallback when the
    run map cannot be found, so the pipeline, the registrar and the chain check cannot drift apart again."""
    import os as _o, re as _r
    here = _o.path.dirname(_o.path.abspath(__file__))
    for rel in ("..", "../skills/pma", "../../pma", "../../../skills/pma", "../../skills/pma", "../pma"):
        p = _o.path.join(here, rel, "RUN.yaml")
        if _o.path.exists(p):
            try:
                m = _r.search(r"^\s*slate_cap:\s*(\d+)", open(p, encoding="utf-8").read(), _r.M)
                if m:
                    return int(m.group(1))
            except OSError:
                pass
    return default


SLATE_CAP = _slate_cap_from_run_yaml()   # R34 (15 -> 25, PM 2026-11-04), read from RUN.yaml parameters.slate_cap
# The fallback only: the step list is READ FROM RUN.yaml (_steps_from_run_yaml). R38 (2026-11-02): FLOOR is retired;
# MTF, CLAIMS, CROSS, FUNNEL, PAIR, TIER2 and TIMING replace it.
KNOWN_STEPS = ["INBOX-CLEAN", "GATHER", "PREPARE", "NOMINATE", "PM-LENS", "RANK", "MTF", "CHALLENGE", "VOTE",
               "CLAIMS", "CROSS", "FUNNEL", "PAIR", "TIER2", "TIMING", "SLATE", "RATIFY", "QA", "DECIDE", "RATIONALE", "ADOPT", "RATIONALE-FINAL", "POSITION", "CONDITIONS",
               "REPEAT-WATCH", "BRACKET", "SCORECARD", "WRITE", "CHECK", "LEVELS", "REPORT", "PUBLISH"]


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


def _step_budgets(run_yaml):
    """Per-step token budgets from RUN.yaml (`budget_tokens: N` inside a step block). None defined = no per-step check."""
    import re as _r
    try:
        txt = open(run_yaml, encoding="utf-8").read()
    except OSError:
        return {}
    out = {}
    for blk in _r.split(r"^  - name:\s*", txt, flags=_r.M)[1:]:
        name = blk.split("\n", 1)[0].strip().strip("'\"")
        m = _r.search(r"^\s{4}budget_tokens:\s*([0-9_]+)", blk, _r.M)
        if m:
            out[name] = int(m.group(1).replace("_", ""))
    return out


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
        rep_ = (M.get("report") or "A")
        env_rep = (os.environ.get("AEGIS_REPORT") or "A").strip().upper()
        if rep_ != env_rep:
            fails.append(f"manifest is report {rep_} but AEGIS_REPORT={env_rep}: the roster this check counts would be wrong")
        if rep_ in ("B", "C"):
            if not M.get("rerun") or (M.get("rerun") or {}).get("publishes_live") is not False:
                fails.append(f"report {rep_} must be a non-live run (rerun block with publishes_live false): it publishes no levels and is not watched by alerts")
            notes.append(f"REPORT {rep_}: scored only; no levels published; reuses report A's weather, macro, market kill and held review")
        rr = M.get("rerun")
        if rr:
            # RERUN (PM 2026-11-03): not live. The run dir must be the r<N> dir, and its publish receipt may list only
            # paths inside it (never the live levels, scorecard log or the original run's record).
            want = str(rr.get("run_dir", "")).strip("/")
            if not os.path.normpath(run_dir).replace("\\", "/").rstrip("/").endswith(want):
                fails.append(f"RERUN {M.get('run_id')}: checked dir {run_dir} is not its run dir {want}")
            rc_ = _load(os.path.join(run_dir, "publish_receipt.json"), "publish_receipt.json", [])
            for pth in (rc_ or {}).get("pushed") or []:
                if not str(pth).strip("/").startswith(want + "/") and str(pth).strip("/") != want:
                    fails.append(f"RERUN {M.get('run_id')} pushed {pth} OUTSIDE {want} -- a rerun must never publish live")
            notes.append(f"RERUN {M.get('run_id')} of {rr.get('of')}: NOT LIVE; the PM promotes it explicitly")
        est = 0
        budgets = _step_budgets(run_yaml)
        for s, row in st.items():
            c = row.get("cost") or {}
            # review finding 5 (2026-11-01): the registrar stores spawns/inlined_bytes/returned_bytes and derives
            # est_tokens only when printing -- mirror registrar._est_tokens (bytes / 4) so the ceiling can trip.
            # P3 (2026-11-04): a seat-reported count (`tokens`, from registrar meter/commit --tokens) is REAL usage; it
            # wins over the byte estimate whenever it is larger (registrar._est_tokens takes the same max).
            reported = int(row.get("tokens") or 0)
            if c.get("est_tokens"):
                one = int(c["est_tokens"])
            elif c and not c.get("tool_only"):
                one = int((int(c.get("inlined_bytes") or 0) + int(c.get("returned_bytes") or 0)) / 4.0)
            else:
                one = 0
            one = max(one, reported)
            est += one
            if s in budgets and one > budgets[s]:
                fails.append(f"STEP OVER BUDGET: {s} est {one:,} > {budgets[s]:,} tokens (RUN.yaml budget_tokens) -- tell the PM")
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
    # R38 (2026-11-02): the open floor is retired. floor_check.json is REQUIRED only on a run map that still has a
    # FLOOR step; on the two-tier funnel it exists only when the QA hold round ran (floor-check --qa), and is then
    # checked. The funnel's own files are required instead: funnel.json (tier 1) and decision.json (tier 2).
    fc = os.path.join(run_dir, "floor_check.json")
    if "FLOOR" in steps or os.path.exists(fc):
        F = _load(fc, "floor_check.json", fails)
        if F is not None and F.get("ok") is not True:
            fails.append("floor_check.json not ok: " + "; ".join(F.get("errors") or ["(no reason)"])[:300])
    if "FUNNEL" in steps:
        FN = _load(os.path.join(run_dir, "funnel.json"), "funnel.json", fails)
        if FN is not None:
            if not isinstance(FN.get("survivors"), list) or not isinstance(FN.get("names"), dict):
                fails.append("funnel.json carries no survivors / names -- tier 1 was not counted by claims-score")
            else:
                ms = FN.get("measurement") or {}
                notes.append(f"funnel: {ms.get('claims_issued')} claims, survivors {len(FN['survivors'])}, dropped "
                             f"{len(FN.get('dropped') or [])}, stances changed {ms.get('stances_changed_n')}")
    if "TIMING" in steps:
        DC = _load(os.path.join(run_dir, "decision.json"), "decision.json", fails)
        if DC is not None:
            if not isinstance(DC.get("names"), dict):
                fails.append("decision.json carries no names -- tier 2 was not counted by decide-timing")
            elif S is not None:
                dn = DC["names"]
                for x in S.get("tickets") or []:
                    n = dn.get(x.get("ticker"))
                    if n is None or n.get("proposal") != x.get("verdict"):
                        fails.append(f"slate ticket {x.get('ticker')}: verdict {x.get('verdict')} != decision.json "
                                     f"{(n or {}).get('proposal')} (R40)")
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
            return _with_report_seat([str(x) for x in d])
    except Exception:
        pass
    return _with_report_seat(["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"])


def _with_report_seat(roster):
    """Three reports (PM 2026-11-05): a C run (env AEGIS_REPORT=C) adds the AQE quant seat as an eighth decider; A and B are the seven."""
    if (os.environ.get("AEGIS_REPORT") or "A").strip().upper() == "C" and "aqe-quant" not in roster:
        return list(roster) + ["aqe-quant"]
    return list(roster)


# NYSE full-day closures (the close a journal can be missing for without being stale).
US_MARKET_HOLIDAYS = {
    "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18",
    "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
}


def last_us_close(run_date_sgt):
    """The US session a morning SGT run reads: the last weekday before the SGT date that was
    not an NYSE holiday (a 06:30 SGT Tuesday run reads Monday's close)."""
    d = _dt.date.fromisoformat(str(run_date_sgt)[:10]) - _dt.timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in US_MARKET_HOLIDAYS:
        d -= _dt.timedelta(days=1)
    return d.isoformat()


def check_book(journal_dir, run_date, export=None, broker_stops_path=None):
    """THE BOOK AND ITS STOPS (PM 2026-11-02: "Stop from Tiger is correct. That's the
    dependency ... both from the trade report and also during the AQE run").
    One source of truth: the close's dated journal (Tiger positions + working orders).
    FAIL when it is missing, stale, did not read the orders, or disagrees with the export or with a
    live broker read. A held name with no stop order is a WARN (the PM's choice to hold it naked
    is real information, not a data defect) -- printed every time, never folded away."""
    fails, notes = [], []
    import glob as _glob
    paths = sorted(_glob.glob(os.path.join(journal_dir, "aegis_journal_????-??-??.json")))
    if not paths:
        return [f"no journal in {journal_dir} -- the book of record is MISSING"], notes
    J = _load(paths[-1], os.path.basename(paths[-1]), fails)
    if J is None:
        return fails, notes
    jdate = J.get("date")
    if run_date:
        want = last_us_close(run_date)
        if not jdate or jdate < want:
            fails.append(f"journal is for {jdate}, the last US close is {want} -- the 05:30 book close did not file (STALE book)")
    pulled = (J.get("broker_sync") or {}).get("open_orders_pull_ran")
    if pulled is not True:
        fails.append(f"journal {jdate}: Tiger's working orders were NOT read at the close "
                     f"(open_orders_pull_ran={pulled!r}) -- no stop in it is today's answer")
    book = {p.get("ticker"): p for p in J.get("open_positions") or []}
    for t, p in sorted(book.items()):
        if pulled is True and p.get("stop_live_broker") is None:
            notes.append(f"WARN {t}: {p.get('qty')} shares held with NO working stop order at Tiger (UNPROTECTED)")
    for f in J.get("review_flags") or []:
        if f.get("type") in ("stop_partial_cover", "auto_included_unrecognized"):
            notes.append(f"WARN {f.get('ticker')}: {f.get('type')} -- {f.get('detail')}")
    notes.append(f"book: journal {jdate}, {len(book)} name(s) "
                 + ", ".join(f"{t} {p.get('qty'):g} stop {p.get('stop_live_broker')}" for t, p in sorted(book.items())
                             if isinstance(p.get('qty'), (int, float))))
    if export is not None:
        held = {h.get("ticker"): h for h in export.get("held_positions") or []}
        if set(held) != set(book):
            fails.append(f"export held book {sorted(held)} != journal {jdate} {sorted(book)}")
        hs = export.get("held_stops")
        if hs is None:
            fails.append("export carries no held_stops block -- AQE did not resolve the stops")
        else:
            if hs.get("journal_date") != jdate:
                fails.append(f"export read the stops from journal {hs.get('journal_date')}, the latest is {jdate}")
            for t, why in sorted((hs.get("differs") or {}).items()):
                fails.append(f"{t}: the two Tiger reads disagree -- {why}")
            if not hs.get("second_read_at"):
                notes.append(f"stops from the close's journal only (no pre-AQE Tiger read: {hs.get('second_read_reason')}) -- normal; the second read is optional (PM 2026-11-02)")
        for t, h in sorted(held.items()):
            if t not in book:
                continue
            src = str(h.get("held_stop_source") or "")
            jstop = book[t].get("stop_live_broker")
            if src.startswith("journal") and h.get("held_sl") != jstop:
                fails.append(f"{t}: export held_sl {h.get('held_sl')} != journal stop {jstop}")
    if broker_stops_path:
        BS = _load(broker_stops_path, "broker_stops.json", fails)
        if BS is not None:
            if BS.get("journal_date") and BS.get("journal_date") != jdate:
                fails.append(f"broker_stops.json was built from journal {BS.get('journal_date')}, the latest is {jdate}")
            for d in BS.get("disagreements") or []:
                fails.append(f"live broker read vs journal: {d}")
            if "disagreements" not in BS:
                notes.append("WARN broker_stops.json carries no journal cross-check (built without --journal)")
    return fails, notes


COMMITTEE_FILES = {"fundamentals_pack.json": "fundamentals_pack.v1", "mtf_grid.json": "mtf_grid.v1",
                   "closes_scorecard.json": "closes_scorecard.v1"}
COURIER_COST = "the courier fallback costs about 1.5M metered tokens (3 Nov 2026: 46% of the run) and is the PM's call"


def check_committee_data(output_dir, run_date, export=None):
    """THE COMMITTEE'S FMP INPUTS (PM 2026-11-03: fetching is code, not a model). Written by the daily AQE run
    (src/pipeline/committee_data.py) to <output>/committee_data/. Missing, stale, FAILED or inconsistent = FAIL
    (the PMA would need the courier fallback; do not start it unattended). ONE coverage rule: any file under 95% served
    (manifest PARTIAL: many names unserved, e.g. the time budget ran out) = FAIL, stop and page; at or above 95% the
    per-name gaps are a WARN that names them and the seats see them as declared gaps (the run proceeds)."""
    import hashlib
    fails, notes = [], []
    d = os.path.join(output_dir, "committee_data")
    mp = os.path.join(d, "manifest.json")
    M = _load(mp, "committee_data/manifest.json", fails)
    if M is None:
        fails[-1] += f" -- the daily run did not publish the committee's data; {COURIER_COST}"
        return fails, notes
    if M.get("schema") != "committee_data_manifest.v1":
        fails.append(f"committee_data manifest schema is {M.get('schema')!r}, not committee_data_manifest.v1")
        return fails, notes
    if run_date and str(M.get("run_date"))[:10] != run_date:
        fails.append(f"committee_data manifest is for {M.get('run_date')}, the run is {run_date} -- STALE; {COURIER_COST}")
        return fails, notes
    if M.get("status") == "FAILED":
        fails.append(f"committee_data FAILED: {M.get('reason')} -- {COURIER_COST}")
        return fails, notes
    files = M.get("files") or {}
    docs = {}
    for name, schema in COMMITTEE_FILES.items():
        e = files.get(name)
        if not isinstance(e, dict):
            fails.append(f"committee_data manifest lists no {name}"); continue
        p = os.path.join(d, name)
        if not os.path.exists(p):
            fails.append(f"committee_data/{name}: MISSING (the manifest says it was published)"); continue
        body = open(p, "rb").read()
        if hashlib.sha256(body).hexdigest() != e.get("sha256") or len(body) != e.get("bytes"):
            fails.append(f"committee_data/{name}: sha256/bytes differ from the manifest -- a torn or edited publish, do not trust it")
            continue
        try:
            docs[name] = json.loads(body)
        except ValueError:
            fails.append(f"committee_data/{name}: not valid JSON"); continue
        if e.get("schema") != schema:
            fails.append(f"committee_data/{name}: schema {e.get('schema')!r}, expected {schema}")
    if fails:
        return fails, notes
    G, F, C = docs["mtf_grid.json"], docs["fundamentals_pack.json"], docs["closes_scorecard.json"]
    for nm, doc in (("mtf_grid.json", G), ("fundamentals_pack.json", F)):
        if doc.get("schema") != COMMITTEE_FILES[nm] or str(doc.get("run_date"))[:10] != str(M.get("run_date"))[:10]:
            fails.append(f"committee_data/{nm}: schema/run_date {doc.get('schema')}/{doc.get('run_date')} disagree with the manifest")
    gh = hashlib.sha256(json.dumps(G.get("names"), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    if gh != G.get("sha256_of_names"):
        fails.append("committee_data/mtf_grid.json: sha256_of_names does not match its names")
    if not isinstance(C.get("_missing"), list) or len([k for k in C if k != "_missing"]) != files["closes_scorecard.json"]["served"]:
        fails.append("committee_data/closes_scorecard.json: _missing / ticker count disagree with the manifest")
    if "SPY" not in C:
        fails.append("committee_data/closes_scorecard.json carries no SPY - the scorecard's benchmark calendar cannot be built")
    elif run_date and max(C["SPY"]) < last_us_close(run_date):
        fails.append(f"committee_data closes: SPY ends {max(C['SPY'])}, the last US close is {last_us_close(run_date)} -- stale closes")
    if export is not None:
        want = sorted({r.get("ticker") for r in (export.get("daily_list") or [])} | {h.get("ticker") for h in (export.get("held_positions") or [])} - {None})
        # EXTRAS ARE FINE (conductor 2026-11-11): the nightly adds Report B's screened names to committee data (#77), so the set may be a SUPERSET of
        # the export. It fails only when an export (or held) name is MISSING from the grid or the fundamentals pack - that is a different export.
        have_g, have_f = set(G.get("names") or {}), set((F.get("tickers") or {}).keys())
        miss_g, miss_f = sorted(set(want) - have_g), sorted(set(want) - have_f)
        if miss_g or miss_f or (M.get("scope") or {}).get("requested", 0) < len(want):
            fails.append(f"committee_data was fetched for {(M.get('scope') or {}).get('requested')} names, today's export has {len(want)} and these are missing from it "
                         f"(mtf: {miss_g[:8]}, fundamentals: {miss_f[:8]}) - a different export")
        elif len(have_g) > len(want):
            notes.append(f"committee data carries +{len(have_g - set(want))} screened names beyond today's export (Report B's screens, by design)")
    if fails:
        return fails, notes
    gc, fc = G["coverage"], F["coverage"]
    if M.get("status") == "PARTIAL":
        why = ", ".join(x for x, on in (("FMP refused the key", M.get("quota_hit")), ("time budget exhausted", M.get("time_budget_exhausted"))) if on)
        thin = [f"{n} {e['served']}/{e['served'] + e['unserved']}" for n, e in files.items() if (e["served"] + e["unserved"]) and e["served"] / (e["served"] + e["unserved"]) < 0.95]
        fails.append(f"committee data is PARTIAL{' (' + why + ')' if why else ''}: under 95% served on {', '.join(thin)} "
                     f"(mtf not served: {gc['not_served_names'][:8]}; fundamentals unserved: {fc['unserved_names'][:8]}) -- "
                     f"stop and page the PM with two replies: 'couriers' ({COURIER_COST}) or 'skip' (run with those names as declared gaps)")
        return fails, notes
    if M.get("quota_hit") or M.get("time_budget_exhausted"):
        why = ", ".join(x for x, on in (("FMP refused the key", M.get("quota_hit")), ("time budget exhausted", M.get("time_budget_exhausted"))) if on)
        notes.append(f"WARN committee data fetch hit a limit ({why}) but every file is still at or above 95% served")
    if gc["not_served_names"] or fc["unserved_names"] or fc["partial_names"] or C["_missing"]:
        notes.append(f"WARN committee data gaps (declared): mtf not served {gc['not_served_names'][:8]}, fundamentals unserved "
                     f"{fc['unserved_names'][:8]} / partial {fc['partial_names'][:8]}, closes missing {C['_missing'][:8]}")
    cs = M.get("closes_scope") or {}
    if cs and (str(cs.get("past_exports_source", "")).startswith("UNAVAILABLE") or not cs.get("past_export_runs")):
        notes.append(f"WARN committee data closes cover only today's export and the ledger ({cs.get('total')} names): past exports' names "
                     f"are {cs.get('past_exports_source') or 'UNAVAILABLE'} - the scorecard's 'vs list' and 'vs SPY' denominators are understated")
    for e in (M.get("errors") or [])[:3]:
        notes.append(f"WARN committee data error: {e}")
    notes.append(f"committee data {M.get('status')}: {M.get('run_date')}, mtf {gc['complete']}/{gc['requested']} complete "
                 f"({gc['hourly_native']} native hourly, {gc['hourly_rolled_up']} rolled up from 15-min, {gc['hourly_none']} none), "
                 f"fundamentals {fc['served']}/{fc['requested']} ({fc['carried']} carried), closes "
                 f"{len([k for k in C if k != '_missing'])}, {M.get('fmp_calls')} FMP calls in {M.get('elapsed_s')}s")
    return fails, notes


DEFAULT_VOICE_CONTRACT = os.path.abspath(os.path.join(HERE, "..", "..", "contracts", "voice_coverage.json"))
DEFAULT_MENUS = os.path.abspath(os.path.join(HERE, "..", "pma", "contracts", "voice_menus.json"))
BLANK = ("", "null", "None", "nan", "NaN")
NAME_CAP = 12


def _flat_keys(o, prefix=""):
    out = set()
    if isinstance(o, dict):
        for k, v in o.items():
            out.add(prefix + k)
            if isinstance(v, dict):
                out |= _flat_keys(v, prefix + k + ".")
    return out


def _read_packet(path):
    """-> (header, rows) of a voice packet TSV; comment lines (# DICT ...) skipped."""
    lines = [l.rstrip("\n") for l in open(path, encoding="utf-8", errors="replace") if l.strip() and not l.startswith("#")]
    if not lines:
        return [], []
    hdr = lines[0].split("\t")
    return hdr, [l.split("\t") for l in lines[1:]]


def check_voice_coverage(packets_dir, export, deciders, contract_path=DEFAULT_VOICE_CONTRACT, menus_path=DEFAULT_MENUS, room=None):
    """PER-VOICE DATA COVERAGE (PM 2026-11-03: "a deterministic per-voice data-coverage report ... BLOCK before the
    vote on a gap, loud, never a silent pass ... distinguish 'not served' from 'off my menu'").
    For each decider: the fields its recognisers read (generated from the canon locks into the contract) against
    its packet's columns and the non-blank rate per name. Every required field is exactly one of:
      SERVED        on the voice's menu, a column in its packet, not blank for every name in scope
      NOT SERVED    on the menu but the column is absent, or blank for EVERY name in scope (a data gap)
      AQE GAP       not on the menu and not an AQE export field at all (a data gap)
      OFF MY MENU   not on the menu but AQE exports it (a menu choice - listed, never a gap, never blocks)
      CONDITIONAL   legitimately blank by AQE's own rule (contract conditional_blank, with the glossary reason)
    A NOT SERVED / AQE GAP field, or a NOT_AVAILABLE recogniser, blocks unless the contract has a WRITTEN REASON for it in `standing` / `capabilities` (printed every run, no block). Name-level
    blanks (a field served for most names, blank for some) are listed per field, scoped to `room` when given, and do
    not block: that is the seat's own declared no_data. Read-only; returns (fails, notes, report)."""
    fails, notes, report = [], [], {}
    contract = _load(contract_path, "voice_coverage contract", fails)
    menus = _load(menus_path, "voice_menus", fails)
    if contract is None or menus is None:
        return fails, notes, report
    cond = contract.get("conditional_blank") or {}
    cond_exact = {k for k in cond if not k.endswith(".*")}
    cond_prefix = tuple(k[:-1] for k in cond if k.endswith(".*"))
    # `bracket.*` makes bracket.stop conditional AND the parent `bracket` a charter lists (it expands to the same columns)
    is_cond = lambda f: f in cond_exact or (bool(cond_prefix) and (f.startswith(cond_prefix) or (f + ".") in cond_prefix))
    export_cols = set()
    for r in (export.get("daily_list") or []) + (export.get("held_positions") or []):
        if isinstance(r, dict):
            export_cols |= _flat_keys(r)
    if not export_cols:
        fails.append("voice coverage: the export has no daily_list columns to compare the charters against")
        return fails, notes, report
    # A FLAT BOOK (PM 2026-11-09): hl_score / hl_state (AQE's health verdict) exist only on held rows. With no position held there is nothing
    # for them to be on, so a charter that reads them has no gap -- it has no held name. Skipped with a WARN, never a FAIL. This is not a
    # `standing` entry: with a held book the same fields are checked exactly as before.
    flat_book = not (export.get("held_positions") or [])
    is_hl = lambda f: f.startswith("hl_") or ".hl_" in f
    flat_noted = set()
    for v in deciders:
        req = (contract.get("required_fields") or {}).get(v)
        if req is None:
            fails.append(f"voice coverage: {v} has no required_fields in the contract (run tools/build_voice_coverage.py)"); continue
        menu = set(menus.get(v) or [])
        if not menu:
            fails.append(f"voice coverage: {v} has no menu in voice_menus.json"); continue
        pk = os.path.join(packets_dir, f"{v}.tsv")
        if not os.path.exists(pk):
            fails.append(f"voice coverage: packet MISSING for {v} ({pk})"); continue
        hdr, rows = _read_packet(pk)
        if not hdr or hdr[0] != "ticker":
            fails.append(f"voice coverage: {v}.tsv has no ticker header"); continue
        scope = [r for r in rows if (room is None or (r and r[0] in room))]
        if room is not None and not scope:
            fails.append(f"voice coverage: none of the room ({len(room)} names) is in {v}'s packet"); continue
        cols = set(hdr)
        on_menu = lambda f: f in menu or any(m.startswith(f + ".") for m in menu)
        in_pkt = lambda f: f in cols or any(c.startswith(f + ".") for c in cols)
        in_exp = lambda f: f in export_cols or any(e.startswith(f + ".") for e in export_cols)
        known = (contract.get("standing") or {}).get(v) or {}
        aliases = (contract.get("served_as") or {}).get(v) or {}
        served, served_as, off_menu, conditional, new_gaps, known_hit, blanks = [], [], [], [], [], [], {}
        for f in req:
            if is_cond(f):
                conditional.append(f); continue
            if flat_book and is_hl(f):
                flat_noted.add(f); continue
            if f in aliases:
                # the canon's name for a column the packet carries under another name: the SOURCE must be served
                src = aliases[f]["as"]
                sidx = [i for i, c in enumerate(hdr) if c == src or c.startswith(src + ".")]
                if on_menu(src) and sidx and not all(all(len(r) <= i or r[i].strip() in BLANK for i in sidx) for r in rows):
                    served_as.append(f"{f}={src}")
                else:
                    new_gaps.append((f, f"SERVED AS {src}, but {src} is not served (not on the menu, no column, or blank for every name)"))
                continue
            if not on_menu(f):
                if in_exp(f):
                    off_menu.append(f)
                elif f in known:
                    known_hit.append(f)
                else:
                    new_gaps.append((f, "AQE GAP: not on the menu and AQE does not export it"))
                continue
            # on the menu: the column must exist and carry something
            idxs = [i for i, c in enumerate(hdr) if c == f or c.startswith(f + ".")]
            if not idxs:
                (known_hit if f in known else new_gaps).append(f if f in known else (f, "NOT SERVED: on the menu but no such column in the packet"))
                continue
            def blank(r, i): return len(r) <= i or r[i].strip() in BLANK
            # A FEED gap is a property of the whole packet column: blank for every name the voice was sent. That is
            # what blocks. Which room names are blank is a name-level fact the seat declares as no_data - it is
            # listed (scoped to the room when given) but never blocks, and a small room can never fake a feed gap.
            if rows and all(all(blank(r, i) for i in idxs) for r in rows) and contract.get("block_when_blank_for_every_name_in_scope", True):
                (known_hit if f in known else new_gaps).append(f if f in known else (f, f"NOT SERVED: blank for all {len(rows)} names in the packet"))
                continue
            served.append(f)
            blank_names = [r[0] for r in scope if all(blank(r, i) for i in idxs)]
            if blank_names:
                blanks[f] = blank_names
        # NOT_AVAILABLE recognisers (the canon's own "this data does not exist"): empty `fields:`, so the loop above
        # cannot see them. Each must be in `capabilities` with a written reason, or it is a new gap.
        caps_known, caps_new = [], []
        for item in (contract.get("declared_unavailable") or {}).get(v) or []:
            why = ((contract.get("capabilities") or {}).get(v) or {}).get(item["id"])
            (caps_known if why else caps_new).append(item)
        for item in caps_new:
            new_gaps.append((f"{item['id']} (NOT_AVAILABLE)", f"CAPABILITY NOT SERVED: the canon declares it unavailable ({item['needs'][:90]}) and no written reason is on file"))
        rep = {"required": len(req), "served": len(served), "served_as": served_as, "conditional": conditional, "off_my_menu": off_menu,
               "capabilities_not_served": [i["id"] for i in caps_known],
               "not_served_known": known_hit, "not_served_new": [f for f, _ in new_gaps], "name_blanks": {k: n[:NAME_CAP] for k, n in blanks.items()},
               "scope": "room" if room is not None else "all packet rows", "names_in_scope": len(scope)}
        report[v] = rep
        for f, why in new_gaps:
            fails.append(f"{v}: {f} -- {why}. The charter reads it; a vote on this is a vote with a hole. Fix the feed, or put it in contracts/voice_coverage.json `standing` with a written reason")
        line = f"{v}: {len(served) + len(served_as)}/{len(req)} served"
        if served_as: line += f" ({len(served_as)} under another name: {', '.join(served_as)})"
        if known_hit: line += f" · NOT SERVED (standing, written reason in the contract): {', '.join(known_hit)}"
        if caps_known: line += f" · CAPABILITY NOT SERVED (canon says NOT_AVAILABLE): {', '.join(i['id'] for i in caps_known)}"
        if off_menu: line += f" · off my menu (a menu choice, not a gap): {', '.join(off_menu)}"
        notes.append(("WARN " if (known_hit or caps_known) else "") + "voice coverage " + line)
        if blanks:       # one compact line per voice; the per-field name lists are in the JSON report (--out)
            per_name = {}
            for f, nm in blanks.items():
                for n in nm:
                    per_name[n] = per_name.get(n, 0) + 1
            worst = sorted(per_name.items(), key=lambda x: (-x[1], x[0]))[:5]
            fields = ", ".join(f"{f} {len(nm)}" for f, nm in sorted(blanks.items(), key=lambda x: (-len(x[1]), x[0]))[:6])
            rep["name_blank_counts"] = {f: len(nm) for f, nm in blanks.items()}
            notes.append(f"WARN voice coverage {v}: name-level blanks in {len(blanks)} served field(s) of {len(scope)} names ({fields}"
                         f"{', ...' if len(blanks) > 6 else ''}); most affected: " + ", ".join(f"{n} ({c} fields)" for n, c in worst)
                         + " -- the seat declares these no_data")
    if flat_noted:
        notes.append(f"WARN voice coverage: flat book: {', '.join(sorted(flat_noted))} not applicable (no position is held, so there is no health verdict to serve); skipped, not a gap")
    return fails, notes, report


def check_cards_html(path):
    """The RENDERED card page must carry no raw field name anywhere in its text (PM 2026-11-04): any underscore token (bar_high,
    high_52w_close, day_vol, ABOVE_STRUCTURE...) in a text node FAILs. The renderer translates them from one table; this proves it."""
    import re as _re
    fails, notes = [], []
    if not path or not os.path.exists(path):
        return [f"cards html: MISSING ({path})"], notes
    h = open(path, encoding="utf-8", errors="replace").read()
    h = _re.sub(r"<style.*?</style>|<script.*?</script>", "", h, flags=_re.S | _re.I)
    # PM 2026-11-04: the committee's verbatim words are the AUDIT TRAIL and live folded in <details>; everything OUTSIDE a <details>
    # must be readable by a trader: no C-codes (C5, C16...), no W/D/H1, no ADX, no %K/%D.
    outside = _re.sub(r"<details.*?</details>", "", h, flags=_re.S | _re.I)
    jargon = {}
    for m in _re.finditer(r">([^<>]+)<", outside):
        node = m.group(1)
        for pat, label in ((r"\bC\d{1,2}\b", "C-codes"), (r"W/D/H1", "W/D/H1"), (r"%K/%D", "%K/%D")):
            for t in _re.findall(pat, node):
                jargon[t] = jargon.get(t, 0) + 1
        if len(node.split()) > 1 and _re.search(r"\bADX\b", node):
            jargon["ADX"] = jargon.get("ADX", 0) + 1
    if jargon:
        fails.append("the rendered cards show committee jargon OUTSIDE the folded audit trail: " + ", ".join(f"{k} x{v}" for k, v in sorted(jargon.items(), key=lambda kv: -kv[1])[:12]))
    bad = {}
    for m in _re.finditer(r">([^<>]+)<", h):
        for t in _re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b", m.group(1)):
            bad[t] = bad.get(t, 0) + 1
    if bad:
        fails.append("the rendered cards still show raw field names: " + ", ".join(f"{k} x{v}" for k, v in sorted(bad.items(), key=lambda kv: -kv[1])[:14]))
    notes.append(f"cards html: {len(h):,} chars scanned for raw field names")
    return fails, notes


def check_cards_text(path):
    """B3 (PM 2026-11-04): the Cards' reason block is ONE plain voice - three one-sentence parts, no raw field names, no vote
    tallies, no jargon, at most 4 numbers. FAIL, not WARN. The rules live in pma_cards.validate_reason (one source); the render
    refuses the same text, this is the gate that proves it before publish."""
    import importlib.util as _iu
    fails, notes = [], []
    T = _load(path, "cards_text.json", fails)
    if T is None:
        return fails, notes
    here = os.path.dirname(os.path.abspath(__file__))
    mod = None
    for rel in ("../pma/tools/pma_cards.py", "../../tools/pma_cards.py", "../../skills/pma/tools/pma_cards.py"):
        p = os.path.join(here, rel)
        if os.path.exists(p):
            spec = _iu.spec_from_file_location("pma_cards_gate", p); mod = _iu.module_from_spec(spec); spec.loader.exec_module(mod); break
    if mod is None:
        return ["pma_cards.py (the reason validator) not found - the cards text cannot be gated"], notes
    n = 0
    for t, c in (T.get("cards") or {}).items():
        n += 1
        if not c.get("reason"):
            fails.append(f"cards.{t}: no `reason` block (agree / wrong_if / wait_for)")
            continue
        fails += [f"cards.{t}.{e}" for e in mod.validate_reason(c["reason"])]
    notes.append(f"cards text: {n} ADVANCE card(s) checked for the plain one-voice reason")
    return fails, notes


def check_cards_lines(path):
    """PM 2026-11-05: cards_lines.json = the WRITER's committee-voice lines 2 and 3 for each card ({TICKER: {why, contested}}). FAIL on any line
    that names a seat, speaks in the first person, carries a tally, a field name or a code, runs past its cap, has more than two numbers or is
    more than one sentence: the renderer would fall back to the extraction line and say so, this proves it before publish. An absent file is a
    WARN-level note (the extraction route still renders), never a silent pass."""
    import importlib.util as _iu
    fails, notes = [], []
    if not path or not os.path.exists(path):
        return fails, [f"cards lines: {path} not found -- the extraction lines will be printed (declared, not silent)"]
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"cards lines: {path} unreadable: {e}"], notes
    doc = doc.get("cards") if isinstance(doc, dict) and isinstance(doc.get("cards"), dict) else doc
    here = os.path.dirname(os.path.abspath(__file__))
    mod = None
    for rel in ("../pma/tools/card_template.py", "../../tools/card_template.py", "../../skills/pma/tools/card_template.py"):
        q = os.path.join(here, rel)
        if os.path.exists(q):
            spec = _iu.spec_from_file_location("card_template_gate", q); mod = _iu.module_from_spec(spec); spec.loader.exec_module(mod); break
    if mod is None:
        return ["card_template.py (the lines gate) not found -- cards_lines.json cannot be gated"], notes
    n = 0
    for t, d in (doc or {}).items():
        for kind in ("why", "contested"):
            ln = (d or {}).get(kind)
            if ln is None or str(ln).strip() == "":
                fails.append(f"cards_lines.{t}.{kind}: missing")
                continue
            n += 1
            fails += [f"cards_lines.{t}.{kind}: {e}" for e in mod.gate_line(ln, kind)]
    notes.append(f"cards lines: {n} writer line(s) checked for {len(doc or {})} ticker(s)")
    return fails, notes


def _legs_from_marker(line):
    """'Macro legs: expected session 2026-11-04 | breadth_whole_market 2026-11-04 CURRENT | dspx 2026-11-03 PUBLISHER_LAG | ... BEHIND: ...' -> legs rows."""
    out = []
    if not isinstance(line, str) or "Macro legs:" not in line:
        return out
    m = re.search(r"expected session (\d{4}-\d{2}-\d{2})", line)
    exp = m.group(1) if m else None
    for part in line.split("|"):
        mm = re.match(r"\s*([a-z0-9_]+) (\d{4}-\d{2}-\d{2}|None) ([A-Z_]+)\s*$", part)
        if mm:
            out.append({"leg": mm.group(1), "as_of": None if mm.group(2) == "None" else mm.group(2), "expected": exp, "reason": mm.group(3),
                        "detail": "read from the run marker's Macro legs line"})
    return out


def check_macro_legs(VA, FT, fallbacks=None):
    """Every macro leg with its REASON CODE (PM 2026-11-04). FAIL: OUR_BUDGET / SOURCE_DOWN (we are slow or the source is down: the
    committee would vote on stale weather), a missing table (a leg that cannot be audited is not passed), and ANY leg behind two
    nights running whatever the reason. WARN with the code: PUBLISHER_LAG; PUBLISHER_CADENCE is a plain note.
    2026-11-05: the PUBLISHED valen copy is a stripped committee copy; when it carries no table the legs are read from `fallbacks`, a list of
    (label, legs-rows) in order of trust (the full valen_dashboard.json, the crown artifact's data_legs, the run marker's line). The gate still FAILS
    when NONE of them carries a table, and every fallback leg goes through the same reason-code rules."""
    fails, notes = [], []
    legs = ((VA or {}).get("data_freshness") or {}).get("legs_table")
    if VA is not None and not legs:
        for label, rows in (fallbacks or []):
            if rows:
                legs = rows
                notes.append(f"macro legs read from {label} (the published valen copy carries no legs table)")
                break
        else:
            fails.append("aqe_valen_dashboard carries no data_freshness.legs_table, and neither valen_dashboard.json, the crown artifact nor the run marker carries one -- the macro legs cannot be audited (reason codes missing)")
    for r in legs or []:
        rc = r.get("reason")
        if rc in ("OUR_BUDGET", "SOURCE_DOWN"):
            fails.append(f"macro leg {r.get('leg')} as of {r.get('as_of')} vs {r.get('expected')}: {rc} -- {r.get('detail')}")
        elif rc == "PUBLISHER_LAG":
            notes.append(f"WARN macro leg {r.get('leg')} as of {r.get('as_of')} vs {r.get('expected')}: PUBLISHER_LAG -- {r.get('detail')}")
        elif rc == "PUBLISHER_CADENCE":
            notes.append(f"macro leg {r.get('leg')} as of {r.get('as_of')}: PUBLISHER_CADENCE -- {r.get('detail')}")
    hist = [h for h in (FT or {}).get("history") or [] if h.get("legs")]
    if len(hist) >= 2:
        for cur in hist[-1]["legs"]:
            if cur.get("reason") in ("CURRENT", "PUBLISHER_CADENCE"):
                continue
            prev = next((x for x in hist[-2]["legs"] if x.get("leg") == cur.get("leg")), None)
            if prev and prev.get("reason") not in ("CURRENT", "PUBLISHER_CADENCE"):
                fails.append(f"macro leg {cur.get('leg')} has been behind two nights running ({prev.get('reason')} then {cur.get('reason')}) -- someone must own this leg's freshness")
    return fails, notes


def check_data(output_dir, run_yaml=DEFAULT_RUN_YAML, journal_dir=None, broker_stops=None, voice_contract=DEFAULT_VOICE_CONTRACT):
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
    # --- the book and its stops (PM 2026-11-02) ---
    jd = journal_dir or os.path.join(os.path.dirname(os.path.abspath(od)), "data", "journal")
    bf, bn = check_book(jd, run_date, EX, broker_stops)
    fails.extend(bf); notes.extend(bn)
    # --- the committee's FMP inputs, fetched by the daily run (PM 2026-11-03) ---
    cf, cn = check_committee_data(od, run_date, EX)
    fails.extend(cf); notes.extend(cn)
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
        if (os.environ.get("AEGIS_REPORT") or "A").strip().upper() == "C":
            for _need in ("aqe_indicators.tsv", "aqe_glossary.md", "c_required_reading.json"):
                if not os.path.exists(os.path.join(pk, _need)):
                    fails.append(f"report C packet file MISSING: {_need} (every C seat must read the AQE indicators and the glossary)")
        present = sorted(f for f in os.listdir(pk) if f.endswith(".tsv"))
        _trim_receipt = None
        _trp = os.path.join(pk, "packet_trim.json")
        if os.path.exists(_trp):
            try:
                _trim_receipt = json.load(open(_trp, encoding="utf-8"))
            except ValueError:
                fails.append("packets/packet_trim.json is not valid JSON -- a declared trim cannot be verified")
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
                _tr = ((_trim_receipt or {}).get("seats") or {}).get(v)
                if _tr is not None:
                    # a DECLARED trim (packet_trim.json, conductor 2026-11-11): the seat must be shown exactly the candidate set minus the omitted names it declared
                    _want = set(uni) - set(_tr.get("omitted") or [])
                    if tick != _want:
                        fails.append(f"packet {v}.tsv disagrees with its declared trim (packet_trim.json): serves {len(tick)}, declares {len(_want)} "
                                     f"(unlisted: {sorted(tick - _want)[:5]}, dropped without a declaration: {sorted(_want - tick)[:5]})")
                    else:
                        notes.append(f"packet {v}: trimmed by declaration ({_tr.get('mode')}): {len(tick)} of {len(uni)} names, {len(_tr.get('omitted') or [])} omitted and listed")
                elif len(tick) < 0.9 * len(uni):
                    fails.append(f"packet {v}.tsv serves {len(tick)} of {len(uni)} candidate names -- a seat is blind to {len(uni) - len(tick)} (yesterday's packet?)")
            notes.append(f"packet {v}: {len(body) - 1} rows, {len(hdr)} columns, {blank / total:.0%} blank")
        extra = [f for f in present if f[:-4] not in deciders]
        if extra:
            fails.append(f"packets for NON-decider seats present (R31 -- a stray file serves a seat the universe it must not see): {extra}")
        stray_json = [f for f in os.listdir(pk) if f.endswith(".json") and f not in ("no_technical_coverage.json", "packet_trim.json")]
        if stray_json:
            fails.append(f"stray packet files (retired macro seats or unknown): {stray_json} (R31)")
    # --- per-voice data coverage (PM 2026-11-03): each charter's required fields against its packet ---
    if voice_contract and EX is not None and os.path.isdir(pk):
        vf, vn, _ = check_voice_coverage(pk, EX, deciders, voice_contract)
        fails.extend(vf); notes.extend(vn)
    elif not voice_contract:
        notes.append("WARN voice coverage check DISABLED by --voice-contract none (never use this in a real run)")
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
    _fb = []
    try:
        _full = _load(os.path.join(od, "valen_dashboard.json"), "valen_dashboard.json", [])
        _fb.append(("valen_dashboard.json", ((_full or {}).get("data_freshness") or {}).get("legs_table")))
        _fb.append(("aqe_crown_macro.json data_legs", ((CR or {}).get("data_legs") or {}).get("legs")))
        _fb.append(("the run marker's Macro legs line", _legs_from_marker((LR or {}).get("macro_legs"))))
    except Exception:  # noqa: BLE001 - a fallback that cannot be read is simply not a fallback
        pass
    mf, mn = check_macro_legs(VA, _load(os.path.join(od, "feed_timing.json"), "feed_timing.json", []), _fb)
    fails += mf; notes += mn
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
    for n in notes:                                  # WARN lines first: they are the PM's to read
        if n.startswith("WARN "):
            print(f"  WARN  {n[5:]}")
    for n in notes:
        if not n.startswith("WARN "):
            print(f"  note  {n}")
    return 0 if not fails else 1


# ---- Which report is this run? (PM 2026-11-05) The environment wins; otherwise the run's own manifest says (`report`), so a seat that runs a
# printed command bare still gets the right roster. Looked for in the working directory, then beside any file named on the command line.
def _resolve_report_from_manifest(argv=None):
    if (os.environ.get("AEGIS_REPORT") or "").strip():
        return
    cands, argv = [], list(argv if argv is not None else sys.argv[1:])
    for i, x in enumerate(argv):
        if x == "--manifest" and i + 1 < len(argv):
            cands.append(argv[i + 1])
    cands.append("run_manifest.json")
    for x in argv:
        if isinstance(x, str) and os.path.exists(x):
            d = x if os.path.isdir(x) else os.path.dirname(os.path.abspath(x))
            cands += [os.path.join(d, "run_manifest.json"), os.path.join(os.path.dirname(d), "run_manifest.json")]
    for c in cands:
        try:
            if os.path.isfile(c):
                rep = str((json.load(open(c)) or {}).get("report") or "").strip().upper()
                if rep in ("B", "C"):
                    os.environ["AEGIS_REPORT"] = rep
                return
        except Exception:
            continue


def main(argv=None):
    _resolve_report_from_manifest(argv)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ready"); r.add_argument("--last-run", required=True); r.add_argument("--today", default=None)
    c = sub.add_parser("chain"); c.add_argument("--run-dir", required=True); c.add_argument("--date", required=True)
    c.add_argument("--levels", default=None); c.add_argument("--run-yaml", default=DEFAULT_RUN_YAML)
    c.add_argument("--ceiling-tokens", type=int, default=DEFAULT_CEILING)
    d_ = sub.add_parser("data"); d_.add_argument("--output-dir", required=True); d_.add_argument("--run-yaml", default=DEFAULT_RUN_YAML)
    d_.add_argument("--voice-contract", default=DEFAULT_VOICE_CONTRACT, help="voice_coverage.json; 'none' disables the per-voice coverage check (tests only)")
    d_.add_argument("--journal-dir", default=None, help="default: <output-dir>/../data/journal")
    d_.add_argument("--broker-stops", default=None, help="GATHER's broker_stops.json, cross-checked against the journal")
    ct = sub.add_parser("cards", help="B3: the Cards' plain one-voice reason block (FAIL on raw field names, tallies, jargon, > 4 numbers)")
    ct.add_argument("--text", default="cards_text.json"); ct.add_argument("--html", default=None, help="the rendered pma_cards_<date>.html: FAIL on any raw field name in its text")
    ct.add_argument("--lines", default=None, help="cards_lines.json (PM 2026-11-05): the writer's committee-voice lines 2 and 3 per card; FAIL on any line that breaks the plain-words/seat/tally gate")
    cv = sub.add_parser("coverage", help="per-voice data coverage; run BEFORE the vote with --phase4 so name-level blanks are scoped to the room")
    cv.add_argument("--packets-dir", required=True); cv.add_argument("--export", required=True)
    cv.add_argument("--phase4", default=None, help="phase4.json: scope name-level blanks to its deliberation_set")
    cv.add_argument("--contract", default=DEFAULT_VOICE_CONTRACT); cv.add_argument("--menus", default=DEFAULT_MENUS)
    cv.add_argument("--run-yaml", default=DEFAULT_RUN_YAML); cv.add_argument("--out", default=None, help="write the full report as JSON")
    a_ = sub.add_parser("all"); a_.add_argument("--last-run", required=True); a_.add_argument("--today", default=None)
    a_.add_argument("--output-dir", default=None)
    a_.add_argument("--run-dir", required=True); a_.add_argument("--date", required=True); a_.add_argument("--levels", default=None)
    a_.add_argument("--run-yaml", default=DEFAULT_RUN_YAML); a_.add_argument("--ceiling-tokens", type=int, default=DEFAULT_CEILING)
    a = ap.parse_args(argv)
    rc = 0
    if a.cmd in ("ready", "all"):
        f, n = check_ready(a.last_run, a.today); rc |= _report("READY", f, n)
    if a.cmd == "data" or (a.cmd == "all" and getattr(a, "output_dir", None)):
        vc = getattr(a, "voice_contract", DEFAULT_VOICE_CONTRACT)
        f, n = check_data(a.output_dir, a.run_yaml, getattr(a, "journal_dir", None),
                          getattr(a, "broker_stops", None), None if str(vc).lower() == "none" else vc); rc |= _report("DATA HANDOFF", f, n)
    if a.cmd == "cards":
        f, n = check_cards_text(a.text); rc |= _report("CARDS TEXT", f, n)
        if getattr(a, "lines", None):
            f, n = check_cards_lines(a.lines); rc |= _report("CARDS LINES", f, n)
        if getattr(a, "html", None):
            f, n = check_cards_html(a.html); rc |= _report("CARDS HTML", f, n)
    if a.cmd == "coverage":
        fails, ex = [], None
        ex = _load(a.export, "export", fails)
        room = None
        if a.phase4:
            p4 = _load(a.phase4, "phase4.json", fails)
            room = set((p4 or {}).get("deliberation_set") or []) or None
            if p4 is not None and not room:
                fails.append("phase4.json has an empty deliberation_set -- nothing to scope the coverage to")
        if ex is not None and not fails:
            f, n, rep = check_voice_coverage(a.packets_dir, ex, _deciders(a.run_yaml), a.contract, a.menus, room)
            fails += f
            if a.out:
                json.dump(rep, open(a.out, "w"), indent=1)
        else:
            n = []
        rc |= _report("VOICE COVERAGE", fails, n)
    if a.cmd in ("chain", "all"):
        f, n = check_chain(a.run_dir, a.date, a.levels, a.run_yaml, a.ceiling_tokens); rc |= _report("CHAIN", f, n)
    return rc


if __name__ == "__main__":
    sys.exit(main())
