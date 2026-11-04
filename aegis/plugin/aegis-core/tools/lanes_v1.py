#!/usr/bin/env python3
"""lanes_v1 -- THREE LANES assigned by code, with lead and advisory seats (PM 2026-11-04: "momentum and pullback;
continuation is a subset of momentum"). PROPOSED, behind parameters.lanes_v1 (off). Nothing here is called by the live run
until the PM signs R43 and the parameter is switched on; the pure functions are tested and the dry-run is in
docs/LANES_V1_SPEC.md.

Pure functions only (no file reads, no AQE import): a record is one AQE export row, optionally carrying the continuation
fields (continuation_pivot / pct_from_continuation_pivot / continuation_state), which AQE exports from 5 Nov 2026.

LANE ASSIGNMENT (first match wins; deterministic; the same row always gets the same lane):
  MOMENTUM_CONTINUATION  the name is already past its base pivot by more than the chase line (pct_from_pivot > 5) AND AQE found
                         a continuation window (a 3-10 bar tight pause that ended within the last 5 bars).
                         Judged against the continuation pivot: BELOW = coiling under the pause high, BUY_ZONE 0-5%,
                         EXTENDED > 5%.
  MOMENTUM_BREAKOUT      the name is at or below its base pivot and not extended: 0 <= pct_from_pivot <= 5 (breaking out inside
                         the chase line), or pct_from_pivot < 0 and within 3% of its 20-bar high and showing a tight bar
                         (squeeze / NR4 / NR7 / coil lens strong) -- coiling under the pivot.
  PULLBACK               below its pivot (pct_from_pivot < 0) and either on a reclaim day (U&R MET/SETUP) or holding a rising
                         20-day average (close above it, slope > 0) or its 50-day average.
  UNLANED                none of the above (e.g. extended with no continuation window). Every seat counts, exactly as today.
"""
from __future__ import annotations

BREAKOUT, CONTINUATION, PULLBACK, UNLANED = "MOMENTUM_BREAKOUT", "MOMENTUM_CONTINUATION", "PULLBACK", "UNLANED"
LANES = (BREAKOUT, CONTINUATION, PULLBACK)

CHASE_PIVOT_PCT = 5.0          # the committee's line (consensus.json objections; export glossary 0-5% buy zone)
COIL_NEAR_HIGH_PCT = 3.0

DECIDERS = ("oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff")

# PM 2026-11-04 named the continuation leads (Livermore, Seow, Elder, Raschke lead; O'Neil + Minervini advise). Breakout and
# pullback leads are PROPOSED from each canon's own method (canon.lock.yaml recognisers) and need the PM's yes.
LEADS = {
    CONTINUATION: ("livermore", "seow", "elder-lens", "raschke"),
    BREAKOUT:     ("oneil", "minervini", "livermore", "wyckoff"),
    PULLBACK:     ("seow", "elder-lens", "raschke", "wyckoff"),
}
PM_SIGNED = {CONTINUATION: True, BREAKOUT: False, PULLBACK: False}


def advisors(lane):
    return tuple(s for s in DECIDERS if lane in LEADS and s not in LEADS[lane])


def _num(x):
    return isinstance(x, (int, float)) and x == x


def assign_lane(r):
    """Returns (lane, [plain reasons])."""
    piv = r.get("pct_from_pivot")
    cont = r.get("continuation_pivot")
    e, hi20 = r.get("entry"), r.get("hi_20d")
    if _num(piv) and piv > CHASE_PIVOT_PCT and _num(cont):
        st = r.get("continuation_state")
        return CONTINUATION, [f"{piv:.1f}% past its base pivot (chase line {CHASE_PIVOT_PCT:g}%)",
                              f"has a continuation pause high at {cont:g}" + (f" ({st})" if st else "")]
    if _num(piv) and 0 <= piv <= CHASE_PIVOT_PCT:
        return BREAKOUT, [f"{piv:.1f}% past its base pivot, inside the {CHASE_PIVOT_PCT:g}% line"]
    under = (hi20 - e) / hi20 * 100 if _num(e) and _num(hi20) and hi20 else None
    lens = r.get("lens") or {}
    tight = [w for w, ok in (("in a squeeze", r.get("was_squeezed")), ("narrowest range in 4 days", r.get("nr4_flag")),
                             ("narrowest range in 7 days", r.get("nr7_flag")), ("coil lens strong", lens.get("coil") == "strong")) if ok]
    if _num(piv) and piv < 0 and _num(under) and under <= COIL_NEAR_HIGH_PCT and tight:
        return BREAKOUT, [f"{abs(piv):.1f}% under its base pivot, {under:.1f}% under its 20-bar high", tight[0]]
    m20, slope, m50 = r.get("ma_20"), r.get("ma_20_slope_5d_pct"), r.get("ma_50")
    holds = []
    if r.get("unr_status") in ("MET", "SETUP"):
        holds.append("reclaim day (undercut and rally)")
    if _num(e) and _num(m20) and e > m20 and _num(slope) and slope > 0:
        holds.append("holding a rising 20-day average")
    elif _num(e) and _num(m50) and e > m50:
        holds.append("holding its 50-day average")
    if _num(piv) and piv < 0 and holds:
        return PULLBACK, [f"{abs(piv):.1f}% under its base pivot"] + holds[:1]
    return UNLANED, ["no lane rule applies (every seat counts, as today)"]


def lane_status(lane, objectors, n_present, present, drop_threshold_all, threshold_mode="proportional"):
    """Verdict status for one ticket under lanes_v1. `objectors` = seats that answered OBJECT; `present` = deciders who ratified.
    A laned ticket is decided by its LEAD seats that are present; advisor objections are listed (`advisor_objectors`), never
    counted. UNLANED = today's rule. Two threshold modes, for the PM to choose between (both measured in the spec):
      proportional  DROP at ceil(leads_present / 2) lead objections (4 leads -> 2). Stricter on a name the leads dislike.
      absolute      DROP at the room's own threshold (4 of 7) counted among the leads only (4 leads -> all four must object)."""
    import math
    if lane not in LEADS:
        n_obj = len(objectors)
        return {"status": "AGREED" if n_obj == 0 else ("DROPPED" if n_obj >= drop_threshold_all else "CONTESTED"),
                "counted_objectors": list(objectors), "advisor_objectors": [], "threshold": drop_threshold_all, "leads_present": None}
    leads = [s for s in LEADS[lane] if s in present]
    lead_obj = sorted(s for s in objectors if s in leads)
    adv_obj = sorted(s for s in objectors if s not in leads)
    thr = (math.ceil(len(leads) / 2) if threshold_mode == "proportional" else drop_threshold_all) if leads else drop_threshold_all
    status = "AGREED" if not lead_obj else ("DROPPED" if len(lead_obj) >= thr else "CONTESTED")
    return {"status": status, "counted_objectors": lead_obj, "advisor_objectors": adv_obj, "threshold": thr, "leads_present": leads}


YARDSTICK = {
    BREAKOUT: ("judge it against its BASE PIVOT: is it breaking out (0-5% past pivot_high, the 5% chase line), is the volume test met, "
               "or is it coiling just under the pivot with a tight bar. Continuation fields do not apply to it."),
    CONTINUATION: ("judge it against its CONTINUATION PIVOT (continuation_pivot, continuation_state, pct_from_continuation_pivot): the high of "
                   "its last 3-10 bar tight pause. BELOW = coiling under the pause high (the break has not happened); BUY_ZONE = 0-5% past it; "
                   "EXTENDED = more than 5% past it. The base pivot_high and its 5% chase line are NOT the yardstick for this name - it is "
                   "already past them by design. Stretch is read in daily ranges over the 20-day average; 'more than 70% over the 200-day' is a "
                   "WARNING you state, not a veto. extension_bracket is AQE's second, labelled bracket (1.272 / 1.618 of the last leg) for a "
                   "name in open air; it ignores nearby resistance, so say so if you rely on it."),
    PULLBACK: ("judge it as a pullback: a reclaim of a rising average or a reclaim day (undercut and rally), under its base pivot. "
               "Extension and distance past the pivot do not apply."),
}


def prompt_lines():
    """The vote-packet text when lanes_v1 is on: the lanes, who leads, and each lane's yardstick (R43)."""
    out = ["LANES v1 (R43, PM 2026-11-04): every ticket carries ONE lane assigned by code from AQE fields: lane=MOMENTUM_BREAKOUT, "
           "MOMENTUM_CONTINUATION, PULLBACK, or UNLANED (no lane rule applied: every seat counts, as before). Continuation is a subset of momentum.",
           "LEADS decide: in a laned ticket only the LEAD seats' OBJECT answers count toward AGREED / CONTESTED / DROPPED (DROP at half of the leads, "
           "rounded up). An ADVISOR's objection is printed on the ticket and never counted - file it anyway, in your own method, with what would clear it."]
    for lane in LANES:
        out.append(f"  {lane}: leads {', '.join(LEADS[lane])}; advisors {', '.join(advisors(lane))}. Yardstick: {YARDSTICK[lane]}")
    out.append("Say which seat-role you are on each ticket (lead or advisor) in your own words only if it changes your answer; the lane and role are in the packet.")
    return out
