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
# Simple percentage bands (PM ruling 2026-08-04). An earlier R-relative version
# was more consistent across tickers but harder to read, and a stop you cannot
# picture is not a stop you will act on.
NEAR_STOP_PCT = _f("AQE_ALERT_NEAR_STOP_PCT", 5.0)    # within X% ABOVE the stop / SL

# Plain movement notification — NOT an entry signal, NOT a decision level.
MOVE_PCT = _f("AQE_ALERT_MOVE_PCT", 2.0)              # +/- X% vs prior close

# Approaching the breakout level (last confirmed pivot high) from BELOW, and
# approaching the first target from below. Named for what they are; the old
# catch-all "AT_LEVEL" told you a level was near without saying which or why.
NEAR_BREAKOUT_PCT = _f("AQE_ALERT_NEAR_BREAKOUT_PCT", 2.0)
NEAR_TARGET_PCT = _f("AQE_ALERT_NEAR_TARGET_PCT", 2.0)

# Retired: BREAKOUT used to fire at +2%..+8% over the PRIOR CLOSE, a band with
# no relationship to the chart. On the 2026-08-04 export the +2% trigger sat
# BELOW real overhead resistance on 37 of 50 names and inside half an ATR for
# most — it fired on "a decent up day", not on clearing anything. Replaced by
# structure_shift == BULLISH_BOS (price closing above the last confirmed pivot
# high) plus the decision-level proximity above.
BREAKOUT_PCT = _f("AQE_ALERT_BREAKOUT_PCT", 2.0)      # legacy, unused
BREAKOUT_MAX_PCT = _f("AQE_ALERT_BREAKOUT_MAX_PCT", 8.0)  # legacy, unused

# COIL / THRUST / FAILED_PUSH: no switch, by design. The signature NEVER fires
# an email on its own — it is appended as a tag to a line that already earned
# its place (⟨Coiling⟩ after a BOS, say), and it is written to every ledger
# entry. Its thresholds are still starting assumptions rather than values
# fitted to real fires (see alerts/intraday.py), which is a reason to WATCH the
# tag accumulate, not to hide it.
#
# There WAS an EMAIL_INTRADAY_SIGNATURES flag here claiming these were
# ledger-only. Nothing read it, so the tag shipped in every email regardless —
# a config that described behaviour the code did not have. Removed rather than
# wired: wiring it would have stripped useful context out of the digest to
# honour a comment.

# Refuse to email off an export older than this many calendar days (stale levels).
MAX_EXPORT_AGE_DAYS = int(_f("AQE_ALERT_MAX_EXPORT_AGE_DAYS", 4))

# --- cadence ---
ALERT_MINUTES = int(_f("AQE_ALERT_MINUTES", 15))     # FMP Starter = 15-min delay

# US market session (Eastern) the alert poll is allowed to email in. Slightly
# padded so the 15-min-delayed last bar still lands inside the window.
MARKET_OPEN = (9, 45)    # 09:45 ET
MARKET_CLOSE = (16, 15)  # 16:15 ET
