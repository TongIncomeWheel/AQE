#!/usr/bin/env python3
"""Panel-before-vote harness (constitution: Design & Review step 5).
Measures a field-conditional proposal on the enriched panel BEFORE the committee votes.
Usage:
  python3 measure_proposal.py --panel data/enriched_panel.parquet \
    --condition "structure_shift == 'BEARISH_CHOCH'" --pool "sc_momentum >= 75" \
    --outcome fwd_max_20d --thresholds 10 20
Prints n, hit rates vs complement, and the volatility-tercile control (the confound that fooled R1).
"""
import argparse
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True); ap.add_argument("--condition", required=True)
    ap.add_argument("--pool", default=None); ap.add_argument("--outcome", default="fwd_max_20d")
    ap.add_argument("--thresholds", nargs="+", type=float, default=[10.0, 20.0])
    a = ap.parse_args()
    df = pd.read_parquet(a.panel)
    if a.pool: df = df.query(a.pool)
    cond, comp = df.query(a.condition), df.query(f"not ({a.condition})")
    print(f"pool={len(df)}  condition n={len(cond)}  complement n={len(comp)}")
    for th in a.thresholds:
        print(f">= +{th}%: condition {(cond[a.outcome] >= th).mean():.1%}  vs complement {(comp[a.outcome] >= th).mean():.1%}")
    if "atr_pct" in df.columns:
        df = df.assign(_terc=pd.qcut(df["atr_pct"], 3, labels=["lowVol", "midVol", "highVol"]))
        print("\nvolatility-tercile control (is the tercile doing the work?):")
        for t, g in df.groupby("_terc", observed=True):
            c, x = g.query(a.condition), g.query(f"not ({a.condition})")
            if len(c) > 30 and len(x) > 30:
                th = a.thresholds[-1]
                print(f"  {t}: condition {(c[a.outcome] >= th).mean():.1%} (n={len(c)}) vs complement {(x[a.outcome] >= th).mean():.1%} (n={len(x)})")
    print("\nRULE: no committee vote on this proposal until these numbers are in the briefing.")

if __name__ == "__main__":
    main()
