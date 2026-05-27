"""Take-Profit Signal Analysis — DSL v2.0 proof of concept.

Replays existing trades with signal-driven TP overlaid on DSL v1.5.
Tests whether engine score degradation during holding period can
improve win rate without destroying the right tail.

Usage: python -m src.calibration.tp_analysis
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.scanner.dsl import compute_initial_stop
from src.engines.utils import atr as compute_atr


@dataclass
class TPRule:
    """A signal-driven take-profit rule to test."""
    name: str
    min_r: float           # minimum R before TP can fire (e.g., 0.2)
    max_tier: int          # only fire TP in tier <= this (1 = Tier 1 only)
    sc_drop: float         # sc_momentum must drop this many points from entry
    elder_drop: float      # elder_score must drop this many points from entry
    flow_drop: float       # flow_100 must drop this many points
    mp_fading: bool        # require mp_state == FADING
    min_signals: int       # how many degradation signals must fire (AND vs OR logic)
    grace_bars: int        # don't fire TP in first N bars (let trade develop)


def simulate_trade_with_tp(
    entry_price: float,
    atr14: float,
    risk: float,
    bars_open: np.ndarray,
    bars_high: np.ndarray,
    bars_low: np.ndarray,
    bars_close: np.ndarray,
    initial_stop: float,
    max_bars: int,
    entry_scores: dict,
    daily_scores: list[dict],
    tp_rule: TPRule,
) -> dict:
    """DSL v1.5 trade simulation with signal-driven TP overlay."""
    n = len(bars_close)
    if n == 0 or risk <= 0:
        return {"exit_bar": 0, "exit_price": entry_price, "exit_type": "no_data",
                "peak_tier": 0, "r_realized": 0.0, "peak_r": 0.0, "be_triggered": False,
                "tp_fired": False}

    target_2r = entry_price + 2.0 * risk
    trail_stop = initial_stop
    highest_tier = 1
    be_triggered = False
    peak_r = 0.0

    for i in range(min(n, max_bars)):
        bar_open = float(bars_open[i])
        bar_high = float(bars_high[i])
        bar_low = float(bars_low[i])
        bar_close = float(bars_close[i])

        # Gap-down exit
        if bar_open <= trail_stop:
            r = (bar_open - entry_price) / risk
            return {"exit_bar": i + 1, "exit_price": bar_open, "exit_type": "gap_stop",
                    "peak_tier": highest_tier, "r_realized": r, "peak_r": peak_r,
                    "be_triggered": be_triggered, "tp_fired": False}

        # Trail stop exit
        if bar_low <= trail_stop:
            r = (trail_stop - entry_price) / risk
            return {"exit_bar": i + 1, "exit_price": trail_stop, "exit_type": "trail_stop",
                    "peak_tier": highest_tier, "r_realized": r, "peak_r": peak_r,
                    "be_triggered": be_triggered, "tp_fired": False}

        # Update R and tier
        current_r = (bar_close - entry_price) / risk
        high_r = (bar_high - entry_price) / risk
        peak_r = max(peak_r, high_r)

        if not be_triggered and high_r >= 0.5:
            be_triggered = True

        if current_r >= 4.0 and highest_tier < 4:
            highest_tier = 4
        elif current_r >= 2.0 and highest_tier < 3:
            highest_tier = 3
        elif current_r >= 1.0 and highest_tier < 2:
            highest_tier = 2

        # --- SIGNAL-DRIVEN TP CHECK ---
        if (i >= tp_rule.grace_bars
                and current_r >= tp_rule.min_r
                and highest_tier <= tp_rule.max_tier
                and i < len(daily_scores)):

            day_scores = daily_scores[i]
            degradation_count = 0

            # SC momentum drop
            if entry_scores.get("sc_momentum", 0) - day_scores.get("sc_momentum", 0) >= tp_rule.sc_drop:
                degradation_count += 1

            # Elder drop
            if entry_scores.get("elder_score", 0) - day_scores.get("elder_score", 0) >= tp_rule.elder_drop:
                degradation_count += 1

            # Flow drop
            if entry_scores.get("flow_100", 0) - day_scores.get("flow_100", 0) >= tp_rule.flow_drop:
                degradation_count += 1

            # MP fading
            if tp_rule.mp_fading and day_scores.get("mp_state") == "FADING":
                degradation_count += 1

            if degradation_count >= tp_rule.min_signals:
                r = (bar_close - entry_price) / risk
                return {"exit_bar": i + 1, "exit_price": bar_close, "exit_type": "tp_signal",
                        "peak_tier": highest_tier, "r_realized": r, "peak_r": peak_r,
                        "be_triggered": be_triggered, "tp_fired": True}

        # Update trail (same as DSL v1.5)
        if highest_tier == 1:
            new_trail = bar_low - 1.0 * atr14
            if be_triggered:
                new_trail = max(new_trail, entry_price)
        elif highest_tier == 2:
            new_trail = bar_low - 1.5 * atr14
            new_trail = max(new_trail, entry_price)
        elif highest_tier == 3:
            new_trail = bar_low - 2.0 * atr14
            new_trail = max(new_trail, entry_price + 1.5 * risk)
        else:
            trail_a = bar_low - 2.5 * atr14
            trail_b = target_2r - 1.0 * atr14
            new_trail = max(trail_a, trail_b)
            new_trail = max(new_trail, entry_price + 3.0 * risk)

        trail_stop = max(trail_stop, new_trail)

    # Time exit
    exit_price = float(bars_close[min(n, max_bars) - 1])
    r = (exit_price - entry_price) / risk
    return {"exit_bar": min(n, max_bars), "exit_price": exit_price, "exit_type": "time",
            "peak_tier": highest_tier, "r_realized": r, "peak_r": peak_r,
            "be_triggered": be_triggered, "tp_fired": False}


def run_tp_backtest(signals: pd.DataFrame, panel: pd.DataFrame,
                    scores: pd.DataFrame, tp_rule: TPRule,
                    max_bars: int = 63) -> pd.DataFrame:
    """Replay all trades with a specific TP rule overlaid on DSL v1.5."""
    panel_c = panel.copy()
    panel_c["date"] = pd.to_datetime(panel_c["date"]).dt.normalize()
    panel_c = panel_c.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel_groups = {t: g.reset_index(drop=True) for t, g in panel_c.groupby("ticker", sort=False)}

    scores_c = scores.copy()
    scores_c["date"] = pd.to_datetime(scores_c["date"]).dt.normalize()
    scores_groups = {}
    for t, g in scores_c.groupby("ticker", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        scores_groups[t] = g

    sig = signals.copy()
    sig["date"] = pd.to_datetime(sig["date"]).dt.normalize()

    results = []
    for _, row in sig.iterrows():
        ticker = row["ticker"]
        bars = panel_groups.get(ticker)
        score_bars = scores_groups.get(ticker)
        if bars is None or bars.empty or score_bars is None:
            results.append({"exit_bar": np.nan, "exit_price": np.nan, "exit_type": np.nan,
                           "peak_tier": np.nan, "r_realized": np.nan, "peak_r": np.nan,
                           "be_triggered": np.nan, "tp_fired": np.nan})
            continue

        bars_dates = bars["date"].to_numpy()
        date_to_idx = {d: i for i, d in enumerate(bars_dates)}
        entry_idx = date_to_idx.get(np.datetime64(row["date"], "ns"))
        if entry_idx is None:
            results.append({"exit_bar": np.nan, "exit_price": np.nan, "exit_type": np.nan,
                           "peak_tier": np.nan, "r_realized": np.nan, "peak_r": np.nan,
                           "be_triggered": np.nan, "tp_fired": np.nan})
            continue

        entry_price = float(bars["close"].iloc[entry_idx])
        atr_col = "atr14_at_entry" if "atr14_at_entry" in row.index else "atr14"
        atr14 = float(row.get(atr_col, np.nan))
        if not np.isfinite(atr14) or atr14 <= 0:
            results.append({"exit_bar": np.nan, "exit_price": np.nan, "exit_type": np.nan,
                           "peak_tier": np.nan, "r_realized": np.nan, "peak_r": np.nan,
                           "be_triggered": np.nan, "tp_fired": np.nan})
            continue

        low_start = max(0, entry_idx - 4)
        recent_lows = bars["low"].iloc[low_start:entry_idx + 1].astype(float).to_numpy()
        initial_stop, risk = compute_initial_stop(entry_price, atr14, recent_lows)

        fwd_start = entry_idx + 1
        fwd_end = min(fwd_start + max_bars, len(bars))
        if fwd_start >= len(bars):
            results.append({"exit_bar": np.nan, "exit_price": np.nan, "exit_type": np.nan,
                           "peak_tier": np.nan, "r_realized": np.nan, "peak_r": np.nan,
                           "be_triggered": np.nan, "tp_fired": np.nan})
            continue

        fwd_open = bars["open"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_high = bars["high"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_low = bars["low"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_close = bars["close"].iloc[fwd_start:fwd_end].astype(float).to_numpy()

        # Get engine scores at entry
        entry_date = row["date"]
        score_dates = score_bars["date"].to_numpy()
        score_date_idx = {d: i for i, d in enumerate(score_dates)}

        entry_scores = {}
        entry_score_idx = score_date_idx.get(np.datetime64(entry_date, "ns"))
        if entry_score_idx is not None:
            sr = score_bars.iloc[entry_score_idx]
            for col in ["sc_momentum", "flow_100", "energy_100", "mp_100", "elder_score"]:
                if col in sr.index:
                    v = sr[col]
                    entry_scores[col] = float(v) if pd.notna(v) else 0.0
            if "mp_state" in sr.index and pd.notna(sr["mp_state"]):
                entry_scores["mp_state"] = str(sr["mp_state"])

        # Get engine scores for each forward bar
        fwd_dates = bars["date"].iloc[fwd_start:fwd_end].to_numpy()
        daily_scores = []
        for d in fwd_dates:
            sidx = score_date_idx.get(d)
            if sidx is not None:
                sr = score_bars.iloc[sidx]
                ds = {}
                for col in ["sc_momentum", "flow_100", "energy_100", "mp_100", "elder_score"]:
                    if col in sr.index:
                        v = sr[col]
                        ds[col] = float(v) if pd.notna(v) else 0.0
                if "mp_state" in sr.index and pd.notna(sr["mp_state"]):
                    ds["mp_state"] = str(sr["mp_state"])
                daily_scores.append(ds)
            else:
                daily_scores.append({})

        trade = simulate_trade_with_tp(
            entry_price, atr14, risk,
            fwd_open, fwd_high, fwd_low, fwd_close,
            initial_stop, max_bars,
            entry_scores, daily_scores, tp_rule,
        )
        results.append(trade)

    res_df = pd.DataFrame(results)
    return pd.concat([sig.reset_index(drop=True), res_df.reset_index(drop=True)], axis=1)


def summarize(label: str, df: pd.DataFrame):
    """Print trade summary stats."""
    valid = df.dropna(subset=["r_realized"])
    n = len(valid)
    if n == 0:
        print(f"  {label}: no trades")
        return
    win = (valid["r_realized"] > 0).mean()
    nonloss = (valid["r_realized"] >= 0).mean()
    avg_r = valid["r_realized"].mean()
    med_r = valid["r_realized"].median()
    tp_count = valid["tp_fired"].sum() if "tp_fired" in valid.columns else 0
    tp_pct = 100 * tp_count / n if n > 0 else 0
    tp_avg_r = valid.loc[valid["tp_fired"] == True, "r_realized"].mean() if tp_count > 0 else 0

    # Non-TP trades (trail/gap/time exits) — did we destroy the right tail?
    non_tp = valid[valid["tp_fired"] != True]
    non_tp_avg = non_tp["r_realized"].mean() if len(non_tp) > 0 else 0

    print(f"  {label:40s} | N={n:5d} | Win={100*win:5.1f}% | NL={100*nonloss:5.1f}% | AvgR={avg_r:+.4f} | MedR={med_r:+.4f} | TP={int(tp_count):4d} ({tp_pct:4.1f}%) avgR={tp_avg_r:+.3f} | Non-TP avgR={non_tp_avg:+.4f}")


def main():
    data_dir = ROOT / "data"
    panel = pd.read_parquet(data_dir / "panel_daily.parquet")
    scores = pd.read_parquet(data_dir / "scores_daily.parquet")

    print("[tp] Building signal population (5-day cooldown, SC>=50)...")
    t0 = time.time()

    COOLDOWN = 5
    THRESHOLD = 50.0
    sigs = []
    scores_sorted = scores.sort_values(["ticker", "date"]).reset_index(drop=True)
    for ticker, grp in scores_sorted.groupby("ticker"):
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
                            "elder_score", "bq_100", "squeeze_score", "fip_quality"]:
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
    sig_df = sig_df.merge(atr_df, on=["ticker", "date"], how="left")
    sig_df = sig_df.dropna(subset=["atr14"])
    sig_df = sig_df.rename(columns={"atr14": "atr14_at_entry"})

    # Apply best recipe
    mask = (
        (sig_df["sc_momentum"] >= 75) &
        (sig_df["flow_100"] >= 72) &
        (sig_df["energy_100"] >= 64) &
        (sig_df["structure_100"] >= 60) &
        (sig_df["mp_100"] >= 60)
    )
    if "elder_score" in sig_df.columns:
        mask &= sig_df["elder_score"] >= 8
    filtered = sig_df[mask].copy().reset_index(drop=True)
    print(f"[tp] {len(filtered)} signals after recipe filter ({time.time()-t0:.1f}s)")

    # Define TP rules to test
    rules = [
        TPRule("BASELINE (no TP)", min_r=999, max_tier=0, sc_drop=999, elder_drop=999,
               flow_drop=999, mp_fading=False, min_signals=99, grace_bars=0),

        # Single-signal rules
        TPRule("SC drop>=10, R>0.2", min_r=0.2, max_tier=1, sc_drop=10, elder_drop=999,
               flow_drop=999, mp_fading=False, min_signals=1, grace_bars=2),
        TPRule("SC drop>=15, R>0.2", min_r=0.2, max_tier=1, sc_drop=15, elder_drop=999,
               flow_drop=999, mp_fading=False, min_signals=1, grace_bars=2),
        TPRule("SC drop>=20, R>0.2", min_r=0.2, max_tier=1, sc_drop=20, elder_drop=999,
               flow_drop=999, mp_fading=False, min_signals=1, grace_bars=2),

        TPRule("Elder drop>=2, R>0.2", min_r=0.2, max_tier=1, sc_drop=999, elder_drop=2,
               flow_drop=999, mp_fading=False, min_signals=1, grace_bars=2),
        TPRule("Elder drop>=3, R>0.2", min_r=0.2, max_tier=1, sc_drop=999, elder_drop=3,
               flow_drop=999, mp_fading=False, min_signals=1, grace_bars=2),

        TPRule("Flow drop>=10, R>0.2", min_r=0.2, max_tier=1, sc_drop=999, elder_drop=999,
               flow_drop=10, mp_fading=False, min_signals=1, grace_bars=2),
        TPRule("Flow drop>=15, R>0.2", min_r=0.2, max_tier=1, sc_drop=999, elder_drop=999,
               flow_drop=15, mp_fading=False, min_signals=1, grace_bars=2),

        TPRule("MP FADING, R>0.2", min_r=0.2, max_tier=1, sc_drop=999, elder_drop=999,
               flow_drop=999, mp_fading=True, min_signals=1, grace_bars=2),

        # Multi-signal rules (any 2 of 4)
        TPRule("Any 2: SC10+Eld2+Fl10+MPf R>0.2", min_r=0.2, max_tier=1, sc_drop=10, elder_drop=2,
               flow_drop=10, mp_fading=True, min_signals=2, grace_bars=2),
        TPRule("Any 2: SC15+Eld3+Fl15+MPf R>0.2", min_r=0.2, max_tier=1, sc_drop=15, elder_drop=3,
               flow_drop=15, mp_fading=True, min_signals=2, grace_bars=2),

        # Same rules but also apply in Tier 2
        TPRule("Any 2: SC10+Eld2+Fl10+MPf T1-2", min_r=0.2, max_tier=2, sc_drop=10, elder_drop=2,
               flow_drop=10, mp_fading=True, min_signals=2, grace_bars=2),

        # Higher min R threshold
        TPRule("Any 2: SC10+Eld2+Fl10+MPf R>0.4", min_r=0.4, max_tier=1, sc_drop=10, elder_drop=2,
               flow_drop=10, mp_fading=True, min_signals=2, grace_bars=3),

        # Longer grace period
        TPRule("Any 2: SC10+Eld2+Fl10+MPf grace=5", min_r=0.2, max_tier=1, sc_drop=10, elder_drop=2,
               flow_drop=10, mp_fading=True, min_signals=2, grace_bars=5),
    ]

    print(f"\n[tp] Testing {len(rules)} TP rules across {len(filtered)} trades...")
    print("=" * 160)

    for rule in rules:
        t1 = time.time()
        result = run_tp_backtest(filtered, panel, scores, rule)
        elapsed = time.time() - t1
        summarize(rule.name, result)

    print("=" * 160)
    print("\n[tp] Legend: Win = R>0 | NL = R>=0 | TP = signal-driven exits | Non-TP = trail/gap/time exits")
    print("[tp] Goal: raise Win% and AvgR without destroying Non-TP avgR (the right tail)")


if __name__ == "__main__":
    main()
