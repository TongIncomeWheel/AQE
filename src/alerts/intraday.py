"""Intraday measures from a single live quote, normalised for time of day.

AQE's engines are COB: ATR14 and every structural level come from completed
daily bars. A live quote gives today's range SO FAR. Comparing the two
directly is the trap — a session's range builds through the day, so at 10:30
a perfectly ordinary stock has travelled ~39% of its ATR and a naive
"range < 0.6 x ATR = coiling" rule calls it a coil. Every normal name would
read COIL until about 13:00, every day. That is a clock, not a market read.

So every measure here is expressed against what is EXPECTED BY THIS HOUR:

    expected range so far = ATR14 x sqrt(elapsed_fraction)

Volatility scales with the square root of time, so a ratio of 0.45 means
"genuinely tight for this point in the session" at 09:45 and at 15:00 alike.

STATED APPROXIMATIONS, not fitted curves:
  * sqrt(t) for range accumulation — principled (Brownian scaling), but not
    measured against our own intraday history, which we do not store.
  * LINEAR for volume accumulation — knowingly wrong at the edges: real
    session volume is U-shaped, heavy at the open and the close, so the pace
    ratio overstates in the first half hour and understates midday. Good
    enough to rank names against each other at the same moment; not good
    enough to compare a 09:45 reading against a 15:00 one.

Both are why COIL/THRUST ship logging-only until their thresholds can be set
from what actually fired rather than from these assumptions.
"""

from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")

# Regular US cash session.
SESSION_OPEN_MIN = 9 * 60 + 30
SESSION_CLOSE_MIN = 16 * 60
SESSION_MINUTES = SESSION_CLOSE_MIN - SESSION_OPEN_MIN      # 390

# Floor on elapsed fraction. In the first minutes the range is essentially
# noise and dividing by ~0 manufactures enormous ratios, so nothing before
# this reads as a coil or a thrust at all.
MIN_ELAPSED_FRACTION = 0.05                                  # ~20 minutes

# Starting thresholds — ASSUMPTIONS pending real data (see module docstring).
COIL_MAX_RATIO = 0.60          # range so far <= 60% of what this hour expects
COIL_MIN_POSITION = 0.70       # ...while holding the top of that range
THRUST_MIN_RATIO = 1.40        # range so far >= 140% of expectation
THRUST_MIN_POSITION = 0.85     # ...and pressing the high
THRUST_MIN_VOL_PACE = 1.30     # ...on volume running hot for the hour
FAILED_PUSH_MAX_POSITION = 0.20   # wide day, but sitting on the low


def session_elapsed_fraction(now: datetime | None = None) -> float:
    """How much of the cash session has passed, 0-1. 1.0 outside/after hours."""
    n = (now or datetime.now(_ET)).astimezone(_ET)
    mins = n.hour * 60 + n.minute
    if mins <= SESSION_OPEN_MIN:
        return 0.0
    if mins >= SESSION_CLOSE_MIN:
        return 1.0
    return (mins - SESSION_OPEN_MIN) / SESSION_MINUTES


def measures(quote: dict, atr14: float | None,
             now: datetime | None = None) -> dict:
    """Time-normalised intraday read for one name.

    Returns {position_in_range, range_pct, range_ratio, vol_pace,
    move_from_open_pct, gap_pct, elapsed, signature}. Any field that cannot be
    computed comes back None rather than a guess — a missing day_high is a data
    gap, not a tight range.
    """
    def f(v):
        try:
            x = float(v)
            return x if math.isfinite(x) else None
        except (TypeError, ValueError):
            return None

    price = f(quote.get("price"))
    hi, lo = f(quote.get("day_high")), f(quote.get("day_low"))
    op, prev = f(quote.get("open")), f(quote.get("prev_close"))
    vol, avg_vol = f(quote.get("volume")), f(quote.get("avg_volume"))
    elapsed = session_elapsed_fraction(now)

    out = {"elapsed": round(elapsed, 3), "position_in_range": None,
           "range_pct": None, "range_ratio": None, "vol_pace": None,
           "move_from_open_pct": None, "gap_pct": None, "signature": None}

    if price is None or price <= 0:
        return out

    # Where in today's range are we trading — the close-location value.
    if hi is not None and lo is not None and hi > lo:
        out["position_in_range"] = round((price - lo) / (hi - lo), 3)
        out["range_pct"] = round(100.0 * (hi - lo) / price, 2)

    if op:
        out["move_from_open_pct"] = round(100.0 * (price / op - 1), 2)
    if prev and op:
        out["gap_pct"] = round(100.0 * (op / prev - 1), 2)

    # Range vs what THIS HOUR expects. The whole point of the module.
    atr = f(atr14)
    if (out["range_pct"] is not None and atr and price
            and elapsed >= MIN_ELAPSED_FRACTION):
        atr_pct = 100.0 * atr / price
        expected = atr_pct * math.sqrt(elapsed)
        if expected > 0:
            out["range_ratio"] = round(out["range_pct"] / expected, 2)

    # Volume pace. Linear elapsed — see the docstring's stated limitation.
    if vol is not None and avg_vol and elapsed >= MIN_ELAPSED_FRACTION:
        out["vol_pace"] = round(vol / (avg_vol * elapsed), 2)

    out["signature"] = classify(out)
    return out


def classify(m: dict) -> str | None:
    """COIL / THRUST / FAILED_PUSH / None from the normalised measures.

    None means "nothing distinctive", NOT "quiet" — an unclassifiable reading
    (missing range, too early in the session) is not evidence of compression.
    """
    pos, ratio, pace = m.get("position_in_range"), m.get("range_ratio"), m.get("vol_pace")
    if pos is None or ratio is None:
        return None
    if ratio <= COIL_MAX_RATIO and pos >= COIL_MIN_POSITION:
        return "COIL"
    if (ratio >= THRUST_MIN_RATIO and pos >= THRUST_MIN_POSITION
            and (pace is None or pace >= THRUST_MIN_VOL_PACE)):
        return "THRUST"
    if ratio >= THRUST_MIN_RATIO and pos <= FAILED_PUSH_MAX_POSITION:
        return "FAILED_PUSH"
    return None


def daily_signature(open_: float | None, high: float | None, low: float | None,
                    close: float | None, volume: float | None,
                    avg_volume: float | None, atr14: float | None) -> dict:
    """The SAME read, computed at COB from a COMPLETED daily bar.

    A per-ticker detail rather than an alert: where the day closed in its own
    range, how wide that range was against the name's normal, and how heavy
    the volume was. Every field on the daily list is COB, and this belongs
    with them.

    NO time normalisation here, and that is the point — the session is over,
    so `range / ATR` is directly meaningful. The sqrt(elapsed) machinery above
    exists only because a LIVE quote measures a half-finished day.
    """
    def f(v):
        try:
            x = float(v)
            return x if math.isfinite(x) else None
        except (TypeError, ValueError):
            return None

    o, h, l, c = f(open_), f(high), f(low), f(close)
    v, av, atr = f(volume), f(avg_volume), f(atr14)
    out = {"day_position": None, "day_range_atr": None, "day_vol_x": None,
           "day_from_open_pct": None, "day_signature": None}
    if h is None or l is None or c is None or h <= l:
        return out

    out["day_position"] = round((c - l) / (h - l), 3)
    if atr and atr > 0:
        out["day_range_atr"] = round((h - l) / atr, 2)
    if v is not None and av:
        out["day_vol_x"] = round(v / av, 2)
    if o:
        out["day_from_open_pct"] = round(100.0 * (c / o - 1), 2)

    pos, rng, vol = out["day_position"], out["day_range_atr"], out["day_vol_x"]
    if rng is not None:
        if rng <= COIL_MAX_RATIO and pos >= COIL_MIN_POSITION:
            out["day_signature"] = "COIL"
        elif (rng >= THRUST_MIN_RATIO and pos >= THRUST_MIN_POSITION
                and (vol is None or vol >= THRUST_MIN_VOL_PACE)):
            out["day_signature"] = "THRUST"
        elif rng >= THRUST_MIN_RATIO and pos <= FAILED_PUSH_MAX_POSITION:
            out["day_signature"] = "FAILED_PUSH"
    return out


def describe(m: dict) -> str:
    """One line for the email/ledger — the numbers behind the signature."""
    bits = []
    if m.get("position_in_range") is not None:
        bits.append(f"{m['position_in_range']:.0%} up today's range")
    if m.get("range_ratio") is not None:
        bits.append(f"range {m['range_ratio']:.2f}x expected for the hour")
    if m.get("vol_pace") is not None:
        bits.append(f"volume {m['vol_pace']:.2f}x pace")
    if m.get("move_from_open_pct") is not None:
        bits.append(f"{m['move_from_open_pct']:+.1f}% from open")
    return " · ".join(bits)
