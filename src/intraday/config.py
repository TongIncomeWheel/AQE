"""Tunable constants for the Intraday Momentum & Bracket (IMB) layer.

This layer is a SEPARATE execution-prep system (recommend-only) that consumes
AQE's EOD export + live intraday bars. It does NOT change the AQE scanner export.
All thresholds live here so the PM can tune them to the charter.
"""

from __future__ import annotations

# ── Session / bar structure ────────────────────────────────────────────────
OR_MINUTES = 30           # opening-range window (first N minutes of the session)
SESSION_OPEN = (9, 30)    # US cash open (ET); bars are timestamped in ET
RVOL_LOOKBACK_DAYS = 10   # prior days used for volume-pace baseline
ATR_BARS = 14             # intraday ATR lookback (in 5-min bars)
ACCEL_LOOKBACK = 6        # bars for the momentum-acceleration slope (~30 min)
EMA_PERIOD = 9            # intraday fast EMA for trend quality

# ── Momentum-state thresholds ──────────────────────────────────────────────
EXTENDED_R = 1.0          # R's past the AQE entry → "extended" (don't chase)
EXTENDED_VWAP_ATR = 2.0   # price this many intraday-ATR above VWAP → extended
VWAP_NEAR_ATR = 0.5       # within this many intraday-ATR of VWAP → "at VWAP"
RVOL_STRONG = 1.3         # volume-pace ≥ this → genuinely elevated participation

# ── IMS (Intraday Momentum Score) component weights (sum need not be 1) ─────
IMS_WEIGHTS = {
    "vwap": 0.25,         # position vs session VWAP
    "slope": 0.15,        # VWAP rising/falling
    "or": 0.15,           # opening-range break
    "rvol": 0.20,         # cumulative volume pace by time-of-day
    "accel": 0.15,        # slope of recent closes
    "trend": 0.10,        # higher-lows / EMA alignment
}

# ── Operative-stop gates (charter §4.2 — all three must pass) ───────────────
MIN_ATR_RATIO = 1.0       # stop width ≥ 1× daily ATR (not too tight)
MIN_RR_TP2 = 2.0          # reward:risk to TP2 ≥ 2.0
# 3rd gate AQE can't apply: live regime stop-% ceiling. ASSUMED values —
# tune to the charter. Risk (entry−stop)/entry must be ≤ the regime's ceiling.
REGIME_STOP_PCT = {"GREEN": 8.0, "YELLOW": 6.0, "ORANGE": 5.0, "RED": 4.0}
DEFAULT_STOP_PCT_CEILING = 6.0
VWAP_STOP_ATR = 0.5       # buffer below VWAP for the vwap-based stop candidate
PIVOT_K = 3               # fractal half-width for intraday swing-low detection

# ── Sizing ─────────────────────────────────────────────────────────────────
RISK_BUDGET = 2100.0      # 3% of $70K (charter: risk per FULL trade is always 3%)


def regime_stop_ceiling(regime) -> float:
    """The stop-% ceiling for the given regime header (dict or level string)."""
    level = regime
    if isinstance(regime, dict):
        level = regime.get("level")
    return REGIME_STOP_PCT.get(str(level or "").upper(), DEFAULT_STOP_PCT_CEILING)
