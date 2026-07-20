#!/usr/bin/env python3
"""
subscore_board.py — the DATA-ONLY top-picks board (D-60).

Deterministic (constitution law 4: code computes, models judge). NO models, no
tokens. Runs every premarket and is ATTACHED to the consensus nomination tally,
so the PM sees — next to WHO the voices nominated — how the raw AQE sub-scores
rank the same universe three ways:
  1) DETECT LENS alone            — lens_positive (count of 6 sub-lenses strong)
  2) EACH VOICE alone             — its own menu fields, ranked (what the sub-scores say)
  3) DATA-ONLY TIERING            — agreement across 3 ORTHOGONAL axes:
        - voice breadth  (how many voices' top-3 a name lands in)
        - detect strength (lens_positive)
        - elder force    (sustained elder_5d)

This is a TRANSPARENCY / decision-support view, NOT a gate (D-4/D-52 spirit): it
ranks and tiers, it never removes or advances a name. The committee still votes
on top of it. The DIVERGENCE between this board and the swarm tally is itself
signal — where pure data likes a name the sector/bellwether read kills (or vice
versa) is exactly where judgment earns its keep.

CLI:
  subscore_board.py --export output/aqe_daily_export.json --universe data/sod/DATE/universe.json
  subscore_board.py --tickers FBP,PSX,VLY,...   [--consensus FBP:6,PSX:5,...]  [--render]
"""
import json, os, argparse

# Each voice's DISCRIMINATING menu fields (field, direction). +1 higher-better, -1 lower-better.
# Mirrors VOICE_MENUS; seow/detect-lens/elder-lens use special metrics below.
VOICE_SPECS = {
    "lynch":        [("sc_momentum", 1), ("structure", 1), ("flow", 1), ("rvol", 1), ("rs_spy_20d", 1)],
    "oneil":        [("rs_spy_20d", 1), ("elder", 1), ("rvol", 1), ("structure", 1), ("sma_distance_pct", -1)],
    "wyckoff":      [("flow", 1), ("energy", 1), ("rvol", 1)],
    "raschke":      [("elder", 1), ("energy", 1)],
    "steenbarger":  [("sc_momentum", 1), ("rvol", 1)],
    "minervini":    [("structure", 1), ("rs_spy_20d", 1), ("sma_distance_pct", -1)],
    "druckenmiller":[("beta_30d", -1), ("sc_momentum", 1)],
    "thorp":        [("sc_momentum", 1), ("bracket.rr", 1)],   # thorp's OWN menu only; bracket.rr null pre-exercise -> proxy, flagged
}
# axis thresholds for tiering
BREADTH_STRONG = 3      # in >=3 voices' top-3
DETECT_STRONG = 4       # >=4 of 6 sub-lenses
ELDER_STRONG = 0.80     # sustained elder force


def _num(v):
    return v if isinstance(v, (int, float)) else None


def _pctiles(pairs):
    """pairs: list of (ticker, value). Missing values sink to 0 percentile. Ties averaged-up."""
    vals = [v for _, v in pairs if v is not None]
    out = {}
    n = len(vals) if vals else 1
    for t, v in pairs:
        if v is None:
            out[t] = 0.0
        else:
            out[t] = sum(1 for y in vals if y <= v) / n
    return out


def _get(r, f):
    """Resolve a possibly-dotted field path (e.g. 'bracket.rr') against the record."""
    cur = r
    for part in f.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _field(records, f):
    return {t: _num(_get(r, f)) for t, r in records.items()}


def _ma_align(r):
    p = (r.get("bracket", {}) or {}).get("price") or r.get("entry")
    if not p:
        return 0.0
    mas = [r.get(k) for k in ("ma_20", "ma_50", "ma_100", "ma_200")]
    mas = [m for m in mas if isinstance(m, (int, float))]
    return sum(1 for m in mas if p > m) / len(mas) if mas else 0.0


def _elder_force(r):
    e5 = r.get("elder_5d") or []
    base = sum(e5[-3:]) / 3 / 10 if len(e5) >= 3 else 0.0
    if r.get("elder_pattern") == "INTERRUPTED":
        base -= 0.25
    if r.get("mp_state") != "STRONG":
        base -= 0.15
    return max(0.0, round(base, 3))


def compute(records, lens_positive):
    U = list(records.keys())
    # --- per-voice composite (mean of percentile-normalised menu fields) ---
    voice_score = {}
    for v, specs in VOICE_SPECS.items():
        parts = {t: [] for t in U}
        for f, dr in specs:
            fp = _pctiles([(t, _field(records, f)[t]) for t in U])
            for t in U:
                parts[t].append(fp[t] if dr > 0 else 1 - fp[t])
        voice_score[v] = {t: round(sum(parts[t]) / len(parts[t]), 3) for t in U}
    # seow: MA-stack alignment + not-extended
    ext = _pctiles([(t, _field(records, "sma_distance_pct")[t]) for t in U])
    voice_score["seow"] = {t: round((_ma_align(records[t]) + (1 - ext[t])) / 2, 3) for t in U}
    # detect-lens: lens_positive/6 ; elder-lens: elder force
    voice_score["detect-lens"] = {t: round(lens_positive.get(t, 0) / 6, 3) for t in U}
    voice_score["elder-lens"] = {t: _elder_force(records[t]) for t in U}

    top_by_voice = {v: sorted(U, key=lambda t: -sc[t])[:3] for v, sc in voice_score.items()}

    # --- breadth + axes + tiers ---
    breadth = {t: 0 for t in U}
    for v, names in top_by_voice.items():
        for t in names:
            breadth[t] += 1
    tiers = {t: {} for t in U}
    for t in U:
        dp = lens_positive.get(t, 0)
        ef = _elder_force(records[t])
        axes = int(breadth[t] >= BREADTH_STRONG) + int(dp >= DETECT_STRONG) + int(ef >= ELDER_STRONG)
        tier = 1 if axes >= 2 else (2 if axes == 1 else 3)
        tiers[t] = {"tier": tier, "axes_strong": axes, "breadth": breadth[t],
                    "detect": dp, "elder_force": ef, "sector": records[t].get("gics_sector")}
    return {"voice_score": voice_score, "top_by_voice": top_by_voice, "tiers": tiers}


def _load_records(export, universe=None, tickers=None):
    d = json.load(open(export))
    dl = {r["ticker"]: r for r in d.get("daily_list", [])}
    lens = {x["ticker"]: x.get("positive", 0) for x in d.get("lens_ranking", {}).get("ranked", [])}
    if tickers:
        U = [t for t in tickers if t in dl]
    elif universe and os.path.exists(universe):
        uj = json.load(open(universe))
        cand = uj.get("candidates", uj if isinstance(uj, list) else [])
        U = [(c.get("t") or c.get("ticker") if isinstance(c, dict) else c) for c in cand]
        U = [t for t in U if t in dl]
    else:  # fallback: screened top by rank
        U = [r["ticker"] for r in sorted(d.get("daily_list", []), key=lambda r: r.get("rank", 9999))[:40]]
    return {t: dl[t] for t in U}, {t: lens.get(t, 0) for t in U}


def render(board, lens_positive, records, consensus=None):
    L, T = board["top_by_voice"], board["tiers"]
    lines = ["## DATA BOARD — pure AQE sub-scores (deterministic, no models; D-60)"]
    # detect lens
    dl_top = sorted(records.keys(), key=lambda t: -lens_positive.get(t, 0))[:8]
    lines.append("\n**Detect lens alone (lens_positive /6):** " +
                 ", ".join(f"{t} {lens_positive.get(t,0)}/6" for t in dl_top))
    # per voice
    lines.append("\n**Each voice alone (top pick by its own sub-scores):**")
    for v in list(VOICE_SPECS) + ["seow", "detect-lens", "elder-lens"]:
        flag = " *(rr-null proxy)*" if v == "thorp" else ""
        lines.append(f"- {v}: {' > '.join(L[v])}{flag}")
    # tiers
    lines.append("\n**Data-only tiering (agreement across breadth / detect / elder force):**")
    for tier in (1, 2, 3):
        names = sorted([t for t in T if T[t]["tier"] == tier], key=lambda t: -T[t]["axes_strong"])
        if not names:
            continue
        def tag(t):
            c = f"·{consensus[t]}v" if consensus and t in consensus else ""
            return f"{t}(b{T[t]['breadth']}/d{T[t]['detect']}/e{T[t]['elder_force']},{T[t]['sector']}{c})"
        lines.append(f"- **Tier {tier}:** " + ", ".join(tag(t) for t in names[:10]))
    if consensus:
        board_t1 = {t for t in T if T[t]["tier"] == 1}
        cons = set(consensus)
        lines.append(f"\n**Board↔consensus:** agree = {sorted(board_t1 & cons) or '—'} · "
                     f"data-only (board T1, low consensus) = {sorted(board_t1 - cons) or '—'} · "
                     f"consensus-only (voted, not data-T1) = {sorted(cons - board_t1) or '—'} "
                     "— the divergence is where judgment/sector read matters.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Aegis data-only sub-score board (D-60, deterministic)")
    ap.add_argument("--export", default="output/aqe_daily_export.json")
    ap.add_argument("--universe")
    ap.add_argument("--tickers")
    ap.add_argument("--consensus", help="T:count,T:count — the nomination tally to annotate against")
    ap.add_argument("--out")
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args(argv)
    tickers = [t.strip() for t in a.tickers.split(",")] if a.tickers else None
    consensus = None
    if a.consensus:
        consensus = {kv.split(":")[0]: int(kv.split(":")[1]) for kv in a.consensus.split(",") if ":" in kv}
    records, lens = _load_records(a.export, a.universe, tickers)
    board = compute(records, lens)
    board["_meta"] = {"n": len(records), "thresholds": {"breadth": BREADTH_STRONG, "detect": DETECT_STRONG, "elder": ELDER_STRONG}}
    if a.out:
        json.dump(board, open(a.out, "w"), indent=1)
    if a.render or not a.out:
        print(render(board, lens, records, consensus))
    return board


if __name__ == "__main__":
    main()
