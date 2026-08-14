#!/usr/bin/env python3
"""
alert_universe.py — the AQE Alerts "casting mat" (D-77).

Builds tonight's intraday alert universe MECHANICALLY from the AQE daily export,
so the alert feed is a formula the PM controls — not a hand-picked committee list
(that was too narrow) and not the old noisy single-factor `sc_momentum > 70` (too
much noise). Deterministic, law 4, no model.

WHY THIS EXISTS (2-day PM deliberation, 20-21 Jul 2026):
- The old alert feed was `sc_momentum >= 70` alone -> 57 names, lots of noise.
- Tightening to `sc_momentum >= 80` -> 2 names, far too narrow (the PM: "many good
  sc_mom that aren't top still run when they have good structure or a good elder
  around it"). So a single threshold on one field is wrong either way.
- The committee hand-picking ~37 names was WORSE — it limited the feed to "our
  singular view" and missed genuine intraday runners (BILL, ETSY ran last night and
  a narrow list would have missed them).
- KEY FINDING: the 6-lens detect count alone MISSES real runners. BILL scored 0/6 on
  the detect lens but ran — it carried `sc_m_gates` (all 5 momentum sub-gates), a
  BULLISH change-of-character, and a significant KNN. So detection must be a COUNT of
  many momentum-incoming signals ("lanes"), with the detect lens as ONE lane (an
  OR-booster), never the gate.

THE CASTING MAT:
  A name is IN the universe if  sc_momentum >= SC_FLOOR  AND  lane_count >= MIN_LANES.
  It is then TIERED by how many lanes fired (depth of confirmation = "is fresh
  momentum arriving, or is this a stale high score"):
     Tier 1 (>= T1_LANES): high-confirmation, priority alerts
     Tier 2 (>= T2_LANES): confirmed, second priority
     Tier 3 (>= MIN_LANES): headline-only / thin confirmation -> watch only
  Each name carries its lane_count + lanes_fired into the market-hours pod, because
  those are the SAME numbers the voices read to judge runner-or-not (D-63).

THE 8 DETECTION LANES (each a distinct "momentum coming in" signal):
  1. sc_m_gates            all 5 momentum sub-gates pass (flow/energy/structure/mp/elder)
  2. choch_state==BULLISH  bullish change-of-character (Wyckoff structural turn)
  3. knn_threshold_clear       Thorp's quant edge fired
  4. detect_lens >= 4/6    the 6-lens detect count (leadership/coil/insti/structure/resistance/sector)
  5. rs_leadership==LEADER relative-strength leader
  6. structure >= 72       structural quality
  7. flow >= 68            participation / accumulation
  8. mp_accel not DECEL    momentum accelerating/building, not rolling over

EVENT OVERLAY: names flagged event-driven (e.g. announced M&A) are STRUCK from the
universe regardless of score — the mechanical screen catches the momentum, the event
filter removes the fake (PYPL 21 Jul: sc 82.5 but +17% takeover pop -> excluded).

Thresholds live in charter/parameters.yaml (alert_universe.*) so the PM tunes the mat
without a code change. Defaults below match the 21 Jul calibration (validated: BILL &
ETSY both land Tier 1; DINO correctly demoted to Tier 3 as a 25%-extended stale move).

Usage:
  python3 tools/alert_universe.py build --export output/aqe_daily_export.json \
      [--event-blocked PYPL,XYZ] [--sc-floor 70] [--min-lanes 2] \
      [--t1 5] [--t2 3] [--out data/alerts/DATE/alert_universe.json]
  python3 tools/alert_universe.py selftest
"""
import json
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lanes  # noqa: E402  — the SINGLE source of the 8-lane logic + thresholds (Lane-2 dedup)

# --- default thresholds now live in tools/lanes.py (lanes.DEFAULTS['alert_universe']) ---
# Kept as a module alias for backwards-compat callers that referenced alert_universe.DEFAULTS.
DEFAULTS = lanes.DEFAULTS["alert_universe"]


def _num(v, dv=0):
    return v if isinstance(v, (int, float)) else dv


def build(daily_list, lens_positive_by_ticker, params=None, event_blocked=None):
    """Pure function (law 4). daily_list: list of AQE records. lens_positive_by_ticker:
    {ticker: int}. Returns the tiered universe dict. Never calls a model or the network.
    Lane logic is single-sourced from tools/lanes.py (byte-identical to the retired local copy)."""
    p = dict(DEFAULTS)
    if params:
        p.update({k: v for k, v in params.items() if v is not None})
    blocked = set(t.upper() for t in (event_blocked or []))

    members, struck = [], []
    for r in daily_list:
        t = r.get("ticker")
        sc = _num(r.get("sc_momentum"))
        if sc < p["sc_floor"]:
            continue
        fired = lanes.lanes_for(r, lens_positive_by_ticker.get(t, 0), p)
        if len(fired) < p["min_lanes"]:
            continue
        row = {
            "ticker": t, "sc_momentum": sc, "lane_count": len(fired),
            "lanes_fired": fired, "mp_state": r.get("mp_state"),
            "ext_pct": _num(r.get("sma_distance_pct")),
            "sector": r.get("gics_sector_name"),
            "rs_spy_20d": _num(r.get("rs_spy_20d")),
        }
        if t in blocked:
            row["struck_reason"] = "event-driven (blocked by event filter)"
            struck.append(row)
        else:
            members.append(row)

    members.sort(key=lambda x: (-x["lane_count"], -x["sc_momentum"]))

    def tier(n):
        if n >= p["t1_lanes"]:
            return 1
        if n >= p["t2_lanes"]:
            return 2
        return 3
    for m in members:
        m["tier"] = tier(m["lane_count"])

    t1 = [m for m in members if m["tier"] == 1]
    t2 = [m for m in members if m["tier"] == 2]
    t3 = [m for m in members if m["tier"] == 3]
    return {
        "recipe": "casting_mat_v1",
        "params": p,
        "count": {"total": len(members), "tier1": len(t1), "tier2": len(t2),
                  "tier3": len(t3), "struck": len(struck)},
        "tier1_priority": t1,
        "tier2_confirmed": t2,
        "tier3_watch": t3,
        "struck_event": struck,
        "lane_legend": {
            "5gates": "all 5 momentum sub-gates pass", "CHoCH+": "bullish change-of-character",
            "KNN": "Thorp quant edge significant", "detect": "6-lens detect >= threshold",
            "LEADER": "rs leadership", "struct": "structure >= threshold",
            "flow": "flow >= threshold", "accel": "momentum not decelerating",
        },
    }


def from_export(export_path, params=None, event_blocked=None):
    """Convenience: load an AQE export file and build. lens positive comes from the
    export's own lens_ranking block (no separate MCP call needed).

    Thresholds are loaded from charter/parameters.yaml (alert_universe.*) via
    lanes.load_params, then any CLI overrides in `params` win on top (CLI still wins)."""
    d = json.load(open(export_path))
    dl = d.get("daily_list", [])
    lens = {}
    for x in (d.get("lens_ranking", {}) or {}).get("ranked", []):
        if isinstance(x, dict):
            lens[x.get("ticker")] = x.get("positive", 0)
    resolved = lanes.load_params("alert_universe")           # parameters.yaml -> honoured
    if params:
        resolved.update({k: v for k, v in params.items() if v is not None})  # CLI wins
    return build(dl, lens, params=resolved, event_blocked=event_blocked)


def _selftest():
    # BILL: 0/6 detect, but 5gates + bullish CHoCH + KNN + LEADER + structure + flow -> must be Tier 1.
    bill = {"ticker": "BILL", "sc_momentum": 77.4, "sc_m_gates": True, "choch_state": "BULLISH",
            "knn_threshold_clear": True, "rs_leadership": "LEADER", "structure": 78.9, "flow": 84.2,
            "mp_accel_state": "DECELERATING", "sma_distance_pct": 20.3, "mp_state": "FADING"}
    # ETSY: detect 2, 5gates + CHoCH + KNN + LEADER + accel -> Tier 1.
    etsy = {"ticker": "ETSY", "sc_momentum": 73.6, "sc_m_gates": True, "choch_state": "BULLISH",
            "knn_threshold_clear": True, "rs_leadership": "LEADER", "structure": 69.5, "flow": 67.1,
            "mp_accel_state": "FLAT", "sma_distance_pct": 18.8, "mp_state": "FADING"}
    # DINO: high sc but only LEADER + flow -> Tier 3 (stale/extended).
    dino = {"ticker": "DINO", "sc_momentum": 79.7, "sc_m_gates": False, "choch_state": "RANGE",
            "knn_threshold_clear": False, "rs_leadership": "LEADER", "structure": 68.4, "flow": 90.8,
            "mp_accel_state": "DECELERATING", "sma_distance_pct": 25.0, "mp_state": "STRONG"}
    # NOISE: sc below floor -> excluded entirely.
    noise = {"ticker": "NOISE", "sc_momentum": 55.0, "rs_leadership": "LEADER"}
    # PYPL: strong but event-blocked -> struck.
    pypl = {"ticker": "PYPL", "sc_momentum": 82.5, "rs_leadership": "LEADER", "structure": 80,
            "flow": 80, "mp_accel_state": "FLAT", "choch_state": "RANGE"}
    lens = {"BILL": 0, "ETSY": 2, "DINO": 1, "PYPL": 3}
    u = build([bill, etsy, dino, noise, pypl], lens, event_blocked=["PYPL"])
    tiers = {m["ticker"]: m["tier"] for m in u["tier1_priority"] + u["tier2_confirmed"] + u["tier3_watch"]}
    assert tiers.get("BILL") == 1, ("BILL must be Tier 1", tiers)
    assert tiers.get("ETSY") == 1, ("ETSY must be Tier 1", tiers)
    assert tiers.get("DINO") == 3, ("DINO must be Tier 3 (stale)", tiers)
    assert "NOISE" not in tiers, "NOISE below sc floor must be excluded"
    assert u["count"]["struck"] == 1 and u["struck_event"][0]["ticker"] == "PYPL", "PYPL must be struck"
    # idempotent membership count
    assert u["count"]["total"] == 3, ("expected 3 members", u["count"])
    print("alert_universe.py selftest: PASS  (BILL/ETSY Tier1, DINO Tier3, NOISE out, PYPL struck)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="AQE alert-universe casting mat (D-77, deterministic)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--export", required=True)
    b.add_argument("--event-blocked", default="")
    b.add_argument("--sc-floor", type=int)
    b.add_argument("--min-lanes", type=int)
    b.add_argument("--t1", type=int, dest="t1_lanes")
    b.add_argument("--t2", type=int, dest="t2_lanes")
    b.add_argument("--out")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        _selftest()
        return
    params = {k: getattr(a, k) for k in ("sc_floor", "min_lanes", "t1_lanes", "t2_lanes")
              if getattr(a, k) is not None}
    blocked = [t.strip().upper() for t in a.event_blocked.split(",") if t.strip()]
    u = from_export(a.export, params=params or None, event_blocked=blocked)
    out = json.dumps(u, indent=1)
    if a.out:
        open(a.out, "w").write(out)
    print(out if not a.out else json.dumps(u["count"], indent=1))


if __name__ == "__main__":
    main()
