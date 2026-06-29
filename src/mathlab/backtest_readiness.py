"""AQE Momentum Intelligence — Backtest Harness (dual-state).

Tests BOTH momentum states and readiness states. Key questions:
  1. Do momentum states discriminate forward outcomes? (A-inputs)
  2. Do readiness states discriminate? (A+C combined)
  3. Does adding C-inputs (Elder/ADX/RSI) improve prediction over A alone?
  4. Does READY_NOW produce faster TP1 hits than WAIT?
  5. Which individual A and C conditions predict outcomes?

Usage:
    python -m src.mathlab.backtest_readiness
    python -m src.mathlab.backtest_readiness --dry-run
    python -m src.mathlab.backtest_readiness --refresh
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

import numpy as np
import pandas as pd

from src.mathlab.readiness import (
    MOMENTUM_STATES,
    READINESS_STATES,
    MOMENTUM_RANK,
    READINESS_RANK,
    dual_state_for_bars,
    momentum_trajectory,
    readiness_trajectory,
)

# ────────────────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────────────────
WARMUP_START = "2024-10-01"
BT_START = "2025-01-01"
BT_END = "2026-05-30"
PULL_END = "2026-06-30"
FORWARD_SESSIONS = 10
COOLDOWN = 5

RETURN_HORIZONS = (1, 2, 3, 5, 7, 10)

CACHE_DIR = Path("data/mathlab_cache")
OUTPUT_DIR = Path("output")

CONVICTION_BUCKETS = [(0, 30, "LOW"), (30, 60, "MID"), (60, 100, "HIGH")]


# ────────────────────────────────────────────────────────────────────────────
# Data (reuses v3.1 cache)
# ────────────────────────────────────────────────────────────────────────────

def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}_daily.parquet"


def pull_daily_bars(ticker: str, force: bool = False) -> pd.DataFrame:
    p = _cache_path(ticker)
    if p.exists() and not force:
        df = pd.read_parquet(p)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            bt_s, bt_e = pd.Timestamp(BT_START), pd.Timestamp(BT_END)
            n_bt = int(((df["date"] >= bt_s) & (df["date"] <= bt_e)).sum())
            if n_bt < 200:
                print(f"STALE({n_bt})->re-pull ", end="", flush=True)
                return pull_daily_bars(ticker, force=True)
        return df
    from src.data.fmp_client import FMPClient, FMPError
    try:
        fc = FMPClient()
        df = fc.get_daily_bars(ticker, from_date=WARMUP_START, to_date=PULL_END)
        if df.empty:
            return df
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p, index=False)
        return df
    except FMPError as e:
        print(f"  [!] {ticker}: FMP error - {e}")
        return pd.DataFrame()


def load_universe() -> list[str]:
    export_path = OUTPUT_DIR / "aqe_daily_export.json"
    if not export_path.exists():
        raise FileNotFoundError(f"No export at {export_path}")
    with open(export_path) as f:
        ex = json.load(f)
    tickers = set()
    for lst in ("longlist", "elder_list"):
        for r in ex.get(lst, []):
            tk = r.get("ticker")
            if tk and tk != "SPY":
                tickers.add(tk)
    return sorted(tickers)


# ────────────────────────────────────────────────────────────────────────────
# Bracket + forward scan
# ────────────────────────────────────────────────────────────────────────────

def bracket_from_bars(bars: pd.DataFrame, date_t: pd.Timestamp):
    b = bars[bars["date"] <= date_t].tail(20)
    if len(b) < 15:
        return None
    hi = b["high"].to_numpy(dtype=float)
    lo = b["low"].to_numpy(dtype=float)
    cl = b["close"].to_numpy(dtype=float)
    entry = float(cl[-1])
    if entry <= 0:
        return None
    trs = []
    for j in range(1, len(b)):
        h, l, pc = float(hi[j]), float(lo[j]), float(cl[j - 1])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr14 = float(np.mean(trs[-14:])) if len(trs) >= 14 else float(np.mean(trs))
    if atr14 <= 0:
        return None
    risk = atr14 * 2.0
    return entry, entry - risk, entry + risk * 1.5, entry + risk * 2.0, risk, atr14


@dataclass
class ForwardResult:
    tp1_hit: bool = False
    tp1_day: int | None = None
    tp2_hit: bool = False
    tp2_day: int | None = None
    sl_hit: bool = False
    sl_day: int | None = None
    first_event: str = "NONE"
    first_event_day: int | None = None
    max_dd_pct: float = 0.0
    forward_returns: dict = field(default_factory=dict)


def scan_forward(bars: pd.DataFrame, date_t: pd.Timestamp,
                 entry: float, sl: float, tp1: float, tp2: float) -> ForwardResult:
    fwd = bars[bars["date"] > date_t].head(FORWARD_SESSIONS)
    r = ForwardResult()
    if fwd.empty:
        return r
    worst_low = entry
    for n_idx, (_, row) in enumerate(fwd.iterrows()):
        n = n_idx + 1
        bar_hi, bar_lo, bar_cl = float(row["high"]), float(row["low"]), float(row["close"])
        ret = (bar_cl - entry) / entry * 100
        if n in RETURN_HORIZONS:
            r.forward_returns[f"T+{n}"] = round(ret, 3)
        if not r.tp1_hit:
            worst_low = min(worst_low, bar_lo)
        if not r.sl_hit and bar_lo <= sl:
            r.sl_hit = True
            r.sl_day = n
            if r.first_event == "NONE":
                r.first_event = "SL"
                r.first_event_day = n
        if not r.tp1_hit and bar_hi >= tp1:
            r.tp1_hit = True
            r.tp1_day = n
            if r.first_event == "NONE":
                r.first_event = "TP1"
                r.first_event_day = n
        if not r.tp2_hit and bar_hi >= tp2:
            r.tp2_hit = True
            r.tp2_day = n
        if r.sl_hit and r.tp1_hit and r.sl_day == r.tp1_day:
            r.first_event = "AMBIGUOUS"
    r.max_dd_pct = round((worst_low - entry) / entry * 100, 3)
    return r


# ────────────────────────────────────────────────────────────────────────────
# Stats helpers
# ────────────────────────────────────────────────────────────────────────────

def _bucket_stats(events: list[dict], bl_tp1: float = 0.0) -> dict:
    n = len(events)
    if n == 0:
        return {"n": 0, "tp1_win_rate": 0, "avg_days_to_tp1": 0,
                "median_days_to_tp1": 0, "sl_hit_rate": 0,
                "none_in_10d_rate": 0, "avg_dd_pct": 0,
                "tp1_then_tp2_rate": 0, "avg_return_T5_pct": 0,
                "avg_return_T10_pct": 0, "edge_vs_baseline": 0}
    tp1 = [e for e in events if e["fwd"].first_event == "TP1"]
    sl = [e for e in events if e["fwd"].first_event == "SL"]
    none_ = [e for e in events if e["fwd"].first_event == "NONE"]
    tp1_rate = len(tp1) / n
    days = [e["fwd"].tp1_day for e in tp1 if e["fwd"].tp1_day]
    dd = [e["fwd"].max_dd_pct for e in events]
    tp1_tp2 = sum(1 for e in tp1 if e["fwd"].tp2_hit)
    t5 = [e["fwd"].forward_returns.get("T+5", 0) for e in events
          if "T+5" in e["fwd"].forward_returns]
    t10 = [e["fwd"].forward_returns.get("T+10", 0) for e in events
           if "T+10" in e["fwd"].forward_returns]
    return {
        "n": n,
        "tp1_win_rate": round(tp1_rate, 4),
        "avg_days_to_tp1": round(float(np.mean(days)), 1) if days else 0,
        "median_days_to_tp1": round(float(median(days)), 1) if days else 0,
        "sl_hit_rate": round(len(sl) / n, 4),
        "none_in_10d_rate": round(len(none_) / n, 4),
        "avg_dd_pct": round(float(np.mean(dd)), 3) if dd else 0,
        "tp1_then_tp2_rate": round(tp1_tp2 / len(tp1), 4) if tp1 else 0,
        "avg_return_T5_pct": round(float(np.mean(t5)), 3) if t5 else 0,
        "avg_return_T10_pct": round(float(np.mean(t10)), 3) if t10 else 0,
        "edge_vs_baseline": round(tp1_rate - bl_tp1, 4),
    }


def _time_profile(events: list[dict]) -> dict:
    p = {}
    for h in RETURN_HORIZONS:
        k = f"T+{h}"
        rets = [e["fwd"].forward_returns.get(k) for e in events
                if k in e["fwd"].forward_returns]
        rets = [r for r in rets if r is not None]
        p[k] = {
            "avg_return_pct": round(float(np.mean(rets)), 3) if rets else 0,
            "pct_profitable": round(sum(1 for r in rets if r > 0) / len(rets), 4) if rets else 0,
        }
    return p


# ────────────────────────────────────────────────────────────────────────────
# Condition-level analysis (A-inputs AND C-inputs separately)
# ────────────────────────────────────────────────────────────────────────────

def _condition_importance(all_events: list[dict], baseline_tp1: float) -> dict:
    a_conditions = [
        "vol_contracting", "vol_expanding_up", "range_tight",
        "close_strong", "close_weak", "mas_stacked",
        "ma10_gt_20", "ma20_gt_50", "price_above_ma10",
        "price_above_ma20", "price_above_ma50",
        "higher_lows", "close_trend_up", "close_trend_down",
        "failed_breakout",
    ]
    c_conditions = [
        "elder_green", "elder_red", "elder_rising",
        "adx_rising", "adx_trending",
        "rsi_bullish", "rsi_rising",
    ]

    importance = {}

    for cond in a_conditions:
        _eval_condition(all_events, cond, "a_conditions", importance)
    for cond in c_conditions:
        _eval_condition(all_events, cond, "c_inputs", importance)

    return importance


def _eval_condition(events, cond, group_key, importance):
    true_events = [e for e in events if e.get(group_key, {}).get(cond)]
    false_events = [e for e in events if not e.get(group_key, {}).get(cond)]
    n_true, n_false = len(true_events), len(false_events)

    if n_true < 30 or n_false < 30:
        importance[cond] = {"n_true": n_true, "n_false": n_false,
                            "group": group_key, "edge": None}
        return

    tp1_true = sum(1 for e in true_events if e["fwd"].first_event == "TP1") / n_true
    tp1_false = sum(1 for e in false_events if e["fwd"].first_event == "TP1") / n_false
    sl_true = sum(1 for e in true_events if e["fwd"].first_event == "SL") / n_true
    sl_false = sum(1 for e in false_events if e["fwd"].first_event == "SL") / n_false
    dd_true = np.mean([e["fwd"].max_dd_pct for e in true_events])
    dd_false = np.mean([e["fwd"].max_dd_pct for e in false_events])

    importance[cond] = {
        "n_true": n_true, "n_false": n_false,
        "group": group_key,
        "tp1_when_true": round(tp1_true, 4),
        "tp1_when_false": round(tp1_false, 4),
        "sl_when_true": round(sl_true, 4),
        "sl_when_false": round(sl_false, 4),
        "dd_when_true": round(float(dd_true), 3),
        "dd_when_false": round(float(dd_false), 3),
        "edge": round(tp1_true - tp1_false, 4),
    }


# ────────────────────────────────────────────────────────────────────────────
# C-input additive value test
# ────────────────────────────────────────────────────────────────────────────

def _c_additive_value(all_events: list[dict], baseline_tp1: float) -> dict:
    """Test whether C-inputs add value ON TOP OF A-inputs.

    For each momentum state (A-only), split by readiness state (A+C) and
    compare. If C adds value, READY_NOW within BUILDING should beat WAIT
    within BUILDING.
    """
    result = {}
    for ms in MOMENTUM_STATES:
        ms_events = [e for e in all_events if e["momentum_state"] == ms]
        if len(ms_events) < 30:
            result[ms] = {"n": len(ms_events), "split": {}}
            continue

        ms_stats = _bucket_stats(ms_events, baseline_tp1)
        split = {}
        for rs in READINESS_STATES:
            rs_events = [e for e in ms_events if e["readiness_state"] == rs]
            if len(rs_events) >= 10:
                split[rs] = _bucket_stats(rs_events, baseline_tp1)
        result[ms] = {
            "n": len(ms_events),
            "tp1_rate": ms_stats["tp1_win_rate"],
            "split": split,
        }
    return result


# ────────────────────────────────────────────────────────────────────────────
# Combination analysis
# ────────────────────────────────────────────────────────────────────────────

def _combination_scan(all_events: list[dict], baseline_tp1: float) -> list[dict]:
    combos = [
        ("A: vol_contract+stacked", "a_conditions", ["vol_contracting", "mas_stacked"]),
        ("A: vol_contract+stacked+strong_close", "a_conditions",
         ["vol_contracting", "mas_stacked", "close_strong"]),
        ("A: vol_expand_up+stacked", "a_conditions", ["vol_expanding_up", "mas_stacked"]),
        ("A: stacked+above_ma10+higher_lows", "a_conditions",
         ["mas_stacked", "price_above_ma10", "higher_lows"]),
        ("A: stacked+tight_range+vol_contract", "a_conditions",
         ["mas_stacked", "range_tight", "vol_contracting"]),
        ("C: elder_green+adx_trending", "c_inputs", ["elder_green", "adx_trending"]),
        ("C: elder_green+rsi_bullish", "c_inputs", ["elder_green", "rsi_bullish"]),
        ("C: elder_rising+adx_rising", "c_inputs", ["elder_rising", "adx_rising"]),
        ("A+C: vol_contract+stacked+elder_green", "mixed",
         [("a_conditions", "vol_contracting"), ("a_conditions", "mas_stacked"),
          ("c_inputs", "elder_green")]),
        ("A+C: vol_contract+stacked+adx_trending", "mixed",
         [("a_conditions", "vol_contracting"), ("a_conditions", "mas_stacked"),
          ("c_inputs", "adx_trending")]),
        ("A+C: stacked+elder_green+rsi_bullish", "mixed",
         [("a_conditions", "mas_stacked"), ("c_inputs", "elder_green"),
          ("c_inputs", "rsi_bullish")]),
        ("A+C: vol_expand+stacked+elder_green", "mixed",
         [("a_conditions", "vol_expanding_up"), ("a_conditions", "mas_stacked"),
          ("c_inputs", "elder_green")]),
    ]

    results = []
    for name, group, conds in combos:
        if group == "mixed":
            matched = [e for e in all_events
                       if all(e.get(g, {}).get(c) for g, c in conds)]
        else:
            matched = [e for e in all_events
                       if all(e.get(group, {}).get(c) for c in conds)]

        n = len(matched)
        if n < 30:
            results.append({"combo": name, "n": n, "edge_vs_baseline": None})
            continue

        not_matched = [e for e in all_events if e not in matched]
        stats = _bucket_stats(matched, baseline_tp1)
        stats_anti = _bucket_stats(not_matched, baseline_tp1)

        results.append({
            "combo": name,
            "n": n,
            "tp1_win_rate": stats["tp1_win_rate"],
            "sl_hit_rate": stats["sl_hit_rate"],
            "avg_dd_pct": stats["avg_dd_pct"],
            "avg_days_to_tp1": stats["avg_days_to_tp1"],
            "tp1_then_tp2": stats["tp1_then_tp2_rate"],
            "edge_vs_baseline": stats["edge_vs_baseline"],
            "edge_vs_anti": round(stats["tp1_win_rate"] - stats_anti["tp1_win_rate"], 4),
            "avg_return_T5": stats["avg_return_T5_pct"],
            "avg_return_T10": stats["avg_return_T10_pct"],
        })

    results.sort(key=lambda x: -(x.get("edge_vs_baseline") or -1))
    return results


# ────────────────────────────────────────────────────────────────────────────
# Main runner
# ────────────────────────────────────────────────────────────────────────────

def run_backtest(tickers: list[str] | None = None,
                 dry_run: bool = False) -> dict:
    if tickers is None:
        tickers = load_universe()
    print(f"[dual-state] Universe: {len(tickers)} tickers")
    print(f"[dual-state] BT window: {BT_START} -> {BT_END}")

    # Phase 1: Pull bars
    print("\n-- Phase 1: Pulling daily bars --")
    all_bars: dict[str, pd.DataFrame] = {}
    failed = []
    for i, tk in enumerate(tickers, 1):
        print(f"  [{i}/{len(tickers)}] {tk}...", end=" ", flush=True)
        df = pull_daily_bars(tk)
        if df.empty:
            print("EMPTY")
            failed.append(tk)
        else:
            all_bars[tk] = df
            print(f"{len(df)} bars")
        if dry_run and i >= 8:
            break

    # Phase 2: Compute dual states
    print(f"\n-- Phase 2: Computing dual states ({len(all_bars)} tickers) --")
    all_states: dict[str, list[dict]] = {}
    for i, (tk, bars) in enumerate(all_bars.items(), 1):
        states = dual_state_for_bars(bars)
        all_states[tk] = states
        if i <= 3 or i % 30 == 0:
            n_bt = sum(1 for s in states
                       if pd.Timestamp(BT_START) <= s["date"] <= pd.Timestamp(BT_END))
            print(f"  [{i}/{len(all_bars)}] {tk}: {len(states)} total, {n_bt} in BT window")

    # Phase 3: Build events
    print(f"\n-- Phase 3: Building events --")
    bt_start = pd.Timestamp(BT_START)
    bt_end = pd.Timestamp(BT_END)

    all_events: list[dict] = []
    momentum_events: dict[str, list[dict]] = {s: [] for s in MOMENTUM_STATES}
    readiness_events: dict[str, list[dict]] = {s: [] for s in READINESS_STATES}

    total_dates = 0
    total_brackets = 0

    for tk, states in all_states.items():
        bars = all_bars[tk]
        bt_states = [s for s in states if bt_start <= s["date"] <= bt_end]
        if not bt_states:
            continue

        last_trigger: pd.Timestamp | None = None

        for s in bt_states:
            dt = s["date"]
            total_dates += 1

            bracket = bracket_from_bars(bars, dt)
            if bracket is None:
                continue
            total_brackets += 1

            entry, sl, tp1, tp2, risk, atr14 = bracket
            fwd = scan_forward(bars, dt, entry, sl, tp1, tp2)

            ev = {
                "ticker": tk,
                "date": str(dt.date()) if hasattr(dt, "date") else str(dt),
                "momentum_state": s["momentum_state"],
                "readiness_state": s["readiness_state"],
                "conviction": s["conviction"],
                "a_conditions": s["a_conditions"],
                "c_inputs": s["c_inputs"],
                "fwd": fwd,
            }

            all_events.append(ev)

            # With cooldown for state-specific buckets
            if last_trigger is None or (dt - last_trigger).days >= COOLDOWN:
                momentum_events[s["momentum_state"]].append(ev)
                readiness_events[s["readiness_state"]].append(ev)
                last_trigger = dt

    print(f"  Total dates: {total_dates:,}")
    print(f"  Valid brackets: {total_brackets:,}")
    print(f"  Total events: {len(all_events):,}")
    print(f"\n  Momentum states:")
    for s in MOMENTUM_STATES:
        print(f"    {s:20s}: {len(momentum_events[s]):,}")
    print(f"\n  Readiness states:")
    for s in READINESS_STATES:
        print(f"    {s:20s}: {len(readiness_events[s]):,}")

    # Phase 4: Baseline
    bl_stats = _bucket_stats(all_events)
    bl_tp1 = bl_stats["tp1_win_rate"]

    # Phase 5: Momentum state stats
    print(f"\n-- Phase 4: Momentum state stats (A-inputs) --")
    mom_results = _compute_state_results(
        MOMENTUM_STATES, momentum_events, all_events, all_states,
        bl_tp1, "momentum_state", MOMENTUM_RANK)

    # Phase 6: Readiness state stats
    print(f"\n-- Phase 5: Readiness state stats (A+C) --")
    rdy_results = _compute_state_results(
        READINESS_STATES, readiness_events, all_events, all_states,
        bl_tp1, "readiness_state", READINESS_RANK)

    # Phase 7: C-input additive value
    print(f"\n-- Phase 6: C-input additive value --")
    c_additive = _c_additive_value(all_events, bl_tp1)
    for ms, data in c_additive.items():
        split = data.get("split", {})
        if not split:
            continue
        parts = []
        for rs, rs_stats in split.items():
            parts.append(f"{rs}={rs_stats['tp1_win_rate']*100:.1f}%({rs_stats['n']})")
        print(f"  {ms:20s}  n={data['n']:>5,}  TP1={data['tp1_rate']*100:.1f}%  "
              f"| {', '.join(parts)}")

    # Phase 8: Condition importance (A and C separately)
    print(f"\n-- Phase 7: Condition importance --")
    cond_imp = _condition_importance(all_events, bl_tp1)
    sorted_cond = sorted(cond_imp.items(),
                         key=lambda x: abs(x[1].get("edge") or 0), reverse=True)
    for cond, data in sorted_cond:
        edge = data.get("edge")
        group = data.get("group", "?")
        tag = "A" if group == "a_conditions" else "C"
        if edge is not None:
            print(f"  [{tag}] {cond:30s}  edge={edge*100:>+5.1f}pp  "
                  f"TP1(T)={data['tp1_when_true']*100:>5.1f}%  "
                  f"TP1(F)={data['tp1_when_false']*100:>5.1f}%  "
                  f"n={data['n_true']:,}/{data['n_false']:,}")
        else:
            print(f"  [{tag}] {cond:30s}  n_true={data['n_true']} (insufficient)")

    # Phase 9: Combination scan
    print(f"\n-- Phase 8: Condition combinations --")
    combos = _combination_scan(all_events, bl_tp1)
    for c in combos:
        edge = c.get("edge_vs_baseline")
        if edge is not None:
            print(f"  {c['combo']:45s}  n={c['n']:>5,}  "
                  f"TP1={c['tp1_win_rate']*100:>5.1f}%  "
                  f"Edge={edge*100:>+5.1f}pp  "
                  f"SL={c['sl_hit_rate']*100:>5.1f}%")
        else:
            print(f"  {c['combo']:45s}  n={c['n']} (insufficient)")

    # Phase 10: State distributions
    mom_dist = _state_distribution(all_events, "momentum_state", MOMENTUM_STATES)
    rdy_dist = _state_distribution(all_events, "readiness_state", READINESS_STATES)

    # Build result
    result = {
        "run_date": str(pd.Timestamp.now().date()),
        "universe_size": len(tickers),
        "date_range": {"from": BT_START, "to": BT_END},
        "bracket_method": "ATR14 x 2.0 DSL, TP1 = 1.5R, TP2 = 2.0R",
        "max_forward_days": FORWARD_SESSIONS,
        "cooldown_sessions": COOLDOWN,
        "total_dates_scanned": total_dates,
        "total_brackets": total_brackets,
        "total_events": len(all_events),
        "data_unavailable": failed,
        "baseline": bl_stats,
        "baseline_time_profile": _time_profile(all_events),
        "momentum_distribution": mom_dist,
        "readiness_distribution": rdy_dist,
        "momentum_states": mom_results,
        "readiness_states": rdy_results,
        "c_additive_value": c_additive,
        "condition_importance": cond_imp,
        "condition_combinations": combos,
        "pass_fail": _build_verdicts(mom_results, rdy_results, bl_stats,
                                     combos, c_additive),
    }

    _save_result(result)
    _print_summary(result)
    return result


def _compute_state_results(state_list, state_events, all_events, all_states,
                           bl_tp1, state_key, rank_map):
    results = {}
    for s in state_list:
        evs = state_events[s]
        stats = _bucket_stats(evs, bl_tp1)

        # Conviction sub-buckets
        conv_buckets = {}
        for lo_b, hi_b, label in CONVICTION_BUCKETS:
            bucket_evs = [e for e in evs if lo_b <= e["conviction"] < hi_b]
            conv_buckets[label] = _bucket_stats(bucket_evs, bl_tp1)

        # Trajectory within state
        traj_buckets: dict[str, list[dict]] = {
            "IMPROVING": [], "STABLE": [], "DETERIORATING": [], "MIXED": [],
        }
        for ev in evs:
            tk_states = all_states.get(ev["ticker"], [])
            ev_date = pd.Timestamp(ev["date"])
            idx = None
            for si, ms in enumerate(tk_states):
                if ms["date"] == ev_date:
                    idx = si
                    break
            if idx is not None and idx >= 4:
                s5 = [tk_states[idx - 4 + j][state_key] for j in range(5)]
                traj = classify_trajectory(s5, rank_map)
            else:
                traj = "MIXED"
            if traj in traj_buckets:
                traj_buckets[traj].append(ev)
        traj_stats = {k: _bucket_stats(v, bl_tp1) for k, v in traj_buckets.items()}

        results[s] = {
            "stats": stats,
            "time_profile": _time_profile(evs),
            "conviction_buckets": conv_buckets,
            "trajectory": traj_stats,
        }

        edge = stats["edge_vs_baseline"] * 100
        print(f"  {s:20s}  n={stats['n']:>5,}  TP1={stats['tp1_win_rate']*100:>5.1f}%  "
              f"Edge={edge:>+5.1f}pp  SL={stats['sl_hit_rate']*100:>5.1f}%  "
              f"DD={stats['avg_dd_pct']:>+6.2f}%  "
              f"d->TP1={stats['avg_days_to_tp1']:>5.1f}")
    return results


def classify_trajectory(states_5d, rank_map):
    if len(states_5d) < 3:
        return "MIXED"
    ranks = [rank_map.get(s, len(rank_map)) for s in states_5d]
    last3 = ranks[-3:]
    if last3[0] > last3[1] > last3[2]:
        return "IMPROVING"
    if last3[0] < last3[1] < last3[2]:
        return "DETERIORATING"
    if max(ranks) - min(ranks) <= 1:
        return "STABLE"
    return "MIXED"


def _state_distribution(events, key, states):
    dist = {}
    n_total = len(events)
    for s in states:
        count = sum(1 for e in events if e[key] == s)
        pct = count / n_total * 100 if n_total else 0
        dist[s] = {"count": count, "pct": round(pct, 1)}
    return dist


# ────────────────────────────────────────────────────────────────────────────
# Verdicts
# ────────────────────────────────────────────────────────────────────────────

def _build_verdicts(mom_results, rdy_results, bl_stats, combos, c_additive):
    bl_tp1 = bl_stats["tp1_win_rate"]
    pf = {}

    # 1. Momentum state discrimination (A-inputs)
    best_m = max(mom_results.items(),
                 key=lambda x: x[1]["stats"]["edge_vs_baseline"])
    worst_m = min(mom_results.items(),
                  key=lambda x: x[1]["stats"]["edge_vs_baseline"])
    spread_m = best_m[1]["stats"]["edge_vs_baseline"] - worst_m[1]["stats"]["edge_vs_baseline"]
    pf["momentum_discrimination"] = {
        "criterion": "Momentum best-to-worst spread >= 6pp",
        "verdict": "PASS" if spread_m >= 0.06 and best_m[1]["stats"]["n"] >= 100 else "FAIL",
        "best": best_m[0], "best_edge": best_m[1]["stats"]["edge_vs_baseline"],
        "worst": worst_m[0], "worst_edge": worst_m[1]["stats"]["edge_vs_baseline"],
        "spread": round(spread_m, 4),
    }

    # 2. Readiness state discrimination (A+C)
    best_r = max(rdy_results.items(),
                 key=lambda x: x[1]["stats"]["edge_vs_baseline"])
    worst_r = min(rdy_results.items(),
                  key=lambda x: x[1]["stats"]["edge_vs_baseline"])
    spread_r = best_r[1]["stats"]["edge_vs_baseline"] - worst_r[1]["stats"]["edge_vs_baseline"]
    pf["readiness_discrimination"] = {
        "criterion": "Readiness best-to-worst spread >= 6pp",
        "verdict": "PASS" if spread_r >= 0.06 and best_r[1]["stats"]["n"] >= 50 else "FAIL",
        "best": best_r[0], "best_edge": best_r[1]["stats"]["edge_vs_baseline"],
        "worst": worst_r[0], "worst_edge": worst_r[1]["stats"]["edge_vs_baseline"],
        "spread": round(spread_r, 4),
    }

    # 3. READY_NOW signal quality
    rn = rdy_results.get("READY_NOW", {}).get("stats", {})
    pf["ready_now_signal"] = {
        "criterion": "READY_NOW: edge >= 5pp, n >= 50",
        "verdict": "PASS" if rn.get("edge_vs_baseline", 0) >= 0.05 and rn.get("n", 0) >= 50 else "FAIL",
        "edge": rn.get("edge_vs_baseline", 0),
        "n": rn.get("n", 0),
        "sl_rate": rn.get("sl_hit_rate", 0),
    }

    # 4. STAND_DOWN avoidance
    sd = rdy_results.get("STAND_DOWN", {}).get("stats", {})
    pf["stand_down_avoidance"] = {
        "criterion": "STAND_DOWN: edge <= -3pp, n >= 100",
        "verdict": "PASS" if sd.get("edge_vs_baseline", 0) <= -0.03 and sd.get("n", 0) >= 100 else "FAIL",
        "edge": sd.get("edge_vs_baseline", 0),
        "n": sd.get("n", 0),
    }

    # 5. READY_NOW faster to TP1 than WAIT
    rn_days = rn.get("median_days_to_tp1", 0)
    wt = rdy_results.get("WAIT", {}).get("stats", {})
    wt_days = wt.get("median_days_to_tp1", 0)
    pf["timing_value"] = {
        "criterion": "READY_NOW median days-to-TP1 < WAIT median days-to-TP1",
        "verdict": "PASS" if rn_days > 0 and wt_days > 0 and rn_days < wt_days else "FAIL",
        "ready_now_days": rn_days,
        "wait_days": wt_days,
    }

    # 6. C-inputs add value (readiness spread > momentum spread)
    pf["c_adds_value"] = {
        "criterion": "Readiness spread >= momentum spread (C adds signal)",
        "verdict": "PASS" if spread_r >= spread_m else "FAIL",
        "readiness_spread": round(spread_r, 4),
        "momentum_spread": round(spread_m, 4),
    }

    # 7. Best condition combination
    best_combo = None
    for c in combos:
        e = c.get("edge_vs_baseline")
        if e is not None and c["n"] >= 100:
            if best_combo is None or e > best_combo.get("edge_vs_baseline", 0):
                best_combo = c
    pf["combo_edge"] = {
        "criterion": "At least one combination with edge >= 3pp, n >= 100",
        "verdict": "PASS" if best_combo and best_combo.get("edge_vs_baseline", 0) >= 0.03 else "FAIL",
        "best_combo": best_combo.get("combo") if best_combo else None,
        "best_edge": best_combo.get("edge_vs_baseline") if best_combo else None,
    }

    return pf


# ────────────────────────────────────────────────────────────────────────────
# Output
# ────────────────────────────────────────────────────────────────────────────

def _save_result(result: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "mathlab_readiness.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  Results -> {out_path}")


def _print_summary(result: dict) -> None:
    bl = result.get("baseline", {})
    bl_tp1 = bl.get("tp1_win_rate", 0) * 100

    print("\n" + "=" * 80)
    print("  AQE MOMENTUM INTELLIGENCE — DUAL-STATE BACKTEST")
    print("=" * 80)
    print(f"  Universe: {result['universe_size']} tickers | "
          f"Events: {result['total_events']:,}")
    print(f"  Baseline TP1: {bl_tp1:.1f}% | SL: {bl.get('sl_hit_rate',0)*100:.1f}%")

    # Momentum states
    print(f"\n-- MOMENTUM STATES (A-inputs: bar conditions) --")
    _print_state_table(result, "momentum_states", MOMENTUM_STATES)

    # Readiness states
    print(f"\n-- READINESS STATES (A+C: bar conditions + Elder/ADX/RSI) --")
    _print_state_table(result, "readiness_states", READINESS_STATES)

    # C-additive value
    print(f"\n-- C-INPUT ADDITIVE VALUE --")
    print(f"  For each momentum state, does readiness sub-split improve prediction?")
    c_add = result.get("c_additive_value", {})
    for ms in MOMENTUM_STATES:
        data = c_add.get(ms, {})
        split = data.get("split", {})
        if not split:
            continue
        parts = []
        for rs in READINESS_STATES:
            if rs in split:
                parts.append(f"{rs}={split[rs]['tp1_win_rate']*100:.1f}%({split[rs]['n']})")
        print(f"  {ms:20s}  base={data.get('tp1_rate',0)*100:.1f}%  | {', '.join(parts)}")

    # Conditions (top 10)
    print(f"\n-- TOP CONDITIONS BY EDGE --")
    cond = result.get("condition_importance", {})
    sorted_c = sorted(cond.items(), key=lambda x: abs(x[1].get("edge") or 0), reverse=True)
    for c_name, data in sorted_c[:12]:
        edge = data.get("edge")
        group = data.get("group", "?")
        tag = "A" if group == "a_conditions" else "C"
        if edge is not None:
            print(f"  [{tag}] {c_name:30s}  edge={edge*100:>+5.1f}pp  "
                  f"n={data['n_true']:,}/{data['n_false']:,}")

    # Combos (top 8)
    print(f"\n-- CONDITION COMBINATIONS (top 8) --")
    for c in result.get("condition_combinations", [])[:8]:
        edge = c.get("edge_vs_baseline")
        if edge is not None:
            print(f"  {c['combo']:45s}  n={c['n']:>5,}  edge={edge*100:>+5.1f}pp")

    # Pass/fail
    print(f"\n-- PASS / FAIL --")
    pf = result.get("pass_fail", {})
    for key, entry in pf.items():
        v = entry.get("verdict", "?")
        marker = "V" if v == "PASS" else "X"
        print(f"  {marker} {key}: {v}")
        print(f"    ({entry.get('criterion', '')})")

    print()


def _print_state_table(result, key, states):
    print(f"  {'State':20s}  {'N':>6s}  {'TP1%':>6s}  {'Edge':>6s}  {'SL%':>6s}  "
          f"{'DD%':>7s}  {'d->TP1':>6s}  {'T+5':>6s}")
    for s in states:
        sr = result[key].get(s, {}).get("stats", {})
        edge = sr.get("edge_vs_baseline", 0) * 100
        print(f"  {s:20s}  {sr.get('n',0):>6,}  "
              f"{sr.get('tp1_win_rate',0)*100:>5.1f}%  "
              f"{edge:>+5.1f}  "
              f"{sr.get('sl_hit_rate',0)*100:>5.1f}%  "
              f"{sr.get('avg_dd_pct',0):>+6.2f}%  "
              f"{sr.get('avg_days_to_tp1',0):>5.1f}  "
              f"{sr.get('avg_return_T5_pct',0):>+5.2f}")


# ────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AQE Dual-State Momentum Backtest")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    if args.refresh:
        import shutil
        if CACHE_DIR.exists():
            n = len(list(CACHE_DIR.glob("*.parquet")))
            print(f"[dual-state] --refresh: clearing {n} cached files")
            shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    run_backtest(dry_run=args.dry_run)
