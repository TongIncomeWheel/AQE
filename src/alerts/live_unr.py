"""Same-day Undercut-and-Rally read for the 15-min cards -- PM 2026-10-07:
"What we need to know is if U&R took place (met or not met) ... I care if
U&R daily has been met (within the day)."

The question per name: did price undercut a DAILY reference level today and
is it back above it now?

  reference levels  (Valen's four support types, as of the last COMPLETED
                    session so a level never moves with today's price):
                    horizontal support (the latest confirmed swing low),
                    trendline support (through the last two rising swing
                    lows, projected to today), the key moving averages
                    EMA9 / EMA21, and unfilled support gaps. Nothing else.
  undercut          the session low is under the level by a real margin
                    (spec.IMPL_UNR_MIN_UNDERCUT_ATR for the swing low,
                    IMPL_MAUR_MIN_UNDERCUT_ATR for the rest): today's low, or
                    yesterday's if it also closed under the level (Valen draws
                    the reclaim as its own day after the dip).
  reclaimed         spot is back above the level. Intraday that is spot, not
                    a close -- the card says so.
  trend gate        EMA21 is rising ("uptrend, rising EMAs"): a broken stock
                    is not a U&R.

MET = at least one level undercut today AND reclaimed. Everything else is
NOT_MET (with the reason), or UNKNOWN when the data to judge isn't there --
never a silent "not met" on missing history. Pure; reuses the very helpers
the nightly VALEN grader uses, so the two can never disagree about what a
reference level is. Figures and a verdict, never a trade call.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.valen import setups as SU
from src.valen import spec as S

MIN_HISTORY = 80

MET, NOT_MET, UNKNOWN = "MET", "NOT_MET", "UNKNOWN"


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
    """Valen's reclaim day. {status, hits, below, levels, stop, volume, reason}.

    A support level is UNDERCUT when the session low is under it by a real
    margin -- today's low, or yesterday's low if yesterday also CLOSED under
    it (so the reclaim happens today). It is RECLAIMED when spot is back
    above. MET = at least one level undercut and reclaimed, with EMA21
    rising. Valen's chart draws the reclaim as its own bar after the dip, so
    an undercut yesterday that closed under the level counts; an undercut
    yesterday that already closed back above does not (that reclaim day was
    yesterday).

    hits  = [{name, level, low, when: "today"|"yesterday", spot_pct}]
    below = undercut, spot still under it
    stop  = today's low (Valen: stop = low of day)
    volume = {pullback_dry, reclaim_x, reclaim_ok}: his two volume marks --
             the pullback ran on below-average volume, the reclaim day on
             above-average. Marks only; they never decide MET.
    levels = every support level (name, level) for the card's reference block."""
    res = {"status": UNKNOWN, "hits": [], "below": [], "levels": [], "stop": None,
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
    try:
        df = df.sort_values("date").reset_index(drop=True)
        b = SU.Bars(df)
        t = b.n - 1
        atr = float(b.atr[t])
        if np.isnan(atr) or atr <= 0:
            res["reason"] = "no ATR"
            return res
        refs = levels(b)
        prev_low, prev_close = float(b.l[t]), float(b.c[t])
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
        today_cut = day_low < lvl - thr
        prior_cut = prev_low < lvl - thr and prev_close < lvl
        if not (today_cut or prior_cut):
            continue
        row = {"name": r["name"], "level": round(float(lvl), 2),
               "low": round(float(day_low if today_cut else prev_low), 2),
               "when": "today" if today_cut else "yesterday"}
        if spot > lvl:
            row["spot_pct"] = round(float((spot / lvl - 1.0) * 100.0), 2)
            res["hits"].append(row)
        else:
            res["below"].append(row)
    if res["hits"]:
        res["status"] = MET
    else:
        res["status"] = NOT_MET
        res["reason"] = ("undercut a level, still below it" if res["below"]
                         else "no support level undercut")
    return res
