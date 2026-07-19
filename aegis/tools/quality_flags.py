#!/usr/bin/env python3
"""Voice quality-evaluation flags (D-39) — RESTORED.

These are the momentum-literature quality flags the voices originally asked for and that
the drift dropped from their data menus. They are SOFT (D-37/D-38): surfaced at
deliberation, never a gate. Each flag names the field(s) behind it (anchor, D-20) and the
voice frameworks whose method uses it (FLAG_VOICES) — so each voice weighs its own flags.

Deterministic (law 4). Thresholds are RB:quality_flags (PM-tunable). Reads a full AQE
record (top-level + subcomponents). Direction of every flag is taken from the data /
glossary — nothing wrong-signed is invented (e.g. exhaustion_score is deliberately NOT
flagged until AQE confirms its direction — BL-040).
"""
from __future__ import annotations

# Which voice frameworks read each flag (from each voice's canon + momentum literature).
FLAG_VOICES = {
    "squeeze":              ["raschke", "minervini", "wyckoff"],   # volatility contraction -> expansion (VCP / coil)
    "tight_base":           ["minervini", "oneil", "wyckoff"],     # base quality / accumulation
    "structure_bos":        ["wyckoff", "minervini", "raschke", "oneil"],  # break of structure = breakout
    "impulse_accelerating": ["oneil", "minervini", "raschke", "wyckoff"],  # impulse strengthening
    "rs_leader":            ["oneil", "minervini"],                # relative-strength leadership
    "rs_resilient":         ["oneil", "minervini"],                # holds up on down days
    "knn_favorable":        ["thorp"],                             # historical directional edge
    "bullish_divergence":   ["raschke", "wyckoff"],
    "bearish_divergence":   ["raschke", "steenbarger", "wyckoff", "oneil", "minervini"],  # reversal warning
    "overextended":         ["minervini", "oneil", "seow"],        # too far from base to chase
    "atr_caution":          ["raschke", "thorp", "seow"],          # volatility elevated
    "structure_choch":      ["wyckoff", "minervini", "raschke"],   # character turned down
    "impulse_interrupted":  ["oneil", "minervini", "raschke"],     # impulse broke
}


# Per-flag catalog: polarity + plain definition + the AQE source field(s) behind it (anchor, D-20).
# Single source of truth for the build (injects each voice's flag vocabulary) AND for menu wiring.
# Keys MUST match FLAG_VOICES exactly (asserted below).
FLAG_CATALOG = {
    "squeeze":              ("strength", "volatility contraction coiling toward expansion (VCP/coil)", ["energy.squeeze_score"]),
    "tight_base":           ("strength", "a long, tight base — accumulation, breakout-ready", ["bq.bq_base_dur", "bq.bq_range_tight"]),
    "structure_bos":        ("strength", "break of structure to the upside (BULLISH_BOS)", ["structure_shift"]),
    "impulse_accelerating": ("strength", "impulse strengthening (Elder ACCELERATION/SUSTAINED or MP ACCELERATING)", ["elder_pattern", "mp_accel_state"]),
    "rs_leader":            ("strength", "relative-strength leadership vs SPY", ["rs_leadership"]),
    "rs_resilient":         ("strength", "holds up on the tape's down days (positive RS on down days)", ["rs_down_day_20d"]),
    "knn_favorable":        ("context",  "historical k-NN analogue set leans up with significance", ["knn_prob", "knn_significant"]),
    "bullish_divergence":   ("strength", "bullish oscillator divergence — momentum turning up", ["div_state"]),
    "bearish_divergence":   ("caution",  "bearish oscillator divergence — reversal/exhaustion risk", ["div_state", "div_bear_count"]),
    "overextended":         ("caution",  "extended far above its SMA — late to chase", ["sma_distance_pct"]),
    "atr_caution":          ("caution",  "ATR/volatility elevated — wider swings, size accordingly", ["atr_caution"]),
    "structure_choch":      ("caution",  "change of character down (BEARISH_CHOCH) — trend intact-question", ["structure_shift"]),
    "impulse_interrupted":  ("caution",  "impulse interrupted (Elder INTERRUPTED) — thrust stalled", ["elder_pattern"]),
}
assert set(FLAG_CATALOG) == set(FLAG_VOICES), "FLAG_CATALOG and FLAG_VOICES keys must match"


def catalog_for_voice(voice: str):
    """The quality-flag vocabulary this voice's framework evaluates: list of
    (flag, polarity, definition, fields). Reverse of FLAG_VOICES. Used by the build to
    inject each voice's OWN restored flags (D-39) into its compiled agent."""
    out = []
    for flag, voices in FLAG_VOICES.items():
        if voice in voices:
            pol, defn, fields = FLAG_CATALOG[flag]
            out.append((flag, pol, defn, fields))
    return out


def source_fields_for_voice(voice: str):
    """Every AQE field a voice's flags anchor on — added to its data menu so anchors are on-menu."""
    fields = []
    for _flag, _pol, _defn, fs in catalog_for_voice(voice):
        for f in fs:
            if f not in fields:
                fields.append(f)
    return fields


_TH_FALLBACK = {"squeeze_min": 5.0, "base_dur_min": 10, "range_tight_min": 12,
                "overextended_sma_pct": 25.0, "rs_down_day_min": 2.0, "knn_prob_min": 0.6}


def _rb_thresholds():
    """RB:quality_flags from charter/parameters.yaml — the PM-tunable source. Falls back to the
    in-code defaults if the charter isn't reachable (e.g. unit test outside the package)."""
    import os
    try:
        import yaml
        here = os.path.dirname(os.path.abspath(__file__))
        p = os.path.join(os.path.dirname(here), "charter", "parameters.yaml")
        qf = (yaml.safe_load(open(p)) or {}).get("quality_flags") or {}
        return {**_TH_FALLBACK, **qf}
    except Exception:
        return dict(_TH_FALLBACK)


def _sub(rec, engine, key):
    return (rec.get("subcomponents") or {}).get(engine, {}).get(key)


def derive(rec: dict, p: dict | None = None) -> dict:
    """Return {'strength': [...], 'caution': [...], 'context': [...]}; each item
    {flag, label, anchor, voices}. A flag appears only when it FIRES."""
    th = _rb_thresholds()
    th.update(p or {})   # explicit override wins over charter default
    S, C, X = [], [], []

    def add(bucket, flag, label, anchor):
        bucket.append({"flag": flag, "label": label, "anchor": anchor, "voices": FLAG_VOICES.get(flag, [])})

    # STRENGTH
    sq = _sub(rec, "energy", "squeeze_score")
    if sq is not None and sq >= th["squeeze_min"]:
        add(S, "squeeze", f"volatility squeeze ({sq}) — breakout pending", {"energy.squeeze_score": sq})
    bd, rt = _sub(rec, "bq", "bq_base_dur"), _sub(rec, "bq", "bq_range_tight")
    if bd is not None and rt is not None and bd >= th["base_dur_min"] and rt >= th["range_tight_min"]:
        add(S, "tight_base", f"tight base ({bd}d, tightness {rt}) — breakout-ready", {"bq.bq_base_dur": bd, "bq.bq_range_tight": rt})
    ss = rec.get("structure_shift")
    if ss == "BULLISH_BOS":
        add(S, "structure_bos", "structure broken UP (BULLISH_BOS)", {"structure_shift": ss})
    elif ss == "BEARISH_CHOCH":
        add(C, "structure_choch", "character turned DOWN (BEARISH_CHOCH)", {"structure_shift": ss})
    ep = rec.get("elder_pattern"); acc = rec.get("mp_accel_state")
    if ep in ("ACCELERATION", "SUSTAINED") or acc == "ACCELERATING":
        add(S, "impulse_accelerating", f"impulse {ep or acc}", {"elder_pattern": ep, "mp_accel_state": acc})
    elif ep == "INTERRUPTED":
        add(C, "impulse_interrupted", "impulse INTERRUPTED", {"elder_pattern": ep})
    if rec.get("rs_leadership") == "LEADER":
        add(S, "rs_leader", "relative-strength LEADER", {"rs_leadership": "LEADER"})
    rdd = rec.get("rs_down_day_20d")
    if rdd is not None and rdd >= th["rs_down_day_min"]:
        add(S, "rs_resilient", f"holds up on down days (RS {rdd})", {"rs_down_day_20d": rdd})
    kp, ks = rec.get("knn_prob"), rec.get("knn_significant")
    if kp is not None and ks and kp >= th["knn_prob_min"]:
        add(X, "knn_favorable", f"kNN {int(kp*100)}% up (significant)", {"knn_prob": kp})

    # CAUTION
    dv = rec.get("div_state")
    if dv == "BEARISH":
        add(C, "bearish_divergence", f"bearish divergence ({rec.get('div_bear_count')}) — reversal risk", {"div_state": dv, "div_bear_count": rec.get("div_bear_count")})
    elif dv == "BULLISH":
        add(S, "bullish_divergence", "bullish divergence", {"div_state": dv})
    sd = rec.get("sma_distance_pct")
    if sd is not None and sd >= th["overextended_sma_pct"]:
        add(C, "overextended", f"extended +{round(sd,1)}% above SMA — late to chase", {"sma_distance_pct": sd})
    if rec.get("atr_caution") is True:
        add(C, "atr_caution", "ATR caution — volatility elevated", {"atr_caution": True})

    return {"strength": S, "caution": C, "context": X}


def for_voice(rec: dict, voice: str, p: dict | None = None) -> dict:
    """The subset of flags whose framework this voice uses — what it weighs when nominating."""
    allf = derive(rec, p)
    keep = lambda lst: [f for f in lst if voice in f["voices"]]
    return {"strength": keep(allf["strength"]), "caution": keep(allf["caution"]), "context": keep(allf["context"])}


def stamp(rows, tickers=None, p=None):
    """Deterministic stamping for the orchestrator (premarket step 6, D-39): return
    {ticker: {strength, caution, context}} for the given tickers (or all rows). No model judgement."""
    want = set(tickers) if tickers else None
    out = {}
    for r in rows:
        t = r.get("ticker")
        if want is None or t in want:
            out[t] = derive(r, p)
    return out


def _load_rows(path):
    import json
    d = json.load(open(path))
    return d.get("daily_list") or d.get("rows") or d


if __name__ == "__main__":
    import json, sys, collections
    # CLI: `quality_flags.py derive <export.json> [TICKER ...]` -> per-ticker fired flags as JSON.
    #      `quality_flags.py [selftest]` -> tally across the sample export (default).
    if len(sys.argv) > 1 and sys.argv[1] == "derive":
        path = sys.argv[2]
        tickers = sys.argv[3:] or None
        print(json.dumps(stamp(_load_rows(path), tickers), default=str, indent=1))
        sys.exit(0)
    d = json.load(open("/tmp/aqe_daily_export.json"))
    rows = d["daily_list"]
    tally = collections.Counter()
    for r in rows:
        fl = derive(r)
        for b in ("strength", "caution", "context"):
            for f in fl[b]:
                tally[f["flag"]] += 1
    print("quality flags firing across", len(rows), "names:")
    for flag, n in tally.most_common():
        print(f"  {flag:22} {n:>3}  (voices: {', '.join(FLAG_VOICES.get(flag, []))})")
    ex = next(r for r in rows if derive(r)["caution"])
    print("\nexample name with flags:", ex["ticker"], json.dumps(derive(ex), default=str)[:400])
