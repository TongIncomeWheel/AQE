"""VALEN frozen spec — every threshold transcribed from source, nothing tuned.

Sources, both read directly (not inferred): the VIV System handbook PDF
("21 Building Blocks to Profitability", v1.3, September 2026) and the web
edition at valensontrades.com/playbook, which states several thresholds the
PDF leaves implicit. Citations below reference the handbook's own piece
numbering ("No. NN/21") since that is stable across PDF/web/future versions;
raw PDF page numbers are not.

DO NOT TUNE ANYTHING HERE. If a number in this file looks wrong, the fix is
to re-read the source and correct the citation, not to adjust the number to
taste — same discipline as src/engines/qs_spec.py.

Two numbers are DELIBERATELY NOT here: the exact ATR-length/MA-type used by
VALEN's own Pine scripts for "ATR multiple from a moving average" and ADR%.
The handbook states the thresholds but not the formula. AQE_VALEN_DASHBOARD_
PROPOSAL.md §9.6 asks the PM to supply the published Pine source so these are
transcribed rather than guessed. Until then this module computes its own ATR
multiple from Wilder ATR(14) — already AQE's house formula
(src/data/drive_sync.py atr_14d) — against the SMA(50), and flags the result
`formula_basis="aqe_house"` rather than `"viv_pine"` so a reader always knows
which one produced a number.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# MARKET TREND — piece 01, "Check the market first"
# ---------------------------------------------------------------------------
# Daily buy signal: price above its 10-day AND 20-day line, 10 above 20.
# Weekly buy signal: the identical test on weekly bars.
# Regime: all three SPY rows yes -> UPTREND, all three no -> DOWNTREND,
# anything mixed -> CHOP ("chop is where breakouts get sold").
TREND_SMA_FAST = 10
TREND_SMA_SLOW = 20
TREND_WEEKLY_SMA_FAST = 10
TREND_WEEKLY_SMA_SLOW = 20
TREND_RISING_WINDOW = 5          # "above a rising 5-day line"

TREND_SYMBOLS = ("SPY", "QQQ")   # both checked; SPY drives the regime word

REGIME_UPTREND = "UPTREND"
REGIME_DOWNTREND = "DOWNTREND"
REGIME_CHOP = "CHOP"

# ---------------------------------------------------------------------------
# EXTENSION — piece 01, "Extension: how stretched the market is"
# ---------------------------------------------------------------------------
# Stocks above their 20-day line, three populations, each on its own track.
# "All stocks" and Nasdaq-100 share one band; the S&P is stricter.
EXT_PCT_ABOVE_20D_LOW_DEFAULT = 25.0
EXT_PCT_ABOVE_20D_HIGH_DEFAULT = 80.0
EXT_PCT_ABOVE_20D_LOW_SP500 = 30.0
EXT_PCT_ABOVE_20D_HIGH_SP500 = 75.0

# VIX / VIX3M (the handbook calls VIX3M "VXV" throughout; same instrument).
# Above 1.00 = uncertainty, bad for stocks. Below 0.82 = calm, good for stocks.
VIX_VIX3M_UNCERTAINTY_ABOVE = 1.00
VIX_VIX3M_CALM_BELOW = 0.82

# SPY/QQQ ATR multiple from the 50-day line. ~6 is as stretched as an INDEX
# gets — a basket never stretches as far as a single stock (single-stock
# bands are PER_STOCK_ATR_MULT_* below, roughly double this).
INDEX_ATR_MULT_STRETCHED = 6.0

# NAAIM managers' exposure. 0 = all cash, 100 = fully invested. Reported
# weekly (Wednesdays) — carries its OWN as_of date, never backfilled to the
# daily run's date. Colours only at the extremes; this module does not gate
# on it, only displays it (optional leg per proposal §9.2).
NAAIM_SCALE_MIN = 0
NAAIM_SCALE_MAX = 100

# ---------------------------------------------------------------------------
# THE SIX-ROW CHECKLIST — piece 01. More yes = more size (a PM/AIC call
# downstream, never computed here). The Net High Net Low row ALONE governs
# how OPEN trades are managed, independent of the other five.
# ---------------------------------------------------------------------------
CHECKLIST_NHNL_FAST = 8          # 8-day average of Net High Net Low
CHECKLIST_NHNL_SLOW = 20         # ... above the 20-day average = green
CHECKLIST_5D_COUNT_MIN = 1.00    # 5-day up4%/down4% count >= this = green
CHECKLIST_MOVER_PCT = 4.0        # "today's count" mover threshold
CHECKLIST_MONTH_MOVER_PCT = 25.0
CHECKLIST_QUARTER_MOVER_PCT = 25.0
CHECKLIST_LAST_N_TRADES = 5      # "my last five closed trades net positive"

# ---------------------------------------------------------------------------
# THE FOUR INSTRUMENTS — piece 01. Whole-market breadth; REQUIRES a
# market-wide population (NOT the curated AQE universe — see
# AQE_VALEN_DASHBOARD_PROPOSAL.md §2.2 for why). Every value this module
# emits under these names MUST carry `population` + `n`.
# ---------------------------------------------------------------------------
MOVER_UP_PCT = 4.0
MOVER_DOWN_PCT = 4.0
MOVER_COUNT_WINDOWS = (5, 10)         # 5-day and 10-day summed counts
MOVER_RATIO_SELLERS_BELOW = 0.50
MOVER_RATIO_BUYERS_ABOVE = 2.00

T2108_MA_WINDOW = 40                  # "share of ALL stocks above their own 40-day"
T2108_WASHED_OUT_BELOW = 20.0
T2108_OVERHEATED_ABOVE = 80.0

NET_HIGH_LOW_LOOKBACK_WEEKS = 52
NET_HIGH_LOW_FAST = 8
NET_HIGH_LOW_SLOW = 20

BIG_MOVER_MONTH_PCT = 25.0
BIG_MOVER_QUARTER_PCT = 25.0

# ---------------------------------------------------------------------------
# STANCE FLIP RULES — piece 01, "What would change it" + web edition.
# Each is shown on the card with TODAY'S VALUE beside it (crown/levels.py
# key_levels shape — what/now/level/distance_pct/if_it_breaks).
# ---------------------------------------------------------------------------
STANCE_TO_POSITIVE_PCT_ABOVE_40D = 50.0     # T2108-style, must clear this
STANCE_TO_POSITIVE_MONTHLY_RISERS = 350     # ABSOLUTE COUNT — full-tape only,
                                             # see proposal §2.2. Unreachable
                                             # on AQE's 819-ticker panel.
STANCE_TO_POSITIVE_5D_COUNT = 1.00
STANCE_TO_NEGATIVE_5D_COUNT = 0.70
# "Trade management changes when the 8-day average of net new highs crosses
# back above the 20-day" — same NH-NL series as the checklist row, read as
# an EVENT (a fresh cross) rather than a level.
TRADE_MGMT_NHNL_CROSS_FAST = CHECKLIST_NHNL_FAST
TRADE_MGMT_NHNL_CROSS_SLOW = CHECKLIST_NHNL_SLOW

STANCE_RISK_ON = "RISK_ON"
STANCE_NEUTRAL = "NEUTRAL"
STANCE_RISK_OFF = "RISK_OFF"

# ---------------------------------------------------------------------------
# ROTATION — piece 03. "Leading" vs "a bounce dressed up as leadership" is
# the single distinction the handbook is most insistent on getting right.
# ---------------------------------------------------------------------------
ROTATION_LEADING_MAX_OFF_HIGH_PCT = 5.0     # "within a few percent of highs"
ROTATION_OFF_FLOOR_MIN_OFF_HIGH_PCT = 15.0  # "15 to 25 percent below highs"
ROTATION_OFF_FLOOR_MAX_OFF_HIGH_PCT = 25.0

ROTATION_LEADING = "LEADING"
ROTATION_OFF_FLOOR = "OFF_THE_FLOOR"
ROTATION_NEITHER = "NEITHER"

# Theme Leaders — three rankings run at once (piece 02 + web edition).
THEME_LEADER_WINDOWS = ("since_open", "1_week", "1_month")
# Piece 02, "How I read it": "I track how every group performed over the
# past week and the past month, and I mark the top five on each list. A
# stock whose group is on those lists is in-theme."
THEME_TOP_N = 5

# ---------------------------------------------------------------------------
# PER-STOCK EXTENSION (piece 17 / appendix "ATR% Multiple From MA") — for the
# no-buy list (Phase 3), not the market card. Index bands above are roughly
# HALF these, "because a basket of stocks never stretches as far as one."
# ---------------------------------------------------------------------------
PER_STOCK_ATR_MULT_LAUNCHPAD_BELOW = 4.0
PER_STOCK_ATR_MULT_NO_ADDS_AROUND = 5.0
PER_STOCK_ATR_MULT_RARE_AIR_LOW = 7.5
PER_STOCK_ATR_MULT_RARE_AIR_HIGH = 8.0
PER_STOCK_ATR_MULT_TRIM_AROUND = 10.0

# ---------------------------------------------------------------------------
# Universe / population labels — every breadth-shaped field must name one.
# "curated" is what AQE's own panel covers; it is NEVER a valid population
# for a field named after a VALEN whole-market instrument (t2108, mover
# counts, net_high_low) — those require "us_wide" or the field is UNAVAILABLE.
# ---------------------------------------------------------------------------
POPULATION_CURATED = "aqe_curated_universe"      # ~493-819 names, see universe.py
POPULATION_US_WIDE = "us_nasdaq_nyse_mcap_gt_2b"  # ma_scanner.get_ma_universe()

FORMULA_BASIS_VIV_PINE = "viv_pine"      # transcribed from the published script
FORMULA_BASIS_AQE_HOUSE = "aqe_house"    # AQE's own formula, same INTENT

# ---------------------------------------------------------------------------
# Parts 2-4 (pieces 04-16) — 2026-09-30. Everything here reads fields AQE's
# own engines already stamp onto daily_list/held_positions; no new scoring.
# PER_STOCK_ATR_MULT_LAUNCHPAD_BELOW above already anticipates the no-buy
# list's "stretched" test, reused as-is. This block adds the one genuinely
# new threshold: how close to earnings counts as "too close to buy."
# ---------------------------------------------------------------------------
NO_BUY_EARNINGS_WITHIN_SESSIONS = 5     # piece 07: "earnings within 5 sessions"

# ---------------------------------------------------------------------------
# PART 3 — HOUSE: the five setups, MEASURED (2026-10-05, PM sign-off on
# docs/AQE_VALEN_HOUSE_SETUPS_PROPOSAL.md: retire the DETECT-field proxies,
# high tight flag only for piece 09, piece 12 long-only, earnings-day EP).
# Two kinds of constant, kept visibly apart:
#   HB_*   transcribed from the handbook, page cited. Never tuned.
#   IMPL_* AQE's own measurement choice where the handbook gives a picture,
#          not a number ("clean and steady", "obvious on sight"). Each one
#          says what words it measures. Changing one is a PM call.
# ---------------------------------------------------------------------------
# Shared (pieces 08/09/10): the 4% expansion day, p.31 Stage 3.
HB_EXPANSION_MIN_PCT = 4.0             # "a day that expands 4% or more"
HB_EXPANSION_BIGGER_THAN_BARS = 5      # "visibly bigger than the last five to ten"
HB_EXPANSION_CLOSE_TOP_FRAC = 0.30     # "closing in the top 30% of its range"
HB_MAX_UP_DAYS_INTO_TRIGGER = 2        # "no more than two up-days into it"
HB_MAX_YOUNG_BASE = 3                  # "the first, second or third base" (p.31, p.35)

# 08 VCP, p.31.
HB_VCP_MIN_RUN_PCT = 30.0              # "a real run of 30% or more into the base"
HB_VCP_LAST_PULLBACK_MAX_PCT = 10.0    # "the last pullback is tight -- 10% deep or less"
IMPL_VCP_SHRINK_RATIO = 0.75           # "each pullback clearly shallower" (handbook
                                       # example halves: 25/12/6) -- each <= 75% of prior
IMPL_VCP_BASE_LOOKBACK = 120           # bars searched for the base's high
IMPL_VCP_RUN_LOOKBACK = 120            # bars searched for the run's origin
IMPL_VCP_MIN_BASE_BARS = 10            # a base needs at least two weeks to exist
IMPL_VCP_ZIGZAG_PCT = 2.5              # smallest swing counted as a pullback
IMPL_RUN_CLEAN_R2 = 0.70               # "clean and steady, not a zig-zag": R^2 of
                                       # log-close vs time across the run

# 09 high tight flag, p.33. (PM 2026-10-05: HTF only, no looser breakout.)
HB_HTF_POLE_MIN_PCT = 90.0             # "roughly a double, 90 to 100% or more"
HB_HTF_POLE_MAX_BARS = 40              # "in eight weeks or less"
HB_HTF_FLAG_IDEAL_MAX_PCT = 20.0       # "no more than 20 to 25% off the pole high"
HB_HTF_FLAG_MAX_PCT = 25.0
HB_HTF_FLAG_MIN_BARS = 15              # "three to five weeks"
HB_HTF_FLAG_IDEAL_MAX_BARS = 25
HB_HTF_FLAG_MAX_BARS = 40              # "not stretching much past eight"
HB_HTF_MAX_FLAG_NUMBER = 2             # "the first or second flag of the run"
IMPL_HTF_POLE_MIN_BARS = 10            # "near-vertical ... is a blow-off": under two
                                       # weeks of climb is not a 45-degree pole
IMPL_HTF_SPIKE_MAX_SHARE = 0.35        # "one big spike day is not a pole": no single
                                       # day carries > 35% of the pole's log gain
IMPL_HTF_POLE_R2 = 0.80                # "a steady staircase": R^2 of the climb

# 10 Undercut and rally, p.35.
IMPL_UNR_WINDOW = 10                   # undercut must be within the last 10 sessions
IMPL_UNR_SUPPORT_LOOKBACK = 40         # prior low searched 40 sessions back
IMPL_UNR_PIVOT_SIDE = 3                # a swing low = lowest of 3 bars either side
IMPL_UNR_MIN_UNDERCUT_ATR = 0.25       # "a REAL dip below": at least a quarter of a
                                       # daily range under the prior low, not a poke
HB_UNR_STOP_MAX_ATR = 1.0              # "stop at the pullback low, under one daily range"
IMPL_PULLBACK_ZIGZAG_PCT = 5.0         # a pullback counted for "1st/2nd/3rd pullback"
IMPL_UNR_RS_RANK_MIN = 70.0            # "relative strength still holding"

# 11 Episodic pivot, p.37.
HB_EP_GAP_MIN_PCT = 10.0               # "opens 10% or more above yesterday's close"
HB_EP_EARNINGS_EXPANSION_PCT = 4.0     # "or a 4%-plus expansion on an earnings day"
HB_EP_VOLUME_MULT = 3.0                # "at least three times normal by the close"
HB_EP_STOP_MAX_ATR = 1.5               # "within about one to one-and-a-half daily ranges"
IMPL_EP_WINDOW = 10                    # gap day searched in the last 10 sessions
                                       # (day one + the Delayed EP's pause)
IMPL_EP_NEGLECT_BARS = 63              # "flat or basing for months": 3 months before
IMPL_EP_NEGLECT_MAX_RUN_PCT = 25.0     # "no big run behind it"
IMPL_EP_FALLING_KNIFE_PCT = -25.0      # "not out of a falling knife"
IMPL_EP_FIRST_GAP_LOOKBACK = 126       # "no recent gap of this kind": 6 months
IMPL_EP_OVERHEAD_PCT = 15.0            # "clear air overhead": no prior 1-yr high
                                       # within 15% above the close

# 12 Parabolic / breakdown, p.39 -- LONG-ONLY RISK WARNINGS (PM 2026-10-05),
# never a short signal.
HB_PARA_MIN_RUN_PCT = 50.0             # "50 to 100% on a big stock" (universe >= $2B)
IMPL_PARA_RUN_BARS = 20                # "in days to weeks"
HB_PARA_MIN_UP_STREAK = 3              # "three to five or more up days in a row"
IMPL_PARA_FAR_ATR_MULT = PER_STOCK_ATR_MULT_RARE_AIR_LOW  # "visibly far above" =
                                       # the handbook's own rare-air band (piece 17)
IMPL_FL_RED_DAY_PCT = -3.0             # "big red high-volume days"
IMPL_FL_RED_DAY_VOL_MULT = 1.5
IMPL_FL_RED_DAYS_MIN = 2
IMPL_FL_LOOKBACK = 30
HB_FL_NO_RECOVERY_SESSIONS = 5         # "50-day lost with no recovery within a few sessions"
IMPL_FL_DOWN_ON_UP_FRAC = 0.5          # "goes down on days the market goes up"
HB_FL_SUPPORT_TESTS = 3                # "three or more tests of the same support"
IMPL_FL_SUPPORT_BAND_PCT = 3.0
IMPL_FL_MIN_CHECKS = 3                 # of the five failed-leader signs

# ---------------------------------------------------------------------------
# GEX Traffic Light — 2026-09-30. A Weather companion instrument, piece 01.
# Frozen exactly as specified (GEX_traffic_light.md), never re-derived.
# Reuses Crown Macro's own real gamma computation (src/macro/crown/gamma.py:
# flip/call-wall/put-wall from real options-chain open interest) — this
# module adds no new data pull, only the traffic-light rule and the read.
# GEX_TICKER is SPY: one of the spec's own three named underlyings
# (SPX/SPY/QQQ), and already Crown's own "primary" index-level proxy
# (gamma.py's analyse()) since Crown has no SPX chain fetch at all.
# ---------------------------------------------------------------------------
GEX_TICKER = "SPY"
GEX_AMBER_ABOVE_FLIP_PCT = 1.0     # rule 3: within 1% above the flip
GEX_AMBER_NEAR_CALL_WALL_PCT = 0.5  # rule 4: within 0.5% of the call wall
