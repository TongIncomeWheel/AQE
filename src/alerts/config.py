"""Tunable thresholds + cadence for the live alert engine.

All overridable via env / HF secrets so the PM can adjust sensitivity without a
redeploy. Defaults are deliberately conservative to avoid alert spam.
"""

from __future__ import annotations

import os


def _f(env: str, default: float) -> float:
    try:
        return float(os.environ.get(env, default))
    except (TypeError, ValueError):
        return default


# --- level tolerances ---
NEAR_STOP_PCT = _f("AQE_ALERT_NEAR_STOP_PCT", 5.0)   # within X% ABOVE the stop
BREAKOUT_PCT = _f("AQE_ALERT_BREAKOUT_PCT", 2.0)     # X% ABOVE the scan entry
MA_TOL_PCT = _f("AQE_ALERT_MA_TOL_PCT", 0.5)         # within X% of any MA
FIB_TOL_PCT = _f("AQE_ALERT_FIB_TOL_PCT", 1.0)       # within X% of a fib level
RVOL_SPIKE = _f("AQE_ALERT_RVOL_SPIKE", 2.0)         # volume / avgVolume >=

# Fibonacci retracements treated as "support" worth flagging.
FIB_KEYS = ("0.382", "0.5", "0.618")
# Moving averages in the support ladder.
MA_WINDOWS = (20, 50, 100, 200)

# --- cadence ---
ALERT_MINUTES = int(_f("AQE_ALERT_MINUTES", 15))     # FMP Starter = 15-min delay

# US market session (Eastern) the alert poll is allowed to email in. Slightly
# padded so the 15-min-delayed last bar still lands inside the window.
MARKET_OPEN = (9, 45)    # 09:45 ET
MARKET_CLOSE = (16, 15)  # 16:15 ET
