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

WHAT IS DELIBERATELY NOT HERE.
No probability, no hit rate, no "quality" verdict. Detection is the easy half
and a detector on its own is decoration: loose rules find cups on everything.
The number that makes a detection worth reading is measured by sweeping this
same code across the panel's history and recording what actually happened next
(see scripts/pattern_calibrate.py). Until that table exists the export ships
`pattern_hit_rate: null` and says so — never a fabricated figure.

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
    out: list[dict] = []
    for i in range(k, m - k):
        win_h, win_l = h[i - k:i + k + 1], l[i - k:i + k + 1]
        if h[i] >= win_h.max():
            out.append({"kind": "H", "price": float(h[i]), "idx": i,
                        "date": str(pd.Timestamp(d[i]).date()),
                        "bars_ago": int(m - 1 - i)})
        elif l[i] <= win_l.min():
            out.append({"kind": "L", "price": float(l[i]), "idx": i,
                        "date": str(pd.Timestamp(d[i]).date()),
                        "bars_ago": int(m - 1 - i)})
    return out


def _blank() -> dict:
    return {"pattern": None, "pattern_stage": None, "pattern_trigger": None,
            "pattern_invalidation": None, "pattern_days": None,
            "pattern_fit": None, "pattern_start": None}


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
                "pattern": "CUP_HANDLE",
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


# Registry — every detector returns the SAME shape, so adding double-bottom or
# ascending-triangle later changes this list and nothing downstream.
DETECTORS = {"CUP_HANDLE": detect_cup_handle}


def detect_all(high, low, close, dates, volume=None, **kw) -> dict:
    """Run every detector; return the highest-fit hit, or a blank record."""
    best = _blank()
    for fn in DETECTORS.values():
        try:
            r = fn(high, low, close, dates, volume, **kw)
        except Exception:  # noqa: BLE001 — a lens must never break the export
            continue
        if r.get("pattern") and (best["pattern_fit"] is None
                                 or (r["pattern_fit"] or 0) > best["pattern_fit"]):
            best = r
    return best
