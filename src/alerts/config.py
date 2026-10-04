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

# Hard floor between two digest EMAILS (not between trigger evaluations,
# which still run every ALERT_MINUTES so nothing misses its window). A PM
# complaint (2026-10-01): two pollers (the in-app thread, the GitHub Actions
# backstop) on the same ~15-min cadence could land close enough together to
# both send — see state.py's digest-batching section. Slightly under
# ALERT_MINUTES, not equal to it, so ordinary small scheduler jitter between
# two honest 15-min cycles doesn't itself get gated.
MIN_DIGEST_GAP_MINUTES = int(_f("AQE_MIN_DIGEST_GAP_MINUTES", 12))

# US market session (Eastern) the alert poll is allowed to email in. Slightly
# padded so the 15-min-delayed last bar still lands inside the window.
MARKET_OPEN = (9, 45)    # 09:45 ET
MARKET_CLOSE = (16, 15)  # 16:15 ET


# --- PMA committee levels (AQE Handoff: PMA Live Alerts, 2026-09-30) -------
def _b(env: str, default: bool) -> bool:
    v = os.environ.get(env)
    if v is None:
        return default
    return v.strip().lower() not in ("0", "false", "no", "")


PMA_LEVELS_ENABLED = _b("PMA_LEVELS_ENABLED", True)
# Relative to the repo root. aegis/output/** is excluded from deploy-hf.yml's
# redeploy trigger on purpose (see the handoff doc) — redeploying the Space
# every morning the committee publishes would kill the container mid-run.
PMA_LEVELS_PATH = os.environ.get("PMA_LEVELS_PATH", "aegis/output/pma/pma_levels.json")

# % distance bands for the two "approaching" WARN alerts (each once in a
# trigger's life — see src/alerts/pma_levels.py's dedup).
HELD_NEAR_PCT = _f("HELD_NEAR_PCT", 3.0)          # held: within X% of either stop
SHORTLIST_NEAR_PCT = _f("SHORTLIST_NEAR_PCT", 1.5)  # shortlist: within X% of entry


# --- PMA condition alerts (AQE Handoff: D123/R21, 2026-10-02) --------------
# "shadow": the new condition checks run every cycle and log to
# condition_ledger/, but email ZERO new messages — the existing trigger
# path (above) keeps running exactly as it does today. "live" (PM's own
# call, 2026-10-02): a state CHANGE (CONDITION MET / FAILED PUSH / CHASED /
# ANALYST OUT / EXIT LINE) also sends an email, as soon as PMA starts
# publishing a row's own `conditions` block (none do yet in production —
# this flag just means AQE is ready the moment they do, not that anything
# fires today).
PMA_CONDITIONS_MODE = os.environ.get("PMA_CONDITIONS_MODE", "live").strip().lower()
PMA_CONDITIONS_LIVE = PMA_CONDITIONS_MODE == "live"

# How many voices get their own criteria line on a condition card (PM
# 2026-10-03: "limit the voices instead of all"). Highest conviction first;
# the rest are folded into one "+N more" line, never dropped silently.
CONDITION_CARD_MAX_SEATS = int(_f("CONDITION_CARD_MAX_SEATS", 3))

# --- AQE-default conditions (PM ruling 2026-10-04: universe = committee
# book + AQE Longlist/Elder). See condition_defaults.py.
CONDITION_DEFAULTS_ENABLED = _b("CONDITION_DEFAULTS_ENABLED", True)
# Which AQE lists feed default-watched names: "longlist", "elder", or both.
CONDITION_DEFAULT_SOURCES = os.environ.get("CONDITION_DEFAULT_SOURCES", "longlist,elder")
# WATCH is the committee's "not yet" bucket -- off unless the PM flips it.
CONDITION_DEFAULTS_INCLUDE_WATCH = _b("CONDITION_DEFAULTS_INCLUDE_WATCH", False)
CONDITION_DEFAULT_VOL_X = _f("CONDITION_DEFAULT_VOL_X", 1.0)
CONDITION_DEFAULT_CHASE_PCT = _f("CONDITION_DEFAULT_CHASE_PCT", 3.0)
# A breakout line further than this above the last close is not armed --
# an hourly close through a level 13% away isn't worth 15-min bar pulls
# every cycle (2026-10-03 export: p90 of candidate lines sat 13% away).
CONDITION_DEFAULT_MAX_LEVEL_PCT = _f("CONDITION_DEFAULT_MAX_LEVEL_PCT", 6.0)
# Hard ceiling on default-watched names per cycle (FMP: one 15-min bar
# pull per name per cycle, 80 calls/min on cloud IPs).
CONDITION_MAX_WATCHED = int(_f("CONDITION_MAX_WATCHED", 120))
