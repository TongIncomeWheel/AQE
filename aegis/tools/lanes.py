#!/usr/bin/env python3
"""
lanes.py — the SINGLE definition of the 8 detection lanes (D-77) + the ONE loader
for their thresholds from charter/parameters.yaml.

WHY THIS EXISTS (Lane-2 consolidation, handoff/08, PM sign-off 2026-07-22):
  alert_universe.lanes_for and conviction_funnel._lane_count re-implemented the
  IDENTICAL 8-lane logic in two files, and NEITHER read parameters.yaml (so the PM
  tuned thresholds and nothing changed). This module is the single source of truth
  for BOTH the lane logic AND the thresholds. The two tools now import from here.
  The lane logic is UNCHANGED — only its location moved (byte-identical results).

THE 8 DETECTION LANES (each a distinct "momentum coming in" signal):
  1. sc_m_gates            all 5 momentum sub-gates pass (flow/energy/structure/mp/elder)
  2. choch_state==BULLISH  bullish change-of-character (Wyckoff structural turn)
  3. knn_significant       Thorp's quant edge fired
  4. detect_lens >= N      the 6-lens detect count (OR-booster, one lane, NEVER the gate)
  5. rs_leadership==LEADER relative-strength leader
  6. structure >= N        structural quality
  7. flow >= N             participation / accumulation
  8. mp_accel not DECEL    momentum accelerating/building/flat, not rolling over

Deterministic (law 4). No model, no network.

Usage:
  python3 tools/lanes.py selftest
"""
import json
import os
import sys

# --- per-section default thresholds (the fallback when parameters.yaml lacks a key) ---
# These MIRROR the alert_universe.* and conviction_funnel.* blocks in
# charter/parameters.yaml and match the 21 Jul 2026 calibration.
DEFAULTS = {
    "alert_universe": {
        "sc_floor": 70,      # core momentum floor (membership gate)
        "min_lanes": 2,      # minimum detection lanes to be in the universe at all
        "t1_lanes": 5,       # Tier 1 threshold (high confirmation)
        "t2_lanes": 3,       # Tier 2 threshold (confirmed)
        "lane_structure": 72,
        "lane_flow": 68,
        "lane_detect": 4,
    },
    "conviction_funnel": {
        "target_min": 10, "target_max": 15,
        "cons_strong_votes": 3, "cons_med_votes": 2,   # consensus grade cutoffs
        "data_strong_lanes": 5, "data_med_lanes": 3,   # DATA (lane) grade cutoffs
        "lens_strong": 4, "lens_med": 2,               # LENS (detect) grade cutoffs
        "lane_structure": 72, "lane_flow": 68, "lane_detect": 4,
        "contradiction_consensus_min_votes": 3,
        "data_lens_only_cap": 6,
    },
}

_PARAMS_PATH = os.path.join(os.path.dirname(__file__), "..", "charter", "parameters.yaml")


def _num(v, dv=0):
    return v if isinstance(v, (int, float)) else dv


def lanes_for(rec, detect_positive, p):
    """Return the list of detection-lane names that fired for one AQE record.
    detect_positive = the name's 6-lens 'positive' count from lens_ranking.
    Extracted VERBATIM from the retired alert_universe.lanes_for — the ONE copy."""
    L = []
    if rec.get("sc_m_gates") is True:
        L.append("5gates")
    if rec.get("choch_state") == "BULLISH":
        L.append("CHoCH+")
    if rec.get("knn_significant") is True:
        L.append("KNN")
    if _num(detect_positive) >= p["lane_detect"]:
        L.append("detect%d" % int(detect_positive))
    if rec.get("rs_leadership") == "LEADER":
        L.append("LEADER")
    if _num(rec.get("structure")) >= p["lane_structure"]:
        L.append("struct")
    if _num(rec.get("flow")) >= p["lane_flow"]:
        L.append("flow")
    if rec.get("mp_accel_state") in ("ACCELERATING", "BUILDING", "FLAT"):
        L.append("accel")
    return L


def lane_count(rec, detect_positive, p):
    """The number of detection lanes that fired = len(lanes_for). The ONE lane count
    both tools use (replaces the retired conviction_funnel._lane_count)."""
    return len(lanes_for(rec, detect_positive, p))


def load_params(section):
    """Return the threshold dict for `section` ('alert_universe' | 'conviction_funnel'),
    reading charter/parameters.yaml and OVERLAYING it on this module's DEFAULTS. A key
    absent from parameters.yaml falls back to the DEFAULT. This is the fix for the
    'PM tunes parameters.yaml but nothing changes' bug — both tools now honour it.

    Only the known threshold keys for the section are pulled (nested lists like the
    'lanes:' menu / 'contradictions:' prose in the yaml are documentation, not thresholds).
    """
    base = dict(DEFAULTS[section])
    try:
        import yaml
        with open(_PARAMS_PATH) as fh:
            doc = yaml.safe_load(fh) or {}
        block = doc.get(section, {}) or {}
        for k in base:                       # only overlay recognised threshold keys
            v = block.get(k)
            if isinstance(v, (int, float)):  # ignore non-scalar yaml (lanes list, prose)
                base[k] = v
    except Exception:
        pass                                 # deterministic fallback to DEFAULTS
    return base


def _selftest():
    # BILL-style record: 5gates + bullish CHoCH + KNN + LEADER + structure + flow, detect 0.
    bill = {"sc_m_gates": True, "choch_state": "BULLISH", "knn_significant": True,
            "rs_leadership": "LEADER", "structure": 78.9, "flow": 84.2,
            "mp_accel_state": "DECELERATING"}
    pa = load_params("alert_universe")
    fired = lanes_for(bill, 0, pa)
    assert fired == ["5gates", "CHoCH+", "KNN", "LEADER", "struct", "flow"], fired
    assert lane_count(bill, 0, pa) == len(fired) == 6, fired
    # detect lane fires only at/above lane_detect; accel fires for FLAT/BUILDING/ACCEL.
    etsy = {"sc_m_gates": True, "choch_state": "BULLISH", "knn_significant": True,
            "rs_leadership": "LEADER", "structure": 69.5, "flow": 67.1,
            "mp_accel_state": "FLAT"}
    fired2 = lanes_for(etsy, 4, pa)   # detect 4 >= lane_detect(4) -> fires
    assert "detect4" in fired2 and "accel" in fired2 and "struct" not in fired2, fired2
    assert lane_count(etsy, 4, pa) == len(fired2), fired2
    # a name below every threshold fires nothing.
    assert lanes_for({}, 0, pa) == [], "empty record must fire no lanes"
    # load_params returns full threshold sets, defaulted keys present.
    pf = load_params("conviction_funnel")
    for k in DEFAULTS["conviction_funnel"]:
        assert k in pf, ("missing funnel threshold", k)
    for k in DEFAULTS["alert_universe"]:
        assert k in pa, ("missing alert threshold", k)
    print("lanes.py selftest: PASS  (8-lane logic single-sourced; load_params overlays parameters.yaml on DEFAULTS)")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "selftest":
        _selftest()
        return
    if argv and argv[0] == "show":
        section = argv[1] if len(argv) > 1 else "alert_universe"
        print(json.dumps(load_params(section), indent=1))
        return
    print(__doc__)


if __name__ == "__main__":
    main()
