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

# ── Universe theta scanner (the standalone, hosted, whole-universe sweep) ────
# Data comes from Alpaca's option-chain snapshot (free "indicative" feed: IV +
# greeks + quotes, one call per underlying — no per-contract fan-out, no throttle).
ALPACA_DATA_URL = "https://data.alpaca.markets"
ALPACA_FEED = "indicative"      # free, ~15-min delayed; "opra" needs the paid sub
ALPACA_KEY_ID_ENV = "ALPACA_API_KEY_ID"
ALPACA_SECRET_ENV = "ALPACA_API_SECRET_KEY"
ALPACA_SPOT_CHUNK = 100         # symbols per batched stock-snapshot call
ALPACA_TIMEOUT = 20             # per-request seconds
ALPACA_MAX_RPM = 180            # client-side pacing — stay under the free 200/min cap
ALPACA_MAX_RETRIES = 4          # retry 429 / 5xx with backoff (honours Retry-After)
# Only fetch OTM puts within this fraction below spot — bounds the chain server-side
# so liquid names don't page through the whole strike ladder (the delta-band filter
# downstream is the real gate; this just keeps the payload small).
ALPACA_MAX_OTM_FRAC = 0.5

# Liquidity is IMPLICIT (PM ruling): the AQE universe is already-liquid names, and
# we only sell ROUND strikes — multiples of $5 are naturally the deep-OI ones — so
# we never spend a call fetching open interest.
ROUND_STRIKE_STEP = 5.0         # keep only strikes that are a multiple of this

# Universe-sweep DTE window (the wheel's monthly sweet spot).
UNIVERSE_DTE_MIN = 20
UNIVERSE_DTE_MAX = 50
UNIVERSE_SCAN_FILE = "output/options_scan.json"   # local working copy of the sweep

# Dedicated Drive folder for the CSP scan (overwritten every run → always ONE
# file, like AQE's export folder). Override with env GDRIVE_CSP_FOLDER_ID.
GDRIVE_CSP_FOLDER_ID = "1HAh3Vw0sWASm5GccifPUP5_cZh31Z7oC"
CSP_SCAN_FILENAME = "options_scan.json"
