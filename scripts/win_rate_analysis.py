"""Deep win rate analysis — what drives losses and how to reach 52%+."""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

scores = pd.read_parquet(ROOT / "data" / "scores_daily.parquet")
panel = pd.read_parquet(ROOT / "data" / "panel_daily.parquet")

# Detect crossup signals
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
            for col in ["flow_100", "energy_100", "structure_100", "mp_100",
                        "elder_score", "mp_state", "bq_100", "k39_value"]:
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
print("  WIN RATE ANALYSIS — What drives losses and how to reach 52%+")
print("=" * 80)

# 1. R distribution
print("\n--- R-MULTIPLE DISTRIBUTION ---")
print(f"  Mean: {np.mean(rs):+.3f}  Median: {np.median(rs):+.3f}  Std: {np.std(rs):.3f}")
for thresh in [-0.5, -0.25, 0.0, 0.1, 0.25]:
    pct = (rs > thresh).sum() / len(rs) * 100
    print(f"  R > {thresh:+.2f}: {pct:.1f}%")

# 2. Winner/loser anatomy
winners = rs[rs > 0]
losers = rs[rs <= 0]
print(f"\n--- WINNER / LOSER ANATOMY ---")
print(f"  Winners: {len(winners)} ({len(winners)/len(rs)*100:.1f}%) | avg R {np.mean(winners):+.3f}")
print(f"  Losers:  {len(losers)} ({len(losers)/len(rs)*100:.1f}%) | avg R {np.mean(losers):+.3f}")
print(f"  Loser percentiles: 10th={np.percentile(losers, 10):+.3f}  25th={np.percentile(losers, 25):+.3f}  "
      f"50th={np.percentile(losers, 50):+.3f}  75th={np.percentile(losers, 75):+.3f}")

# 3. DSL tier analysis
print("\n--- EXIT BY DSL TIER ---")
if "dsl_peak_tier" in df.columns:
    for tier in sorted(df["dsl_peak_tier"].dropna().unique()):
        sub = df.loc[df["dsl_peak_tier"] == tier]
        if len(sub) < 10:
            continue
        wr = (sub["dsl_r_realized"] > 0).sum() / len(sub) * 100
        avg = sub["dsl_r_realized"].mean()
        print(f"  Tier {tier}: {len(sub):5} trades | Win {wr:.1f}% | Avg R {avg:+.3f}")

# 4. Fixed-bar exit comparison
print("\n--- FIXED-BAR EXIT WIN RATES ---")
for col, label in [("r_5d", "5-day"), ("r_10d", "10-day"), ("r_21d", "21-day")]:
    if col in df.columns:
        vals = df[col].dropna().values
        wr = (vals > 0).sum() / len(vals) * 100
        avg = np.mean(vals) * 100
        print(f"  {label}: Win {wr:.1f}% | Avg return {avg:+.2f}%")

# 5. Phase analysis
print("\n--- WIN RATE BY POSTURE PHASE ---")
if "mp_state" in df.columns:
    for phase in ["BUILDING", "STRONG", "FADING"]:
        sub = df.loc[df["mp_state"] == phase]
        if len(sub) >= 20:
            wr = (sub["dsl_r_realized"] > 0).sum() / len(sub) * 100
            avg = sub["dsl_r_realized"].mean()
            print(f"  {phase:10}: {len(sub):5} trades | Win {wr:.1f}% | Avg R {avg:+.3f}")

# 6. Elder analysis
print("\n--- WIN RATE BY ELDER IMPULSE ---")
if "elder_score" in df.columns:
    for label, lo, hi in [("Low (0-5)", 0, 5), ("Mid (5-8)", 5, 8), ("High (8-10)", 8, 10.01)]:
        sub = df.loc[(df["elder_score"] >= lo) & (df["elder_score"] < hi)]
        if len(sub) >= 20:
            wr = (sub["dsl_r_realized"] > 0).sum() / len(sub) * 100
            avg = sub["dsl_r_realized"].mean()
            print(f"  {label:15}: {len(sub):5} trades | Win {wr:.1f}% | Avg R {avg:+.3f}")

# 7. BQ analysis
print("\n--- WIN RATE BY BASE QUALITY ---")
if "bq_100" in df.columns:
    for label, lo, hi in [("Low (0-50)", 0, 50), ("Mid (50-75)", 50, 75), ("High (75+)", 75, 100.01)]:
        sub = df.loc[(df["bq_100"] >= lo) & (df["bq_100"] < hi)]
        if len(sub) >= 20:
            wr = (sub["dsl_r_realized"] > 0).sum() / len(sub) * 100
            avg = sub["dsl_r_realized"].mean()
            print(f"  {label:15}: {len(sub):5} trades | Win {wr:.1f}% | Avg R {avg:+.3f}")

# 8. Stacked filters for maximum win rate
print("\n--- STACKED FILTERS (combining for higher win rate) ---")
combos = [
    ("BUILDING only", df["mp_state"] == "BUILDING"),
    ("BUILDING + Elder>=7", (df["mp_state"] == "BUILDING") & (df["elder_score"] >= 7)),
    ("BUILDING + Elder>=8", (df["mp_state"] == "BUILDING") & (df["elder_score"] >= 8)),
    ("Elder>=8 (any phase)", df["elder_score"] >= 8),
    ("Elder>=9 (any phase)", df["elder_score"] >= 9),
]
if "bq_100" in df.columns:
    combos.extend([
        ("BQ>=70", df["bq_100"] >= 70),
        ("BQ>=80", df["bq_100"] >= 80),
        ("BUILDING + BQ>=70", (df["mp_state"] == "BUILDING") & (df["bq_100"] >= 70)),
        ("BUILDING + Elder>=7 + BQ>=70",
         (df["mp_state"] == "BUILDING") & (df["elder_score"] >= 7) & (df["bq_100"] >= 70)),
        ("Elder>=8 + BQ>=70",
         (df["elder_score"] >= 8) & (df["bq_100"] >= 70)),
    ])

for label, filt in combos:
    sub = df.loc[filt]
    if len(sub) >= 10:
        wr = (sub["dsl_r_realized"] > 0).sum() / len(sub) * 100
        avg = sub["dsl_r_realized"].mean()
        marker = " <-- 52%+" if wr >= 52 else ""
        print(f"  {label:35}: {len(sub):5} trades | Win {wr:.1f}% | Avg R {avg:+.3f}{marker}")

# 9. Alternative exit: what if we used a tighter initial stop?
print("\n--- ALTERNATIVE EXIT: TIGHTER STOP (-0.5R instead of -1R) ---")
tight_rs = np.clip(rs, -0.5, None)
wr_tight = (tight_rs > 0).sum() / len(tight_rs) * 100
print(f"  Win rate: {wr_tight:.1f}% (vs current {(rs > 0).sum()/len(rs)*100:.1f}%)")
print(f"  Avg R: {np.mean(tight_rs):+.3f} (vs current {np.mean(rs):+.3f})")

# 10. Alternative: time-based profit lock (exit after 10 bars if profitable)
print("\n--- ALTERNATIVE: EARLY EXIT AT +0.5R PROFIT TARGET ---")
capped_rs = np.where(rs > 0.5, 0.5, rs)
wr_cap = (capped_rs > 0).sum() / len(capped_rs) * 100
print(f"  Win rate: {wr_cap:.1f}% | Avg R: {np.mean(capped_rs):+.3f}")
print(f"  (Same winners, just capped profits — win rate unchanged but avg R lower)")

# 11. What if we counted ANY positive exit as a win, regardless of R?
print("\n--- R BREAKPOINTS: WHERE DOES 52% LIVE? ---")
for cutoff in np.arange(-0.6, 0.1, 0.05):
    wr = (rs > cutoff).sum() / len(rs) * 100
    if 48 <= wr <= 56:
        print(f"  R > {cutoff:+.2f}: {wr:.1f}%")

print("\n" + "=" * 80)
print("  CONCLUSION")
print("=" * 80)
overall_wr = (rs > 0).sum() / len(rs) * 100
print(f"\n  Current win rate: {overall_wr:.1f}% (R > 0)")
print(f"  The DSL trailing stop creates large winners but frequent small losers.")
print(f"  To reach 52%, the EXIT logic must change — entry filters alone cannot do it.")
print(f"  Options: tighter stop, earlier profit-taking, or hybrid exit.")
