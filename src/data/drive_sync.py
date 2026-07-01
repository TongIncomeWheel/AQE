"""Google Drive sync — export the daily scan to one Google Drive folder.

Single destination: the Drive folder pinned by ID in `gdrive_uploader.py`
(GDRIVE_FOLDER_ID, default = the linked AQE folder). Written via the Drive
REST API only — there are NO local Drive-mount writes.

  aqe_daily_export.json  (scan + SRM combined, overwritten each run)

The committee reads this one file. SRM grading is embedded as the export's
`srm` / `srm_signals` sections, so there is no separate SRM file.
A copy is also written to the local OUTPUT_DIR — that is the app's own working
file (read by the UI in cloud mode), not a user-facing Drive folder.

Each run overwrites the same filename so the Drive folder never clutters.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.analyzer.ptrs import compute_ptrs
from src.data.sector_mapper import (
    ETF_TO_NAME,
    SECTOR_MAP_DRIVE_FILENAME,
    SECTOR_MAP_FOLDER_ID,
    load_sector_map,
)
from src.engines.srm import (
    GICS_ETFS, get_sector_health, grade_all_sectors,
    enrich_sectors_intermarket, load_intermarket_cache,
    TICKER_TO_THEMATIC, TICKER_TO_THEMATICS, grade_thematic_baskets,
)
from src.scanner.betas import load_betas
from src.scanner.levels import load_elder_history, load_trade_levels

from src.data.paths import OUTPUT_DIR, PROJECT_ROOT  # single source of truth

# Drive destination is the folder pinned in gdrive_uploader (by ID), reached
# via the REST API. No local Drive-mount path.
EXPORT_FILENAME = "aqe_daily_export.json"

# Sector RAG map (AQE Data Schema Spec v1.0 §6) — published as a SINGLE file to
# a dedicated Drive subfolder (the round-trip source of truth; folder + filename
# defined in sector_mapper). AQE restores it on startup, auto-sources GICS for
# any blank, and overwrites the one file each run. Version stamps the run date.
SECTOR_MAP_FILENAME = SECTOR_MAP_DRIVE_FILENAME

# Self-describing schema legend shipped at the top of every export so the AIC
# reads each level correctly and never confuses a STOP with a TARGET with an
# ENTRY. Direction convention (LONG setups): STOPS sit BELOW entry, TARGETS sit
# ABOVE entry. Prices are absolute USD unless the field ends in _rr / _ratio /
# _pct / _ann. AQE exports DATA + computed LEVELS only — no sizing, no decisions.
_FIELD_GLOSSARY = {
    "_convention": (
        "LONG setups: STOPS are BELOW entry, TARGETS are ABOVE entry. Values are "
        "absolute USD prices unless the name ends in _rr/_ratio/_pct/_ann (ratios) "
        "or is a list/object. 'rr' = reward-to-risk in R, where 1R = dsl_risk."
    ),
    "entry": "Reference entry = prior close-of-day. The live fill is the IBKR price at "
             "bracket time, NOT this value.",
    "dsl_stop": "Primary protective STOP (below entry): β-adjusted structural stop = "
                "recent 5-session low − 0.5·ATR, clamped to [0.75, 2.0–2.5]×ATR.",
    "dsl_risk": "1R in USD = entry − dsl_stop. The risk unit every R-multiple uses.",
    "dsl_atr_ratio": "Stop width in ATRs = dsl_risk / atr_14d (ratio).",
    "dsl_rr_pct": "Risk per share as a percent of entry = dsl_risk / entry × 100 (pct).",
    "dsl_tp_1r/2r/3r": "MECHANICAL targets = entry + 1/2/3 × dsl_risk. These drive the "
                       "DSL trail tiers + the win-rate backtest — they are NOT a move "
                       "forecast. For profit-taking on real structure use structural_targets.",
    "atr_14d": "14-day Average True Range in USD (the volatility unit).",
    "coil_entry": "An ENTRY level (not a stop/target) = dsl_stop + atr_14d (1×ATR above "
                  "the stop) — the optimal resting-limit entry. A PULLBACK limit that sits "
                  "≤ entry except when the stop is < 1×ATR (dsl_atr_ratio<1); its side vs "
                  "entry therefore varies, so field_schema tags it side:n/a.",
    "max_chase_tp2": "Max ENTRY price where R:R to dsl_tp_2r stays ≥ 2.0. Above it, a TP2 "
                     "plan is no longer 2R — stand down or switch target.",
    "max_chase_tp3": "Max ENTRY price where R:R to dsl_tp_3r stays ≥ 2.0.",
    "rr_tp2_at_coil": "R:R to dsl_tp_2r if entered at coil_entry (ratio). Reference only — "
                      "computed off the reference entry; recomputed at the live fill per §4.4.",
    "rr_tp3_at_coil": "R:R to dsl_tp_3r if entered at coil_entry (ratio). Reference only — "
                      "computed off the reference entry; recomputed at the live fill per §4.4.",
    "optimal_stop": "The OPERATIVE stop = strongest+closest valid level (best of "
                    "dsl_stop / fib / MA / swing below entry) passing ALL 3 charter §4.2 "
                    "gates: atr_ratio≥1.0, rr_tp2≥2.0, AND risk_pct≤regime ceiling "
                    "(GREEN 12% / YELLOW 8% / ORANGE 6% / RED 4%). "
                    "{price,type,atr_ratio,rr_tp2,risk_pct,risk_usd,regime_valid}. "
                    "**risk_usd = entry − price is the RISK to size against — NOT dsl_risk.** "
                    "This is the fully validated stop — no further regime check needed.",
    "structural_levels": "VALID candidate STOPS below entry from structure (dsl_stop/swing_low/"
                         "swing_low_1/2/3/ma_cluster/fib_618/fib_786/ma20-200). ONLY levels "
                         "passing all 3 gates (atr_ratio≥1.0, rr_tp2≥2.0, risk_pct≤regime "
                         "ceiling) are included. Each {type,price,atr_ratio,rr_tp2,risk_pct,"
                         "valid,regime_valid}. structural_levels_total = how many candidates "
                         "were evaluated (valid + invalid).",
    "structural_levels_total": "Total candidate stops evaluated before filtering to valid-only "
                               "(integer). Compare to len(structural_levels) to see how many "
                               "were eliminated by the 3-gate filter.",
    "structural_targets": "THE take-profit levels. ABOVE entry, anchored to REAL structure: "
                          "type 'resistance' = prior confirmed pivot-high overhead; "
                          "'prior_high' = current swing peak; 'fib_1272/1618/2000/2618' = "
                          "measured-move extensions. Each {type,price,rr,r_optimal,"
                          "r_optimal_source}: **r_optimal** = R vs the structural risk "
                          "(optimal_stop.risk_usd when available, else dsl_risk — "
                          "r_optimal_source tells which: 'structural' or 'dsl_risk'). "
                          "TAKE PROFIT against these PRICES nearest-first — NEVER off "
                          "dsl_tp_Nr (those are mechanical entry + N×dsl_risk, not a target). "
                          "Empty only when no structure anchors exist above price.",
    "fib_swing_low/high": "Anchors of the current detected up-swing (absolute USD).",
    "fib_236/382/500/618/786": "Fib RETRACEMENT supports below the swing high — potential "
                               "pullback/STOP levels (absolute USD).",
    "ma_20/50/100/200": "Simple moving averages (absolute USD) — dynamic support/resistance.",
    "vol_30d_ann": "30-day annualised realised volatility (decimal: 0.18 = 18%). This IS "
                   "the Charter §4.5 operative sizing vol (the charter calls it 'vol_30d'; "
                   "AQE's field is annualised — same number). For"
                   "sizing/VaR, not a target.",
    "beta_252d": "1-year beta vs SPY (cov/var).",
    "ptrs": "Engine score + sector health. Disposition/sizing is the committee's call — "
            "AQE exports no sizing.",
    # Enrichment Spec v2.0 — new per-record signals + cleanup flags
    "rs_down_day_20d": "All-weather leadership: stock's avg outperformance vs SPY on SPY "
                       "DOWN days (last 20 sessions). Positive = beats SPY when market "
                       "drops = genuine leader (pct).",
    "rs_leadership": "Classification from rs_down_day_20d: LEADER (>+0.25), IN-LINE, "
                     "LAGGARD (<−0.25).",
    "setup_state": "Daily lifecycle classification: EXTENDED (>8% above MA10, do not chase) "
                   "/ BREAKOUT-READY (VCP + VWAP above + exhaustion clear) / "
                   "CONTINUATION-READY (MA stack bullish + near MA10) / BASING (coil "
                   "forming, not yet at trigger).",
    "breakout_conviction": "Quality score (0–100) of the most recent expansion bar "
                           "(range > 1.3× base avg). Higher = higher-quality breakout.",
    "breakout_grade": "Letter grade from breakout_conviction: A (≥80) / B (≥65) / "
                      "C (≥50) / D (<50).",
    "breakout_pattern": "Named pattern of the most recent expansion bar: "
                        "TELEGRAPHED_CONTINUATION / ABSORPTION_REVERSAL / "
                        "SURPRISE_THRUST / STANDARD_BREAKOUT.",
    "breakout_bar_date": "Date of the most recent expansion bar (YYYY-MM-DD).",
    "atr_caution": "True if dsl_atr_ratio was floored to 1.5 in YELLOW/ORANGE/RED regime "
                   "(the structural stop was too tight for the regime).",
    "beta_data_error": "True if beta_60d exceeded ±5.0 (data error; capped value in "
                       "beta_60d_capped).",
    "malformed_bracket": "True if the DSL stop sits within 0.5% of entry (bracket is "
                         "unusable — stop virtually at entry).",
    "beta_60d_capped": "beta_60d capped at ±5.0 (use this; raw beta_60d may be a data "
                       "error).",
    "dsl_atr_ratio_floored": "dsl_atr_ratio floored at 1.5 in YELLOW+ regime (use this "
                             "for sizing; raw dsl_atr_ratio may be sub-ATR).",
    # Readiness Score — entry timing
    "rd_score": "Readiness composite (0-100). Measures compression + trigger signals. "
                "READY (80+) / WATCH (60-79) / NEUTRAL (40-59) / NOT_READY (<40).",
    "rd_state": "Readiness state label: READY / WATCH / NEUTRAL / NOT_READY.",
    "rd_compression": "Compression sub-score (0-60). Tight range + dry volume + EMA convergence.",
    "rd_trigger": "Trigger sub-score (0-25). Range expansion + volume surge from compression.",
    "rd_pos_mod": "Position modifier (-15 to 0). Penalty for already-extended names.",
    "rd_rs_bonus": "RS acceleration bonus (0-15). Positive when outperforming SPY recently.",
    # Health Score — position maintenance
    "hl_score": "Health composite (0-100). Measures trend integrity for held positions. "
                "HOLD_ADD (75+) / HOLD (50-74) / TIGHTEN (30-49) / EXIT (<30).",
    "hl_state": "Health state label: HOLD_ADD / HOLD / TIGHTEN / EXIT.",
    "hl_trend": "Trend structure sub-score (0-35). Higher lows + bars above EMA21.",
    "hl_flow": "Flow confirmation sub-score (0-25). MFI health + volume up/down ratio.",
    "hl_rs": "Relative strength sub-score (0-20). RS vs SPY maintenance.",
    "hl_risk": "Risk flags penalty (-20 to 0). ATR spike + close weakness + EMA breakdown.",
}

# HARD GUARD — machine-readable schema the AIC keys off STRUCTURALLY (not prose).
# Every tradeable level carries an explicit role/unit/side so a stop can never be
# read as a target, a ratio as a price, or a level on the wrong side of entry.
# Controlled vocabularies (any reader can validate against these enums):
_FIELD_SCHEMA_ENUMS = {
    "role": ["entry", "reference", "stop", "target", "fib_support",
             "moving_average", "risk_metric", "volatility", "ratio",
             "signal", "flag"],
    "unit": ["usd", "r_multiple", "ratio", "pct", "atr", "decimal",
             "score", "label", "boolean", "date"],
    "side": ["below_entry", "above_entry", "at_entry", "n/a"],
}


def _fs(role: str, unit: str, side: str) -> dict:
    return {"role": role, "unit": unit, "side": side}


_FIELD_SCHEMA = {
    "entry":          _fs("reference", "usd", "at_entry"),
    "dsl_stop":       _fs("stop", "usd", "below_entry"),
    "dsl_risk":       _fs("risk_metric", "usd", "n/a"),
    "dsl_atr_ratio":  _fs("ratio", "atr", "n/a"),
    "dsl_rr_pct":     _fs("ratio", "pct", "n/a"),
    "dsl_tp_1r":      _fs("target", "usd", "above_entry"),
    "dsl_tp_2r":      _fs("target", "usd", "above_entry"),
    "dsl_tp_3r":      _fs("target", "usd", "above_entry"),
    "atr_14d":        _fs("volatility", "usd", "n/a"),
    "coil_entry":     _fs("entry", "usd", "n/a"),
    "max_chase_tp2":  _fs("entry", "usd", "above_entry"),
    "max_chase_tp3":  _fs("entry", "usd", "above_entry"),
    "rr_tp2_at_coil": _fs("ratio", "r_multiple", "n/a"),
    "rr_tp3_at_coil": _fs("ratio", "r_multiple", "n/a"),
    "optimal_stop":   _fs("stop", "usd", "below_entry"),
    "structural_levels":  _fs("stop", "usd", "below_entry"),
    "structural_levels_total": _fs("ratio", "decimal", "n/a"),
    "structural_targets": _fs("target", "usd", "above_entry"),
    "fib_swing_low":  _fs("reference", "usd", "n/a"),
    "fib_swing_high": _fs("reference", "usd", "n/a"),
    "fib_236":        _fs("fib_support", "usd", "n/a"),
    "fib_382":        _fs("fib_support", "usd", "n/a"),
    "fib_500":        _fs("fib_support", "usd", "n/a"),
    "fib_618":        _fs("fib_support", "usd", "n/a"),
    "fib_786":        _fs("fib_support", "usd", "n/a"),
    "ma_20":          _fs("moving_average", "usd", "n/a"),
    "ma_50":          _fs("moving_average", "usd", "n/a"),
    "ma_100":         _fs("moving_average", "usd", "n/a"),
    "ma_200":         _fs("moving_average", "usd", "n/a"),
    "vol_30d_ann":    _fs("volatility", "decimal", "n/a"),
    "beta_252d":      _fs("risk_metric", "ratio", "n/a"),
    # Enrichment Spec v2.0
    "rs_down_day_20d":      _fs("signal", "pct", "n/a"),
    "rs_leadership":        _fs("signal", "label", "n/a"),
    "setup_state":          _fs("signal", "label", "n/a"),
    "breakout_conviction":  _fs("signal", "score", "n/a"),
    "breakout_grade":       _fs("signal", "label", "n/a"),
    "breakout_pattern":     _fs("signal", "label", "n/a"),
    "breakout_bar_date":    _fs("reference", "date", "n/a"),
    "atr_caution":          _fs("flag", "boolean", "n/a"),
    "beta_data_error":      _fs("flag", "boolean", "n/a"),
    "malformed_bracket":    _fs("flag", "boolean", "n/a"),
    "beta_60d_capped":      _fs("risk_metric", "ratio", "n/a"),
    "dsl_atr_ratio_floored": _fs("ratio", "atr", "n/a"),
    # Readiness / Health
    "rd_score":             _fs("signal", "score", "n/a"),
    "rd_state":             _fs("signal", "label", "n/a"),
    "rd_compression":       _fs("signal", "score", "n/a"),
    "rd_trigger":           _fs("signal", "score", "n/a"),
    "rd_pos_mod":           _fs("signal", "score", "n/a"),
    "rd_rs_bonus":          _fs("signal", "score", "n/a"),
    "hl_score":             _fs("signal", "score", "n/a"),
    "hl_state":             _fs("signal", "label", "n/a"),
    "hl_trend":             _fs("signal", "score", "n/a"),
    "hl_flow":              _fs("signal", "score", "n/a"),
    "hl_rs":                _fs("signal", "score", "n/a"),
    "hl_risk":              _fs("signal", "score", "n/a"),
}


def _rank_explain(pipe_rank: float, floor: float, sc_mom: float,
                  pe_qualified: bool, ticker: str,
                  sm: dict, sector_grades: dict) -> str:
    """1-liner explaining why a ticker sits at its rank."""
    parts: list[str] = []
    pr = pipe_rank or 0
    fl = floor or 0
    if pr >= 80:
        parts.append(f"PipeRk {pr:.0f} leads")
    elif pr >= 60:
        parts.append(f"PipeRk {pr:.0f}")
    elif pr > 0:
        parts.append(f"PipeRk {pr:.0f} caps rank")
    else:
        parts.append("No PipeRk")
    if pe_qualified:
        parts.append("PE pick")
    if pr <= 0:
        parts.append(f"Floor {fl:.0f} sorts")
    elif fl >= 70 and pr < 70:
        parts.append(f"engines strong (Floor {fl:.0f})")
    elif fl < 45 and pr > 0:
        parts.append(f"Floor {fl:.0f} drags")
    etf = sm.get(ticker, "")
    grade = sector_grades.get(etf, {}).get("grade", "")
    if grade == "DEPLOY":
        parts.append("sector DEPLOY")
    elif grade == "AVOID":
        parts.append("sector AVOID")
    return "; ".join(parts) if parts else ""


def _build_srm_gics() -> tuple[list[dict], dict, dict, dict]:
    """Full 11-sector SRM grading with trend data + DSG-18/19 intermarket.

    Returns (srm_gics_array, srm_signals_dict, macro_weather_dict, intermarket_dict).
    srm_gics: one row per sector (sorted DEPLOY→AVOID) with grade, sh_value,
              roc20, roc5, divergence, above_sma20, sh_trend, grade_trend,
              + DSG-18 RRG fields + DSG-19 macro fields + combined gate.
    srm_signals: {deploy, hold, turning, watch, avoid, blocked} ETF lists.
    macro_weather: global macro weather summary.
    intermarket: §3A.6 COB intermarket brief (UUP/TLT/HYG/SPY-IWM + posture).
    """
    import pandas as pd
    from src.data.paths import PANEL_DAILY as panel_path

    empty_signals = {"deploy": [], "hold": [], "turning": [], "watch": [], "avoid": [], "blocked": []}

    if not panel_path.exists():
        return [], empty_signals, {}, {}
    panel = pd.read_parquet(panel_path, columns=["date", "ticker", "close"])
    etfs_plus = set(GICS_ETFS) | {"SPY"}
    panel = panel[panel["ticker"].isin(etfs_plus)]
    if panel.empty:
        return [], empty_signals, {}, {}

    graded = grade_all_sectors(panel, trend_days=10)

    # DSG-18: RRG from panel (SPY + sectors are in the panel)
    # DSG-19: macro from the intermarket cache saved by the orchestrator
    cache = load_intermarket_cache()
    macro_data_for_enrich = None  # we don't re-fetch; use cached results instead
    enrich_sectors_intermarket(graded, panel, macro_data_for_enrich)

    # Overlay cached macro results (orchestrator had the FMP macro data)
    if cache and cache.get("sectors"):
        for etf, cached_fields in cache["sectors"].items():
            if etf in graded:
                for k in ("macro_headwind_score", "macro_headwind_flag",
                          "entry_gate", "entry_gate_reason"):
                    if k in cached_fields:
                        graded[etf][k] = cached_fields[k]

    macro_weather = (cache or {}).get("macro_weather", {})
    intermarket = (cache or {}).get("intermarket", {})

    grade_order = {"DEPLOY": 0, "HOLD": 1, "TURNING": 2, "WATCH": 3, "AVOID": 4}

    rows = []
    for etf in GICS_ETFS:
        if etf in graded:
            info = graded[etf]
            rows.append({
                "etf": etf,
                "sector": ETF_TO_NAME.get(etf, etf),
                "grade": info.get("grade", "WATCH"),
                "trend_state": info.get("trend_state", ""),
                "sh_value": info.get("sh", 0),
                "roc20": info.get("roc20", 0.0),
                "roc5": info.get("roc5", 0.0),
                "divergence": info.get("divergence", 0.0),
                "above_sma20": info.get("above_sma20", False),
                "sh_trend": info.get("sh_trend", []),
                "grade_trend": info.get("grade_trend", []),
                "rrg_rs_ratio": info.get("rrg_rs_ratio"),
                "rrg_rs_momentum": info.get("rrg_rs_momentum"),
                "rrg_quadrant": info.get("rrg_quadrant"),
                "rrg_direction": info.get("rrg_direction"),
                "rrg_grade_override": info.get("rrg_grade_override"),
                "macro_headwind_score": info.get("macro_headwind_score"),
                "macro_headwind_flag": info.get("macro_headwind_flag"),
                "entry_gate": info.get("entry_gate"),
                "entry_gate_reason": info.get("entry_gate_reason"),
            })
        else:
            rows.append({
                "etf": etf,
                "sector": ETF_TO_NAME.get(etf, etf),
                "grade": "NO_DATA",
                "trend_state": "",
                "sh_value": -5,
                "roc20": 0.0,
                "roc5": 0.0,
                "divergence": 0.0,
                "above_sma20": False,
                "sh_trend": [],
                "grade_trend": [],
                "rrg_rs_ratio": None,
                "rrg_rs_momentum": None,
                "rrg_quadrant": "NO_DATA",
                "rrg_direction": "STABLE",
                "rrg_grade_override": None,
                "macro_headwind_score": None,
                "macro_headwind_flag": "NO_DATA",
                "entry_gate": "WATCH",
                "entry_gate_reason": "No data",
            })

    rows.sort(key=lambda r: grade_order.get(r["grade"], 3))

    signals: dict[str, list[str]] = {"deploy": [], "hold": [], "turning": [], "watch": [], "avoid": [], "blocked": []}
    for r in rows:
        g = r["grade"].lower()
        if g in signals:
            signals[g].append(r["etf"])
        if g == "avoid" or g == "no_data":
            signals["blocked"].append(r["etf"])
        if r.get("entry_gate") == "BLOCKED" and r["etf"] not in signals["blocked"]:
            signals["blocked"].append(r["etf"])

    return rows, signals, macro_weather, intermarket


def _compute_v21_lookups(sm: dict) -> dict:
    """Per-ticker lookups for AQE v2.1 fields. Defensive — returns {} on any error.

    Returns {rvol, rs, sma, corr, spy_roc_20d} where rvol/rs/sma are
    {ticker: float} and corr is {ticker: (corr, class)}.
    """
    out = {"rvol": {}, "rs": {}, "sma": {}, "ma": {}, "corr": {},
           "vol30": {}, "beta252": {}, "spy_roc_20d": None}
    try:
        import numpy as np
        import pandas as pd
        from src.data.paths import PANEL_DAILY, SPY_DAILY

        if not PANEL_DAILY.exists():
            return out
        p = pd.read_parquet(PANEL_DAILY, columns=["date", "ticker", "close", "volume"])
        p["date"] = pd.to_datetime(p["date"]).dt.normalize()
        p = p.sort_values(["ticker", "date"])

        spy_roc = None
        if SPY_DAILY.exists():
            spy = pd.read_parquet(SPY_DAILY, columns=["date", "close"]).sort_values("date")
            if len(spy) >= 21 and float(spy["close"].iloc[-21]) > 0:
                spy_roc = (float(spy["close"].iloc[-1]) / float(spy["close"].iloc[-21]) - 1) * 100
        out["spy_roc_20d"] = round(float(spy_roc), 2) if spy_roc is not None else None

        # Daily returns pivot for sector correlation + 252d beta
        close_piv = p.pivot_table(index="date", columns="ticker", values="close")
        rets = close_piv.pct_change()
        spy_rets = rets["SPY"] if "SPY" in rets.columns else None

        for tk, g in p.groupby("ticker", sort=False):
            cl = g["close"].to_numpy(dtype=float)
            vol = g["volume"].to_numpy(dtype=float)
            # vol_30d_ann = std of daily log returns over last 30 sessions, annualised
            if len(cl) >= 31:
                logret = np.diff(np.log(cl[-31:]))
                logret = logret[np.isfinite(logret)]
                if len(logret) >= 2:
                    out["vol30"][tk] = round(float(np.std(logret, ddof=1) * np.sqrt(252)), 4)
            # beta_252d = cov(stock, SPY) / var(SPY) on daily returns over 252 sessions
            if spy_rets is not None and tk in rets.columns and tk != "SPY":
                pair = pd.concat([rets[tk], spy_rets], axis=1).dropna().tail(252)
                if len(pair) >= 60:
                    sp = pair.iloc[:, 1].to_numpy(dtype=float)
                    st_ = pair.iloc[:, 0].to_numpy(dtype=float)
                    var_sp = float(np.var(sp, ddof=1))
                    if var_sp > 0:
                        beta = float(np.cov(st_, sp, ddof=1)[0, 1] / var_sp)
                        if np.isfinite(beta):
                            out["beta252"][tk] = round(beta, 3)
            # rvol = today / 20-day prior average
            if len(vol) >= 21:
                avg20 = float(np.nanmean(vol[-21:-1]))
                if avg20 > 0:
                    out["rvol"][tk] = round(float(vol[-1]) / avg20, 2)
            # sma_distance_pct vs 50D SMA
            if len(cl) >= 50:
                sma50 = float(np.nanmean(cl[-50:]))
                if sma50 > 0:
                    out["sma"][tk] = round((float(cl[-1]) / sma50 - 1) * 100, 2)
            # absolute MA ladder (20/50/100/200) — for live MA-support alerts
            ma = {}
            for w in (20, 50, 100, 200):
                if len(cl) >= w:
                    m = float(np.nanmean(cl[-w:]))
                    if m > 0:
                        ma[w] = round(m, 2)
            if ma:
                out["ma"][tk] = ma
            # rs_spy_20d = stock 20d ROC − SPY 20d ROC
            if len(cl) >= 21 and spy_roc is not None and cl[-21] > 0:
                roc = (float(cl[-1]) / float(cl[-21]) - 1) * 100
                out["rs"][tk] = round(roc - spy_roc, 2)
            # sector_corr = 60d Pearson corr of daily returns vs parent ETF
            etf = sm.get(tk)
            if etf and etf in rets.columns and tk in rets.columns:
                pair = rets[[tk, etf]].dropna().tail(60)
                if len(pair) >= 30:
                    c = float(pair[tk].corr(pair[etf]))
                    if np.isfinite(c):
                        cls = ("IDIOSYNCRATIC" if c < 0.30
                               else "MIXED" if c < 0.70 else "SECTOR_DEPENDENT")
                        out["corr"][tk] = (round(c, 2), cls)
    except Exception:  # noqa: BLE001 — never let enrichment break the export
        pass
    return out


def _compute_enrichment_lookups(dsl_all: dict, betas: dict,
                                regime_level: str) -> dict:
    """Pre-compute Enrichment Spec v2.0 fields per ticker.

    Returns {ticker: {rs_down_day_20d, rs_leadership, breakout_conviction,
    breakout_grade, breakout_pattern, breakout_bar_date, atr_caution,
    beta_data_error, malformed_bracket, beta_60d_capped,
    dsl_atr_ratio_floored}}.
    """
    out: dict = {}
    try:
        import numpy as np
        import pandas as pd
        from src.data.paths import PANEL_DAILY, SPY_DAILY
        from src.engines.enrichment import enrich_record

        if not PANEL_DAILY.exists():
            return out
        pan = pd.read_parquet(
            PANEL_DAILY,
            columns=["date", "ticker", "open", "high", "low", "close", "volume"])
        pan["date"] = pd.to_datetime(pan["date"]).dt.normalize()
        pan = pan.sort_values("date")
        grp = {t: g for t, g in pan.groupby("ticker", sort=False)}

        spy_daily = None
        if SPY_DAILY.exists():
            spy_daily = pd.read_parquet(
                SPY_DAILY, columns=["date", "close"]).sort_values("date")

        for tk, g in grp.items():
            d = dsl_all.get(tk, {})
            beta_60d = (betas.get(tk) or {}).get(60)
            out[tk] = enrich_record(
                stock_daily=g,
                spy_daily=spy_daily,
                elder_ctx=None,
                entry=d.get("entry"),
                stop=d.get("stop"),
                dsl_risk=d.get("risk"),
                beta_60d=beta_60d,
                dsl_atr_ratio=d.get("dsl_atr_ratio"),
                regime_level=regime_level,
            )
    except Exception:  # noqa: BLE001
        pass
    return out


def _is_num(*vals) -> bool:
    """True if every value is a finite number."""
    return all(isinstance(v, (int, float)) and v == v and v not in (float("inf"), float("-inf"))
               for v in vals)


_REGIME_STOP_CEILINGS: dict[str, float] = {
    "GREEN": 12.0, "YELLOW": 8.0, "ORANGE": 6.0, "RED": 4.0,
}


def regime_stop_ceiling(regime_level: str | None) -> float:
    """Charter §4.2 regime-calibrated stop-% ceiling."""
    return _REGIME_STOP_CEILINGS.get((regime_level or "GREEN").upper(), 12.0)


def _structural_stop_analysis(
    d: dict, ma: dict | None, regime_level: str | None = None,
) -> tuple[list[dict], dict | None, int]:
    """DSG-18 B3 — enumerate candidate structural stops and pick the optimal one.

    Full 3-gate validation per Charter §4.2:
      1. atr_ratio >= 1.0 (ATR floor)
      2. rr_tp2 >= 2.0 (R:R gate)
      3. risk_pct <= regime stop-% ceiling (GREEN 12%, YELLOW 8%, ORANGE 6%, RED 4%)

    Returns (valid_levels_only, optimal, total_candidates_evaluated).
    The export carries only valid candidates — invalid ones are noise for the AIC.
    """
    entry, atr14, tp2 = d.get("entry"), d.get("atr14"), d.get("tp_2r")
    if not _is_num(entry, atr14, tp2) or atr14 <= 0:
        return [], None, 0
    fib = d.get("fib") or {}
    rets = fib.get("retracements") or {}
    ceiling = regime_stop_ceiling(regime_level)

    all_levels: list[dict] = []
    _seen: set[float] = set()                # de-dup by price; first label wins

    def _add(typ: str, price, date: str | None = None) -> None:
        if not _is_num(price):
            return
        risk = entry - price
        if risk <= 0:            # a long's stop must sit below entry
            return
        p2 = round(float(price), 2)
        if p2 in _seen:          # same shelf already added under an earlier label
            return
        _seen.add(p2)
        atr_ratio = round(risk / atr14, 2)
        rr_tp2 = round((tp2 - entry) / risk, 2)
        risk_pct = round(risk / entry * 100, 2) if entry else 99.0
        regime_ok = bool(risk_pct <= ceiling)
        item = {"type": typ, "price": p2,
                "atr_ratio": atr_ratio, "rr_tp2": rr_tp2, "risk_pct": risk_pct,
                "valid": bool(atr_ratio >= 1.0 and rr_tp2 >= 2.0 and regime_ok),
                "regime_valid": regime_ok,
                "role": "stop", "side": "below_entry"}   # hard guard
        if date:
            item["date"] = date
        all_levels.append(item)

    _add("dsl_stop", d.get("stop"))
    _add("swing_low", fib.get("swing_low"), fib.get("swing_low_date"))
    # §4.2 Step C — last 3 confirmed pivot lows below entry (from levels.swing_lows)
    for _i, _sl in enumerate(d.get("swing_lows") or [], 1):
        if isinstance(_sl, dict):
            _add(f"swing_low_{_i}", _sl.get("price"), _sl.get("date"))
    _add("fib_618", rets.get("0.618"))
    _add("fib_786", rets.get("0.786"))
    # Compressed MA20/MA50 cluster (within 1×ATR) — a confluence support shelf.
    _ma20, _ma50 = (ma or {}).get(20), (ma or {}).get(50)
    if _is_num(_ma20, _ma50) and abs(_ma20 - _ma50) <= atr14:
        _add("ma_cluster", min(_ma20, _ma50))
    for _w in (20, 50, 100, 200):
        _add(f"ma{_w}", (ma or {}).get(_w))

    total_evaluated = len(all_levels)
    valids = [x for x in all_levels if x["valid"]]
    optimal = None
    if valids:
        best = max(valids, key=lambda x: x["price"])   # tightest = closest to entry
        _orisk = round(entry - best["price"], 2)
        optimal = {"price": best["price"], "type": best["type"],
                   "atr_ratio": best["atr_ratio"], "rr_tp2": best["rr_tp2"],
                   "risk_pct": best["risk_pct"],
                   "risk_usd": _orisk,                  # STRUCTURAL risk to size against
                   "regime_valid": True,
                   "role": "stop", "side": "below_entry",   # hard guard
                   "rationale": "Strongest+closest valid level passing all 3 gates "
                                "(ATR>=1.0, R:R-TP2>=2.0, risk_pct<=regime ceiling). "
                                "risk_usd = entry - price is the structural risk."}
    return valids, optimal, total_evaluated


def _structural_target_analysis(d: dict) -> list[dict]:
    """Take-profit ladder anchored to REAL structure rather than mechanical
    R-multiples. Two structure sources, merged nearest-first:
      • `resistance`  — prior CONFIRMED pivot highs above price (multi-swing
                        overhead resistance the move must clear), and the current
                        swing high (`prior_high`);
      • fib measured-move extensions of the current swing (`fib_1272/1618/2000/2618`).

    Each target above entry gets {type, price, rr} where rr = (price − entry) /
    dsl_risk — reward in R, which VARIES per name with the real structure (unlike
    the fixed tp_1r/2r/3r). The mechanical tp_Nr stay as the risk/trail framework;
    this is the structural objective AIC takes profit against. Near-equal levels
    (within 0.5·ATR) collapse, keeping the resistance label over a fib label.
    """
    entry, risk, atr14 = d.get("entry"), d.get("risk"), d.get("atr14")
    if not _is_num(entry, risk) or risk <= 0:
        return []
    fib = d.get("fib") or {}
    exts = fib.get("extensions") or {}

    raw: list[dict] = []

    def _add(typ: str, price, date: str | None = None) -> None:
        if not _is_num(price) or price <= entry:   # a long's target sits above entry
            return
        item = {"type": typ, "price": round(float(price), 2),
                "rr": round((price - entry) / risk, 2),
                "role": "target", "side": "above_entry"}   # hard guard
        if date:
            item["date"] = date
        raw.append(item)

    # Structure (resistance) first so it wins on de-dup ties, then measured moves.
    for r in (d.get("resistance") or []):
        _add("resistance", r.get("price"), r.get("date"))
    _add("prior_high", fib.get("swing_high"))
    _add("fib_1272", exts.get("1.272"))
    _add("fib_1618", exts.get("1.618"))
    _add("fib_2000", exts.get("2.0"))
    _add("fib_2618", exts.get("2.618"))

    raw.sort(key=lambda x: x["price"])
    gap = atr14 * 0.5 if _is_num(atr14) and atr14 > 0 else 0.0
    targets: list[dict] = []
    for t in raw:
        if targets and gap > 0 and (t["price"] - targets[-1]["price"]) < gap:
            continue                               # collapse near-equal levels
        targets.append(t)
    return targets


def _v21_record_fields(tk: str, d: dict, lk: dict, sm: dict,
                       sector_grades: dict,
                       regime_level: str | None = None) -> dict:
    """AQE v2.1 / Data-Schema-v1.0 per-record fields. Bulletproof: returns a
    full key set with null values on any error, so the schema is always present.
    """
    fields = {
        "gics_sector": None, "gics_sector_name": None, "gics_gate": "CHECK",
        "sector_corr": None, "sector_corr_class": None, "sector_corr_flag": None,
        "thematic_basket": None, "thematic_grade": None,
        "thematic_parent_gics": None, "thematic_parent_grade": None,
        "thematic_baskets": [],
        "rvol": None, "rs_spy_20d": None, "sma_distance_pct": None,
        "ma_20": None, "ma_50": None, "ma_100": None, "ma_200": None,
        # DSG-18 fib ladder (flat — retracement supports + swing anchors)
        "fib_swing_low": None, "fib_swing_high": None,
        "fib_236": None, "fib_382": None, "fib_500": None,
        "fib_618": None, "fib_786": None,
        # DSG-18 Group A — bracket-ready derived levels
        "atr_14d": None, "coil_entry": None,
        "max_chase_tp2": None, "max_chase_tp3": None,
        "rr_tp2_at_coil": None, "rr_tp3_at_coil": None,
        # DSG-18 Group B — vol / beta / structural stop selection
        "vol_30d_ann": None, "beta_252d": None,
        "structural_levels": [], "structural_levels_total": 0,
        "optimal_stop": None, "optimal_stop_exists": False,
        "structural_targets": [],
        "held": False,
        # Readiness / Health scores
        "rd_score": None, "rd_state": None,
        "rd_compression": None, "rd_trigger": None, "rd_pos_mod": None, "rd_rs_bonus": None,
        "hl_score": None, "hl_state": None,
        "hl_trend": None, "hl_flow": None, "hl_rs": None, "hl_risk": None,
        # Enrichment Spec v2.0 — new per-record signals + cleanup flags
        "rs_down_day_20d": None, "rs_leadership": None,
        "setup_state": "BASING",
        "breakout_conviction": None, "breakout_grade": None,
        "breakout_pattern": None, "breakout_bar_date": None,
        "atr_caution": False, "beta_data_error": False,
        "malformed_bracket": False,
        "beta_60d_capped": None, "dsl_atr_ratio_floored": None,
    }
    try:
        etf = sm.get(tk)
        fields["gics_sector"] = etf
        fields["gics_sector_name"] = ETF_TO_NAME.get(etf) if etf else None
        grade = sector_grades.get(etf, {}).get("grade") if etf else None
        entry_gate = sector_grades.get(etf, {}).get("entry_gate") if etf else None
        if entry_gate:
            fields["gics_gate"] = entry_gate
        elif grade in ("DEPLOY", "HOLD"):
            fields["gics_gate"] = "PASS"
        elif grade == "AVOID":
            fields["gics_gate"] = "BLOCKED"
        elif grade:
            fields["gics_gate"] = "WATCH"
        else:
            fields["gics_gate"] = "CHECK"

        corr = (lk.get("corr") or {}).get(tk)
        if corr:
            fields["sector_corr"], fields["sector_corr_class"] = corr[0], corr[1]
            fields["sector_corr_flag"] = corr[1]  # alias for Alfred §9C

        # Thematic basket (data only — gate unchanged). A ticker may belong to
        # MULTIPLE baskets (v2.0 dual-listing, e.g. IREN AI_Infra + Crypto): the
        # singular fields carry the PRIMARY basket (backward compat), and
        # thematic_baskets lists ALL of them so the committee sees both angles.
        # Parent GICS may differ from the ticker's own gics_sector.
        baskets = TICKER_TO_THEMATICS.get(tk) or []
        if baskets:
            thematic = lk.get("thematic") or {}
            annotated = []
            for b in baskets:
                tg = thematic.get(b) or {}
                annotated.append({
                    "basket": b,
                    "grade": tg.get("grade"),
                    "parent_gics": tg.get("parent_gics"),
                    "parent_grade": tg.get("parent_grade"),
                })
            fields["thematic_baskets"] = annotated
            primary = annotated[0]
            fields["thematic_basket"] = primary["basket"]
            fields["thematic_grade"] = primary["grade"]
            fields["thematic_parent_gics"] = primary["parent_gics"]
            fields["thematic_parent_grade"] = primary["parent_grade"]
        fields["rvol"] = (lk.get("rvol") or {}).get(tk)
        fields["rs_spy_20d"] = (lk.get("rs") or {}).get(tk)
        fields["sma_distance_pct"] = (lk.get("sma") or {}).get(tk)
        _ma = (lk.get("ma") or {}).get(tk) or {}
        for w in (20, 50, 100, 200):
            if _ma.get(w) is not None:
                fields[f"ma_{w}"] = _ma[w]
        fields["held"] = tk in (lk.get("held") or set())

        # ── DSG-18 fib ladder (flat) ───────────────────────────────────────
        _fib = d.get("fib") or {}
        _rets = _fib.get("retracements") or {}
        fields["fib_swing_low"] = _fib.get("swing_low")
        fields["fib_swing_high"] = _fib.get("swing_high")
        fields["fib_236"] = _rets.get("0.236")
        fields["fib_382"] = _rets.get("0.382")
        fields["fib_500"] = _rets.get("0.5")
        fields["fib_618"] = _rets.get("0.618")
        fields["fib_786"] = _rets.get("0.786")

        # ── DSG-18 Group A — bracket-ready derived levels ──────────────────
        _stop, _atr14 = d.get("stop"), d.get("atr14")
        _tp2, _tp3 = d.get("tp_2r"), d.get("tp_3r")
        if _is_num(_stop, _atr14) and _atr14 > 0:
            fields["atr_14d"] = round(float(_atr14), 2)
            _coil = round(_stop + _atr14, 2)
            fields["coil_entry"] = _coil
            if _is_num(_tp2):
                fields["max_chase_tp2"] = round((_tp2 + 2 * _stop) / 3, 2)
            if _is_num(_tp3):
                fields["max_chase_tp3"] = round((_tp3 + 2 * _stop) / 3, 2)
            if (_coil - _stop) > 0:
                if _is_num(_tp2):
                    fields["rr_tp2_at_coil"] = round((_tp2 - _coil) / (_coil - _stop), 2)
                if _is_num(_tp3):
                    fields["rr_tp3_at_coil"] = round((_tp3 - _coil) / (_coil - _stop), 2)

        # ── DSG-18 Group B — vol / beta / structural stop selection ────────
        fields["vol_30d_ann"] = (lk.get("vol30") or {}).get(tk)
        fields["beta_252d"] = (lk.get("beta252") or {}).get(tk)
        _slevels, _optimal, _sl_total = _structural_stop_analysis(
            d, _ma, regime_level=regime_level)
        fields["structural_levels"] = _slevels
        fields["structural_levels_total"] = _sl_total
        fields["optimal_stop"] = _optimal
        fields["optimal_stop_exists"] = _optimal is not None
        _stargets = _structural_target_analysis(d)
        # r_optimal = R of each structural TP vs risk. Prefer structural risk
        # (optimal_stop.risk_usd); fall back to dsl_risk with a source tag.
        _entry = d.get("entry")
        _orisk = None
        _r_opt_source = None
        if _optimal and _is_num(_optimal.get("risk_usd")) and _optimal["risk_usd"] > 0:
            _orisk = _optimal["risk_usd"]
            _r_opt_source = "structural"
        elif _is_num(d.get("risk")) and d["risk"] > 0:
            _orisk = d["risk"]
            _r_opt_source = "dsl_risk"
        if _orisk and _is_num(_entry):
            for _t in _stargets:
                if _is_num(_t.get("price")):
                    _t["r_optimal"] = round((_t["price"] - _entry) / _orisk, 2)
                    _t["r_optimal_source"] = _r_opt_source
        fields["structural_targets"] = _stargets

        # ── Readiness / Health scores (from scores_daily or orchestrator) ──
        _rdhl = (lk.get("rdhl") or {}).get(tk, {})
        for _rk in ("rd_score", "rd_state", "rd_compression", "rd_trigger",
                     "rd_pos_mod", "rd_rs_bonus",
                     "hl_score", "hl_state", "hl_trend", "hl_flow",
                     "hl_rs", "hl_risk"):
            if _rk in _rdhl and _rdhl[_rk] is not None:
                fields[_rk] = _rdhl[_rk]

        # ── Enrichment Spec v2.0 — pre-computed per-ticker signals ────────
        _enr = (lk.get("enrichment") or {}).get(tk, {})
        for _ek in ("rs_down_day_20d", "rs_leadership",
                     "breakout_conviction", "breakout_grade",
                     "breakout_pattern", "breakout_bar_date",
                     "atr_caution", "beta_data_error", "malformed_bracket",
                     "beta_60d_capped", "dsl_atr_ratio_floored",
                     "setup_state"):
            if _ek in _enr and _enr[_ek] is not None:
                fields[_ek] = _enr[_ek]
    except Exception:  # noqa: BLE001
        pass
    return fields


def _num(v):
    """Return a clean float or None (drops NaN / non-numeric)."""
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _build_held_positions(held, dsl_all, betas, lk, sm, sector_grades, ptrs_fn,
                          regime_level=None):
    """Merge each PTJ held position with AQE's current engine read on it.

    Gives AIC, in one place: the trade (entry/qty/SL/TP/unrealised from the PTJ)
    + what the engine now says (scores, MP state, DSL bracket, sector, RS, …).
    """
    if not held:
        return []
    import pandas as pd
    from src.data.paths import SCORES_DAILY
    sc_lookup: dict = {}
    try:
        if SCORES_DAILY.exists():
            df = pd.read_parquet(SCORES_DAILY)
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            latest = df[df["date"] == df["date"].max()]
            sc_lookup = {r["ticker"]: r for _, r in latest.iterrows()}
    except Exception:  # noqa: BLE001
        sc_lookup = {}

    out = []
    for p in held:
        tk = p.get("ticker")
        if not tk:
            continue
        d = dsl_all.get(tk, {})
        s = sc_lookup.get(tk)
        sg = (lambda k: _num(s.get(k)) if s is not None else None)
        sc = sg("sc_momentum")
        v21 = _v21_record_fields(tk, d, lk, sm, sector_grades,
                                 regime_level=regime_level)
        out.append({
            "ticker": tk,
            # --- the trade (from PTJ) ---
            "qty": p.get("qty"),
            "entry": _num(p.get("entry")),
            "live_px": _num(p.get("livePx")),
            "held_sl": _num(p.get("sl")),
            "held_tp1": _num(p.get("tp1")),
            "held_tp2": _num(p.get("tp2")),
            "trade_date": p.get("tradeDate") or p.get("entryDate"),
            "unreal_usd": _num(p.get("unrealUsd")),
            "exposure": _num(p.get("exposure")),
            "ptj_sector": p.get("sector"),
            "ptj_srm_grade": p.get("srmGrade"),
            "notes": p.get("notes"),
            "held": True,
            # --- AQE engine read ---
            "sc_momentum": round(sc, 1) if sc is not None else None,
            "sc_momentum_raw": round(sg("sc_momentum_raw") or sc, 1) if (sg("sc_momentum_raw") or sc) is not None else None,
            "ptrs": ptrs_fn(sc, tk) if sc is not None else None,
            "pipe_rank": round(sg("pipe_rank"), 1) if sg("pipe_rank") is not None else None,
            "flow": round(sg("flow_100"), 0) if sg("flow_100") is not None else None,
            "energy": round(sg("energy_100"), 0) if sg("energy_100") is not None else None,
            "structure": round(sg("structure_100"), 0) if sg("structure_100") is not None else None,
            "mp": round(sg("mp_100"), 0) if sg("mp_100") is not None else None,
            "mp_state": (str(s.get("mp_state")) if s is not None and pd.notna(s.get("mp_state")) else None),
            "elder": round(sg("elder_score"), 1) if sg("elder_score") is not None else None,
            "cob_price": sg("close"),   # COB close (FMP) — held_book exposure basis
            "beta_30d": (betas.get(tk) or {}).get(30),
            "beta_60d": (betas.get(tk) or {}).get(60),
            "dsl_stop": d.get("stop"), "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"), "dsl_tp_2r": d.get("tp_2r"), "dsl_tp_3r": d.get("tp_3r"),
            "dsl_atr_ratio": d.get("dsl_atr_ratio"), "atr_14d": v21["atr_14d"],
            "gics_sector": v21["gics_sector"], "gics_gate": v21["gics_gate"],
            "sector_corr": v21["sector_corr"], "sector_corr_class": v21["sector_corr_class"],
            "rs_spy_20d": v21["rs_spy_20d"], "sma_distance_pct": v21["sma_distance_pct"],
            "rvol": v21["rvol"],
            # absolute MA ladder — so the live alert engine can evaluate MA
            # support on held names uniformly with candidates.
            "ma_20": v21["ma_20"], "ma_50": v21["ma_50"],
            "ma_100": v21["ma_100"], "ma_200": v21["ma_200"],
            # DSG-18 flat fib ladder + bracket-ready fields (same as candidates).
            "fib_swing_low": v21["fib_swing_low"], "fib_swing_high": v21["fib_swing_high"],
            "fib_236": v21["fib_236"], "fib_382": v21["fib_382"], "fib_500": v21["fib_500"],
            "fib_618": v21["fib_618"], "fib_786": v21["fib_786"],
            "coil_entry": v21["coil_entry"],
            "max_chase_tp2": v21["max_chase_tp2"], "max_chase_tp3": v21["max_chase_tp3"],
            "rr_tp2_at_coil": v21["rr_tp2_at_coil"], "rr_tp3_at_coil": v21["rr_tp3_at_coil"],
            "vol_30d_ann": v21["vol_30d_ann"], "beta_252d": v21["beta_252d"],
            "structural_levels": v21["structural_levels"],
            "optimal_stop": v21["optimal_stop"], "optimal_stop_exists": v21["optimal_stop_exists"],
            "structural_targets": v21["structural_targets"],
        })
    return out


def build_export(shortlist: dict | None = None) -> dict:
    """Build export from shortlist.json + scores_daily.parquet.

    Contains top_picks, edge_list, longlist, and watchlist.
    Every ticker is tagged with source (longlist / watchlist) and pe status.
    """
    if shortlist is None:
        sl_path = OUTPUT_DIR / "shortlist.json"
        if not sl_path.exists():
            return {}
        shortlist = json.loads(sl_path.read_text(encoding="utf-8"))

    sl = shortlist
    sgt = ZoneInfo("Asia/Singapore")
    now_sgt = datetime.now(sgt)

    # Auto-source GICS for any universe ticker missing from the map (via FMP),
    # up front, so BOTH the export's sector_map_gaps field and the published RAG
    # reflect the filled map — AIC should never see blanks AQE could resolve.
    try:
        from src.data.sector_mapper import build_sector_map, get_sector_map_gaps
        if get_sector_map_gaps():
            build_sector_map()
    except Exception:  # noqa: BLE001
        pass

    # Full 11-sector SRM grading + DSG-18/19 intermarket (spec §2)
    srm_gics, srm_signals, macro_weather, intermarket = _build_srm_gics()

    export: dict = {
        "date": sl.get("date", ""),
        "exported_at": now_sgt.strftime("%Y-%m-%d %H:%M:%S SGT"),
        "market": "US equities — close-of-day scan",
        "regime": sl.get("regime", {}),
        # §3A.6 COB intermarket brief — Druckenmiller's premarket opener.
        # Top-level, between regime and srm (per Alfred 11 Jun spec).
        "intermarket": intermarket,
        # Full SRM schema — combined into this one file (no separate SRM file).
        # `srm` is the canonical sector-grade list the AIC reader + protocols
        # consume; `srm_signals` carries the deploy/hold/.../avoid ETF buckets.
        # (The srm_gics/srm_deploy/srm_avoid aliases were dropped — duplicates.)
        "srm": srm_gics,
        "srm_signals": srm_signals,
        "macro_weather": macro_weather,
        "top_picks": [],
        "edge_list": [],
        "longlist": [],
        "watchlist": [],
        "elder_list": [],
    }

    # ---- Shared helpers (loaded once, used by all four lists) ----
    # PTRS = SC_MOM + SH (sector only). Regime handles VIX sizing separately.
    sector_grades = {r["etf"]: {"grade": r["grade"], "sh": r["sh_value"]} for r in srm_gics} if srm_gics else sl.get("srm_detail", {})

    def _ptrs(sc_mom, ticker):
        sh = get_sector_health(ticker, sector_grades)
        r = compute_ptrs(sc_mom, sh)
        v = r.get("ptrs")
        return round(v, 1) if v is not None and v == v else 0.0

    def _floor(rm):
        e = rm.get("engines", {})
        return min(e.get("flow", 0), e.get("energy", 0),
                   e.get("structure", 0), e.get("mp", 0))

    def _sc_from_engines(eng):
        """SC_MOM = Flow×0.30 + Energy×0.30 + Structure×0.20 + MP×0.20."""
        return round(
            eng.get("flow", 0) * 0.30 + eng.get("energy", 0) * 0.30
            + eng.get("structure", 0) * 0.20 + eng.get("mp", 0) * 0.20, 1
        )

    # Extract regime level for DSL v1.5 dynamic stop width
    regime_level = (sl.get("regime", {}).get("level") or "GREEN").upper()
    export["regime_stop_pct_ceiling"] = regime_stop_ceiling(regime_level)

    sm = load_sector_map()
    betas = load_betas()
    dsl_all = load_trade_levels(betas=betas, regime_level=regime_level)
    elder5 = load_elder_history()
    pe_tickers = {p["ticker"] for p in sl.get("precision_edge", [])}

    # ---- AQE v2.1 enrichment (rvol, rs_spy, sma_distance, sector_corr) ----
    _v21_lk = _compute_v21_lookups(sm)
    export["spy_roc_20d"] = _v21_lk.get("spy_roc_20d")

    # ---- Enrichment Spec v2.0 (rs_down_day, breakout_conviction, cleanup) ----
    _v21_lk["enrichment"] = _compute_enrichment_lookups(
        dsl_all, betas, regime_level)

    # ---- Thematic basket grades (SRM v3.0) — pure panel math, 0 FMP calls ----
    # Graded from constituents' equal-weight index, capped at parent GICS grade.
    # Exported as DATA (per-record + a top-level block); the gate is unchanged.
    try:
        import pandas as _pd
        from src.data.paths import PANEL_DAILY as _pdaily
        if _pdaily.exists():
            _panel_tb = _pd.read_parquet(_pdaily, columns=["date", "ticker", "close"])
            _panel_tb["date"] = _pd.to_datetime(_panel_tb["date"]).dt.normalize()
            _v21_lk["thematic"] = grade_thematic_baskets(_panel_tb, sector_grades)
        else:
            _v21_lk["thematic"] = {}
    except Exception:  # noqa: BLE001
        _v21_lk["thematic"] = {}
    export["thematic_baskets"] = _v21_lk["thematic"]
    from datetime import date as _date
    export["sector_map_version"] = _date.today().isoformat()
    # HARD GUARD (machine-readable, keyed off structure) + prose glossary so the
    # AIC can never read a stop as a target or a ratio as a price. Every nested
    # level item (structural_levels/targets, optimal_stop) also carries role/side.
    export["field_schema"] = _FIELD_SCHEMA
    export["field_schema_enums"] = _FIELD_SCHEMA_ENUMS
    export["field_glossary"] = _FIELD_GLOSSARY
    try:
        from src.data.universe import load_universe
        _univ = load_universe(include_benchmark=False)
        export["sector_map_gaps"] = sorted([t for t in _univ if t not in sm])
    except Exception:  # noqa: BLE001
        export["sector_map_gaps"] = []

    # ---- Held positions (from the daily PTJ) + AQE engine read ----
    try:
        from src.data.ptj import load_held_positions
        _held = load_held_positions()
    except Exception:  # noqa: BLE001
        _held = []
    _v21_lk["held"] = {h.get("ticker") for h in _held if h.get("ticker")}
    export["held_positions"] = _build_held_positions(
        _held, dsl_all, betas, _v21_lk, sm, sector_grades, _ptrs,
        regime_level=regime_level)

    # Portfolio Hedge Layer (Charter §4C) — beta-adj book exposure + gap losses.
    try:
        from src.analyzer.held_book import build_held_book
        export["held_book"] = build_held_book(
            export["held_positions"], now_sgt.strftime("%Y-%m-%d %H:%M:%S SGT"))
    except Exception:  # noqa: BLE001 — additive; never blocks the export
        pass

    # mp_state + readiness/health lookup from scores_daily.parquet.
    import pandas as pd
    from src.data.paths import SCORES_DAILY as _scores_path
    _mp_states: dict[str, str] = {}
    _rdhl_lookup: dict[str, dict] = {}
    if _scores_path.exists():
        _rdhl_cols = ["date", "ticker", "mp_state"]
        _rd_hl_fields = [
            "rd_score", "rd_state", "rd_compression", "rd_trigger",
            "rd_pos_mod", "rd_rs_bonus",
            "hl_score", "hl_state", "hl_trend", "hl_flow", "hl_rs", "hl_risk",
        ]
        _sc = pd.read_parquet(_scores_path)
        _sc["date"] = pd.to_datetime(_sc["date"]).dt.normalize()
        _latest = _sc[_sc["date"] == _sc["date"].max()]
        _mp_states = dict(zip(_latest["ticker"], _latest["mp_state"].astype(str)))
        for _, _row in _latest.iterrows():
            _tk = _row["ticker"]
            _rd_hl_vals = {}
            for _f in _rd_hl_fields:
                if _f in _row.index:
                    _v = _row[_f]
                    if isinstance(_v, str):
                        _rd_hl_vals[_f] = _v
                    elif _v is not None and _v == _v:
                        _rd_hl_vals[_f] = round(float(_v), 1) if not isinstance(_v, str) else _v
            if _rd_hl_vals:
                _rdhl_lookup[_tk] = _rd_hl_vals
    _v21_lk["rdhl"] = _rdhl_lookup

    # Top Picks = candidates (PTRS-ranked shortlist) — SAME schema as longlist
    for c in sl.get("candidates", []):
        tk = c["ticker"]
        e = c["engines"]
        d = dsl_all.get(tk, {})
        sc_val = c.get("sc_momentum", 0) or 0
        floor = round(min(e["flow"], e["energy"], e["structure"], e["mp"]), 1)
        export["top_picks"].append({
            "rank": c["rank"],
            "ticker": tk,
            "sc_momentum": round(sc_val, 1),
            "sc_momentum_raw": round(c.get("sc_momentum_raw", sc_val), 1),
            "ptrs": round(c.get("ptrs", 0), 1),
            "pipe_rank": round(c.get("pipe_rank", 0), 1),
            "fip_spike_excluded": c.get("fip_spike_excluded", False),
            "fip_window_effective": c.get("fip_window_effective", 252),
            "floor": floor,
            "beta_30d": (betas.get(tk) or {}).get(30),
            "beta_60d": (betas.get(tk) or {}).get(60),
            "flow": round(e["flow"], 1),
            "energy": round(e["energy"], 1),
            "structure": round(e["structure"], 1),
            "mp": round(e["mp"], 1),
            "elder": e["elder"],
            "mp_state": _mp_states.get(tk, c.get("mp_state", "")),
            "entry": c["levels"].get("entry"),
            "dsl_stop": d.get("stop"),
            "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"),
            "dsl_tp_2r": d.get("tp_2r"),
            "dsl_tp_3r": d.get("tp_3r"),
            "dsl_rr_pct": d.get("rr_pct"),
            "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "elder_5d": elder5.get(tk),
            "rank_explain": _rank_explain(
                c.get("pipe_rank", 0), floor, sc_val,
                tk in pe_tickers, tk, sm, sector_grades,
            ),
            "source": "top_picks",
            "pe": tk in pe_tickers,
            **_v21_record_fields(tk, d, _v21_lk, sm, sector_grades, regime_level=regime_level),
        })

    # Edge List = Precision Edge — SAME schema as longlist
    for ei, pe in enumerate(sl.get("precision_edge", []), 1):
        eng = pe["engines"]
        tk = pe["ticker"]
        d = dsl_all.get(tk, {})
        pe_sc = pe.get("sc_momentum") or _sc_from_engines(eng)
        pe_raw = pe.get("sc_momentum_raw") or pe_sc
        floor = round(min(eng["flow"], eng["energy"], eng["structure"], eng["mp"]), 1)
        export["edge_list"].append({
            "rank": ei,
            "ticker": tk,
            "sc_momentum": round(pe_sc, 1),
            "sc_momentum_raw": round(pe_raw, 1),
            "ptrs": _ptrs(pe_sc, tk),
            "pipe_rank": round(pe.get("pipe_rank", 0), 1),
            "fip_spike_excluded": pe.get("fip_spike_excluded", False),
            "fip_window_effective": pe.get("fip_window_effective", 252),
            "floor": floor,
            "beta_30d": (betas.get(tk) or {}).get(30),
            "beta_60d": (betas.get(tk) or {}).get(60),
            "flow": round(eng["flow"], 1),
            "energy": round(eng["energy"], 1),
            "structure": round(eng["structure"], 1),
            "mp": round(eng["mp"], 1),
            "elder": eng["elder"],
            "mp_state": _mp_states.get(tk, pe.get("mp_state", "")),
            "entry": pe["levels"].get("entry"),
            "dsl_stop": d.get("stop"),
            "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"),
            "dsl_tp_2r": d.get("tp_2r"),
            "dsl_tp_3r": d.get("tp_3r"),
            "dsl_rr_pct": d.get("rr_pct"),
            "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "elder_5d": elder5.get(tk),
            "rank_explain": _rank_explain(
                pe.get("pipe_rank", 0), floor, pe_sc,
                True, tk, sm, sector_grades,
            ),
            "source": "edge_list",
            "pe": True,
            **_v21_record_fields(tk, d, _v21_lk, sm, sector_grades, regime_level=regime_level),
        })
    longlist_tickers: set[str] = set()
    sorted_rm = sorted(sl.get("recipe_matches", []),
                       key=lambda rm: (
                           _ptrs(rm.get("sc_momentum", 0) or 0, rm["ticker"]),
                           rm.get("pipe_rank", 0),
                           _floor(rm),
                       ),
                       reverse=True)
    for i, rm in enumerate(sorted_rm, 1):
        e = rm["engines"]
        floor = round(min(e["flow"], e["energy"], e["structure"], e["mp"]), 1)
        sc_val = rm.get("sc_momentum", 0) or 0
        longlist_tickers.add(rm["ticker"])
        d = dsl_all.get(rm["ticker"], {})
        export["longlist"].append({
            "rank": i,
            "ticker": rm["ticker"],
            "sc_momentum": round(sc_val, 1),
            "sc_momentum_raw": round(rm.get("sc_momentum_raw", sc_val), 1),
            "ptrs": _ptrs(sc_val, rm["ticker"]),
            "pipe_rank": round(rm.get("pipe_rank", 0), 1),
            "fip_spike_excluded": rm.get("fip_spike_excluded", False),
            "fip_window_effective": rm.get("fip_window_effective", 252),
            "floor": floor,
            "beta_30d": (betas.get(rm["ticker"]) or {}).get(30),
            "beta_60d": (betas.get(rm["ticker"]) or {}).get(60),
            "flow": round(e["flow"], 1),
            "energy": round(e["energy"], 1),
            "structure": round(e["structure"], 1),
            "mp": round(e["mp"], 1),
            "elder": e["elder"],
            "mp_state": _mp_states.get(rm["ticker"], rm.get("mp_state", "")),
            "entry": rm["levels"].get("entry"),
            "dsl_stop": d.get("stop"),
            "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"),
            "dsl_tp_2r": d.get("tp_2r"),
            "dsl_tp_3r": d.get("tp_3r"),
            "dsl_rr_pct": d.get("rr_pct"),
            "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "elder_5d": elder5.get(rm["ticker"]),
            "rank_explain": _rank_explain(
                rm.get("pipe_rank", 0), floor, sc_val,
                rm.get("pe_qualified", False), rm["ticker"],
                sm, sector_grades,
            ),
            "source": "longlist",
            "pe": bool(rm.get("pe_qualified")),
            **_v21_record_fields(rm["ticker"], d, _v21_lk, sm, sector_grades, regime_level=regime_level),
        })

    # --- Watchlist + Elder list: both derived from the latest scores_daily ---
    # Watchlist = full universe above the raw SC_MOM bar (the broad radar).
    # Elder list = names with Elder Impulse >= 8 on the latest close — pure
    # VISIBILITY for fresh strong-impulse setups that other gates filtered out.
    # It changes NO screen/criteria/strategy; same record schema as the rest.
    import pandas as pd
    from src.data.paths import SCORES_DAILY as scores_path

    if scores_path.exists():
        sc_df = pd.read_parquet(scores_path)
        sc_df["date"] = pd.to_datetime(sc_df["date"]).dt.normalize()
        sc_df = sc_df[sc_df["date"] == sc_df["date"].max()].copy()

        raw_col = (
            "sc_momentum_raw" if "sc_momentum_raw" in sc_df.columns
            else "sc_momentum"
        )
        for c in ("pipe_rank", "flow_100", "energy_100", "structure_100", "mp_100"):
            if c in sc_df.columns:
                sc_df[c] = pd.to_numeric(sc_df[c], errors="coerce").fillna(0)
        sc_df["_floor"] = sc_df[
            ["flow_100", "energy_100", "structure_100", "mp_100"]].min(axis=1)
        _sh = sc_df["ticker"].map(
            lambda t: sector_grades.get(sm.get(t, ""), {}).get("sh", 0))
        sc_df["_ptrs"] = (sc_df["sc_momentum"].fillna(0) + _sh.fillna(0)).round(1)
        sc_df = sc_df[~sc_df["ticker"].isin(set(GICS_ETFS) | {"SPY"})].copy()

        def _wl_record(wr, rank, source):
            tk = wr["ticker"]
            d = dsl_all.get(tk, {})
            wfl = round(float(wr["_floor"]), 1)
            wsc = float(wr.get("sc_momentum", 0)) or 0
            wpr = float(wr.get("pipe_rank", 0))
            return {
                "rank": rank,
                "ticker": tk,
                "sc_momentum": round(wsc, 1),
                "sc_momentum_raw": round(float(wr.get(raw_col, wsc)), 1),
                "ptrs": round(float(wr["_ptrs"]), 1),
                "pipe_rank": round(wpr, 1),
                "fip_spike_excluded": bool(wr.get("fip_spike_excluded", False)),
                "fip_window_effective": int(wr.get("fip_window_effective", 252)),
                "floor": wfl,
                "beta_30d": (betas.get(tk) or {}).get(30),
                "beta_60d": (betas.get(tk) or {}).get(60),
                "flow": round(float(wr.get("flow_100", 0)), 1),
                "energy": round(float(wr.get("energy_100", 0)), 1),
                "structure": round(float(wr.get("structure_100", 0)), 1),
                "mp": round(float(wr.get("mp_100", 0)), 1),
                "elder": round(float(wr.get("elder_score", 0)), 1),
                "mp_state": _mp_states.get(tk, str(wr.get("mp_state", ""))),
                "entry": d.get("entry"),
                "dsl_stop": d.get("stop"),
                "dsl_risk": d.get("risk"),
                "dsl_tp_1r": d.get("tp_1r"),
                "dsl_tp_2r": d.get("tp_2r"),
                "dsl_tp_3r": d.get("tp_3r"),
                "dsl_rr_pct": d.get("rr_pct"),
                "dsl_atr_ratio": d.get("dsl_atr_ratio"),
                "elder_5d": elder5.get(tk),
                "rank_explain": _rank_explain(
                    wpr, wfl, wsc, tk in pe_tickers, tk, sm, sector_grades),
                "source": source,
                "pe": tk in pe_tickers,
                "on_longlist": tk in longlist_tickers,
                **_v21_record_fields(tk, d, _v21_lk, sm, sector_grades, regime_level=regime_level),
            }

        # Watchlist — raw SC_MOM ≥ 70, ranked PTRS → PipeRank → Floor.
        # Broad candidate set — raw SC_MOM ≥ 50 (UI sliders trim upward).
        _wl = sc_df[sc_df[raw_col] >= 50].sort_values(
            ["_ptrs", "pipe_rank", "_floor"], ascending=False).reset_index(drop=True)
        for i, (_, wr) in enumerate(_wl.iterrows(), 1):
            export["watchlist"].append(_wl_record(wr, i, "watchlist"))

        # Elder list — Elder Impulse >= 8 on the latest close (visibility only).
        if "elder_score" in sc_df.columns:
            _el = sc_df[
                pd.to_numeric(sc_df["elder_score"], errors="coerce").round() >= 8
            ].sort_values(["_ptrs", "pipe_rank", "_floor"],
                          ascending=False).reset_index(drop=True)
            for i, (_, wr) in enumerate(_el.iterrows(), 1):
                export["elder_list"].append(_wl_record(wr, i, "elder_list"))

    # ---- TWO lists (PM): the single screening `longlist` + the standalone
    # `elder_list`. Longlist replaces watchlist/PE/top_picks (their info survives
    # as on_longlist / pe FLAGS). Elder list is its OWN list — sole criterion
    # Elder ≥ 8, nothing else (the strong-breakout catcher). held_positions stays.
    _merged: dict = {}
    for _tname in ("top_picks", "edge_list", "longlist", "watchlist"):
        for _r in export.get(_tname, []):
            _tk = _r.get("ticker")
            if not _tk:
                continue
            if "on_longlist" not in _r:
                _r["on_longlist"] = _tk in longlist_tickers
            if _tk in _merged:                       # OR-merge the qualifying flags
                if _r.get("on_longlist"):
                    _merged[_tk]["on_longlist"] = True
                if _r.get("pe"):
                    _merged[_tk]["pe"] = True
            else:
                _merged[_tk] = _r
    # Longlist tier = the longlist SCREEN, full stop (PM ruling, 26 Jun 2026):
    # SC_MOM > 64 AND PTRS >= 60 AND Elder >= 7. ONE definition — `longlist_screen`
    # is the single source of truth the Scanner sliders also default to, so what you
    # SEE == what FIRES (the alert engine monitors `longlist`). The broad raw-SC>=50
    # pool is gone — it was noise blasting random alerts every evening. on_longlist
    # (full recipe) / pe stay as per-row BADGES, not membership gates. The standalone
    # Elder>=8 list is built independently below and is unaffected.
    from src.longlist_screen import passes as _ll_passes
    _longlist = sorted(
        (_r for _r in _merged.values() if _ll_passes(_r)),
        key=lambda r: (r.get("ptrs") or 0), reverse=True)
    for _i, _r in enumerate(_longlist, 1):
        _r["rank"] = _i
        _r["source"] = "longlist"

    # Elder list = EVERY name with Elder >= 8 (sole criterion). Built from the
    # scores_daily pass AND derived from the merged longlist — so it can never be
    # empty while Elder-10 names are visible in the longlist (the prior bug: it
    # only read scores_daily, which can be absent at export time).
    _elderlist = list(export.get("elder_list", []))
    _el_seen = {r.get("ticker") for r in _elderlist if r.get("ticker")}
    for _r in _longlist:
        if (_r.get("elder") or 0) >= 8 and _r.get("ticker") not in _el_seen:
            _el_seen.add(_r.get("ticker"))
            _elderlist.append(dict(_r))          # copy; re-tagged below
    _elderlist = sorted(_elderlist, key=lambda r: (r.get("ptrs") or 0), reverse=True)
    for _i, _r in enumerate(_elderlist, 1):
        _r["rank"] = _i
        _r["source"] = "elder_list"

    # ---- Elder Context block (Instruction v1.1) on EVERY row of BOTH lists ----
    # `elder_5d` + elder_pattern are free. VWAP (5-day hourly base vs COB) and the
    # volume trend / up-down ratio (buyer-seller / accum-distribution) need HOURLY
    # bars — fetched from FMP here so the EXPORT carries them (not just the Pricer).
    # Bounded + best-effort + cached per ticker; disable with AQE_ELDER_CTX_HOURLY=0.
    try:
        import os as _os
        import pandas as _pd
        from src.data.paths import PANEL_DAILY as _PAN
        from src.engines.elder_context import compute_elder_context, elder_pattern
        _pan = _pd.read_parquet(
            _PAN, columns=["date", "ticker", "open", "high", "low", "close", "volume"])
        _pan["date"] = _pd.to_datetime(_pan["date"]).dt.normalize()
        _pan = _pan.sort_values("date")
        _grp = {t: g for t, g in _pan.groupby("ticker", sort=False)}

        # Hourly bars per ticker (5-day window) for VWAP + volume context.
        _hourly: dict = {}
        if _os.environ.get("AQE_ELDER_CTX_HOURLY", "1") != "0":
            try:
                from src.data.fmp_client import FMPClient
                _fc = FMPClient()
                _need = list({r.get("ticker")
                              for r in (_longlist + _elderlist) if r.get("ticker")})
                for _tk in _need[:400]:                 # safety cap
                    try:
                        _hourly[_tk] = _fc.get_intraday_bars(_tk, interval="1hour") or []
                    except Exception:  # noqa: BLE001
                        _hourly[_tk] = []
            except Exception:  # noqa: BLE001
                _hourly = {}

        def _attach_elder(_rows):
            for _r in _rows:
                _tk = _r.get("ticker")
                _e5 = _r.get("elder_5d") or []
                _r["elder_pattern"] = elder_pattern(_e5)
                _g = _grp.get(_tk)
                _daily = ([] if _g is None else [
                    {"date": str(d.date()), "open": o, "high": h, "low": low,
                     "close": c, "volume": v}
                    for d, o, h, low, c, v in zip(
                        _g["date"].tail(20), _g["open"].tail(20), _g["high"].tail(20),
                        _g["low"].tail(20), _g["close"].tail(20), _g["volume"].tail(20))])
                _st = _r.get("structural_targets") or []
                _res = _st[0].get("price") if _st and isinstance(_st[0], dict) else None
                _r["elder_context"] = compute_elder_context(
                    _e5, _hourly.get(_tk) or [], _daily, resistance_price=_res)

        _attach_elder(_longlist)
        _attach_elder(_elderlist)

        # Enrichment v2.0: recompute setup_state now that elder_context is attached.
        from src.engines.enrichment import compute_setup_state as _css
        for _r in _longlist + _elderlist:
            _cl = _r.get("entry")           # COB close = reference entry
            _m10 = _r.get("ma_20")          # ma_10 not exported; use ma_20 as nearest
            _m20 = _r.get("ma_20")
            _m50 = _r.get("ma_50")
            _ec = _r.get("elder_context")
            if _cl and _m10:
                # Compute proper MA10 from the panel if available
                _pg = _grp.get(_r.get("ticker"))
                if _pg is not None and len(_pg) >= 10:
                    import numpy as _np
                    _cls = _pg["close"].astype(float).to_numpy()
                    _m10 = float(_np.mean(_cls[-10:]))
                _r["setup_state"] = _css(_cl, _m10, _m20, _m50, _ec)
    except Exception:  # noqa: BLE001 — elder_context is additive, never blocks export
        for _r in _longlist + _elderlist:
            _r.setdefault("elder_pattern", None)
            _r.setdefault("elder_context", None)

    export["longlist"] = _longlist
    export["elder_list"] = _elderlist          # standalone list — kept
    # The broad watchlist (SC>=50) is NOT shown to the AIC, but the alert engine
    # needs a wider monitored set than the tight longlist — otherwise the narrow
    # trigger bands (buy-zone crossing, 2-8% breakout, near-stop) rarely fire on
    # just ~20 names. _alert_pool carries the dedup'd watchlist minus longlist/elder
    # tickers so the alert engine has ~100+ names to watch without spamming the AIC.
    _alert_seen = {r.get("ticker") for r in _longlist + _elderlist if r.get("ticker")}
    _alert_pool = [r for r in export.get("watchlist", [])
                   if r.get("ticker") and r.get("ticker") not in _alert_seen]
    export["_alert_pool"] = _alert_pool
    for _k in ("top_picks", "edge_list", "watchlist"):
        export.pop(_k, None)
    export["summary"] = {"longlist_count": len(_longlist),
                         "elder_count": len(_elderlist),
                         "held_count": len(export.get("held_positions") or [])}

    # ---- Uniform schema per list (null-fill each to one key set) ----
    for _lname in ("longlist", "elder_list"):
        _rows = export.get(_lname) or []
        if not _rows:
            continue
        _all_keys: set[str] = set()
        for _rec in _rows:
            _all_keys.update(_rec.keys())
        _order = list(_rows[0].keys())
        _order += [k for k in sorted(_all_keys) if k not in _order]
        export[_lname] = [{k: _rec.get(k) for k in _order} for _rec in _rows]

    # ---- Backward-compat shim — minimal aliases so stale skills still find
    # key fields. Remove when skills are updated to the current schema. ------
    for _lname_bc in ("longlist", "elder_list", "_alert_pool"):
        for _rec in export.get(_lname_bc) or []:
            _rec.setdefault("stop", _rec.get("dsl_stop"))
    for _hp in export.get("held_positions") or []:
        _hp.setdefault("stop", _hp.get("dsl_stop"))
    _sigs = export.get("srm_signals") or {}
    export.setdefault("srm_deploy", _sigs.get("deploy", []))
    export.setdefault("srm_avoid", _sigs.get("avoid", []))

    # ---- Permanent schema validation — BLOCKS export on missing fields ----
    _REQUIRED_FIELDS = [
        "ticker", "sc_momentum", "ptrs", "flow", "energy", "structure",
        "mp", "elder", "entry", "stop",
        "dsl_stop", "dsl_risk", "dsl_rr_pct",
        "dsl_atr_ratio", "atr_14d",
        "dsl_tp_1r", "dsl_tp_2r", "dsl_tp_3r",
        "beta_30d", "beta_60d", "elder_5d", "mp_state", "pe", "pipe_rank",
        "floor", "rank_explain",
        # DSG-18 flat fib ladder + bracket-ready fields
        "fib_swing_low", "fib_swing_high",
        "fib_236", "fib_382", "fib_500", "fib_618", "fib_786",
        "coil_entry", "max_chase_tp2", "max_chase_tp3",
        "rr_tp2_at_coil", "rr_tp3_at_coil",
        "vol_30d_ann", "beta_252d",
        "structural_levels", "structural_levels_total",
        "optimal_stop", "optimal_stop_exists",
        "structural_targets",
        # Enrichment Spec v2.0
        "rs_down_day_20d", "rs_leadership", "setup_state",
        "breakout_conviction", "breakout_grade", "breakout_pattern",
        "breakout_bar_date",
        "atr_caution", "beta_data_error", "malformed_bracket",
        "beta_60d_capped", "dsl_atr_ratio_floored",
    ]
    for _rec in export["longlist"]:
        _missing = [f for f in _REQUIRED_FIELDS if f not in _rec]
        if _missing:
            raise ValueError(
                f"SCHEMA VIOLATION: longlist record "
                f"'{_rec.get('ticker', '?')}' missing fields: {_missing}"
            )

    return export


def _upload_file(filename: str, content: str) -> dict:
    """Upload to the pinned Drive folder via REST API. Returns result dict.

    Destination is the folder ID configured in gdrive_uploader
    (GDRIVE_FOLDER_ID, default = the linked AQE folder).
    """
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            return gdrive_uploader.upload_or_replace(
                filename, content, mime="application/json",
            )
        return {"ok": False, "reason": "not configured"}
    except Exception as exc:                                                    # noqa: BLE001
        return {"ok": False, "reason": f"uploader error: {exc}"}


def _upload_file_to_folder(filename: str, content: str, folder_id: str) -> dict:
    """Upload to a specific Drive folder ID via REST API. Returns result dict."""
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            return gdrive_uploader.upload_or_replace(
                filename, content, mime="application/json", folder_id=folder_id,
            )
        return {"ok": False, "reason": "not configured"}
    except Exception as exc:                                                    # noqa: BLE001
        return {"ok": False, "reason": f"uploader error: {exc}"}


def _build_sector_map_rich() -> dict:
    """Build the rich sector RAG map (Data Schema Spec v1.0 §6.2) for Drive.

    {version, ticker_count, tickers: {tk: {gics_etf, gics_sector_name,
    thematic_basket, source, confirmed_date}}, gaps}.

    AQE auto-sources GICS for any universe ticker missing from the map (via
    FMP profiles) BEFORE serializing, so the published RAG has no blanks — the
    user does not curate by hand; AQE fills the gaps.
    """
    from datetime import date as _date
    _ver = _date.today().isoformat()

    # Auto-fill blanks: resolve GICS for unmapped universe tickers via FMP
    # (incremental — only the gaps are fetched). Best-effort.
    try:
        from src.data.sector_mapper import build_sector_map, get_sector_map_gaps
        if get_sector_map_gaps():
            build_sector_map()
    except Exception:  # noqa: BLE001
        pass

    sm = load_sector_map()
    try:
        from src.data.universe import load_universe
        univ = load_universe(include_benchmark=False)
    except Exception:  # noqa: BLE001
        univ = list(sm.keys())

    tickers: dict[str, dict] = {}
    gaps: list[str] = []
    for t in sorted(set(univ) | set(sm.keys())):
        etf = sm.get(t)
        basket = TICKER_TO_THEMATIC.get(t)
        if etf:
            tickers[t] = {
                "gics_etf": etf,
                "gics_sector_name": ETF_TO_NAME.get(etf),
                "thematic_basket": basket,
                "source": "AUTO",
                "confirmed_date": _ver,
            }
        else:
            tickers[t] = {
                "gics_etf": None, "gics_sector_name": None,
                "thematic_basket": basket, "source": "UNKNOWN",
                "confirmed_date": None,
            }
            gaps.append(t)
    return {
        "version": _ver,
        "ticker_count": len(tickers),
        "tickers": tickers,
        "gaps": gaps,
    }


def export_to_drive(shortlist: dict | None = None) -> dict:
    """Build the combined export JSON and publish it to the Drive folder.

    Publishes ONE file, overwriting it each run so the folder never clutters:
      aqe_daily_export.json — scan + SRM combined (the committee's read)

    written via:
      - Local OUTPUT_DIR (the app's own working copy — always)
      - Drive REST API into the pinned folder (if OAuth configured)

    Returns dict with status and per-file results.
    """
    export = build_export(shortlist)
    if not export:
        return {"status": "skipped", "reason": "No shortlist data"}

    date_str = export.get("date", "unknown")
    written: list[str] = []
    drive_results: list[dict] = []

    # ---- AQE export ----
    aqe_content = json.dumps(export, indent=2)
    local_aqe = OUTPUT_DIR / EXPORT_FILENAME
    if local_aqe.exists():
        local_aqe.unlink()
    local_aqe.write_text(aqe_content, encoding="utf-8")
    written.append(str(local_aqe))

    r = _upload_file(EXPORT_FILENAME, aqe_content)
    drive_results.append({"file": EXPORT_FILENAME, "target": "AQE", **r})
    if r.get("ok"):
        written.append(f"gdrive:{EXPORT_FILENAME}")

    # ---- Sector RAG map → dedicated Drive subfolder (Schema v1.0 §6) ----
    # Best-effort; never affects the primary AQE export status.
    try:
        sector_rich = json.dumps(_build_sector_map_rich(), indent=2)
        sm_local = OUTPUT_DIR / SECTOR_MAP_FILENAME
        if sm_local.exists():
            sm_local.unlink()
        sm_local.write_text(sector_rich, encoding="utf-8")
        written.append(str(sm_local))
        rs = _upload_file_to_folder(SECTOR_MAP_FILENAME, sector_rich, SECTOR_MAP_FOLDER_ID)
        drive_results.append({"file": SECTOR_MAP_FILENAME, "target": "SectorMap", **rs})
        if rs.get("ok"):
            written.append(f"gdrive:{SECTOR_MAP_FILENAME}")
            # Keep the dedicated sector folder to a single file — trash any
            # duplicate/stale copies so AIC always reads exactly one RAG.
            try:
                from src.data import gdrive_uploader
                gdrive_uploader.keep_only_file(SECTOR_MAP_FOLDER_ID, rs.get("file_id"))
            except Exception:                                                   # noqa: BLE001
                pass
    except Exception as exc:                                                    # noqa: BLE001
        drive_results.append({"file": SECTOR_MAP_FILENAME, "ok": False, "reason": str(exc)})

    # Status: ok if the file reached Drive (beyond the local working copy)
    drive_written = [w for w in written if "gdrive:" in w]
    status = "ok" if drive_written else "partial"
    reason = None
    if status == "partial":
        reason = drive_results[0].get("reason") if drive_results else "Drive not published"

    return {
        "status": status,
        "date": date_str,
        "exported_at": export.get("exported_at", ""),
        "written": written,
        "drive_api_results": drive_results,
        **({"reason": reason} if reason else {}),
    }


# Legacy — keep for backward compat
def sync_to_drive(files: list[Path] | None = None) -> dict:
    """Export daily JSON to Google Drive (via local mount)."""
    return export_to_drive()
