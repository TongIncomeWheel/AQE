"""Stage Weather frozen spec — the four-stage market cycle, transcribed.

Source: Stan Weinstein, *Secrets for Profiting in Bull and Bear Markets*
(McGraw-Hill, 1988), ch. 2 "Stage Analysis" — the origin of the four-stage
model that the Schwab "Four Stages of Stock Market Cycles" explainer (PM
reference, 2026-11-10) summarises as accumulation / mark-up / distribution /
mark-down. Weinstein's operative tool is the 30-WEEK moving average read on a
WEEKLY chart: which side of it price is on, and which way it slopes.

Two prefixes, same discipline as src/valen/spec.py and src/engines/qs_spec.py:
  WS_*   transcribed from Weinstein (the 30-week MA, the 52-week Mansfield RS
         line, the cycle order 1->2->3->4->1).
  IMPL_* AQE's own measurement where the source gives a picture, not a number
         ("the MA flattens out", "price crisscrosses the MA"). Chosen once,
         documented, NEVER tuned to make a backtest look good. If one looks
         wrong, change it here with a PM sign-off and say why.

DO NOT TUNE ANYTHING HERE.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# The yardstick
# ---------------------------------------------------------------------------
WS_MA_WEEKS = 30                 # the 30-week simple moving average (~150 trading days)
WS_RS_MA_WEEKS = 52              # Mansfield relative-strength zero line: ratio vs its own 52-wk MA

# ---------------------------------------------------------------------------
# AQE's measurement of "rising / flat / falling" and of a stage change
# ---------------------------------------------------------------------------
# MA slope = % change of the 30-week MA over the last 4 completed weeks.
# |slope| < 0.5% is FLAT. Why 0.5: an index compounding ~10%/yr moves its
# 30-wk MA ~0.75% per 4 weeks, so a normal bull reads RISING; a genuinely
# flat base wobbles well inside half a percent.
IMPL_SLOPE_LOOKBACK_WEEKS = 4
IMPL_SLOPE_FLAT_PCT = 0.5

# A stage change is CONFIRMED only after the new reading holds this many
# consecutive COMPLETED weeks. One week is a warning (shown as `candidate`),
# two is a stage. Stops a single close across the MA from flipping the call.
IMPL_CONFIRM_WEEKS = 2

# Evidence windows (marks only — never inputs to the stage call).
IMPL_VOLUME_WINDOW_WEEKS = 10    # up-week vs down-week average volume
IMPL_RS_SLOPE_WEEKS = 4          # is the Mansfield RS line rising?
IMPL_RANGE_WEEKS = 52            # 52-week range position (also the cold-start seed)

# Minimum completed weekly bars before any stage is called. Below this the
# stage is NA, never a guess.
MIN_WEEKS = WS_MA_WEEKS + IMPL_SLOPE_LOOKBACK_WEEKS

# Universe breadth: change in a stage's share (percentage points) vs 4 weeks
# ago inside +/- this band reads STEADY.
IMPL_BREADTH_STEADY_PTS = 3.0
IMPL_BREADTH_LOOKBACK_WEEKS = 4

# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------
STAGES = (1, 2, 3, 4)
STAGE_NAME = {
    1: "Basing",
    2: "Advancing",
    3: "Topping",
    4: "Declining",
}
CYCLE_NAME = {                   # the market-cycle words (Wyckoff / Schwab)
    1: "Accumulation",
    2: "Mark-up",
    3: "Distribution",
    4: "Mark-down",
}
STAGE_PLAIN = {
    1: "basing after a fall: price chops around a flat 30-week average",
    2: "advancing: price above a rising 30-week average",
    3: "topping after a rise: the 30-week average has rolled flat and price is chopping around it",
    4: "declining: price below a falling 30-week average",
}

# The only legal confirmed transitions, in cycle order. A jump 2->4 (a crash
# straight through the MA) is allowed and recorded as such: markets do skip
# a visible top. 1->4 / 3->2 are a FAILED base / a resumed advance.
TRANSITION_LABEL = {
    (1, 2): "BREAKOUT",           # base -> advance
    (2, 3): "TOPPING",            # advance -> top
    (3, 4): "BREAKDOWN",          # top -> decline
    (4, 1): "BASING",             # decline -> base
    (3, 2): "ADVANCE_RESUMED",    # top resolved upward
    (1, 4): "BASE_FAILED",        # base resolved downward
    (2, 4): "BROKE_DOWN_FROM_ADVANCE",
    (4, 2): "V_REVERSAL",
}

MARKET_SYMBOLS = ("SPY", "QQQ")  # both on the panel every engine reads; SPY leads
BENCHMARK = "SPY"

POPULATION_PANEL = "aqe_panel_equities"   # every single-name ticker on panel_weekly
