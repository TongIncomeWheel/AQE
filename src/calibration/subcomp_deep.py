"""Deep sub-component search — win rate focused.

The first pass showed loose filters beat on volume, not quality.
This pass targets: highest WIN RATE with minimum 100 trades, 3+ filters.
"""
from __future__ import annotations
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.calibration.subcomp_optimizer import detect_signals, compute_outcomes


def main():
    data_dir = ROOT / "data"
    scores = pd.read_parquet(data_dir / "scores_daily.parquet")
    scores["date"] = pd.to_datetime(scores["date"]).dt.normalize()
    panel = pd.read_parquet(data_dir / "panel_daily.parquet")
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()

    print("Detecting signals...")
    signals = detect_signals(scores)
    print("Computing outcomes...")
    trades = compute_outcomes(signals, panel)
    print(f"{len(trades)} trades total")

    # Targeted grid: features with strongest WR lift
    GRID = {
        "volume_score":  [None, 5, 6],
        "accum_score":   [None, 5, 6],
        "trend_score":   [None, 12, 15],
        "elder_score":   [None, 7, 8, 9],
        "adx_val":       [None, 20, 25, 30],
        "squeeze_score": [None, 5, 8, 10],
        "excess_return": [None, 3, 5, 10],
        "impulse_green": [None, True],  # derived below
        "en_pos50":      [None, 50, 65],
        "ms_p50":        [None, 50, 65],
        "rs_accel":      [None, 3, 5],
    }

    # Derive impulse_green boolean
    if "impulse_state" in trades.columns:
        trades["impulse_green"] = trades["impulse_state"] == "GREEN"

    print()
    print("=" * 70)
    print("  DEEP SEARCH: Win Rate Focused")
    print("  3+ filters, 100+ trades, ranked by win rate")
    print("=" * 70)

    from itertools import product
    features = list(GRID.keys())
    threshold_lists = [GRID[f] for f in features]
    total = 1
    for t in threshold_lists:
        total *= len(t)
    print(f"  Grid: {len(features)} features, {total:,} combos")

    best = []
    t0 = time.time()
    count = 0

    for combo in product(*threshold_lists):
        count += 1
        mask = pd.Series(True, index=trades.index)
        filters = {}
        n_active = 0

        for feat, thresh in zip(features, combo):
            if thresh is None:
                continue
            if feat not in trades.columns:
                continue
            if isinstance(thresh, bool):
                mask &= trades[feat] == thresh
            else:
                mask &= trades[feat] >= thresh
            filters[feat] = thresh
            n_active += 1

        if n_active < 3:
            continue

        n = mask.sum()
        if n < 100:
            continue

        rs = trades.loc[mask, "r_realized"].values
        wins = rs[rs > 0]
        losses = rs[rs <= 0]
        wr = len(wins) / n

        if wr < 0.33:
            continue

        avg_r = float(np.mean(rs))
        avg_win = float(np.mean(wins)) if len(wins) else 0
        avg_loss = float(np.mean(losses)) if len(losses) else 0
        payoff = avg_win / abs(avg_loss) if avg_loss != 0 else 0
        exp = wr * avg_win - (1 - wr) * abs(avg_loss)
        med_r = float(np.median(rs))

        best.append({
            "filters": filters,
            "n": int(n),
            "wr": wr,
            "avg_r": avg_r,
            "med_r": med_r,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "payoff": payoff,
            "exp": exp,
            "n_filters": n_active,
        })

    elapsed = time.time() - t0
    print(f"  Searched {count:,} combos in {elapsed:.1f}s")
    print(f"  Found {len(best)} recipes with WR>33% and 100+ trades")

    # Sort by win rate first, then expectancy
    best.sort(key=lambda x: (-x["wr"], -x["exp"]))

    print()
    print("=" * 70)
    print("  TOP 15 by WIN RATE")
    print("=" * 70)
    for i, r in enumerate(best[:15], 1):
        fstr = " & ".join(f"{k}>={v}" for k, v in r["filters"].items())
        print(f"  #{i}: WR={r['wr']*100:.1f}% | {r['n']:>5} trades | "
              f"AvgR={r['avg_r']:+.3f} | MedR={r['med_r']:+.3f} | "
              f"Payoff={r['payoff']:.2f}:1 | Exp={r['exp']:+.4f}R")
        print(f"       {fstr}")
        print()

    # Now sort by expectancy (quality of edge)
    best.sort(key=lambda x: -x["exp"])
    print("=" * 70)
    print("  TOP 15 by EXPECTANCY (R per trade)")
    print("=" * 70)
    for i, r in enumerate(best[:15], 1):
        fstr = " & ".join(f"{k}>={v}" for k, v in r["filters"].items())
        print(f"  #{i}: Exp={r['exp']:+.4f}R | WR={r['wr']*100:.1f}% | {r['n']:>5} trades | "
              f"AvgR={r['avg_r']:+.3f} | Payoff={r['payoff']:.2f}:1")
        print(f"       {fstr}")
        print()

    # Baseline comparison
    print("=" * 70)
    print("  COMPARISON")
    print("=" * 70)
    rs_all = trades["r_realized"].values
    w_all = rs_all[rs_all > 0]
    l_all = rs_all[rs_all <= 0]
    wr_all = len(w_all) / len(rs_all)
    exp_all = wr_all * np.mean(w_all) - (1-wr_all) * abs(np.mean(l_all))
    print(f"  BASELINE (all signals): WR={wr_all*100:.1f}% | {len(rs_all)} trades | "
          f"Exp={exp_all:+.4f}R")

    agg_mask = (
        (trades["sc_momentum"] >= 75) & (trades["flow_100"] >= 80) &
        (trades["energy_100"] >= 64) & (trades["structure_100"] >= 60) &
        (trades["mp_100"] >= 60) & (trades["elder_score"] >= 7)
    )
    agg = trades[agg_mask]
    if len(agg):
        agg_rs = agg["r_realized"].values
        agg_w = agg_rs[agg_rs > 0]
        agg_l = agg_rs[agg_rs <= 0]
        agg_wr = len(agg_w) / len(agg)
        agg_exp = agg_wr * np.mean(agg_w) - (1-agg_wr) * abs(np.mean(agg_l))
        print(f"  CURRENT RECIPE (agg): WR={agg_wr*100:.1f}% | {len(agg)} trades | "
              f"Exp={agg_exp:+.4f}R")

    print("=" * 70)


if __name__ == "__main__":
    main()
