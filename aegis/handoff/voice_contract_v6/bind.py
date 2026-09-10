#!/usr/bin/env python3
"""bind.py — bind each voice's PM-signed canon (aegis/canon/<voice>/canon.lock.yaml)
to the engine glossary (glossary.lock.json). Emits binding/<voice>.binding.yaml and
aqe_deliverables.json. Deterministic; no judgment beyond the alias table below, which is
the ONLY hand-written part and is printed in every binding file for PM review."""
import json, re, glob, hashlib, sys, os
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
# Layout A (conductor run dir): <run>/contract/bind.py, canon at <run>/aqe_src/aegis/canon
# Layout B (AQE repo):          aegis/handoff/voice_contract_v6/bind.py, canon at aegis/canon
REPO = os.environ.get("AQE_REPO") or (f"{os.path.dirname(ROOT)}/aqe_src" if os.path.isdir(f"{os.path.dirname(ROOT)}/aqe_src") else os.path.abspath(f"{ROOT}/../../.."))
CANON = f"{REPO}/aegis/canon"
_g = [p for p in (f"{ROOT}/glossary.lock.json", f"{ROOT}/glossary.lock.min.json") if os.path.exists(p)][0]
G = json.load(open(_g))["fields"]
_m = [p for p in ("/home/claude/build/aegis-core/skills/pma/contracts/voice_menus.json", f"{REPO}/aegis/contracts/voice_menus.json", f"{ROOT}/voice_menus.v6.json") if os.path.exists(p)][0]
MENUS = json.load(open(_m))

paths = set(G)
leaf = {}
for p in paths:
    leaf.setdefault(p.split(".")[-1], []).append(p)

# ---- alias table: canon vocabulary -> export path, with fit + loss statement ----
# fit: EXACT (same quantity) | PROXY (stands in, loss stated) | DERIVABLE (engine can compute
#      from data it already holds) | ABSENT (engine must add; needs data it does not hold today)
#      | HELD_BOOK (exists only on held_positions rows) | RUNTIME (broker/portfolio, not AQE's job)
#      | OUTPUT (a canon output, not an input) | MACRO (macro layer, served to crown/druck only)
ALIAS = {
    # --- moving averages / oscillators (name drift) ---
    "sma20": ("ma_20", "EXACT", ""), "sma40": ("ma_40", "EXACT", ""), "sma50": ("ma_50", "EXACT", ""),
    "cci20": ("cci_20", "EXACT", ""), "atr_14": ("atr_14d", "EXACT", ""),
    "atr20": ("atr_14d", "PROXY", "window 14 not 20; ~5-10% narrower on trending names"),
    "close": ("entry", "EXACT", "entry == last daily close (drive_sync: round(close,2))"),
    "realised_vol_30d": ("vol_30d_ann", "EXACT", "annualised (x sqrt(252)); rule thresholds must be in annualised terms"),
    "avg_daily_volume": ("elder_context.volume.avg_vol_20d", "PROXY", "20-day mean, absent on 9 radar/QS-only rows"),
    "rvol": ("rvol_20d", "EXACT", ""),
    # --- bracket vocabulary ---
    "entry_price": ("entry", "EXACT", ""), "stop_price": ("bracket.stop", "EXACT", "null when bracket.valid false (71.7% today)"),
    "stop_distance_pct": ("bracket.risk_pct", "EXACT", "percent not fraction; null when bracket invalid"),
    "expected_gain_r": ("bracket.rr", "PROXY", "measured to TP2, not TP1"),
    "target": ("bracket.targets", "PROXY", "AQE targets, not the seat's own"),
    "current_stop": ("held_positions[].held_sl", "HELD_BOOK", ""),
    "monthly_high_11": ("high_52w", "PROXY", "52-week not 11-month"), "monthly_low_11": ("low_52w", "PROXY", "52-week not 11-month"),
    # --- OHLC bars: delivered 2026-09-10 (AQE_INSTRUCTIONS.md §2) ---
    "low": ("bar_low", "EXACT", ""),
    "high": ("bar_high", "EXACT", ""), "open": ("bar_open", "EXACT", ""),
    "prior_bar_high": ("prior_bar_high", "EXACT", ""), "prior_bar_low": ("prior_bar_low", "EXACT", ""),
    "prior_day_low": ("prior_bar_low", "EXACT", "= prior_bar_low"),
    "sma20_slope_5d": ("ma_20_slope_5d_pct", "EXACT", ""),
    "pct_run_10d": ("pct_run_10d", "EXACT", ""),
    "days_since_swing_high": ("days_since_swing_high", "PROXY",
                              "business-day count (weekends excluded, exchange holidays not) — "
                              "an approximation, not an exact trading-session count"),
    "pullback_bar_range": ("bar_range_5d", "PROXY",
                           "last 5 bars unconditionally, not bars scoped to the detected pullback "
                           "specifically — coarser than the canon's own definition"),
    "stock_pct_change_63d": ("ret_63d", "EXACT", ""),
    "index_pct_change_63d": (None, "DERIVABLE",
                             "computed as spy_ret_63d, but that's a top-level export constant "
                             "and nominator TSVs are row-sliced only -- no per-row delivery "
                             "mechanism exists yet, so serving it would be a permanently-null "
                             "column, not real data"),
    "industry_group_pct_change_63d": (None, "DERIVABLE",
                                      "sector ETF 20d roc exists at srm[].roc20 (top-level, "
                                      "keyed by sector, not industry-group 63d anyway), but "
                                      "nominator TSVs are row-sliced only -- no per-ticker "
                                      "lookup into a top-level array exists yet, so this was "
                                      "being served as a permanently-null column"),
    "most_recent_swing_low": ("fib_swing_low", "PROXY", "fib swing, not the seat's own swing definition"),
    "prior_support": ("fib_swing_low", "PROXY", ""), "support_level": ("fib_swing_low", "PROXY", ""),
    "base_low": ("base_low_20d", "EXACT", ""),
    "breakout_bar_low": (None, "ABSENT", "needs OHLC + breakout-bar identification"),
    # --- held book / runtime ---
    "days_held": ("held_positions[].trade_date", "HELD_BOOK", "derive from trade_date"),
    "high_since_entry": (None, "HELD_BOOK", "not published; engine holds the panel — add to held_positions"),
    "portfolio_value": (None, "RUNTIME", "dynCap from aegis journal"), "position_size_pct": (None, "RUNTIME", "sizing is the PM's, not the seat's"),
    "tick_size": (None, "RUNTIME", ""), "bid": (None, "RUNTIME", "broker"), "ask": (None, "RUNTIME", "broker"),
    "implied_vol": (None, "RUNTIME", "not in AQE; Tiger option chain"),
    "universe_membership": ("source", "EXACT", "source label says which list the row came from"),
    "setup_flag": (None, "OUTPUT", "the seat's own output"), "signal_id": (None, "OUTPUT", ""),
    "expected_hold_days": (None, "OUTPUT", "canon constant"), "monitoring_interval": (None, "OUTPUT", ""),
    "gap_risk_flag": ("gap_risk_flag", "EXACT", ""),
    # --- thorp statistics ---
    "candidate_set_vol_rank": (None, "DERIVABLE", "rank of vol_30d_ann within candidate_set; pipeline can compute"),
    "backtest_trade_count": ("cohort_n", "EXACT", ""),
    "signal_edge_current": ("cohort_hit_rate_20d", "EXACT", ""),
    "signal_edge_trailing_median": (None, "ABSENT", "needs hit-rate history; engine keeps one table per run"),
    "rules_generated_count": (None, "OUTPUT", ""), "sample_start": (None, "ABSENT", "hit-rate window t-79..t-20 is fixed; publish as constant"),
    "sample_end": (None, "ABSENT", ""), "candidates_passing_count": (None, "DERIVABLE", "len(candidate_set)"),
    # --- objects / macro ---
    "bracket": ("bracket.*", "EXACT", "object"), "lens": ("lens.*", "EXACT", "object; lens.extension is a constant null by PM ruling"),
    "srm": ("srm[].*", "MACRO", ""), "regime": ("regime.*", "MACRO", ""), "srm_weather": ("macro_weather.*", "MACRO", ""),
    "macro_brief": (None, "MACRO", "crown macro form, not export"), "lens_ranking": ("lens_ranking.*", "EXACT", "top-level object"),
    "signal_radar": ("signal_radar.*", "EXACT", "top-level object"), "ptrs": (None, "ABSENT", "not found in export or engine"),
    "hl_score": ("held_positions[].hl_score", "HELD_BOOK", ""), "hl_state": ("held_positions[].hl_state", "HELD_BOOK", ""),
    "lens_ranking.method": ("lens_ranking.*", "EXACT", "member of top-level object"), "lens_ranking.ranked": ("lens_ranking.*", "EXACT", "member"),
    "lens_ranking.full_data_in": ("lens_ranking.*", "EXACT", "member"),
    "signal_radar.scan_date": ("signal_radar.*", "EXACT", "member"), "signal_radar.n_scored": ("signal_radar.*", "EXACT", "member"),
    "signal_radar.note": ("signal_radar.*", "EXACT", "member"),
    "regime.implication": (None, "ABSENT", "export regime has only {vix, level}; canon wants the level's implication text -> publish or map from regime_stop_pct_ceiling"),
    "regime.trend": (None, "ABSENT", "export regime has no trend key; spy_roc_20d + intermarket.spy_iwm serve as PROXY"),
}
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())

def resolve(f):
    f = str(f)
    if f.startswith("NOT_SERVED"):
        return (None, "ABSENT", f)
    if f in ALIAS:
        return ALIAS[f]
    if f in paths:
        return (f, "EXACT", "")
    if f in leaf and len(leaf[f]) == 1:
        return (leaf[f][0], "EXACT", "")
    # wildcard object refs like srm[].grade, thematic_baskets.*.grade, intermarket.tlt.roc20
    for p in paths:
        if p == f or p.replace("[]", "").replace(".*", "") == f.replace("[]", "").replace(".*", ""):
            return (p, "EXACT", "")
    for p in paths:
        if norm(p.split(".")[-1]) == norm(f):
            return (p, "EXACT", "name drift only")
    return (None, "ABSENT", "no alias, no path")

def gl(path):
    if not path: return None
    if path.endswith(".*") or path.endswith("[].*"):
        return {"object": path, "members": sorted(p for p in paths if p.startswith(path[:-2]))[:40]}
    e = G.get(path)
    if not e:
        # macro/held wildcards not in glossary by exact key
        cands = [p for p in paths if p.endswith(path.split("[].")[-1])]
        e = G.get(cands[0]) if cands else None
    if not e: return {"path": path, "glossary": "MISSING"}
    return {k: e[k] for k in ("definition", "formula", "engine_source", "units", "direction", "null_means", "granularity", "enum", "known_traps")}

os.makedirs(f"{ROOT}/binding", exist_ok=True)
deliver = {}
summary = []
for cf in sorted(glob.glob(f"{CANON}/*/canon.lock.yaml")):
    c = yaml.safe_load(open(cf)); v = c["voice"]
    rc = c.get("recognisers") or []
    if isinstance(rc, dict): rc = list(rc.values())
    use = {}
    for r in rc:
        if not isinstance(r, dict): continue
        fl = r.get("fields") or []
        if isinstance(fl, str): fl = [fl]
        for f in fl:
            use.setdefault(str(f), []).append({"rule": r.get("id"), "if": (r.get("if") or "")[:200]})
    rows = []
    fits = {}
    for f, rules in sorted(use.items()):
        path, fit, loss = resolve(f)
        fits[fit] = fits.get(fit, 0) + 1
        row = {"canon_field": f, "export_path": path, "fit": fit, "loss": loss, "rules": rules}
        if path: row["glossary"] = gl(path)
        rows.append(row)
        if fit in ("ABSENT", "DERIVABLE"):
            deliver.setdefault(f, {"fit": fit, "note": loss, "wanted_by": []})["wanted_by"].append({"voice": v, "rules": [x["rule"] for x in rules]})
    menu = MENUS.get(v) or []
    canon_paths = {r["export_path"] for r in rows if r["export_path"]}
    on_menu_not_canon = sorted(m for m in menu if m not in canon_paths and not any(m.startswith(cp[:-2]) for cp in canon_paths if cp.endswith(".*")))
    out = {
        "voice": v, "pm_signed": c.get("pm_signed"), "canon_diff_sha": c.get("diff_sha"),
        "generated": "2026-09-09", "glossary_sha": hashlib.sha256(open(_g,"rb").read()).hexdigest()[:16],
        "fit_counts": fits,
        "bindings": rows,
        "menu_fields_no_canon_rule": on_menu_not_canon,
        "alias_table_note": "ALIAS in bind.py is the only hand-written mapping; every other row is an exact path match.",
    }
    yaml.safe_dump(out, open(f"{ROOT}/binding/{v}.binding.yaml", "w"), sort_keys=False, width=110, allow_unicode=True)
    summary.append((v, len(rows), fits, len(menu), len(on_menu_not_canon)))
json.dump(deliver, open(f"{ROOT}/aqe_deliverables.json", "w"), indent=1)
for s in summary:
    print(f"{s[0]:14s} canon_fields={s[1]:3d} fits={s[2]}  menu={s[3]} menu_without_rule={s[4]}")
print("deliverables:", len(deliver))
