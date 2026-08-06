"""Agentic AQE — the data-contract augmentation layer (D-24 / D-29).

PURPOSE
-------
AQE already computes every field. What the AGENTIC consumer (Aegis's voices) needs on
top is: a definition, an enum set, and a method for EVERY exported field — so an agent
reads understanding, not a bare number. This module is that layer.

NON-BREAKING BY CONSTRUCTION
----------------------------
It does NOT change any existing calculation, field, or the production export. It only
ADDS to two already-present-but-incomplete export blocks:
  * field_glossary       (was 52/97 fields) -> complete
  * field_schema_enums   (was 3 fields)     -> every categorical field
Call `augment_export(export_dict)` at the end of the export builder to fill them in
place. Existing consumers see the same fields plus richer metadata; nothing is removed.

PROVENANCE
----------
Definitions/methods transposed from src/engines/*.py docstrings; enum sets from engine
string literals UNION observed values in the live feed. The 3 genuinely-undocumented
fields are marked UNDOCUMENTED for the AQE owner to define — never guessed.
"""
from __future__ import annotations

# ── Enum sets: engine-authoritative (grepped from src/engines) ∪ observed in the feed ──
FIELD_ENUMS = {
    "mp_state": ["BUILDING", "STRONG", "FADING"],
    "mp_accel_state": ["ACCELERATING", "FLAT", "DECELERATING"],
    "choch_state": ["BULLISH", "BEARISH", "NONE"],
    "div_state": ["BULLISH", "BEARISH", "MIXED", "NONE"],
    "pin_bar_state": ["NONE", "BULLISH_PIN", "BEARISH_PIN"],          # pin_bar.py
    "structure_shift": ["RANGE", "BULLISH_BOS", "ABOVE_STRUCTURE", "BEARISH_CHOCH"],  # ABOVE_STRUCTURE added 2026-08-06 (broke out earlier and kept running)
    "elder_pattern": ["ACCELERATION", "ACCUMULATION_BASE", "CORRECTION_REENTRY", "INTERRUPTED", "SUSTAINED"],
    "gics_gate": ["PASS", "WATCH", "CAUTION", "BLOCKED"],              # srm.sector_entry_gate
    "rs_leadership": ["LEADER", "IN-LINE", "LAGGARD"],
    "sector_trend_state": ["Declining — Avoid", "Momentum Fading — Hold, Don't Add",
                            "Recovering From Weakness — Watch for Entry", "Leading — Deploy"],
    "sector_rrg_quadrant": ["LEADING", "WEAKENING", "LAGGING", "IMPROVING"],
    "sector_rrg_direction": ["ENTERING", "DEEPENING", "EXITING"],
    "thematic_grade": ["DEPLOY", "HOLD", "TURNING", "WATCH", "AVOID"],
    "thematic_parent_grade": ["DEPLOY", "HOLD", "TURNING", "WATCH", "AVOID"],
    "thematic_rrg_quadrant": ["LEADING", "WEAKENING", "LAGGING", "IMPROVING"],
    "thematic_rrg_direction": ["ENTERING", "DEEPENING", "EXITING"],
    "hl_state": ["HOLD", "TIGHTEN", "EXIT"],                           # health.py
}

# ── Glossary fills for the 45 fields the production glossary omits ──
# Engine-sourced where the engine computes it; factual for self-evident market fields.
GLOSSARY_FILL = {
    "sc_momentum": "SC_MOMENTUM composite [0,100], uncapped weighted average of flow/energy/structure/mp/elder (scoring.py v1.8.0); floors not applied to the composite, Elder gate enforced at qualification.",
    "sc_momentum_raw": "The ungated SC_MOMENTUM weighted average (== sc_momentum in v1.8.0).",
    "flow": "Flow engine [0,100] (flow.py): MFI+CMF+Heikin-Ashi quality + A/D linreg + volume trend/spike + up/down skew.",
    "energy": "Energy engine [0,100] (energy.py): range-position proxy + price-action + squeeze + exhaustion + ATR.",
    "structure": "Structure engine [0,100] (structure.py): clip((rs_spy+rs_accel+base+ms_pos+resist+wk+earn)/95*100).",
    "mp": "Momentum Persistence [0,100] (mp.py): abs_mom+ADX+rel_mom+trend.",
    "mp_state": "Momentum-persistence phase label (mp.py).",
    "elder": "Elder Impulse score [0,10] (elder.py): state{0,2,4}+slope{0-3}+MACD-histogram{0-3}.",
    "elder_5d": "Elder impulse read over a 5-day context (list of recent impulse states).",
    "elder_context": "Hourly VWAP/VCP/exhaustion context object behind the elder read (elder_context.py).",
    "elder_pattern": "Labelled Elder impulse pattern (see enum).",
    "beta_30d": "30-day beta vs SPY — the portfolio-gate window (D-6).",
    "day_vol": "(formerly `rvol`) The day's volume over the name's own prior 20-day average; >1 = above-normal participation.",
    "rs_spy_20d": "20-day relative strength vs SPY (%).",
    "sma_distance_pct": "Percent distance of price from its SMA — extension (large + = extended, ~0 = at support).",
    "ma_20": "20-day simple moving average of close.",
    "ma_50": "50-day simple moving average of close.",
    "ma_100": "100-day simple moving average of close.",
    "ma_200": "200-day simple moving average of close.",
    "fib_swing_low": "Lower anchor (swing low) of the Fibonacci retracement.",
    "fib_swing_high": "Upper anchor (swing high) of the Fibonacci retracement.",
    "fib_236": "23.6% Fibonacci retracement of swing_low->swing_high (USD).",
    "fib_382": "38.2% Fibonacci retracement (USD).",
    "fib_500": "50% retracement (USD).",
    "fib_618": "61.8% Fibonacci retracement (USD).",
    "fib_786": "78.6% Fibonacci retracement (USD).",
    "rank": "Overall daily rank of the name in the scored universe.",
    "pipe_rank": "Momentum-pipeline rank (pipeline_rank.py).",
    "gics_sector": "GICS sector ETF code the name maps to.",
    "gics_sector_name": "GICS sector name.",
    "gics_gate": "Sector entry gate PASS/WATCH/CAUTION/BLOCKED (srm.sector_entry_gate: grade+RRG+macro).",
    "thematic_basket": "Thematic basket the name belongs to (srm thematic layer).",
    "thematic_baskets": "All thematic baskets the name belongs to. Each entry carries grade, grade_path, breadth_pct, parent_capped_grade, parent_gics, parent_grade and RRG.",
    "thematic_grade": "Grade of the name's thematic basket (see enum) — the theme's OWN reading, UNCAPPED since 2026-08-05. Read it alongside thematic_parent_grade rather than assuming the sector already constrained it.",
    "thematic_parent_gics": "Parent GICS sector of the thematic basket.",
    "thematic_parent_grade": "Grade of the parent GICS sector.",
    "on_elder": "Flag: name is on the Elder list.",
    "on_longlist": "Flag: name is on the longlist.",
    "in_ledger": "Flag: name is currently tracked in the nomination ledger.",
    "held": "Flag: name is currently held.",
    "source": "Data-source tag for the record.",
    "floor": "UNDOCUMENTED — AQE owner to define (meaning not recoverable from code comments).",
    "fip_spike_excluded": "UNDOCUMENTED — AQE owner to define (FIP spike-exclusion flag; confirm semantics).",
    "fip_window_effective": "UNDOCUMENTED — AQE owner to define (effective FIP window; confirm semantics).",
}

# ── Subcomponent documentation (the sub-scores behind each engine composite) ──
SUBCOMPONENT_DOCS = {
    "flow": "MFI + CMF + Heikin-Ashi quality (flow_score), A/D linreg (accum_score), volume trend/spike (volume_score), up/down skew (skew_score); diagnostics mfi, cmf, ha_quality_count.",
    "energy": "range-position proxy (vp_position_score), price action, squeeze, exhaustion, ATR; diagnostics en_pos50, en_trend_bars.",
    "structure": "RS-vs-SPY, RS-acceleration, base, market-structure position, resistance, weekly, earnings sub-scores; diagnostics rs_vs_spy, rs_accel, base_days, bd_mode.",
    "mp": "absolute momentum, ADX, relative momentum, trend sub-scores; diagnostics roc_zscore, excess_return, adx_val, di_bullish.",
    "bq": "Base Quality: range tightness (ATR5/ATR20), volume dry-up, base duration, EMA convergence; used by SC_POSITION.",
    "pipe": "Pipeline rank inputs: 12m return, ADX, RSI, volume, MA sub-scores, momentum_composite, pipe_tier.",
}

UNDOCUMENTED = ["floor", "fip_spike_excluded", "fip_window_effective"]


def augment_export(export: dict) -> dict:
    """Fill field_glossary + field_schema_enums IN PLACE, non-destructively.
    Existing entries win (never overwrite AQE's own definition); we only ADD missing keys."""
    fg = export.setdefault("field_glossary", {})
    for k, v in GLOSSARY_FILL.items():
        fg.setdefault(k, v)
    fse = export.setdefault("field_schema_enums", {})
    for k, v in FIELD_ENUMS.items():
        fse.setdefault(k, v)
    export["_agentic_subcomponent_docs"] = SUBCOMPONENT_DOCS
    export["_agentic_dictionary_version"] = "1.0"
    return export


def coverage(export: dict) -> dict:
    """Report glossary/enum coverage after augmentation — for the Agentic AQE tab."""
    row = next((r for r in export.get("daily_list", []) if isinstance(r, dict)), {})
    fields = [f for f in row if not f.startswith("_")]
    fg = export.get("field_glossary", {})
    fse = export.get("field_schema_enums", {})
    return {
        "total_fields": len(fields),
        "glossary_covered": sum(1 for f in fields if f in fg),
        "enum_fields": len(fse),
        "undocumented": [f for f in UNDOCUMENTED if f in fields],
        "subcomponent_engines": list(SUBCOMPONENT_DOCS),
    }
