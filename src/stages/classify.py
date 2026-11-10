"""Stage classifier: one ticker's weekly bars -> Stage 1/2/3/4 (Weinstein).

The call is two facts read on COMPLETED weekly bars, and nothing else:
  1. which side of its 30-week average price closed on, and
  2. which way that average slopes (rising / flat / falling, spec.IMPL_SLOPE_*).

  close > MA and MA rising   -> Stage 2 reading
  close < MA and MA falling  -> Stage 4 reading
  anything else              -> TRANSITIONAL: Stage 3 if it follows an
                                advance (2 or 3), Stage 1 if it follows a
                                decline (4 or 1). The cycle order is the
                                tie-break, exactly as Weinstein draws it.

A change of stage is confirmed only after the new reading holds
spec.IMPL_CONFIRM_WEEKS completed weeks; until then it shows as `candidate`.
The still-forming week (mid-week runs) never confirms anything — it is
reported as `candidate_forming`, a live warning only.

Relative strength (Mansfield, vs SPY), up/down-week volume and the 52-week
range position ride along as EVIDENCE. They never move the stage call: a
stage that silently depended on RS would no longer be Weinstein's stage, and
the reader could not tell which fact produced it.

Pure: takes arrays/Series, opens no file, calls no network.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import spec as S

TRANSITIONAL = "T"


def _f(x, nd=2):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if math.isfinite(v) else None


def _reading(close: float, ma: float, slope_pct: float):
    """The raw weekly reading: 2, 4, TRANSITIONAL, or None (not enough data)."""
    if not (math.isfinite(close) and math.isfinite(ma) and math.isfinite(slope_pct)):
        return None
    if close > ma and slope_pct > S.IMPL_SLOPE_FLAT_PCT:
        return 2
    if close < ma and slope_pct < -S.IMPL_SLOPE_FLAT_PCT:
        return 4
    return TRANSITIONAL


def _as_stage(reading, current, range_pos):
    """Map a raw reading to a stage given where the cycle currently is."""
    if reading in (2, 4):
        return reading
    if current in (2, 3):
        return 3
    if current in (4, 1):
        return 1
    # cold start inside a range: top half of the 52-week range = a top, else a base
    if range_pos is not None and math.isfinite(range_pos):
        return 3 if range_pos >= 0.5 else 1
    return 1


def stage_series(closes: pd.Series, highs: pd.Series | None = None,
                 lows: pd.Series | None = None) -> pd.DataFrame:
    """Week-by-week stage for a COMPLETED-weeks close series (date-indexed,
    oldest first). Columns: reading, ma, slope_pct, stage, candidate,
    stage_since, seeded. Rows before spec.MIN_WEEKS carry stage None."""
    closes = closes.astype(float)
    ma = closes.rolling(S.WS_MA_WEEKS, min_periods=S.WS_MA_WEEKS).mean()
    slope = (ma / ma.shift(S.IMPL_SLOPE_LOOKBACK_WEEKS) - 1.0) * 100.0
    hi = (highs if highs is not None else closes).astype(float).rolling(
        S.IMPL_RANGE_WEEKS, min_periods=S.WS_MA_WEEKS).max()
    lo = (lows if lows is not None else closes).astype(float).rolling(
        S.IMPL_RANGE_WEEKS, min_periods=S.WS_MA_WEEKS).min()
    span = (hi - lo).replace(0, np.nan)
    rpos = (closes - lo) / span

    stage = None
    since = None
    seeded = True
    pending, pending_n, pending_since = None, 0, None
    rows = []
    for i, d in enumerate(closes.index):
        r = _reading(closes.iat[i], ma.iat[i], slope.iat[i])
        if r is None:
            rows.append((r, None, None, None, None, None))
            continue
        cand = _as_stage(r, stage, rpos.iat[i])
        if stage is None:
            stage, since = cand, d                       # cold-start seed
        elif cand == stage:
            pending, pending_n, pending_since = None, 0, None
        else:
            if cand == pending:
                pending_n += 1
            else:
                pending, pending_n, pending_since = cand, 1, d
            if pending_n >= S.IMPL_CONFIRM_WEEKS:
                stage, since, seeded = pending, pending_since, False
                pending, pending_n, pending_since = None, 0, None
        rows.append((r, stage, cand, since, seeded, d))
    out = pd.DataFrame(rows, index=closes.index,
                       columns=["reading", "stage", "candidate", "stage_since", "seeded", "_d"])
    out["ma"] = ma
    out["slope_pct"] = slope
    out["range_pos"] = rpos
    return out.drop(columns="_d")


def _mansfield(closes: pd.Series, bench: pd.Series | None) -> tuple[float | None, bool | None]:
    if bench is None or bench.empty:
        return None, None
    ratio = (closes / bench.reindex(closes.index)).dropna()
    if len(ratio) < S.WS_RS_MA_WEEKS + S.IMPL_RS_SLOPE_WEEKS:
        return None, None
    rs = (ratio / ratio.rolling(S.WS_RS_MA_WEEKS).mean() - 1.0) * 100.0
    now, then = rs.iat[-1], rs.iat[-1 - S.IMPL_RS_SLOPE_WEEKS]
    if not (math.isfinite(now) and math.isfinite(then)):
        return None, None
    return _f(now), bool(now > then)


def _updown_volume(closes: pd.Series, volume: pd.Series | None) -> float | None:
    """Average volume of up-weeks / average volume of down-weeks, last N
    completed weeks. > 1 = heavier on advances (accumulation-shaped), < 1 =
    heavier on declines (distribution-shaped). None when it can't be read."""
    if volume is None or volume.empty:
        return None
    w = S.IMPL_VOLUME_WINDOW_WEEKS
    chg = closes.diff().tail(w)
    vol = volume.reindex(chg.index).astype(float)
    up, dn = vol[chg > 0], vol[chg < 0]
    if up.empty or dn.empty or not (dn.mean() > 0):
        return None
    return _f(up.mean() / dn.mean())


def classify(weekly: pd.DataFrame, bench_closes: pd.Series | None = None,
             forming_after=None) -> dict:
    """One ticker's stage read.

    `weekly`: date/close (+ optional high/low/volume) weekly bars, any order.
    `bench_closes`: SPY weekly closes (date-indexed) for the Mansfield RS line.
    `forming_after`: the latest COMPLETED session date. A weekly bar dated
        after it is the still-forming week: excluded from the stage call,
        reported as `candidate_forming` only.
    """
    if weekly is None or weekly.empty:
        return {"status": "NA", "reason": "no weekly bars"}
    w = weekly.assign(date=pd.to_datetime(weekly["date"])).sort_values("date").set_index("date")
    forming = None
    if forming_after is not None:
        cutoff = pd.Timestamp(forming_after)
        if w.index[-1] > cutoff:
            forming = w.iloc[-1]
            w = w[w.index <= cutoff]
    if len(w) < S.MIN_WEEKS:
        return {"status": "NA", "reason": f"{len(w)} completed weeks < {S.MIN_WEEKS} needed",
                "weeks": len(w)}

    closes = w["close"].astype(float)
    ser = stage_series(closes, w.get("high"), w.get("low"))
    last = ser.iloc[-1]
    if last["stage"] is None or pd.isna(last["stage"]):
        return {"status": "NA", "reason": "30-week average not yet formed", "weeks": len(w)}

    stage = int(last["stage"])
    since = pd.Timestamp(last["stage_since"])
    weeks_in = int((ser.index > since).sum() + 1) if since in ser.index else None
    prior = ser["stage"][ser.index < since].dropna()
    previous_stage = int(prior.iat[-1]) if not prior.empty else None
    # confirmed THIS completed week = the confirming week is the latest bar
    confirmed_now = (previous_stage is not None and previous_stage != stage
                     and len(ser) >= 2 and ser["stage"].iat[-2] != stage)

    cand_forming = None
    if forming is not None:
        all_closes = pd.concat([closes, pd.Series([float(forming["close"])], index=[forming.name])])
        ma_f = all_closes.tail(S.WS_MA_WEEKS).mean()
        ma_back = all_closes.iloc[-S.WS_MA_WEEKS - S.IMPL_SLOPE_LOOKBACK_WEEKS:-S.IMPL_SLOPE_LOOKBACK_WEEKS].mean()
        r = _reading(float(forming["close"]), ma_f, (ma_f / ma_back - 1.0) * 100.0)
        if r is not None:
            cand_forming = _as_stage(r, stage, last["range_pos"])

    rs, rs_rising = _mansfield(closes, bench_closes)
    cand = int(last["candidate"])
    transition = S.TRANSITION_LABEL.get((previous_stage, stage)) if previous_stage else None
    return {
        "status": "OK",
        "stage": stage,
        "stage_name": S.STAGE_NAME[stage],
        "cycle_name": S.CYCLE_NAME[stage],
        "since": since.date().isoformat(),
        "weeks_in_stage": weeks_in,
        "previous_stage": previous_stage,
        "transition": transition,
        "confirmed_this_week": bool(confirmed_now),
        "seeded": bool(last["seeded"]),          # no confirmed change in history yet: rests on the cold-start seed
        # this week's raw read mapped to a stage; differs from `stage` = an unconfirmed change in progress
        "candidate": cand,
        "candidate_forming": cand_forming,       # the still-forming week, if any (warning only)
        "as_of_week": closes.index[-1].date().isoformat(),
        "close": _f(closes.iat[-1]),
        "ma30w": _f(last["ma"]),
        "ma30w_slope_pct_4w": _f(last["slope_pct"]),
        "pct_from_ma30w": _f((closes.iat[-1] / last["ma"] - 1.0) * 100.0),
        "range_pos_52w": _f(last["range_pos"], 3),
        "rs_mansfield": rs,
        "rs_rising": rs_rising,
        "updown_volume_ratio": _updown_volume(closes, w["volume"] if "volume" in w else None),
        "weeks": len(w),
        "_series": ser["stage"],                 # stripped before writing; breadth history reads it
    }
