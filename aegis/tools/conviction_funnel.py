#!/usr/bin/env python3
"""
conviction_funnel.py — the premarket three-axis conviction funnel (D-78/D-79/D-80).

================================ SELECTION DOCTRINE (LOCKED, D-80) ================================
  DATA leads  ·  LENS seconds  ·  VOICES corroborate or challenge  →  consensus for HIGH CONVICTION.

  - DATA (the 8-lane casting mat, D-77) is the primary, mechanical signal of momentum arriving.
  - LENS (the 6-lens detect) is the second confirmer.
  - Data OR lens strong = a name enters the ~10-15 shortlist (the mechanically-confirmed set).
  - VOICES then CORROBORATE (nominate/add conviction), are SILENT (advisory), or CHALLENGE
    (dissent / bear case, or vote a name the mechanicals do NOT confirm).
  - HIGH CONVICTION = mechanical confirmation AND voice corroboration (the committee synthesis).
    A mechanically-strong name the voices challenge, or a voted name the mechanicals don't confirm,
    is a DELIBERATION item the committee must resolve (run or drop) — never an auto-advance.
  Voices corroborate or challenge; they never buy a seat on their own. Data leads.
==================================================================================================

Records the "lane methodology" into the DAILY PREMARKET run. The PM's mandate:
  "data driven, lens and consensus driven. Concise summary highlighting contradictory
   or positive overlaps that we can deepen deliberation. Always start from approx
   10-15 names to filter down into a high conviction plan."

It scores every nominated name on THREE independent axes and finds where they agree
(high conviction, fast-track) and where they disagree (deepen deliberation):

  CONSENSUS  — the voices: nomination count + average conviction (the swarm's vote)
  DATA       — the 8-lane casting mat (D-77): momentum-arrival depth (mechanical)
  LENS       — the 6-lens detect count (leadership/coil/insti/structure/resistance/sector)

Each axis is graded S(trong)/M(edium)/W(eak). A name strong on >=2 axes enters the
CONVERGENCE SHORTLIST (targets ~10-15 names) that carries into deep deliberation.
Names that are strong on ONE axis but contradicted by the others are surfaced
separately as CONTRADICTIONS TO RESOLVE — the committee must explicitly rule on them:
  - consensus_only : voted well but the data/lens do not confirm (fresh, or stale? e.g. DINO)
  - data_lens_only : mechanically/lens strong but the swarm under-nominated (a missed runner?)

Deterministic (law 4). Reuses the D-77 lane definition and the D-60 divergence idea;
adds nothing to the render layer. Thresholds in parameters.yaml -> conviction_funnel.

Usage:
  python3 tools/conviction_funnel.py build --tally data/sod/DATE/tally.json \
      --export output/aqe_daily_export.json [--out data/sod/DATE/conviction_funnel.json]
  python3 tools/conviction_funnel.py selftest
"""
import json
import argparse

DEFAULTS = {
    "target_min": 10, "target_max": 15,
    "cons_strong_votes": 3, "cons_med_votes": 2,       # consensus grade cutoffs
    "data_strong_lanes": 5, "data_med_lanes": 3,       # DATA (lane) grade cutoffs
    "lens_strong": 4, "lens_med": 2,                   # LENS (detect) grade cutoffs
    "lane_structure": 72, "lane_flow": 68, "lane_detect": 4,
    "contradiction_consensus_min_votes": 3,            # a "consensus-only" tension needs real votes
    "data_lens_only_cap": 6,                           # cap the missed-runner list
}


def _num(v, dv=0):
    return v if isinstance(v, (int, float)) else dv


def _lane_count(rec, detect_positive, p):
    return sum([
        rec.get("sc_m_gates") is True,
        rec.get("choch_state") == "BULLISH",
        rec.get("knn_significant") is True,
        _num(detect_positive) >= p["lane_detect"],
        rec.get("rs_leadership") == "LEADER",
        _num(rec.get("structure")) >= p["lane_structure"],
        _num(rec.get("flow")) >= p["lane_flow"],
        rec.get("mp_accel_state") in ("ACCELERATING", "BUILDING", "FLAT"),
    ])


def _grade(val, strong, med):
    return "S" if val >= strong else ("M" if val >= med else "W")


def build(tally, daily_list, lens_positive, params=None, event_blocked=None):
    """Pure function. tally: {ticker: {count, convictions{voice:conv}, ...}}.
    daily_list: AQE records. lens_positive: {ticker:int}. Returns the funnel dict."""
    p = dict(DEFAULTS)
    if params:
        p.update({k: v for k, v in params.items() if v is not None})
    blocked = set(t.upper() for t in (event_blocked or []))
    idx = {r.get("ticker"): r for r in daily_list}

    scored = []
    for t, info in tally.items():
        if t in blocked:
            continue
        r = idx.get(t)
        if not r:
            continue
        votes = _num(info.get("count"))
        convs = list((info.get("convictions") or {}).values())
        avg_conv = round(sum(convs) / len(convs), 1) if convs else 0.0
        lanes = _lane_count(r, lens_positive.get(t, 0), p)
        detect = _num(lens_positive.get(t, 0))
        gc = _grade(votes, p["cons_strong_votes"], p["cons_med_votes"])
        gd = _grade(lanes, p["data_strong_lanes"], p["data_med_lanes"])
        gl = _grade(detect, p["lens_strong"], p["lens_med"])
        n_strong = sum(x == "S" for x in (gc, gd, gl))
        scored.append({
            "ticker": t, "votes": votes, "avg_conviction": avg_conv,
            "lane_count": lanes, "detect": detect, "sc_momentum": _num(r.get("sc_momentum")),
            "ext_pct": _num(r.get("sma_distance_pct")), "sector": r.get("gics_sector_name"),
            "axes": {"consensus": gc, "data": gd, "lens": gl}, "n_strong": n_strong,
            "profile": f"{gc}/{gd}/{gl}",
        })

    # CONVERGENCE SHORTLIST — DATA + LENS FIRST, consensus ADVISORY (D-79, PM: "data but
    # lens first before we anchor on voices advisory"). The PRIMARY membership test is the
    # MECHANICAL one: a name is a candidate iff DATA is strong OR LENS is strong. The voices
    # (consensus) are then an OVERLAY on top — they CONFIRM (voted too) or are ADVISORY-SILENT
    # (data/lens say go, the swarm did not nominate) — never the entry ticket.
    primary = [s for s in scored if s["axes"]["data"] == "S" or s["axes"]["lens"] == "S"]
    # rank by mechanical strength first (lanes+detect), consensus only as a tiebreak/advisory.
    primary.sort(key=lambda s: (-(s["lane_count"] + s["detect"]), -s["lane_count"], -s["votes"]))
    shortlist = primary[:p["target_max"]]
    for s in shortlist:
        confirmed = s["votes"] >= p["cons_med_votes"]
        s["consensus_read"] = "CONFIRMED" if confirmed else "advisory-silent"
        if s["n_strong"] == 3:
            s["class"] = "TRIPLE"                       # data + lens + voices all agree
        elif confirmed:
            s["class"] = "CONFIRMED"                    # data/lens-led AND the swarm backed it
        else:
            s["class"] = "DATA_LED"                     # data/lens-led, voices advisory-silent (promoted anyway)
        s["mech"] = "+".join([ax for ax in ("data", "lens") if s["axes"][ax] == "S"])

    # CONTRADICTION — voted well but the MECHANICALS do not confirm. These are NOT in the
    # data/lens-first shortlist (voices are advisory, not the anchor); they are surfaced for the
    # committee to explicitly rule on: fresh, or stale/extended? (e.g. DINO 4 votes / 2 lanes).
    consensus_only = sorted(
        [s for s in scored if s["votes"] >= p["contradiction_consensus_min_votes"]
         and s["axes"]["data"] != "S" and s["axes"]["lens"] != "S"],
        key=lambda s: (-s["votes"], s["lane_count"]))
    for s in consensus_only:
        s["tension"] = ("voted by %d but only %d/8 lanes, %d/6 lens — voices advisory only; "
                        "fresh, or stale/extended? committee must rule (run or drop)"
                        % (s["votes"], s["lane_count"], s["detect"]))
    # The former 'data_lens_only missed-runner' set is now PROMOTED into the shortlist as
    # DATA_LED entries (data leads, voices advisory). Keep an empty list for schema stability.
    data_lens_only = []

    return {
        "recipe": "conviction_funnel_v1",
        "params": p,
        "axes_legend": {"CONSENSUS": "voices: nomination count + avg conviction",
                        "DATA": "8-lane casting mat (D-77) momentum-arrival depth",
                        "LENS": "6-lens detect count"},
        "counts": {"nominated_scored": len(scored), "shortlist": len(shortlist),
                   "consensus_only_contradictions": len(consensus_only),
                   "data_lens_only_contradictions": len(data_lens_only)},
        "convergence_shortlist": shortlist,
        "contradictions": {"consensus_only": consensus_only, "data_lens_only": data_lens_only},
        "summary": _summary(shortlist, consensus_only, data_lens_only),
    }


def _summary(shortlist, cons_only, data_only):
    triples = [s["ticker"] for s in shortlist if s.get("class") == "TRIPLE"]
    confirmed = [s["ticker"] for s in shortlist if s.get("class") == "CONFIRMED"]
    data_led = [s["ticker"] for s in shortlist if s.get("class") == "DATA_LED"]
    lines = []
    lines.append("SHORTLIST is DATA+LENS-first, voices advisory (D-79).")
    if triples:
        lines.append("TRIPLE (data+lens+voices agree — highest): " + ", ".join(triples))
    if confirmed:
        lines.append("CONFIRMED (data/lens-led, swarm backed): " + ", ".join(confirmed))
    if data_led:
        lines.append("DATA-LED, voices advisory-silent (mechanically strong, swarm under-nominated — deliberate): "
                     + ", ".join(data_led))
    if cons_only:
        lines.append("CONTRADICTION — voted but mechanicals do NOT confirm (voices advisory only; run or drop?): "
                     + ", ".join("%s(%dv,%d lanes)" % (s["ticker"], s["votes"], s["lane_count"]) for s in cons_only))
    lines.append("Deliberate the %d shortlist names; explicitly RESOLVE each contradiction." % len(shortlist))
    return " | ".join(lines)


def from_files(tally_path, export_path, params=None, event_blocked=None):
    tally = json.load(open(tally_path)).get("tally", {})
    d = json.load(open(export_path))
    lens = {x.get("ticker"): x.get("positive", 0)
            for x in (d.get("lens_ranking", {}) or {}).get("ranked", []) if isinstance(x, dict)}
    return build(tally, d.get("daily_list", []), lens, params=params, event_blocked=event_blocked)


def _selftest():
    dl = [
        {"ticker": "SHO", "sc_momentum": 68.1, "sc_m_gates": False, "choch_state": "BULLISH", "knn_significant": True,
         "rs_leadership": "LEADER", "structure": 60, "flow": 70, "mp_accel_state": "BUILDING", "sma_distance_pct": 5},
        {"ticker": "DINO", "sc_momentum": 79.7, "sc_m_gates": False, "choch_state": "RANGE", "knn_significant": False,
         "rs_leadership": "LEADER", "structure": 68, "flow": 90, "mp_accel_state": "DECELERATING", "sma_distance_pct": 25},
        {"ticker": "DJT", "sc_momentum": 75.2, "sc_m_gates": True, "choch_state": "BULLISH", "knn_significant": True,
         "rs_leadership": "LEADER", "structure": 80, "flow": 80, "mp_accel_state": "FLAT", "sma_distance_pct": 15},
    ]
    lens = {"SHO": 5, "DINO": 1, "DJT": 1}
    tally = {"SHO": {"count": 3, "convictions": {"a": 4, "b": 4, "c": 4}},
             "DINO": {"count": 4, "convictions": {"a": 4, "b": 4, "c": 3, "d": 5}},
             "DJT": {"count": 1, "convictions": {"a": 3}}}
    f = build(tally, dl, lens)
    sl = {s["ticker"]: s for s in f["convergence_shortlist"]}
    # D-79: data+lens FIRST, voices advisory.
    assert "SHO" in sl and sl["SHO"]["class"] == "TRIPLE", "SHO (all 3 strong) must be TRIPLE in shortlist"
    # DJT is data-strong but only 1 vote -> now PROMOTED into the shortlist as DATA_LED (voices advisory-silent).
    assert "DJT" in sl and sl["DJT"]["class"] == "DATA_LED", "DJT must be DATA_LED in the shortlist (data leads, voices advisory)"
    assert sl["DJT"]["consensus_read"] == "advisory-silent", "DJT consensus must read advisory-silent"
    # DINO is voted (4) but mechanically weak (data W, lens W) -> NOT in shortlist; a consensus-only contradiction.
    assert "DINO" not in sl, "DINO (voted but data/lens weak) must NOT enter the data-first shortlist"
    assert any(s["ticker"] == "DINO" for s in f["contradictions"]["consensus_only"]), "DINO must be a consensus-only contradiction"
    print("conviction_funnel.py selftest: PASS  (D-79 data+lens-first: SHO triple; DJT data-led/advisory-silent in shortlist; DINO voted-but-unconfirmed contradiction)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Premarket three-axis conviction funnel (D-78, deterministic)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--tally", required=True)
    b.add_argument("--export", required=True)
    b.add_argument("--event-blocked", default="")
    b.add_argument("--out")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        _selftest()
        return
    blocked = [t.strip().upper() for t in a.event_blocked.split(",") if t.strip()]
    f = from_files(a.tally, a.export, event_blocked=blocked)
    out = json.dumps(f, indent=1)
    if a.out:
        open(a.out, "w").write(out)
    print(out if not a.out else json.dumps(f["counts"], indent=1) + "\n\n" + f["summary"])


if __name__ == "__main__":
    main()
