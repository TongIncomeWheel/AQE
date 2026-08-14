#!/usr/bin/env python3
"""
alert_list.py — the DAILY AQE ALERT LONGLIST amalgamator (D-82).

WHAT THIS IS (the locked D-82 design):
  Universe -> AQE Scoreboard -> fork THREE lists -> amalgamate into ONE daily
  AQE alert longlist that the AQE engine monitors intraday (every 30 min) and the
  market-hours agent sweeps to request committee deliberation.

    List A = top 50 by tier, Data+Detect lens  = the EXISTING casting mat
             (tools/alert_universe.py). REUSED here, NOT reimplemented.
    List B = strongest 5-day Elder, top 15      = NEW (thin) — this file.
    List C = up to 10 ideas per committee voice  = the EXISTING voice nominations
             (data/sod/DATE/nominations/<voice>.json). READ-ONLY reuse — these
             already feed committee and MUST remain completely intact.
    List P = the Pipeline Ledger's active `trigger_silent` rows (D-83) = names a
             previous committee PARKED on a stated condition. READ-ONLY reuse of
             data/persistent/pipeline_ledger.json. A parked name is not in today's
             plan and usually not strong enough for A/B, so without List P its
             condition could only be noticed by post-market's end-of-day sweep — a
             full session late. Each P entry carries its trigger and case snapshot.

  The amalgam A u B u C u P is the daily alert longlist.

ANTI-SPAGHETTI (handoff/08 doctrine): this REUSES existing outputs. It does NOT
re-screen FMP, does NOT re-implement the 8-lane casting mat, does NOT re-run the
voices. List A is alert_universe.from_export verbatim; List C is a read-only union
of the nomination files the committee already produced. No order/execution path is
touched (constitution law 1). Deterministic, no model, no network (law 4).

TWO ARTIFACTS written by build():
  (a) data/alerts/DATE/alert_list.json   — the intraday longlist AQE monitors
       {date, source, counts:{A,B,C,total_unique}, entries:[...], elder_field_used}
  (b) data/sod/DATE/premarket_review.json — the List C review store (the full
       per-voice nominations union, "up to 10 ideas per voice").

ELDER GAP (real, documented): the AQE export SHOULD ship `elder_5d` populated;
when it is null/empty for every name, List B FALLS BACK to the `elder` composite
and records which field it used ("elder_5d" | "elder(fallback)") in the output.
`elder_5d` may ship either as a scalar or as a 5-element daily series; a series is
reduced to its mean (the 5-day Elder strength) for ranking.

Usage:
  python3 tools/alert_list.py build --export output/aqe_daily_export.json \
      --nominations-dir data/sod/2026-07-21/nominations [--out <path>]
  python3 tools/alert_list.py selftest
"""
import json
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alert_universe  # noqa: E402  — List A source (the EXISTING casting mat). REUSE, do not reimplement.

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PARAMS_PATH = os.path.join(os.path.dirname(__file__), "..", "charter", "parameters.yaml")

# Fallback defaults (mirror charter/parameters.yaml -> alert_list.*). parameters.yaml wins.
DEFAULTS = {
    "list_a_top": 50,
    "list_b_elder_top": 15,
    "list_c_per_voice": 10,
    "breakout_pct": 2.0,
    "intraday_cadence_min": 30,
}


def _num(v, dv=None):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else dv


def load_params():
    """Overlay charter/parameters.yaml -> alert_list.* on DEFAULTS (deterministic fallback)."""
    p = dict(DEFAULTS)
    try:
        import yaml
        with open(_PARAMS_PATH) as fh:
            doc = yaml.safe_load(fh) or {}
        block = doc.get("alert_list", {}) or {}
        for k in p:
            v = block.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                p[k] = v
    except Exception:
        pass
    return p


# --------------------------------------------------------------------------- List A
def list_a(export_path, top=50, params=None, event_blocked=None):
    """List A = the EXISTING casting mat (tools/alert_universe.from_export), flattened
    across all tiers and cut to the top `top` by (tier asc, lane_count desc, sc_momentum desc).
    Each row keeps ticker, sc_momentum, tier, lane_count, lanes_fired."""
    u = alert_universe.from_export(export_path, params=params, event_blocked=event_blocked)
    members = (u.get("tier1_priority", []) + u.get("tier2_confirmed", [])
               + u.get("tier3_watch", []))
    members = sorted(members, key=lambda m: (m.get("tier", 9),
                                             -_num(m.get("lane_count"), 0),
                                             -_num(m.get("sc_momentum"), 0),
                                             m.get("ticker", "")))
    rows = [{
        "ticker": m.get("ticker"),
        "sc_momentum": m.get("sc_momentum"),
        "tier": m.get("tier"),
        "lane_count": m.get("lane_count"),
        "lanes_fired": m.get("lanes_fired", []),
    } for m in members[:top]]
    return rows


# --------------------------------------------------------------------------- List B
def _elder5d_value(rec):
    """Reduce elder_5d to a scalar 5-day Elder strength. A 5-element daily series ->
    its mean; a bare number -> itself; anything else (null/empty) -> None (the gap)."""
    v = rec.get("elder_5d")
    if isinstance(v, (list, tuple)):
        nums = [x for x in v if isinstance(x, (int, float)) and not isinstance(x, bool)]
        return sum(nums) / len(nums) if nums else None
    return _num(v, None)


def list_b(daily_list, top=15):
    """List B = strongest 5-day Elder, top `top`. Ranks by elder_5d DESC; if elder_5d
    is null/empty for EVERY name, FALLS BACK to the `elder` composite and records which
    field was used. Each row keeps ticker, the elder value, elder_rank.

    Returns (rows, elder_field_used)."""
    have_5d = any(_elder5d_value(r) is not None for r in daily_list)
    if have_5d:
        field, valfn = "elder_5d", _elder5d_value
    else:
        field, valfn = "elder(fallback)", (lambda r: _num(r.get("elder"), None))
    scored = []
    for r in daily_list:
        t = r.get("ticker")
        val = valfn(r)
        if t is None or val is None:
            continue
        scored.append((t, val))
    # deterministic: value DESC, ticker ASC on ties
    scored.sort(key=lambda x: (-x[1], x[0]))
    rows = [{"ticker": t, "elder_value": round(val, 2), "elder_rank": i + 1}
            for i, (t, val) in enumerate(scored[:top])]
    return rows, field


# --------------------------------------------------------------------------- List C
def list_c(nominations_dir, per_voice=10):
    """List C = the EXISTING voice nominations (READ-ONLY). Reads every <voice>.json,
    takes up to `per_voice` nominations per voice, and amalgamates per ticker into
    {ticker, voices:[...], max_conviction, reasons:[...]}.

    Returns (amalgam_rows, per_voice_raw) where per_voice_raw is the full union for the
    review store. NEVER writes to nominations_dir."""
    per_voice_raw = []
    by_ticker = {}
    for path in sorted(glob.glob(os.path.join(nominations_dir, "*.json"))):
        try:
            doc = json.load(open(path))
        except Exception:
            continue
        voice = doc.get("voice") or os.path.splitext(os.path.basename(path))[0]
        noms = (doc.get("nominations") or [])[:per_voice]
        per_voice_raw.append({"voice": voice, "date": doc.get("date"), "nominations": noms})
        for n in noms:
            t = n.get("ticker")
            if not t:
                continue
            conv = _num(n.get("conviction"), 0)
            e = by_ticker.setdefault(t, {"ticker": t, "voices": [], "max_conviction": 0,
                                         "reasons": []})
            if voice not in e["voices"]:
                e["voices"].append(voice)
            e["max_conviction"] = max(e["max_conviction"], conv)
            if n.get("reason"):
                e["reasons"].append({"voice": voice, "reason": n.get("reason"),
                                     "conviction": conv})
    amalgam = sorted(by_ticker.values(),
                     key=lambda e: (-e["max_conviction"], -len(e["voices"]), e["ticker"]))
    return amalgam, per_voice_raw


def list_p(ledger_path=None):
    """List P = the Pipeline Ledger's PARKED names (D-83) — active `trigger_silent`
    rows the committee asked to keep alive until a stated condition fires.

    Why they belong on the alert list at all: a parked name is by definition NOT in
    today's plan and usually not strong enough to make List A/B, so without this it
    would be invisible intraday and its condition could only ever be noticed by
    post-market's end-of-day sweep — a full session late. Membership here is what
    lets the market-hours sweep see it move in real time.

    READ-ONLY: never writes the ledger. An absent store is an empty list, not an
    error (a normal state before the first proposal). Rows carry their own trigger
    so the market-hours sweep can evaluate the condition, not just the bracket."""
    path = ledger_path or os.environ.get(
        "AEGIS_PIPELINE_LEDGER", os.path.join(ROOT, "data", "persistent", "pipeline_ledger.json"))
    try:
        doc = json.load(open(path))
    except Exception:
        return []
    rows = []
    for r in doc.get("rows", []) or []:
        if r.get("status") != "active" or r.get("classification") != "trigger_silent":
            continue
        t = str(r.get("ticker", "")).upper()
        if not t:
            continue
        rows.append({"ticker": t, "trigger": r.get("trigger"),
                     "case_snapshot": r.get("case_snapshot"),
                     "origin_date": r.get("origin_date")})
    rows.sort(key=lambda r: r["ticker"])
    return rows


# --------------------------------------------------------------------------- amalgamate
def _bracket_for(rec, breakout_pct):
    """Pull the alert bracket from the export record's `bracket`.
    prior_cob = bracket.price; breakout_level = round(prior_cob*(1+pct/100), 2)."""
    br = (rec.get("bracket") or {}) if rec else {}
    prior_cob = _num(br.get("price"), None)
    entry = br.get("entry", rec.get("entry") if rec else None)
    bracket_out = {
        "entry": entry,
        "stop": br.get("stop"),
        "targets": br.get("targets"),
        "prior_cob": prior_cob,
    }
    breakout_level = (round(prior_cob * (1 + breakout_pct / 100.0), 2)
                      if isinstance(prior_cob, (int, float)) else None)
    return bracket_out, breakout_level


def amalgamate(a_rows, b_rows, c_rows, export_index, breakout_pct=2.0, p_rows=None):
    """Union A u B u C u P by ticker. Each entry:
      {ticker, categories:[subset of A/B/C/P], why:{...for whichever fired},
       bracket:{entry, stop, targets, prior_cob}, breakout_level, sc_momentum}
    NO PTRS / subscores in the alert-list entry."""
    a_by = {r["ticker"]: r for r in a_rows}
    b_by = {r["ticker"]: r for r in b_rows}
    c_by = {r["ticker"]: r for r in c_rows}
    p_by = {r["ticker"]: r for r in (p_rows or [])}
    tickers = set(a_by) | set(b_by) | set(c_by) | set(p_by)

    entries = []
    for t in tickers:
        cats = []
        why = {}
        if t in a_by:
            cats.append("A")
            why["A"] = "tier%s, %s lanes" % (a_by[t].get("tier"), a_by[t].get("lane_count"))
        if t in b_by:
            cats.append("B")
            why["B"] = "elder %.1f (rank %s)" % (b_by[t]["elder_value"], b_by[t]["elder_rank"])
        if t in c_by:
            cats.append("C")
            why["C"] = "%s conv%s" % (",".join(c_by[t]["voices"]), c_by[t]["max_conviction"])
        if t in p_by:
            cats.append("P")
            tg = p_by[t].get("trigger") or {}
            why["P"] = "parked %s — fires on %s %s %s" % (
                p_by[t].get("origin_date"), tg.get("field"), tg.get("op"), tg.get("value"))

        rec = export_index.get(t, {})
        bracket_out, breakout_level = _bracket_for(rec, breakout_pct)
        scm = _num(rec.get("sc_momentum"), None)
        if scm is None and t in a_by:
            scm = a_by[t].get("sc_momentum")

        entry = {
            "ticker": t,
            "categories": cats,
            "why": why,
            "bracket": bracket_out,
            "breakout_level": breakout_level,
            "sc_momentum": scm,
        }
        # A parked name carries its condition and its case so the market-hours sweep
        # can check the actual trigger, not just the bracket, and so the pod that
        # wakes on it sees the case the committee made when it parked the name.
        if t in p_by:
            entry["pipeline"] = {"trigger": p_by[t].get("trigger"),
                                 "case_snapshot": p_by[t].get("case_snapshot"),
                                 "origin_date": p_by[t].get("origin_date")}
        entries.append(entry)

    # deterministic: multi-list first, then momentum, then ticker
    entries.sort(key=lambda e: (-len(e["categories"]), -_num(e["sc_momentum"], -1), e["ticker"]))
    return entries


# --------------------------------------------------------------------------- build
def build(export_path, nominations_dir, out=None, review_out=None, params=None,
          event_blocked=None, ledger_path=None):
    """Load the export + nominations, fork the three lists, amalgamate, and write BOTH
    artifacts. Returns the alert_list dict. DATE is reused from the export."""
    p = dict(load_params())
    if params:
        p.update({k: v for k, v in params.items() if v is not None})

    d = json.load(open(export_path))
    date = d.get("date")
    daily_list = d.get("daily_list", []) or []
    export_index = {r.get("ticker"): r for r in daily_list if r.get("ticker")}

    a_rows = list_a(export_path, top=int(p["list_a_top"]), event_blocked=event_blocked)
    b_rows, elder_field_used = list_b(daily_list, top=int(p["list_b_elder_top"]))
    c_rows, per_voice_raw = list_c(nominations_dir, per_voice=int(p["list_c_per_voice"]))
    p_rows = list_p(ledger_path)

    entries = amalgamate(a_rows, b_rows, c_rows, export_index,
                         breakout_pct=float(p["breakout_pct"]), p_rows=p_rows)

    # Event filter is GLOBAL (D-11): an event-driven name is struck from the ENTIRE alert
    # list, not just List A. List A (casting mat) already excludes event_blocked, but a
    # takeover/M&A pop could still re-enter the amalgam via List B (elder) or List C (a
    # voice that nominated it), so strike across all three here — visible, never silent.
    blocked = set(t.upper() for t in (event_blocked or []))
    struck = [e for e in entries if str(e.get("ticker", "")).upper() in blocked]
    for e in struck:
        e["struck_reason"] = "event-driven (blocked by event filter, D-11)"
    entries = [e for e in entries if str(e.get("ticker", "")).upper() not in blocked]

    alert_list_doc = {
        "date": date,
        "source": {
            "kind": "aqe_alert_longlist_v1",
            "export_path": export_path,
            "nominations_dir": nominations_dir,
            "recipe": {"A": "casting_mat top %d (tools/alert_universe.py)" % int(p["list_a_top"]),
                       "B": "strongest 5d elder top %d" % int(p["list_b_elder_top"]),
                       "C": "voice nominations, up to %d/voice (read-only)" % int(p["list_c_per_voice"]),
                       "P": "pipeline ledger active trigger_silent rows (read-only, D-83)"},
            "cadence_min": int(p["intraday_cadence_min"]),
        },
        "counts": {"A": len(a_rows), "B": len(b_rows), "C": len(c_rows), "P": len(p_rows),
                   "total_unique": len(entries), "struck_event": len(struck)},
        "entries": entries,
        "struck_event": struck,
        "elder_field_used": elder_field_used,
    }

    review_doc = {
        "date": date,
        "source": {"kind": "premarket_review_v1", "nominations_dir": nominations_dir,
                   "note": "List C store — full per-voice nominations union (up to %d ideas/voice). "
                           "READ-ONLY reuse of the committee's nomination files." % int(p["list_c_per_voice"])},
        "per_voice": per_voice_raw,
        "amalgam_by_ticker": c_rows,
    }

    # landing paths (DATE from the export). --out overrides the alert_list path; when it
    # does, the review lands beside it (keeps ad-hoc runs off the committed SOD tree).
    if out:
        out_path = out
    else:
        out_path = os.path.join("data", "alerts", str(date), "alert_list.json")
    if review_out:
        review_path = review_out
    elif out:
        review_path = os.path.join(os.path.dirname(os.path.abspath(out)), "premarket_review.json")
    else:
        review_path = os.path.join("data", "sod", str(date), "premarket_review.json")

    for path, doc in ((out_path, alert_list_doc), (review_path, review_doc)):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(doc, fh, indent=1)

    alert_list_doc["_written"] = {"alert_list": out_path, "premarket_review": review_path}
    return alert_list_doc


# --------------------------------------------------------------------------- selftest
def _selftest():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="alert_list_selftest_")

    # Inline export. AAA lands in A (tier1), B (elder), AND C (nominated) -> multi-category.
    # elder_5d is NULL on every record -> List B must FALL BACK to `elder`.
    export = {
        "date": "2026-07-21",
        "daily_list": [
            {"ticker": "AAA", "sc_momentum": 82.0, "sc_m_gates": True, "choch_state": "BULLISH",
             "knn_threshold_clear": True, "rs_leadership": "LEADER", "structure": 80.0, "flow": 80.0,
             "mp_accel_state": "FLAT", "elder_5d": None, "elder": 9.0, "entry": 100.0,
             "bracket": {"price": 100.0, "stop": 95.0,
                         "targets": [{"type": "prior_high", "price": 104.0}]}},
            {"ticker": "BBB", "sc_momentum": 74.0, "rs_leadership": "LEADER", "flow": 80.0,
             "mp_accel_state": "FLAT", "elder_5d": None, "elder": 8.0, "entry": 50.0,
             "bracket": {"price": 50.0, "stop": 47.0, "targets": []}},
            {"ticker": "CCC", "sc_momentum": 60.0, "elder_5d": None, "elder": 10.0,
             "bracket": {"price": 20.0, "stop": None, "targets": []}},
        ],
        "lens_ranking": {"ranked": [
            {"ticker": "AAA", "positive": 5}, {"ticker": "BBB", "positive": 1},
            {"ticker": "CCC", "positive": 0},
        ]},
    }
    export_path = os.path.join(tmp, "export.json")
    json.dump(export, open(export_path, "w"))

    # Inline nominations dir (List C). AAA nominated by two voices; DDD by one (C-only, no export rec).
    noms_dir = os.path.join(tmp, "nominations")
    os.makedirs(noms_dir)
    json.dump({"voice": "oneil", "date": "2026-07-21", "nominations": [
        {"ticker": "AAA", "reason": "leader", "conviction": 5},
        {"ticker": "DDD", "reason": "base", "conviction": 3}]},
        open(os.path.join(noms_dir, "oneil.json"), "w"))
    json.dump({"voice": "minervini", "date": "2026-07-21", "nominations": [
        {"ticker": "AAA", "reason": "vcp", "conviction": 4}]},
        open(os.path.join(noms_dir, "minervini.json"), "w"))

    out = os.path.join(tmp, "alert_list.json")
    doc = build(export_path, noms_dir, out=out)

    # A/B/C all populate
    assert doc["counts"]["A"] >= 1, doc["counts"]
    assert doc["counts"]["B"] >= 1, doc["counts"]
    assert doc["counts"]["C"] >= 1, doc["counts"]
    assert doc["counts"]["total_unique"] == len(doc["entries"])

    ents = {e["ticker"]: e for e in doc["entries"]}
    # AAA in >1 list carries multiple categories (all three here)
    assert set(ents["AAA"]["categories"]) == {"A", "B", "C"}, ents["AAA"]["categories"]
    assert "A" in ents["AAA"]["why"] and "B" in ents["AAA"]["why"] and "C" in ents["AAA"]["why"]
    # elder fallback fired (elder_5d null everywhere)
    assert doc["elder_field_used"] == "elder(fallback)", doc["elder_field_used"]
    # entries carry bracket + breakout_level (+2% over prior COB)
    assert ents["AAA"]["bracket"]["prior_cob"] == 100.0, ents["AAA"]["bracket"]
    assert ents["AAA"]["bracket"]["stop"] == 95.0
    assert ents["AAA"]["breakout_level"] == 102.0, ents["AAA"]["breakout_level"]
    # C-only ticker with no export record -> present, C category, null bracket
    assert "DDD" in ents and ents["DDD"]["categories"] == ["C"], ents.get("DDD")
    assert ents["DDD"]["bracket"]["prior_cob"] is None
    # NO PTRS / subscores leaked into the alert entry
    for e in doc["entries"]:
        assert "ptrs" not in e and "subcomponents" not in e, ("subscore leaked", e)
    # review store has per-voice ideas
    review_path = doc["_written"]["premarket_review"]
    review = json.load(open(review_path))
    voices = {v["voice"] for v in review["per_voice"]}
    assert voices == {"oneil", "minervini"}, voices
    assert any(len(v["nominations"]) >= 1 for v in review["per_voice"])
    # elder rank: CCC(10) > AAA(9) > BBB(8) on the fallback composite
    b_ranks = {e["ticker"]: e for e in doc["entries"]}
    assert b_ranks["CCC"]["why"]["B"].startswith("elder 10.0 (rank 1)"), b_ranks["CCC"]["why"]


    # --- List P (D-83): an active trigger_silent row joins the alert list, carrying its
    # condition and case; a fired/expired/closed row or a daily_reconsider row does NOT.
    import tempfile as _tf
    _t = _tf.mkdtemp()
    _lp = os.path.join(_t, "pipeline_ledger.json")
    json.dump({"rows": [
        {"ticker": "PPP", "status": "active", "classification": "trigger_silent",
         "trigger": {"field": "sc_momentum", "op": ">=", "value": 75},
         "case_snapshot": "spring held; wants momentum", "origin_date": "2026-07-20"},
        {"ticker": "QQQ", "status": "active", "classification": "daily_reconsider",
         "trigger": None, "case_snapshot": "base intact", "origin_date": "2026-07-20"},
        {"ticker": "RRR", "status": "expired", "classification": "trigger_silent",
         "trigger": {"field": "sc_momentum", "op": ">=", "value": 90},
         "case_snapshot": "stale", "origin_date": "2026-06-01"},
    ]}, open(_lp, "w"))
    prows = list_p(_lp)
    assert [r["ticker"] for r in prows] == ["PPP"], (
        "only ACTIVE trigger_silent rows join List P: %s" % prows)
    assert list_p(os.path.join(_t, "nope.json")) == [], "an absent ledger is an empty List P, not an error"
    pdoc = build(export_path, noms_dir, out=os.path.join(_t, "alert_list.json"), ledger_path=_lp)
    pents = {e["ticker"]: e for e in pdoc["entries"]}
    assert pdoc["counts"]["P"] == 1, pdoc["counts"]
    assert "P" in pents["PPP"]["categories"] and pents["PPP"]["pipeline"]["trigger"]["value"] == 75
    assert pents["PPP"]["pipeline"]["case_snapshot"] == "spring held; wants momentum"
    assert "QQQ" not in pents and "RRR" not in pents
    # a name already on A/B/C that is ALSO parked gains P, it does not duplicate
    assert len([e for e in pdoc["entries"] if e["ticker"] == "PPP"]) == 1

    print("alert_list.py selftest: PASS  (A/B/C populate; AAA multi-category A+B+C; "
          "List P takes active trigger_silent rows only and carries the trigger+case; "
          "elder fallback on null elder_5d; bracket+breakout_level present; review store per-voice)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Daily AQE alert longlist amalgamator (D-82, deterministic)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--export", required=True)
    b.add_argument("--nominations-dir", required=True)
    b.add_argument("--out", help="alert_list path (default data/alerts/DATE/alert_list.json); "
                                 "review lands beside it when set")
    b.add_argument("--review-out", help="override the premarket_review.json path")
    b.add_argument("--event-blocked", default="")
    b.add_argument("--ledger", help="pipeline_ledger.json path for List P "
                                   "(default data/persistent/pipeline_ledger.json)")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        _selftest()
        return
    blocked = [t.strip().upper() for t in a.event_blocked.split(",") if t.strip()]
    doc = build(a.export, a.nominations_dir, out=a.out, review_out=a.review_out,
                event_blocked=blocked or None, ledger_path=a.ledger)
    summary = {"date": doc["date"], "counts": doc["counts"],
               "elder_field_used": doc["elder_field_used"], "written": doc["_written"]}
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
