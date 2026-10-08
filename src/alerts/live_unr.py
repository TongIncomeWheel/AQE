"""Valen's U&R across the two timeframes -- PM 2026-10-07/08/09.

THE DAILY CHART picks the stock and the day. THE INTRADAY CHART picks the
entry. This module is the daily half; live_measures.vwap_trigger is the
intraday half; condition_state joins them. They are deliberately NOT
chained: the entry trigger does not wait for the daily level to be reclaimed
(that was the first cut's mistake -- a VWAP candle that closed while spot was
still just under the level sent nothing).

  CANDIDATE ("armed")  a daily support level was undercut -- today, or within
                       the last IMPL_UNR_ARMED_SESSIONS sessions with the
                       last close still under it -- and EMA21 is rising.
                       Levels are Valen's four: horizontal support (latest
                       swing low), trendline support, EMA9 / EMA21, support
                       gaps; all as of the last completed session.
  reclaimed            spot is back above the level. A TICK on the card, not
                       a gate. Judged on spot, not a close.
  stop                 today's low of day (his stop).
  volume marks         pullback ran on below-average volume; the reclaim day
                       on above-average. Marks only.

Status: ARMED / NOT_MET / UNKNOWN. Missing history is UNKNOWN, never a silent
not-met. Pure; reuses the helpers the nightly VALEN grader uses. Figures and
a state, never a trade call.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.valen import setups as SU
from src.valen import spec as S

MIN_HISTORY = 80

ARMED, NOT_MET, UNKNOWN = "ARMED", "NOT_MET", "UNKNOWN"


def _frame(history: list[dict]) -> pd.DataFrame | None:
    try:
        df = pd.DataFrame(history)
        need = {"date", "open", "high", "low", "close", "volume"}
        if not need.issubset(df.columns):
            return None
        return df[list(need)].dropna()
    except Exception:  # noqa: BLE001
        return None


def levels(b: "SU.Bars") -> list[dict]:
    """Every daily reference level as of the last completed session:
    [{name, kind, level}], in a fixed reading order."""
    t = b.n - 1
    out = []
    sw = SU._swing_lows(b.l, t - S.IMPL_UNR_SUPPORT_LOOKBACK, t - S.IMPL_UNR_PIVOT_SIDE,
                        S.IMPL_UNR_PIVOT_SIDE)
    if sw:
        out.append({"name": "Swing low", "kind": "swing", "level": float(b.l[sw[-1]])})
    for n in S.PM_UNR_DAILY_EMA_SPANS:
        out.append({"name": f"EMA{n}", "kind": "ma", "level": float(b.ema[n][t])})
    tl = SU._trendline(b)
    if tl is not None:
        out.append({"name": "Trendline", "kind": "trend", "level": float(tl[b.n])})  # today
    for g in SU._support_gaps(b, win0=b.n):
        out.append({"name": "Gap", "kind": "gap", "level": float(g)})
    return out


def evaluate(history: list[dict] | None, spot: float | None, day_low: float | None,
             vol_x: float | None = None, today=None) -> dict:
    """{status, armed, levels, stop, volume, reason}.

    armed  = support levels undercut recently: [{name, level, low, when,
             reclaimed, spot_pct}] where `when` is "today" or "N sessions ago"
             and `reclaimed` says spot is back above (a tick, not a gate).
    levels = every support level (name, level) for the card's reference block.
    stop   = today's low (Valen: stop = low of day).
    volume = {pullback_dry, reclaim_x, reclaim_ok}: marks only."""
    res = {"status": UNKNOWN, "armed": [], "levels": [], "stop": None,
           "volume": {"pullback_dry": None, "reclaim_x": None, "reclaim_ok": None},
           "reason": None}
    if not history or spot is None or day_low is None or spot <= 0:
        res["reason"] = "no daily history or live price"
        return res
    df = _frame(history)
    if df is not None and today is not None and len(df):
        # a panel refreshed intraday already carries today's partial bar
        df = df[pd.to_datetime(df["date"]).dt.date != pd.Timestamp(today).date()]
    if df is None or len(df) < MIN_HISTORY:
        res["reason"] = "not enough daily history"
        return res
    n_back = S.IMPL_UNR_ARMED_SESSIONS
    try:
        df = df.sort_values("date").reset_index(drop=True)
        b = SU.Bars(df)
        t = b.n - 1
        atr = float(b.atr[t])
        if np.isnan(atr) or atr <= 0:
            res["reason"] = "no ATR"
            return res
        refs = levels(b)
        recent_lows = [float(b.l[t - k]) for k in range(n_back)]       # newest first
        last_close = float(b.c[t])
        if not np.isnan(b.vol50[t]) and b.vol50[t] > 0:
            res["volume"]["pullback_dry"] = bool(float(np.mean(b.v[t - 2:t + 1])) < b.vol50[t])
    except Exception as exc:  # noqa: BLE001
        res["reason"] = f"error: {type(exc).__name__}"
        return res
    res["levels"] = [{"name": r["name"], "level": round(r["level"], 2)} for r in refs]
    res["stop"] = round(float(day_low), 2)
    if vol_x is not None:
        res["volume"]["reclaim_x"] = round(float(vol_x), 2)
        res["volume"]["reclaim_ok"] = bool(vol_x >= S.IMPL_UNR_RECLAIM_VOL_X)

    if not b.rising(b.ema[21], t):
        res["status"], res["reason"] = NOT_MET, "EMA21 is not rising"
        return res
    for r in refs:
        lvl = r["level"]
        thr = (S.IMPL_UNR_MIN_UNDERCUT_ATR if r["kind"] == "swing"
               else S.IMPL_MAUR_MIN_UNDERCUT_ATR) * atr
        cut_today = day_low < lvl - thr
        # an undercut in the last few sessions only counts while the last
        # close is still under the level: a level already reclaimed at the
        # close means that reclaim day has passed.
        ago = next((k + 1 for k, lo in enumerate(recent_lows) if lo < lvl - thr), None)
        cut_recent = ago is not None and last_close < lvl
        if not (cut_today or cut_recent):
            continue
        low = float(day_low) if cut_today else float(recent_lows[ago - 1])
        row = {"name": r["name"], "level": round(float(lvl), 2), "low": round(low, 2),
               "when": "today" if cut_today else ("yesterday" if ago == 1
                                                  else f"{ago} sessions ago"),
               "reclaimed": bool(spot > lvl)}
        if spot > lvl:
            row["spot_pct"] = round(float((spot / lvl - 1.0) * 100.0), 2)
        else:
            row["spot_pct"] = round(float((spot / lvl - 1.0) * 100.0), 2)   # negative: under it
        res["armed"].append(row)
    if res["armed"]:
        res["status"] = ARMED
    else:
        res["status"] = NOT_MET
        res["reason"] = f"no support level undercut in the last {n_back} sessions"
    return res
