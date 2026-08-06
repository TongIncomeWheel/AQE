"""Chart-pattern lens — classic formations read off the CONFIRMED pivot series.

WHY THIS IS A LENS AND NOT A SCREEN (PM ruling 2026-08-06). A pattern is a
column on the one daily_list, the same way Longlist / Elder / QS are. It adds
no names, gates nothing, and sizes nothing. It answers one question next to the
others: is this name currently sitting inside a recognisable formation, and
where is the level that would confirm it.

THE DESIGN RULE: PATTERNS ARE GEOMETRY OVER PIVOTS, NEVER OVER RAW BARS.
Everything here consumes `pivot_series()` — the same 11-bar fractal convention
(k=5) the bracket engine and structure_shift already use. That is deliberate:

  * a pattern's trigger level is then the SAME kind of object as the levels
    the PM already trades against, not a second, subtly different notion of
    "resistance" that disagrees with the bracket by a few cents;
  * a bar-by-bar template matcher would find a cup in any 60 bars of noise.
    Requiring the shape to be made of CONFIRMED pivots — each needing 5 clean
    bars on either side — throws most of that away before any tolerance is
    applied.

NO PROBABILITY, AND THAT IS THE DESIGN (PM ruling 2026-08-06: "this pattern is
just a visual flag for me, not a signal"). A historical hit-rate table was
built and then removed on that ruling — a flag does not need one, and shipping
an unused calibration layer is how dead code accumulates. Nothing here says a
shape works; `pattern_fit` measures only how closely it matches the textbook
drawing. If a measured edge is ever wanted, the sweep is in git history at
dd9bcdc rather than sitting unread in the tree.

EVERY TOLERANCE BELOW IS A CHOICE, NOT A FACT. Ten traders draw ten different
cups. The constants are transcribed from the conventional definitions (O'Neil's
cup depth, the third-of-the-cup handle limit) rather than fitted to make our
own board look good, and they are named and grouped so they can be argued with
and re-set once real outcomes exist.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Same fractal strength as levels.py — one definition of "a pivot" across AQE.
PIVOT_K = 5

# How far back a formation may start. A textbook cup runs 2-6 months, so a
# 3-month window would systematically miss the classic ones and quietly report
# only the short ones. Search 6 months and let the reader filter on
# `pattern_days`, which every detection carries.
PATTERN_WINDOW = 126                    # ~6 months of trading days

# ── Cup & handle ────────────────────────────────────────────────────────────
# The conventional shape: a peak, a rounded decline, a recovery back to that
# peak, then a small drift lower on lighter volume before the break.
CUP_MIN_DEPTH_PCT = 12.0      # shallower than this is a pause, not a cup
CUP_MAX_DEPTH_PCT = 40.0      # deeper is a crash with a bounce, not a base
CUP_RIM_TOLERANCE_PCT = 6.0   # how close the right rim must come to the left
CUP_MIN_DAYS = 25             # a cup that forms in three weeks is a flag
CUP_MAX_DAYS = 250
HANDLE_MAX_RETRACE = 0.34     # handle may give back at most a third of the cup
HANDLE_MIN_DAYS = 3
HANDLE_MAX_DAYS = 40
HANDLE_MAX_VOL_RATIO = 1.10   # handle volume vs the cup's — must not be heavier


def pivot_series(high: np.ndarray, low: np.ndarray, dates: np.ndarray,
                 k: int = PIVOT_K, window: int = PATTERN_WINDOW) -> list[dict]:
    """Every CONFIRMED fractal pivot in the window, oldest -> newest.

    Each entry is {kind: 'H'|'L', price, date, idx, bars_ago}. `idx` indexes the
    windowed arrays, so callers can slice bars between two pivots.

    "Confirmed" means k bars have passed to its right without exceeding it, so
    the last k bars can never produce a pivot — a pattern is never called on a
    shape whose final turn has not held yet.
    """
    n = len(high)
    if n < 2 * k + 1 or len(low) != n or len(dates) != n:
        return []
    start = max(0, n - window)
    h, l, d = high[start:], low[start:], dates[start:]
    m = len(h)
    raw: list[dict] = []
    for i in range(k, m - k):
        win_h, win_l = h[i - k:i + k + 1], l[i - k:i + k + 1]
        if h[i] >= win_h.max():
            raw.append({"kind": "H", "price": float(h[i]), "idx": i,
                        "date": str(pd.Timestamp(d[i]).date()),
                        "bars_ago": int(m - 1 - i)})
        elif l[i] <= win_l.min():
            raw.append({"kind": "L", "price": float(l[i]), "idx": i,
                        "date": str(pd.Timestamp(d[i]).date()),
                        "bars_ago": int(m - 1 - i)})
    # ONE TURN = ONE PIVOT. A flat or rounded top satisfies the fractal test on
    # several adjacent bars, so the raw scan emits the same turn two or three
    # times. Left in, that breaks any rule reading CONSECUTIVE pivots: an
    # ascending triangle would see a "low" that failed to step up above the
    # identical low one bar earlier, and reject a perfectly good shape.
    # Collapse same-kind neighbours within k bars, keeping the extreme.
    out: list[dict] = []
    for p in raw:
        if (out and out[-1]["kind"] == p["kind"]
                and p["idx"] - out[-1]["idx"] <= k):
            better = (p["price"] > out[-1]["price"] if p["kind"] == "H"
                      else p["price"] < out[-1]["price"])
            if better:
                out[-1] = p
            continue
        out.append(p)
    return out


def _blank() -> dict:
    return {"pattern": None, "pattern_direction": None, "pattern_stage": None,
            "pattern_trigger": None, "pattern_invalidation": None,
            "pattern_days": None, "pattern_fit": None, "pattern_start": None,
            "pattern_alt": None}


def _fit(depth_pct: float, rim_gap_pct: float, handle_retrace: float,
         vol_ratio: float | None) -> float:
    """0-1 quality. NOT a probability — a "how textbook is this shape" score.

    Deliberately flat-weighted across the four things the definition actually
    constrains. A cleverer weighting would be a fitted model wearing a score's
    clothing, and there is nothing yet to fit it against.
    """
    mid = (CUP_MIN_DEPTH_PCT + CUP_MAX_DEPTH_PCT) / 2
    depth_s = 1.0 - min(1.0, abs(depth_pct - mid) / (mid - CUP_MIN_DEPTH_PCT))
    rim_s = 1.0 - min(1.0, rim_gap_pct / CUP_RIM_TOLERANCE_PCT)
    hand_s = 1.0 - min(1.0, handle_retrace / HANDLE_MAX_RETRACE)
    vol_s = 1.0 if vol_ratio is None else 1.0 - min(1.0, vol_ratio / HANDLE_MAX_VOL_RATIO)
    return round((depth_s + rim_s + hand_s + vol_s) / 4.0, 3)


def detect_cup_handle(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                      dates: np.ndarray, volume: np.ndarray | None = None,
                      k: int = PIVOT_K, window: int = PATTERN_WINDOW) -> dict:
    """The most recent cup & handle, or a blank record.

    Reads the pivot series right-to-left looking for: left rim (H) -> cup low
    (L) -> right rim (H) within tolerance of the left -> optional handle low
    (L) that gives back only part of the cup.

    `pattern_stage`:
      CUP        both rims formed, no handle yet — the shape is not tradeable
                 but the level is already known
      HANDLE     handle low in place, price drifting under the rim
      TRIGGERED  price has closed above the rim

    Blank (every key present, all None) when nothing is found. An absent key
    would make a reader's `.get()` silently mean "no pattern" on a row where
    the detector never ran at all — those are different states.
    """
    out = _blank()
    n = len(high)
    if n < 2 * k + 1 or len(close) != n:
        return out
    start = max(0, n - window)
    h, l, c = high[start:], low[start:], close[start:]
    v = volume[start:] if volume is not None and len(volume) == n else None
    d = dates[start:]
    piv = pivot_series(high, low, dates, k=k, window=window)
    if len(piv) < 3:
        return out

    last_close = float(c[-1])
    if not np.isfinite(last_close) or last_close <= 0:
        return out

    highs = [p for p in piv if p["kind"] == "H"]
    # Newest right-rim candidate first: the most recent formation is the one
    # that matters, and an older cup on the same chart has already resolved.
    for ri in range(len(highs) - 1, 0, -1):
        right = highs[ri]
        for li in range(ri - 1, -1, -1):
            left = highs[li]
            span = right["idx"] - left["idx"]
            if span < CUP_MIN_DAYS:
                continue
            if span > CUP_MAX_DAYS:
                break
            # Rims must be comparable heights — that is what makes it a cup
            # rather than a leg up or a lower high.
            rim_gap = abs(right["price"] - left["price"]) / left["price"] * 100
            if rim_gap > CUP_RIM_TOLERANCE_PCT:
                continue
            # The cup low is the deepest point BETWEEN the rims, taken from the
            # bars rather than the pivot list: the true low of the base is what
            # sets the depth, whether or not it happened to confirm as a pivot.
            seg = l[left["idx"]:right["idx"] + 1]
            if len(seg) == 0:
                continue
            cup_low = float(np.nanmin(seg))
            rim = max(left["price"], right["price"])
            if cup_low <= 0:
                continue
            depth = (rim - cup_low) / rim * 100
            if not (CUP_MIN_DEPTH_PCT <= depth <= CUP_MAX_DEPTH_PCT):
                continue

            # ---- handle: what happened AFTER the right rim
            post = l[right["idx"]:]
            handle_low = float(np.nanmin(post)) if len(post) else None
            handle_days = int(len(post) - 1)
            retrace = ((rim - handle_low) / (rim - cup_low)
                       if handle_low is not None and rim > cup_low else None)

            vol_ratio = None
            if v is not None and handle_days >= 1:
                cup_v = np.nanmean(v[left["idx"]:right["idx"] + 1])
                han_v = np.nanmean(v[right["idx"]:])
                if np.isfinite(cup_v) and cup_v > 0 and np.isfinite(han_v):
                    vol_ratio = float(han_v / cup_v)

            stage = "CUP"
            if last_close > rim:
                stage = "TRIGGERED"
            elif (retrace is not None and handle_days >= HANDLE_MIN_DAYS
                  and handle_days <= HANDLE_MAX_DAYS
                  and retrace <= HANDLE_MAX_RETRACE
                  and (vol_ratio is None or vol_ratio <= HANDLE_MAX_VOL_RATIO)):
                stage = "HANDLE"
            elif handle_days > HANDLE_MAX_DAYS:
                # Drifted too long under the rim — the handle has become a new
                # base and this formation is no longer the live read.
                continue
            elif retrace is not None and retrace > HANDLE_MAX_RETRACE:
                # Gave back more than a third of the cup: the base failed.
                continue

            out.update({
                "pattern": "CUP_HANDLE", "pattern_direction": "BULLISH",
                "pattern_stage": stage,
                # The rim is the level that confirms it. Same kind of object as
                # last_pivot_high, so the alert layer watches it identically.
                "pattern_trigger": round(rim, 2),
                # Invalidation = the handle's low if there is one, else the cup
                # low. Below it the shape is gone, whatever the fit score says.
                "pattern_invalidation": round(
                    handle_low if (stage == "HANDLE" and handle_low is not None)
                    else cup_low, 2),
                "pattern_days": int(span + handle_days),
                "pattern_fit": _fit(depth, rim_gap,
                                    retrace if retrace is not None else 0.0,
                                    vol_ratio),
                "pattern_start": str(pd.Timestamp(d[left["idx"]]).date()),
            })
            return out
    return out


# ── Double bottom ───────────────────────────────────────────────────────────
# Two lows at roughly the same level with a real bounce between them. The
# bounce is what separates a base from a flat drift: without a minimum rise,
# ANY two similar lows in a quiet range qualify, and quiet ranges are common.
#
# The base test is doing most of the work. Without it the rule fired on 30 of
# 40 random walks — any drifting series throws up two similar lows with a
# bounce between them somewhere in six months. Requiring the pair to be THE
# low of the window, not just A pair of lows inside it, takes that to single
# figures. A double bottom that is not at the bottom is not a double bottom.
DB_LOW_TOLERANCE_PCT = 3.0    # how close the second low must come to the first
DB_MIN_DAYS = 15              # closer together than this is one low, not two
DB_MAX_DAYS = 160
DB_MIN_BOUNCE_PCT = 12.0      # the middle peak must be this far above the lows
DB_BASE_TOLERANCE_PCT = 4.0   # ...and both lows must be this near the window low


def _double_extreme(high, low, close, dates, bullish: bool,
                    k: int = PIVOT_K, window: int = PATTERN_WINDOW) -> dict:
    """Double bottom (bullish) and double top (bearish) in ONE code path.

    Parameterised rather than reflected. Reflecting prices looked elegant and
    was wrong twice over: negated prices trip every `<= 0` guard, and a
    percentage tolerance measured against a negative base changes sign. Two
    hand-written copies would instead drift apart the first time a tolerance is
    tuned. One path, one flag, comparisons swapped.

    Trigger is the NECKLINE — the peak between the two lows, or the trough
    between the two tops. That is the level whose break confirms the shape.

    Stages: BASE (both feet in, price still the wrong side of the neckline) /
    TRIGGERED.
    """
    out = _blank()
    n = len(high)
    if n < 2 * k + 1 or len(close) != n:
        return out
    start = max(0, n - window)
    h, l, c, d = high[start:], low[start:], close[start:], dates[start:]
    piv = pivot_series(high, low, dates, k=k, window=window)
    feet = [p for p in piv if p["kind"] == ("L" if bullish else "H")]
    if len(feet) < 2:
        return out
    last_close = float(c[-1])
    # The extreme of the window the pair must sit at: the floor for a bottom,
    # the ceiling for a top.
    edge = float(np.nanmin(l)) if bullish else float(np.nanmax(h))
    if edge <= 0:
        return out

    for si in range(len(feet) - 1, 0, -1):          # newest second foot first
        second = feet[si]
        for fi in range(si - 1, -1, -1):
            first = feet[fi]
            span = second["idx"] - first["idx"]
            if span < DB_MIN_DAYS:
                continue
            if span > DB_MAX_DAYS:
                break
            if first["price"] <= 0:
                continue
            gap = abs(second["price"] - first["price"]) / first["price"] * 100
            if gap > DB_LOW_TOLERANCE_PCT:
                continue
            # Both feet must sit at the EXTREME of the window. Two similar lows
            # halfway up a range are a pause, not a base — and two similar highs
            # halfway up are not a top.
            if (max(abs(first["price"] - edge), abs(second["price"] - edge))
                    / edge * 100) > DB_BASE_TOLERANCE_PCT:
                continue
            seg = (h if bullish else l)[first["idx"]:second["idx"] + 1]
            if len(seg) == 0:
                continue
            neck = float(np.nanmax(seg) if bullish else np.nanmin(seg))
            base = (min(first["price"], second["price"]) if bullish
                    else max(first["price"], second["price"]))
            if base <= 0:
                continue
            bounce = abs(neck - base) / base * 100
            if bounce < DB_MIN_BOUNCE_PCT:
                continue
            # Already through the base since the second foot? Then the shape
            # failed and is not the live read, whatever it looked like.
            after = (l if bullish else h)[second["idx"]:]
            if len(after):
                broke = (float(np.nanmin(after)) < base * 0.98 if bullish
                         else float(np.nanmax(after)) > base * 1.02)
                if broke:
                    continue

            triggered = last_close > neck if bullish else last_close < neck
            sym = 1.0 - min(1.0, gap / DB_LOW_TOLERANCE_PCT)
            depth = min(1.0, bounce / (DB_MIN_BOUNCE_PCT * 3))
            out.update({
                "pattern": "DOUBLE_BOTTOM" if bullish else "DOUBLE_TOP",
                "pattern_direction": "BULLISH" if bullish else "BEARISH",
                "pattern_stage": "TRIGGERED" if triggered else "BASE",
                "pattern_trigger": round(neck, 2),
                "pattern_invalidation": round(base, 2),
                "pattern_days": int(len(c) - 1 - first["idx"]),
                "pattern_fit": round((sym + depth) / 2, 3),
                "pattern_start": str(pd.Timestamp(d[first["idx"]]).date()),
            })
            return out
    return out


def detect_double_bottom(high, low, close, dates, volume=None, **kw) -> dict:
    """Two lows at a level with a real bounce between them — BULLISH."""
    return _double_extreme(high, low, close, dates, bullish=True, **kw)


def detect_double_top(high, low, close, dates, volume=None, **kw) -> dict:
    """The bearish twin. Trigger breaks DOWNWARD and the invalidation sits
    ABOVE it — read pattern_direction before assuming either."""
    return _double_extreme(high, low, close, dates, bullish=False, **kw)


# ── Triangles ───────────────────────────────────────────────────────────────
# A flat side tested repeatedly while the other side marches toward it.
# Ascending: flat ceiling, lows stepping UP (bullish). Descending: flat floor,
# highs stepping DOWN (bearish). The marching side is the entire content —
# without it a flat ceiling is just a resistance level, which AQE already ships
# as last_pivot_high.
AT_TOP_TOLERANCE_PCT = 3.0    # how flat the tested side must be across touches
AT_MIN_LOW_RISE_PCT = 1.0     # average travel required per step of the staircase
AT_MAX_LOW_SLIP_PCT = 1.5     # a single step may go the wrong way this much
AT_MIN_DAYS = 20
AT_MAX_DAYS = 160
AT_MIN_TOUCHES = 2            # of the flat side — one touch is not a level


def _flat_side_triangle(high, low, close, dates, bullish: bool,
                        k: int = PIVOT_K, window: int = PATTERN_WINDOW) -> dict:
    out = _blank()
    n = len(high)
    if n < 2 * k + 1 or len(close) != n:
        return out
    start = max(0, n - window)
    c, d = close[start:], dates[start:]
    piv = pivot_series(high, low, dates, k=k, window=window)
    flats = [p for p in piv if p["kind"] == ("H" if bullish else "L")]
    steps = [p for p in piv if p["kind"] == ("L" if bullish else "H")]
    if len(flats) < AT_MIN_TOUCHES or len(steps) < 2:
        return out
    last_close = float(c[-1])

    # Every touch near the newest one — NOT necessarily contiguous. The first
    # version walked backwards and stopped at the first pivot outside tolerance,
    # so one spike anywhere in the run destroyed the formation and the pattern
    # almost never fired. A level is a price that keeps being tested; an
    # intervening overshoot does not un-test it.
    ref = flats[-1]
    if ref["price"] <= 0:
        return out
    touches = [p for p in flats
               if abs(p["price"] - ref["price"]) / ref["price"] * 100
               <= AT_TOP_TOLERANCE_PCT]
    if len(touches) < AT_MIN_TOUCHES:
        return out
    span = touches[-1]["idx"] - touches[0]["idx"]
    if not (AT_MIN_DAYS <= span <= AT_MAX_DAYS):
        return out

    inner = [p for p in steps if touches[0]["idx"] < p["idx"] < touches[-1]["idx"]]
    if len(inner) < 2 or inner[0]["price"] <= 0:
        return out
    # The staircase is judged AS A STAIRCASE. The first version demanded every
    # consecutive pair travel 1%+ in the right direction, so one flat tread in
    # an otherwise textbook shape threw the whole thing away.
    travel = (inner[-1]["price"] - inner[0]["price"]) / inner[0]["price"] * 100
    if not bullish:
        travel = -travel
    if travel < AT_MIN_LOW_RISE_PCT * (len(inner) - 1):
        return out
    for a, b in zip(inner, inner[1:]):
        if a["price"] <= 0:
            continue
        step = (b["price"] - a["price"]) / a["price"] * 100
        if not bullish:
            step = -step
        if step < -AT_MAX_LOW_SLIP_PCT:
            return out          # a tread that went materially backwards

    level = float(np.mean([p["price"] for p in touches]))
    last_step = inner[-1]["price"]
    if (last_step >= level) if bullish else (last_step <= level):
        return out
    triggered = last_close > level if bullish else last_close < level

    spread = max(p["price"] for p in touches) - min(p["price"] for p in touches)
    flat = 1.0 - min(1.0, (spread / level * 100) / AT_TOP_TOLERANCE_PCT)
    reach = abs(level - inner[0]["price"])
    climb = min(1.0, abs(last_step - inner[0]["price"]) / reach) if reach > 0 else 0.0
    reps = min(1.0, (len(touches) - AT_MIN_TOUCHES + 1) / 3.0)
    out.update({
        "pattern": "ASC_TRIANGLE" if bullish else "DESC_TRIANGLE",
        "pattern_direction": "BULLISH" if bullish else "BEARISH",
        "pattern_stage": "TRIGGERED" if triggered else "FORMING",
        "pattern_trigger": round(level, 2),
        "pattern_invalidation": round(last_step, 2),
        "pattern_days": int(len(c) - 1 - touches[0]["idx"]),
        "pattern_fit": round((flat + climb + reps) / 3, 3),
        "pattern_start": str(pd.Timestamp(d[touches[0]["idx"]]).date()),
    })
    return out


def detect_ascending_triangle(high, low, close, dates, volume=None, **kw) -> dict:
    """Flat ceiling, lows stepping up into it — BULLISH."""
    return _flat_side_triangle(high, low, close, dates, bullish=True, **kw)


def detect_descending_triangle(high, low, close, dates, volume=None, **kw) -> dict:
    """Flat floor, highs stepping down onto it — BEARISH. Trigger breaks
    DOWNWARD; the invalidation sits ABOVE it."""
    return _flat_side_triangle(high, low, close, dates, bullish=False, **kw)


# ── Wedges ──────────────────────────────────────────────────────────────────
# Both trendlines pointing the SAME way while converging. That convergence is
# the content: a rising wedge is not "an uptrend" — it is an uptrend whose
# highs are running out of steam faster than its lows are, which is why the
# conventional read is bearish despite every high being higher.
#
# Written directly rather than mirrored: the two wedges are not reflections of
# each other in the way a double top reflects a double bottom. A RISING wedge
# is bearish and a FALLING wedge is bullish, so mirroring one would produce the
# other's shape with the wrong direction attached.
WEDGE_MIN_PIVOTS = 2          # per side — two points define each trendline
WEDGE_MIN_DAYS = 20
WEDGE_MAX_DAYS = 160
WEDGE_MIN_CONVERGENCE = 0.30  # the far end must be <=70% as wide as the near end
WEDGE_MIN_SLOPE_PCT = 3.0     # total travel of the slower line, over the wedge


def _wedge(high, low, close, dates, volume=None, rising=True,
           k: int = PIVOT_K, window: int = PATTERN_WINDOW) -> dict:
    out = _blank()
    n = len(high)
    if n < 2 * k + 1 or len(close) != n:
        return out
    start = max(0, n - window)
    c, d = close[start:], dates[start:]
    piv = pivot_series(high, low, dates, k=k, window=window)
    hs = [p for p in piv if p["kind"] == "H"]
    ls = [p for p in piv if p["kind"] == "L"]
    if len(hs) < WEDGE_MIN_PIVOTS or len(ls) < WEDGE_MIN_PIVOTS:
        return out

    h0, h1 = hs[0], hs[-1]
    l0, l1 = ls[0], ls[-1]
    span = max(h1["idx"], l1["idx"]) - min(h0["idx"], l0["idx"])
    if not (WEDGE_MIN_DAYS <= span <= WEDGE_MAX_DAYS):
        return out
    if h0["price"] <= 0 or l0["price"] <= 0:
        return out
    dh = (h1["price"] - h0["price"]) / h0["price"] * 100
    dl = (l1["price"] - l0["price"]) / l0["price"] * 100

    if rising:
        # Both lines up, lows climbing FASTER — the wedge closes from below.
        if dh <= 0 or dl <= 0 or dl <= dh:
            return out
        slower = dh
    else:
        # Both lines down, highs falling FASTER — the wedge closes from above.
        if dh >= 0 or dl >= 0 or dh >= dl:
            return out
        slower = -dl
    if slower < WEDGE_MIN_SLOPE_PCT:
        return out

    start_w = h0["price"] - l0["price"]
    end_w = h1["price"] - l1["price"]
    if start_w <= 0 or end_w <= 0 or end_w / start_w > (1 - WEDGE_MIN_CONVERGENCE):
        return out

    last_close = float(c[-1])
    if rising:
        trigger, invalid = l1["price"], h1["price"]      # breaks DOWN
        stage = "TRIGGERED" if last_close < trigger else "FORMING"
        name, direction = "RISING_WEDGE", "BEARISH"
    else:
        trigger, invalid = h1["price"], l1["price"]      # breaks UP
        stage = "TRIGGERED" if last_close > trigger else "FORMING"
        name, direction = "FALLING_WEDGE", "BULLISH"

    conv = min(1.0, (1 - end_w / start_w) / 0.7)
    steep = min(1.0, abs(slower) / (WEDGE_MIN_SLOPE_PCT * 4))
    pts = min(1.0, (len(hs) + len(ls) - 4) / 4.0)
    first = min(h0["idx"], l0["idx"])
    out.update({
        "pattern": name, "pattern_direction": direction, "pattern_stage": stage,
        "pattern_trigger": round(trigger, 2),
        "pattern_invalidation": round(invalid, 2),
        "pattern_days": int(len(c) - 1 - first),
        "pattern_fit": round((conv + steep + pts) / 3, 3),
        "pattern_start": str(pd.Timestamp(d[first]).date()),
    })
    return out


def detect_rising_wedge(high, low, close, dates, volume=None, **kw) -> dict:
    """Higher highs AND higher lows, converging — BEARISH despite the uptrend."""
    return _wedge(high, low, close, dates, volume, rising=True, **kw)


def detect_falling_wedge(high, low, close, dates, volume=None, **kw) -> dict:
    """Lower highs AND lower lows, converging — BULLISH despite the downtrend."""
    return _wedge(high, low, close, dates, volume, rising=False, **kw)


# ── Head & shoulders ────────────────────────────────────────────────────────
# Three peaks, the middle one clearly highest, shoulders at comparable heights.
# The NECKLINE through the two intervening lows is the level that matters; the
# head is only what makes the shape recognisable.
HS_MIN_HEAD_PCT = 3.0         # head must clear both shoulders by this much
HS_SHOULDER_TOLERANCE_PCT = 8.0   # how unequal the shoulders may be
HS_MIN_DAYS = 25
HS_MAX_DAYS = 160


def _head_shoulders(high, low, close, dates, bullish: bool,
                    k: int = PIVOT_K, window: int = PATTERN_WINDOW) -> dict:
    """H&S (bearish) and inverse H&S (bullish) in ONE code path.

    Three extremes of the same kind, the middle one clearly the furthest out,
    the outer two at comparable levels. The NECKLINE through the two
    intervening opposite pivots is the level that matters; the head is only
    what makes the shape recognisable.
    """
    out = _blank()
    n = len(high)
    if n < 2 * k + 1 or len(close) != n:
        return out
    start = max(0, n - window)
    c, d = close[start:], dates[start:]
    piv = pivot_series(high, low, dates, k=k, window=window)
    peaks = [p for p in piv if p["kind"] == ("L" if bullish else "H")]
    necks = [p for p in piv if p["kind"] == ("H" if bullish else "L")]
    if len(peaks) < 3 or len(necks) < 2:
        return out
    last_close = float(c[-1])
    sign = -1.0 if bullish else 1.0          # "further out" flips direction

    for ri in range(len(peaks) - 1, 1, -1):            # newest right shoulder
        right, head, left = peaks[ri], peaks[ri - 1], peaks[ri - 2]
        if left["price"] <= 0 or right["price"] <= 0:
            continue
        span = right["idx"] - left["idx"]
        if not (HS_MIN_DAYS <= span <= HS_MAX_DAYS):
            continue
        # The head has to be a head — beyond BOTH shoulders by a clear margin.
        if (min(sign * (head["price"] - left["price"]) / left["price"],
                sign * (head["price"] - right["price"]) / right["price"]) * 100
                < HS_MIN_HEAD_PCT):
            continue
        # ...and the shoulders comparable, or it is just a lower high / higher low.
        if (abs(right["price"] - left["price"]) / left["price"] * 100
                > HS_SHOULDER_TOLERANCE_PCT):
            continue
        mids = [p["price"] for p in necks if left["idx"] < p["idx"] < right["idx"]]
        if len(mids) < 2:
            continue
        neck = float(np.mean(mids))
        if neck <= 0:
            continue
        # The neckline must sit BETWEEN the shoulders and the head, or the
        # shape is not the one being described.
        shoulder = min(left["price"], right["price"]) if not bullish \
            else max(left["price"], right["price"])
        if (neck <= shoulder) if bullish else (neck >= shoulder):
            continue

        triggered = last_close > neck if bullish else last_close < neck
        far = max(left["price"], right["price"]) if not bullish \
            else min(left["price"], right["price"])
        head_s = min(1.0, (sign * (head["price"] - far) / far * 100)
                     / (HS_MIN_HEAD_PCT * 3))
        sym = 1.0 - min(1.0, (abs(right["price"] - left["price"]) / left["price"] * 100)
                        / HS_SHOULDER_TOLERANCE_PCT)
        out.update({
            "pattern": "INV_HEAD_SHOULDERS" if bullish else "HEAD_SHOULDERS",
            "pattern_direction": "BULLISH" if bullish else "BEARISH",
            "pattern_stage": "TRIGGERED" if triggered else "FORMING",
            "pattern_trigger": round(neck, 2),
            "pattern_invalidation": round(head["price"], 2),
            "pattern_days": int(len(c) - 1 - left["idx"]),
            "pattern_fit": round((max(0.0, head_s) + sym) / 2, 3),
            "pattern_start": str(pd.Timestamp(d[left["idx"]]).date()),
        })
        return out
    return out


def detect_head_shoulders(high, low, close, dates, volume=None, **kw) -> dict:
    """Classic BEARISH reversal: left shoulder, higher head, right shoulder.
    Trigger is the neckline and it breaks DOWNWARD."""
    return _head_shoulders(high, low, close, dates, bullish=False, **kw)


def detect_inverse_head_shoulders(high, low, close, dates, volume=None, **kw) -> dict:
    """The BULLISH reflection: two troughs either side of a deeper one, with a
    neckline through the intervening peaks. Trigger breaks upward."""
    return _head_shoulders(high, low, close, dates, bullish=True, **kw)


# Registry — every detector returns the SAME shape, so adding one changes this
# dict and nothing downstream. BOTH directions are represented on purpose: a
# lens that only ever reports bullish shapes is not reading the chart, it is
# flattering it.
DETECTORS = {
    # bullish
    "CUP_HANDLE": detect_cup_handle,
    "DOUBLE_BOTTOM": detect_double_bottom,
    "ASC_TRIANGLE": detect_ascending_triangle,
    "FALLING_WEDGE": detect_falling_wedge,
    "INV_HEAD_SHOULDERS": detect_inverse_head_shoulders,
    # bearish
    "DOUBLE_TOP": detect_double_top,
    "DESC_TRIANGLE": detect_descending_triangle,
    "RISING_WEDGE": detect_rising_wedge,
    "HEAD_SHOULDERS": detect_head_shoulders,
}


def detect_all(high, low, close, dates, volume=None, **kw) -> dict:
    """Run every detector; return the best match, with the others named.

    A chart can legitimately match more than one shape, and often the matches
    DISAGREE about direction — a cup & handle and a double top are the same
    geometry (two highs at a level with a trough between) and differ only in
    which way price eventually resolves. Silently reporting whichever scored
    higher would hand the reader a bullish or bearish flag decided by a
    tie-break they cannot see.

    So the runner-up names ride along in `pattern_alt`. For a VISUAL flag that
    is the useful answer: "this looks like a cup, and it also looks like a
    double top" is a true statement about an ambiguous chart, and the eye
    settles it in a second.

    CAVEAT worth knowing: pattern_fit is only comparable WITHIN a pattern.
    Each shape scores different things (a cup scores depth and handle volume, a
    triangle scores flatness and touches), so ranking across patterns by fit is
    rough. Fixing that properly needs outcome data, which was deliberately not
    built (see the module docstring).
    """
    hits = []
    for fn in DETECTORS.values():
        try:
            r = fn(high, low, close, dates, volume, **kw)
        except Exception:  # noqa: BLE001 — a lens must never break the export
            continue
        if r.get("pattern"):
            hits.append(r)
    if not hits:
        return _blank()
    hits.sort(key=lambda r: r.get("pattern_fit") or 0.0, reverse=True)
    best = hits[0]
    others = [r["pattern"] for r in hits[1:]]
    best["pattern_alt"] = ", ".join(others) if others else None
    return best
