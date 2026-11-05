#!/usr/bin/env python3
"""aqe_glossary.py -- builds contracts/aqe_glossary.md, the plain one-page glossary of AQE's composites and sub-components.

Report C (PM 2026-11-05): the AQE-quant seat argues from AQE's own indicators, so every indicator it may cite has to be explained in words
a reader can check: what it measures, its range, what high and low mean. No formulas in the body; each section ends with a footnote that
points at the heading of docs/AQE_TECHNICAL_REFERENCE.md where the arithmetic lives. The test suite proves (a) every composite and every
export sub-component has an entry, (b) every footnote heading exists in the reference doc, (c) the body carries no formula characters.

    python3 tools/aqe_glossary.py            # write contracts/aqe_glossary.md
    python3 tools/aqe_glossary.py --check    # exit 1 if the file on disk is stale
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "contracts", "aqe_glossary.md")

REF = "docs/AQE_TECHNICAL_REFERENCE.md"
# footnote key -> heading text in the reference doc (the test opens the doc and finds each one)
REF_HEADINGS = {
    "F": "1.1 Flow v1.3", "E": "1.2 Energy v1.3.1", "S": "1.3 Structure v1.5.0", "M": "1.4 Momentum Persistence (MP) v1.2",
    "EL": "1.5 Elder Impulse", "BQ": "1.6 Base Quality (BQ)", "K": "1.7 K39 gate", "SC": "2. Composite scores",
    "PR": "3. Pipeline Rank v1.0",
}

# (field, plain name, what it measures, range, high means, low means)
# Composites are top-level row fields; sub-components are read as subcomponents.<engine>.<field>.
COMPOSITES = [
    ("sc_momentum", "Momentum score", "the overall momentum read: money flow and energy count most, structure and persistence next", "0 to 100", "strong, well-supported momentum on every engine", "weak or patchy momentum", "SC"),
    ("sc_m_gates", "Momentum gate", "whether every engine clears its own floor, including Elder", "true or false", "true means every engine passed its floor", "false means at least one engine is below its floor", "SC"),
    ("sc_m_gate_detail", "Momentum gate breakdown", "which engines passed or failed the momentum gate", "a pass or fail per engine", "all pass: no weak link", "the failing engine is the weak link", "SC"),
    ("sc_p_gates", "Position gate", "the longer-hold version of the gate: floors on every engine, base quality and the weekly check", "true or false", "true means the name qualifies as a position candidate", "false means at least one floor is missed", "SC"),
    ("sc_p_gate_detail", "Position gate breakdown", "which engines (and the weekly check) passed or failed the position gate", "a pass or fail per engine", "all pass: no weak link", "the failing engine is the weak link", "SC"),
    ("pipe_rank", "Pipeline rank", "a first-pass screen of trend and the smoothness of the path to get there", "0 to 100", "strong trend reached by steady rather than jumpy days", "weak trend or a jumpy path", "PR"),
    ("flow", "Flow", "whether money is flowing in or out, and how clean the volume is", "0 to 100", "steady buying, volume on the up days, clean candles", "selling pressure or thin, messy volume", "F"),
    ("energy", "Energy", "where price sits in its recent range, how coiled it is, and whether the run looks tired", "0 to 100", "price high in its range with room to run, coiled or expanding in a healthy way", "price low in its range, no coil, or a stretched run", "E"),
    ("structure", "Structure", "strength against the market, quality of the base, weekly trend and distance to the recent high", "0 to 100", "outperforming the market, a clean base, weekly trend up", "lagging the market, no base, weak weekly trend", "S"),
    ("mp", "Momentum persistence", "how strong and how well-aligned the trend is, and whether it keeps going", "0 to 100", "strong move, strong trend, all averages aligned", "a fading or unaligned move", "M"),
    ("mp_state", "Momentum state", "the lifecycle label of persistence: STRONG, BUILDING or FADING", "three labels", "STRONG means rising and already high", "FADING is only the default label, it does not by itself mean decay", "M"),
    ("mp_accel_state", "Momentum acceleration", "whether momentum itself is speeding up, steady or slowing", "ACCELERATING, FLAT or DECELERATING", "accelerating means momentum is still gathering pace", "decelerating means the push is slowing", "M"),
    ("elder", "Elder Impulse", "a short-term gauge of whether trend and momentum agree right now", "0 to 10", "trend and momentum both rising", "both falling, the red condition where buying is discouraged", "EL"),
]

SUBCOMPONENTS = {
    "flow": [
        ("flow_score", "Core flow", "money flow and candle cleanliness together", "0 to 17", "buying pressure with tidy candles", "selling or noisy candles"),
        ("accum_score", "Accumulation", "whether the buying/selling balance line is rising faster than before", "0 to 7.5", "accumulation is accelerating", "no accumulation or distribution"),
        ("volume_score", "Volume trend and spikes", "whether recent volume is rising against its normal level, plus any spike", "0 to 7.5", "volume is picking up", "volume is drying up"),
        ("skew_score", "Up-volume skew", "whether volume is concentrated on up days or down days", "0 to 3.5", "volume leans to the up days", "volume leans to the down days"),
        ("ext_score", "Extension adjustment", "a bonus for a clean breakout on volume, a penalty for a climax or a stretched, weakly closing bar", "-8 to +5", "positive: a confirmed breakout or room to mean-revert up", "negative: climax or extension risk"),
        ("mfi", "Money flow index", "dollar-weighted buying pressure over the last ten bars", "0 to 100", "above 55 is buyers in control", "below 40 is sellers in control"),
        ("cmf", "Close-in-range money flow", "whether volume tends to close near the day's high or low", "about -1 to +1", "positive: closes near the highs on volume", "negative: closes near the lows on volume"),
        ("ha_quality_count", "Clean candle count", "how many of the last ten smoothed candles were orderly", "0 to 10", "many orderly candles", "choppy, erratic candles"),
    ],
    "energy": [
        ("vp_position_score", "Range position score", "points for sitting high in the 50-day range, with a deliberate penalty at the very top", "0 to 17.5", "high in the range but not at the extreme", "low in the range"),
        ("price_action_score", "Price-action quality", "higher lows, tightness of the last week against the last month, and the size of any pullback", "0 to about 12", "orderly higher lows and a tight range", "ragged action, or price sitting low in the range (which discounts the score)"),
        ("squeeze_score", "Squeeze / coil", "how compressed volatility is: the coiled-spring read", "0 to 12.5", "tightly coiled", "no compression"),
        ("exhaustion_score", "Exhaustion", "wear on a long run: climactic volume, divergence at highs, wide bars with no follow-through", "0 to 10, with 10 as untouched", "10 means no sign of exhaustion (or the run is too young to judge)", "low means a tired, climax-prone run"),
        ("atr_score", "Range expansion", "whether daily ranges are expanding at a healthy pace", "0 to 7", "moderate expansion", "stagnant ranges, or a blow-off expansion"),
        ("en_pos50", "50-day range position", "where price sits between the 50-day low and high", "0 to 100", "near the 50-day high", "near the 50-day low"),
        ("en_trend_bars", "Days above the 20-day average", "how many bars in a row price has held above its 20-day average", "0 and up", "a long unbroken run (exhaustion checks start at 15)", "a young or broken run"),
    ],
    "structure": [
        ("rs_spy_score", "Relative strength score", "points for beating the market over about three months", "0 to 15", "clearly outperforming", "lagging"),
        ("rs_accel_score", "Relative-strength acceleration score", "points for outperformance that is improving", "0 to 15", "the lead over the market is widening", "the lead is shrinking"),
        ("base_score", "Base quality score", "how long and how orderly the recent consolidation was, with credit that fades after a breakout", "0 to 15", "a well-formed base of the right length", "no base, or one that is too short or too old"),
        ("ms_pos_score", "Market-structure position", "points for sitting high in the 50-day range", "0 to 15", "near the range high", "low in the range"),
        ("resist_score", "Room-to-high score", "how close price is to the recent high; just under it scores best, a chase above it scores less", "0 to 10", "just below the high", "far below it, or chasing above it"),
        ("wk_score", "Weekly trend score", "whether the weekly close is above a rising ten-week average", "0 to 15", "weekly trend up", "weekly trend down"),
        ("earn_score", "Earnings-distance score", "how far away the next earnings report is", "0 to 10", "earnings are far off (10 means beyond 20 days or unknown)", "earnings are imminent"),
        ("rs_vs_spy", "Relative strength, raw", "the stock's three-month return minus the market's, in percentage points", "any, in percent", "positive: beating the market", "negative: trailing the market"),
        ("rs_accel", "Relative-strength change, raw", "the one-month relative return minus the three-month relative return, in percentage points", "any, in percent", "positive: the lead is improving", "negative: the lead is eroding"),
        ("base_days", "Base length", "number of days of consolidation counted", "0 and up", "10 to 25 days is the sweet spot", "very short or very long bases score less"),
        ("bd_mode", "Base type", "which base pattern was detected (1, 2 or 3, or 4 for several)", "0 to 4", "label only", "label only"),
    ],
    "mp": [
        ("abs_mom_score", "Momentum size score", "how unusually strong the last month's move is against the stock's own history", "0 to 30", "an unusually strong move", "a weak or negative move"),
        ("mp_adx_score", "Trend strength score", "points for a strong trend with buyers on top", "0 to 25", "a strong, bullish trend", "no trend or a bearish one"),
        ("rel_mom_score", "Relative momentum score", "points for beating the market over the last month", "0 to 25", "well ahead of the market", "behind the market"),
        ("trend_score", "Trend alignment score", "whether price is above its 20-day and 50-day averages and both are rising", "0 to 20", "full alignment", "price below its averages"),
        ("roc_zscore", "Momentum, in standard deviations", "the month's move measured in units of the stock's own normal variation", "about -3 to +4", "2 or more is exceptional", "below 0 is weaker than usual"),
        ("excess_return", "Excess one-month return", "the stock's one-month return minus the market's, in percentage points", "any, in percent", "positive: beating the market", "negative: trailing"),
        ("adx_val", "Trend-strength reading", "how directional the trend is, regardless of up or down", "0 to 100", "above 25 is a real trend, above 40 is very strong", "below 20 is drifting"),
        ("di_bullish", "Buyers on top", "whether upward pressure exceeds downward pressure", "true or false", "true: buyers lead", "false: sellers lead"),
    ],
    "bq": [
        ("bq_range_tight", "Range tightness", "whether recent daily ranges have shrunk against the month", "0 to 30", "ranges have contracted sharply", "ranges are as wide as ever"),
        ("bq_vol_dry", "Volume dry-up", "whether recent volume has fallen against the month", "0 to 25", "volume has dried up, which is how a base ends", "volume is still elevated"),
        ("bq_base_dur", "Base duration", "how long the base has lasted", "0 to 20", "10 to 25 days", "too short or too long"),
        ("bq_ema_conv", "Average convergence", "how tightly the 8, 13 and 21-day averages are bunched", "0 to 25", "tightly bunched", "spread apart"),
        ("bq_base_days", "Base days counted", "the day count behind the base duration score", "0 and up", "longer base", "shorter base"),
    ],
    "pipe": [
        ("pr_ret_12m", "Twelve-month return score", "points for the 12-month return, ignoring the most recent month", "0 to 20", "a large gain", "a loss"),
        ("pr_adx_score", "Trend-strength score", "points for a strong, bullish trend", "0 to 20", "strong trend", "weak trend"),
        ("pr_rsi_score", "Relative-strength-index score", "points for a healthy reading, with a penalty when overbought", "0 to 20", "50 to 70: healthy", "oversold, or above 80 and overbought"),
        ("pr_vol_score", "Volume score", "whether recent volume is rising against its norm", "0 to 20", "rising volume", "falling volume"),
        ("pr_ma_score", "Moving-average score", "how many of the key averages price is above, and whether they stack in order", "0 to 20", "above all of them, in order", "below them"),
        ("momentum_composite", "Pipeline momentum", "the sum of the five pipeline scores above", "0 to 100", "strong across all five", "weak across the five"),
        ("pipe_tier", "Pipeline tier", "the label the pipeline rank earns: A-TIER, B-STRONG, C-WATCH or D-SKIP", "four labels", "A-TIER and B-STRONG advance to full scoring", "C-WATCH and D-SKIP do not"),
    ],
}
ENGINE_NAMES = {"flow": ("Flow", "F"), "energy": ("Energy", "E"), "structure": ("Structure", "S"), "mp": ("Momentum persistence", "M"),
                "bq": ("Base quality (feeds the position gate only)", "BQ"), "pipe": ("Pipeline rank parts", "PR")}


def all_fields():
    """(composite fields, {engine: [subcomponent fields]}) -- the test compares this to the export."""
    return [c[0] for c in COMPOSITES], {e: [r[0] for r in rows] for e, rows in SUBCOMPONENTS.items()}


def render():
    L = ["# AQE glossary -- plain words (generated by tools/aqe_glossary.py; do not hand-edit)", "",
         "Every indicator the AQE-quant seat may cite, in words. Cite a field by the name shown in code font. Each row reads: what it measures · its range · what high means · what low means. "
         "Nothing here is a gate and nothing here is a call: these are readings, and the vote is yours.", "",
         "## Headline composites (top-level fields on every row)", ""]
    for f, name, meas, rng, hi, lo, _ref in COMPOSITES:
        L.append(f"- `{f}` -- **{name}.** Measures {meas}. Range: {rng}. High: {hi}. Low: {lo}.")
    L += ["", "## Sub-components (read as `subcomponents.<engine>.<field>`; they show WHY an engine scored what it did)", ""]
    for eng, rows in SUBCOMPONENTS.items():
        nm, _ref = ENGINE_NAMES[eng]
        L += [f"### {nm} -- `subcomponents.{eng}.*`", ""]
        for f, name, meas, rng, hi, lo in rows:
            L.append(f"- `{f}` -- **{name}.** Measures {meas}. Range: {rng}. High: {hi}. Low: {lo}.")
        L.append("")
    L += ["## Reading rules", "",
          "- A missing value is a disclosure, never a zero: say the reading was not available.",
          "- Composites are uncapped readings; the gates are separate true/false flags, so a high score with a failed gate is a real combination worth naming.",
          "- A raw field (relative strength, excess return, adx reading) is in its own units; a score field is the engine's points. Do not compare across the two.",
          "- Position size, stops and targets are not part of this glossary and not part of your vote.", "",
          "---", "Footnotes -- where the arithmetic lives (not needed to vote):", ""]
    seen = []
    for key in ["SC", "F", "E", "S", "M", "EL", "BQ", "K", "PR"]:
        L.append(f"[{key}] {REF} -- section \"{REF_HEADINGS[key]}\"")
        seen.append(key)
    L.append("")
    return "\n".join(L)


def main(argv):
    text = render()
    if "--check" in argv:
        cur = open(OUT).read() if os.path.exists(OUT) else ""
        if cur != text:
            print("aqe_glossary.md is stale -- run python3 tools/aqe_glossary.py", file=sys.stderr)
            return 1
        print("aqe_glossary.md is current")
        return 0
    with open(OUT, "w") as f:
        f.write(text)
    print(f"wrote {os.path.relpath(OUT)} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
