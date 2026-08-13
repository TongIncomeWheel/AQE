"""Emit the AQE data taxonomy as CSV.

Output: docs/AQE_DATA_TAXONOMY.csv

Columns
    field              the name that actually ships — the engine's own
                       DataFrame column where one exists, even where a later
                       merge step renames it for export (that rename is
                       recorded in `represents`, never silently followed)
    parent             the field this one feeds; blank at the root
    level              composite | engine | component | leaf | block | context
    output             numeric range, type, or literal
    state              enum values, pipe-separated; blank if not categorical
    represents         what the number is, one clause
    source             the REAL calculator: a src/ file:line that computes
                       this value, or an external source (FMP endpoint, the
                       PTJ broker journal, cboe.com, cftc.gov). Never the
                       export's own field_glossary — that dict describes
                       fields, it does not compute them, and citing it as a
                       "source" was citing documentation as evidence.
    formula            the arithmetic, transcribed from source
    weight             contribution to parent: fraction, max points, or blank
    used_by            every downstream consumer that reads this field as an
                       INPUT — QS lens/recipe, the Longlist/Elder-list gate,
                       a DETECT-layer lens, an alert trigger, the sector
                       entry gate. Blank means: computed and exported, no
                       confirmed reader elsewhere in the codebase — worth
                       knowing, not necessarily worth removing.
    ships_in_export    WHERE this value actually lands in
                       aqe_daily_export.json — "daily_list" (every scored
                       ticker), "held_positions only", "subcomponents.<eng>"
                       (nested, only when subcomponents is populated, and
                       sometimes under a RENAMED key — stated explicitly when
                       it differs from `field`), "srm[]"/"thematic_baskets[]"/
                       "qs{}"/"lens_ranking" (their own blocks), or
                       "NOT EXPORTED — reference/calculation figure only" for
                       an internal intermediate an engine computes and
                       discards on the way to a score that IS exported.
                       Computed from the real registries (_FIELD_SCHEMA,
                       _SUBCOMPONENT_SPEC, the held-only glossary markers),
                       not hand-typed, so it can't drift from what the code
                       actually does.

Two inputs:
  1. SCORE_TREE below — parent/child math transcribed from src/engines/*.py
     with the divisor and every component maximum. Verified to sum: Flow 38,
     Energy 59.5, Structure 95, MP 100, BQ 100, Elder 10.
  2. The export's own field_schema / field_glossary / enum sets, read from
     code at generation time, for whatever the tree does not cover — used
     ONLY to discover field names and enum values that exist; the source and
     formula for every one of those fields is still traced back to the real
     calculator by hand, never left pointing at the glossary text itself.

A malformed-key guard: the export's own `_FIELD_GLOSSARY` dict carries three
keys that join several real field names with a slash
("fib_236/382/500/618/786", "ma_20/50/100/200", "fib_swing_low/high") — one
glossary entry documenting five fields at once. Naively iterating that dict's
keys turns each into a fake taxonomy row. MALFORMED_GLOSSARY_KEYS below names
them explicitly so they are dropped, not emitted as three garbage fields
whose real name is a felony against CSV.

Run:  python -m scripts.build_data_taxonomy
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "AQE_DATA_TAXONOMY.csv"

COLUMNS = ["field", "parent", "level", "output", "state", "represents",
           "source", "formula", "weight", "used_by", "ships_in_export"]

# Keys in the export's own field_glossary that document several real fields
# under one slash-joined pseudo-name. Not field names — dropped outright.
MALFORMED_GLOSSARY_KEYS = {
    "fib_236/382/500/618/786", "ma_20/50/100/200", "fib_swing_low/high",
}


def R(field, parent, level, output, state, represents, source, formula,
     weight="", used_by="", ships_in_export=""):
    return dict(zip(COLUMNS, [field, parent, level, output, state, represents,
                              source, formula, weight, used_by,
                              ships_in_export]))


# ── composites ───────────────────────────────────────────────────────────
SCORE_TREE = [
    R("sc_momentum", "", "composite", "0-100", "",
      "Momentum pipeline composite, 1-3 week hold; no engine floor is "
      "applied to it, floors gate separately via sc_m_gates",
      "engines/scoring.py:_sc_momentum_raw",
      "clip(0.30*flow + 0.30*energy + 0.20*structure + 0.20*mp, 0, 100)"),
    R("sc_momentum_raw", "sc_momentum", "composite", "0-100", "",
      "The same weighted average, read before sc_m_gates is applied",
      "engines/scoring.py:_sc_momentum_raw", "sc_momentum_raw = sc_momentum"),
    R("sc_m_gates", "sc_momentum", "leaf", "bool", "true|false",
      "All momentum gate floors cleared", "engines/scoring.py:_sc_m_gates",
      "flow>=60 AND energy>=60 AND structure>=55 AND mp>=55 "
      "AND elder>=6.5"),
    R("sc_position", "", "composite", "0-100", "",
      "Base-building composite, 3-6 week hold. CONFIRMED NEVER EXPORTED: "
      "computed into scores_daily, absent from all 162 records of a live "
      "daily_list — not null-stripped, genuinely never wired into the "
      "export. Unlike an intermediate such as fl_fb, this is a full, real "
      "composite that simply never reaches the JSON.",
      "engines/scoring.py:_sc_position_raw",
      "clip(0.10*flow + 0.30*energy + 0.20*structure + 0.05*mp + 0.35*bq, "
      "0, 100)"),
    R("sc_p_gates", "sc_position", "leaf", "bool", "true|false",
      "All position gate floors cleared", "engines/scoring.py:SC_P_GATES",
      "flow>=40 AND energy>=60 AND structure>=65 AND mp>=40 AND bq>=60 "
      "AND k39_gate"),

    # ── Flow ─────────────────────────────────────────────────────────────
    R("flow", "sc_momentum", "engine", "0-100", "",
      "Money flow: institutional accumulation vs distribution", "engines/flow.py:193-194",
      "clip(flow_score+accum_score+volume_score+skew_score+ext_score, 0, 38) "
      "/ 38 * 100", "0.30 of sc_momentum; 0.10 of sc_position"),
    R("flow_score", "flow", "component", "0-17", "",
      "MFI/CMF joint band, plus Heikin-Ashi consecutive-quality count",
      "engines/flow.py:69-110", "clip(fl_fb + ha_b, upper=17)", "17 of 38"),
    R("fl_fb", "flow_score", "leaf", "0-11", "",
      "MFI/CMF joint threshold band", "engines/flow.py:69-73",
      "(mfi>38 OR cmf>-0.05)->2.5; (mfi>42 AND cmf>0)->5.0; "
      "(mfi>48 AND cmf>0.02)->8.0; (mfi>55 AND cmf>0.05)->11.0", "11 of 17"),
    R("hac", "ha_b", "leaf", "int 0-10", "",
      "Count of the trailing 10 bars whose Heikin-Ashi body sits inside "
      "0.5x ATR20 of the prior bar's open/close midpoint", "engines/flow.py:78-99",
      "hc=(O+H+L+C)/4; ho[t]=(O+C)/2, ho[t-i]=(O[t-i-1]+C[t-i-1])/2 for "
      "i=1..9; count over i=0..9 of |hc[t-i]-ho[t-i]| < 0.5*ATR20[t]"),
    R("ha_b", "flow_score", "leaf", "0|2|4|6", "",
      "Step score on hac", "engines/flow.py:105-107",
      "hac>=2->2.0, hac>=3->4.0, hac>=5->6.0", "6 of 17"),
    R("accum_score", "flow", "component", "0-7.5", "",
      "A/D line short vs long linear-regression slope", "engines/flow.py:120-124",
      "ad_short>0->1.5; ad_short>ad_long*0.85->3.0; ad_short>ad_long->5.5; "
      "ad_short>ad_long*1.1->7.5", "7.5 of 38", used_by="QS:FLOW lens"),
    R("ad_short", "accum_score", "leaf", "float", "",
      "10-bar linear-regression endpoint of the 60-bar rolling A/D sum",
      "engines/flow.py:117-121",
      "ad=rollsum(((2*close-low-high)/(high-low))*volume, 60); "
      "linreg_endpoint(ad, 10)"),
    R("ad_long", "accum_score", "leaf", "float", "",
      "20-bar linear-regression endpoint of the same 60-bar rolling A/D sum",
      "engines/flow.py:117-122", "linreg_endpoint(ad, 20)"),
    R("volume_score", "flow", "component", "0-7.5", "",
      "Volume trend plus spike, capped", "engines/flow.py:126-138",
      "clip(vt_b + spk_b, upper=7.5)", "7.5 of 38"),
    R("vtr", "volume_score", "leaf", "ratio", "",
      "5-day average volume over 20-day average volume. The identical "
      "SMA(5)/SMA(20) volume ratio is computed independently in 4 places: "
      "here, bq.py's vd_ratio, pipeline_rank.py's vol_ratio, and "
      "readiness.py's own vd_ratio — same formula, four implementations.",
      "engines/flow.py:126-127", "sma(volume,5) / sma(volume,20)"),
    R("vt_b", "volume_score", "leaf", "0|2|4|5.5", "",
      "Step score on vtr", "engines/flow.py:131-133",
      "vtr>0.9->2.0, vtr>1.05->4.0, vtr>1.2->5.5"),
    R("spk", "volume_score", "leaf", "ratio", "",
      "Current bar's volume over the 20-day average", "engines/flow.py:128",
      "volume / sma(volume,20)"),
    R("spk_b", "volume_score", "leaf", "0|1|2", "",
      "Step score on spk", "engines/flow.py:129-130",
      "spk>1.5->1.0, spk>2.0->2.0"),
    R("skew_score", "flow", "component", "0-3.5", "",
      "Up-volume vs down-volume over 10 bars", "engines/flow.py:148-151",
      "udr>=0.8->1.5, udr>1.2->2.5, udr>1.5->3.5", "3.5 of 38"),
    R("udr", "skew_score", "leaf", "ratio", "",
      "10-bar sum of up-close volume over 10-bar sum of down-close volume",
      "engines/flow.py:141-146",
      "up_vol=volume where close[t]>close[t-1] else 0; dn_vol=volume where "
      "close[t]<=close[t-1] else 0; sum(up_vol,10) / sum(dn_vol,10)"),
    R("ext_score", "flow", "component", "-8 to +5", "",
      "Extension penalty/bonus, evaluated top-down until one condition fires",
      "engines/flow.py:172-189",
      "(is_nh AND vr>1.5 AND cr>0.6)->5.0; (pp>85 AND vr>1.2 AND cr>0.5)"
      "->3.0; (de>12 AND vr>2.0 AND cr<0.4)->-8.0; (de>8 AND NOT isc AND "
      "cr<0.4)->-5.0; pp<25->3.0; else 0.0"),
    R("pp", "ext_score", "leaf", "0-100 pct", "",
      "Close position inside the 20-bar high/low range", "engines/flow.py:156-162",
      "(close-lowest(low,20)) / (highest(high,20)-lowest(low,20)) * 100; "
      "50.0 when the 20-bar range is zero"),
    R("de", "ext_score", "leaf", "pct", "",
      "Close distance from EMA20, as a percent of EMA20",
      "engines/flow.py:163-164", "(close-EMA20) / EMA20 * 100"),

    # ── Energy ───────────────────────────────────────────────────────────
    R("energy", "sc_momentum", "engine", "0-100", "",
      "Stored energy: compression, position, exhaustion", "engines/energy.py:192-194",
      "clip((vp_position_score+price_action_score+squeeze_score+"
      "exhaustion_score+atr_score) / 59.5 * 100, 0, 100)",
      "0.30 of sc_momentum; 0.30 of sc_position"),
    R("vp_position_score", "energy", "component", "0-17.5", "",
      "Range-position proxy for volume-profile location. The true VP array "
      "(POC/VAH/VAL) is diagnostic only in Pine and is not computed here.",
      "engines/energy.py:39-61", "clip(en_psc + en_lvn_proxy, upper=17.5)",
      "17.5 of 59.5"),
    R("en_pos50", "vp_position_score", "leaf", "0-100 pct", "",
      "Close position inside the 50-bar high/low range. IDENTICAL formula to "
      "ms_pos_score (structure.py:181-186) — same window, same zero-range "
      "fallback, independently implemented in two engines.",
      "engines/energy.py:39-46",
      "(close - lowest(low,50)) / (highest(high,50) - lowest(low,50)) * 100; "
      "50.0 when the 50-bar range is zero", used_by="QS:STRUCTURE lens"),
    R("en_psc", "vp_position_score", "leaf", "3-17", "",
      "Step score on en_pos50; the 90+ tier scores below the 75-90 tier "
      "on purpose — Pine's own extension penalty", "engines/energy.py:48-54",
      "en_pos50<30->3.0, en_pos50>=30->5.0, >=45->8.0, >=60->12.0, "
      ">=75->17.0, >=90->15.0"),
    R("en_lvn_proxy", "vp_position_score", "leaf", "0|1.5", "",
      "Low-volume-node proxy: tight 5-bar range high in the 50-bar range",
      "engines/energy.py:56-60",
      "(en_pos50>75 AND (highest(high,5)-lowest(low,5))<2*ATR20)->1.5; else 0"),
    R("price_action_score", "energy", "component", "0-12.5", "",
      "Higher lows, range tightness, pullback depth, discounted low in range",
      "engines/energy.py:69-100",
      "pa_raw = structure_score + tightness_score + pullback_score; "
      "pa_raw*0.7 if en_pos50<45; pa_raw*0.5 if en_pos50<30; else pa_raw",
      "12.5 of 59.5"),
    R("hl_count", "price_action_score", "leaf", "0-4", "",
      "Count of the last 4 bars making a higher low", "engines/energy.py:64-67",
      "sum over i=0..3 of (low[t-i] > low[t-i-1])"),
    R("structure_score", "price_action_score", "leaf", "0-5", "",
      "Step score on hl_count", "engines/energy.py:68-72",
      "hl_count>=1->1.5, >=2->3.0, >=3->4.0, >=4->5.0", "5 of 12.5"),
    R("compression_ratio", "price_action_score", "leaf", "ratio", "",
      "5-bar range as a fraction of the 20-bar range", "engines/energy.py:74-76",
      "(highest(high,5)-lowest(low,5)) / (highest(high,20)-lowest(low,20))"),
    R("tightness_score", "price_action_score", "leaf", "0-4.5", "",
      "Step score on compression_ratio, boosted while trending",
      "engines/energy.py:77-86",
      "base: ratio<0.9->1.0, <0.7->2.0, <0.5->3.5, <0.3->4.5; "
      "clip(base+1.5, upper=4.5) if close>EMA20 AND close>close[5]", "4.5 of 12.5"),
    R("pullback_pct", "price_action_score", "leaf", "0-100 pct", "",
      "Pullback from the 20-bar high", "engines/energy.py:88-89",
      "(highest(high,20) - close) / highest(high,20) * 100"),
    R("pullback_score", "price_action_score", "leaf", "0-3", "",
      "Step score on pullback_pct", "engines/energy.py:90-93",
      "pullback_pct<25->1.0, <15->2.0, <10->2.5, <5->3.0", "3 of 12.5"),
    R("squeeze_score", "energy", "component", "0-12.5", "",
      "Bollinger/Keltner squeeze state and bandwidth percentile. Same bb/kc "
      "construction as readiness.py's own compression sub-score — a "
      "duplicate, different downstream bands.",
      "engines/energy.py:113-124",
      "sq=false: bwp<50->4.0, bwp<30->8.5; sq=true: 5.0, bwp<50->7.5, "
      "bwp<35->10.0, bwp<20->12.5", "12.5 of 59.5", used_by="QS:COIL lens"),
    R("bwp", "squeeze_score", "leaf", "0-100 pct", "",
      "Bollinger bandwidth's own 50-bar percentile", "engines/energy.py:104-111",
      "bw=(BB_upper-BB_lower)/BB_mid*100, BB=SMA20 +/- 2*stdev_pop(close,20); "
      "bwp=(bw-lowest(bw,50)) / (highest(bw,50)-lowest(bw,50)) * 100"),
    R("sq", "squeeze_score", "leaf", "bool", "true|false",
      "Bollinger Bands sitting inside Keltner Channels", "engines/energy.py:112",
      "BB_lower>KC_lower AND BB_upper<KC_upper, KC=SMA20 +/- 1.5*ATR20"),
    R("exhaustion_score", "energy", "component", "0-10", "",
      "Penalty for climactic, divergent or wide-spread bars, applied only "
      "once the trend is mature", "engines/energy.py:126-167",
      "en_trend_bars>=15: clip(10 + climactic_penalty + divergence_penalty "
      "+ wide_spread_penalty, lower=0); en_trend_bars<15: 10.0", "10 of 59.5"),
    R("en_trend_bars", "exhaustion_score", "leaf", "int >=0", "",
      "Consecutive bars closing above EMA20", "engines/energy.py:129-134",
      "en_trend_bars[t] = en_trend_bars[t-1]+1 if close[t]>EMA20[t] else 0"),
    R("climactic_penalty", "exhaustion_score", "leaf", "-4|-2.5|0", "",
      "Penalty for a high-volume bar with a weak price gain; later clauses "
      "override earlier ones where both match", "engines/energy.py:138-141",
      "(vol_ratio>2.5 AND gain_pct<3)->-2.5; (vol_ratio>3.0 AND gain_pct<2)"
      "->-4.0 [overrides]; else 0; vol_ratio=volume/SMA20vol, "
      "gain_pct=(close/close[1]-1)*100"),
    R("divergence_penalty", "exhaustion_score", "leaf", "-3|-2|0", "",
      "Penalty for a new price high with MFI or MACD not confirming; later "
      "clauses override earlier ones where both match",
      "engines/energy.py:143-151",
      "(price_new_high AND MACD_line<max(MACD_line[1..5]))->-2.0; "
      "(price_new_high AND MFI14<max(MFI14[1..5]))->-3.0 [overrides]; else 0; "
      "price_new_high = high==highest(high,10)"),
    R("wide_spread_penalty", "exhaustion_score", "leaf", "-3|-1.5|0", "",
      "Penalty for an abnormally wide bar on high volume with no follow-through",
      "engines/energy.py:153-161",
      "(bar_range_ratio>2.0 AND vol_ratio>2.0 AND NOT follow_through)"
      "->-3.0; (bar_range_ratio>1.5 AND vol_ratio>1.5)->-1.5; else 0; "
      "bar_range_ratio=(high-low)/ATR20, follow_through=close[1]<close AND high[1]<high"),
    R("atr_score", "energy", "component", "0-7", "",
      "ATR expansion inside the productive band; the resolved bands below "
      "(not the code's override order) are the ones that actually apply",
      "engines/energy.py:182-189",
      "pct<-10->0.0; -10<=pct<0->0.5; 0<=pct<10->1.0; 10<=pct<15->4.0; "
      "15<=pct<20->5.5; 20<=pct<=80->7.0; 80<pct<=150->4.0; pct>150->2.0",
      "7 of 59.5"),
    R("atr_expansion_pct", "atr_score", "leaf", "pct", "",
      "5-bar ATR average vs 20-bar ATR average, percent change",
      "engines/energy.py:170-172",
      "(SMA(ATR20,5) - SMA(ATR20,20)) / SMA(ATR20,20) * 100"),

    # ── Structure ────────────────────────────────────────────────────────
    R("structure", "sc_momentum", "engine", "0-100", "",
      "Relative strength, base quality, overhead supply", "engines/structure.py",
      "clip((rs_spy+rs_accel+base+ms_pos+resist+wk+earn) / 95 * 100, 0, 100)",
      "0.20 of sc_momentum; 0.20 of sc_position"),
    R("rs_spy_score", "structure", "component", "0-15", "",
      "Relative performance vs SPY", "engines/structure.py:40-50",
      "rs_vs_spy: >-3->3, >0->6, >2->10, >5->12, >10->15", "15 of 95"),
    R("rs_vs_spy", "rs_spy_score", "leaf", "pct", "",
      "60-day return, stock minus SPY", "engines/structure.py:40-43",
      "(close/close[60]-1)*100 - (spy_close/spy_close[60]-1)*100",
      used_by="QS:LEADERSHIP lens"),
    R("rs_accel_score", "structure", "component", "0-15", "",
      "Change in relative strength", "engines/structure.py:52-61",
      "rs_accel: >-5->3, >-2->6, >0->9, >2->12, >5->15", "15 of 95"),
    R("rs_accel", "rs_accel_score", "leaf", "pct", "",
      "20-day relative strength minus the 60-day relative strength",
      "engines/structure.py:52-54",
      "((close/close[20]-1)-(spy/spy[20]-1))*100 - rs_vs_spy"),
    R("base_score", "structure", "component", "0-15", "",
      "Base duration and quality, with post-breakout decay",
      "engines/structure.py:64-178",
      "clip(base_raw * base_quality_mult, upper=15)", "15 of 95"),
    R("base_days", "base_score", "leaf", "int >=0", "",
      "Bars in a qualifying base, latched through breakout, decaying after",
      "engines/structure.py:66-131",
      "raw count of consecutive in_base bars (VCP OR staircase OR smooth "
      "mode); on breakout the count LATCHES, holds 10 bars, then reverts"),
    R("in_base", "base_days", "leaf", "bool", "true|false",
      "Whether the bar qualifies as inside a base, by any of 3 modes",
      "engines/structure.py:66-83",
      "mode1 VCP: 10-bar range<=15% of close; mode2 staircase: above rising "
      "SMA50, 1.5-8% pullback, >=2 of last 5 lows higher; mode3 smooth: "
      "EMA20 rising, close within 1*ATR20 of EMA20, close>SMA50"),
    R("base_raw", "base_score", "leaf", "0-15", "",
      "Step score on base_days", "engines/structure.py:133-141",
      "base_days <3->0, <5->3, 5-6->6, 7-9->10, 10-25->15, 26-30->12, "
      "31-35->8, >35->5"),
    R("hl_in_base", "base_score", "leaf", "0-10", "",
      "Higher lows counted inside the base lookback window",
      "engines/structure.py:145-158",
      "count over i=1..min(base_days,10) of (low[t-i] > low[t-i-1])"),
    R("base_quality_mult", "base_score", "leaf", "0.6|0.8|1.0", "",
      "Multiplier on base_raw from hl_in_base", "engines/structure.py:159-161",
      "hl_in_base <2 ->0.6, >=2 ->0.8, >=4 ->1.0"),
    R("ms_pos_score", "structure", "component", "0-15", "",
      "Position in the 50-bar range. The engine's own DataFrame column is "
      "named ms_pos_score (structure.py:235), not the shorter 'ms_pos' this "
      "field was previously mislabelled as here.",
      "engines/structure.py:163-192",
      "ms_p50: >=45->4, >=60->7, >=75->10, >=85->13, >=95->15", "15 of 95",
      used_by="QS:STRUCTURE lens; QS recipes"),
    R("ms_p50", "ms_pos_score", "leaf", "0-100 pct", "",
      "Close position inside the 50-bar high/low range. IDENTICAL formula "
      "to en_pos50 (energy.py:39-46) — independently implemented.",
      "engines/structure.py:163-168",
      "(close-lowest(low,50)) / (highest(high,50)-lowest(low,50)) * 100; "
      "50.0 when the 50-bar range is zero"),
    R("resist_score", "structure", "component", "0-10", "",
      "Clear air overhead; high means little resistance",
      "engines/structure.py:194-200",
      "dist_to_resist: <=15->3, <=8->5, <=3->10, <=0->7", "10 of 95"),
    R("dist_to_resist", "resist_score", "leaf", "pct", "",
      "Distance from close to the 50-bar high", "engines/structure.py:194",
      "(highest(high,50) - close) / close * 100"),
    R("wk_score", "structure", "component", "0-15", "",
      "Weekly close vs weekly SMA10; 7.5 when no weekly data is available",
      "engines/structure.py:202-212",
      "no weekly data: 7.5; else: wk_close>wk_sma10*0.93->2.0, "
      "wk_close>wk_sma10*0.97->5.0, wk_close>wk_sma10->10.0, "
      "(wk_close>wk_sma10 AND wk_rising)->15.0; wk_rising=wk_sma10>wk_sma10[1]",
      "15 of 95"),
    R("earn_score", "structure", "component", "0-10", "",
      "Distance to the next earnings date", "src/data/earnings.py:earn_proximity_score:116-126",
      "days<=5->0.0, days<=10->4.0, days<=20->7.0, days>20 or unknown->10.0",
      "10 of 95"),

    # ── MP ───────────────────────────────────────────────────────────────
    R("mp", "sc_momentum", "engine", "0-100", "",
      "Momentum persistence: will the move keep going", "engines/mp.py",
      "clip(abs_mom + adx + rel_mom + trend, 0, 100)",
      "0.20 of sc_momentum; 0.05 of sc_position"),
    R("abs_mom_score", "mp", "component", "0-30", "",
      "20-day ROC z-score against its own 50-day distribution",
      "engines/mp.py:42-49",
      "roc_zscore>=2.0->30, >=1.5->26, >=1.0->22, >=0.5->16, >=0.0->10, "
      ">=-0.5->5, else 0", "30 of 100", used_by="QS:MOMENTUM lens (inverted)"),
    R("roc_zscore", "abs_mom_score", "leaf", "z-score", "",
      "20-day rate of change, standardised against its own 50-day mean/stdev",
      "engines/mp.py:42-45",
      "roc20=(close/close[20]-1)*100; roc_zscore=(roc20-sma(roc20,50))/"
      "stdev_pop(roc20,50)", used_by="QS:MOMENTUM lens (inverted)"),
    R("adx_score", "mp", "component", "0-25", "",
      "Trend strength, gated on DI direction", "engines/mp.py:57-62",
      "(adx_val>=20 AND di_bullish)->12; (adx_val>=25 AND di_bullish)->18; "
      "(adx_val>=30 AND di_bullish)->22; (adx_val>=40 AND di_bullish)->25; "
      "else 0", "25 of 100"),
    R("adx_val", "adx_score", "leaf", "0-100", "",
      "14-period Average Directional Index, Wilder RMA of DX. Same formula "
      "as pipeline_rank.py's own DMI/ADX (pr_adx_score's input) — different "
      "code, mathematically equivalent, a genuine duplicate.",
      "engines/mp.py:139-155",
      "plus_di=100*wilder_rma(plus_dm,14)/wilder_rma(TR,14); minus_di "
      "likewise on minus_dm; dx=100*|plus_di-minus_di|/(plus_di+minus_di); "
      "adx_val=wilder_rma(dx,14)"),
    R("di_bullish", "adx_score", "leaf", "bool", "true|false",
      "+DI above -DI — directional gate on the ADX score",
      "engines/mp.py:58", "plus_di > minus_di"),
    R("rel_mom_score", "mp", "component", "0-25", "",
      "20-day excess return vs SPY", "engines/mp.py:65-72",
      "excess_return>=15->25, >=10->22, >=5->18, >=2->13, >=0->8, "
      ">=-3->3, else 0", "25 of 100", used_by="QS:MOMENTUM lens (inverted)"),
    R("excess_return", "rel_mom_score", "leaf", "pct", "",
      "20-day return, stock minus SPY", "engines/mp.py:65-68",
      "(close/close[20]-1)*100 - (spy_close/spy_close[20]-1)*100"),
    R("trend_score", "mp", "component", "0-20", "",
      "Moving-average stacking; the five clauses are mutually exclusive by "
      "construction. above20=close>EMA20, above50=close>SMA50, "
      "ma20_rising=EMA20>EMA20[3], ma50_rising=SMA50>SMA50[5]",
      "engines/mp.py:74-94",
      "(above20 AND NOT above50)->5; (above50 AND NOT ma50_rising)->8; "
      "(above50 AND ma50_rising AND NOT above20)->12; (above20 AND above50 "
      "AND ma50_rising AND NOT ma20_rising)->16; (above20 AND above50 AND "
      "ma20_rising AND ma50_rising)->20; else 0", "20 of 100"),
    R("mp_state", "mp", "leaf", "label", "BUILDING|STRONG|FADING",
      "Phase label for the momentum reading", "engines/mp.py:104-107",
      "default FADING; (mp_rising AND mp<75)->BUILDING; (mp_rising AND "
      "mp>=75)->STRONG; mp_rising = mp_score>mp_score[3]"),
    R("mp_accel", "mp", "leaf", "float", "",
      "Additive momentum acceleration, outside the Pine spec", "engines/mp.py:113",
      "sma(roc_zscore.diff(5), 3)"),
    R("mp_accel_state", "mp_accel", "leaf", "label",
      "ACCELERATING|FLAT|DECELERATING", "Step score on mp_accel",
      "engines/mp.py:115-117",
      "default FLAT; mp_accel>0.10->ACCELERATING; mp_accel<-0.10->DECELERATING"),

    # ── Elder ────────────────────────────────────────────────────────────
    R("elder", "", "engine", "0-10", "",
      "Elder Impulse: trend and momentum agreeing", "engines/elder.py",
      "state_score + slope_score + hist_score"),
    R("elder_state_score", "elder", "component", "0|2|4", "",
      "Impulse colour", "engines/elder.py:55-59",
      "impulse_green->4.0, impulse_blue->2.0, impulse_red->0.0", "4 of 10"),
    R("impulse_state", "elder_state_score", "leaf", "label",
      "GREEN|RED|NEUTRAL(=BLUE)",
      "Combined EMA13 direction and MACD-histogram direction",
      "engines/elder.py:42-52",
      "green = EMA13 rising AND histogram rising; "
      "red = EMA13 falling AND histogram falling; blue = neither"),
    R("elder_slope_score", "elder", "component", "0-3", "",
      "3-bar EMA13 slope percent, banded", "engines/elder.py:61-69",
      "ema_slope>0->1.0, >0.3->2.0, >1.0->3.0", "3 of 10"),
    R("ema_slope", "elder_slope_score", "leaf", "pct", "",
      "EMA13 change over 3 bars, as a percent of its current value",
      "engines/elder.py:61-62", "(EMA13 - EMA13[3]) / EMA13 * 100"),
    R("elder_hist_score", "elder", "component", "0-3", "",
      "MACD(12,26,9) histogram trend, banded", "engines/elder.py:72-77",
      "hist>0 AND not accelerating->2.0; hist<=0 AND accelerating->1.0; "
      "hist>0 AND accelerating->3.0; else 0.0", "3 of 10"),
    R("hist_accel", "elder_hist_score", "leaf", "float", "",
      "Bar-over-bar change in the MACD histogram", "engines/elder.py:71",
      "hist - hist[1]"),
    R("elder_pattern", "elder", "leaf", "label",
      "SUSTAINED|CORRECTION_REENTRY|ACCELERATION|ACCUMULATION_BASE|"
      "INTERRUPTED|null",
      "Rule match over the last 5 rounded elder scores (v[0..4]=T-4..T-0), "
      "checked in this order — first match wins", "engines/elder_context.py:19-47",
      "(count(v>=9)>=4 AND min(v)>=8)->SUSTAINED; (interior v[i]<=7 after an "
      "earlier v>=9, with v[-1]>=9)->CORRECTION_REENTRY; (v[0]<=6 or v[1]<=6, "
      "AND v[-1]>=9 AND v[-2]>=9 AND v[-1]>=v[0])->ACCELERATION; "
      "(max(v)<=8 AND min(v)<=6 AND v non-decreasing)->ACCUMULATION_BASE; "
      "(any v[i]<=5 for i>=1)->INTERRUPTED; else null"),

    # ── BQ / K39 ─────────────────────────────────────────────────────────
    R("bq", "sc_position", "engine", "0-100", "",
      "Base quality for sc_position, which never reaches the export (see "
      "that row) — so bq doesn't either, despite being fully computed",
      "engines/bq.py:139",
      "clip(bq_range_tight + bq_vol_dry + bq_base_dur + bq_ema_conv, 0, 100)",
      "0.35 of sc_position"),
    R("bq_range_tight", "bq", "component", "0-30", "",
      "Range tightness. rt_ratio (ATR5/ATR20) is computed identically in "
      "readiness.py's own rd_compression sub-score — a duplicate, "
      "different downstream bands.", "engines/bq.py:32-39",
      "rt_ratio<1.0->4, <0.9->8, <0.8->14, <0.7->20, <0.6->25, <0.5->30",
      "30 of 100", used_by="QS:COIL lens"),
    R("rt_ratio", "bq_range_tight", "leaf", "ratio", "",
      "5-bar ATR over 20-bar ATR", "engines/bq.py:35", "ATR(5) / ATR(20)"),
    R("bq_vol_dry", "bq", "component", "0-25", "",
      "Volume dry-up", "engines/bq.py:42-49",
      "vd_ratio<1.1->5, <0.95->10, <0.8->15, <0.65->20, <0.5->25",
      "25 of 100"),
    R("vd_ratio", "bq_vol_dry", "leaf", "ratio", "",
      "5-day average volume over 20-day average volume", "engines/bq.py:43-45",
      "SMA(volume,5) / SMA(volume,20)"),
    R("bq_base_dur", "bq", "component", "0-20", "",
      "Base duration, step score on bq_base_days", "engines/bq.py:118-124",
      "(3<=days<=4)->4.0, (5<=days<=6)->8.0, (7<=days<=9)->14.0, "
      "(10<=days<=25)->20.0, (25<=days<=35)->14.0, days>35->8.0, else 0",
      "20 of 100"),
    R("bq_base_days", "bq_base_dur", "leaf", "int >=0", "",
      "Bars in a qualifying base — BQ's own instance of the mechanism "
      "structure.base_days also uses, with a 60-bar pivot and an 8% band, "
      "not shared state with it", "engines/bq.py:60-116",
      "in_band_basic=(highest(high,60)-close)<=0.08*highest(high,60); "
      "in_base=in_band_basic OR mode2_staircase OR mode3_smooth (both gated "
      "by in_band_basic); raw count of consecutive in_base bars, LATCHED on "
      "breakout (close>rolling consolidation high AND vol>SMA20vol AND "
      "raw>=3) for 10 bars, then reverts to the live raw count"),
    R("bq_ema_conv", "bq", "component", "0-25", "",
      "EMA(8/13/21) convergence. Same formula as readiness.py's own "
      "rd_compression sub-score — a duplicate, different downstream bands.",
      "engines/bq.py:128-136",
      "norm_spread<2.5->5, <1.8->10, <1.2->15, <0.8->20, <0.5->25",
      "25 of 100", used_by="QS:COIL lens"),
    R("norm_spread", "bq_ema_conv", "leaf", "ratio", "",
      "Spread of EMA8/13/21 normalised by ATR20", "engines/bq.py:128-131",
      "(max(EMA8,EMA13,EMA21) - min(EMA8,EMA13,EMA21)) / ATR(20)"),
    R("k39_gate", "sc_position", "leaf", "bool", "true|false",
      "Weekly stochastic and OBV confirmation. Never reaches the export, "
      "same as sc_position/bq — see sc_position's row.", "engines/k39.py",
      "stoch(weekly,39)>50 AND obv_weekly>sma(obv_weekly,30); "
      "mapped to daily as-of, no look-ahead"),

    # ── Pipeline Rank ────────────────────────────────────────────────────
    R("pipe_rank", "", "engine", "0-100", "",
      "Pre-screen rank used to order the scoring queue", "engines/pipeline_rank.py:157",
      "clip(momentum_composite*0.70 + fip_quality*0.30, 0, 100)"),
    R("momentum_composite", "pipe_rank", "leaf", "0-100", "",
      "Sum of five 20-point technical sub-scores", "engines/pipeline_rank.py:93-155",
      "clip(ret_12m_score + pr_adx_score + rsi_score + vol_score + ma_score, "
      "0, 100)", "70 pct weight"),
    R("ret_12m_score", "momentum_composite", "leaf", "0-20", "",
      "12-month return skipping the most recent month, banded. The "
      "function's own local variable is named ret_score; the DataFrame "
      "column (and the field this row documents) is ret_12m_score.",
      "engines/pipeline_rank.py:93-99",
      "ret_12m=(close/close[231]-1)*100; >-10->4, >0->8, >10->12, >25->16, "
      ">50->20", "20 of 100"),
    R("pr_adx_score", "momentum_composite", "leaf", "0-20", "",
      "ADX(14) trend strength, gated on DI direction. Same Wilder ADX/DMI "
      "formula as MP's adx_val (mp.py:139-158) — different code, "
      "mathematically equivalent, a genuine duplicate. Corrected 2026-08-13 "
      "from an earlier claim here that they were not the same series.",
      "engines/pipeline_rank.py:254-273",
      "pr_adx_val>15->5; (pr_adx_val>20 AND pr_di_bullish)->10; "
      "(pr_adx_val>25 AND pr_di_bullish)->15; (pr_adx_val>30 AND "
      "pr_di_bullish)->20; pr_di_bullish = pr_di_plus>pr_di_minus, "
      "pr_di_plus=100*wilder_rma(plus_dm,14)/ATR(14)", "20 of 100"),
    R("rsi_score", "momentum_composite", "leaf", "0-20", "",
      "RSI(14) momentum zone, with an overbought penalty",
      "engines/pipeline_rank.py:111-119",
      "rsi>30->5; rsi>40->10; rsi>50->15; (50<=rsi<=70)->20; rsi>80->10",
      "20 of 100"),
    R("vol_score", "momentum_composite", "leaf", "0-20", "",
      "5-day vs 20-day average volume, banded", "engines/pipeline_rank.py:121-127",
      "vol_ratio=sma(volume,5)/sma(volume,20); >0.7->5, >0.9->10, >1.0->15, "
      ">1.2->20", "20 of 100"),
    R("ma_score", "momentum_composite", "leaf", "0-20", "",
      "Moving-average stack, additive not banded", "engines/pipeline_rank.py:129-144",
      "clip(4*[close>EMA20] + 4*[close>EMA50] + 3*[close>EMA150] + "
      "3*[close>EMA200] + 3*[EMA20>EMA50>EMA150>EMA200] + "
      "3*[SMA50>SMA50[5]], upper=20)", "20 of 100"),
    R("fip_quality", "pipe_rank", "leaf", "0-100", "",
      "FIP path-quality score, penalised for spikes", "engines/pipeline_rank.py:161-184",
      "base: fip_raw>0.10->10; (0<fip_raw<=0.10)->30; (-0.05<=fip_raw<=0)"
      "->60; (-0.10<=fip_raw<-0.05)->80; fip_raw<-0.10->100; else 50; "
      "clip(base - spike_penalty, 0, 100)", "30 pct weight"),
    R("fip_raw", "fip_quality", "leaf", "float", "",
      "Fraction of down days minus fraction of up days over 252 sessions, "
      "signed by the 252-session cumulative return's own direction",
      "engines/pipeline_rank.py:164-168",
      "(pct_negative_days - pct_positive_days) * sign(close/close[252]-1)"),
    R("spike_penalty", "fip_quality", "leaf", "0|30", "",
      "Penalty for any 5-day window with a single-day move over 8pct",
      "engines/pipeline_rank.py:180-183",
      "30 if max(|daily_return|, trailing 5d) > 0.08 else 0"),
    R("fip_spike_excluded", "fip_quality", "leaf", "bool", "true|false",
      "Whether the most recent bar sits inside a detected prior price "
      "spike's exclusion window (DSG-20)", "engines/pipeline_rank.py:187-207",
      "true when _detect_prior_spike() finds a qualifying spike overlapping "
      "the last bar"),
    R("fip_window_effective", "fip_quality", "leaf", "int", "",
      "Bars actually used in the 252-session FIP window after spike "
      "exclusion", "engines/pipeline_rank.py:188-207",
      "252 by default; shortened when fip_spike_excluded is true"),
    R("pipe_tier", "pipe_rank", "leaf", "label", "D-SKIP|C-WATCH|B-STRONG|A-TIER",
      "Tier label from pipe_rank. pipe_rank ITSELF ships on every daily_list "
      "row; this tier, and every one of its sub-scores below "
      "(momentum_composite, fip_quality, ret_12m_score...), does not — "
      "confirmed absent from all 162 records of a live export.",
      "engines/pipeline_rank.py:230-234",
      "default D-SKIP; pipe_rank>=45->C-WATCH; >=60->B-STRONG; >=75->A-TIER"),

    # PTRS and the disposition ceiling that briefly replaced it are both
    # retired (2026-08-13). Both were a re-read of SC_MOMENTUM through a
    # threshold table with no consumer. The shortlist's only floor is now a
    # direct comparison: sc_momentum >= 45 (SHORTLIST_MIN_SC in
    # pipeline/daily_orchestrator.py) — not a scored value, so it has no row
    # here; see the taxonomy note in that file.

    # ── DETECT layer state fields ───────────────────────────────────────
    # These carry a categorical label (an enum) rather than a number, but the
    # label is itself computed from thresholds like everything else here —
    # "what state it's in" is not exempt from "how it was calculated".
    R("structure_shift", "", "leaf", "label",
      "BULLISH_BOS|ABOVE_STRUCTURE|BEARISH_CHOCH|RANGE|null",
      "Close vs the most recent CONFIRMED swing pivot", "data/drive_sync.py:1160-1206",
      "ext_pct=(entry/confirmed_pivot_high-1)*100 when entry>confirmed_pivot_high: "
      "ext_pct<=2.0->BULLISH_BOS, ext_pct>2.0->ABOVE_STRUCTURE; "
      "entry<swing_low->BEARISH_CHOCH; else RANGE; null if no swing found"),
    R("structure_shift_ref", "structure_shift", "leaf", "usd", "",
      "The level structure_shift is measured against", "data/drive_sync.py:1198-1206",
      "confirmed_pivot_high for BULLISH_BOS/ABOVE_STRUCTURE; swing_low for "
      "BEARISH_CHOCH; null for RANGE"),
    R("div_state", "", "leaf", "label", "BULLISH|BEARISH|MIXED|NONE",
      "Regular divergence direction at the last two confirmed pivots",
      "engines/divergence.py:132-141",
      "bull_count>0 AND bear_count==0->BULLISH; bear_count>0 AND "
      "bull_count==0->BEARISH; both>0->MIXED; else NONE"),
    R("div_bull_count", "div_state", "leaf", "0-5", "",
      "Oscillators confirming bullish divergence", "engines/divergence.py:107-118",
      "count over 5 oscillators of (osc[p2]>osc[p1]) at the last 2 confirmed "
      "pivot lows p1<p2, gated on price making a lower low and p2 being fresh"),
    R("div_bear_count", "div_state", "leaf", "0-5", "",
      "Oscillators confirming bearish divergence", "engines/divergence.py:119-130",
      "count over 5 oscillators of (osc[p2]<osc[p1]) at the last 2 confirmed "
      "pivot highs p1<p2, gated on price making a higher high and p2 fresh"),
    R("choch_state", "", "leaf", "label", "BULLISH|BEARISH|NONE",
      "Direction of the latest change-of-character event",
      "engines/smart_money_knn.py:293-301",
      "trend<=0 AND close>last_confirmed_swing_high -> trend=1 -> BULLISH; "
      "trend>=0 AND close<last_confirmed_swing_low -> trend=-1 -> BEARISH"),
    R("pin_bar_state", "", "leaf", "label", "BULLISH_PIN|BEARISH_PIN|NONE",
      "Rejection-candle geometry on the last closed bar", "engines/pin_bar.py:46-65",
      "lower_wick>=0.66*range AND body<=0.4*range AND upper_wick<=0.4*range "
      "->BULLISH_PIN; mirrored on upper_wick->BEARISH_PIN; else NONE"),
    R("squeeze_breakout_state", "", "leaf", "label", "BREAKOUT_UP|BREAKOUT_DOWN|NONE",
      "Bollinger-squeeze breakout event on the last closed bar",
      "engines/squeeze_breakout.py:compute_squeeze_breakout",
      "was squeezed (bb inside kc) on the PRIOR bar AND close crosses "
      "bb_upper this bar ->BREAKOUT_UP; crosses bb_lower ->BREAKOUT_DOWN; "
      "else NONE. Shares its squeeze test with squeeze_score "
      "(engines/utils.py:bollinger_keltner_squeeze) rather than recomputing "
      "a second definition."),
    R("vwap_14d_position", "", "leaf", "label", "ABOVE|BELOW",
      "Last close vs the rolling 14-session VWAP",
      "engines/vwap.py:compute_vwap",
      "close>=vwap_14d -> ABOVE; else BELOW"),
    R("mover_subtype", "", "leaf", "label", "explosive|trend|tight_base|squeeze",
      "The z-scored feature family the name resembles most",
      "engines/signal_radar.py:219-229",
      "argmax over 4 families of mean((feature-frozen_mean)/frozen_std) "
      "across each family's feature set"),

    # ── Sector / thematic state fields ──────────────────────────────────
    R("grade", "", "leaf", "label", "DEPLOY|HOLD|TURNING|WATCH|AVOID",
      "Sector ETF grade — the srm[] list's own field name (renamed here "
      "2026-08-13 from a made-up 'gics_grade' to match what actually "
      "ships). Evaluated top-down, first match wins; grade_path says which "
      "of the two roads to DEPLOY or two to TURNING actually fired.",
      "engines/srm.py:280-317",
      "(above_sma20 AND roc20>5.0)->DEPLOY; (above_sma20 AND roc20>=0 AND "
      "roc5>=6.0 AND divergence>=5.0)->DEPLOY; (above_sma20 AND roc20>0)"
      "->HOLD; (above_sma20 AND roc20<=0 AND divergence>=5.0)->TURNING; "
      "(NOT above_sma20 AND divergence>0)->TURNING; (above_sma20 AND "
      "roc20<=0)->WATCH; else AVOID",
      used_by="gics_gate; sector_trend_state; thematic_grade's own ladder "
              "(same function, different index)"),
    R("above_sma20", "grade", "leaf", "bool", "true|false",
      "Latest close above the sector ETF's 20-day SMA", "engines/srm.py:293",
      "close[-1] > sma(close,20)[-1]"),
    R("roc20", "grade", "leaf", "pct", "",
      "20-session rate of change", "engines/srm.py:294",
      "(close[-1]/close[-21]-1)*100"),
    R("roc5", "grade", "leaf", "pct", "",
      "5-session rate of change", "engines/srm.py:295",
      "(close[-1]/close[-6]-1)*100"),
    R("divergence", "grade", "leaf", "pct", "",
      "5d thrust running ahead of (or behind) the 20d pace",
      "engines/srm.py:297", "roc5 - roc20"),
    R("grade_path", "grade", "leaf", "label",
      "trend|acceleration|recovery|below_sma_recovering|stalled|declining|"
      "insufficient_bars",
      "Which of grade's rules actually fired — a grade you cannot account "
      "for is a grade you cannot argue with", "engines/srm.py:302-317",
      "the matched clause's own path label, in the order tested"),
    R("sh_value", "grade", "leaf", "int", "",
      "Sector-Health point value mapped from grade — a historical term; "
      "nothing downstream sizes or gates on it any more, since PTRS (which "
      "used to add this to a ticker's score) was retired 2026-08-13",
      "engines/srm.py:46-52",
      "DEPLOY->3, HOLD->0, TURNING->-3, WATCH->-5, AVOID->-8"),
    R("grade_trend", "grade", "leaf", "list[label]", "",
      "grade re-evaluated on each of the last N sessions, oldest first, no "
      "look-ahead (each entry graded only on bars up to that day)",
      "engines/srm.py:330-343", "[grade_sector_etf(bars[:k]) for k in window]"),
    R("etf", "", "leaf", "label", "",
      "The GICS sector ETF ticker this srm[] row is for", "engines/srm.py",
      "one row per member of GICS_ETFS"),
    R("sector", "", "leaf", "str", "",
      "Human-readable GICS sector name for the row's etf", "engines/srm.py",
      "static ETF->sector-name map"),
    R("gics_gate", "grade", "leaf", "label", "PASS|WATCH|CAUTION|BLOCKED",
      "Sector entry gate combining grade, RRG quadrant and macro flag. "
      "Ships on the srm[] list itself as entry_gate/entry_gate_reason "
      "(same function, same computation) as well as projected onto every "
      "scored ticker in daily_list under this name.",
      "engines/srm.py:966-983",
      "grade==AVOID->BLOCKED; (macro==HEADWIND AND rrg==LAGGING)->BLOCKED; "
      "macro==HEADWIND->CAUTION; (rrg in [LAGGING,WEAKENING] AND "
      "macro==CAUTION)->CAUTION; (grade in [DEPLOY,HOLD] AND rrg in "
      "[LEADING,IMPROVING] AND macro in [TAILWIND,NEUTRAL])->PASS; else WATCH",
      used_by="lens_consensus:sector lens (PASS->strong, "
              "BLOCKED/CAUTION->warn, WATCH/CHECK->ok)"),
    R("entry_gate_reason", "gics_gate", "leaf", "str", "",
      "The reason string sector_entry_gate returned alongside the gate "
      "label — same function as gics_gate, the srm[] list's own copy",
      "engines/srm.py:966-983",
      "the matched clause's own reason string, e.g. 'AVOID grade'"),
    R("sector_trend_state", "grade", "leaf", "label",
      "Momentum Building — Add|Momentum Fading — Hold, Don't Add|"
      "Recovering From Weakness — Watch for Entry|Declining — Avoid",
      "A directive label from (trend direction, momentum slope)",
      "engines/srm.py:234-244",
      "(above_sma20, divergence>0): (T,T)->Momentum Building — Add; "
      "(T,F)->Momentum Fading — Hold, Don't Add; (F,T)->Recovering From "
      "Weakness — Watch for Entry; (F,F)->Declining — Avoid"),
    R("sector_rrg_quadrant", "", "leaf", "label",
      "LEADING|IMPROVING|WEAKENING|LAGGING",
      "Relative-Rotation-Graph quadrant vs SPY", "engines/srm.py:662-669",
      "(rs_ratio>=100 AND rs_momentum>=100)->LEADING; (rs_ratio<100 AND "
      "rs_momentum>=100)->IMPROVING; (rs_ratio>=100 AND rs_momentum<100)"
      "->WEAKENING; else LAGGING"),
    R("rs_ratio", "sector_rrg_quadrant", "leaf", "float ~100", "",
      "Sector/SPY price ratio, normalised to 100 at the start of the window",
      "engines/srm.py:585-591",
      "rs_line=sector_close/spy_close over the trailing 42 bars; "
      "rs_ratio=100*rs_line[-1]/rs_line[0]"),
    R("rs_momentum", "sector_rrg_quadrant", "leaf", "float ~100", "",
      "10-bar rate of change of rs_ratio's own normalised series, offset by 100",
      "engines/srm.py:592-597", "100*(rs_norm[-1]/rs_norm[-11]-1)+100"),
    R("sector_rrg_direction", "sector_rrg_quadrant", "leaf", "label",
      "ENTERING|DEEPENING|STABLE|EXITING",
      "Quadrant-change first, then distance-from-center trend",
      "engines/srm.py:672-684",
      "quadrant changed since yesterday->ENTERING; else "
      "dist=sqrt((rs_ratio-100)^2+(rs_momentum-100)^2): "
      "dist>dist_prev*1.02->DEEPENING; dist<dist_prev*0.98->EXITING; "
      "else STABLE"),
    R("thematic_grade", "grade", "leaf", "label",
      "DEPLOY|HOLD|TURNING|WATCH|AVOID|NO_DATA",
      "Basket grade, demoted from a narrow rally", "engines/srm.py:485-495",
      "index_grade = gics_grade's own ladder applied to the basket's "
      "equal-weight constituent index vs SPY; grade = HOLD[narrow] if "
      "index_grade==DEPLOY AND breadth<0.60 else index_grade"),
    R("breadth_pct", "thematic_grade", "leaf", "0-100 pct", "",
      "Fraction of basket constituents above their OWN 20-day SMA — the "
      "real srm.py key is breadth_pct, not 'basket_breadth' as this row was "
      "named before being checked against the source",
      "engines/srm.py:372-382,516",
      "100 * count(constituent close > constituent's own SMA20) / "
      "n_measurable"),
    R("parent_capped_grade", "thematic_grade", "leaf", "label",
      "DEPLOY|HOLD|TURNING|WATCH|AVOID|NO_DATA",
      "What thematic_grade WOULD read if still clamped at the parent GICS "
      "grade — the old, more conservative rule, published so it survives "
      "even though thematic_grade itself no longer applies it "
      "(retired 2026-08-05)", "engines/srm.py:363-373",
      "thematic_grade if GRADE_ORDER[thematic]>=GRADE_ORDER[parent] else "
      "parent_grade"),
    R("thematic_parent_grade", "thematic_grade", "leaf", "label",
      "DEPLOY|HOLD|TURNING|WATCH|AVOID",
      "The parent GICS sector's own gics_grade, carried for context — no "
      "longer clamps thematic_grade (retired 2026-08-05, see "
      "parent_capped_grade for the old clamped value)",
      "engines/srm.py:418-424", "sector_grades[parent_gics_etf].grade"),
    R("thematic_rrg_quadrant", "thematic_grade", "leaf", "label",
      "LEADING|IMPROVING|WEAKENING|LAGGING",
      "Same RRG quadrant function as sector_rrg_quadrant, on the basket's "
      "own equal-weight index vs SPY", "engines/srm.py:418-420,600",
      "gics_rrg_quadrant(rs_ratio, rs_momentum) computed on the basket index"),
    R("thematic_rrg_direction", "thematic_rrg_quadrant", "leaf", "label",
      "ENTERING|DEEPENING|STABLE|EXITING",
      "Same RRG direction function as sector_rrg_direction, on the basket",
      "engines/srm.py:672-684", "sector_rrg_direction's formula, basket index"),

    # ── Held-position state ──────────────────────────────────────────────
    # Held-only. hl_trend/hl_flow/hl_rs/hl_risk are its own 4-part composite,
    # sub-scored to the same depth as Flow/Energy/etc. would take another full
    # pass — held here at composite level since hl_state is the state field.
    R("hl_score", "", "engine", "0-100", "",
      "Composite trend-integrity read for a held position",
      "engines/health.py:10-18",
      "clip(hl_trend + hl_flow + hl_rs + hl_risk, 0, 100); "
      "hl_trend 0-35, hl_flow 0-25, hl_rs 0-20, hl_risk -20-0"),
    R("hl_state", "hl_score", "leaf", "label", "HOLD_ADD|HOLD|TIGHTEN|EXIT",
      "Held-position action band on hl_score", "engines/health.py:190-193",
      "default EXIT; hl_score>=30->TIGHTEN; >=50->HOLD; >=75->HOLD_ADD"),
    R("rs_leadership", "", "leaf", "label", "LEADER|IN-LINE|LAGGARD",
      "20-day average outperformance vs SPY on SPY's own down days",
      "engines/enrichment.py:48-58",
      "avg_outperf=mean(stock_ret-spy_ret over days where spy_ret<0, 20d); "
      "avg_outperf>0.25->LEADER; avg_outperf<-0.25->LAGGARD; else IN-LINE"),

    # ── membership ───────────────────────────────────────────────────────
    R("on_longlist", "", "leaf", "bool", "true|false",
      "Longlist membership", "src/longlist_screen.py:26-37",
      "sc_momentum_raw >= 65 AND elder >= 7",
      used_by="alert universe (unheld needs >=2 of on_longlist/on_elder/on_qs, "
              "or on_qs alone)"),
    R("on_elder", "", "leaf", "bool", "true|false",
      "Standalone Elder list membership. NOT computed in longlist_screen.py "
      "despite that file's proximity — the real check is inline in "
      "drive_sync.py, corrected 2026-08-13 from an earlier wrong citation "
      "here.", "src/data/drive_sync.py:1964", "elder >= 8",
      used_by="alert universe"),
    R("on_qs", "", "leaf", "bool", "true|false",
      "Quiet Strength emitted a read for this name", "engines/qs_daily.py",
      "qs block present and scored", used_by="alert universe"),

    # ── lens consensus ───────────────────────────────────────────────────
    R("lens_positive", "", "leaf", "0-6", "",
      "Count of lenses reading strong", "engines/lens_consensus.py",
      "unweighted count over leadership, coil, insti_money, structure, "
      "resistance, sector; extension never counts"),
    R("lens_warnings", "", "leaf", "0-6", "",
      "Count of lenses reading warn", "engines/lens_consensus.py",
      "unweighted count, same six lenses"),

    # ── Flow internals QS reads directly ─────────────────────────────────
    R("mfi", "flow_score", "leaf", "0-100", "",
      "Money Flow Index(14) — the standard volume-weighted RSI variant",
      "engines/flow.py:53-56", "standard MFI(14) on typical price and volume",
      used_by="QS:FLOW lens"),
    R("cmf", "flow_score", "leaf", "-1 to 1", "",
      "Chaikin Money Flow(20)", "engines/flow.py:60-66",
      "sum(((close-low)-(high-close))/(high-low)*volume, 20) / sum(volume, 20)",
      used_by="QS:FLOW lens"),

    # ── DETECT-layer auxiliary fields (state already documented above) ──
    R("pin_bar_date", "pin_bar_state", "leaf", "date", "",
      "Date of the last bar's pin-bar read, if any", "engines/pin_bar.py:126",
      "date of the last bar, when pin_bar_state != NONE"),
    R("pin_bar_level", "pin_bar_state", "leaf", "usd", "",
      "The rejection extreme — support for a bullish pin, resistance for a "
      "bearish one", "engines/pin_bar.py:127-129",
      "low[-1] if BULLISH_PIN else high[-1]"),
    R("inside_bar", "", "leaf", "bool", "true|false",
      "Whether the last bar's range sits strictly inside the prior bar's",
      "engines/pin_bar.py:119-121",
      "high[-1] < high[-2] AND low[-1] > low[-2] (strict both sides)"),
    R("pib_pattern", "inside_bar", "leaf", "bool", "true|false",
      "Pin bar immediately followed by an inside bar — rejection, then pause",
      "engines/pin_bar.py:122",
      "prev_bar_was_a_pin_bar AND inside_bar"),
    R("choch_date", "choch_state", "leaf", "date", "",
      "Date of the latest change-of-character event", "engines/smart_money_knn.py:293-301",
      "date of the bar where trend flipped"),
    R("squeeze_breakout_date", "squeeze_breakout_state", "leaf", "date", "",
      "Date of the breakout, if any", "engines/squeeze_breakout.py:compute_squeeze_breakout",
      "date of the last bar, when squeeze_breakout_state != NONE"),
    R("squeeze_breakout_volume_confirmed", "squeeze_breakout_state", "leaf", "bool",
      "true|false",
      "Was volume on the breakout bar above its own 20-bar average",
      "engines/squeeze_breakout.py:compute_squeeze_breakout",
      "squeeze_breakout_state==NONE -> null; else volume[-1] > "
      "sma(volume, 20)[-1]"),
    R("was_squeezed", "", "leaf", "bool", "true|false",
      "Is the last bar itself currently squeezed, independent of a breakout",
      "engines/squeeze_breakout.py:compute_squeeze_breakout",
      "engines/utils.py:bollinger_keltner_squeeze's own squeeze boolean, "
      "read at the last bar"),
    R("vwap_14d", "vwap_14d_position", "leaf", "usd", "",
      "Rolling 14-session volume-weighted average price",
      "engines/vwap.py:compute_vwap",
      "sum(typical_price*volume, 14) / sum(volume, 14), typical_price = "
      "(high+low+close)/3"),
    R("div_date", "div_state", "leaf", "date", "",
      "Anchor date of the divergence — the newer pivot of whichever side "
      "(bull/bear) has more confirming oscillators", "engines/divergence.py:145-152",
      "date at pivot p2 on the majority side; bull side wins ties"),
    R("div_oscs", "div_state", "leaf", "str", "",
      "Which oscillators fired, comma-joined; bearish names prefixed with -",
      "engines/divergence.py:143-144",
      "','.join(bull_names + ['-'+n for n in bear_names])"),
    R("knn_prob", "choch_state", "leaf", "0-1", "",
      "Mean outcome of the k nearest historical same-direction CHoCH events "
      "on this ticker", "engines/smart_money_knn.py:191-202",
      "pool = past, same-direction, resolved CHoCH events within 500 bars; "
      "actual_k=min(5,pool size); knn_prob=mean(outcome of actual_k nearest "
      "by Euclidean distance over [vol_delta,displacement,velocity])",
      used_by="alerts (VETO_HELD, via qs.vetoes) — not directly; see "
              "knn_significant"),
    R("knn_significant", "knn_prob", "leaf", "bool", "true|false",
      "knn_prob clears 0.60/0.40. AIC Charter Amendment v2.8 (2026-07-15): "
      "at k=5 this is a PLAIN THRESHOLD CHECK, not a significance test — "
      "3-of-5 agreeing clears 60% trivially, by chance, on a sample that "
      "small. Never call it 'significant'/'confident' without that caveat.",
      "engines/smart_money_knn.py:108,203",
      "knn_prob >= 0.60 OR knn_prob <= 0.40"),
    R("knn_neighbors_used", "knn_prob", "leaf", "int 0-5", "",
      "How many neighbours actually fed knn_prob — below 5 when the "
      "ticker's own CHoCH history is thin", "engines/smart_money_knn.py:221",
      "min(k=5, pool size)"),
    R("knn_tp1", "knn_prob", "leaf", "usd", "",
      "Statistical projection from the neighbours' favourable-run "
      "distribution — an analog, not a structural level. Read alongside "
      "bracket.targets, never in place of them.", "engines/smart_money_knn.py:212",
      "close + sign*mean(neighbours' favorable_run)*0.5"),
    R("knn_tp2", "knn_prob", "leaf", "usd", "",
      "Same projection at the neighbours' median favourable run",
      "engines/smart_money_knn.py:213", "close + sign*median(favorable_run)"),
    R("knn_tp3", "knn_prob", "leaf", "usd", "",
      "Same projection at the neighbours' 75th-percentile favourable run",
      "engines/smart_money_knn.py:214",
      "close + sign*percentile(favorable_run, 75)"),

    # ── Candles and chart patterns ────────────────────────────────────────
    R("candle_d", "", "leaf", "label",
      "DOJI|HAMMER|SHOOTING_STAR|BULLISH_ENGULFING|BEARISH_ENGULFING|"
      "BULLISH_HARAMI|BEARISH_HARAMI|MORNING_STAR|EVENING_STAR|PIERCING|"
      "DARK_CLOUD|THREE_WHITE_SOLDIERS|THREE_BLACK_CROWS|null",
      "Single/multi-bar candlestick geometry on the last daily bar, checked "
      "in a fixed priority order (3-bar patterns first, down to single-bar "
      "DOJI last)", "engines/candles.py:166",
      "rule-based geometry classifier; each pattern its own body/wick ratio "
      "test against the trailing 1-3 bars"),
    R("candle_d_dir", "candle_d", "leaf", "label", "BULLISH|BEARISH|NEUTRAL",
      "Direction implied by candle_d", "engines/candles.py",
      "fixed per pattern (e.g. HAMMER->BULLISH, DOJI->NEUTRAL)"),
    R("candle_w", "", "leaf", "label", "same enum as candle_d",
      "Same detector, on the current weekly bar", "engines/candles.py:166",
      "detect_candle() on weekly OHLC"),
    R("candle_w_dir", "candle_w", "leaf", "label", "BULLISH|BEARISH|NEUTRAL",
      "Direction implied by candle_w", "engines/candles.py", "fixed per pattern"),
    R("candle_w_date", "candle_w", "leaf", "date", "",
      "Date of the weekly bar candle_w was read from", "engines/candles.py", ""),
    R("pattern", "", "leaf", "label",
      "CUP_HANDLE|DOUBLE_TOP|DOUBLE_BOTTOM|HEAD_SHOULDERS|"
      "INV_HEAD_SHOULDERS|ASCENDING_TRIANGLE|DESCENDING_TRIANGLE|null",
      "Chart-pattern detector over a 126-bar (~6 month) window. pattern_fit "
      "(0-1) measures ONLY how closely the shape matches the textbook "
      "geometry — it is not a probability the pattern resolves.",
      "engines/patterns.py:48,665-674",
      "6 independent detectors, each returning its own pattern name + "
      "fit/stage/trigger on a match; first detector to match wins"),
    R("pattern_fit", "pattern", "leaf", "0-1", "",
      "Geometric match quality for the detected pattern; PATTERN_MIN_FIT="
      "0.50 is the floor a caller should treat as a real match",
      "engines/patterns.py:689", "per-pattern average of its own shape tests"),
    R("pattern_stage", "pattern", "leaf", "label",
      "FORMING|BASE|TRIGGERED", "Where the pattern is in its own lifecycle",
      "engines/patterns.py:143", "per-detector state, set on match"),
    R("pattern_trigger", "pattern", "leaf", "usd", "",
      "The breakout/breakdown price that would confirm the pattern",
      "engines/patterns.py", "per-pattern breakout level"),
    R("pattern_invalidation", "pattern", "leaf", "usd", "",
      "The price that would invalidate the pattern read",
      "engines/patterns.py", "per-pattern invalidation level"),
    R("pattern_direction", "pattern", "leaf", "label", "BULLISH|BEARISH",
      "Direction implied by the detected pattern", "engines/patterns.py",
      "fixed per pattern type"),
    R("pattern_days", "pattern", "leaf", "int", "",
      "Bars the pattern has been forming", "engines/patterns.py", ""),
    R("pattern_start", "pattern", "leaf", "date", "",
      "Date the pattern's formation began", "engines/patterns.py", ""),
    R("pattern_alt", "pattern", "leaf", "label", "same enum as pattern",
      "Every other detector that also matched, comma-joined — not just the "
      "runner-up", "engines/patterns.py:735-750",
      "detectors sorted by pattern_fit desc, after dropping spent shapes "
      "and fits below PATTERN_MIN_FIT(0.50); winner -> pattern, "
      "', '.join(the rest) -> pattern_alt"),
    R("pattern_w", "", "leaf", "label", "same enum as pattern",
      "Same 6-detector sweep on weekly bars", "engines/patterns.py",
      "6 detectors on weekly OHLC"),
    R("pattern_w_dir", "pattern_w", "leaf", "label", "BULLISH|BEARISH",
      "Direction of the weekly pattern", "engines/patterns.py",
      "fixed per pattern type"),
    R("pattern_w_stage", "pattern_w", "leaf", "label", "FORMING|BASE|TRIGGERED",
      "Lifecycle stage of the weekly pattern", "engines/patterns.py",
      "per-detector state, set on match"),
    R("pattern_w_trigger", "pattern_w", "leaf", "usd", "",
      "Weekly breakout/breakdown trigger price", "engines/patterns.py", ""),

    # ── Levels: fib, moving averages, risk/beta/vol ──────────────────────
    R("fib_swing_low", "", "leaf", "usd", "",
      "Low of the auto-detected current up-swing", "src/scanner/levels.py:45-63",
      "find_swing(): lowest pivot low -> the peak, 120-bar search window, "
      "5-bar fractal pivots"),
    R("fib_swing_high", "fib_swing_low", "leaf", "usd", "",
      "High of the same detected swing", "src/scanner/levels.py:45-63",
      "highest high in the window following the swing low"),
    R("fib_236", "fib_swing_low", "leaf", "usd", "",
      "23.6% Fibonacci retracement support", "src/scanner/levels.py:216-225",
      "swing_high - (swing_high-swing_low)*0.236"),
    R("fib_382", "fib_swing_low", "leaf", "usd", "",
      "38.2% Fibonacci retracement support", "src/scanner/levels.py:216-225",
      "swing_high - (swing_high-swing_low)*0.382"),
    R("fib_500", "fib_swing_low", "leaf", "usd", "",
      "50% Fibonacci retracement support", "src/scanner/levels.py:216-225",
      "swing_high - (swing_high-swing_low)*0.5"),
    R("fib_618", "fib_swing_low", "leaf", "usd", "",
      "61.8% Fibonacci retracement support", "src/scanner/levels.py:216-225",
      "swing_high - (swing_high-swing_low)*0.618"),
    R("fib_786", "fib_swing_low", "leaf", "usd", "",
      "78.6% Fibonacci retracement support", "src/scanner/levels.py:216-225",
      "swing_high - (swing_high-swing_low)*0.786"),
    R("ma_20", "", "leaf", "usd", "",
      "20-day simple moving average, absolute price",
      "src/data/drive_sync.py:904-910", "mean(close, trailing 20 bars)"),
    R("ma_50", "ma_20", "leaf", "usd", "", "50-day simple moving average",
      "src/data/drive_sync.py:904-910", "mean(close, trailing 50 bars)"),
    R("ma_100", "ma_20", "leaf", "usd", "", "100-day simple moving average",
      "src/data/drive_sync.py:904-910", "mean(close, trailing 100 bars)"),
    R("ma_200", "ma_20", "leaf", "usd", "", "200-day simple moving average",
      "src/data/drive_sync.py:904-910", "mean(close, trailing 200 bars)"),
    R("sma_distance_pct", "", "leaf", "pct", "",
      "Close distance from the 50-day SMA", "src/data/drive_sync.py:898-901",
      "(close/sma(close,50)-1)*100"),
    R("rs_down_day_20d", "rs_leadership", "leaf", "pct", "",
      "20-day average stock-vs-SPY outperformance, measured only on SPY's "
      "own down days", "engines/enrichment.py:40-51",
      "mean(stock_daily_ret - spy_daily_ret, over the trailing 20 sessions "
      "where spy_daily_ret<0)"),
    R("rs_spy_20d", "", "leaf", "pct", "",
      "Stock's own 20-day ROC minus SPY's 20-day ROC — unconditional, "
      "every day counted (rs_down_day_20d is the down-days-only variant)",
      "src/data/drive_sync.py:912-914",
      "(close/close[20]-1)*100 - (spy_close/spy_close[20]-1)*100"),
    R("beta_30d", "", "leaf", "ratio", "",
      "30-day rolling beta vs SPY — sizes the DSL/bracket ATR clamp for "
      "high-beta names", "src/scanner/betas.py:26-69",
      "cov(stock daily returns, SPY daily returns) / var(SPY daily "
      "returns), trailing 30 sessions"),
    R("beta_252d", "beta_30d", "leaf", "ratio", "",
      "252-day (1-year) beta vs SPY — a separate inline computation from "
      "beta_30d, not the same code path (beta_30d/60d live in "
      "scanner/betas.py; this is computed directly in drive_sync.py). Same "
      "formula, independently implemented — a duplicate worth "
      "consolidating.", "src/data/drive_sync.py:815-839",
      "cov(stock, SPY daily returns)/var(SPY daily returns), trailing 252 "
      "sessions, min 60 required"),
    R("vol_30d_ann", "", "leaf", "pct", "",
      "Annualised realised volatility, 30-session daily log returns",
      "src/data/drive_sync.py:823-827",
      "stdev(diff(log(close)), trailing 30 sessions, ddof=1) * sqrt(252)"),
    R("day_vol", "", "leaf", "ratio", "",
      "Today's volume over its own 20-day prior average (renamed from rvol "
      "2026-08-05 — the only volume-participation field on the row)",
      "src/data/drive_sync.py:840-843",
      "volume[-1] / mean(volume[-21:-1])"),
    R("atr_14d", "", "leaf", "usd", "",
      "14-day Average True Range, absolute price units",
      "src/data/drive_sync.py:1130", "Wilder ATR(14)"),
    R("atr_caution", "", "leaf", "bool", "true|false",
      "Structural stop distance is thin relative to ATR, in an elevated "
      "VIX regime", "engines/enrichment.py:273-278",
      "regime in [YELLOW,ORANGE,RED] AND dsl_atr_ratio<1.5"),
    R("malformed_bracket", "bracket", "leaf", "bool", "true|false",
      "Structural stop sits within 0.5pct of entry — too tight to be a "
      "real bracket", "engines/enrichment.py:268-271",
      "|entry-stop|/entry*100 < 0.5"),
    R("bracket", "", "leaf", "dict", "",
      "The stop/target set — the single source of truth for structural "
      "risk, replacing the retired mechanical DSL/TP fields",
      "engines/bracket_engine.py", "structural stop (tightest valid "
      "support) + nearest-first structural targets, R:R vs structural TP2"),
    R("sc_m_gate_detail", "sc_m_gates", "leaf", "dict[bool]", "",
      "Per-engine pass/fail breakdown behind sc_m_gates",
      "engines/scoring.py:gate_breakdown_momentum",
      "{flow, energy, structure, mp, elder}: each engine's own SC_M_GATES "
      "floor, individually"),
    R("sc_p_gate_detail", "sc_p_gates", "leaf", "dict[bool]", "",
      "Per-engine pass/fail breakdown behind sc_p_gates",
      "engines/scoring.py:gate_breakdown_position",
      "{flow, energy, structure, mp, bq, k39}: each engine's own SC_P_GATES "
      "floor, individually"),

    # ── Elder context, held-position identity ────────────────────────────
    R("elder_5d", "elder", "leaf", "list[float]", "",
      "Trailing 5 sessions of elder, oldest first — the input elder_pattern "
      "classifies", "engines/elder.py", "last 5 elder_score values"),
    R("elder_context", "elder", "leaf", "dict", "",
      "Hourly VWAP/VCP/exhaustion read behind the elder pattern",
      "engines/elder_context.py:91", "computed from intraday hourly bars + "
      "the daily frame; keys computed_date, hourly_bars_used, vwap_5d, "
      "volume, vcp, exhaustion_check"),
    R("floor", "", "leaf", "0-100", "",
      "Weakest of the four core engines — a name is only as strong as its "
      "worst leg. Missing from the export's own _FIELD_GLOSSARY despite "
      "being a real, simple computation — the text was never written, the "
      "code was.",
      "src/data/drive_sync.py:1709,1744,1781",
      "min(flow, energy, structure, mp)"),
    R("entry", "", "leaf", "usd", "",
      "The price everything else on the row is scored against — EOD close "
      "on a daily run", "src/data/drive_sync.py", "the day's close"),
    R("last_pivot_high", "structure_shift", "leaf", "dict", "",
      "The confirmed pivot high structure_shift is measured against, "
      "shipped on the row so a consumer can check the level without "
      "recomputing it", "src/data/drive_sync.py:1180-1188",
      "{price, date} of the nearest confirmed pivot high"),
    R("gics_sector", "", "leaf", "str", "",
      "GICS sector code for the ticker", "src/data/sector_mapper.py",
      "static ticker->sector map"),
    R("gics_sector_name", "gics_sector", "leaf", "str", "",
      "Human-readable name for gics_sector", "src/data/sector_mapper.py",
      "static sector-code->name map"),
    R("held", "", "leaf", "bool", "true|false",
      "Ticker is in the PM's live book", "src/data/drive_sync.py:1113",
      "ticker in the set of tickers on held_positions"),
    R("in_ledger", "held", "leaf", "bool", "true|false",
      "Ticker has an open entry in the signal ledger", "src/data/signal_ledger.py",
      "ticker present in the ledger's open-position table"),
    R("live_px", "held", "leaf", "usd", "",
      "Current mark for a held ticker — the SAME FMP close every other "
      "field on the record is scored against, not a separate live quote",
      "EXTERNAL: FMP quote endpoint, via src/data/fmp_client.py", ""),
    R("held_sl", "held", "leaf", "usd", "",
      "Stop-loss recorded in the PTJ broker journal for this held position",
      "EXTERNAL: PTJ trade journal, read by src/data/ptj.py", ""),
    R("held_tp1", "held", "leaf", "usd", "",
      "First take-profit recorded in the PTJ journal",
      "EXTERNAL: PTJ trade journal, read by src/data/ptj.py", ""),
    R("held_tp2", "held", "leaf", "usd", "",
      "Second take-profit recorded in the PTJ journal",
      "EXTERNAL: PTJ trade journal, read by src/data/ptj.py", ""),
    R("unreal_usd", "held", "leaf", "usd", "",
      "Unrealised P&L. NOT YET WIRED — currently reads a journal field the "
      "2026-07-28 journal restructure renamed; kept as its own row so this "
      "stays visible rather than silently reading zero.",
      "src/data/drive_sync.py", ""),

    # ── Signal Radar conviction labels ───────────────────────────────────
    R("runner_conviction_label", "runner_setup", "leaf", "label",
      "MINIMAL|LOW|MODERATE|HIGH|MAX",
      "Ladder label on runner_conviction (0-4)", "engines/signal_radar.py",
      "0->MINIMAL, 1->LOW, 2->MODERATE, 3->HIGH, 4->MAX"),
    R("premove_conviction_label", "premove_setup", "leaf", "label",
      "MINIMAL|LOW|MODERATE|HIGH|MAX",
      "Ladder label on premove_conviction (0-4)", "engines/signal_radar.py",
      "0->MINIMAL, 1->LOW, 2->MODERATE, 3->HIGH, 4->MAX"),

    # ── QS block — a frozen calibration-table lookup, not a formula ─────
    R("qs", "", "leaf", "dict", "",
      "Quiet Strength read for this name. An absent qs key means QS could "
      "not evaluate the name — not the same as a poor score.",
      "engines/qs_daily.py, qs_engine.py",
      "lenses -> recipes -> vetoes -> calibration -> conviction 0-5 -> "
      "levels -> why; the calibration step is a lookup against a frozen "
      "historical table (data/qs/calibration.json), not a closed-form "
      "formula", used_by="alerts (qs.vetoes gates VETO_HELD)"),
    R("qs.state", "qs", "leaf", "label", "",
      "QS's own regime read at scoring time", "engines/qs_fields.py", ""),
    R("qs.objective", "qs", "leaf", "usd", "",
      "The +-2x ATR14 level the odds were measured against — the yardstick, "
      "not the tradeable bracket. Never merge with bracket.targets.",
      "engines/qs_engine.py", "entry +/- 2*ATR14, signed by direction"),
    R("qs.odds.p", "qs", "leaf", "0-1", "",
      "Calibrated probability of touching qs.objective within 20 sessions, "
      "read from the frozen historical look-alike table — NOT a formula, "
      "a table lookup on (lens_total band, recipe_hits band, regime).",
      "data/qs/calibration.json via engines/qs_engine.py", ""),
    R("qs.odds.extrapolated", "qs.odds.p", "leaf", "bool", "true|false",
      "The bucket this name landed in had too few historical members, so "
      "the probability is extrapolated from neighbouring buckets rather "
      "than read directly", "engines/qs_engine.py",
      "true when the matched (lens_total, recipe_hits, regime) bucket in "
      "calibration.json falls below its own minimum sample size"),
    R("qs.engine.recipe_hits", "qs", "leaf", "int 0-40", "",
      "How many of the 40 frozen recipes this name matches. All 40 are "
      "counted including 8 duplicate pairs — de-duplicating would drop a "
      "probability band.", "data/qs/recipe_book.json via engines/qs_engine.py",
      ""),
    R("qs.engine.qs_persist", "qs", "leaf", "int", "",
      "Prior STORED sessions this name has scored, from aqe.db — not "
      "calendar days", "engines/qs_store.py", ""),
    R("qs.unevaluable_vetoes", "qs", "leaf", "list[str]", "",
      "Which of the 5 frozen vetoes could not be evaluated (missing input), "
      "so a reader knows the veto pass was partial", "engines/qs_engine.py:155-175",
      ""),
    R("qs_market", "", "leaf", "dict", "",
      "The regime terciles QS's own lenses were scored against on this run",
      "engines/qs_fields.py", ""),
    R("qs_status", "", "leaf", "label", "",
      "OK|DEGRADED|UNAVAILABLE — distinguishes a QS outage from a quietly "
      "unremarkable market", "engines/qs_daily.py", ""),

    # ── misc identity / pointers ──────────────────────────────────────────
    R("ticker", "", "leaf", "str", "",
      "The equity symbol — present on every daily_list, held_positions and "
      "srm row; had zero rows anywhere in this taxonomy until now",
      "EXTERNAL: FMP, via the universe screen (src/data/universe.py)", ""),
    R("rank", "", "leaf", "int", "",
      "Position in the sorted daily_list", "src/data/drive_sync.py",
      "row index after the list's own sort"),
    R("source", "", "leaf", "label", "",
      "Which screen surfaced this row (longlist/elder/qs/watchlist/etc.)",
      "src/data/drive_sync.py", ""),
    R("subcomponents", "", "leaf", "dict", "",
      "The engine sub-scores behind each headline read, nested by engine — "
      "context only, never a gate. See _SUBCOMPONENT_SPEC for the exact "
      "per-engine column list.", "src/data/drive_sync.py:1268-1283", ""),
    R("thematic_basket", "thematic_grade", "leaf", "str", "",
      "Which thematic basket(s) this ticker belongs to", "engines/srm.py",
      "static ticker membership in THEMATIC_BASKETS"),
    R("thematic_parent_gics", "thematic_basket", "leaf", "str", "",
      "The GICS sector ETF the basket rolls up to", "engines/srm.py",
      "THEMATIC_BASKETS[name]['parent_gics_etf']"),

    # ── final stragglers ──────────────────────────────────────────────────
    R("atr_quarter_stop", "", "leaf", "usd", "",
      "A volatility stop, offered as a reference beside the structural "
      "bracket — not the bracket itself and not a gate",
      "src/data/drive_sync.py", "entry - 0.25*ATR14"),
    R("atr_quarter_risk_pct", "atr_quarter_stop", "leaf", "pct", "",
      "atr_quarter_stop's distance as a percent of entry",
      "src/data/drive_sync.py", "atr_quarter_stop distance / entry * 100"),
    R("runner_setup", "", "leaf", "bool", "true|false",
      "Job 2 (continuation) — a short young base with a strong 5-day "
      "thrust and clear overhead", "engines/signal_radar.py:51,205-208",
      "base_days<=15 AND ret_5d>14.5 AND resist_score<=8.5"),
    R("runner_conviction", "runner_setup", "leaf", "0-4", "",
      "Count of the 4 runner_setup legs sitting in their favourable "
      "tercile, against frozen cut points", "engines/signal_radar.py:211-216",
      "sum of 4 booleans vs data/signal_engine_params.json cuts"),
    R("premove_setup", "", "leaf", "bool", "true|false",
      "Job 1 (pre-move) — the frozen launcher fingerprint, applied only to "
      "names that are quiet at the scan date", "engines/signal_radar.py",
      "is_quiet (20d return in [-8,8]% AND pos20<0.90) AND every frozen "
      "launcher-fingerprint leg", used_by="lens_consensus:coil lens (True->strong)"),
    R("premove_conviction", "premove_setup", "leaf", "0-4", "",
      "Count of frozen launcher-fingerprint legs satisfied, forced 0 when "
      "not quiet", "engines/signal_radar.py:245-246",
      "sum of legs vs data/signal_engine_params.json cuts; 0 if not is_quiet"),
    R("lens", "", "leaf", "dict", "",
      "The per-lens strong/ok/warn/-- read behind lens_positive/"
      "lens_warnings", "engines/lens_consensus.py",
      "{leadership, coil, insti_money, structure, resistance, extension, "
      "sector}"),
]

for _r in SCORE_TREE:
    _r["source"] = "src/" + _r["source"] if _r["source"] and not _r["source"].startswith("src/") else _r["source"]


# ── export blocks ────────────────────────────────────────────────────────
# Every block's REAL calculator — not build_export, which only assembles
# blocks other functions already computed. Citing the assembler as "source"
# was the same defect as citing the glossary: correct that a value passes
# through that line, wrong that it's computed there. Found and fixed
# 2026-08-13 after being asked directly why every block cited the same file.
BLOCKS = [
    ("date", "str", "Scan date, US close", "src/data/drive_sync.py:build_export"),
    ("exported_at", "iso8601", "Write time, SGT", "src/data/drive_sync.py:build_export"),
    ("market", "str", "Market descriptor", "src/data/drive_sync.py:build_export"),
    ("regime", "dict", "VIX bucket only — the structural input to the bracket "
     "engine's stop-ceiling gate, not a market-regime narrative (Hurst "
     "removed 2026-08-13; src/analyzer/regime.py itself retired the same "
     "day as a redundant wrapper — Crown/Macro Weather/Druckenmiller now "
     "own the regime read)",
     "src/engines/bracket_engine.py:classify_vix_regime"),
    ("intermarket", "dict", "Cross-asset context",
     "engines/srm.py:compute_intermarket,enrich_sectors_intermarket:928-1050"),
    ("srm", "list", "One graded row per GICS sector",
     "engines/srm.py:grade_all_sectors:293-334"),
    ("macro_weather", "dict", "7-instrument direction read",
     "engines/srm.py:compute_macro_weather:789-928"),
    ("regime_stop_pct_ceiling", "float", "Regime cap on stop width, percent",
     "src/engines/bracket_engine.py:regime_stop_ceiling"),
    ("spy_roc_20d", "float", "SPY 20-day rate of change",
     "src/data/drive_sync.py:_compute_enrichment_lookups:813 (build_export "
     "only copies it from that lookup, computed alongside vol_30d_ann/"
     "beta_252d/day_vol)"),
    ("thematic_baskets", "dict", "35 baskets, graded, with RRG position",
     "engines/srm.py:grade_thematic_baskets:408-495"),
    ("sector_map_version", "str", "GICS map version in force",
     "src/data/sector_mapper.py"),
    ("sector_map_gaps", "list", "Unclassified tickers",
     "src/data/sector_mapper.py"),
    ("field_schema", "dict", "Self-described field types",
     "src/data/drive_sync.py:_FIELD_SCHEMA"),
    ("field_schema_enums", "dict", "Permitted values per categorical field",
     "src/data/drive_sync.py:_FIELD_SCHEMA_ENUMS"),
    ("field_glossary", "dict", "Self-described field meanings",
     "src/data/drive_sync.py:_FIELD_GLOSSARY"),
    ("held_positions_status", "enum", "live | cache_fallback | unknown",
     "src/data/ptj.py"),
    ("held_positions", "list", "PM live book from the trade journal",
     "src/data/ptj.py (EXTERNAL: the PTJ broker journal)"),
    ("held_book", "dict", "Beta-adjusted exposure, gap scenarios, sector weights",
     "src/analyzer/held_book.py:build_held_book:30"),
    ("daily_list", "list", "Every scored ticker, full field set",
     "src/data/drive_sync.py:_v21_record_fields (per-row assembly of every "
     "engine's own output — the row itself has no single calculator, each "
     "field does)"),
    ("lens_ranking", "dict", "Same names ordered by lens agreement",
     "engines/lens_consensus.py:build_lens_ranking:121-154"),
    ("summary", "dict", "Run counts", "src/data/drive_sync.py:build_export"),
    ("signal_radar", "dict", "Radar tag totals", "engines/signal_radar.py"),
    ("data_quality", "dict", "Scored records carrying a null core field",
     "src/data/drive_sync.py:_compute_data_quality:2296"),
]


def leaf_rows() -> list[dict]:
    """Everything the score tree does not cover, from the export's own dicts."""
    from src.data import drive_sync as D
    from src.engines import agentic_dictionary as AD

    covered = {r["field"] for r in SCORE_TREE} | {b[0] for b in BLOCKS}
    enums = {**D._FIELD_SCHEMA_ENUMS, **AD.FIELD_ENUMS}
    gloss = {**AD.GLOSSARY_FILL, **D._FIELD_GLOSSARY}
    schema = D._FIELD_SCHEMA

    rows = []
    uncovered = []
    for name in sorted(set(schema) | set(gloss) | set(enums)):
        if name in covered or name.startswith("_"):
            continue
        if name in MALFORMED_GLOSSARY_KEYS:
            continue
        # Retired fields keep a glossary entry so an older export stays
        # readable. They are not part of the current data set.
        if "RETIRED" in str(gloss.get(name, "")):
            continue
        sch = schema.get(name) or {}
        unit = sch.get("unit", "") if isinstance(sch, dict) else ""
        role = sch.get("role", "") if isinstance(sch, dict) else ""
        desc = re.sub(r"\s+", " ", str(gloss.get(name, ""))).strip()
        desc = desc.split(". ")[0][:180]
        if name in ("role", "side", "unit"):
            # These three are not data fields — they're the schema's own
            # controlled vocabulary. They have no glossary text at all
            # (confirmed empty); their real content is the enum list
            # itself, in _FIELD_SCHEMA_ENUMS, not the glossary.
            rows.append(R(name, "", "leaf", "label", "|".join(
                        str(v) for v in D._FIELD_SCHEMA_ENUMS.get(name, [])),
                        f"Schema vocabulary dimension, not a data field — "
                        f"every field.{name} value in field_schema is drawn "
                        f"from this enum",
                        "src/data/drive_sync.py:_FIELD_SCHEMA_ENUMS", "",
                        role))
            continue
        # No real source traced for this one yet — surfaced by
        # test_almost_nothing_still_cites_the_glossary_as_its_source so a
        # newly added export field can't quietly re-open the hole this
        # closed.
        uncovered.append(name)
        rows.append(R(name, _parent_of(name), "leaf", unit or "",
                      "|".join(str(v) for v in enums.get(name, [])),
                      desc, "UNSOURCED src/data/drive_sync.py:_FIELD_GLOSSARY",
                      "", role))
    if uncovered:
        import sys
        print(f"  [taxonomy] {len(uncovered)} field(s) still only sourced to "
              f"the glossary: {uncovered}", file=sys.stderr)
    return rows


PARENTS = [
    (("div_", ), "divergence"), (("knn_", "choch_"), "smart_money_knn"),
    (("pin_bar", "inside_bar", "pib_"), "pin_bar"),
    (("runner_", "premove_", "mover_"), "signal_radar"),
    (("fib_", ), "fibonacci"), (("ma_", ), "moving_averages"),
    (("qs", ), "qs"), (("bracket", ), "bracket_engine"),
    (("pattern", "candle_"), "patterns"),
    (("sector_", "gics_"), "srm"), (("thematic_", ), "srm_thematic"),
    (("hl_", ), "health"), (("lens", ), "lens_consensus"),
    (("fip_", ), "fip"), (("beta_", "vol_", "atr_", "rvol", "rs_"), "market_stats"),
]


def _parent_of(name: str) -> str:
    for prefixes, parent in PARENTS:
        if any(name.startswith(p) for p in prefixes):
            return parent
    return ""


# Fields that live only inside the srm[] sector list, not projected onto any
# per-ticker daily_list row. Hand-verified against drive_sync.py — these are
# NOT in _FIELD_SCHEMA because they were never meant to be a per-ticker field.
# _FIELD_SCHEMA / _FIELD_GLOSSARY turned out NOT to be a reliable "is this on
# daily_list" test — a direct read of a live export found 97 keys on a
# daily_list record, including sc_momentum, flow, energy, structure, mp,
# on_longlist, gics_gate: the export's most fundamental fields, none of them
# in either schema dict. Those two dicts document a SUBSET of what ships, not
# the full set, so a field's absence from them proves nothing. The live
# export file is the only reliable ground truth for what actually landed in
# JSON on a real run — read it directly at generation time.
EXPORT_SAMPLE = ROOT / "aegis" / "output" / "aqe_daily_export.json"

# The SRM list's own field names differ from what gets PROJECTED onto a
# scored ticker (confirmed from a live srm[0] read): the list itself carries
# grade/roc20/roc5/divergence/above_sma20/grade_path/sh_value/grade_trend/
# sh_trend/etf/sector/entry_gate/entry_gate_reason/macro_headwind_flag/
# macro_headwind_score/rrg_quadrant/rrg_direction/rrg_rs_ratio/
# rrg_rs_momentum/rrg_grade_override/trend_state — note trend_state and
# rrg_quadrant/rrg_direction, NOT "sector_"-prefixed; the sector_-prefixed
# names are the separate per-ticker projected fields.
SRM_LIST_FIELDS = {
    "grade", "above_sma20", "roc20", "roc5", "divergence", "grade_path",
    "sh_value", "grade_trend", "sh_trend", "etf", "sector", "entry_gate",
    "entry_gate_reason", "macro_headwind_flag", "macro_headwind_score",
    "rrg_quadrant", "rrg_direction", "rrg_rs_ratio", "rrg_rs_momentum",
    "rrg_grade_override", "trend_state",
}
# None of these are projected onto daily_list under the SAME name (the
# projected names carry a sector_/rrg_ prefix instead), so every one of them
# is srm[]-only.
SRM_LIST_ONLY = set(SRM_LIST_FIELDS)

# thematic_baskets[] is empty on every record in the stale 2026-07-28 sample
# (no basket matched), so its per-entry keys can't be read live — confirmed
# instead from the dict literal that builds it, drive_sync.py:1078-1089.
THEMATIC_LIST_FIELDS = {
    "basket", "grade", "grade_path", "breadth_pct", "parent_capped_grade",
    "parent_gics", "parent_grade", "rrg_quadrant", "rrg_direction",
}
# grade/grade_path/parent_gics/parent_grade/rrg_quadrant/rrg_direction ALSO
# reach daily_list, flattened from the FIRST basket onto
# thematic_grade/thematic_parent_gics/thematic_parent_grade/
# thematic_rrg_quadrant/thematic_rrg_direction (drive_sync.py:1091-1096) —
# under different names, so those are classified "daily_list" via the live
# sample, not listed here. Only the fields with no flattened daily_list
# sibling are basket-list-only.
THEMATIC_LIST_ONLY = {"basket", "breadth_pct", "parent_capped_grade"}

QS_BLOCK_PREFIX = "qs."
QS_BLOCK_ONLY = {"qs_market", "qs_status"}

# The PTJ broker-journal fields that ride on held_positions only, confirmed
# from a live held_positions[0] read: cob_price, exposure, notes,
# position_type, ptj_sector, ptj_srm_grade, qty, trade_date.
_JOURNAL_ONLY = {"cob_price", "exposure", "notes", "position_type",
                 "ptj_sector", "ptj_srm_grade", "qty", "trade_date"}


def _load_live_export_keys() -> dict:
    """{'daily_list', 'held_positions', 'srm'} -> the real key set observed
    on a live export record. Empty sets if no export is on disk — the
    classifier falls back to the schema dicts + hand-verified sets above,
    it does not fail."""
    if not EXPORT_SAMPLE.exists():
        return {"daily_list": set(), "held_positions": set(), "srm": set()}
    try:
        import json
        d = json.loads(EXPORT_SAMPLE.read_text(encoding="utf-8"))
        dl = set((d.get("daily_list") or [{}])[0].keys())
        hp = set((d.get("held_positions") or [{}])[0].keys())
        srm = set((d.get("srm") or [{}])[0].keys())
        return {"daily_list": dl, "held_positions": hp, "srm": srm}
    except Exception:  # noqa: BLE001
        return {"daily_list": set(), "held_positions": set(), "srm": set()}


def classify_export_location(name: str) -> str:
    """WHERE this field actually lands in aqe_daily_export.json, or the
    honest 'not exported' answer for a pure calculation intermediate.

    Primary ground truth is a LIVE export file's own keys (daily_list[0],
    held_positions[0], srm[0]) — _FIELD_SCHEMA/_FIELD_GLOSSARY were tried
    first and found to cover only a subset of what actually ships (see
    EXPORT_SAMPLE's comment). Falls back to the schema dicts and the
    hand-verified srm[]/thematic[]/qs{}/journal sets above for anything the
    one sampled record happens not to carry (a null-stripped or
    conditional field).
    """
    from src.data import drive_sync as D

    live = _load_live_export_keys()

    if name in ("role", "side", "unit"):
        return ("field_schema{}'s own entries — every field_schema[name] "
               "dict carries a role/unit/side; not a scalar of its own")
    if name.startswith(QS_BLOCK_PREFIX) or name in QS_BLOCK_ONLY:
        return "qs{} block"
    if name in _JOURNAL_ONLY:
        return "held_positions only (PTJ broker journal passthrough)"
    if name in THEMATIC_LIST_ONLY:
        return "daily_list[].thematic_baskets[] (nested, per-basket)"

    # daily_list checked before srm[]-only, because several names exist on
    # BOTH (e.g. 'grade' does not, but this ordering matters generally) —
    # a field actually observed on a scored ticker is definitively exported
    # there regardless of what else shares its name elsewhere.
    if name in live["daily_list"]:
        return "daily_list"
    if name in live["held_positions"]:
        return "held_positions only"
    if name in SRM_LIST_ONLY and name in live["srm"]:
        return "srm[] block only (not projected per-ticker)"
    if name in SRM_LIST_ONLY:
        return "srm[] block only (not projected per-ticker)"

    held_glossary_only = {k for k, v in D._FIELD_GLOSSARY.items()
                          if "held_positions only" in str(v)
                          or "held only" in str(v).lower()}
    if name in held_glossary_only:
        return "held_positions only"
    if name in D._FIELD_SCHEMA or name in D._FIELD_GLOSSARY:
        return "daily_list"

    for engine, cols in D._SUBCOMPONENT_SPEC.items():
        if name in cols:
            return f"subcomponents.{engine}"

    # Known merge-time renames: the field documents the ENGINE's own raw
    # column (this taxonomy's stated principle), but the export only ships
    # the renamed name inside subcomponents. Stated explicitly rather than
    # left to look unexported.
    renamed = {
        "ret_12m_score": "subcomponents.pipe (as pr_ret_12m)",
        "rsi_score": "subcomponents.pipe (as pr_rsi_score)",
        "vol_score": "subcomponents.pipe (as pr_vol_score)",
        "ma_score": "subcomponents.pipe (as pr_ma_score)",
    }
    if name in renamed:
        return renamed[name]

    return "NOT EXPORTED — reference/calculation figure only"


def main() -> None:
    rows = [R(n, "", "block", t, "", d, src, "", ships_in_export="top-level export key")
            for n, t, d, src in BLOCKS]
    rows += SCORE_TREE
    rows += leaf_rows()

    for r in rows:
        if not r["ships_in_export"] and r["level"] != "block":
            r["ships_in_export"] = classify_export_location(r["field"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)} — {len(rows)} rows")


if __name__ == "__main__":
    main()
