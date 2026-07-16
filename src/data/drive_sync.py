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
from src.engines.bracket_engine import compute_bracket, regime_stop_ceiling, stamp_bracket_volume
from src.engines import scoring
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
        "or is a list/object. 'rr'/'r' = reward-to-risk in R, where 1R = bracket.risk "
        "(= price − bracket.stop, the structural risk unit)."
    ),
    "_decision_framework": (
        "AQE reads the trade lifecycle in three distinct stages — do NOT conflate "
        "them; each answers a different question, so there is no 'picking at random': "
        "(1) DETECT — is a move brewing? = Signal Radar (runner_setup = a name already "
        "moving with another leg; premove_setup = a pre-move, ~12-day lead). These are "
        "DETECTION tags, not entries. "
        "(2) ENTER — is it time to buy, and where? = the bracket (stop/targets/R:R) + "
        "the live alert engine (buy-zone / breakout / near-stop levels). The PM/AIC "
        "pulls the trigger here. "
        "(3) HOLD — should an OPEN position stay on? = Health (hl_score/hl_state, on "
        "held_positions ONLY): HOLD_ADD / HOLD / TIGHTEN / EXIT on trend integrity. "
        "Readiness (the old rd_* entry-timing composite) is intentionally NOT in this "
        "feed — it overlapped premove_setup + the alert levels, so DETECT and ENTER "
        "already cover entry timing. AQE makes NO decision at any stage; it supplies "
        "the data and levels, the AIC decides."
    ),
    "entry": "Reference entry = prior close-of-day. The live fill is the IBKR price at "
             "bracket time, NOT this value.",
    "atr_14d": "14-day Average True Range in USD (the volatility unit).",
    "bracket": "THE bracket — the single source of truth for stop + targets (mechanical "
               "DSL/TP is retired). A nested object: {price, price_source (eod_close on the "
               "daily run / live_15min on a live pull), stop, stop_type (swing_low/ma/fib "
               "that the stop sits on), stop_atr_dist (risk in ATRs — read this, not raw "
               "USD), risk (=price−stop, the R unit to size against), risk_pct, "
               "targets[{type,tp (TP1/2/3),price,r,atr_dist}] (structural resistance/MA/fib "
               "ABOVE price, nearest-first — TAKE PROFIT against these), rr (R:R to the "
               "structural TP2), rr_tp1/rr_tp2/rr_tp3 (R:R to each of the first three targets), "
               "atr_fallback_stop (= 1×ATR below price — the reference stop to use ONLY when "
               "valid=false, i.e. no structural level exists), "
               "valid, invalid_reason}. When valid=false the name has NO tradeable bracket "
               "('no valid bracket') — show that, never a mechanical fallback. STOP is below "
               "price, TARGETS above; R and ATR distances are relative, not absolute noise. "
               "VOLUME VALIDATION: dated levels carry vol_ratio (pivot-bar volume / trailing "
               "20-bar avg) + vol_validated (ratio ≥ 1.2) — a level DEFENDED on high volume "
               "is a stronger level; the stop's own read is stop_date + stop_vol_ratio + "
               "stop_vol_validated (present when the stop is swing-based). Data only — the "
               "3 gates are unchanged.",
    "structure_shift": "BOS/CHoCH read vs the CONFIRMED swing anchors (data only, never a "
                       "gate): BULLISH_BOS = COB close broke ABOVE the last confirmed swing "
                       "high (break of structure — trend continuation/ignition); "
                       "BEARISH_CHOCH = close broke BELOW the up-swing's anchor low "
                       "(character change — the up-structure failed); RANGE = inside the "
                       "swing. Null when no swing is detected.",
    "structure_shift_ref": "The swing level the shift is measured against (USD): the broken "
                           "swing high for BULLISH_BOS, the broken anchor low for "
                           "BEARISH_CHOCH; null for RANGE.",
    "mp_accel": "Momentum ACCELERATION (2nd derivative): 5-bar change of the MP momentum "
                "z-score (roc_zscore), smoothed 3 bars. Positive = momentum itself is "
                "building; negative = rolling over. Flags inflection BEFORE the level/"
                "mp_state confirms — read alongside mp_state (which is a knife-edge when "
                "the score plateaus). Additive diagnostic, not part of the Pine spec.",
    "mp_accel_state": "Label for mp_accel with a ±0.10 dead-zone: ACCELERATING / "
                      "DECELERATING / FLAT.",
    "div_state": "Regular price-vs-oscillator DIVERGENCE at the last close (non-repainting: "
                 "confirmed pivots only, freshness-gated ~10 bars): BULLISH = price made a "
                 "lower pivot low while ≥1 oscillator made a higher low (downmove losing "
                 "internal energy); BEARISH mirror on highs; MIXED = both; NONE. Oscillators "
                 "tested: RSI, MFI, CMF, MACD, OBV — all AQE-computed. Context only, "
                 "never a gate.",
    "div_bull_count": "How many of the 5 oscillators confirm the bullish divergence (0-5). "
                      "More confirming oscillators = stronger read.",
    "div_bear_count": "How many of the 5 oscillators confirm the bearish divergence (0-5).",
    "div_oscs": "Which oscillators fired, comma-joined — bullish names bare, bearish names "
                "prefixed '-' (e.g. 'rsi,mfi,-obv'). Null when none.",
    "div_date": "Date of the confirming (newer) pivot anchoring the divergence.",
    "pin_bar_state": "Candlestick REJECTION pattern on the LAST closed bar (pure geometry, "
                     "no lookahead): BULLISH_PIN = long lower wick (≥66% of range) + small "
                     "body (≤40%) + small upper wick (≤40%) — the market pushed down and got "
                     "rejected; BEARISH_PIN mirrors it (long upper wick). NONE = no pattern. "
                     "Filtered so the bar's range must be ≥2× the prior bar's range (rejects "
                     "'pin bars' that are just noise inside an already-tiny range).",
    "pin_bar_date": "Date of the pin bar (null when pin_bar_state=NONE).",
    "pin_bar_level": "The pin bar's rejection extreme (USD): the LOW for a bullish pin "
                     "(a candidate support), the HIGH for a bearish pin (candidate "
                     "resistance). Null when pin_bar_state=NONE.",
    "inside_bar": "True if the LAST bar's range is fully inside the PRIOR bar's range "
                  "(high < prev_high AND low > prev_low) — a one-bar consolidation pause.",
    "pib_pattern": "True if the SECOND-TO-LAST bar was a pin bar AND the last bar is an "
                   "inside bar relative to it — the 'rejection, then pause' combo pattern. "
                   "Independent of pin_bar_state (which only reads the LAST bar itself).",
    "choch_state": "Change-of-Character (swing-break trend flip), the LATEST detected event: "
                   "BULLISH = close broke above the last confirmed swing high while the prior "
                   "trend was flat/down; BEARISH mirrors it (broke below swing low). NONE = "
                   "no CHoCH detected. Non-repainting (confirmed pivots only).",
    "choch_date": "Date of the latest CHoCH event (null when choch_state=NONE).",
    "knn_prob": "K-NEAREST-NEIGHBORS directional probability (0-1) for the current CHoCH: "
                "the win-rate of the K most similar HISTORICAL CHoCH events on this SAME "
                "ticker (matched on 3 features — volume-delta, ATR-normalised displacement, "
                "velocity — via Euclidean distance), where 'win' = the move's max favorable "
                "excursion exceeded its max adverse excursion within a fixed lookahead. This "
                "IS genuine instance-based learning (a real kNN), not a black box — but it's "
                "simple (3 hand-picked features, no training beyond the ticker's own history) "
                "and should be read as one more context signal, not a probability of profit. "
                "Null when there's no CHoCH or too few historical analogs to query.",
    "knn_significant": "True iff knn_prob clears a fixed threshold in either direction (≥60% or "
                       "≤40% by default). CAVEAT (AIC Charter Amendment v2.8, 2026-07-15 ruling): "
                       "this is a plain threshold check on a SMALL neighbor count (k=5 by "
                       "default), NOT a statistical significance test — at k=5, 3-of-5 agreeing "
                       "clears the 60% bar trivially, including by chance. Carries no p-value or "
                       "confidence-interval semantics. Read as 'the threshold was crossed', not "
                       "'the analogs meaningfully agree'.",
    "knn_neighbors_used": "How many historical analog events the knn_prob is averaged over "
                          "(0 if none found).",
    "knn_tp1": "Nearest kNN-implied target (USD): current price ± half the neighbors' mean "
              "favorable excursion, signed by the CHoCH direction. A statistical projection "
              "from historical analogs, NOT a structural level — read alongside bracket.targets, "
              "never in place of them.",
    "knn_tp2": "Mid kNN-implied target: current price ± the neighbors' MEDIAN favorable "
              "excursion, signed by direction.",
    "knn_tp3": "Far kNN-implied target: current price ± the neighbors' 75th-percentile "
              "favorable excursion, signed by direction.",
    "fib_swing_low/high": "Anchors of the current detected up-swing (absolute USD).",
    "fib_236/382/500/618/786": "Fib RETRACEMENT supports below the swing high — potential "
                               "pullback/STOP levels (absolute USD).",
    "ma_20/50/100/200": "Simple moving averages (absolute USD) — dynamic support/resistance.",
    "vol_30d_ann": "30-day annualised realised volatility (decimal: 0.18 = 18%). This IS "
                   "the Charter §4.5 operative sizing vol (the charter calls it 'vol_30d'; "
                   "AQE's field is annualised — same number). For"
                   "sizing/VaR, not a target.",
    "beta_252d": "1-year beta vs SPY (cov/var).",
    "ptrs": "= SC_MOMENTUM verbatim (PM ruling: the Sector-Health adjustment is DROPPED — "
            "sector context is read separately and qualitatively via `srm`/RRG, not "
            "double-counted into a per-ticker score). Disposition/sizing is the "
            "committee's call — AQE exports no sizing.",
    # Enrichment Spec v2.0 — new per-record signals + cleanup flags
    "rs_down_day_20d": "All-weather leadership: stock's avg outperformance vs SPY on SPY "
                       "DOWN days (last 20 sessions). Positive = beats SPY when market "
                       "drops = genuine leader (pct).",
    "rs_leadership": "Classification from rs_down_day_20d: LEADER (>+0.25), IN-LINE, "
                     "LAGGARD (<−0.25).",
    "atr_caution": "True if the structural stop was too tight for the regime "
                   "(risk% near the regime ceiling).",
    "malformed_bracket": "True if the structural stop sits within 0.5% of price "
                         "(bracket unusable — stop virtually at entry).",
    # Health Score — HOLD decision, held_positions ONLY (see decision framework).
    "hl_score": "Health composite (0-100). Trend integrity of a HELD position — the "
                "HOLD decision. HOLD_ADD (75+) / HOLD (50-74) / TIGHTEN (30-49) / EXIT (<30). "
                "Shown ONLY on held_positions.",
    "hl_state": "Health state label (held only): HOLD_ADD / HOLD / TIGHTEN / EXIT.",
    # Signal Radar (M14-M18) — DETECTION tags, NOT gates and NOT sizing.
    "runner_setup": "DETECTION tag (bool): name is already moving with another leg — "
                    "short young base + strong 5-day thrust + clear overhead (M15 rule). "
                    "NOT a gate, NOT sizing; the PM decides entry/bracket/size live. Any % "
                    "reported for this tag elsewhere is a DETECTION RATE (how often tagged "
                    "names historically touched a level, price-path only) — never a win rate.",
    "runner_conviction": "DETECTION conviction (0-4): how many of the four M15 legs "
                         "(short base / strong 5d momentum / clear overhead / room below the "
                         "20d high) are in their favourable tercile. Higher = stronger "
                         "historical detection, not a probability of profit.",
    "runner_conviction_label": "Human-readable conviction = word + number, e.g. 'HIGH (3/4)'. "
                         "The word is anchored to the historical +20%/20d detection ladder "
                         "(MINIMAL 0 / LOW 1 / MODERATE 2 / HIGH 3 / MAX 4 ~= 5/13/27/43% "
                         "detection). Read this, not the bare number. Still a detection tag, "
                         "not a win rate, not sizing.",
    "mover_subtype": "DETECTION sub-type label (explosive / trend / tight_base / squeeze) — "
                     "the family whose z-score profile the name matches best (M16c). Context "
                     "only; not a gate.",
    "premove_setup": "DETECTION tag (bool): name is QUIET now but coiled to launch — very "
                     "young base + squeeze on + well below the recent high (M18 rule, applies "
                     "only to quiet-pond names). Historical launches came a median ~12 trading "
                     "days after the tag — a pre-move radar, not a same-day trigger. NOT a "
                     "gate, NOT sizing; % elsewhere = detection rate, not win rate.",
    "premove_conviction": "DETECTION conviction (0-4): count of M18 launcher-fingerprint legs "
                          "present. Context only; not a probability of profit.",
    "premove_conviction_label": "Human-readable pre-move conviction = word + number, e.g. "
                          "'HIGH (3/4)' (MINIMAL 0 / LOW 1 / MODERATE 2 / HIGH 3 / MAX 4). Read "
                          "this, not the bare number. Detection tag, not a win rate, not sizing.",
    "sc_m_gates": "SC_MOMENTUM qualification gate (bool): True iff EVERY engine floor passes — "
                  "Flow≥60, Energy≥60, Structure≥55, MP≥55, Elder≥6.5 (Pine SC_M_GATES). It does "
                  "NOT cap the score (composite is uncapped); it flags whether the momentum "
                  "read is fully gated. See sc_m_gate_detail for which specific check fails.",
    "sc_m_gate_detail": "Per-engine SC_MOMENTUM gate pass/fail (dict): {flow, energy, structure, "
                        "mp, elder} each True/False vs the SC_M_GATES threshold — so you read WHICH "
                        "check a name is failing without recomputing. false = that engine is below "
                        "its floor.",
    "sc_p_gates": "SC_POSITION qualification gate (bool): True iff every engine floor passes — "
                  "Flow≥40, Energy≥60, Structure≥65, MP≥40, BQ≥60 (Pine SC_P_GATES) AND the K39 "
                  "weekly gate. Does NOT cap the score. See sc_p_gate_detail for the breakdown.",
    "sc_p_gate_detail": "Per-engine SC_POSITION gate pass/fail (dict): {flow, energy, structure, "
                        "mp, bq, k39} each True/False vs the SC_P_GATES threshold (k39 = the weekly "
                        "confirmation gate; null if unavailable).",
    "subcomponents": "The engine SUB-SCORES behind each headline read — nested by engine, so the "
                     "AIC sees WHY an engine scored what it did (context, never a gate). "
                     "flow: {flow_score (MFI+CMF+HA core), accum_score, volume_score, skew_score, "
                     "ext_score (extension penalty), mfi, cmf, ha_quality_count}. "
                     "energy: {vp_position_score (volume-profile position), price_action_score, "
                     "squeeze_score (BB/KC squeeze — the TTM-squeeze read), exhaustion_score, "
                     "atr_score, en_pos50, en_trend_bars}. "
                     "structure: {rs_spy_score, rs_accel_score, base_score, ms_pos_score (market "
                     "structure), resist_score (overhead), wk_score (weekly trend = HTF bias), "
                     "earn_score, rs_vs_spy (raw), rs_accel (raw), base_days, bd_mode}. "
                     "mp: {abs_mom_score, mp_adx_score, rel_mom_score, trend_score, roc_zscore "
                     "(momentum z), excess_return (vs SPY %), adx_val, di_bullish}. "
                     "bq: {bq_range_tight, bq_vol_dry, bq_base_dur, bq_ema_conv, bq_base_days}. "
                     "pipe: {pr_ret_12m, pr_adx_score, pr_rsi_score, pr_vol_score, pr_ma_score "
                     "(MA-stack alignment), momentum_composite, pipe_tier}. "
                     "Readiness sub-scores are intentionally NOT here (hidden per the "
                     "decision-framework ruling) and Health sub-scores stay held-only/dropped.",
    "sector_trend_state": "The ticker's GICS-sector SRM trend-state for the day (e.g. 'Momentum "
                          "Building — Add' / 'Momentum Fading — Hold' / 'Recovering' / 'Declining'). "
                          "Context; the gate is gics_gate, unchanged.",
    "sector_rrg_quadrant": "The ticker's sector RRG quadrant vs SPY: LEADING / IMPROVING / "
                          "WEAKENING / LAGGING.",
    "sector_rrg_direction": "The ticker's sector RRG direction of travel: ENTERING / DEEPENING / "
                          "EXITING / STABLE.",
    "thematic_rrg_quadrant": "The ticker's PRIMARY thematic basket's RRG quadrant vs SPY "
                          "(LEADING / IMPROVING / WEAKENING / LAGGING).",
    "thematic_rrg_direction": "The ticker's PRIMARY thematic basket's RRG direction "
                          "(ENTERING / DEEPENING / EXITING / STABLE).",
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
    "atr_14d":        _fs("volatility", "usd", "n/a"),
    # THE BRACKET — the single object carrying stop + targets + R:R. Mechanical
    # DSL/TP fields are RETIRED. `bracket` is a nested object (see field_glossary);
    # its own stop/target items self-tag role/side.
    "bracket":        _fs("stop", "usd", "below_entry"),
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
    # Enrichment Spec v2.0 (setup_state + breakout_* hidden — Signal Radar overlap)
    "rs_down_day_20d":      _fs("signal", "pct", "n/a"),
    "rs_leadership":        _fs("signal", "label", "n/a"),
    "atr_caution":          _fs("flag", "boolean", "n/a"),
    "malformed_bracket":    _fs("flag", "boolean", "n/a"),
    # Health (HOLD decision, held_positions only)
    "hl_score":             _fs("signal", "score", "n/a"),
    "hl_state":             _fs("signal", "label", "n/a"),
    # Signal Radar (M14-M18) — additive DETECTION tags (never gate/size)
    "runner_setup":            _fs("signal", "boolean", "n/a"),
    "runner_conviction":       _fs("signal", "score", "n/a"),
    "runner_conviction_label": _fs("signal", "label", "n/a"),
    "mover_subtype":           _fs("signal", "label", "n/a"),
    "premove_setup":           _fs("signal", "boolean", "n/a"),
    "premove_conviction":      _fs("signal", "score", "n/a"),
    "premove_conviction_label": _fs("signal", "label", "n/a"),
    # SC gate qualification (overall bool + per-engine pass/fail breakdown)
    "sc_m_gates":              _fs("signal", "boolean", "n/a"),
    "sc_m_gate_detail":        _fs("signal", "label", "n/a"),
    "sc_p_gates":              _fs("signal", "boolean", "n/a"),
    "sc_p_gate_detail":        _fs("signal", "label", "n/a"),
    # Engine subcomponents (nested by engine — context only, never a gate)
    "subcomponents":           _fs("signal", "score", "n/a"),
    # Structure shift (BOS/CHoCH) — data only, never a gate
    "structure_shift":         _fs("signal", "label", "n/a"),
    "structure_shift_ref":     _fs("reference", "usd", "n/a"),
    # Momentum acceleration + divergence (TV-analysis Phases 2+3 — context only)
    "mp_accel":                _fs("signal", "decimal", "n/a"),
    "mp_accel_state":          _fs("signal", "label", "n/a"),
    "div_state":               _fs("signal", "label", "n/a"),
    "div_bull_count":          _fs("signal", "score", "n/a"),
    "div_bear_count":          _fs("signal", "score", "n/a"),
    "div_oscs":                _fs("signal", "label", "n/a"),
    "div_date":                _fs("reference", "date", "n/a"),
    # Pin bar / inside bar (candlestick geometry — data only)
    "pin_bar_state":           _fs("signal", "label", "n/a"),
    "pin_bar_date":            _fs("reference", "date", "n/a"),
    "pin_bar_level":           _fs("reference", "usd", "n/a"),
    "inside_bar":              _fs("flag", "boolean", "n/a"),
    "pib_pattern":             _fs("flag", "boolean", "n/a"),
    # Smart Money kNN — CHoCH + instance-based learning (context only, never a gate)
    "choch_state":             _fs("signal", "label", "n/a"),
    "choch_date":              _fs("reference", "date", "n/a"),
    "knn_prob":                _fs("signal", "ratio", "n/a"),
    "knn_significant":         _fs("flag", "boolean", "n/a"),
    "knn_neighbors_used":      _fs("signal", "score", "n/a"),
    # side is n/a (not a fixed above/below-entry field): direction depends on
    # choch_state — above entry for BULLISH, below entry for BEARISH.
    "knn_tp1":                 _fs("target", "usd", "n/a"),
    "knn_tp2":                 _fs("target", "usd", "n/a"),
    "knn_tp3":                 _fs("target", "usd", "n/a"),
    # Sector (SRM) + thematic rotation DIRECTION per ticker
    "sector_trend_state":     _fs("signal", "label", "n/a"),
    "sector_rrg_quadrant":    _fs("signal", "label", "n/a"),
    "sector_rrg_direction":   _fs("signal", "label", "n/a"),
    "thematic_rrg_quadrant":  _fs("signal", "label", "n/a"),
    "thematic_rrg_direction": _fs("signal", "label", "n/a"),
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



def _v21_record_fields(tk: str, d: dict, lk: dict, sm: dict,
                       sector_grades: dict,
                       regime_level: str | None = None) -> dict:
    """AQE v2.1 / Data-Schema-v1.0 per-record fields. Bulletproof: returns a
    full key set with null values on any error, so the schema is always present.
    """
    fields = {
        "gics_sector": None, "gics_sector_name": None, "gics_gate": "CHECK",
        "thematic_basket": None, "thematic_grade": None,
        "thematic_parent_gics": None, "thematic_parent_grade": None,
        "thematic_baskets": [],
        # Sector (SRM) + thematic RRG DIRECTION per ticker — the day's rotation read
        "sector_trend_state": None,
        "sector_rrg_quadrant": None, "sector_rrg_direction": None,
        "thematic_rrg_quadrant": None, "thematic_rrg_direction": None,
        "rvol": None, "rs_spy_20d": None, "sma_distance_pct": None,
        "ma_20": None, "ma_50": None, "ma_100": None, "ma_200": None,
        # DSG-18 fib ladder (flat — retracement supports + swing anchors)
        "fib_swing_low": None, "fib_swing_high": None,
        "fib_236": None, "fib_382": None, "fib_500": None,
        "fib_618": None, "fib_786": None,
        "atr_14d": None,
        "vol_30d_ann": None, "beta_252d": None,
        # THE BRACKET — single source of truth (bracket_engine). Structural stop +
        # targets, R:R vs structural TP2, ATR-relative. Mechanical DSL/TP retired.
        "bracket": None,
        "held": False,
        # Structure shift (BOS/CHoCH) — data only, never a gate
        "structure_shift": None, "structure_shift_ref": None,
        # Health score (hold decision, held_positions only)
        "hl_score": None, "hl_state": None,
        # Enrichment Spec v2.0 — RS leadership + bracket-quality flags. setup_state
        # and breakout_* are HIDDEN from the feed (they overlapped Signal Radar's
        # DETECT layer); the engine still computes them, they are just not exported.
        "rs_down_day_20d": None, "rs_leadership": None,
        "atr_caution": False, "malformed_bracket": False,
        # Signal Radar (M14-M18) — additive DETECTION tags (never gate/size)
        "runner_setup": False, "runner_conviction": 0,
        "runner_conviction_label": None, "mover_subtype": None,
        "premove_setup": False, "premove_conviction": 0,
        "premove_conviction_label": None,
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

        # Sector rotation DIRECTION for the day (data only — gate unchanged):
        # SRM trend_state + the sector's RRG quadrant/direction (from srm_detail).
        if etf:
            _srm_rrg = (lk.get("srm_rrg") or {}).get(etf) or {}
            fields["sector_trend_state"] = (_srm_rrg.get("trend_state")
                                            or sector_grades.get(etf, {}).get("trend_state"))
            fields["sector_rrg_quadrant"] = _srm_rrg.get("rrg_quadrant")
            fields["sector_rrg_direction"] = _srm_rrg.get("rrg_direction")


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
                    "rrg_quadrant": tg.get("rrg_quadrant"),
                    "rrg_direction": tg.get("rrg_direction"),
                })
            fields["thematic_baskets"] = annotated
            primary = annotated[0]
            fields["thematic_basket"] = primary["basket"]
            fields["thematic_grade"] = primary["grade"]
            fields["thematic_parent_gics"] = primary["parent_gics"]
            fields["thematic_parent_grade"] = primary["parent_grade"]
            fields["thematic_rrg_quadrant"] = primary["rrg_quadrant"]
            fields["thematic_rrg_direction"] = primary["rrg_direction"]
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

        # ── ATR + vol / beta ───────────────────────────────────────────────
        _atr14 = d.get("atr14")
        if _is_num(_atr14) and _atr14 > 0:
            fields["atr_14d"] = round(float(_atr14), 2)
        fields["vol_30d_ann"] = (lk.get("vol30") or {}).get(tk)
        fields["beta_252d"] = (lk.get("beta252") or {}).get(tk)

        # ── THE BRACKET — single source of truth (bracket_engine) ──────────
        # Structural stop (tightest valid support) + structural targets
        # (resistance/MA/fib, nearest-first), R:R measured vs the structural TP2,
        # ATR-relative distances. Daily run → price = EOD close. Mechanical DSL/TP
        # is RETIRED — this is the only bracket AQE exposes. Un-bracketable names
        # carry valid=false + invalid_reason ("no valid bracket").
        _bracket = compute_bracket(d, _ma, regime_level,
                                   price=d.get("entry"), price_source="eod_close")
        fields["bracket"] = {_k: _bracket[_k] for _k in (
            "price", "price_source", "stop", "stop_type", "stop_atr_dist",
            "stop_date", "risk", "risk_pct", "targets", "rr",
            "rr_tp1", "rr_tp2", "rr_tp3", "atr_fallback_stop",
            "valid", "invalid_reason")}

        # ── Structure shift (BOS/CHoCH) — TV-analysis Phase 5 ─────────────
        # COB close vs the CONFIRMED swing anchors: above the last confirmed
        # swing high = BULLISH_BOS (break of structure); below the up-swing's
        # anchor low = BEARISH_CHOCH (character change); else RANGE. Null when
        # no swing is detected. Data only — never a gate.
        _entry_px = d.get("entry")
        _ssh, _ssl = _fib.get("swing_high"), _fib.get("swing_low")
        if _is_num(_entry_px) and _is_num(_ssh) and _is_num(_ssl):
            if _entry_px > _ssh:
                fields["structure_shift"] = "BULLISH_BOS"
                fields["structure_shift_ref"] = _ssh
            elif _entry_px < _ssl:
                fields["structure_shift"] = "BEARISH_CHOCH"
                fields["structure_shift_ref"] = _ssl
            else:
                fields["structure_shift"] = "RANGE"
                fields["structure_shift_ref"] = None

        # ── Health score (hold-decision, held_positions only) ─────────────
        # Readiness (rd_*) is HIDDEN from the AIC feed — the engine still runs
        # and persists to scores_daily, but the DETECT→ENTER→HOLD framework
        # gives AIC Signal Radar (detect) → alerts (enter) → Health (hold),
        # so rd_* is not stamped. Health (hl_score/hl_state) rides on every
        # record here; the feed scrub keeps it on held_positions and strips it
        # off the daily list (a hold read only matters once you're in a trade).
        _rdhl = (lk.get("rdhl") or {}).get(tk, {})
        for _rk in ("hl_score", "hl_state"):
            if _rk in _rdhl and _rdhl[_rk] is not None:
                fields[_rk] = _rdhl[_rk]

        # ── Enrichment Spec v2.0 — pre-computed per-ticker signals ────────
        # setup_state + breakout_* are NOT copied — they overlapped Signal Radar
        # (the DETECT layer) and are hidden from the feed. Only the RS-leadership
        # read + bracket-quality flags ride on the record.
        _enr = (lk.get("enrichment") or {}).get(tk, {})
        for _ek in ("rs_down_day_20d", "rs_leadership",
                     "atr_caution", "malformed_bracket"):
            if _ek in _enr and _enr[_ek] is not None:
                fields[_ek] = _enr[_ek]

        # ── Signal Radar (M14-M18) — additive DETECTION tags ──────────────
        # runner_setup / premove_setup + conviction + subtype. Never gate/size;
        # PM reads them like on_longlist/pe. % elsewhere = detection rate, not win rate.
        _sig = (lk.get("signals") or {}).get(tk, {})
        for _sk in ("runner_setup", "runner_conviction", "runner_conviction_label",
                     "mover_subtype", "premove_setup", "premove_conviction",
                     "premove_conviction_label"):
            if _sk in _sig and _sig[_sk] is not None:
                fields[_sk] = _sig[_sk]
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


# ---------------------------------------------------------------------------
# Engine SUBCOMPONENT surface (PM ruling: educate the AIC — the engines already
# compute ~60 sub-scores nightly into scores_daily; ship them, don't hide them).
# Readiness (rd_*) stays hidden (decision-framework ruling) and the Health
# sub-scores stay dropped (PM ruling) — this block covers the 6 scoring engines.
# ---------------------------------------------------------------------------
_SUBCOMPONENT_SPEC = {
    # engine → scores_daily columns (missing columns degrade to None)
    "flow": ["flow_score", "accum_score", "volume_score", "skew_score",
              "ext_score", "mfi", "cmf", "ha_quality_count"],
    "energy": ["vp_position_score", "price_action_score", "squeeze_score",
                "exhaustion_score", "atr_score", "en_pos50", "en_trend_bars"],
    "structure": ["rs_spy_score", "rs_accel_score", "base_score", "ms_pos_score",
                   "resist_score", "wk_score", "earn_score",
                   "rs_vs_spy", "rs_accel", "base_days", "bd_mode"],
    "mp": ["abs_mom_score", "mp_adx_score", "rel_mom_score", "trend_score",
            "roc_zscore", "excess_return", "adx_val", "di_bullish"],
    "bq": ["bq_range_tight", "bq_vol_dry", "bq_base_dur", "bq_ema_conv",
            "bq_base_days"],
    "pipe": ["pr_ret_12m", "pr_adx_score", "pr_rsi_score", "pr_vol_score",
              "pr_ma_score", "momentum_composite", "pipe_tier"],
}


def _sub_val(v):
    """Round numerics, pass strings/bools, NaN/missing → None."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v if v and v != "nan" else None
    try:
        f = float(v)
        return round(f, 2) if f == f else None
    except (TypeError, ValueError):
        return None


def _sub_str(v):
    """Clean string or None (NaN-safe)."""
    if v is None:
        return None
    s = str(v)
    return s if s and s not in ("nan", "None") else None


def _sub_int(v):
    """Clean int or None (NaN-safe)."""
    f = _sub_val(v)
    return int(f) if isinstance(f, float) or isinstance(f, int) else None


def _sub_bool(v):
    """Clean bool or None — only a genuine Python/NumPy bool passes through."""
    import numpy as _np
    if isinstance(v, (bool, _np.bool_)):
        return bool(v)
    return None


_NEW_ENGINE_NULL = {
    "mp_accel": None, "mp_accel_state": None, "div_state": None,
    "div_bull_count": None, "div_bear_count": None,
    "div_oscs": None, "div_date": None,
    "pin_bar_state": None, "pin_bar_date": None, "pin_bar_level": None,
    "inside_bar": None, "pib_pattern": None,
    "choch_state": None, "choch_date": None, "knn_prob": None,
    "knn_significant": None, "knn_neighbors_used": None,
    "knn_tp1": None, "knn_tp2": None, "knn_tp3": None,
}


def _new_engine_fields(row) -> dict:
    """Momentum-acceleration + divergence + pin-bar + smart-money-kNN fields
    from a scores_daily row (TV-analysis Phases 2/3/6/7). Missing columns
    degrade to None."""
    if row is None:
        return dict(_NEW_ENGINE_NULL)
    get = row.get if hasattr(row, "get") else (lambda k: None)
    return {
        "mp_accel": _sub_val(get("mp_accel")),
        "mp_accel_state": _sub_str(get("mp_accel_state")),
        "div_state": _sub_str(get("div_state")),
        "div_bull_count": _sub_int(get("div_bull_count")),
        "div_bear_count": _sub_int(get("div_bear_count")),
        "div_oscs": _sub_str(get("div_oscs")),
        "div_date": _sub_str(get("div_date")),
        "pin_bar_state": _sub_str(get("pin_bar_state")),
        "pin_bar_date": _sub_str(get("pin_bar_date")),
        "pin_bar_level": _sub_val(get("pin_bar_level")),
        "inside_bar": _sub_bool(get("inside_bar")),
        "pib_pattern": _sub_bool(get("pib_pattern")),
        "choch_state": _sub_str(get("choch_state")),
        "choch_date": _sub_str(get("choch_date")),
        "knn_prob": _sub_val(get("knn_prob")),
        "knn_significant": _sub_bool(get("knn_significant")),
        "knn_neighbors_used": _sub_int(get("knn_neighbors_used")),
        "knn_tp1": _sub_val(get("knn_tp1")),
        "knn_tp2": _sub_val(get("knn_tp2")),
        "knn_tp3": _sub_val(get("knn_tp3")),
    }


def _subcomponents(row) -> dict | None:
    """Nested per-engine sub-score block from a scores_daily row (Series/dict).
    Always returns the full key set (None-filled) so the schema is stable."""
    if row is None:
        return None
    try:
        get = row.get if hasattr(row, "get") else (lambda k: None)
        return {eng: {c: _sub_val(get(c)) for c in cols}
                for eng, cols in _SUBCOMPONENT_SPEC.items()}
    except Exception:  # noqa: BLE001 — additive, never blocks the export
        return None


def _held_sc_gates(s) -> dict:
    """SC_MOMENTUM/SC_POSITION gate breakdown for a held record from its
    scores_daily row (`s`), or nulls when the name wasn't scored. Same thresholds
    as the daily_list rows (SC_M_GATES / SC_P_GATES)."""
    if s is None:
        return {"sc_m_gates": None, "sc_m_gate_detail": None,
                "sc_p_gates": None, "sc_p_gate_detail": None}
    _gm = scoring.gate_breakdown_momentum(
        s.get("flow_100"), s.get("energy_100"), s.get("structure_100"),
        s.get("mp_100"), s.get("elder_score"))
    _gp = scoring.gate_breakdown_position(
        s.get("flow_100"), s.get("energy_100"), s.get("structure_100"),
        s.get("mp_100"), s.get("bq_100"), s.get("k39_gate"))
    return {"sc_m_gates": _gm["pass"], "sc_m_gate_detail": _gm["detail"],
            "sc_p_gates": _gp["pass"], "sc_p_gate_detail": _gp["detail"]}


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
            # SC gate breakdown (same thresholds as daily_list rows) so the AIC
            # reads which check a held name fails without recomputing.
            **_held_sc_gates(s),
            # Engine subcomponents — same nightly sub-score block as daily_list.
            "subcomponents": _subcomponents(s),
            # Momentum acceleration + divergence (same fields as daily_list rows)
            **_new_engine_fields(s),
            # Health = the HOLD decision (trend integrity), the whole point of the
            # held book. Sourced from scores_daily; held names are force-scored in
            # the orchestrator so this is populated even off the top-50 screen.
            "hl_score": round(sg("hl_score"), 1) if sg("hl_score") is not None else None,
            "hl_state": (str(s.get("hl_state")) if s is not None and pd.notna(s.get("hl_state")) else None),
            # Signal-ledger DETECTION tags (from Signal Radar) so a held name shows
            # whether it's ALSO firing runner/pre-move — same as the daily_list rows.
            "runner_setup": bool(v21.get("runner_setup")),
            "runner_conviction_label": v21.get("runner_conviction_label"),
            "premove_setup": bool(v21.get("premove_setup")),
            "premove_conviction_label": v21.get("premove_conviction_label"),
            "in_ledger": bool(v21.get("runner_setup") or v21.get("premove_setup")),
            "cob_price": sg("close"),   # COB close (FMP) — held_book exposure basis
            "beta_30d": (betas.get(tk) or {}).get(30),
            "atr_14d": v21["atr_14d"],
            "gics_sector": v21["gics_sector"], "gics_gate": v21["gics_gate"],
            "rs_spy_20d": v21["rs_spy_20d"], "sma_distance_pct": v21["sma_distance_pct"],
            "rvol": v21["rvol"],
            # absolute MA ladder — so the live alert engine can evaluate MA
            # support on held names uniformly with candidates.
            "ma_20": v21["ma_20"], "ma_50": v21["ma_50"],
            "ma_100": v21["ma_100"], "ma_200": v21["ma_200"],
            # DSG-18 flat fib ladder.
            "fib_swing_low": v21["fib_swing_low"], "fib_swing_high": v21["fib_swing_high"],
            "fib_236": v21["fib_236"], "fib_382": v21["fib_382"], "fib_500": v21["fib_500"],
            "fib_618": v21["fib_618"], "fib_786": v21["fib_786"],
            "vol_30d_ann": v21["vol_30d_ann"], "beta_252d": v21["beta_252d"],
            # THE BRACKET — structural stop/targets (single source of truth).
            "bracket": v21["bracket"],
            # Structure shift (BOS/CHoCH) — v21 already computes this; was being
            # dropped since this dict cherry-picks keys instead of merging **v21.
            "structure_shift": v21.get("structure_shift"),
            "structure_shift_ref": v21.get("structure_shift_ref"),
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
        # PM ruling: PTRS drops the Sector-Health adjustment (that is a committee
        # deliberation; SRM grade + sector/thematic RRG give the qualitative read).
        # PTRS = the engine score, no sector discount.
        r = compute_ptrs(sc_mom, 0.0)
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

    # ---- Sector rotation per ticker: SRM trend_state + sector RRG (from srm_detail,
    # which carries trend_state/rrg_quadrant/rrg_direction; sector_grades may not).
    _v21_lk["srm_rrg"] = sl.get("srm_detail") or {}

    # ---- Signal Radar (M14-M18) — per-ticker DETECTION tags + standalone block ----
    # runner_setup / premove_setup + conviction + subtype from the FULL scored
    # universe. Computed ONCE: the lookup stamps the 5 fields onto each list record,
    # and the ranked lists become the standalone `signal_radar` block below (so the
    # QUIET pre-move names — which never reach the longlist — are still surfaced).
    # ADDITIVE + read-only; a failure degrades to no tags / empty block, never blocks
    # the export or changes any existing field.
    _radar = None
    try:
        from src.engines.signal_radar import compute_radar
        _radar = compute_radar()
        _v21_lk["signals"] = _radar["lookup"]
        print(f"  Signal Radar: {len(_radar['runner_setup'])} runner / "
              f"{len(_radar['premove_setup'])} pre-move tags "
              f"({len(_radar['lookup'])} scored)")
    except Exception as _exc:  # noqa: BLE001
        _v21_lk["signals"] = {}
        print(f"  [WARN] Signal Radar skipped: {_exc}")

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
        from src.data.ptj import load_held_positions, ptj_status
        _held = load_held_positions()
        export["held_positions_status"] = ptj_status()
    except Exception:  # noqa: BLE001
        _held = []
        export["held_positions_status"] = "unknown"
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
        # Only Health is stamped onto records (held_positions only). Readiness
        # (rd_*) stays computed + persisted in scores_daily but is not read into
        # the export — it is hidden from the AIC feed.
        _rd_hl_fields = ["hl_score", "hl_state"]
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
            "flow": round(e["flow"], 1),
            "energy": round(e["energy"], 1),
            "structure": round(e["structure"], 1),
            "mp": round(e["mp"], 1),
            "elder": e["elder"],
            "mp_state": _mp_states.get(tk, c.get("mp_state", "")),
            "entry": c["levels"].get("entry"),
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
            "flow": round(eng["flow"], 1),
            "energy": round(eng["energy"], 1),
            "structure": round(eng["structure"], 1),
            "mp": round(eng["mp"], 1),
            "elder": eng["elder"],
            "mp_state": _mp_states.get(tk, pe.get("mp_state", "")),
            "entry": pe["levels"].get("entry"),
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
            "flow": round(e["flow"], 1),
            "energy": round(e["energy"], 1),
            "structure": round(e["structure"], 1),
            "mp": round(e["mp"], 1),
            "elder": e["elder"],
            "mp_state": _mp_states.get(rm["ticker"], rm.get("mp_state", "")),
            "entry": rm["levels"].get("entry"),
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

    # Signal Radar alert pool — full records for the radar names (esp. QUIET
    # pre-movers, which sit below every list) so the alert engine can WATCH them
    # and fire when one runs EARLY, before it graduates onto the longlist. Built
    # inside the scores block below where sc_df + _wl_record are in scope.
    _radar_pool_recs: list = []

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
        # PTRS = engine score, no Sector-Health adjustment (PM ruling; SRM/RRG
        # carry the sector read separately).
        sc_df["_ptrs"] = sc_df["sc_momentum"].fillna(0).round(1)
        sc_df = sc_df[~sc_df["ticker"].isin(set(GICS_ETFS) | {"SPY"})].copy()

        def _wl_record(wr, rank, source):
            tk = wr["ticker"]
            d = dsl_all.get(tk, {})
            wfl = round(float(wr["_floor"]), 1)
            wsc = float(wr.get("sc_momentum", 0)) or 0
            wpr = float(wr.get("pipe_rank", 0))
            # SC gate breakdown — computed from the RAW engine scores (not the
            # rounded display values) against the exact SC_M_GATES/SC_P_GATES
            # thresholds, so the feed shows WHICH check a name fails.
            _gm = scoring.gate_breakdown_momentum(
                wr.get("flow_100"), wr.get("energy_100"),
                wr.get("structure_100"), wr.get("mp_100"), wr.get("elder_score"))
            _gp = scoring.gate_breakdown_position(
                wr.get("flow_100"), wr.get("energy_100"),
                wr.get("structure_100"), wr.get("mp_100"), wr.get("bq_100"),
                wr.get("k39_gate"))
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
                "flow": round(float(wr.get("flow_100", 0)), 1),
                "energy": round(float(wr.get("energy_100", 0)), 1),
                "structure": round(float(wr.get("structure_100", 0)), 1),
                "mp": round(float(wr.get("mp_100", 0)), 1),
                "elder": round(float(wr.get("elder_score", 0)), 1),
                # SC gate qualification (overall bool + per-engine breakdown)
                "sc_m_gates": _gm["pass"], "sc_m_gate_detail": _gm["detail"],
                "sc_p_gates": _gp["pass"], "sc_p_gate_detail": _gp["detail"],
                # Engine SUBCOMPONENTS — the nightly sub-scores behind each engine
                # read (nested by engine; see field_glossary). Educates the AIC on
                # WHY an engine scored what it did. Zero extra compute.
                "subcomponents": _subcomponents(wr),
                # Momentum acceleration + divergence (TV-analysis Phases 2+3)
                **_new_engine_fields(wr),
                "mp_state": _mp_states.get(tk, str(wr.get("mp_state", ""))),
                "entry": d.get("entry"),
                "elder_5d": elder5.get(tk),
                "rank_explain": _rank_explain(
                    wpr, wfl, wsc, tk in pe_tickers, tk, sm, sector_grades),
                "source": source,
                "pe": tk in pe_tickers,
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

        # Signal Radar pool — full records (DSL levels + scores + radar tags) for
        # every runner/pre-move name, so the alert engine can watch for an EARLY
        # move. Pre-movers matter most: they are quiet and below every list.
        if _radar is not None:
            _sc_by_tk = {r["ticker"]: r for _, r in sc_df.iterrows()}
            _rr = 0
            for _grp, _src in (("premove_setup", "radar-premove"),
                               ("runner_setup", "radar-runner")):
                for _e in _radar.get(_grp, []):
                    _wr = _sc_by_tk.get(_e.get("ticker"))
                    if _wr is None:
                        continue
                    _rr += 1
                    _radar_pool_recs.append(_wl_record(_wr, _rr, _src))

    # ---- TWO lists (PM): the single screening `longlist` + the standalone
    # `elder_list`. Longlist replaces watchlist/PE/top_picks. Elder list is its OWN
    # list — sole criterion Elder ≥ 8, nothing else (the strong-breakout catcher).
    # `on_longlist` is RETIRED (undocumented badge, AIC noise). held_positions stays.
    _merged: dict = {}
    for _tname in ("top_picks", "edge_list", "longlist", "watchlist"):
        for _r in export.get(_tname, []):
            _tk = _r.get("ticker")
            if not _tk:
                continue
            if _tk in _merged:                       # OR-merge the pe flag
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
                _st = ((_r.get("bracket") or {}).get("targets")) or []
                _res = _st[0].get("price") if _st and isinstance(_st[0], dict) else None
                _r["elder_context"] = compute_elder_context(
                    _e5, _hourly.get(_tk) or [], _daily, resistance_price=_res)

        _attach_elder(_longlist)
        _attach_elder(_elderlist)

        # ── Volume-validated pivots (TV-analysis Phase 4) ─────────────────
        # A level DEFENDED on high volume is a stronger level. Delegates to
        # bracket_engine.stamp_bracket_volume (the SINGLE source of truth for
        # this math — adhoc.py's ad-hoc scorer calls the identical function on
        # its own fetched bars, so the daily feed and ad-hoc scoring can never
        # drift onto two different vol_ratio formulas). Best-effort per record.
        def _stamp_vol_validation(_rows):
            for _r in _rows:
                try:
                    _g = _grp.get(_r.get("ticker"))
                    _b = _r.get("bracket") or {}
                    if _g is None or "volume" not in _g.columns or not _b:
                        continue
                    stamp_bracket_volume(_b, _g["date"], _g["volume"])
                except Exception:  # noqa: BLE001
                    continue

        _stamp_vol_validation(_longlist)
        _stamp_vol_validation(_elderlist)
        _stamp_vol_validation(_radar_pool_recs)
        # Held positions get the SAME volume-validated bracket read as every
        # other tier — the whole point of "one suite everywhere" (PM ruling).
        _stamp_vol_validation(export.get("held_positions") or [])
    except Exception:  # noqa: BLE001 — elder_context is additive, never blocks export
        for _r in _longlist + _elderlist:
            _r.setdefault("elder_pattern", None)
            _r.setdefault("elder_context", None)

    # HARD CUT (PM ruling) — longlist/elder_list are NO LONGER exported keys. The
    # single `daily_list` (built below = longlist ∪ elder ∪ ledger, each row flagged
    # on_longlist/on_elder/in_ledger) is the ONE list the AIC + UI read. The internal
    # _longlist/_elderlist still drive daily_list, the alert universe, and the
    # Signal-Radar overlap flags — they are just not surfaced as separate export keys.
    export.pop("longlist", None)
    export.pop("elder_list", None)
    # Alert universe (PM ruling 2026-07-07) = the daily AQE list + signal ledger.
    # The broad SC>=50 `_alert_pool` was DROPPED (it was noise); the Signal-Radar
    # pre-move names backfill the tighter set. Alerts fire only on names AQE
    # actually surfaces that day.
    _alert_seen = {r.get("ticker") for r in _longlist + _elderlist if r.get("ticker")}

    # Signal Radar pool — the QUIET pre-movers (and any runner) nothing else
    # watches, so an EARLY breakout still fires an alert. Dedup against the daily
    # list (longlist/elder); require DSL levels to evaluate.
    _radar_covered = _alert_seen
    _radar_pool: list = []
    _radar_seen: set = set()
    for _r in _radar_pool_recs:
        _tk = _r.get("ticker")
        if (not _tk or _tk in _radar_covered or _tk in _radar_seen
                or not (_r.get("bracket") or {}).get("stop")):
            continue
        _radar_seen.add(_tk)
        _radar_pool.append(_r)
    export["_radar_pool"] = _radar_pool
    for _k in ("top_picks", "edge_list", "watchlist"):
        export.pop(_k, None)

    # ---- THE DAILY LIST — collapse longlist ∪ elder ∪ signal-ledger into ONE
    # list (PM ruling). Each name appears ONCE, flagged so the AIC reads
    # membership + correspondence in a single row (no cross-checking 3 lists).
    # `on_longlist` = passed the longlist screen (SC_MOM≥65 & PTRS≥60 & Elder≥7,
    # via longlist_screen.passes on `_longlist`) — the REAL membership (the stale
    # recipe-set badge is gone). Elder is folded in because event-driven
    # SUPER-RUNNERS hit Elder≥8 WITHOUT the normal scoring/structure sequence.
    # `_radar_pool` supplies full records for ledger names not on the longlist/elder.
    _dl: dict = {}
    for _r in _longlist:
        _tk = _r.get("ticker")
        if _tk:
            _dl[_tk] = {**_r, "on_longlist": True, "on_elder": False}
    for _r in _elderlist:
        _tk = _r.get("ticker")
        if not _tk:
            continue
        if _tk in _dl:
            _dl[_tk]["on_elder"] = True
        else:
            _dl[_tk] = {**_r, "on_longlist": False, "on_elder": True}
    for _r in _radar_pool:                      # ledger names not on longlist/elder
        _tk = _r.get("ticker")
        if _tk and _tk not in _dl:
            _dl[_tk] = {**_r, "on_longlist": False, "on_elder": False}
    for _r in _dl.values():
        _r["in_ledger"] = bool(_r.get("runner_setup") or _r.get("premove_setup"))
    _daily_list = sorted(_dl.values(), key=lambda r: (r.get("ptrs") or 0), reverse=True)
    for _i, _r in enumerate(_daily_list, 1):
        _r["rank"] = _i
    export["daily_list"] = _daily_list

    export["summary"] = {
        "daily_count": len(_daily_list),
        "longlist_count": sum(1 for r in _daily_list if r.get("on_longlist")),
        "elder_count": sum(1 for r in _daily_list if r.get("on_elder")),
        "ledger_count": sum(1 for r in _daily_list if r.get("in_ledger")),
        "held_count": len(export.get("held_positions") or []),
        "held_positions_status": export.get("held_positions_status", "unknown"),
    }

    # ---- Standalone Signal Radar block (M14-M18) — the one place AIC scans the
    # radar daily. Two ranked lists over the FULL scored universe, each name flagged
    # with whether it is ALSO on the watchlist / elder list (overlap at a glance).
    # DETECTION tags only — never a gate, never sizing. Additive; empty on failure.
    try:
        if _radar is not None:
            _ll_tk = {r.get("ticker") for r in _longlist if r.get("ticker")}
            _el_tk = {r.get("ticker") for r in _elderlist if r.get("ticker")}
            for _grp in ("runner_setup", "premove_setup"):
                for _e in _radar.get(_grp, []):
                    _e["on_longlist"] = _e["ticker"] in _ll_tk
                    _e["on_elder"] = _e["ticker"] in _el_tk
            export["signal_radar"] = {
                "scan_date": _radar.get("scan_date"),
                "n_scored": _radar.get("n_scored"),
                "runner_setup": _radar.get("runner_setup", []),
                "premove_setup": _radar.get("premove_setup", []),
                "note": _radar.get("note"),
            }
            export["summary"]["runner_count"] = len(_radar.get("runner_setup", []))
            export["summary"]["premove_count"] = len(_radar.get("premove_setup", []))
    except Exception:  # noqa: BLE001 — radar block is additive, never blocks export
        pass

    # ---- Feed scrub (PM ruling) — clean the AIC feed before the uniform pass.
    # Decision framework: DETECT (Signal Radar) → ENTER (alert engine) → HOLD
    # (Health). Readiness overlapped premove_setup + the alerts, so it is NOT
    # shown to the AIC (the engine + scores_daily still compute it — just hidden).
    #  • `pe` (deprecated) + `rank_explain` (useless): gone everywhere.
    #  • Readiness (all rd_*): hidden from the whole feed.
    #  • Health: composite+state (hl_score/hl_state) on held_positions ONLY (it's a
    #    hold decision); the 4 hl_ sub-scores dropped everywhere.
    #  • Enrichment overlap (setup_state + breakout_*): hidden — Signal Radar IS the
    #    DETECT layer, so these competing detect signals are stripped (engine kept).
    # (`on_longlist` is NO LONGER scrubbed — it's now the real, documented longlist
    #  membership flag on daily_list, not the retired stale recipe badge.)
    _DEPRECATED = ("pe", "rank_explain")
    _READINESS = ("rd_score", "rd_state", "rd_compression", "rd_trigger",
                  "rd_pos_mod", "rd_rs_bonus")
    _HL_SUB = ("hl_trend", "hl_flow", "hl_rs", "hl_risk")
    _HEALTH_CORE = ("hl_score", "hl_state")
    _ENRICH_OVERLAP = ("setup_state", "breakout_conviction", "breakout_grade",
                       "breakout_pattern", "breakout_bar_date")
    for _lname in ("daily_list", "_radar_pool"):
        for _r in export.get(_lname) or []:
            for _dk in _DEPRECATED + _READINESS + _HL_SUB + _HEALTH_CORE + _ENRICH_OVERLAP:
                _r.pop(_dk, None)
    for _r in export.get("held_positions") or []:
        for _dk in _DEPRECATED + _READINESS + _HL_SUB + _ENRICH_OVERLAP:  # keep hl_score/hl_state
            _r.pop(_dk, None)

    # ---- Uniform schema per list (null-fill each to one key set) ----
    for _lname in ("daily_list",):
        _rows = export.get(_lname) or []
        if not _rows:
            continue
        _all_keys: set[str] = set()
        for _rec in _rows:
            _all_keys.update(_rec.keys())
        _order = list(_rows[0].keys())
        _order += [k for k in sorted(_all_keys) if k not in _order]
        export[_lname] = [{k: _rec.get(k) for k in _order} for _rec in _rows]

    # ---- Permanent schema validation — BLOCKS export on missing fields ----
    _REQUIRED_FIELDS = [
        "ticker", "sc_momentum", "ptrs", "flow", "energy", "structure",
        "mp", "elder", "entry", "atr_14d",
        "beta_30d", "elder_5d", "mp_state", "pipe_rank", "floor",
        # DSG-18 flat fib ladder
        "fib_swing_low", "fib_swing_high",
        "fib_236", "fib_382", "fib_500", "fib_618", "fib_786",
        "vol_30d_ann", "beta_252d",
        # THE BRACKET — single source of truth (structural stop + targets)
        "bracket",
        # Enrichment Spec v2.0 (setup_state + breakout_* hidden — Signal Radar overlap)
        "rs_down_day_20d", "rs_leadership",
        "atr_caution", "malformed_bracket",
        # SC gate qualification (overall bool + per-engine breakdown alongside)
        "sc_m_gates", "sc_p_gates",
        # Engine subcomponents block (nested; None-filled when a column is absent)
        "subcomponents",
        # Structure shift (BOS/CHoCH — null when no swing detected)
        "structure_shift",
        # Momentum acceleration + divergence + pin-bar + smart-money kNN
        # (null until the next scores run)
        "mp_accel", "div_state", "pin_bar_state", "choch_state",
    ]
    for _rec in export.get("daily_list") or []:
        _missing = [f for f in _REQUIRED_FIELDS if f not in _rec]
        if _missing:
            raise ValueError(
                f"SCHEMA VIOLATION: daily_list record "
                f"'{_rec.get('ticker', '?')}' missing fields: {_missing}"
            )

    # ---- Data-quality guard — VALUE-level, not just key-level (2026-07-15 ruling).
    # _REQUIRED_FIELDS above only checks a key exists; a NaN engine result (e.g.
    # insufficient bar-history warmup) silently becomes JSON null via _num() and
    # sails straight through that check. NEVER blocks the export — a single
    # thin-history ticker must not take down the whole nightly committee feed —
    # but it is surfaced loudly (top-level `data_quality` block + a pipeline log
    # line + a Scanner UI warning) so a blank is never mistaken for "nothing to
    # see here".
    export["data_quality"] = _compute_data_quality(
        export.get("daily_list") or [], export.get("held_positions") or [])

    return export


# Fields that, for a ticker which made it into daily_list/held_positions at all
# (i.e. went through full scoring), must never be null — a null here means a
# real data gap (thin history, an FMP gap, a degenerate calc), not a
# legitimate "not detected" state (unlike div_state=NONE,
# structure_shift=null-no-swing, etc., which ARE valid states and are
# intentionally excluded from this list).
_HARD_REQUIRED_NONNULL = [
    "sc_momentum", "flow", "energy", "structure", "mp", "elder",
    "entry", "atr_14d", "bracket",
]


def _compute_data_quality(daily_list: list[dict], held_positions: list[dict]) -> dict:
    """Flag records with a null core field despite having been fully scored.

    Value-level companion to the key-level `_REQUIRED_FIELDS` guard above.
    Never raises/blocks — returns a flag list for the caller to surface.
    """
    flagged: list[dict] = []
    for tier, rows in (("daily_list", daily_list), ("held_positions", held_positions)):
        for rec in rows:
            nulls = [f for f in _HARD_REQUIRED_NONNULL if rec.get(f) is None]
            if nulls:
                flagged.append({"ticker": rec.get("ticker"), "tier": tier, "null_fields": nulls})
    return {"flagged_count": len(flagged), "flagged": flagged}


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
        "data_quality": export.get("data_quality", {"flagged_count": 0, "flagged": []}),
        **({"reason": reason} if reason else {}),
    }


# Legacy — keep for backward compat
def sync_to_drive(files: list[Path] | None = None) -> dict:
    """Export daily JSON to Google Drive (via local mount)."""
    return export_to_drive()
