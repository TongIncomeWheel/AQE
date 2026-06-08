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


# --- level tolerances (only Buy / Breakout / Approaching-stop are emailed) ---
NEAR_STOP_PCT = _f("AQE_ALERT_NEAR_STOP_PCT", 5.0)    # within X% ABOVE the stop
BREAKOUT_PCT = _f("AQE_ALERT_BREAKOUT_PCT", 2.0)      # breakout starts X% over entry
BREAKOUT_MAX_PCT = _f("AQE_ALERT_BREAKOUT_MAX_PCT", 8.0)  # …and only up to X% (fresh)

# Refuse to email off an export older than this many calendar days (stale levels).
MAX_EXPORT_AGE_DAYS = int(_f("AQE_ALERT_MAX_EXPORT_AGE_DAYS", 4))

# --- cadence ---
ALERT_MINUTES = int(_f("AQE_ALERT_MINUTES", 15))     # FMP Starter = 15-min delay

# US market session (Eastern) the alert poll is allowed to email in. Slightly
# padded so the 15-min-delayed last bar still lands inside the window.
MARKET_OPEN = (9, 45)    # 09:45 ET
MARKET_CLOSE = (16, 15)  # 16:15 ET
