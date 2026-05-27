"""Measure the impact of DSL v1.5 breakeven-after-+0.5R on win rate."""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

scores = pd.read_parquet(ROOT / "data" / "scores_daily.parquet")
panel = pd.read_parquet(ROOT / "data" / "panel_daily.parquet")

# Quick signal detection
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
            for col in ["flow_100", "energy_100", "structure_100", "mp_100", "elder_score", "mp_state"]:
                if col in row.index:
                    sig[col] = row[col] if col == "mp_state" else (float(row[col]) if pd.notna(row[col]) else 0.0)
            signals.append(sig)

sig_df = pd.DataFrame(signals)
sig_df["date"] = pd.to_datetime(sig_df["date"]).dt.normalize()

from src.engines.utils import atr as compute_atr
atr_values = []
for ticker, grp in panel.groupby("ticker"):
    grp = grp.sort_values("date").reset_index(drop=True)
    a = compute_atr(grp["high"], grp["low"], grp["close"], 14)
    df_a = grp[["ticker", "date"]].copy()
    df_a["atr14"] = a.values
    atr_values.append(df_a)
atr_df = pd.concat(atr_values, ignore_index=True)
atr_df["date"] = pd.to_datetime(atr_df["date"]).dt.normalize()
sig_df = sig_df.merge(atr_df, on=["ticker", "date"], how="left").dropna(subset=["atr14"])
sig_df = sig_df.rename(columns={"atr14": "atr14_at_entry"})

print("[BE] Computing DSL v1.5 outcomes (with breakeven-after-+0.5R)...")
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
rs = df["dsl_r_realized"].dropna().values

print("=" * 80)
print("  DSL v1.5 IMPACT ANALYSIS (breakeven-after-+0.5R)")
print("=" * 80)

wins = (rs > 0).sum()
losses = (rs < 0).sum()
be_exits = (rs == 0).sum()
wr = wins / len(rs) * 100 if len(rs) > 0 else 0

print(f"\n  Total trades: {len(rs)}")
print(f"  Winners: {wins} ({wins/len(rs)*100:.1f}%)")
print(f"  Losers:  {losses} ({losses/len(rs)*100:.1f}%)")
print(f"  Breakeven: {be_exits} ({be_exits/len(rs)*100:.1f}%)")
print(f"  Win rate (R > 0): {wr:.1f}%")
print(f"  Avg R: {np.mean(rs):+.4f}")
print(f"  Median R: {np.median(rs):+.4f}")

# Win rate excluding breakeven (only count wins vs losses)
if wins + losses > 0:
    wr_excl = wins / (wins + losses) * 100
    print(f"  Win rate (excl BE): {wr_excl:.1f}%")

# Non-negative rate (wins + breakeven)
non_neg = (rs >= 0).sum()
print(f"  Non-loss rate (R >= 0): {non_neg/len(rs)*100:.1f}%")

# Tier distribution
print("\n  Tier distribution:")
if "dsl_peak_tier" in df.columns:
    for tier in sorted(df["dsl_peak_tier"].dropna().unique()):
        sub = df.loc[df["dsl_peak_tier"] == tier]
        if len(sub) < 5:
            continue
        sub_wr = (sub["dsl_r_realized"] > 0).sum() / len(sub) * 100
        sub_avg = sub["dsl_r_realized"].mean()
        be_count = (sub["dsl_r_realized"] == 0).sum()
        print(f"    Tier {tier:.0f}: {len(sub):5} trades | Win {sub_wr:.1f}% | Avg R {sub_avg:+.3f} | BE exits: {be_count}")

# BE trigger stats
if "dsl_be_triggered" in df.columns:
    be_t = df["dsl_be_triggered"].sum()
    print(f"\n  Breakeven triggered: {be_t}/{len(df)} ({be_t/len(df)*100:.1f}%)")

# Phase breakdown with new DSL
print("\n  By posture phase:")
if "mp_state" in df.columns:
    for phase in ["BUILDING", "STRONG", "FADING"]:
        sub = df.loc[df["mp_state"] == phase]
        if len(sub) >= 20:
            sub_wr = (sub["dsl_r_realized"] > 0).sum() / len(sub) * 100
            sub_avg = sub["dsl_r_realized"].mean()
            sub_nonloss = (sub["dsl_r_realized"] >= 0).sum() / len(sub) * 100
            print(f"    {phase:10}: {len(sub):5} trades | Win {sub_wr:.1f}% | Non-loss {sub_nonloss:.1f}% | Avg R {sub_avg:+.3f}")

# BUILDING only
print("\n  BUILDING phase with DSL v1.5:")
b = df.loc[df["mp_state"] == "BUILDING"]
if len(b) >= 20:
    b_rs = b["dsl_r_realized"].dropna().values
    b_wins = (b_rs > 0).sum()
    b_be = (b_rs == 0).sum()
    b_nonloss = (b_rs >= 0).sum()
    print(f"    Win rate: {b_wins/len(b_rs)*100:.1f}%")
    print(f"    Non-loss rate: {b_nonloss/len(b_rs)*100:.1f}%")
    print(f"    Avg R: {np.mean(b_rs):+.4f}")
