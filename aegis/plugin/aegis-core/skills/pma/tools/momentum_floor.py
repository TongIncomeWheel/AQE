#!/usr/bin/env python3
"""momentum_floor.py — the MOMENTUM BOOK floor (v5.2, PM-ratified 2026-08-31).

Runs at PREPARE, immediately after `pma_pipeline.py trim`, BEFORE any voice
packet is sliced. Drops every candidate failing the momentum bar so that no
seat — whatever its methodology — ever nominates outside the book.

PM ruling 2026-08-31 (option "Standard"):
    keep iff  rs_leadership in {LEADER, IN-LINE}  AND  rs_spy_20d > 5.0

Why this exists: the funnel had NO relative-strength qualification anywhere.
2026-08-26 deliberated VTR at rs_spy_20d -7.77 and PM at -6.50; 2026-08-31
deliberated MO at -2.52 and STAG at -5.81. Style-diverse seats (dip, geography,
R-arithmetic) kept tabling non-momentum names in a momentum book. The floor
scopes the seats; it does not silence them.

Deterministic. No model in the path. Dropped names are written out and MUST be
printed as one line in the brief header — visible, never silent.

If charter/parameters.yaml later carries a `momentum_floor:` block
(leadership_allowed, rs_spy_20d_min), those values win over the defaults here.
"""
import json, argparse, sys, os

DEFAULT_LEADERSHIP = {"LEADER", "IN-LINE"}
DEFAULT_RS_MIN = 5.0


def load_params(path):
    """Best-effort read of charter/parameters.yaml momentum_floor block (no yaml dep)."""
    lead, rs_min = set(DEFAULT_LEADERSHIP), DEFAULT_RS_MIN
    try:
        in_block = False
        for line in open(path):
            if line.startswith("momentum_floor:"):
                in_block = True
                continue
            if in_block:
                if line[:1] not in (" ", "\t"):
                    break
                s = line.strip()
                if s.startswith("rs_spy_20d_min:"):
                    rs_min = float(s.split(":", 1)[1].split("#")[0].strip())
                elif s.startswith("leadership_allowed:"):
                    v = s.split(":", 1)[1].split("#")[0].strip().strip("[]")
                    lead = {x.strip().strip("'\"") for x in v.split(",") if x.strip()}
    except (OSError, ValueError):
        pass
    return lead, rs_min


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, help="candidate_set.json from trim (edited in place)")
    ap.add_argument("--params", default=None, help="optional charter/parameters.yaml")
    ap.add_argument("--dropped-out", default="floor_dropped.json")
    a = ap.parse_args()

    lead_ok, rs_min = (load_params(a.params) if a.params
                       else (set(DEFAULT_LEADERSHIP), DEFAULT_RS_MIN))

    cs = json.load(open(a.candidates))
    rows_key = next((k for k in ("rows", "names", "candidates", "universe")
                     if isinstance(cs.get(k), list)), None)
    if rows_key is None:
        print("momentum_floor: FATAL — no candidate rows list found", file=sys.stderr)
        sys.exit(2)

    keep, drop = [], []
    for r in cs[rows_key]:
        try:
            rs = float(r.get("rs_spy_20d"))
        except (TypeError, ValueError):
            rs = None
        lead = r.get("rs_leadership")
        # A missing rs reading FAILS the floor — a momentum book cannot hold
        # an opinion on a name whose momentum is unmeasured. Declared, not silent.
        if rs is not None and rs > rs_min and lead in lead_ok:
            keep.append(r)
        else:
            drop.append({"ticker": r.get("ticker"), "rs_spy_20d": rs,
                         "rs_leadership": lead,
                         "reason": ("rs unmeasured" if rs is None else
                                    f"rs {rs} <= {rs_min}" if rs <= rs_min else
                                    f"leadership {lead} not in {sorted(lead_ok)}")})

    cs[rows_key] = keep
    cs["momentum_floor"] = {"ratified": "2026-08-31", "profile": "standard",
                            "leadership_allowed": sorted(lead_ok),
                            "rs_spy_20d_min": rs_min,
                            "kept": len(keep), "dropped": len(drop)}
    json.dump(cs, open(a.candidates, "w"), indent=1)
    json.dump(drop, open(a.dropped_out, "w"), indent=1)
    print(f"receipt: momentum floor (not-LAGGARD & rs>{rs_min}) — "
          f"{len(keep)} kept, {len(drop)} dropped -> {a.dropped_out}")


if __name__ == "__main__":
    main()
