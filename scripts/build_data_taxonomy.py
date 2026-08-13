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
      "Momentum pipeline composite, 1-3 week hold", "engines/scoring.py:SC_M_WEIGHTS",
      "0.30*flow + 0.30*energy + 0.20*structure + 0.20*mp; uncapped, no floors applied"),
    R("sc_momentum_raw", "sc_momentum", "composite", "0-100", "",
      "Ungated composite; equals sc_momentum in v1.8.0", "engines/scoring.py",
      "same weighted average before gate flags"),
    R("sc_m_gates", "sc_momentum", "leaf", "bool", "true|false",
      "All momentum gate floors cleared", "engines/scoring.py:SC_M_GATES",
      "elder>=6.5 AND flow>=60 AND energy>=60 AND structure>=55 AND mp>=55"),
    R("sc_position", "", "composite", "0-100", "",
      "Base-building composite, 3-6 week hold", "engines/scoring.py:SC_P_WEIGHTS",
      "0.10*flow + 0.30*energy + 0.20*structure + 0.05*mp + 0.35*bq"),
    R("sc_p_gates", "sc_position", "leaf", "bool", "true|false",
      "All position gate floors cleared", "engines/scoring.py:SC_P_GATES",
      "flow>=40 AND energy>=60 AND structure>=65 AND mp>=40 AND bq>=60 AND k39"),

    # ── Flow ─────────────────────────────────────────────────────────────
    R("flow", "sc_momentum", "engine", "0-100", "",
      "Money flow: institutional accumulation vs distribution", "engines/flow.py",
      "clip(flow_score+accum_score+volume_score+skew_score+ext, 0, 38) / 38 * 100",
      "0.30 of sc_momentum; 0.10 of sc_position"),
    R("flow_score", "flow", "component", "0-17", "",
      "MFI + CMF joint band, plus Heikin-Ashi consecutive-bar count",
      "engines/flow.py:69-110", "clip(fl_fb + ha_b, upper=17)", "17 of 38"),
    R("fl_fb", "flow_score", "leaf", "0-11", "",
      "MFI/CMF joint threshold band", "engines/flow.py:69-73",
      "mfi>38 or cmf>-0.05 ->2.5; mfi>42 and cmf>0 ->5.0; "
      "mfi>48 and cmf>0.02 ->8.0; mfi>55 and cmf>0.05 ->11.0", "11 of 17"),
    R("ha_b", "flow_score", "leaf", "0|2|4|6", "",
      "Heikin-Ashi consecutive-bar quality count, banded",
      "engines/flow.py:105-107",
      "count(qualifying HA bars in trailing window) >=2->2, >=3->4, >=5->6",
      "6 of 17"),
    R("accum_score", "flow", "component", "0-7.5", "",
      "A/D line short vs long linear-regression slope", "engines/flow.py:120-124",
      "ad=rollsum(A/D,60); s=linreg(ad,10); l=linreg(ad,20); "
      "s>0->1.5; s>l*0.85->3.0; s>l->5.5; s>l*1.1->7.5", "7.5 of 38"),
    R("volume_score", "flow", "component", "0-7.5", "",
      "Volume trend plus spike", "engines/flow.py:130-138",
      "vtr=sma(v,5)/sma(v,20): >0.9->2, >1.05->4, >1.2->5.5; "
      "spk=v/sma(v,20): >1.5->1, >2.0->2; clip(sum, upper=7.5)", "7.5 of 38"),
    R("skew_score", "flow", "component", "0-3.5", "",
      "Up-volume vs down-volume over 10 bars", "engines/flow.py:148-151",
      "udr=sum(up_vol,10)/sum(down_vol,10): >=0.8->1.5, >1.2->2.5, >1.5->3.5",
      "3.5 of 38"),
    R("ext_score", "flow", "component", "-8 to +5", "",
      "Extension from 20-bar range and EMA20", "engines/flow.py:159-190",
      "range position and EMA20 distance banded; negative when overextended",
      "-8..+5 of 38"),

    # ── Energy ───────────────────────────────────────────────────────────
    R("energy", "sc_momentum", "engine", "0-100", "",
      "Stored energy: compression, position, exhaustion", "engines/energy.py",
      "clip((vp_position+price_action+squeeze+exhaustion+atr) / 59.5 * 100, 0, 100)",
      "0.30 of sc_momentum; 0.30 of sc_position"),
    R("vp_position_score", "energy", "component", "0-17.5", "",
      "Range-position proxy for volume-profile location", "engines/energy.py:39-61",
      "clip(en_psc + en_lvn_proxy, upper=17.5); true VP array (POC/VAH/VAL) "
      "is diagnostic only in Pine and not computed here", "17.5 of 59.5"),
    R("en_pos50", "vp_position_score", "leaf", "0-100 pct", "",
      "Close position inside the 50-bar high/low range", "engines/energy.py:39-46",
      "(close - lowest(low,50)) / (highest(high,50) - lowest(low,50)) * 100; "
      "50.0 when the 50-bar range is zero"),
    R("en_psc", "vp_position_score", "leaf", "3-17", "",
      "Step score banding en_pos50, with an extension penalty at the top",
      "engines/energy.py:48-54",
      "en_pos50 <30->3, >=30->5, >=45->8, >=60->12, >=75->17, >=90->15 "
      "(90+ scores LESS than 75-90 on purpose — Pine's own extension penalty)",
      "17 of 17.5"),
    R("en_lvn_proxy", "vp_position_score", "leaf", "0|1.5", "",
      "Low-volume-node proxy: tight 5-bar range high in the 50-bar range",
      "engines/energy.py:56-60",
      "1.5 if (en_pos50>75) AND (highest(high,5)-lowest(low,5) < 2*ATR20) else 0",
      "1.5 of 17.5"),
    R("price_action_score", "energy", "component", "0-12.5", "",
      "Higher lows, range tightness, pullback depth, discounted low in range",
      "engines/energy.py:69-100",
      "clip(structure_score + tightness_score + pullback_score, ...) then "
      "x0.7 if en_pos50<45, x0.5 if en_pos50<30", "12.5 of 59.5"),
    R("hl_count", "price_action_score", "leaf", "0-4", "",
      "Count of the last 4 bars making a higher low", "engines/energy.py:64-67",
      "sum over i=0..3 of (low[t-i] > low[t-i-1])"),
    R("structure_score", "price_action_score", "leaf", "0-5", "",
      "Step score on hl_count", "engines/energy.py:68-72",
      "hl_count >=1->1.5, >=2->3.0, >=3->4.0, >=4->5.0", "5 of 12.5"),
    R("compression_ratio", "price_action_score", "leaf", "ratio", "",
      "5-bar range as a fraction of the 20-bar range", "engines/energy.py:74-76",
      "(highest(high,5)-lowest(low,5)) / (highest(high,20)-lowest(low,20))"),
    R("tightness_score", "price_action_score", "leaf", "0-4.5", "",
      "Step score on compression_ratio, boosted while trending",
      "engines/energy.py:77-86",
      "ratio<0.9->1.0, <0.7->2.0, <0.5->3.5, <0.3->4.5; "
      "+1.5 (capped 4.5) if close>EMA20 AND close>close[5]", "4.5 of 12.5"),
    R("pullback_pct", "price_action_score", "leaf", "0-100 pct", "",
      "Pullback from the 20-bar high", "engines/energy.py:88-89",
      "(highest(high,20) - close) / highest(high,20) * 100"),
    R("pullback_score", "price_action_score", "leaf", "0-3", "",
      "Step score on pullback_pct", "engines/energy.py:90-93",
      "pullback_pct<25->1.0, <15->2.0, <10->2.5, <5->3.0", "3 of 12.5"),
    R("squeeze_score", "energy", "component", "0-12.5", "",
      "Bollinger/Keltner squeeze and bandwidth percentile", "engines/energy.py:102-124",
      "no squeeze: bwp<50->4, bwp<30->8.5; in squeeze (bb inside keltner): 5, "
      "bwp<50->7.5, bwp<35->10, bwp<20->12.5", "12.5 of 59.5"),
    R("bwp", "squeeze_score", "leaf", "0-100 pct", "",
      "Bollinger bandwidth percentile of its own 50-bar range",
      "engines/energy.py:104-111",
      "bw=(BB_upper-BB_lower)/BB_mid*100 (BB: SMA20 +/- 2*stdev20); "
      "bwp=(bw-lowest(bw,50))/(highest(bw,50)-lowest(bw,50))*100"),
    R("exhaustion_score", "energy", "component", "0-10", "",
      "Penalty for climactic, divergent or wide-spread bars, applied only "
      "once the trend is mature", "engines/energy.py:126-167",
      "en_trend_bars>=15: clip(10 + climactic_penalty + divergence_penalty "
      "+ wide_spread_penalty, lower=0); else 10 unconditionally", "10 of 59.5"),
    R("en_trend_bars", "exhaustion_score", "leaf", "int >=0", "",
      "Consecutive bars closing above EMA20", "engines/energy.py:129-134",
      "running count, resets to 0 on any close <= EMA20"),
    R("climactic_penalty", "exhaustion_score", "leaf", "-4|-2.5|0", "",
      "Penalty for a high-volume bar with a weak price gain",
      "engines/energy.py:138-141",
      "vol/SMA20vol>3.0 AND gain%<2 ->-4.0; >2.5 AND gain%<3 ->-2.5; else 0"),
    R("divergence_penalty", "exhaustion_score", "leaf", "-3|-2|0", "",
      "Penalty for a new price high with MFI or MACD not confirming",
      "engines/energy.py:143-151",
      "new 10-bar high AND MFI(14)<its 5-bar-prior max ->-3.0; "
      "new high AND MACD-line<its 5-bar-prior max ->-2.0; else 0"),
    R("wide_spread_penalty", "exhaustion_score", "leaf", "-3|-1.5|0", "",
      "Penalty for an abnormally wide bar on high volume",
      "engines/energy.py:153-161",
      "range/ATR20>2.0 AND vol/SMA20vol>2.0 AND no next-bar follow-through "
      "->-3.0; range/ATR20>1.5 AND vol/SMA20vol>1.5 ->-1.5; else 0"),
    R("atr_score", "energy", "component", "0-7", "",
      "ATR expansion inside the productive band", "engines/energy.py:182-189",
      "atr_expansion_pct in [20,80] -> 7; >=15 -> 5.5; >=10 -> 4.0; "
      ">150 -> 2.0; >80 -> 4.0; >=0 -> 1.0; >=-10 -> 0.5; else 0", "7 of 59.5"),
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
      "Weekly close vs weekly SMA10", "engines/structure.py:202-212",
      "no weekly data->7.5; else wk_close vs wk_sma10: >0.93x->2, >0.97x->5, "
      ">1.00x->10, and rising->15", "15 of 95"),
    R("earn_score", "structure", "component", "0-10", "",
      "Distance to the next earnings date", "engines/structure.py:docstring",
      "days_to_earnings: <=5->0, <=10->4, <=20->7, >20 or unknown->10", "10 of 95"),

    # ── MP ───────────────────────────────────────────────────────────────
    R("mp", "sc_momentum", "engine", "0-100", "",
      "Momentum persistence: will the move keep going", "engines/mp.py",
      "clip(abs_mom + adx + rel_mom + trend, 0, 100)",
      "0.20 of sc_momentum; 0.05 of sc_position"),
    R("abs_mom_score", "mp", "component", "0-30", "",
      "20-day ROC z-score against its own 50-day distribution",
      "engines/mp.py:42-49",
      "z=roc_zscore: >=2->30, >=1.5->26, >=1->22, >=0.5->16, >=0->10, "
      ">=-0.5->5, else 0", "30 of 100"),
    R("roc_zscore", "abs_mom_score", "leaf", "z-score", "",
      "20-day rate of change, standardised against its own 50-day mean/stdev",
      "engines/mp.py:42-45",
      "roc20=(close/close[20]-1)*100; z=(roc20-sma(roc20,50))/"
      "stdev_pop(roc20,50)"),
    R("adx_score", "mp", "component", "0-25", "",
      "Trend strength, only when DI is bullish", "engines/mp.py:57-62",
      "adx_val>=20 and di_bullish->12, >=25->18, >=30->22, >=40->25", "25 of 100"),
    R("adx_val", "adx_score", "leaf", "0-100", "",
      "14-period Average Directional Index (Wilder)", "engines/mp.py:57",
      "standard ADX from +DI/-DI (Wilder-smoothed directional movement)"),
    R("di_bullish", "adx_score", "leaf", "bool", "true|false",
      "+DI above -DI — directional gate on the ADX score",
      "engines/mp.py:58", "plus_di > minus_di"),
    R("rel_mom_score", "mp", "component", "0-25", "",
      "20-day excess return vs SPY", "engines/mp.py:65-72",
      "excess_return: >=15->25, >=10->22, >=5->18, >=2->13, >=0->8, "
      ">=-3->3, else 0", "25 of 100"),
    R("excess_return", "rel_mom_score", "leaf", "pct", "",
      "20-day return, stock minus SPY", "engines/mp.py:65-68",
      "(close/close[20]-1)*100 - (spy_close/spy_close[20]-1)*100"),
    R("trend_score", "mp", "component", "0-20", "",
      "Moving-average stacking", "engines/mp.py:74-94",
      "above EMA20 only, not above SMA50 ->5; above SMA50, SMA50 not "
      "rising ->8; above SMA50 and rising, not above EMA20 ->12; above "
      "both and SMA50 rising but EMA20 not ->16; above both and both "
      "rising ->20", "20 of 100"),
    R("mp_state", "mp", "leaf", "label", "BUILDING|STRONG|FADING",
      "Phase label for the momentum reading", "engines/mp.py", "banded on mp"),
    R("mp_accel", "mp", "leaf", "float", "",
      "Additive momentum acceleration, outside the Pine spec", "engines/mp.py",
      "change in momentum; dead zone +/-0.10"),
    R("mp_accel_state", "mp_accel", "leaf", "label",
      "ACCELERATING|FLAT|DECELERATING", "Acceleration band",
      "engines/mp.py:ACCEL_UP/ACCEL_DN", ">0.10 up, <-0.10 down, else flat"),

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
      "ACCELERATION|ACCUMULATION_BASE|CORRECTION_REENTRY|INTERRUPTED|SUSTAINED",
      "Named impulse sequence", "engines/elder_context.py", "5-state classifier"),

    # ── BQ / K39 ─────────────────────────────────────────────────────────
    R("bq", "sc_position", "engine", "0-100", "",
      "Base quality for the position pipeline", "engines/bq.py",
      "bq_range_tight + bq_vol_dry + bq_base_dur + bq_ema_conv; already 0-100",
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
      "Base duration", "engines/bq.py:52-125",
      "same 3-mode/latch/decay mechanism as structure's base_score, with a "
      "60-bar pivot and an 8% band, and its own tiers: 3-4d->4, 5-6d->8, "
      "7-9d->14, 10-25d->20, 25-35d->14, >35d->8", "20 of 100"),
    R("bq_base_days", "bq_base_dur", "leaf", "int >=0", "",
      "BQ's own base-day count — same mechanism as structure.base_days but a "
      "distinct instance (60-bar pivot, 8% band, not shared state)",
      "engines/bq.py:60-116", "see bq_base_dur formula"),
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
      "Pre-screen rank used to order the scoring queue", "engines/pipeline_rank.py",
      "percentile blend of 12-month return, base and liquidity"),
    R("pipe_tier", "pipe_rank", "leaf", "label", "A-TIER|B|C-WATCH|D-SKIP",
      "Tier label from pipe_rank", "engines/pipeline_rank.py", "banded on pipe_rank"),

    # PTRS and the disposition ceiling that briefly replaced it are both
    # retired (2026-08-13). Both were a re-read of SC_MOMENTUM through a
    # threshold table with no consumer. The shortlist's only floor is now a
    # direct comparison: sc_momentum >= 45 (SHORTLIST_MIN_SC in
    # pipeline/daily_orchestrator.py) — not a scored value, so it has no row
    # here; see the taxonomy note in that file.

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
