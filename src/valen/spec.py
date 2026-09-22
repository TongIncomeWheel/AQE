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
POPULATION_US_WIDE = "us_nasdaq_nyse_mcap_gt_1b"  # ma_scanner.get_ma_universe()

FORMULA_BASIS_VIV_PINE = "viv_pine"      # transcribed from the published script
FORMULA_BASIS_AQE_HOUSE = "aqe_house"    # AQE's own formula, same INTENT
