"""MOMENTUM HIGH engine: vectorised over wide (date x ticker) price matrices, per the BACKTEST REVIEW session's reference rules (spec.py).

`compute(panel, spy)` returns a Result holding the membership matrix for EVERY date, so `first_day` (membership in the prior 5 sessions, with the top-20% cuts
recomputed per date) and the 3-sample-date reference check read the same numbers the export does. Pure function of prices: no scores, no files, no network.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import spec as S


@dataclass
class Result:
    members: pd.DataFrame            # bool, date x ticker: passes every rule that date
    eligible: pd.DataFrame           # bool: price >= $5 and ATR% in [1.5, 15] (the percentile + breadth population)
    market: pd.DataFrame             # per date: spy_above_200d, breadth_pct_above_50d, eligible_n, market_ok
    feat: dict                       # wide frames used by the per-row fields: close, hi252, atr14, atr_pct, adx14, mom, rs
    counts: pd.DataFrame             # per date: how many names passed each gate in order (for the status/diagnostics)


def _wide(panel: pd.DataFrame, col: str) -> pd.DataFrame:
    return panel.pivot_table(index="date", columns="ticker", values=col, aggfunc="last").sort_index()


def _wilder(x: pd.DataFrame) -> pd.DataFrame:
    return x.ewm(alpha=1.0 / S.ADX_N, adjust=False, min_periods=S.ADX_N).mean()


def _week_complete_map(index: pd.DatetimeIndex) -> tuple[pd.Series, pd.DatetimeIndex]:
    """For each session t, the W-FRI label of the LAST COMPLETED week as of t's close. A session is a week's last session when it is a Friday or the next
    session in the calendar falls in a later week (holiday Friday); the panel's final session counts as complete only if it is a Friday."""
    wk = index.to_period("W-FRI")
    nxt = pd.Series(wk[1:].tolist() + [None], index=index)
    cur = pd.Series(wk, index=index)
    is_end = np.array([(n is not None and n != c) or (n is None and idx.weekday() == 4) for c, n, idx in zip(cur, nxt, index)])
    labels = np.where(is_end, [p.end_time.normalize() for p in wk], [(p - 1).end_time.normalize() for p in wk])
    return pd.Series(pd.DatetimeIndex(labels), index=index), pd.DatetimeIndex(sorted(set(labels)))


def compute(panel: pd.DataFrame, spy: pd.DataFrame, tickers: list[str] | None = None) -> Result:
    p = panel
    if tickers is not None:
        p = p[p["ticker"].isin(set(tickers))]
    close, high, low = _wide(p, "close"), _wide(p, "high"), _wide(p, "low")
    idx = close.index
    spy_close = spy.assign(date=pd.to_datetime(spy["date"]).dt.normalize()).drop_duplicates("date").set_index("date")["close"].sort_index().reindex(idx)

    pc = close.shift(1)
    tr = np.fmax(np.fmax(high - low, (high - pc).abs()), (low - pc).abs())
    atr14 = tr.rolling(S.ATR_N, min_periods=S.ATR_MIN_PERIODS).mean()
    atr_pct = atr14 / close * 100.0

    ema = {n: close.ewm(span=n, adjust=False, min_periods=n).mean() for n in S.EMA_SPANS}
    hi252 = high.rolling(S.HIGH_WINDOW, min_periods=S.HIGH_MIN_PERIODS).max()
    mom = close.shift(S.MOM_SKIP) / close.shift(S.MOM_LONG) - 1.0
    rs = close / close.shift(S.RS_LOOKBACK) - (spy_close / spy_close.shift(S.RS_LOOKBACK)).to_numpy()[:, None]

    macd = close.ewm(span=S.MACD_FAST, adjust=False).mean() - close.ewm(span=S.MACD_SLOW, adjust=False).mean()
    hist = macd - macd.ewm(span=S.MACD_SIGNAL, adjust=False).mean()
    elder_green = (ema[13] > ema[13].shift(1)) & (hist > hist.shift(1))

    up, dn = high.diff(), -low.diff()
    plus_dm = up.where((up > dn) & (up > 0), 0.0).where(up.notna())
    minus_dm = dn.where((dn > up) & (dn > 0), 0.0).where(dn.notna())
    atr_w = _wilder(tr)
    pdi, mdi = 100.0 * _wilder(plus_dm) / atr_w, 100.0 * _wilder(minus_dm) / atr_w
    dx = 100.0 * (pdi - mdi).abs() / (pdi + mdi)
    adx = _wilder(dx)
    adx_ok = (adx >= S.ADX_MIN) & (pdi > mdi)

    # weekly, completed weeks only
    wclose = close.resample("W-FRI").last()
    w10, w30 = wclose.rolling(S.WEEK_SMA_FAST, min_periods=S.WEEK_SMA_FAST).mean(), wclose.rolling(S.WEEK_SMA_SLOW, min_periods=S.WEEK_SMA_SLOW).mean()
    w_ok = (wclose > w30) & (w30 > w30.shift(S.WEEK_SLOPE_LOOKBACK)) & (wclose > w10)
    lab, _ = _week_complete_map(idx)
    weekly_ok = w_ok.reindex(lab.to_numpy()).fillna(False).astype(bool)
    weekly_ok.index = idx

    eligible = (close >= S.MIN_PRICE) & (atr_pct >= S.ATR_PCT_LO) & (atr_pct <= S.ATR_PCT_HI)
    top_mom = mom.where(eligible).rank(axis=1, pct=True) >= S.TOP_PCT
    top_rs = rs.where(eligible).rank(axis=1, pct=True) >= S.TOP_PCT

    trend = (close > ema[150]) & (ema[150] > ema[200]) & ((ema[200] / ema[200].shift(S.EMA200_RISING_LOOKBACK) - 1.0) > 0) & (close > ema[50])
    near_high = close >= S.NEAR_HIGH_FRAC * hi252
    stacked = (ema[21] > ema[50]) & (ema[50] > ema[150]) & (close > ema[21])
    gates = [("eligible", eligible), ("trend", trend), ("near_high", near_high), ("stacked", stacked), ("top_mom", top_mom), ("top_rs", top_rs),
             ("elder_green", elder_green), ("adx", adx_ok), ("weekly", weekly_ok)]
    members, counts = eligible.copy(), {}
    counts["eligible"] = eligible.sum(axis=1)
    for name, g in gates[1:]:
        members = members & g.fillna(False).astype(bool)
        counts[name] = members.sum(axis=1)

    sma50 = close.rolling(S.SMA50, min_periods=S.SMA50).mean()
    spy_sma200 = spy_close.rolling(S.SMA200, min_periods=S.SMA200).mean()
    n_el = eligible.sum(axis=1)
    breadth = ((close > sma50) & eligible).sum(axis=1) / n_el.where(n_el > 0) * 100.0
    spy_above = (spy_close > spy_sma200).where(spy_sma200.notna())
    market = pd.DataFrame({"spy_above_200d": spy_above, "breadth_pct_above_50d": breadth, "eligible_n": n_el})
    market["market_ok"] = (market["spy_above_200d"] == True) & (market["breadth_pct_above_50d"] >= S.BREADTH_MIN_PCT)  # noqa: E712
    short = close.notna().sum(axis=0) < S.MIN_BARS_FOR_MOM
    return Result(members=members.fillna(False).astype(bool), eligible=eligible, market=market,
                  feat={"close": close, "hi252": hi252, "atr14": atr14, "atr_pct": atr_pct, "adx14": adx, "mom": mom, "rs": rs, "short_history": short},
                  counts=pd.DataFrame(counts))


def rows_at(res: Result, date, limit: int | None = None) -> list[dict]:
    """The member rows for one date, ranked by mom_12_1 descending. Pure arithmetic on the matrices; `first_day` = not a member in the prior 5 sessions."""
    d = pd.Timestamp(date).normalize()
    i = res.members.index.get_loc(d)
    mem = res.members.iloc[i]
    names = mem[mem].index.tolist()
    prior = res.members.iloc[max(0, i - S.FIRST_DAY_LOOKBACK):i]
    f = res.feat
    out = []
    for t in names:
        c, hi, a = float(f["close"].at[d, t]), float(f["hi252"].at[d, t]), float(f["atr14"].at[d, t])
        out.append({"ticker": t, "mom_12_1": round(float(f["mom"].at[d, t]), 4), "rs_63": round(float(f["rs"].at[d, t]), 4),
                    "pct_from_52w_high": round((c / hi - 1.0) * 100.0, 2), "close": round(c, 2), "atr14": round(a, 4), "atr_pct": round(float(f["atr_pct"].at[d, t]), 2),
                    "adx14": round(float(f["adx14"].at[d, t]), 1), "first_day": bool(not (prior[t].any() if len(prior) else False)),
                    "reference_stop": round(c - S.STOP_ATR_MULT * a, 2)})
    out.sort(key=lambda r: -r["mom_12_1"])
    for k, r in enumerate(out, 1):
        r["rank"] = k
    return out[:limit] if limit else out
