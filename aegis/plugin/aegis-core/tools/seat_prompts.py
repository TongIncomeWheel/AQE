#!/usr/bin/env python3
"""seat_prompts.py -- the committee's round prompts, built from the run's OWN files (conductor + PM 2026-11-19; first slice of the repo-owned prompt tool).

WHY: the round prompts used to be scratch text hand-copied from the previous day's (19 Nov: yesterday's book in R1, then MBGL/CHYM in RATIFY2). This builds the
prompts of the LATER rounds -- CROSS, TIER2, RATIFY, FLOOR2, RATIFY2, ADOPT -- from templates in contracts/prompts/ and from facts read out of the run directory
(run_manifest date, phase4, funnel, claims packets, qa note, slate, rationale draft). A source file that is missing is a loud SystemExit, never a default and never
a carried value.

SEAT ROWS (the 19 Nov NOT_SERVED audit): later rounds used to carry no AQE rows at all. Every prompt now has one more READ item,
<work>/seat_rows/<ROUND>/<seat>.json: each of the round's tickers, sliced to THAT seat's own menu + the held and momentum floors, built by `pma_pipeline.py seat-rows`
(run by this tool). A ticker with no row is declared in the file (row_gap). The prompt tells the seat that a field not in the file is off its menu.

PERSISTENT SEATS: each prompt is self-contained for FACTS (session, data-through date, the round's tickers and the files to write are in the text), so a seat that is
resumed with the round as a message does not have to remember an earlier file or re-read its card to know what is being asked of it.

STALE-TEXT TEST: `check_prompt` fails a prompt that carries an ISO date other than the run date / the data-through date, or a ticker that belongs to another run's
book or slate and not to this run's own files (the RBRK / SPCX / MBGL / CHYM defects).

    python3 seat_prompts.py build --round CROSS --work /home/user/pma_run/2026-11-19 --repo /home/user/AQE [--out DIR] [--no-rows]
    python3 seat_prompts.py build --round ALL ...
    python3 seat_prompts.py check --work ... --repo ... --file prompt.txt [--file ...]
"""
import argparse
import datetime
import glob
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACTS = os.path.abspath(os.path.join(HERE, "..", "contracts"))
TEMPLATES = os.path.join(CONTRACTS, "prompts")
SEATS = ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]
ROUNDS = ["CROSS", "TIER2", "RATIFY", "FLOOR2", "RATIFY2", "ADOPT"]
SEAT_ROWS_NOTE = ("each ticker of this round with the AQE fields on YOUR menu (plus the held and momentum floors); a field that is not in it is off your menu, "
                  "a ticker with row_gap has no AQE row and you declare it unread")


def die(msg):
    raise SystemExit(f"seat_prompts: {msg}")


def jload(path, what):
    if not os.path.exists(path):
        die(f"{what} is missing ({path}) -- refusing to build from a carried or guessed value")
    try:
        return json.load(open(path, encoding="utf-8"))
    except ValueError as e:
        die(f"{what} is not valid JSON ({path}: {e})")


def tickers_of(items):
    return [x if isinstance(x, str) else (x.get("ticker") or x.get("name")) for x in items]


# ------------------------------------------------------------------------------------------------ run facts
def run_dates(work, data_through=None):
    man = jload(os.path.join(work, "run_manifest.json"), "run_manifest.json")
    date = str(man.get("date") or "")
    try:
        d = datetime.date.fromisoformat(date)
    except ValueError:
        die(f"run_manifest.json has no valid date ({date!r})")
    if data_through:
        p = datetime.date.fromisoformat(data_through)
    elif man.get("data_through"):
        p = datetime.date.fromisoformat(str(man["data_through"]))
    else:                                       # the previous US weekday; a holiday needs the manifest's data_through or --data-through
        p = d - datetime.timedelta(days=1)
        while p.weekday() >= 5:
            p -= datetime.timedelta(days=1)
    return d, p


def base_facts(work, data_through=None):
    d, p = run_dates(work, data_through)
    return {"DATE": d.isoformat(), "WEEKDAY": d.strftime("%A"), "US_SESSION": f"{d.strftime('%a')} {d.day} {d.strftime('%b')}",
            "DATA_DATE": p.isoformat(), "DATA_WEEKDAY": p.strftime("%A")}


def _held_from_qa(work):
    qa = jload(os.path.join(work, "forms", "qa", "steenbarger.json"), "forms/qa/steenbarger.json")
    holds = qa.get("holds") or []
    if not holds:
        die("forms/qa/steenbarger.json carries no holds -- there is no floor round to build")
    return [h["ticker"] for h in holds], holds


def _routed_claims(work, seat):
    """(claim ids routed to this seat, their tickers) from claims_board.json -- the board the registrar validates the cross form against."""
    cb = jload(os.path.join(work, "claims_board.json"), "claims_board.json")
    ids = (cb.get("routing") or {}).get(seat)
    if ids is None:
        die(f"claims_board.json routes nothing to {seat} (not a decider present in this run)")
    claim_t = {c["claim_id"]: t for t, n in (cb.get("names") or {}).items() for c in n.get("claims") or []}
    missing = [i for i in ids if i not in claim_t]
    if missing:
        die(f"claims_board.json routes claim ids that no name carries: {missing[:5]}")
    return ids, [claim_t[i] for i in ids]


def round_tickers(rnd, work, seat):
    """The tickers THIS seat sees in this round (the seat-rows list)."""
    if rnd == "CROSS":
        return list(dict.fromkeys(_routed_claims(work, seat)[1]))
    if rnd == "TIER2":
        return tickers_of(jload(os.path.join(work, "funnel.json"), "funnel.json")["survivors"])
    if rnd == "RATIFY":
        return [t["ticker"] for t in jload(os.path.join(work, "slate.json"), "slate.json")["tickets"]]
    if rnd in ("FLOOR2", "RATIFY2"):
        return _held_from_qa(work)[0]
    if rnd == "ADOPT":
        d = jload(os.path.join(work, "rationale_draft.json"), "rationale_draft.json")
        return list(dict.fromkeys(x["ticker"] for x in (d.get("tickets") or d.get("rationale") or d.get("names") or []) if isinstance(x, dict) and x.get("ticker")))
    die(f"unknown round {rnd}")


def round_facts(rnd, work, seat):
    f = {}
    if rnd == "CROSS":
        f["N_CLAIMS"] = str(len(_routed_claims(work, seat)[0]))
    elif rnd == "TIER2":
        sv = tickers_of(jload(os.path.join(work, "funnel.json"), "funnel.json")["survivors"])
        h = math.ceil(len(sv) / 2)
        a, b = sv[:h], sv[h:]
        f.update(N_SURV=str(len(sv)), P1N=str(len(a)), P1=" ".join(a), P2N=str(len(b)), P2=" ".join(b))
    elif rnd in ("FLOOR2", "RATIFY2"):
        held, holds = _held_from_qa(work)
        words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
        f.update(N_HELD=str(len(held)), N_HELD_WORD=words.get(len(held), str(len(held))), S="" if len(held) == 1 else "s", HELD_LIST=", ".join(held),
                 HELD_AND=held[0] if len(held) == 1 else ", ".join(held[:-1]) + " and " + held[-1],
                 QA_QUESTIONS="\n".join(f"- {h['ticker']}: {h['question']}" for h in holds),
                 HELD_FILES=" and ".join(f"{work}/forms/floor2/{seat}-{t}.json" for t in held))
    return f


def seat_rows_path(work, rnd, seat):
    return os.path.join(work, "seat_rows", rnd, f"{seat}.json")


def render(rnd, seat, work, repo, with_rows=True, data_through=None):
    tpl = os.path.join(TEMPLATES, f"{rnd}.txt")
    if not os.path.exists(tpl):
        die(f"no template for {rnd} ({tpl})")
    text = open(tpl, encoding="utf-8").read()
    facts = {**base_facts(work, data_through), **round_facts(rnd, work, seat),
             "SEAT": seat.upper(), "seat": seat, "R": work, "PLUG": os.path.join(repo, "aegis", "plugin")}
    n = len(re.findall(r"^\d+\. ", text.split("<<SEAT_ROWS_ITEM>>")[0].split("READ ONLY")[-1], flags=re.M)) + 1 if "<<SEAT_ROWS_ITEM>>" in text else None
    sr = seat_rows_path(work, rnd, seat)
    if "<<SEAT_ROWS_ITEM>>" in text:
        facts["SEAT_ROWS_ITEM"] = (f"{n}. Your AQE data for this round: {sr} -- {SEAT_ROWS_NOTE}" if with_rows else None)
        text = text.replace("\n<<SEAT_ROWS_ITEM>>", "\n<<SEAT_ROWS_ITEM>>" if with_rows else "")
    facts["SEAT_ROWS_INLINE"] = f"; (6) your AQE data for these tickers: {sr} ({SEAT_ROWS_NOTE})" if with_rows else ""
    for k, v in sorted(facts.items(), key=lambda kv: -len(kv[0])):
        if v is not None:
            text = text.replace(f"<<{k}>>", str(v))
    left = re.findall(r"<<[A-Za-z_0-9]+>>", text)
    if left:
        die(f"{rnd}/{seat}: unfilled placeholder(s) {sorted(set(left))}")
    return text


def build_rows(rnd, seat, work, repo, menus=None, py=sys.executable):
    """Run `pma_pipeline.py seat-rows` for this seat and this round's tickers -> <work>/seat_rows/<ROUND>/<seat>.json."""
    names = round_tickers(rnd, work, seat)
    if not names:
        die(f"{rnd}/{seat}: no tickers to build rows for")
    pipe = os.path.join(HERE, "pma_pipeline.py")
    out = os.path.join(work, "seat_rows", rnd, "_tmp_" + seat)
    cmd = [py, pipe, "seat-rows", "--candidates", os.path.join(work, "candidate_set.json"), "--menus", menus or os.path.join(CONTRACTS, "voice_menus.json"),
           "--tickers", *names, "--date", run_dates(work)[0].isoformat(), "--outdir", out, "--seats", seat]
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, AEGIS_REPORT=os.environ.get("AEGIS_REPORT", "A")))
    final = seat_rows_path(work, rnd, seat)
    os.makedirs(os.path.dirname(final), exist_ok=True)
    src = os.path.join(out, f"{seat}.json")
    if os.path.exists(src):
        os.replace(src, final)
    if r.returncode != 0:
        print(f"seat_prompts: WARNING {rnd}/{seat}: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:]}")
    return final, names


# ------------------------------------------------------------------------------------------------ the stale-text test
TICKER_WORD = re.compile(r"\b[A-Z]{2,5}\b")


def run_tickers(work):
    """Every ticker the run's own files name."""
    out = set()
    for fn in ("candidate_set.json", "phase4.json", "funnel.json", "slate.json", "slate_held.json", "claims_board.json", "rationale_draft.json", "consensus.json"):
        p = os.path.join(work, fn)
        if os.path.exists(p):
            out |= set(re.findall(r'"ticker":\s*"([A-Z.]{1,6})"', open(p, encoding="utf-8").read()))
            out |= set(re.findall(r'"([A-Z]{2,5})":\s*\{', open(p, encoding="utf-8").read()))
    return out


def foreign_tickers(repo, work, run_date):
    """Tickers that belong to ANOTHER run's book / slate / held files and not to this run's own files."""
    mine = run_tickers(work)
    out = set()
    for d in glob.glob(os.path.join(repo, "aegis", "output", "pma", "run", "*")):
        if os.path.basename(d).startswith(run_date):
            continue
        for fn in ("slate.json", "slate_held.json", "broker_stops.json", "committee_position.json"):
            p = os.path.join(d, fn)
            if os.path.exists(p):
                try:
                    out |= set(re.findall(r'"(?:ticker|symbol)":\s*"([A-Z.]{1,6})"', open(p, encoding="utf-8").read()))
                except OSError:
                    pass
    return out - mine


def check_prompt(text, work, repo, data_through=None):
    """-> list of defects. A date the run does not own, or another run's ticker, in a generated prompt."""
    d, p = run_dates(work, data_through)
    allowed = {d.isoformat(), p.isoformat()}
    bad = []
    for m in sorted(set(re.findall(r"\b20\d\d-\d\d-\d\d\b", text))):
        if m not in allowed:
            bad.append(f"date {m} is not this run's date {d} or its data-through date {p}")
    words = set(TICKER_WORD.findall(text))
    for t in sorted(words & foreign_tickers(repo, work, d.isoformat())):
        bad.append(f"ticker {t} belongs to another run's book or slate, not to this run's own files")
    return bad


# ------------------------------------------------------------------------------------------------ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--round", required=True, help="CROSS|TIER2|RATIFY|FLOOR2|RATIFY2|ADOPT|ALL")
    b.add_argument("--work", required=True); b.add_argument("--repo", required=True)
    b.add_argument("--out", default=None); b.add_argument("--seats", nargs="*", default=None)
    b.add_argument("--no-rows", action="store_true", help="do not build seat rows (prompts then carry no seat-rows READ item); a declared degradation")
    b.add_argument("--data-through", default=None)
    c = sub.add_parser("check")
    c.add_argument("--work", required=True); c.add_argument("--repo", required=True); c.add_argument("--file", action="append", required=True); c.add_argument("--data-through", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        rc = 0
        for f in a.file:
            bad = check_prompt(open(f, encoding="utf-8").read(), a.work, a.repo, a.data_through)
            for x in bad:
                print(f"STALE {f}: {x}")
            rc |= bool(bad)
        print("seat_prompts check: " + ("FAIL" if rc else "clean"))
        return rc
    rounds = ROUNDS if a.round.upper() == "ALL" else [a.round.upper()]
    seats = a.seats or SEATS
    out_root = a.out or os.path.join(a.work, "prompts")
    rc = 0
    for rnd in rounds:
        if rnd not in ROUNDS:
            die(f"round {rnd} is not one of {ROUNDS} (the earlier rounds are not repo-owned yet)")
        for s in seats:
            if not a.no_rows:
                build_rows(rnd, s, a.work, a.repo)
            text = render(rnd, s, a.work, a.repo, with_rows=not a.no_rows, data_through=a.data_through)
            bad = check_prompt(text, a.work, a.repo, a.data_through)
            if bad:
                rc = 1
                for x in bad:
                    print(f"STALE {rnd}/{s}: {x}")
            os.makedirs(os.path.join(out_root, rnd), exist_ok=True)
            open(os.path.join(out_root, rnd, f"{s}.txt"), "w", encoding="utf-8").write(text)
        print(f"seat_prompts: {rnd}: {len(seats)} prompt(s) -> {os.path.join(out_root, rnd)}" + ("" if a.no_rows else f"; seat rows -> {os.path.join(a.work, 'seat_rows', rnd)}"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
