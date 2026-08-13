"""Emit the AQE data taxonomy as CSV.

Output: docs/AQE_DATA_TAXONOMY.csv

Columns
    field              exported name, or internal name for a component
    parent             the field this one feeds; blank at the root
    level              composite | engine | component | leaf | block | context
    output             numeric range, type, or literal
    state              enum values, pipe-separated; blank if not categorical
    represents         what the number is, one clause
    source             module:symbol
    formula            the arithmetic, transcribed from source
    weight             contribution to parent: fraction, max points, or blank

Two inputs:
  1. SCORE_TREE below — parent/child math transcribed from src/engines/*.py
     with the divisor and every component maximum. Verified to sum: Flow 38,
     Energy 59.5, Structure 95, MP 100, BQ 100, Elder 10.
  2. The export's own field_schema / field_glossary / enum sets, read from code
     at generation time, for every leaf the tree does not cover.

Run:  python -m scripts.build_data_taxonomy
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "AQE_DATA_TAXONOMY.csv"

COLUMNS = ["field", "parent", "level", "output", "state", "represents",
           "source", "formula", "weight"]


def R(field, parent, level, output, state, represents, source, formula, weight=""):
    return dict(zip(COLUMNS, [field, parent, level, output, state, represents,
                              source, formula, weight]))


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
      "Base-building composite, 3-6 week hold", "engines/scoring.py:_sc_position_raw",
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
      "ad_short>ad_long*1.1->7.5", "7.5 of 38"),
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
      "5-day average volume over 20-day average volume", "engines/flow.py:126-127",
      "sma(volume,5) / sma(volume,20)"),
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
      "Close position inside the 50-bar high/low range", "engines/energy.py:39-46",
      "(close - lowest(low,50)) / (highest(high,50) - lowest(low,50)) * 100; "
      "50.0 when the 50-bar range is zero"),
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
      "Bollinger/Keltner squeeze state and bandwidth percentile",
      "engines/energy.py:113-124",
      "sq=false: bwp<50->4.0, bwp<30->8.5; sq=true: 5.0, bwp<50->7.5, "
      "bwp<35->10.0, bwp<20->12.5", "12.5 of 59.5"),
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
      "(close/close[60]-1)*100 - (spy_close/spy_close[60]-1)*100"),
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
    R("ms_pos", "structure", "component", "0-15", "",
      "Position in the 50-bar range", "engines/structure.py:163-192",
      "ms_p50: >=45->4, >=60->7, >=75->10, >=85->13, >=95->15", "15 of 95"),
    R("ms_p50", "ms_pos", "leaf", "0-100 pct", "",
      "Close position inside the 50-bar high/low range",
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
      ">=-0.5->5, else 0", "30 of 100"),
    R("roc_zscore", "abs_mom_score", "leaf", "z-score", "",
      "20-day rate of change, standardised against its own 50-day mean/stdev",
      "engines/mp.py:42-45",
      "roc20=(close/close[20]-1)*100; roc_zscore=(roc20-sma(roc20,50))/"
      "stdev_pop(roc20,50)"),
    R("adx_score", "mp", "component", "0-25", "",
      "Trend strength, gated on DI direction", "engines/mp.py:57-62",
      "(adx_val>=20 AND di_bullish)->12; (adx_val>=25 AND di_bullish)->18; "
      "(adx_val>=30 AND di_bullish)->22; (adx_val>=40 AND di_bullish)->25; "
      "else 0", "25 of 100"),
    R("adx_val", "adx_score", "leaf", "0-100", "",
      "14-period Average Directional Index, Wilder RMA of DX",
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
      ">=-3->3, else 0", "25 of 100"),
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
      "Base quality for the position pipeline; the four components already "
      "sum to 0-100 so there is no divisor, unlike Flow/Energy/Structure",
      "engines/bq.py:139",
      "clip(bq_range_tight + bq_vol_dry + bq_base_dur + bq_ema_conv, 0, 100)",
      "0.35 of sc_position"),
    R("bq_range_tight", "bq", "component", "0-30", "",
      "Range tightness", "engines/bq.py:32-39",
      "rt_ratio<1.0->4, <0.9->8, <0.8->14, <0.7->20, <0.6->25, <0.5->30",
      "30 of 100"),
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
      "EMA(8/13/21) convergence", "engines/bq.py:128-136",
      "norm_spread<2.5->5, <1.8->10, <1.2->15, <0.8->20, <0.5->25",
      "25 of 100"),
    R("norm_spread", "bq_ema_conv", "leaf", "ratio", "",
      "Spread of EMA8/13/21 normalised by ATR20", "engines/bq.py:128-131",
      "(max(EMA8,EMA13,EMA21) - min(EMA8,EMA13,EMA21)) / ATR(20)"),
    R("k39_gate", "sc_position", "leaf", "bool", "true|false",
      "Weekly stochastic and OBV confirmation", "engines/k39.py",
      "stoch(weekly,39)>50 AND obv_weekly>sma(obv_weekly,30); "
      "mapped to daily as-of, no look-ahead"),

    # ── Pipeline Rank ────────────────────────────────────────────────────
    R("pipe_rank", "", "engine", "0-100", "",
      "Pre-screen rank used to order the scoring queue", "engines/pipeline_rank.py:157",
      "clip(momentum_composite*0.70 + fip_quality*0.30, 0, 100)"),
    R("momentum_composite", "pipe_rank", "leaf", "0-100", "",
      "Sum of five 20-point technical sub-scores", "engines/pipeline_rank.py:93-155",
      "clip(ret_score + adx_score + rsi_score + vol_score + ma_score, 0, 100)",
      "70 pct weight"),
    R("ret_score", "momentum_composite", "leaf", "0-20", "",
      "12-month return skipping the most recent month, banded",
      "engines/pipeline_rank.py:93-99",
      "ret_12m=(close/close[231]-1)*100; >-10->4, >0->8, >10->12, >25->16, "
      ">50->20", "20 of 100"),
    R("pr_adx_score", "momentum_composite", "leaf", "0-20", "",
      "ADX(14) trend strength, gated on DI direction. pipeline_rank.py has "
      "its own _adx/_dmi (ATR-normalised DI), a separate implementation "
      "from MP's adx_val/di_bullish, not the same series",
      "engines/pipeline_rank.py:102-109",
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
      "FIP path-quality score, penalised for spikes", "engines/pipeline_rank.py:161-172",
      "base: fip_raw>0.10->10; (0<fip_raw<=0.10)->30; (-0.05<=fip_raw<=0)"
      "->60; (-0.10<=fip_raw<-0.05)->80; fip_raw<-0.10->100; else 50; "
      "clip(base - spike_penalty, 0, 100)", "30 pct weight"),
    R("pipe_tier", "pipe_rank", "leaf", "label", "D-SKIP|C-WATCH|B-STRONG|A-TIER",
      "Tier label from pipe_rank", "engines/pipeline_rank.py:230-234",
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
    R("mover_subtype", "", "leaf", "label", "explosive|trend|tight_base|squeeze",
      "The z-scored feature family the name resembles most",
      "engines/signal_radar.py:219-229",
      "argmax over 4 families of mean((feature-frozen_mean)/frozen_std) "
      "across each family's feature set"),

    # ── Sector / thematic state fields ──────────────────────────────────
    R("gics_grade", "", "leaf", "label", "DEPLOY|HOLD|TURNING|WATCH|AVOID",
      "Sector ETF grade; evaluated top-down, first match wins. Two roads "
      "reach DEPLOY (a 20d trend road, a 5d acceleration road) and two "
      "reach TURNING; grade_path on the row says which one fired. "
      "divergence=roc5-roc20", "engines/srm.py:299-317",
      "(above20 AND roc20>5.0)->DEPLOY; (above20 AND roc20>=0 AND roc5>=6.0 "
      "AND divergence>=5.0)->DEPLOY; (above20 AND roc20>0)->HOLD; (above20 "
      "AND roc20<=0 AND divergence>=5.0)->TURNING; (NOT above20 AND "
      "divergence>0)->TURNING; (above20 AND roc20<=0)->WATCH; else AVOID"),
    R("gics_gate", "", "leaf", "label", "PASS|WATCH|CAUTION|BLOCKED",
      "Sector entry gate combining grade, RRG quadrant and macro flag",
      "engines/srm.py:966-983",
      "grade==AVOID->BLOCKED; (macro==HEADWIND AND rrg==LAGGING)->BLOCKED; "
      "macro==HEADWIND->CAUTION; (rrg in [LAGGING,WEAKENING] AND "
      "macro==CAUTION)->CAUTION; (grade in [DEPLOY,HOLD] AND rrg in "
      "[LEADING,IMPROVING] AND macro in [TAILWIND,NEUTRAL])->PASS; else WATCH"),
    R("sector_trend_state", "gics_grade", "leaf", "label",
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
    R("thematic_grade", "gics_grade", "leaf", "label",
      "DEPLOY|HOLD|TURNING|WATCH|AVOID|NO_DATA",
      "Basket grade, demoted from a narrow rally", "engines/srm.py:485-495",
      "index_grade = gics_grade's own ladder applied to the basket's "
      "equal-weight constituent index vs SPY; grade = HOLD[narrow] if "
      "index_grade==DEPLOY AND breadth<0.60 else index_grade"),
    R("basket_breadth", "thematic_grade", "leaf", "0-1 pct", "",
      "Fraction of basket constituents above their OWN 20-day SMA",
      "engines/srm.py:372-382",
      "count(constituent close > constituent's own SMA20) / n_measurable"),
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
      "Longlist membership", "longlist_screen.py:passes",
      "sc_momentum_raw >= 65 AND elder >= 7"),
    R("on_elder", "", "leaf", "bool", "true|false",
      "Standalone Elder list membership", "longlist_screen.py", "elder >= 8"),
    R("on_qs", "", "leaf", "bool", "true|false",
      "Quiet Strength emitted a read for this name", "engines/qs_daily.py",
      "qs block present and scored"),

    # ── lens consensus ───────────────────────────────────────────────────
    R("lens_positive", "", "leaf", "0-6", "",
      "Count of lenses reading strong", "engines/lens_consensus.py",
      "unweighted count over leadership, coil, insti_money, structure, "
      "resistance, sector; extension never counts"),
    R("lens_warnings", "", "leaf", "0-6", "",
      "Count of lenses reading warn", "engines/lens_consensus.py",
      "unweighted count, same six lenses"),
]

for _r in SCORE_TREE:
    _r["source"] = "src/" + _r["source"] if _r["source"] and not _r["source"].startswith("src/") else _r["source"]


# ── export blocks ────────────────────────────────────────────────────────
BLOCKS = [
    ("date", "str", "Scan date, US close"),
    ("exported_at", "iso8601", "Write time, SGT"),
    ("market", "str", "Market descriptor"),
    ("regime", "dict", "VIX bucket, Hurst, size ceiling"),
    ("intermarket", "dict", "Cross-asset context"),
    ("srm", "list", "One graded row per GICS sector"),
    ("srm_signals", "dict", "Sector-level signals"),
    ("macro_weather", "dict", "7-instrument direction read"),
    ("regime_stop_pct_ceiling", "float", "Regime cap on stop width, percent"),
    ("spy_roc_20d", "float", "SPY 20-day rate of change"),
    ("thematic_baskets", "dict", "35 baskets, graded, with RRG position"),
    ("sector_map_version", "str", "GICS map version in force"),
    ("sector_map_gaps", "list", "Unclassified tickers"),
    ("field_schema", "dict", "Self-described field types"),
    ("field_schema_enums", "dict", "Permitted values per categorical field"),
    ("field_glossary", "dict", "Self-described field meanings"),
    ("held_positions_status", "enum", "live | cache_fallback | unknown"),
    ("held_positions", "list", "PM live book from the trade journal"),
    ("held_book", "dict", "Beta-adjusted exposure, gap scenarios, sector weights"),
    ("daily_list", "list", "Every scored ticker, full field set"),
    ("lens_ranking", "dict", "Same names ordered by lens agreement"),
    ("summary", "dict", "Run counts"),
    ("signal_radar", "dict", "Radar tag totals"),
    ("data_quality", "dict", "Scored records carrying a null core field"),
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
    for name in sorted(set(schema) | set(gloss) | set(enums)):
        if name in covered or name.startswith("_"):
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
        rows.append(R(name, _parent_of(name), "leaf", unit or "",
                      "|".join(str(v) for v in enums.get(name, [])),
                      desc, "src/data/drive_sync.py:_FIELD_GLOSSARY", "",
                      role))
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


def main() -> None:
    rows = [R(n, "", "block", t, "", d, "src/data/drive_sync.py:build_export", "")
            for n, t, d in BLOCKS]
    rows += SCORE_TREE
    rows += leaf_rows()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)} — {len(rows)} rows")


if __name__ == "__main__":
    main()
