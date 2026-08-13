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
      "MFI + CMF + Heikin-Ashi bar quality", "engines/flow.py:110",
      "clip(mfi_cmf_bands + ha_bands, upper=17); ha_bands: count>=2->2, >=3->4, >=5->6",
      "17 of 38"),
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
      "Range-position proxy for volume-profile location", "engines/energy.py:61",
      "clip(en_psc + en_lvn_proxy, upper=17.5); true VP array is diagnostic only",
      "17.5 of 59.5"),
    R("price_action_score", "energy", "component", "0-12.5", "",
      "Higher lows, range tightness, pullback depth", "engines/energy.py:69-100",
      "structure(<=5: hl>=1->1.5,>=2->3,>=3->4,>=4->5) + tightness(<=4.5) + "
      "pullback(<25%->1,<15%->2,<10%->2.5,<5%->3); "
      "x0.7 if pos50<45, x0.5 if pos50<30", "12.5 of 59.5"),
    R("squeeze_score", "energy", "component", "0-12.5", "",
      "Bollinger/Keltner squeeze and bandwidth percentile", "engines/energy.py:117-124",
      "no squeeze: bwp<50->4, bwp<30->8.5; in squeeze: 5, bwp<50->7.5, "
      "bwp<35->10, bwp<20->12.5", "12.5 of 59.5"),
    R("exhaustion_score", "energy", "component", "0-10", "",
      "Penalty for climactic, divergent or wide-spread bars", "engines/energy.py:167-168",
      "10 + climactic_penalty + divergence_penalty + wide_spread_penalty, "
      "floored at 0; only applied once the trend is mature", "10 of 59.5"),
    R("atr_score", "energy", "component", "0-7", "",
      "ATR expansion inside the productive band", "engines/energy.py:182-189",
      "atr_expansion_pct in [20,80] -> 7; >=0 -> 1; >=-10 -> 0.5; "
      ">80 -> 4; >150 -> 2", "7 of 59.5"),

    # ── Structure ────────────────────────────────────────────────────────
    R("structure", "sc_momentum", "engine", "0-100", "",
      "Relative strength, base quality, overhead supply", "engines/structure.py",
      "clip((rs_spy+rs_accel+base+ms_pos+resist+wk+earn) / 95 * 100, 0, 100)",
      "0.20 of sc_momentum; 0.20 of sc_position"),
    R("rs_spy_score", "structure", "component", "0-15", "",
      "Relative performance vs SPY", "engines/structure.py:45-50",
      "rs_vs_spy: >-3->3, >0->6, >2->10, >5->12, >10->15", "15 of 95"),
    R("rs_accel_score", "structure", "component", "0-15", "",
      "Change in relative strength", "engines/structure.py:56-61",
      "rs_accel: >-5->3, >-2->6, >0->9, >2->12, >5->15", "15 of 95"),
    R("base_score", "structure", "component", "0-15", "",
      "Base duration and quality, with post-breakout decay",
      "engines/structure.py:178",
      "clip(base_raw * higher_lows_multiplier, upper=15); "
      "base_days tiers <3->0,<5->3,5-7->6,7-10->10,10-25->15,25-30->12,"
      "30-35->8,>35->5; multiplier <2 lows->0.6, >=2->0.8, >=4->1.0", "15 of 95"),
    R("ms_pos", "structure", "component", "0-15", "",
      "Position in the 50-bar range", "engines/structure.py:187-192",
      "ms_p50: >=45->4, >=60->7, >=75->10, >=85->13, >=95->15", "15 of 95"),
    R("resist_score", "structure", "component", "0-10", "",
      "Clear air overhead; high means little resistance",
      "engines/structure.py:196-200",
      "dist_to_resist: <=15->3, <=8->5, <=3->10, <=0->7", "10 of 95"),
    R("wk_score", "structure", "component", "0-15", "",
      "Weekly close vs weekly SMA10", "engines/structure.py:205-212",
      "wk_close vs wk_sma10: >0.93x->2, >0.97x->5, >1.00x->10, "
      "and rising->15; 7.5 when no weekly data", "15 of 95"),
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
      "engines/mp.py:48",
      "z=(roc20-sma(roc20,50))/stdev(roc20,50): >=2->30, >=1.5->26, >=1->22, "
      ">=0.5->16, >=0->10, >=-0.5->5, else 0", "30 of 100"),
    R("adx_score", "mp", "component", "0-25", "",
      "Trend strength, only when DI is bullish", "engines/mp.py:58-62",
      "adx>=20 and di_bullish->12, >=25->18, >=30->22, >=40->25", "25 of 100"),
    R("rel_mom_score", "mp", "component", "0-25", "",
      "20-day excess return vs SPY", "engines/mp.py:70",
      "excess: >=15->25, >=10->22, >=5->18, >=2->13, >=0->8, >=-3->3, else 0",
      "25 of 100"),
    R("trend_score", "mp", "component", "0-20", "",
      "Moving-average stacking", "engines/mp.py:84-94",
      "above MA20 only->5; above MA50->8; MA50 rising->12; "
      "stacked basic->16; fully stacked->20", "20 of 100"),
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
      "Impulse colour", "engines/elder.py", "green->4, blue->2, red->0", "4 of 10"),
    R("elder_slope_score", "elder", "component", "0-3", "",
      "3-bar EMA13 slope percent", "engines/elder.py", "banded 0-3", "3 of 10"),
    R("elder_hist_score", "elder", "component", "0-3", "",
      "MACD histogram trend", "engines/elder.py",
      "MACD(12,26,9 EMA signal) histogram direction, banded 0-3", "3 of 10"),
    R("elder_pattern", "elder", "leaf", "label",
      "ACCELERATION|ACCUMULATION_BASE|CORRECTION_REENTRY|INTERRUPTED|SUSTAINED",
      "Named impulse sequence", "engines/elder_context.py", "5-state classifier"),

    # ── BQ / K39 ─────────────────────────────────────────────────────────
    R("bq", "sc_position", "engine", "0-100", "",
      "Base quality for the position pipeline", "engines/bq.py",
      "bq_range_tight + bq_vol_dry + bq_base_dur + bq_ema_conv; already 0-100",
      "0.35 of sc_position"),
    R("bq_range_tight", "bq", "component", "0-30", "",
      "Range tightness", "engines/bq.py", "ATR(5)/ATR(20) ratio, banded", "30 of 100"),
    R("bq_vol_dry", "bq", "component", "0-25", "",
      "Volume dry-up", "engines/bq.py", "SMA(vol,5)/SMA(vol,20), banded", "25 of 100"),
    R("bq_base_dur", "bq", "component", "0-20", "",
      "Base duration", "engines/bq.py", "3-mode detector with latch and decay",
      "20 of 100"),
    R("bq_ema_conv", "bq", "component", "0-25", "",
      "EMA convergence", "engines/bq.py", "EMA spread / ATR(20), banded", "25 of 100"),
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

    # ── disposition ──────────────────────────────────────────────────────
    R("disposition", "sc_momentum", "leaf", "label",
      "FULL|HALF|QUARTER|REJECT",
      "Ticker-quality ceiling; the PM sizes, AQE does not",
      "analyzer/ptrs.py:compute_disposition",
      "sc_momentum >=60->FULL(1.0), >=50->HALF(0.5), >=45->QUARTER(0.25), "
      "else REJECT(0.0)"),
    R("max_size", "disposition", "leaf", "0-1", "",
      "Fraction of a full risk unit permitted by ticker quality",
      "analyzer/ptrs.py:DISPOSITION_CUTS", "1.0 | 0.5 | 0.25 | 0.0"),

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
