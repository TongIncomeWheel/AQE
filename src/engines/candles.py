"""Candlestick lens — the last completed bar's shape, on DAILY and WEEKLY.

Same treatment as the chart-pattern lens: a visual flag as a column, never a
gate, never a signal, no probability attached. Easier than chart patterns
because there is nothing to fit — a bar either engulfs the one before it or it
does not.

TWO TIMEFRAMES, TWO COLUMNS, NEVER MERGED (PM ruling 2026-08-06: "candlesticks
should cover weeklys and dailys"). A weekly engulfing is five sessions of
agreement; a daily engulfing is one. Collapsing them into a single field would
destroy exactly the difference that makes the weekly worth reading. The panel
already builds panel_weekly.parquet, so the second timeframe costs no extra
data — only a second call.

ONE DEFINITION OF A PIN BAR, NOT TWO. Hammer and shooting star are the same
geometry AQE already ships as `pin_bar_state`, so this module CALLS
`pin_bar._pin_bar_at` rather than re-deriving the test. The two fields can
therefore agree on the same bar by construction — they are one implementation
seen from two places, not two implementations of one idea. (The alternative,
a second wick-ratio rule living here, is how a field ends up meaning something
subtly different from its twin: see the day_vol_x / rvol duplicate this session
started by deleting.)

SIGNIFICANCE ORDER. When several fire on the same bar the widest-context one
wins: a three-bar reversal says more than a two-bar one, which says more than
the shape of a single candle. That ordering is a convention, not a measurement.

Every threshold below is the conventional definition, not a fitted value.
"""

from __future__ import annotations

import numpy as np

from src.engines.pin_bar import _pin_bar_at

# Pin-bar geometry — the SAME numbers pin_bar.compute_pin_bar defaults to, so
# the daily candle read and pin_bar_state cannot disagree about a hammer.
PIN_WICK_RATIO = 0.60
PIN_BODY_RATIO = 0.30
PIN_OPP_WICK_RATIO = 0.20

DOJI_MAX_BODY = 0.08          # body <= 8% of range: open and close effectively equal
MARUBOZU_MIN_BODY = 0.90      # body >= 90% of range: no meaningful wick either side
STAR_MAX_MIDDLE_BODY = 0.40   # the star's own body, vs its range
ENGULF_MIN_BODY = 0.30        # an engulfing bar must have a real body of its own
SOLDIERS_MIN_BODY = 0.55      # each of the three must be a decisive candle
HARAMI_MAX_INNER = 0.60       # inner body at most this share of the prior body

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


def _blank() -> dict:
    return {"candle": None, "candle_direction": None, "candle_date": None}


def _f(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _body(o, c):
    return abs(c - o)


def _three_bar(o, h, l, c) -> tuple[str, str] | None:
    """Morning / evening star, three soldiers / crows. Needs 3 bars."""
    if len(c) < 3:
        return None
    o1, o2, o3 = o[-3], o[-2], o[-1]
    c1, c2, c3 = c[-3], c[-2], c[-1]
    r2 = h[-2] - l[-2]
    b1, b2, b3 = _body(o1, c1), _body(o2, c2), _body(o3, c3)

    # STAR: decisive bar, small-bodied pause gapping away, then a decisive bar
    # back through the middle of the first. The middle candle's SMALL body is
    # the pattern — a big middle bar is just a two-day reversal.
    if r2 > 0 and b2 <= STAR_MAX_MIDDLE_BODY * r2:
        mid1 = (o1 + c1) / 2
        if c1 < o1 and c3 > o3 and c3 > mid1 and max(o2, c2) < c1:
            return "MORNING_STAR", BULLISH
        if c1 > o1 and c3 < o3 and c3 < mid1 and min(o2, c2) > c1:
            return "EVENING_STAR", BEARISH

    # THREE IN A ROW: each closing beyond the last, each a real body, each
    # opening within the previous body (a gap-and-run is a different animal).
    rngs = [h[-3] - l[-3], r2, h[-1] - l[-1]]
    if all(r > 0 for r in rngs):
        bodies = [b1 / rngs[0], b2 / rngs[1], b3 / rngs[2]]
        if all(b >= SOLDIERS_MIN_BODY for b in bodies):
            if (c1 > o1 and c2 > o2 and c3 > o3 and c2 > c1 and c3 > c2
                    and o2 <= c1 and o3 <= c2):
                return "THREE_WHITE_SOLDIERS", BULLISH
            if (c1 < o1 and c2 < o2 and c3 < o3 and c2 < c1 and c3 < c2
                    and o2 >= c1 and o3 >= c2):
                return "THREE_BLACK_CROWS", BEARISH
    return None


def _two_bar(o, h, l, c) -> tuple[str, str] | None:
    """Engulfing, piercing / dark cloud, harami. Needs 2 bars."""
    if len(c) < 2:
        return None
    o1, o2, c1, c2 = o[-2], o[-1], c[-2], c[-1]
    r1, r2 = h[-2] - l[-2], h[-1] - l[-1]
    b1, b2 = _body(o1, c1), _body(o2, c2)
    if r2 <= 0 or r1 <= 0:
        return None

    # ENGULFING: today's body swallows yesterday's, opposite colour.
    if b2 >= ENGULF_MIN_BODY * r2:
        if (c1 < o1 and c2 > o2 and c2 >= o1 and o2 <= c1):
            return "BULLISH_ENGULFING", BULLISH
        if (c1 > o1 and c2 < o2 and c2 <= o1 and o2 >= c1):
            return "BEARISH_ENGULFING", BEARISH

        # PIERCING / DARK CLOUD: opens beyond yesterday's extreme, then closes
        # back past the MIDPOINT of yesterday's body without engulfing it.
        mid1 = (o1 + c1) / 2
        if c1 < o1 and o2 < c1 and c2 > mid1 and c2 < o1:
            return "PIERCING", BULLISH
        if c1 > o1 and o2 > c1 and c2 < mid1 and c2 > o1:
            return "DARK_CLOUD", BEARISH

    # HARAMI: today's body sits entirely inside yesterday's, and is much
    # smaller. The pause after a decisive bar.
    if b1 > 0 and b2 <= HARAMI_MAX_INNER * b1:
        inside = max(o2, c2) <= max(o1, c1) and min(o2, c2) >= min(o1, c1)
        if inside:
            if c1 < o1:
                return "BULLISH_HARAMI", BULLISH
            if c1 > o1:
                return "BEARISH_HARAMI", BEARISH
    return None


def _one_bar(o, h, l, c) -> tuple[str, str] | None:
    """Pin bars (via the SHARED pin_bar test), doji, marubozu."""
    o1, h1, l1, c1 = o[-1], h[-1], l[-1], c[-1]
    rng = h1 - l1
    if rng <= 0:
        return None
    prev_range = (h[-2] - l[-2]) if len(c) >= 2 else float("nan")
    pin = _pin_bar_at(o1, h1, l1, c1, prev_range,
                      wick_ratio=PIN_WICK_RATIO, body_ratio=PIN_BODY_RATIO,
                      opp_wick_ratio=PIN_OPP_WICK_RATIO,
                      small_candle_filter=False, small_candle_mult=0.0)
    if pin == "BULLISH_PIN":
        return "HAMMER", BULLISH
    if pin == "BEARISH_PIN":
        return "SHOOTING_STAR", BEARISH

    body = _body(o1, c1)
    if body <= DOJI_MAX_BODY * rng:
        return "DOJI", NEUTRAL
    if body >= MARUBOZU_MIN_BODY * rng:
        return ("MARUBOZU_BULL", BULLISH) if c1 > o1 else ("MARUBOZU_BEAR", BEARISH)
    return None


def detect_candle(open_, high, low, close, dates=None) -> dict:
    """The most significant candlestick reading on the LAST completed bar.

    Widest context wins: three-bar, then two-bar, then the single candle. Blank
    (every key present, all None) when nothing distinctive — which is the common
    case and is not the same as "not computed".
    """
    out = _blank()
    try:
        o = np.asarray(open_, dtype=float)
        h = np.asarray(high, dtype=float)
        l = np.asarray(low, dtype=float)
        c = np.asarray(close, dtype=float)
    except (TypeError, ValueError):
        return out
    if len(c) == 0 or not (len(o) == len(h) == len(l) == len(c)):
        return out
    if not np.isfinite([o[-1], h[-1], l[-1], c[-1]]).all():
        return out

    hit = _three_bar(o, h, l, c) or _two_bar(o, h, l, c) or _one_bar(o, h, l, c)
    if not hit:
        return out
    name, direction = hit
    out.update({"candle": name, "candle_direction": direction,
                "candle_date": (str(dates[-1])[:10] if dates is not None
                                and len(dates) else None)})
    return out
