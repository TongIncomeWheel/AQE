"""TP Analysis v2 — Three-bucket breakdown + absolute flow floor tests.

Tests whether exit-when-flow-drops-below-X works better than relative drop.
"""
from __future__ import annotations
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.scanner.dsl import compute_initial_stop
from src.engines.utils import atr as compute_atr
from src.calibration.tp_analysis import TPRule, run_tp_backtest


def three_bucket(label, df):
    v = df.dropna(subset=["r_realized"])
    n = len(v)
    if n == 0:
        print(f"  {label}: no trades")
        return
    wins = (v["r_realized"] > 0.05).sum()
    be = ((v["r_realized"] >= -0.05) & (v["r_realized"] <= 0.05)).sum()
    losses = (v["r_realized"] < -0.05).sum()
    tp_n = int(v["tp_fired"].sum()) if "tp_fired" in v.columns else 0
    avg_r = v["r_realized"].mean()
    w_avg = v.loc[v["r_realized"] > 0.05, "r_realized"].mean() if wins > 0 else 0
    l_avg = v.loc[v["r_realized"] < -0.05, "r_realized"].mean() if losses > 0 else 0
    print(f"  {label:44s} | N={n:5d} | WIN {wins:4d} ({100*wins/n:5.1f}%) | BE {be:4d} ({100*be/n:5.1f}%) | LOSS {losses:4d} ({100*losses/n:5.1f}%) | AvgR={avg_r:+.4f} | W={w_avg:+.3f} L={l_avg:+.3f} | TP={tp_n}")


def build_signals(scores, panel):
    """Build signal population with recipe filter."""
    COOLDOWN, THRESHOLD = 5, 50.0
    sigs = []
    for ticker, grp in scores.sort_values(["ticker", "date"]).groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        if "sc_momentum" not in grp.columns:
            continue
        sc = grp["sc_momentum"].values
        bars_since = COOLDOWN + 1
        for i in range(len(sc)):
            bars_since += 1
            if sc[i] >= THRESHOLD and bars_since > COOLDOWN:
                row = grp.iloc[i]
                sig = {"ticker": ticker, "date": row["date"], "sc_momentum": float(sc[i])}
                for col in ["flow_100", "energy_100", "structure_100", "mp_100",
                            "elder_score", "squeeze_score", "fip_quality"]:
                    if col in row.index:
                        sig[col] = float(row[col]) if pd.notna(row[col]) else 0.0
                if "mp_state" in row.index and pd.notna(row["mp_state"]):
                    sig["mp_state"] = str(row["mp_state"])
                sigs.append(sig)
                bars_since = 0

    sig_df = pd.DataFrame(sigs)

    # Add ATR
    atr_values = []
    for ticker, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        a = compute_atr(grp["high"], grp["low"], grp["close"], 14)
        df_a = grp[["ticker", "date"]].copy()
        df_a["atr14"] = a.values
        atr_values.append(df_a)
    atr_df = pd.concat(atr_values, ignore_index=True)
    atr_df["date"] = pd.to_datetime(atr_df["date"]).dt.normalize()
    sig_df["date"] = pd.to_datetime(sig_df["date"]).dt.normalize()
    sig_df = sig_df.merge(atr_df, on=["ticker", "date"], how="left").dropna(subset=["atr14"])
    sig_df = sig_df.rename(columns={"atr14": "atr14_at_entry"})

    # Recipe filter
    mask = (
        (sig_df["sc_momentum"] >= 75) & (sig_df["flow_100"] >= 72) &
        (sig_df["energy_100"] >= 64) & (sig_df["structure_100"] >= 60) &
        (sig_df["mp_100"] >= 60)
    )
    if "elder_score" in sig_df.columns:
        mask &= sig_df["elder_score"] >= 8
    return sig_df[mask].copy().reset_index(drop=True)


def run_absolute_floor_test(filtered, panel_groups, scores_groups, floor_value,
                            min_r=0.2, grace=2, max_bars=63):
    """Test TP when current flow drops BELOW an absolute level."""
    results = []
    for _, row in filtered.iterrows():
        ticker = row["ticker"]
        bars = panel_groups.get(ticker)
        score_bars = scores_groups.get(ticker)
        if bars is None or bars.empty or score_bars is None:
            results.append({"r_realized": np.nan, "tp_fired": False})
            continue

        bars_dates = bars["date"].to_numpy()
        date_to_idx = {d: i for i, d in enumerate(bars_dates)}
        entry_idx = date_to_idx.get(np.datetime64(row["date"], "ns"))
        if entry_idx is None:
            results.append({"r_realized": np.nan, "tp_fired": False})
            continue

        entry_price = float(bars["close"].iloc[entry_idx])
        atr14 = float(row.get("atr14_at_entry", np.nan))
        if not np.isfinite(atr14) or atr14 <= 0:
            results.append({"r_realized": np.nan, "tp_fired": False})
            continue

        low_start = max(0, entry_idx - 4)
        recent_lows = bars["low"].iloc[low_start:entry_idx + 1].astype(float).to_numpy()
        initial_stop, risk = compute_initial_stop(entry_price, atr14, recent_lows)

        fwd_start = entry_idx + 1
        fwd_end = min(fwd_start + max_bars, len(bars))
        if fwd_start >= len(bars):
            results.append({"r_realized": np.nan, "tp_fired": False})
            continue

        score_dates_arr = score_bars["date"].to_numpy()
        score_date_idx = {d: i for i, d in enumerate(score_dates_arr)}
        fwd_dates = bars["date"].iloc[fwd_start:fwd_end].to_numpy()
        fwd_o = bars["open"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_h = bars["high"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_l = bars["low"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_c = bars["close"].iloc[fwd_start:fwd_end].astype(float).to_numpy()

        n = len(fwd_c)
        target_2r = entry_price + 2.0 * risk
        trail_stop = initial_stop
        highest_tier = 1
        be_triggered = False
        peak_r = 0.0
        tp_fired = False
        exit_r = np.nan

        for i in range(min(n, max_bars)):
            bo = float(fwd_o[i])
            bh = float(fwd_h[i])
            bl = float(fwd_l[i])
            bc = float(fwd_c[i])

            if bo <= trail_stop:
                exit_r = (bo - entry_price) / risk
                break
            if bl <= trail_stop:
                exit_r = (trail_stop - entry_price) / risk
                break

            current_r = (bc - entry_price) / risk
            high_r = (bh - entry_price) / risk
            peak_r = max(peak_r, high_r)
            if not be_triggered and high_r >= 0.5:
                be_triggered = True
            if current_r >= 4.0 and highest_tier < 4:
                highest_tier = 4
            elif current_r >= 2.0 and highest_tier < 3:
                highest_tier = 3
            elif current_r >= 1.0 and highest_tier < 2:
                highest_tier = 2

            # Absolute floor TP
            if i >= grace and current_r >= min_r and highest_tier <= 1:
                sidx = score_date_idx.get(fwd_dates[i]) if i < len(fwd_dates) else None
                if sidx is not None:
                    cur_flow = score_bars["flow_100"].iloc[sidx]
                    cur_flow = float(cur_flow) if pd.notna(cur_flow) else 100.0
                    if cur_flow < floor_value:
                        exit_r = current_r
                        tp_fired = True
                        break

            # Trail update
            if highest_tier == 1:
                nt = bl - 1.0 * atr14
                if be_triggered:
                    nt = max(nt, entry_price)
            elif highest_tier == 2:
                nt = max(bl - 1.5 * atr14, entry_price)
            elif highest_tier == 3:
                nt = max(bl - 2.0 * atr14, entry_price + 1.5 * risk)
            else:
                nt = max(max(bl - 2.5 * atr14, target_2r - 1.0 * atr14), entry_price + 3.0 * risk)
            trail_stop = max(trail_stop, nt)
        else:
            exit_r = (float(fwd_c[min(n, max_bars) - 1]) - entry_price) / risk

        results.append({"r_realized": exit_r, "tp_fired": tp_fired})

    return pd.DataFrame(results)


def run_combo_test(filtered, panel_groups, scores_groups, drop_thresh, floor_value,
                   min_r=0.2, grace=2, max_bars=63):
    """Test TP requiring BOTH relative drop AND absolute floor breach."""
    results = []
    for _, row in filtered.iterrows():
        ticker = row["ticker"]
        bars = panel_groups.get(ticker)
        score_bars = scores_groups.get(ticker)
        if bars is None or bars.empty or score_bars is None:
            results.append({"r_realized": np.nan, "tp_fired": False})
            continue

        bars_dates = bars["date"].to_numpy()
        date_to_idx = {d: i for i, d in enumerate(bars_dates)}
        entry_idx = date_to_idx.get(np.datetime64(row["date"], "ns"))
        if entry_idx is None:
            results.append({"r_realized": np.nan, "tp_fired": False})
            continue

        entry_price = float(bars["close"].iloc[entry_idx])
        entry_flow = float(row.get("flow_100", 100.0))
        atr14 = float(row.get("atr14_at_entry", np.nan))
        if not np.isfinite(atr14) or atr14 <= 0:
            results.append({"r_realized": np.nan, "tp_fired": False})
            continue

        low_start = max(0, entry_idx - 4)
        recent_lows = bars["low"].iloc[low_start:entry_idx + 1].astype(float).to_numpy()
        initial_stop, risk = compute_initial_stop(entry_price, atr14, recent_lows)

        fwd_start = entry_idx + 1
        fwd_end = min(fwd_start + max_bars, len(bars))
        if fwd_start >= len(bars):
            results.append({"r_realized": np.nan, "tp_fired": False})
            continue

        score_dates_arr = score_bars["date"].to_numpy()
        score_date_idx = {d: i for i, d in enumerate(score_dates_arr)}
        fwd_dates = bars["date"].iloc[fwd_start:fwd_end].to_numpy()
        fwd_o = bars["open"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_h = bars["high"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_l = bars["low"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_c = bars["close"].iloc[fwd_start:fwd_end].astype(float).to_numpy()

        n = len(fwd_c)
        target_2r = entry_price + 2.0 * risk
        trail_stop = initial_stop
        highest_tier = 1
        be_triggered = False
        peak_r = 0.0
        tp_fired = False
        exit_r = np.nan

        for i in range(min(n, max_bars)):
            bo = float(fwd_o[i])
            bh = float(fwd_h[i])
            bl = float(fwd_l[i])
            bc = float(fwd_c[i])

            if bo <= trail_stop:
                exit_r = (bo - entry_price) / risk
                break
            if bl <= trail_stop:
                exit_r = (trail_stop - entry_price) / risk
                break

            current_r = (bc - entry_price) / risk
            high_r = (bh - entry_price) / risk
            peak_r = max(peak_r, high_r)
            if not be_triggered and high_r >= 0.5:
                be_triggered = True
            if current_r >= 4.0 and highest_tier < 4:
                highest_tier = 4
            elif current_r >= 2.0 and highest_tier < 3:
                highest_tier = 3
            elif current_r >= 1.0 and highest_tier < 2:
                highest_tier = 2

            # Combo TP: drop from entry + below absolute floor
            if i >= grace and current_r >= min_r and highest_tier <= 1:
                sidx = score_date_idx.get(fwd_dates[i]) if i < len(fwd_dates) else None
                if sidx is not None:
                    cur_flow = score_bars["flow_100"].iloc[sidx]
                    cur_flow = float(cur_flow) if pd.notna(cur_flow) else 100.0
                    dropped = (entry_flow - cur_flow) >= drop_thresh
                    below = cur_flow < floor_value
                    if dropped and below:
                        exit_r = current_r
                        tp_fired = True
                        break

            if highest_tier == 1:
                nt = bl - 1.0 * atr14
                if be_triggered:
                    nt = max(nt, entry_price)
            elif highest_tier == 2:
                nt = max(bl - 1.5 * atr14, entry_price)
            elif highest_tier == 3:
                nt = max(bl - 2.0 * atr14, entry_price + 1.5 * risk)
            else:
                nt = max(max(bl - 2.5 * atr14, target_2r - 1.0 * atr14), entry_price + 3.0 * risk)
            trail_stop = max(trail_stop, nt)
        else:
            exit_r = (float(fwd_c[min(n, max_bars) - 1]) - entry_price) / risk

        results.append({"r_realized": exit_r, "tp_fired": tp_fired})

    return pd.DataFrame(results)


def main():
    data_dir = ROOT / "data"
    panel = pd.read_parquet(data_dir / "panel_daily.parquet")
    scores = pd.read_parquet(data_dir / "scores_daily.parquet")

    print("[tp2] Building signals...")
    t0 = time.time()
    filtered = build_signals(scores, panel)
    print(f"[tp2] {len(filtered)} signals ({time.time()-t0:.1f}s)")

    # Entry flow distribution
    fl = filtered["flow_100"]
    print(f"\n[tp2] Entry flow distribution:")
    for pct in [10, 25, 50, 75, 90, 95]:
        print(f"  {pct}th pctile: {fl.quantile(pct/100):.1f}")
    print(f"  Mean: {fl.mean():.1f} | Min: {fl.min():.1f} | Max: {fl.max():.1f}")

    # Prep lookups
    panel_c = panel.copy()
    panel_c["date"] = pd.to_datetime(panel_c["date"]).dt.normalize()
    panel_c = panel_c.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel_groups = {t: g.reset_index(drop=True) for t, g in panel_c.groupby("ticker", sort=False)}

    scores_c = scores.copy()
    scores_c["date"] = pd.to_datetime(scores_c["date"]).dt.normalize()
    scores_groups = {t: g.sort_values("date").reset_index(drop=True) for t, g in scores_c.groupby("ticker", sort=False)}

    # Baseline
    print("\n" + "=" * 180)
    print("  THREE-BUCKET: Win (R>0.05) | Breakeven (|R|<=0.05) | Loss (R<-0.05)")
    print("=" * 180)

    baseline = TPRule("BASELINE", min_r=999, max_tier=0, sc_drop=999, elder_drop=999,
                      flow_drop=999, mp_fading=False, min_signals=99, grace_bars=0)
    bl = run_tp_backtest(filtered, panel, scores, baseline)
    three_bucket("BASELINE (no TP)", bl)

    print("\n--- Relative flow drop (from entry) ---")
    for fd in [10, 12, 15, 18, 20]:
        rule = TPRule(f"FlowDrop{fd}", min_r=0.2, max_tier=1, sc_drop=999, elder_drop=999,
                      flow_drop=fd, mp_fading=False, min_signals=1, grace_bars=2)
        res = run_tp_backtest(filtered, panel, scores, rule)
        three_bucket(f"Flow drop >= {fd} from entry", res)

    print("\n--- Absolute flow floor (exit when flow < X) ---")
    for floor in [50, 55, 60, 65, 70]:
        res = run_absolute_floor_test(filtered, panel_groups, scores_groups, floor)
        res_full = pd.concat([filtered.reset_index(drop=True), res], axis=1)
        three_bucket(f"Flow drops below {floor} (absolute)", res_full)

    print("\n--- Combo: relative drop AND absolute floor ---")
    for drop, floor in [(8, 65), (10, 65), (10, 60), (12, 65), (10, 70), (8, 70)]:
        res = run_combo_test(filtered, panel_groups, scores_groups, drop, floor)
        res_full = pd.concat([filtered.reset_index(drop=True), res], axis=1)
        three_bucket(f"Drop >= {drop} AND below {floor}", res_full)

    print("\n" + "=" * 180)


if __name__ == "__main__":
    main()
