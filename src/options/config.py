"""Tunable constants for the AQE Options scanner + calculator.

All knobs live here so the PM can tune them to the wheel charter. Overridable per
call — these are defaults. Pure data; no I/O.
"""

from __future__ import annotations

# ── Pricing assumptions (Black-Scholes inputs the chain doesn't carry) ──────
RISK_FREE_RATE = 0.043    # annualised risk-free (~3-month T-bill); override per run
DIVIDEND_YIELD = 0.0      # continuous div yield of the underlying; pass per name
YEAR_DAYS = 365.0         # calendar-day basis for time-to-expiry + annualising

# ── Capital / sizing (charter: $70K base, 3% risk = $2,100 per FULL trade) ──
CAPITAL = 70_000.0
RISK_BUDGET = 2_100.0     # defined-risk budget per position (put credit spreads)
MAX_POSITIONS = 6         # cash-secured collateral is split across at most 6 slots

# ── CSP theta-scanner filters (the income-wheel entry screen) ───────────────
# Short-put delta band — the wheel's sweet spot (moderate assignment odds).
CSP_DELTA_MIN = 0.15      # |delta| floor (too far OTM → thin premium)
CSP_DELTA_MAX = 0.35      # |delta| ceiling (too close → high assignment risk)
CSP_DTE_MIN = 7           # min days to expiry (avoid gamma/pin week unless wanted)
CSP_DTE_MAX = 60          # max days to expiry (theta/day decays past ~45 DTE)
CSP_MIN_POP = 0.65        # min prob the put expires worthless (not assigned)
CSP_MIN_ANNUAL_YIELD = 0.15   # min annualised return on collateral to surface
CSP_MIN_OI = 100          # liquidity floor (open interest)
CSP_MAX_SPREAD_PCT = 0.15     # max (ask-bid)/mid — reject wide, untradeable quotes

# ── Put-credit-spread filters (defined-risk variant of the wheel entry) ─────
SPREAD_MIN_RRR = 0.25     # min max_profit/max_loss (reward:risk) to surface
SPREAD_DEFAULT_WIDTH = 5.0    # default strike width when auto-pairing legs

# ── Ranking ─────────────────────────────────────────────────────────────────
# The theta scanner's primary sort key. "annual_yield" = return-on-collateral
# annualised; "theta_efficiency" = daily theta credit per $ of collateral.
SCAN_RANK_KEY = "annual_yield"
