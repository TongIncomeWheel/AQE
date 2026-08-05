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


# --- level tolerances ------------------------------------------------------
# NEAR_STOP is R-RELATIVE, not a flat percentage. Measured on the 2026-08-04
# export, a flat 5% band spanned 0.4 to 3.3 ATRs and 0.4 to 2.5 R across the
# universe — the same alert meant something different on every ticker. 0.25R
# means the same thing everywhere.
NEAR_STOP_R = _f("AQE_ALERT_NEAR_STOP_R", 0.25)       # within X of 1R above the stop
NEAR_STOP_PCT = _f("AQE_ALERT_NEAR_STOP_PCT", 5.0)    # fallback when risk is unknown

# Plain movement notification — NOT an entry signal, NOT a decision level.
MOVE_PCT = _f("AQE_ALERT_MOVE_PCT", 2.0)              # +/- X% vs prior close

# Proximity to a DECISION level (bracket stop, TP1, last confirmed pivot high).
# Deliberately NOT every structural level: within 2% of any of the ~15 levels a
# row carries catches 72% of the universe, which is wallpaper. Restricted to
# these three it was 2 of 83 on the same data.
NEAR_LEVEL_PCT = _f("AQE_ALERT_NEAR_LEVEL_PCT", 2.0)

# Retired: BREAKOUT used to fire at +2%..+8% over the PRIOR CLOSE, a band with
# no relationship to the chart. On the 2026-08-04 export the +2% trigger sat
# BELOW real overhead resistance on 37 of 50 names and inside half an ATR for
# most — it fired on "a decent up day", not on clearing anything. Replaced by
# structure_shift == BULLISH_BOS (price closing above the last confirmed pivot
# high) plus the decision-level proximity above.
BREAKOUT_PCT = _f("AQE_ALERT_BREAKOUT_PCT", 2.0)      # legacy, unused
BREAKOUT_MAX_PCT = _f("AQE_ALERT_BREAKOUT_MAX_PCT", 8.0)  # legacy, unused

# COIL / THRUST are computed and LEDGERED but not emailed until their
# thresholds are set from real fires rather than from the sqrt(t) and
# linear-volume assumptions in alerts/intraday.py.
EMAIL_INTRADAY_SIGNATURES = os.environ.get(
    "AQE_ALERT_EMAIL_INTRADAY", "0") == "1"

# Refuse to email off an export older than this many calendar days (stale levels).
MAX_EXPORT_AGE_DAYS = int(_f("AQE_ALERT_MAX_EXPORT_AGE_DAYS", 4))

# --- cadence ---
ALERT_MINUTES = int(_f("AQE_ALERT_MINUTES", 15))     # FMP Starter = 15-min delay

# US market session (Eastern) the alert poll is allowed to email in. Slightly
# padded so the 15-min-delayed last bar still lands inside the window.
MARKET_OPEN = (9, 45)    # 09:45 ET
MARKET_CLOSE = (16, 15)  # 16:15 ET
