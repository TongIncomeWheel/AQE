#!/usr/bin/env python3
"""
universe_build.py — the SINGLE owning builder of data/sod/DATE/universe.json (Lane 1, handoff/08).

THE ONE-LINE TRUTH:
  FMP  ->  AQE engine (external box)  ->  output/aqe_daily_export.json  ->  kernel
The AQE export IS ALREADY the fully-scored universe (D-66). There is no separate
"build universe, then run AQE". This builder does the ONE downstream shaping step:
read the AQE export and emit universe.json in ONE fixed shape. FMP feeds AQE upstream —
the kernel does NOT re-screen FMP (that redundant second screen, tools/universe_screen.py,
is retired from the premarket path; see its DEPRECATED banner).

OUTPUT SHAPE (fixed, schema-enforced by contracts/universe.schema.json):
  {
    "date":        <export date>,
    "source":      {"kind": "aqe_daily_export", "export_date": ..., "export_path": ...},
    "count":       <len(names)>,
    "names":       [ <daily_list record TRIMMED to the consumed field set>, ... ],
    "near_misses": [ <trimmed record + near_miss_reason>, ... ]
  }

The universe is the FULL AQE longlist — every name AQE scored — because the kernel applies
NO screen of its own: AQE's daily export IS the screened longlist (D-66), so the voices
nominate from all of it. The kernel cuts nothing, so `near_misses` is [] and D-37's "no
silent early cut" holds trivially (the only screen is AQE's, upstream — there is no kernel
screen to be "just outside" of). This is distinct from the ALERT universe (tools/alert_universe.py),
which is the narrowed data+detect set floored at sc>=70.

Each name is TRIMMED to the CONSUMED field set (Lane 4) — never the whole 97-field record.

Deterministic (law 4). No model, no network.

Usage:
  python3 tools/universe_build.py build --export output/aqe_daily_export.json \
      [--out data/sod/DATE/universe.json]
  python3 tools/universe_build.py selftest
"""
import json
import argparse
import os

# --- Lane 4 CONSUMED field set: the union of code-read fields + D-53 voice-menu fields.
# The kernel persists ONLY these into universe.json; everything else in the 97-field AQE
# record is dropped (never copied). Keep this list in sync with contracts/universe.schema.json
# and docs/AQE_SLIM_EMIT_SPEC.md.
CONSUMED = [
    "ticker", "rank", "sc_momentum", "sc_momentum_raw", "flow", "energy", "structure",
    "mp", "mp_state", "mp_accel_state", "elder", "elder_5d", "elder_pattern", "entry",
    "beta_30d", "day_vol", "rs_spy_20d", "rs_leadership", "rs_down_day_20d", "sma_distance_pct",
    "ma_20", "ma_50", "ma_100", "ma_200", "atr_14d", "gics_sector", "gics_sector_name",
    "sector_trend_state", "structure_shift", "choch_state", "div_bear_count", "div_state",
    "knn_prob", "knn_threshold_clear", "atr_caution", "runner_setup", "mover_subtype",
    "pin_bar_state", "sc_m_gates", "sc_m_gate_detail", "sc_p_gate_detail", "lens",
    "lens_positive", "source", "held", "bracket", "subcomponents",
]

# --- Fields AQE renamed, old name -> new name. Applied on READ so an ARCHIVED export
# (or an in-flight one written by an engine build older than the rename) still fills the
# voice menu instead of silently arriving null. Nothing writes the old name.
RENAMED = {"rvol": "day_vol"}   # renamed 2026-08-05; same number, same formula


def _trim(rec):
    """Return the record trimmed to the consumed field set (present keys only)."""
    out = {k: rec.get(k) for k in CONSUMED if k in rec}
    for old, new in RENAMED.items():
        if new not in out and old in rec:
            out[new] = rec[old]
    return out


def build(export, export_path=None):
    """Pure function (law 4). export: the loaded aqe_daily_export dict. Returns the
    fixed-shape universe = the FULL AQE longlist, each record trimmed to the consumed
    field set. The kernel applies NO screen of its own — AQE's export IS the screened
    longlist (D-66), so voices nominate from every name AQE scored. near_misses is []:
    nothing is cut kernel-side, so D-37's 'no silent early cut' holds trivially."""
    dl = export.get("daily_list", []) or []
    names = [_trim(r) for r in dl]
    return {
        "date": export.get("date"),
        "source": {"kind": "aqe_daily_export", "export_date": export.get("date"),
                   "export_path": export_path},
        "count": len(names),
        "names": names,
        "near_misses": [],
    }


def from_export(export_path):
    d = json.load(open(export_path))
    return build(d, export_path=export_path)


def _selftest():
    export = {
        "date": "2026-07-21",
        "daily_list": [
            # trimmed, bloat dropped
            {"ticker": "AAA", "sc_momentum": 82.5, "rank": 1, "flow": 88.0, "structure": 86.0,
             "gics_sector_name": "Financials", "subcomponents": None, "held": False,
             "fib_236": 53.89, "pipe_rank": 52.4, "thematic_baskets": [{"x": 1}]},   # last 3 = bloat, must drop
            # a low-score name is STILL in the universe (kernel screens nothing — voices see it)
            {"ticker": "BBB", "sc_momentum": 40.0, "rank": 120, "flow": 60.0},
            {"ticker": "CCC", "sc_momentum": 70.0, "rank": 30},
        ],
    }
    u = build(export, export_path="X")
    assert u["date"] == "2026-07-21"
    assert u["source"]["kind"] == "aqe_daily_export" and u["source"]["export_date"] == "2026-07-21"
    tickers = [n["ticker"] for n in u["names"]]
    # FULL longlist — every AQE name present, including the low-score one; no kernel cut.
    assert tickers == ["AAA", "BBB", "CCC"], ("universe must carry the full AQE longlist", tickers)
    assert u["count"] == 3
    assert u["near_misses"] == [], "near_misses must be empty — the kernel applies no screen"
    # trimming: bloat fields dropped, consumed fields kept (incl null subcomponents)
    aaa = u["names"][0]
    for dropped in ("fib_236", "pipe_rank", "thematic_baskets"):
        assert dropped not in aaa, ("bloat field leaked", dropped)
    for kept in ("ticker", "sc_momentum", "flow", "structure", "subcomponents", "held"):
        assert kept in aaa, ("consumed field lost", kept)
    print("universe_build.py selftest: PASS  (FULL AQE longlist, no kernel screen; "
          "trimmed to consumed set; near_misses empty)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build data/sod/DATE/universe.json from the AQE export (Lane 1, deterministic)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--export", required=True)
    b.add_argument("--out", help="default: data/sod/<export date>/universe.json")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        _selftest()
        return
    u = from_export(a.export)
    out_path = a.out or os.path.join("data", "sod", str(u["date"]), "universe.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(u, fh, indent=1)
    print("wrote %s: %d names, %d near-misses" % (out_path, u["count"], len(u["near_misses"])))


if __name__ == "__main__":
    main()
