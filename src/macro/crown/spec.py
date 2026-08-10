"""Crown Institutional Process — every frozen constant, cited to the kernel.

Source: `Crown_Institutional_Process_Kernel_v1.4.md`. Section numbers below are
that document's. Where the kernel gives a number in code (§5) the value here is
a **transcription** — if it disagrees with the doc, the doc is right and this
file is a bug. Where the kernel gives only prose (§2.3, §2.4), the constant is
marked DERIVED and the reasoning is stated, because a reader must be able to
tell a transcribed number from one we chose.

This layer is deliberately standalone. It does NOT read SRM, Macro Weather or
the Thematic RRG, and nothing in it feeds them. Merge/dedup is a later decision
(PM directive, 2026-08-09) — building it separately first is what makes the
overlap measurable instead of assumed.
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════
# §2.2 / §5 — Heartbeat (RSP / SPY)
# ═══════════════════════════════════════════════════════════════════════

HEARTBEAT_NUM = "RSP"          # equal-weight S&P 500
HEARTBEAT_DEN = "SPY"          # cap-weighted S&P 500

HB_LOOKBACK_DAYS = 252         # §5 heartbeat_regime lookback_days
HB_SLOPE_WINDOW = 20           # §5 history[-20:]
HB_MIN_HISTORY = 20            # §5 len(history) < 20 -> neutral
HB_SLOPE_EPS = 0.00015         # §5 slope threshold, ratio units per day
HB_RANGE_TOP = 0.75            # §5 range_pct > 0.75 -> "top"
HB_RANGE_BOTTOM = 0.25         # §5 range_pct < 0.25 -> "bottom"

# §5 confidence ladder, transcribed exactly.
HB_CONF_EXTREME = 0.75         # regime + matching range extreme (tired/exhausted)
HB_CONF_TRENDING = 0.65        # regime with no range extreme
HB_CONF_NEUTRAL = 0.45         # no slope
HB_CONF_NO_HISTORY = 0.30      # < 20 observations

# §5 route_after_heartbeat — below this the process STOPS. This is the
# centre of gravity: no positioning work is done on a market we can't read.
HB_CONFIDENCE_GATE = 0.40


# ═══════════════════════════════════════════════════════════════════════
# §2.3 / §5 — CTA flow
# ═══════════════════════════════════════════════════════════════════════

CTA_FLIP_THRESHOLD = 0.75      # §5 |signal| >= 0.75 counts as an extreme
CTA_BIAS_EPS = 0.25            # §5 avg > 0.25 risk_on / < -0.25 risk_off
CTA_FLIP_RISK_HI = 0.40        # §5 flip_risk > 0.4 -> size 0.60
CTA_FLIP_RISK_LO = 0.20        # §5 flip_risk < 0.2 + directional -> size 1.15
CTA_SIZE_CROWDED = 0.60        # §5
CTA_SIZE_CLEAN_TREND = 1.15    # §5
CTA_SIZE_NEUTRAL = 1.00        # §5
CHECKLIST_FLIP_PENALTY_AT = 0.45   # §5 node_checklist: flip_risk > 0.45 ...
CHECKLIST_FLIP_PENALTY = 0.70      # §5 ... -> size_mult *= 0.7

# DERIVED (§2.3 names CTAs as "systematic trend-followers" but gives no model).
# The public literature the kernel points at:
#   Moskowitz-Ooi-Pedersen (2012) time-series momentum — 12-month lookback,
#   vol-scaled to a constant target.
#   Faber (2007) GTAA — price vs the 10-month SMA (~200 sessions).
# The industry-standard proxy blends short/medium/long lookbacks equally.
CTA_LOOKBACKS = (42, 126, 252)     # ~2, 6, 12 months in sessions
CTA_FABER_SMA = 200                # ~10 months
CTA_VOL_WINDOW = 60                # sessions for realised vol
CTA_VOL_TARGET = 0.10              # 10% annualised, the standard managed-futures target
CTA_MAX_LEVERAGE = 2.0             # cap on target_vol / realised_vol
CTA_MIN_HISTORY = 260              # need the longest lookback + a vol window
CTA_FLIP_HORIZONS = (1, 5, 20)     # sessions ahead to solve flip levels for
TRADING_DAYS = 252


# ═══════════════════════════════════════════════════════════════════════
# §2.4 — VIX structure
# ═══════════════════════════════════════════════════════════════════════

# FMP symbols. These are now only a FALLBACK: Cboe computes every one of these
# indices and publishes the full history free (see cboe.py), so the primary
# source is the publisher. `^VIX` works on our Starter plan; `^VIXEQ`, `^VIX3M`
# and `^VIX9D` do NOT (probed 2026-08-09) — which is exactly why going to Cboe
# matters rather than being a nicety.
VIX_SYMBOL = "^VIX"
VIXEQ_SYMBOL = "^VIXEQ"        # Cboe S&P 500 Constituent Volatility Index
VIX3M_SYMBOL = "^VIX3M"
VIX9D_SYMBOL = "^VIX9D"

# DERIVED. §2.4 gives the tool (VIXEQ - VIX) and its meaning but no cut points.
# These are PERCENTILE bands over the trailing window, not absolute vol points,
# because the spread's level drifts with the vol regime and a fixed number would
# read as "elevated" for a year at a time.
DISPERSION_WINDOW = 504        # 2 years of percentile history
DISPERSION_ELEVATED_PCTL = 0.80    # §2.4 "elevated spread has predicted 5-7% drawdowns"
DISPERSION_CALM_PCTL = 0.20

# §2.4's PRACTICAL rule is directional — "Rising VIXEQ-VIX spread -> hidden
# stress" — while the narrative cites an ELEVATED spread ahead of drawdowns.
# Those are not the same state, and on 2026-08-07 they disagreed: the spread sat
# at the 98th percentile of its whole history while having fallen 9.2 points in
# twenty sessions. So level and direction are reported separately, and the
# tactical flag needs both — you want to be buying downside as stress BUILDS,
# not as it unwinds.
DISPERSION_RISE_WINDOW = 20        # sessions
DISPERSION_RISE_EPS = 0.5          # vol points; below this the move is noise
VIX_VERY_LOW = 15.0            # §2.4 / §3 Example 5 "very low VIX"
VIX_ELEVATED = 25.0            # §2.4 "already priced" — not a fresh sell signal

# The realised-dispersion fallback when ^VIXEQ is unavailable. This measures the
# SAME phenomenon (single-stock vol rising while the index stays calm) from bars
# we already hold, but it is REALISED, not implied — it lags, and it carries no
# forward-looking premium. It is named differently everywhere so the two can
# never be mistaken for each other on a card.
DISP_REALISED_WINDOW = 30      # sessions of realised vol
DISP_MIN_CONSTITUENTS = 50     # below this the cross-sectional average is noise


# ═══════════════════════════════════════════════════════════════════════
# §2.3 — Gamma
# ═══════════════════════════════════════════════════════════════════════

GAMMA_UNDERLYINGS = ("SPY", "QQQ")   # §2.4 "VIX sits ... alongside ES"; index-level
GAMMA_DTE_MAX = 45             # DERIVED — beyond ~6wks dealer gamma is negligible
GAMMA_DTE_MIN = 0              # §2.3 "0DTE creates extreme short-term gamma"
GAMMA_STRIKE_BAND = 0.15       # DERIVED — ±15% of spot; outside it OI is vestigial
GAMMA_CONTRACT_MULTIPLIER = 100
GAMMA_WALL_MIN_SHARE = 0.03    # DERIVED — absolute floor: <3% of a side is noise
# DERIVED. A share threshold alone cannot tell a wall from an evenly-spread
# ladder: with 30 strikes an even chain gives every strike 3.3%, which would
# clear any fixed floor and name an arbitrary strike "the wall". A wall is a
# strike carrying materially MORE than its even share, so the test is relative
# to the ladder's own width and the fixed floor is only the backstop.
GAMMA_WALL_DOMINANCE = 2.5     # x the even share (1 / number of strikes)


# ═══════════════════════════════════════════════════════════════════════
# §2.5 — Divergence
# ═══════════════════════════════════════════════════════════════════════

DIV_RSI_PERIOD = 14
DIV_PIVOT_K = 5                # matches AQE's single pivot definition (patterns.py)
# Sessions searched for the prior comparable pivot. 120 (~6 months), not 60: a
# quarter frequently contains only ONE confirmed swing high at index level, and a
# divergence needs two. A window too short doesn't report "no divergence" — it
# reports "no second pivot", and those read identically downstream.
DIV_LOOKBACK = 120
DIV_MIN_SEPARATION = 5         # two pivots closer than this are one turn
# §2.5 "Cross-asset / Intermarket": equities making new highs while copper or
# breadth fails to confirm.
DIV_CONFIRMERS = ("HG", "RSP")     # copper (growth) + equal-weight (breadth)
DIV_NEW_HIGH_WINDOW = 60
# §2.5 "Positioning vs Price": price rising while COT large-spec is extreme.
DIV_COT_EXTREME_PCTL = 0.85


# ═══════════════════════════════════════════════════════════════════════
# §2.1 — the hierarchy itself, as data
# ═══════════════════════════════════════════════════════════════════════

HIERARCHY = (
    "heartbeat",       # 1. What kind of market is this?
    "positioning",     # 2. Who is positioned and how crowded? (COT + Gamma + CTA)
    "volatility",      # 3. What is the true volatility & risk regime?
    "divergence",      # 4. Where is momentum diverging from price?
    "expression",      # 5. Only then -> concrete trade expression
)

# §3 — the five expression families. The regime dictates the ALLOWED family;
# the individual setup is chosen afterwards and is NOT this layer's job.
EXPRESSION_FAMILIES = {
    "BROADENING_CARRY": {
        "context": "Heartbeat rising, range not extreme, gamma positive, dispersion normal.",
        "equity": "Long RSP or equal-weight financials / healthcare basket",
        "pair": "Long equal-weight sector / short the matching mega-cap",
        "options": "Bull call verticals, or long stock + short OTM calls (carry)",
    },
    "NARROWING_CONCENTRATED": {
        "context": "Heartbeat falling, leaders dominant, CTA elevated long, gamma negative.",
        "equity": "Concentrated long AI hardware / physical bottleneck names",
        "pair": "Long bottleneck tilt (memory, power, foundry) vs broad software",
        "options": "Call debit spreads, or long gamma if acceleration expected",
    },
    "HIDDEN_STRESS_DOWNSIDE": {
        "context": "Index calm, single-stock vol rising, dispersion elevated.",
        "equity": "Reduce gross; this is a tactical, time-sensitive expression",
        "pair": "n/a",
        "options": "Cheap downside in QQQ or ES — put debit spreads or long puts",
    },
    "DIVERGENCE_PAIR_SHORT": {
        "context": "Leaders at new highs, RSI not confirming, CTA extreme.",
        "equity": "Short the diverging leader / long equal-weight or defensives",
        "pair": "Short leader vs long equal-weight",
        "options": "Bear put vertical on the leader or on QQQ",
    },
    "MEAN_REVERSION_PREMIUM": {
        "context": "Positive gamma, very low VIX, broadening. Mean-reversion.",
        "equity": "Fade extremes toward the gamma walls",
        "pair": "n/a",
        "options": "Iron condors, credit spreads, covered calls. Avoid breakouts.",
    },
    "NONE": {
        "context": "Heartbeat confidence below the gate — the process stopped.",
        "equity": "No new risk", "pair": "n/a", "options": "n/a",
    },
}

# §3 Example 3 — the sizing note attached to the hidden-stress expression.
HIDDEN_STRESS_SIZE = 0.50      # DERIVED from "size reduced because tactical"
# §3 Example 4 — "overall size cut 30-40% because flip risk is elevated".
DIVERGENCE_PAIR_SIZE = 0.65

# AQE never sizes. This multiplier is a MULTIPLIER on the PM's own risk budget,
# published as a number for the committee to apply — not a dollar amount and not
# a share count. (CLAUDE.md: "AQE makes no decisions, no sizing.")
SIZE_MULT_FLOOR = 0.0
SIZE_MULT_CAP = 1.15           # §5 never exceeds CTA_SIZE_CLEAN_TREND
