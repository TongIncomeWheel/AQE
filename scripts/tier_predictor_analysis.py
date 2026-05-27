"""What predicts whether a trade reaches +1R (Tier 2+) vs dying in Tier 1?

If we can filter OUT the Tier-1 losers at entry, win rate jumps
while keeping the 2:1+ R:R character intact.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

scores = pd.read_parquet(ROOT / "data" / "scores_daily.parquet")
panel = pd.read_parquet(ROOT / "data" / "panel_daily.parquet")

# Detect crossup signals with ALL available features
signals = []
scores_sorted = scores.sort_values(["ticker", "date"]).reset_index(drop=True)
for ticker, grp in scores_sorted.groupby("ticker"):
    grp = grp.sort_values("date").reset_index(drop=True)
    if "sc_momentum" not in grp.columns:
        continue
    sc = grp["sc_momentum"].values
    for i in range(1, len(sc)):
        if sc[i] >= 50.0 and sc[i - 1] < 50.0:
            row = grp.iloc[i]
            sig = {"ticker": ticker, "date": row["date"], "sc_momentum": float(sc[i])}
            for col in grp.columns:
                if col not in ("ticker", "date", "sc_momentum") and col in row.index:
                    val = row[col]
                    if isinstance(val, str):
                        sig[col] = val
                    elif pd.notna(val):
                        sig[col] = float(val)
                    else:
                        sig[col] = 0.0
            # Capture momentum ACCELERATION (today's sc_mom - yesterday's)
            sig["sc_mom_delta"] = float(sc[i] - sc[i - 1])
            signals.append(sig)

sig_df = pd.DataFrame(signals)
sig_df["date"] = pd.to_datetime(sig_df["date"]).dt.normalize()

from src.engines.utils import atr as compute_atr

# Add ATR and price-relative-to-ATR features
atr_values = []
for ticker, grp in panel.groupby("ticker"):
    grp = grp.sort_values("date").reset_index(drop=True)
    a = compute_atr(grp["high"], grp["low"], grp["close"], 14)
    df_a = grp[["ticker", "date"]].copy()
    df_a["atr14"] = a.values
    df_a["close_price"] = grp["close"].values
    df_a["volume"] = grp["volume"].values
    # Rolling volume average (20-day)
    df_a["vol_avg_20"] = grp["volume"].rolling(20).mean().values
    # Day's range relative to ATR (how compressed is today?)
    df_a["range_pct_atr"] = ((grp["high"] - grp["low"]) / a).values
    # Close position within day's range
    day_range = grp["high"] - grp["low"]
    df_a["close_in_range"] = ((grp["close"] - grp["low"]) / day_range.replace(0, np.nan)).values
    atr_values.append(df_a)

atr_df = pd.concat(atr_values, ignore_index=True)
atr_df["date"] = pd.to_datetime(atr_df["date"]).dt.normalize()
sig_df = sig_df.merge(atr_df, on=["ticker", "date"], how="left", suffixes=("", "_panel"))
sig_df = sig_df.dropna(subset=["atr14"])
sig_df = sig_df.rename(columns={"atr14": "atr14_at_entry"})

# Volume ratio at entry
sig_df["vol_ratio"] = sig_df["volume"] / sig_df["vol_avg_20"].replace(0, np.nan)

from src.scanner.dsl import compute_dsl_outcomes

outcomes = compute_dsl_outcomes(sig_df, panel, max_bars=63)

# Apply best recipe
mask = (
    (outcomes["sc_momentum"] >= 75)
    & (outcomes["flow_100"] >= 80)
    & (outcomes["energy_100"] >= 64)
    & (outcomes["structure_100"] >= 60)
    & (outcomes["mp_100"] >= 65)
)
df = outcomes.loc[mask].copy()

# Tag: did the trade reach Tier 2+?
df["reached_1r"] = df["dsl_peak_tier"] >= 2.0
df["winner"] = df["dsl_r_realized"] > 0

print("=" * 80)
print("  TIER PREDICTOR ANALYSIS — What at entry predicts reaching +1R?")
print("=" * 80)
print(f"\n  Total trades: {len(df)}")
print(f"  Reached +1R (Tier 2+): {df['reached_1r'].sum()} ({df['reached_1r'].mean()*100:.1f}%)")
print(f"  Win rate (R > 0): {df['winner'].mean()*100:.1f}%")

# Feature importance via win rate split
print("\n--- FEATURE ANALYSIS: TOP vs BOTTOM HALF ---")
features = [
    ("sc_momentum", "SC Momentum"),
    ("flow_100", "Flow"),
    ("energy_100", "Energy"),
    ("structure_100", "Structure"),
    ("mp_100", "MP"),
    ("elder_score", "Elder Impulse"),
    ("sc_mom_delta", "SC Momentum Jump"),
    ("vol_ratio", "Volume Ratio"),
    ("close_in_range", "Close in Range"),
    ("range_pct_atr", "Day Range/ATR"),
]

print(f"\n  {'Feature':25} {'High half WR':>12} {'Low half WR':>12} {'Diff':>8} {'High 1R%':>10} {'Low 1R%':>10} {'1R Diff':>8}")
print("  " + "-" * 87)

useful_features = []
for col, name in features:
    if col not in df.columns:
        continue
    vals = df[col].dropna()
    if len(vals) < 100:
        continue
    median = vals.median()
    high = df.loc[df[col] >= median]
    low = df.loc[df[col] < median]
    if len(high) < 30 or len(low) < 30:
        continue
    wr_hi = high["winner"].mean() * 100
    wr_lo = low["winner"].mean() * 100
    r1_hi = high["reached_1r"].mean() * 100
    r1_lo = low["reached_1r"].mean() * 100
    diff = wr_hi - wr_lo
    r1_diff = r1_hi - r1_lo
    marker = " ***" if abs(diff) > 3 else " *" if abs(diff) > 1.5 else ""
    print(f"  {name:25} {wr_hi:10.1f}%  {wr_lo:10.1f}%  {diff:+6.1f}%  {r1_hi:8.1f}%  {r1_lo:8.1f}%  {r1_diff:+6.1f}%{marker}")
    if abs(diff) > 1.5:
        useful_features.append((col, name, diff))

# Posture phase analysis for Tier 2+ rate
print("\n--- POSTURE PHASE -> TIER 2+ RATE ---")
if "mp_state" in df.columns:
    for phase in ["BUILDING", "STRONG", "FADING"]:
        sub = df.loc[df["mp_state"] == phase]
        if len(sub) >= 20:
            wr = sub["winner"].mean() * 100
            r1 = sub["reached_1r"].mean() * 100
            avg_r = sub["dsl_r_realized"].mean()
            print(f"  {phase:10}: {len(sub):5} trades | Win {wr:.1f}% | Reach +1R: {r1:.1f}% | Avg R {avg_r:+.3f}")

# Volume confirmation analysis
print("\n--- VOLUME AT ENTRY -> WIN RATE ---")
if "vol_ratio" in df.columns:
    vr = df["vol_ratio"].dropna()
    for label, lo, hi in [
        ("Low vol (<0.8x avg)", 0, 0.8),
        ("Normal (0.8-1.2x)", 0.8, 1.2),
        ("Above avg (1.2-2x)", 1.2, 2.0),
        ("High vol (2x+)", 2.0, 999),
    ]:
        sub = df.loc[(df["vol_ratio"] >= lo) & (df["vol_ratio"] < hi)]
        if len(sub) >= 20:
            wr = sub["winner"].mean() * 100
            r1 = sub["reached_1r"].mean() * 100
            avg_r = sub["dsl_r_realized"].mean()
            print(f"  {label:25}: {len(sub):5} trades | Win {wr:.1f}% | +1R: {r1:.1f}% | Avg R {avg_r:+.3f}")

# SC momentum jump size
print("\n--- SC MOMENTUM JUMP SIZE -> WIN RATE ---")
if "sc_mom_delta" in df.columns:
    for label, lo, hi in [
        ("Small jump (<5pt)", 0, 5),
        ("Medium (5-15pt)", 5, 15),
        ("Large (15-30pt)", 15, 30),
        ("Huge (30pt+)", 30, 999),
    ]:
        sub = df.loc[(df["sc_mom_delta"] >= lo) & (df["sc_mom_delta"] < hi)]
        if len(sub) >= 20:
            wr = sub["winner"].mean() * 100
            r1 = sub["reached_1r"].mean() * 100
            avg_r = sub["dsl_r_realized"].mean()
            print(f"  {label:25}: {len(sub):5} trades | Win {wr:.1f}% | +1R: {r1:.1f}% | Avg R {avg_r:+.3f}")

# Close position in day range
print("\n--- CLOSE IN DAY RANGE -> WIN RATE ---")
if "close_in_range" in df.columns:
    for label, lo, hi in [
        ("Closed near low (0-33%)", 0, 0.33),
        ("Closed mid (33-66%)", 0.33, 0.66),
        ("Closed near high (66%+)", 0.66, 1.01),
    ]:
        sub = df.loc[(df["close_in_range"] >= lo) & (df["close_in_range"] < hi)]
        if len(sub) >= 20:
            wr = sub["winner"].mean() * 100
            r1 = sub["reached_1r"].mean() * 100
            avg_r = sub["dsl_r_realized"].mean()
            print(f"  {label:30}: {len(sub):5} trades | Win {wr:.1f}% | +1R: {r1:.1f}% | Avg R {avg_r:+.3f}")

# Best combo: stack all positive features
print("\n--- BEST STACKED ENTRY FILTERS ---")
combos = []

# Start with base recipe (already applied)
base = df.copy()
combos.append(("Base recipe", base))

if "mp_state" in df.columns:
    combos.append(("+ BUILDING phase", df.loc[df["mp_state"] == "BUILDING"]))
    combos.append(("+ BUILDING or STRONG", df.loc[df["mp_state"].isin(["BUILDING", "STRONG"])]))

if "vol_ratio" in df.columns:
    combos.append(("+ Volume > 1.0x avg", df.loc[df["vol_ratio"] >= 1.0]))
    combos.append(("+ Volume > 1.2x avg", df.loc[df["vol_ratio"] >= 1.2]))

if "close_in_range" in df.columns:
    combos.append(("+ Close > 50% of range", df.loc[df["close_in_range"] >= 0.5]))
    combos.append(("+ Close > 66% of range", df.loc[df["close_in_range"] >= 0.66]))

if "sc_mom_delta" in df.columns:
    combos.append(("+ SC jump > 10pt", df.loc[df["sc_mom_delta"] >= 10]))

# Multi-feature combos
if "mp_state" in df.columns and "vol_ratio" in df.columns:
    combos.append(("+ BUILDING + Vol>1.2x",
                   df.loc[(df["mp_state"] == "BUILDING") & (df["vol_ratio"] >= 1.2)]))

if "mp_state" in df.columns and "close_in_range" in df.columns:
    combos.append(("+ BUILDING + Close>66%",
                   df.loc[(df["mp_state"] == "BUILDING") & (df["close_in_range"] >= 0.66)]))

if "close_in_range" in df.columns and "vol_ratio" in df.columns:
    combos.append(("+ Close>66% + Vol>1.0x",
                   df.loc[(df["close_in_range"] >= 0.66) & (df["vol_ratio"] >= 1.0)]))

if all(c in df.columns for c in ["mp_state", "close_in_range", "vol_ratio"]):
    combos.append(("+ BUILDING + Close>66% + Vol>1x",
                   df.loc[(df["mp_state"] == "BUILDING") & (df["close_in_range"] >= 0.66) & (df["vol_ratio"] >= 1.0)]))

print(f"\n  {'Filter':45} {'N':>5} {'Win%':>6} {'+1R%':>6} {'AvgR':>7} {'T/wk':>5}")
print("  " + "-" * 75)
date_range_weeks = max(1, (df["date"].max() - df["date"].min()).days / 7)
for label, sub in combos:
    if len(sub) >= 15:
        wr = sub["winner"].mean() * 100
        r1 = sub["reached_1r"].mean() * 100
        avg_r = sub["dsl_r_realized"].mean()
        tpw = len(sub) / date_range_weeks
        marker = " <<<" if wr >= 45 else ""
        print(f"  {label:45} {len(sub):5} {wr:5.1f}% {r1:5.1f}% {avg_r:+.3f} {tpw:5.1f}{marker}")
