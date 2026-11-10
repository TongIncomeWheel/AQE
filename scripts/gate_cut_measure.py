#!/usr/bin/env python3
"""gate_cut_measure.py -- READ-ONLY measurement (PM 2026-11-10): how many big movers did the shortlist gate cut on the day before the move started?

Gate under test: SC_MOMENTUM >= 45 AND Elder >= 7 (the shortlist floor plus the longlist's Elder floor). Nothing is recommended and nothing is changed: numbers only.

For every name in the scored universe on a date (scores_daily), a "big move" is a rise of >= 30% within the next 20 trading sessions. Two cuts of the same event set:
  (1) FIRST DAY: the earliest scored day of each run of consecutive qualifying days -- the first day the move was already coming;
  (2) TROUGH: the move's actual start -- for each run, the peak day p (highest close in the following 20 sessions) and the lowest close s between the run's first day and p;
      only kept if close[p]/close[s]-1 >= 30%. The gate state is read ON the trough day s, the last day before the move began.
Each is reported with: how many the gate cut, split by reason (SC only, Elder only, both), the SC and Elder quartiles of the cut names, and the split by
whether the name closed below its own 50-day average that day. Survivorship: the scored universe is today's rule applied to history.

    python -m scripts.gate_cut_measure [--sc 45] [--elder 7] [--move 0.30] [--horizon 20]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load():
    from src.data.paths import DATA_DIR
    sc, px = DATA_DIR / "scores_daily.parquet", DATA_DIR / "panel_daily.parquet"
    if not (sc.exists() and px.exists()):
        from src.data import persist
        print("[measure] restoring the state snapshot ...", flush=True)
        print(persist.load_snapshot_best(only=["scores_daily.parquet", "panel_daily.parquet"]), flush=True)
    s = pd.read_parquet(sc, columns=["date", "ticker", "sc_momentum", "elder_score"])
    p = pd.read_parquet(px, columns=["date", "ticker", "close"])
    for d in (s, p):
        d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    return s, p


def q(x):
    x = pd.Series(x).dropna()
    return {"n": int(len(x)), "p25": round(float(x.quantile(.25)), 1), "median": round(float(x.median()), 1), "p75": round(float(x.quantile(.75)), 1)} if len(x) else {"n": 0}


def summarise(df, sc_min, el_min):
    cut_sc = df["sc"] < sc_min
    cut_el = df["elder"] < el_min
    cut = cut_sc | cut_el
    def part(m):
        d = df[m]
        c = cut[m]
        return {"events": int(len(d)), "cut": int(c.sum()), "cut_pct": round(100 * float(c.mean()), 1) if len(d) else None,
                "cut_by_sc_only": int((cut_sc & ~cut_el)[m].sum()), "cut_by_elder_only": int((cut_el & ~cut_sc)[m].sum()), "cut_by_both": int((cut_sc & cut_el)[m].sum()),
                "sc_of_cut": q(d.loc[c, "sc"]), "elder_of_cut": q(d.loc[c, "elder"]), "sc_of_passed": q(d.loc[~c, "sc"]), "elder_of_passed": q(d.loc[~c, "elder"])}
    below = df["below50"] == True  # noqa: E712
    return {"all": part(pd.Series(True, index=df.index)), "below_50day": part(below), "at_or_above_50day": part(~below & df["below50"].notna())}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--sc", type=float, default=45.0); ap.add_argument("--elder", type=float, default=7.0)
    ap.add_argument("--move", type=float, default=0.30); ap.add_argument("--horizon", type=int, default=20)
    a = ap.parse_args(argv)
    s, p = load()
    dates = sorted(s["date"].unique())
    print(f"[measure] scored dates: {len(dates)} ({pd.Timestamp(dates[0]).date()} .. {pd.Timestamp(dates[-1]).date()}); scored rows {len(s):,}; tickers {s['ticker'].nunique()}")
    H = a.horizon
    rows_first, rows_trough, base_n, base_cut = [], [], 0, 0
    pv = p.sort_values(["ticker", "date"])
    sc_idx = s.set_index(["ticker", "date"])[["sc_momentum", "elder_score"]]
    for tk, g in pv.groupby("ticker", sort=False):
        g = g.reset_index(drop=True)
        c = g["close"].astype(float).to_numpy()
        n = len(c)
        if n < H + 2:
            continue
        ma50 = pd.Series(c).rolling(50, min_periods=50).mean().to_numpy()
        fwd = np.full(n, np.nan)
        for i in range(n - 1):
            w = c[i + 1:i + 1 + H]
            if len(w) == H:                       # only days with a FULL forward window are judged
                fwd[i] = w.max() / c[i] - 1.0
        ok = fwd >= a.move
        # scored-on-that-day mask
        scored = np.array([(tk, d) in sc_idx.index for d in g["date"]])
        valid = ~np.isnan(fwd) & scored
        base_n += int(valid.sum())
        i = 0
        while i < n:
            if ok[i] and scored[i]:
                j = i
                while j + 1 < n and ok[j + 1]:
                    j += 1
                run_end = j
                # peak day: highest close in the 20 sessions after the first day of the run
                win = c[i + 1:i + 1 + H]
                pk = i + 1 + int(np.argmax(win))
                seg = c[i:pk + 1]
                sidx = i + int(np.argmin(seg))
                def rec(k):
                    key = (tk, g["date"].iloc[k])
                    if key not in sc_idx.index:
                        return None
                    r = sc_idx.loc[key]
                    r = r.iloc[0] if isinstance(r, pd.DataFrame) else r
                    return {"ticker": tk, "date": g["date"].iloc[k], "sc": float(r["sc_momentum"]) if pd.notna(r["sc_momentum"]) else np.nan,
                            "elder": float(r["elder_score"]) if pd.notna(r["elder_score"]) else np.nan,
                            "below50": (bool(c[k] < ma50[k]) if not np.isnan(ma50[k]) else None)}
                r1 = rec(i)
                if r1: rows_first.append(r1)
                if c[pk] / c[sidx] - 1.0 >= a.move:
                    r2 = rec(sidx)
                    if r2: rows_trough.append(r2)
                i = run_end + 1
            else:
                i += 1
    # base rate: how often does the gate pass a random scored name-day
    allv = s.dropna(subset=["sc_momentum", "elder_score"])
    base_pass = float(((allv["sc_momentum"] >= a.sc) & (allv["elder_score"] >= a.elder)).mean())
    out = {"gate": {"sc_momentum_min": a.sc, "elder_min": a.elder}, "move": {"rise": a.move, "within_sessions": H},
           "data": {"scored_dates": len(dates), "first": str(pd.Timestamp(dates[0]).date()), "last": str(pd.Timestamp(dates[-1]).date()), "scored_rows": int(len(s)),
                    "tickers": int(s["ticker"].nunique()), "judged_name_days": base_n},
           "gate_passes_this_share_of_all_scored_name_days": round(100 * base_pass, 1)}
    for label, rows in (("first_day_of_move_window", rows_first), ("trough_day_the_day_before_the_move", rows_trough)):
        df = pd.DataFrame(rows)
        out[label] = summarise(df, a.sc, a.elder) if len(df) else {"events": 0}
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
