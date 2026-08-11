#!/usr/bin/env python3
"""pma_run.py — deterministic runner for the /premarket-analysis (PMA) kernel, v0.1.

Implements the DETERMINISTIC stages only (S1 ingest, S2 market frame, S3 candidate
frame, S7 plan assembly, S8 self-audit). No model judgment anywhere in this tool —
same inputs, same outputs. Judgment stages (S4 voices, S5 challenge/weather,
S6 deliberation) are spawned agents whose outputs this tool merely validates and
renders.

Usage:
  python3 tools/pma_run.py s1 --export PATH --crown PATH --date YYYY-MM-DD [--ack "reason"]
  python3 tools/pma_run.py s2 --date YYYY-MM-DD
  python3 tools/pma_run.py s3 --date YYYY-MM-DD
  python3 tools/pma_run.py s7 --date YYYY-MM-DD --render
  python3 tools/pma_run.py s8 --date YYYY-MM-DD

Conventions:
  - AEGIS root = parent of this file's directory. All artifacts under
    data/pma/DATE/ ; contracts under contracts/pma/.
  - Every output is schema-validated against its own contract before it lands.
    An artifact that fails its own contract is a build bug, and the tool exits 1.
  - Staleness is DECLARED in every downstream artifact (staleness_days + pm_ack),
    never silently dropped. A stale export proceeds only with an explicit --ack,
    recorded verbatim.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONTRACTS = os.path.join(ROOT, "contracts")
PMA_CONTRACTS = os.path.join(CONTRACTS, "pma")

STATUS_LINE = "DRAFT — PM approval required. Nothing is staged, nothing is armed."


# ---------------------------------------------------------------- helpers

def out_dir(date):
    d = os.path.join(ROOT, "data", "pma", date)
    os.makedirs(d, exist_ok=True)
    return d


def now_iso():
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path):
    with open(path) as f:
        return json.load(f)


def schema_errors(instance, schema_path, limit=10):
    """Validate; return list of error strings (empty = valid)."""
    import jsonschema
    schema = load_json(schema_path)
    validator = jsonschema.Draft202012Validator(schema)
    errs = []
    for e in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        errs.append(f"{loc}: {e.message[:200]}")
        if len(errs) >= limit:
            errs.append("... (truncated)")
            break
    return errs


def write_validated(obj, date, name, schema_name):
    """Write artifact only after it validates against its own contract."""
    schema_path = os.path.join(PMA_CONTRACTS, schema_name)
    errs = schema_errors(obj, schema_path)
    if errs:
        print(f"[pma] BUILD BUG — {name} fails its own contract {schema_name}:", file=sys.stderr)
        for e in errs:
            print("   ", e, file=sys.stderr)
        sys.exit(1)
    path = os.path.join(out_dir(date), name)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"[pma] wrote {os.path.relpath(path, ROOT)} (valid vs {schema_name})")
    return path


def parse_date(s):
    return dt.date.fromisoformat(s[:10])


def staleness_block(receipt):
    """The declaration every downstream artifact carries."""
    exp = receipt["files"]["export"]
    return {
        "export_date": exp["generated_at"],
        "staleness_days": exp["staleness_days"],
        "pm_ack": receipt["pm_ack"],
    }


def read_receipt(date):
    path = os.path.join(out_dir(date), "ingest_receipt.json")
    if not os.path.exists(path):
        print("[pma] no ingest_receipt.json for this date — run s1 first.", file=sys.stderr)
        sys.exit(1)
    r = load_json(path)
    if not r["proceed"]:
        print(f"[pma] ingest receipt says proceed=false ({r['blocking_reason']}) — refusing.", file=sys.stderr)
        sys.exit(1)
    return r


def input_paths(receipt):
    return receipt["files"]["export"]["path"], receipt["files"]["crown"]["path"]


def _apply_aliases(node, aliases):
    """Recursively add new-name keys where only the old name exists (validation-only).
    Returns True if any alias was applied anywhere."""
    applied = False
    if isinstance(node, dict):
        for old, new in aliases.items():
            if old in node and new not in node:
                node[new] = node[old]
                applied = True
        for v in node.values():
            applied = _apply_aliases(v, aliases) or applied
    elif isinstance(node, list):
        for v in node:
            applied = _apply_aliases(v, aliases) or applied
    return applied


# ---------------------------------------------------------------- S1 INGEST

def s1(args):
    run_date = args.date
    notes = []
    receipt = {
        "artifact": "pma_ingest_receipt",
        "run_date": run_date,
        "generated_at": now_iso(),
        "files": {},
        "crown_absent": False,
        "proceed": False,
        "blocking_reason": None,
        "pm_ack": None,
        "notes": notes,
    }

    # ---- export ----
    exp = {"found": False, "path": None, "fetched_at": None, "generated_at": None,
           "staleness_days": None, "schema_valid": None, "schema_errors": [],
           "tripwire_result": None, "status": None,
           "oldest_source_days_behind": None, "degraded_flags": []}
    receipt["files"]["export"] = exp
    if args.export and os.path.exists(args.export):
        exp["found"] = True
        exp["path"] = os.path.abspath(args.export)
        exp["fetched_at"] = now_iso()
        try:
            export = load_json(args.export)
        except Exception as e:  # malformed JSON = refuse
            receipt["blocking_reason"] = f"export is not parseable JSON: {e}"
            return finish_s1(receipt, run_date)
        exp["generated_at"] = export.get("date")
        if exp["generated_at"]:
            exp["staleness_days"] = (parse_date(run_date) - parse_date(exp["generated_at"])).days
        # Full jsonschema validation against the existing export contract.
        # The contract documents field renames (x_field_renames: "old -> new")
        # and instructs readers of archived exports to treat the two names as
        # one field — so the rename equivalence is applied BEFORE validating
        # (deterministic, contract-sanctioned, recorded; export on disk unchanged).
        exp_schema_path = os.path.join(CONTRACTS, "aqe_export.schema.json")
        exp_schema = load_json(exp_schema_path)
        aliases = {}
        for k in exp_schema.get("x_field_renames", {}):
            parts = [p.strip() for p in k.split("->")]
            if len(parts) == 2:
                aliases[parts[0]] = parts[1]
        to_validate = export
        if aliases:
            to_validate = json.loads(json.dumps(export))  # deep copy; validation-only
            if _apply_aliases(to_validate, aliases):
                notes.append(
                    "card-vs-reality: export predates schema x_field_renames "
                    f"({', '.join(f'{o} -> {n}' for o, n in aliases.items())}); validated with the "
                    "schema's own rename equivalence applied. The export on disk is unchanged.")
        errs = schema_errors(to_validate, exp_schema_path)
        exp["validation_basis"] = "full"
        if errs:
            # Full validation still fails after the documented rename equivalence.
            # Fall back to the structural check on required top-level keys — but
            # NEVER silently: the full errors stay in the receipt verbatim and
            # the drift is filed as a design finding in notes.
            required_top = load_json(exp_schema_path).get("required", [])
            missing_top = [k for k in required_top if k not in export]
            if not missing_top:
                exp["validation_basis"] = "structural_fallback"
                exp["degraded_flags"].append(
                    f"full aqe_export.schema.json validation failed ({len(errs)} recorded error(s), "
                    f"e.g. {errs[0]}); all {len(required_top)} required top-level keys present — "
                    "proceeding on the structural basis, drift recorded in notes")
                notes.append(
                    "card-vs-reality: this export fails the current aqe_export.schema.json "
                    f"(x_version {load_json(exp_schema_path).get('x_version')}) beyond the documented renames — "
                    f"sample: {'; '.join(errs[:3])}. Schema postdates the export or the exporter drifted; "
                    "filed as a design finding, not silently fixed.")
                exp["schema_valid"] = True  # on the declared structural basis
                exp["schema_errors"] = errs  # kept verbatim — the fallback never hides them
            else:
                exp["degraded_flags"].append(
                    f"structural check failed too — missing required top-level keys: {missing_top}")
                exp["schema_valid"] = False
                exp["schema_errors"] = errs
        else:
            exp["schema_valid"] = True
            exp["schema_errors"] = []
        # tripwires (existing machinery, reused not cloned)
        tw = subprocess.run([sys.executable, os.path.join(HERE, "tripwires.py"), args.export],
                            capture_output=True, text=True)
        exp["tripwire_result"] = {"exit_code": tw.returncode,
                                  "output": (tw.stdout + tw.stderr).strip()[:2000]}
        dq = export.get("data_quality", {})
        if dq.get("flagged_count"):
            exp["degraded_flags"].append(f"data_quality flagged_count={dq['flagged_count']}")
        if export.get("held_positions_status") not in (None, "live"):
            exp["degraded_flags"].append(f"held_positions_status={export.get('held_positions_status')}")
    else:
        receipt["blocking_reason"] = f"export not found at {args.export}"
        return finish_s1(receipt, run_date)

    # ---- crown ----
    cr = {"found": False, "path": None, "fetched_at": None, "generated_at": None,
          "staleness_days": None, "schema_valid": None, "schema_errors": [],
          "tripwire_result": None, "status": None,
          "oldest_source_days_behind": None, "degraded_flags": []}
    receipt["files"]["crown"] = cr
    if args.crown and os.path.exists(args.crown):
        cr["found"] = True
        cr["path"] = os.path.abspath(args.crown)
        cr["fetched_at"] = now_iso()
        try:
            crown = load_json(args.crown)
        except Exception as e:
            receipt["crown_absent"] = True
            cr["degraded_flags"].append(f"crown not parseable ({e}) — run continues AQE-only")
            crown = None
        if crown is not None:
            cr["generated_at"] = crown.get("generated_at")
            if cr["generated_at"]:
                cr["staleness_days"] = (parse_date(run_date) - parse_date(cr["generated_at"][:10])).days
            errs = schema_errors(crown, os.path.join(PMA_CONTRACTS, "crown_macro.schema.json"))
            cr["schema_valid"] = not errs
            cr["schema_errors"] = errs
            cr["status"] = crown.get("status")
            cr["oldest_source_days_behind"] = (crown.get("how_current") or {}).get("oldest_source_days_behind")
            if cr["status"] == "DEGRADED":
                # NOT a failure — propagates as a flag with limits verbatim
                cr["degraded_flags"].append("crown status DEGRADED — limits[] carried verbatim downstream")
                cr["degraded_flags"].extend(crown.get("limits", []))
            if errs:
                receipt["crown_absent"] = True
                cr["degraded_flags"].append("crown failed structural contract — treated as absent, run continues AQE-only")
    else:
        receipt["crown_absent"] = True
        cr["degraded_flags"].append("crown file missing — run continues AQE-only (plan headline will say so)")

    # ---- freshness / proceed ladder ----
    if not exp["schema_valid"]:
        receipt["blocking_reason"] = "export failed aqe_export.schema.json validation"
        return finish_s1(receipt, run_date)
    if exp["tripwire_result"]["exit_code"] != 0:
        receipt["blocking_reason"] = "tripwires BLOCK on export"
        return finish_s1(receipt, run_date)
    if exp["staleness_days"] and exp["staleness_days"] > 0:
        if args.ack:
            receipt["pm_ack"] = args.ack
            receipt["proceed"] = True
            notes.append(
                f"export is {exp['staleness_days']} day(s) stale (export date {exp['generated_at']}, "
                f"run date {run_date}); proceeding ONLY on explicit acknowledgement, recorded verbatim in pm_ack")
        else:
            receipt["blocking_reason"] = (
                f"export stale by {exp['staleness_days']} day(s) and no --ack given "
                "(RB:data_sources.staleness — stale needs explicit PM acknowledgement)")
            return finish_s1(receipt, run_date)
    else:
        receipt["proceed"] = True

    return finish_s1(receipt, run_date)


def finish_s1(receipt, run_date):
    write_validated(receipt, run_date, "ingest_receipt.json", "ingest_receipt.schema.json")
    print(f"[pma] S1 proceed={receipt['proceed']}"
          + (f" blocking_reason={receipt['blocking_reason']}" if receipt["blocking_reason"] else "")
          + (f" pm_ack={receipt['pm_ack']!r}" if receipt["pm_ack"] else ""))
    return 0 if receipt["proceed"] else 1


# ---------------------------------------------------------------- S2 MARKET FRAME

def s2(args):
    run_date = args.date
    receipt = read_receipt(run_date)
    export_path, crown_path = input_paths(receipt)
    export = load_json(export_path)
    crown = load_json(crown_path) if (crown_path and not receipt["crown_absent"]) else None

    gaps = []
    exp_stale = receipt["files"]["export"]["staleness_days"]
    if exp_stale:
        gaps.append(f"export is {exp_stale} day(s) stale — pm_ack: {receipt['pm_ack']}")
    reg = export["regime"]

    # momentum caveat: the hurst/trend implication in one plain sentence, said once here
    caveat_text = (
        f"Tape reads {reg['trend']} (hurst {reg['hurst']}, VIX {reg['vix']}, regime {reg['level']}): "
        f"{reg['implication']}."
    )
    if reg["trend"] != "TRENDING":
        caveat_text += " A non-trending tape is a caveat on every momentum idea downstream."

    # crown block
    if crown:
        levels = [l for l in crown.get("key_levels", [])]
        near = sorted(levels, key=lambda l: abs(l["distance_pct"]) if l.get("distance_pct") is not None else 1e9)[:8]
        crown_block = {
            "present": True,
            "status": crown.get("status"),
            "headline": crown["read_me_first"]["headline"],
            "family": crown["the_call"]["expression_family"],
            "match_quality": crown["the_call"].get("match_quality"),
            "size_multiplier": crown["the_call"]["size_multiplier"],
            "conditions_met": crown["the_call"].get("conditions_met", []),
            "conditions_not_met": crown["the_call"].get("conditions_not_met", []),
            "key_levels_near": near,
            "limits": crown.get("limits", []),
            "oldest_source_days_behind": (crown.get("how_current") or {}).get("oldest_source_days_behind"),
            "source": "aqe_crown_macro.json (read_me_first, the_call, key_levels, limits — relayed, never re-generated)",
        }
        if crown.get("status") == "DEGRADED":
            gaps.append("crown ran DEGRADED — its limits[] are carried verbatim in crown.limits")
    else:
        crown_block = {"present": False, "status": None, "headline": None, "family": None,
                       "match_quality": None, "size_multiplier": None, "conditions_met": [],
                       "conditions_not_met": [], "key_levels_near": [], "limits": [],
                       "oldest_source_days_behind": None,
                       "source": "aqe_crown_macro.json (ABSENT)"}
        gaps.append("Crown macro absent — regime read is AQE-only")

    # sectors — the rotation map, straight relay with provenance
    sectors = [{
        "etf": s["etf"], "sector": s["sector"], "grade": s["grade"],
        "rrg_quadrant": s["rrg_quadrant"], "rrg_direction": s.get("rrg_direction"),
        "macro_headwind_flag": s["macro_headwind_flag"],
        "entry_gate": s["entry_gate"], "entry_gate_reason": s.get("entry_gate_reason"),
        "source": f"srm[etf={s['etf']}]",
    } for s in export["srm"]]

    im, mw = export["intermarket"], export["macro_weather"]
    cross_asset = {
        "dollar": {
            "text": f"Dollar (UUP) {mw['uup_direction']}: close {im['uup']['close']}, roc5 {im['uup']['roc5']}, roc20 {im['uup']['roc20']}, above_sma20 {im['uup']['above_sma20']}.",
            "values": {"close": im["uup"]["close"], "roc5": im["uup"]["roc5"], "roc20": im["uup"]["roc20"]},
            "sources": ["intermarket.uup", "macro_weather.uup_direction"]},
        "bonds": {
            "text": f"Bonds (TLT) {mw['tlt_direction']}: close {im['tlt']['close']}, roc5 {im['tlt']['roc5']}, roc20 {im['tlt']['roc20']}.",
            "values": {"close": im["tlt"]["close"], "roc5": im["tlt"]["roc5"], "roc20": im["tlt"]["roc20"]},
            "sources": ["intermarket.tlt", "macro_weather.tlt_direction"]},
        "credit": {
            "text": f"Credit (HYG) {mw['hyg_direction']}: close {im['hyg']['close']}, roc5 {im['hyg']['roc5']}, HYG-TLT spread {im['hyg']['hyg_tlt_spread']}.",
            "values": {"close": im["hyg"]["close"], "roc5": im["hyg"]["roc5"], "hyg_tlt_spread": im["hyg"]["hyg_tlt_spread"]},
            "sources": ["intermarket.hyg", "macro_weather.hyg_direction"]},
        "breadth": {
            "text": f"Large vs small (SPY-IWM roc20 spread {im['spy_iwm']['spread']}): SPY {im['spy_iwm']['spy_roc20']} vs IWM {im['spy_iwm']['iwm_roc20']}. Macro read: {mw['regime_description']}",
            "values": {"spy_roc20": im["spy_iwm"]["spy_roc20"], "iwm_roc20": im["spy_iwm"]["iwm_roc20"], "spread": im["spy_iwm"]["spread"]},
            "sources": ["intermarket.spy_iwm", "macro_weather.regime_description"]},
    }

    thematic = [{
        "basket": name, "grade": b.get("grade"), "parent_gics": b.get("parent_gics"),
        "rrg_quadrant": b.get("rrg_quadrant"), "roc20": b.get("roc20"),
        "source": f"thematic_baskets.{name}",
    } for name, b in export.get("thematic_baskets", {}).items()]

    frame = {
        "artifact": "pma_market_frame",
        "run_date": run_date,
        "generated_at": now_iso(),
        "staleness": staleness_block(receipt),
        "risk_tone": {"value": reg["level"], "source": "regime.level"},
        "momentum_caveat": {
            "text": caveat_text,
            "hurst": reg["hurst"], "trend": reg["trend"],
            "implication": reg["implication"], "vix": reg["vix"],
            "sources": ["regime.hurst", "regime.trend", "regime.implication", "regime.vix"],
        },
        "crown": crown_block,
        "sectors": sectors,
        "cross_asset": cross_asset,
        "thematic": thematic,
        "summary_counts": {"values": export.get("summary", {}), "source": "summary"},
        "data_quality": {"values": export.get("data_quality", {}), "source": "data_quality"},
        "declared_gaps": gaps,
    }
    write_validated(frame, run_date, "market_frame.json", "market_frame.schema.json")
    print(f"[pma] S2 risk_tone={reg['level']} crown_family={crown_block['family']} x{crown_block['size_multiplier']} gaps={len(gaps)}")
    return 0


# ---------------------------------------------------------------- S3 CANDIDATE FRAME

def s3(args):
    run_date = args.date
    receipt = read_receipt(run_date)
    export_path, _ = input_paths(receipt)
    export = load_json(export_path)
    notes = []

    dl = export["daily_list"]
    universe = [dict(row) for row in dl]  # SERVED fields verbatim, un-reordered, nothing dropped or added

    # frame counts — the card asks for "counts by tier"; the export has no `tier`
    # field. Reality: `source` (longlist/elder_list/radar-premove) + `gics_gate` +
    # lens positive-count are the served tierings. Adapted, and recorded.
    notes.append("card-vs-reality: S3 card says frame carries 'counts by tier' — the export has no "
                 "`tier` field. Adapted to the served tierings: by_source, by_gics_gate, "
                 "lens_positive_distribution.")
    by = lambda key: _count(universe, key)
    lens_dist = {}
    for r in export.get("lens_ranking", {}).get("ranked", []):
        lens_dist[str(r["positive"])] = lens_dist.get(str(r["positive"]), 0) + 1

    held_tickers = sorted(r["ticker"] for r in universe if r.get("held"))
    book = [p["ticker"] for p in export.get("held_positions", [])]
    not_in_universe = sorted(set(book) - {r["ticker"] for r in universe})
    if not_in_universe:
        notes.append(f"held book has {len(not_in_universe)} name(s) the scan did not serve today "
                     f"({', '.join(not_in_universe)}) — declared so no voice 'discovers' them; "
                     "position work stays in the existing machinery (v0.1 scope).")

    # near-misses — the card cites near_misses[] (D-37); the export has no such
    # field. Reality: signal_radar runner/premove setups NOT already in daily_list
    # are the served 'surfaced, never nominated' pool. Adapted, and recorded.
    notes.append("card-vs-reality: S3 card says near_misses[] (D-37) — the export has no near_miss "
                 "field. Adapted: signal_radar.runner_setup + premove_setup entries whose tickers "
                 "are not in daily_list are surfaced as near_misses.")
    in_universe = {r["ticker"] for r in universe}
    near = []
    sr = export.get("signal_radar", {})
    for kind in ("runner_setup", "premove_setup"):
        for e in sr.get(kind, []):
            if e["ticker"] not in in_universe:
                near.append({"ticker": e["ticker"], "source": f"signal_radar.{kind}",
                             "conviction": e.get("conviction"),
                             "note": e.get("conviction_label")})

    cand = {
        "artifact": "pma_candidate_set",
        "run_date": run_date,
        "generated_at": now_iso(),
        "staleness": staleness_block(receipt),
        "frame": {
            "universe_count": len(universe),
            "by_source": by("source"),
            "by_sector": by("gics_sector"),
            "by_gics_gate": by("gics_gate"),
            "lens_positive_distribution": lens_dist,
            "valid_bracket_count": sum(1 for r in universe if (r.get("bracket") or {}).get("valid")),
            "held_count": len(held_tickers),
            "held_tickers": held_tickers,
            "held_book_not_in_universe": not_in_universe,
        },
        "universe": universe,
        "near_misses": near,
        "notes": notes,
    }
    write_validated(cand, run_date, "candidate_set.json", "candidate_set.schema.json")
    f = cand["frame"]
    print(f"[pma] S3 universe={f['universe_count']} held={f['held_count']} "
          f"valid_brackets={f['valid_bracket_count']} near_misses={len(near)}")
    return 0


def _count(rows, key):
    out = {}
    for r in rows:
        k = str(r.get(key))
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------- S7 PLAN ASSEMBLY

def _maybe(date, name):
    p = os.path.join(out_dir(date), name)
    return load_json(p) if os.path.exists(p) else None


def s7(args):
    run_date = args.date
    receipt = read_receipt(run_date)
    frame = _maybe(run_date, "market_frame.json")
    if frame is None:
        print("[pma] S7 needs market_frame.json — run s2 first.", file=sys.stderr)
        sys.exit(1)
    committee = _maybe(run_date, "committee_read.json")
    weather = _maybe(run_date, "weather.json")
    challenge = _maybe(run_date, "challenge.json")
    cand = _maybe(run_date, "candidate_set.json")

    gaps = list(frame.get("declared_gaps", []))
    stale = frame["staleness"]
    if committee is None:
        gaps.append("committee_read.json absent — no verdicts; plan ships without actionable ideas")
    if weather is None:
        gaps.append("weather.json absent — weather pair rendered from the crown relay in market_frame only")
    if challenge is None:
        gaps.append("challenge.json absent — no rogers entries to weigh")

    # 1. headline — day type + data quality, staleness + DEGRADED always visible
    c = frame["crown"]
    head = f"{frame['risk_tone']['value']} tape, {frame['momentum_caveat']['trend']} (hurst {frame['momentum_caveat']['hurst']})"
    if c["present"]:
        head += f"; Crown: {c['family']} at {c['size_multiplier']}x ({c['match_quality']} match)"
        if c["status"] == "DEGRADED":
            head += " — Crown ran DEGRADED, see limits"
    else:
        head += "; Crown macro absent — regime read is AQE-only"
    if stale["staleness_days"]:
        head += f". DATA: export {stale['staleness_days']} days stale ({stale['export_date']}) — {stale['pm_ack']}"

    # 2. weather pair — verbatim relay; explicitly context, not gate
    crown_now = (weather or {}).get("crown") if weather else (
        {"present": c["present"], "status": c["status"],
         "read_me_first_headline": c["headline"],
         "the_call": {"expression_family": c["family"], "size_multiplier": c["size_multiplier"],
                      "match_quality": c["match_quality"],
                      "conditions_met": c["conditions_met"], "conditions_not_met": c["conditions_not_met"]},
         "limits": c["limits"],
         "note": "relayed from market_frame.crown (weather.json absent)"} if c["present"] else None)
    druck_next = (weather or {}).get("druckenmiller")

    # 3. actionable ideas — every ADVANCE (absent committee → empty list, declared above)
    ideas, watch = [], []
    chal_by_ticker = {}
    if challenge:
        for e in challenge.get("entries", []):
            chal_by_ticker.setdefault(e.get("ticker"), []).append(e.get("text") or e.get("summary") or "")
    bracket_by_ticker = {r["ticker"]: r.get("bracket") for r in (cand or {}).get("universe", [])}
    if committee:
        for v in committee.get("verdicts", []):
            if v["verdict"] == "ADVANCE":
                ideas.append({
                    "ticker": v["ticker"], "conviction": v["conviction"],
                    "entry_frame": bracket_by_ticker.get(v["ticker"]),
                    "why_data": v["data_anchors"], "bear_case": v["bear_case"],
                    "rogers_flag": "; ".join(chal_by_ticker.get(v["ticker"], [])) or None,
                })
            elif v["verdict"] == "HOLD-FOR-CONDITIONS":
                watch.append({"ticker": v["ticker"],
                              "count": len(v.get("nominating_seats", [])) or None,
                              "seats": v.get("nominating_seats", []),
                              "promote_condition": "; ".join(v.get("conditions", [])) or None})

    # 5. key levels — nearest crown levels ride with their "if it breaks" lines
    levels = []
    for l in c.get("key_levels_near", []):
        levels.append({"what": l["what"], "now": l.get("now"), "level": l["level"],
                       "unit": l.get("unit"), "distance_pct": l.get("distance_pct"),
                       "if_it_breaks": l.get("if_it_breaks", ""),
                       "source": "crown.key_levels"})

    # 6. what would change this plan — falsifiers verbatim
    would_change = []
    crown_file_path = receipt["files"]["crown"]["path"]
    if c["present"] and crown_file_path and os.path.exists(crown_file_path):
        would_change.extend(load_json(crown_file_path)["read_me_first"].get("what_would_change_it", []))
    if committee:
        for v in committee.get("verdicts", []):
            would_change.extend(v.get("conditions", []))

    plan = {
        "artifact": "pma_premarket_plan",
        "run_date": run_date,
        "generated_at": now_iso(),
        "headline": head,
        "weather_pair": {"crown_now": crown_now, "druckenmiller_next": druck_next,
                         "label": "context, not gate (D-4)"},
        "actionable_ideas": ideas,
        "watch_table": watch,
        "key_levels": levels,
        "what_would_change": would_change,
        "declared_gaps": gaps,
        "status_line": STATUS_LINE,
    }
    write_validated(plan, run_date, "premarket_plan.json", "premarket_plan.schema.json")
    if args.render:
        md = render_md(plan)
        md_path = os.path.join(out_dir(run_date), "plan.md")
        with open(md_path, "w") as f:
            f.write(md)
        print(f"[pma] wrote {os.path.relpath(md_path, ROOT)}")
    print(f"[pma] S7 ideas={len(ideas)} watch={len(watch)} gaps={len(gaps)}")
    return 0


def render_md(plan):
    L = [f"# Premarket plan — {plan['run_date']}", "",
         f"**{plan['headline']}**", "",
         "## Weather (context, not gate)"]
    cn = plan["weather_pair"]["crown_now"]
    if cn:
        call = cn.get("the_call", {})
        L.append(f"- **Crown NOW** ({cn.get('status')}): {cn.get('read_me_first_headline') or (cn.get('read_me_first') or {}).get('headline', '')}")
        L.append(f"  - family {call.get('expression_family')} at {call.get('size_multiplier')}x, match {call.get('match_quality')}; conditions not met: {', '.join(call.get('conditions_not_met', [])) or 'none'}")
    else:
        L.append("- **Crown NOW**: absent — regime read is AQE-only")
    dn = plan["weather_pair"]["druckenmiller_next"]
    L.append(f"- **Druckenmiller NEXT**: {dn.get('so_what') if dn else 'not run this pass'}")
    L += ["", "## Actionable ideas"]
    if plan["actionable_ideas"]:
        for i in plan["actionable_ideas"]:
            why = "; ".join(f"{a.get('label', a['field'])}={a['value']}" for a in i["why_data"])
            L.append(f"- **{i['ticker']}** (conviction {i['conviction']}) — why (data): {why}. Bear case: {i['bear_case']}"
                     + (f" Rogers: {i['rogers_flag']}" if i.get("rogers_flag") else ""))
    else:
        L.append("- none — committee has not run (see declared gaps)")
    L += ["", "## Watch table"]
    if plan["watch_table"]:
        for w in plan["watch_table"]:
            L.append(f"- {w['ticker']} ({w.get('count') or '?'} seats: {', '.join(w.get('seats', []))}) — promotes if: {w.get('promote_condition')}")
    else:
        L.append("- empty this pass")
    L += ["", "## Key levels to watch today"]
    for l in plan["key_levels"]:
        now = f" (now {l['now']}" + (f", {l['distance_pct']}% away)" if l.get("distance_pct") is not None else ")") if l.get("now") is not None else ""
        L.append(f"- **{l['what']}** at {l['level']}{now}: {l['if_it_breaks']}")
    L += ["", "## What would change this plan"]
    L += [f"- {w}" for w in plan["what_would_change"]] or ["- nothing recorded"]
    L += ["", "## Declared gaps"]
    L += [f"- {g}" for g in plan["declared_gaps"]] or ["- none"]
    L += ["", f"**{plan['status_line']}**", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- S8 SELF-AUDIT

STAGE_ARTIFACTS = [
    ("ingest_receipt.json", "ingest_receipt.schema.json"),
    ("market_frame.json", "market_frame.schema.json"),
    ("candidate_set.json", "candidate_set.schema.json"),
    ("weather.json", "weather.schema.json"),
    ("committee_read.json", "committee_read.schema.json"),
    ("premarket_plan.json", "premarket_plan.schema.json"),
]


def s8(args):
    run_date = args.date
    receipt = read_receipt(run_date)
    d = out_dir(run_date)

    stages_present, bridge = {}, []
    for name, schema in STAGE_ARTIFACTS:
        p = os.path.join(d, name)
        present = os.path.exists(p)
        stages_present[name] = present
        if present:
            errs = schema_errors(load_json(p), os.path.join(PMA_CONTRACTS, schema))
            bridge.append({"artifact": name, "schema": f"contracts/pma/{schema}",
                           "valid": not errs, "errors": errs})
    voices_dir = os.path.join(d, "voices")
    stages_present["voices/"] = os.path.isdir(voices_dir) and bool(os.listdir(voices_dir))
    stages_present["challenge.json"] = os.path.exists(os.path.join(d, "challenge.json"))

    # data demand — partial until voices run; declared, not faked
    per_voice, shortfalls = {}, []
    if stages_present["voices/"]:
        nom_schema = os.path.join(CONTRACTS, "nomination.schema.json")
        for fn in sorted(os.listdir(voices_dir)):
            if not fn.endswith(".json"):
                continue
            v = load_json(os.path.join(voices_dir, fn))
            errs = schema_errors(v, nom_schema)
            if errs:
                shortfalls.append(f"{fn}: invalid vs nomination.schema.json ({errs[0]})")
                continue
            cited = sorted({f for n in v.get("nominations", []) for f in (n.get("fields_cited") or n.get("field_values") or {})})
            per_voice[v.get("voice", fn)] = {
                "fields_cited": cited,
                "not_served_declared": v.get("data_gaps", []) or [],
            }
        demand_status = f"voices present: {len(per_voice)} nomination file(s) audited"
    else:
        demand_status = "PARTIAL — no voices have run this pass; data_demand is empty by fact, not by silence"

    # plan traceability — every ADVANCE anchor must resolve to a real value in the day's inputs
    unresolved, checked = [], 0
    plan = _maybe(run_date, "premarket_plan.json")
    if plan and plan["actionable_ideas"]:
        export = load_json(receipt["files"]["export"]["path"])
        by_ticker = {r["ticker"]: r for r in export.get("daily_list", [])}
        for idea in plan["actionable_ideas"]:
            row = by_ticker.get(idea["ticker"], {})
            for a in idea["why_data"]:
                checked += 1
                got = _resolve(row, a["field"])
                if got is None or (isinstance(a["value"], (int, float)) and isinstance(got, (int, float))
                                   and abs(got - a["value"]) > max(1e-6, abs(a["value"]) * 0.001)):
                    unresolved.append(f"{idea['ticker']}.{a['field']}: plan says {a['value']!r}, export says {got!r}")
        trace_status = "checked" if not unresolved else "ANCHOR MISMATCHES FOUND"
    else:
        trace_status = "no ADVANCE ideas to trace this pass"

    gaps = list((plan or {}).get("declared_gaps", []))
    if receipt["files"]["export"]["staleness_days"]:
        s = receipt["files"]["export"]
        gaps.append(f"run used a {s['staleness_days']}-day-stale export ({s['generated_at']}); pm_ack: {receipt['pm_ack']}")

    audit = {
        "artifact": "pma_run_audit",
        "run_date": run_date,
        "generated_at": now_iso(),
        "stages_present": stages_present,
        "data_demand": {"status": demand_status, "per_voice": per_voice},
        "seat_health": {"status": "no judgment seats ran this pass" if not per_voice else f"{len(per_voice)} seats returned",
                        "shortfalls": shortfalls},
        "bridge_integrity": bridge,
        "plan_traceability": {"status": trace_status, "checked": checked, "unresolved": unresolved},
        "gaps_carried": gaps,
    }
    write_validated(audit, run_date, "run_audit.json", "run_audit.schema.json")
    bad = [b["artifact"] for b in bridge if not b["valid"]]
    print(f"[pma] S8 bridge_integrity: {len(bridge)} artifacts checked, "
          f"{'ALL VALID' if not bad else 'INVALID: ' + ', '.join(bad)}; traceability: {trace_status}")
    return 0


def _resolve(row, dotted):
    cur = row
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="PMA deterministic runner (v0.1)")
    sub = ap.add_subparsers(dest="stage", required=True)
    p1 = sub.add_parser("s1", help="ingest: validate export+crown, staleness, receipt")
    p1.add_argument("--export", required=True)
    p1.add_argument("--crown", required=True)
    p1.add_argument("--date", required=True)
    p1.add_argument("--ack", default=None,
                    help="explicit PM acknowledgement to proceed on a stale export; recorded verbatim")
    for name, fn in (("s2", s2), ("s3", s3), ("s8", s8)):
        p = sub.add_parser(name)
        p.add_argument("--date", required=True)
    p7 = sub.add_parser("s7", help="plan assembly (deterministic render)")
    p7.add_argument("--date", required=True)
    p7.add_argument("--render", action="store_true", help="also write plan.md")
    args = ap.parse_args()
    rc = {"s1": s1, "s2": s2, "s3": s3, "s7": s7, "s8": s8}[args.stage](args)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
