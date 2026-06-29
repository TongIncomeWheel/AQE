"""AQE Momentum Intelligence — Backtest Harness.

Tests momentum states across the AQE universe. For each state, measures:
- TP1 win rate vs random-entry baseline
- Ride quality (drawdown before TP1)
- Capital velocity (days to TP1)
- Time profile (T+1 through T+10)
- Conviction score discrimination within states

The key question: do the states predict which ticker-days are better entries
and which are healthy holds vs broken trends?

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
    STATES,
    STATE_RANK,
    classify_trajectory,
    momentum_for_bars,
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

# Conviction score buckets for within-state analysis
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
# Stats
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
# Condition-level analysis
# ────────────────────────────────────────────────────────────────────────────

def _condition_importance(all_events: list[dict], baseline_tp1: float) -> dict:
    """Which individual conditions predict TP1?"""
    bool_conditions = [
        "vol_contracting", "vol_expanding_up", "range_tight",
        "close_strong", "close_weak", "mas_stacked",
        "ma10_gt_20", "ma20_gt_50", "price_above_ma10",
        "price_above_ma20", "price_above_ma50",
        "higher_lows", "close_trend_up", "close_trend_down",
        "failed_breakout",
    ]

    importance = {}
    for cond in bool_conditions:
        true_events = [e for e in all_events if e.get("conditions", {}).get(cond)]
        false_events = [e for e in all_events if not e.get("conditions", {}).get(cond)]

        n_true = len(true_events)
        n_false = len(false_events)

        if n_true < 30 or n_false < 30:
            importance[cond] = {"n_true": n_true, "n_false": n_false,
                                "tp1_when_true": None, "tp1_when_false": None,
                                "edge": None}
            continue

        tp1_true = sum(1 for e in true_events if e["fwd"].first_event == "TP1") / n_true
        tp1_false = sum(1 for e in false_events if e["fwd"].first_event == "TP1") / n_false
        sl_true = sum(1 for e in true_events if e["fwd"].first_event == "SL") / n_true
        sl_false = sum(1 for e in false_events if e["fwd"].first_event == "SL") / n_false

        dd_true = np.mean([e["fwd"].max_dd_pct for e in true_events])
        dd_false = np.mean([e["fwd"].max_dd_pct for e in false_events])

        importance[cond] = {
            "n_true": n_true,
            "n_false": n_false,
            "tp1_when_true": round(tp1_true, 4),
            "tp1_when_false": round(tp1_false, 4),
            "sl_when_true": round(sl_true, 4),
            "sl_when_false": round(sl_false, 4),
            "dd_when_true": round(float(dd_true), 3),
            "dd_when_false": round(float(dd_false), 3),
            "edge": round(tp1_true - tp1_false, 4),
        }

    return importance


# ────────────────────────────────────────────────────────────────────────────
# Combination analysis
# ────────────────────────────────────────────────────────────────────────────

def _combination_scan(all_events: list[dict], baseline_tp1: float) -> list[dict]:
    """Test specific condition combinations that might produce edge."""
    combos = [
        ("vol_contract+stacked", ["vol_contracting", "mas_stacked"]),
        ("vol_contract+stacked+strong_close", ["vol_contracting", "mas_stacked", "close_strong"]),
        ("vol_contract+stacked+higher_lows", ["vol_contracting", "mas_stacked", "higher_lows"]),
        ("vol_contract+close_trend_up", ["vol_contracting", "close_trend_up"]),
        ("vol_expand_up+stacked", ["vol_expanding_up", "mas_stacked"]),
        ("vol_expand_up+stacked+strong_close", ["vol_expanding_up", "mas_stacked", "close_strong"]),
        ("stacked+above_ma10+higher_lows", ["mas_stacked", "price_above_ma10", "higher_lows"]),
        ("stacked+tight_range+vol_contract", ["mas_stacked", "range_tight", "vol_contracting"]),
        ("stacked+close_trend_up+above_ma10", ["mas_stacked", "close_trend_up", "price_above_ma10"]),
        ("above_ma50+NOT_above_ma10+higher_lows", None),  # pullback within trend
    ]

    results = []
    for name, conds in combos:
        if conds is None:
            # Special: pullback within trend
            matched = [e for e in all_events
                       if e.get("conditions", {}).get("price_above_ma50")
                       and not e.get("conditions", {}).get("price_above_ma10")
                       and e.get("conditions", {}).get("higher_lows")]
        else:
            matched = [e for e in all_events
                       if all(e.get("conditions", {}).get(c) for c in conds)]

        not_matched = [e for e in all_events if e not in matched]

        n = len(matched)
        if n < 30:
            results.append({"combo": name, "n": n, "edge": None})
            continue

        stats = _bucket_stats(matched, baseline_tp1)
        stats_anti = _bucket_stats(not_matched, baseline_tp1)
        tp = _time_profile(matched)

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
            "time_profile": tp,
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
    print(f"[momentum] Universe: {len(tickers)} tickers")
    print(f"[momentum] BT window: {BT_START} -> {BT_END}")

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

    # Phase 2: Compute momentum states for every ticker
    print(f"\n-- Phase 2: Computing momentum states ({len(all_bars)} tickers) --")
    all_momentum: dict[str, list[dict]] = {}
    for i, (tk, bars) in enumerate(all_bars.items(), 1):
        states = momentum_for_bars(bars)
        all_momentum[tk] = states
        if i <= 3 or i % 30 == 0:
            n_bt = sum(1 for s in states
                       if pd.Timestamp(BT_START) <= s["date"] <= pd.Timestamp(BT_END))
            print(f"  [{i}/{len(all_bars)}] {tk}: {len(states)} total, {n_bt} in BT window")

    # Phase 3: Build events
    print(f"\n-- Phase 3: Building events --")
    bt_start = pd.Timestamp(BT_START)
    bt_end = pd.Timestamp(BT_END)

    all_events: list[dict] = []
    state_events: dict[str, list[dict]] = {s: [] for s in STATES}

    # Per-state cooldown tracking per ticker
    total_dates = 0
    total_brackets = 0

    for tk, states in all_momentum.items():
        bars = all_bars[tk]
        bt_states = [s for s in states if bt_start <= s["date"] <= bt_end]
        if not bt_states:
            continue

        last_trigger_per_state: dict[str, pd.Timestamp | None] = {s: None for s in STATES}

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
                "state": s["state"],
                "conviction": s["conviction"],
                "conditions": s["conditions"],
                "fwd": fwd,
            }

            all_events.append(ev)

            # State-specific with cooldown
            ms = s["state"]
            lt = last_trigger_per_state[ms]
            if lt is None or (dt - lt).days >= COOLDOWN:
                state_events[ms].append(ev)
                last_trigger_per_state[ms] = dt

    print(f"  Total dates: {total_dates:,}")
    print(f"  Valid brackets: {total_brackets:,}")
    print(f"  Total events: {len(all_events):,}")
    for s in STATES:
        print(f"  {s:20s}: {len(state_events[s]):,} (with cooldown)")

    # Phase 4: Stats per state
    print(f"\n-- Phase 4: State stats --")
    bl_stats = _bucket_stats(all_events)
    bl_tp1 = bl_stats["tp1_win_rate"]

    state_results = {}
    for s in STATES:
        evs = state_events[s]
        stats = _bucket_stats(evs, bl_tp1)
        tp = _time_profile(evs)

        # Conviction sub-buckets within this state
        conv_buckets = {}
        for lo_b, hi_b, label in CONVICTION_BUCKETS:
            bucket_evs = [e for e in evs if lo_b <= e["conviction"] < hi_b]
            conv_buckets[label] = _bucket_stats(bucket_evs, bl_tp1)

        # Trajectory within this state
        traj_buckets: dict[str, list[dict]] = {
            "IMPROVING": [], "STABLE": [], "DETERIORATING": [], "MIXED": [],
        }
        for ev in evs:
            tk_states = all_momentum.get(ev["ticker"], [])
            ev_date = pd.Timestamp(ev["date"])
            idx = None
            for si, ms in enumerate(tk_states):
                if ms["date"] == ev_date:
                    idx = si
                    break
            if idx is not None and idx >= 4:
                s5 = [tk_states[idx - 4 + j]["state"] for j in range(5)]
                traj = classify_trajectory(s5)
            else:
                traj = "MIXED"
            if traj in traj_buckets:
                traj_buckets[traj].append(ev)
        traj_stats = {k: _bucket_stats(v, bl_tp1) for k, v in traj_buckets.items()}

        state_results[s] = {
            "stats": stats,
            "time_profile": tp,
            "conviction_buckets": conv_buckets,
            "trajectory": traj_stats,
        }

        edge = stats["edge_vs_baseline"] * 100
        print(f"  {s:20s}  n={stats['n']:>5,}  TP1={stats['tp1_win_rate']*100:>5.1f}%  "
              f"Edge={edge:>+5.1f}pp  SL={stats['sl_hit_rate']*100:>5.1f}%  "
              f"DD={stats['avg_dd_pct']:>+6.2f}%")

    # Phase 5: Condition importance
    print(f"\n-- Phase 5: Condition importance --")
    cond_imp = _condition_importance(all_events, bl_tp1)
    sorted_cond = sorted(cond_imp.items(),
                         key=lambda x: abs(x[1].get("edge") or 0), reverse=True)
    for cond, data in sorted_cond:
        edge = data.get("edge")
        if edge is not None:
            print(f"  {cond:30s}  edge={edge*100:>+5.1f}pp  "
                  f"TP1(T)={data['tp1_when_true']*100:>5.1f}%  "
                  f"TP1(F)={data['tp1_when_false']*100:>5.1f}%  "
                  f"n={data['n_true']:,}/{data['n_false']:,}")
        else:
            print(f"  {cond:30s}  n_true={data['n_true']} (insufficient)")

    # Phase 6: Combination scan
    print(f"\n-- Phase 6: Condition combinations --")
    combos = _combination_scan(all_events, bl_tp1)
    for c in combos:
        edge = c.get("edge_vs_baseline")
        if edge is not None:
            print(f"  {c['combo']:40s}  n={c['n']:>5,}  "
                  f"TP1={c['tp1_win_rate']*100:>5.1f}%  "
                  f"Edge={edge*100:>+5.1f}pp  "
                  f"SL={c['sl_hit_rate']*100:>5.1f}%")
        else:
            print(f"  {c['combo']:40s}  n={c['n']} (insufficient)")

    # Phase 7: State distribution (how often is each state seen?)
    print(f"\n-- Phase 7: State distribution --")
    state_dist = {}
    for s in STATES:
        count = sum(1 for e in all_events if e["state"] == s)
        pct = count / len(all_events) * 100 if all_events else 0
        state_dist[s] = {"count": count, "pct": round(pct, 1)}
        print(f"  {s:20s}  {count:>6,}  ({pct:>5.1f}%)")

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
        "state_distribution": state_dist,
        "states": state_results,
        "condition_importance": cond_imp,
        "condition_combinations": combos,
        "pass_fail": _build_verdicts(state_results, bl_stats, combos),
    }

    _save_result(result)
    _print_summary(result)
    return result


def _build_verdicts(state_results: dict, bl_stats: dict, combos: list[dict]) -> dict:
    """Build pass/fail verdicts."""
    bl_tp1 = bl_stats["tp1_win_rate"]
    pf = {}

    # 1. Do states discriminate? Best state edge >= 3pp, worst <= -3pp
    best_state = max(state_results.items(),
                     key=lambda x: x[1]["stats"]["edge_vs_baseline"])
    worst_state = min(state_results.items(),
                      key=lambda x: x[1]["stats"]["edge_vs_baseline"])
    spread = best_state[1]["stats"]["edge_vs_baseline"] - worst_state[1]["stats"]["edge_vs_baseline"]
    pf["state_discrimination"] = {
        "criterion": "Best-to-worst state spread >= 6pp, both n>=100",
        "verdict": "PASS" if (
            spread >= 0.06
            and best_state[1]["stats"]["n"] >= 100
            and worst_state[1]["stats"]["n"] >= 100
        ) else "FAIL",
        "best_state": best_state[0],
        "best_edge": best_state[1]["stats"]["edge_vs_baseline"],
        "worst_state": worst_state[0],
        "worst_edge": worst_state[1]["stats"]["edge_vs_baseline"],
        "spread": round(spread, 4),
    }

    # 2. HIGH_CONVICTION is the go signal — does it have real edge?
    hc = state_results.get("HIGH_CONVICTION", {}).get("stats", {})
    pf["high_conviction_signal"] = {
        "criterion": "HIGH_CONVICTION: edge >= 5pp, n >= 50, SL <= baseline SL",
        "verdict": "PASS" if (
            hc.get("edge_vs_baseline", 0) >= 0.05
            and hc.get("n", 0) >= 50
            and hc.get("sl_hit_rate", 1) <= bl_stats.get("sl_hit_rate", 0) + 0.02
        ) else "FAIL",
        "edge": hc.get("edge_vs_baseline", 0),
        "n": hc.get("n", 0),
        "sl_rate": hc.get("sl_hit_rate", 0),
    }

    # 3. BREAKING_DOWN should be a avoid signal — negative edge
    bd = state_results.get("BREAKING_DOWN", {}).get("stats", {})
    pf["breakdown_avoidance"] = {
        "criterion": "BREAKING_DOWN: edge <= -3pp, n >= 100",
        "verdict": "PASS" if (
            bd.get("edge_vs_baseline", 0) <= -0.03
            and bd.get("n", 0) >= 100
        ) else "FAIL",
        "edge": bd.get("edge_vs_baseline", 0),
        "n": bd.get("n", 0),
    }

    # 4. PULLBACK_HEALTHY should outperform BREAKING_DOWN
    ph = state_results.get("PULLBACK_HEALTHY", {}).get("stats", {})
    pf["pullback_discrimination"] = {
        "criterion": "PULLBACK_HEALTHY TP1 > BREAKING_DOWN TP1 by >= 3pp, both n>=50",
        "verdict": "PASS" if (
            ph.get("tp1_win_rate", 0) - bd.get("tp1_win_rate", 0) >= 0.03
            and ph.get("n", 0) >= 50
            and bd.get("n", 0) >= 50
        ) else "FAIL",
    }

    # 5. Any condition combination with meaningful edge?
    best_combo = None
    for c in combos:
        e = c.get("edge_vs_baseline")
        if e is not None and c["n"] >= 100:
            if best_combo is None or e > best_combo.get("edge_vs_baseline", 0):
                best_combo = c
    pf["combo_edge"] = {
        "criterion": "At least one combination with edge >= 3pp, n >= 100",
        "verdict": "PASS" if (
            best_combo is not None
            and best_combo.get("edge_vs_baseline", 0) >= 0.03
        ) else "FAIL",
        "best_combo": best_combo.get("combo") if best_combo else None,
        "best_edge": best_combo.get("edge_vs_baseline") if best_combo else None,
        "best_n": best_combo.get("n") if best_combo else None,
    }

    return pf


def _save_result(result: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "mathlab_readiness.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  Results -> {out_path}")


def _print_summary(result: dict) -> None:
    bl = result.get("baseline", {})
    bl_tp1 = bl.get("tp1_win_rate", 0) * 100

    print("\n" + "=" * 78)
    print("  AQE MOMENTUM INTELLIGENCE - BACKTEST RESULTS")
    print("=" * 78)
    print(f"  Universe: {result['universe_size']} tickers | "
          f"Dates: {result['total_dates_scanned']:,} | "
          f"Events: {result['total_events']:,}")
    print(f"  Baseline TP1: {bl_tp1:.1f}% | SL: {bl.get('sl_hit_rate',0)*100:.1f}% | "
          f"DD: {bl.get('avg_dd_pct',0):+.2f}%")

    # State results
    print(f"\n-- STATE RESULTS --")
    print(f"  {'State':20s}  {'N':>6s}  {'TP1%':>6s}  {'Edge':>6s}  {'SL%':>6s}  "
          f"{'DD%':>7s}  {'d->TP1':>6s}  {'T+5':>6s}  {'T+10':>6s}")
    for s in STATES:
        sr = result["states"].get(s, {}).get("stats", {})
        edge = sr.get("edge_vs_baseline", 0) * 100
        print(f"  {s:20s}  {sr.get('n',0):>6,}  "
              f"{sr.get('tp1_win_rate',0)*100:>5.1f}%  "
              f"{edge:>+5.1f}  "
              f"{sr.get('sl_hit_rate',0)*100:>5.1f}%  "
              f"{sr.get('avg_dd_pct',0):>+6.2f}%  "
              f"{sr.get('avg_days_to_tp1',0):>5.1f}  "
              f"{sr.get('avg_return_T5_pct',0):>+5.2f}  "
              f"{sr.get('avg_return_T10_pct',0):>+5.2f}")

    # Condition importance (top 10)
    print(f"\n-- TOP CONDITIONS BY EDGE --")
    cond = result.get("condition_importance", {})
    sorted_c = sorted(cond.items(), key=lambda x: abs(x[1].get("edge") or 0), reverse=True)
    for c, data in sorted_c[:10]:
        edge = data.get("edge")
        if edge is not None:
            print(f"  {c:30s}  edge={edge*100:>+5.1f}pp  "
                  f"n={data['n_true']:,}/{data['n_false']:,}")

    # Combinations
    print(f"\n-- CONDITION COMBINATIONS --")
    for c in result.get("condition_combinations", []):
        edge = c.get("edge_vs_baseline")
        if edge is not None:
            print(f"  {c['combo']:40s}  n={c['n']:>5,}  edge={edge*100:>+5.1f}pp")

    # Pass/fail
    print(f"\n-- PASS / FAIL --")
    pf = result.get("pass_fail", {})
    for key, entry in pf.items():
        v = entry.get("verdict", "?")
        marker = "V" if v == "PASS" else "X"
        print(f"  {marker} {key}: {v}")
        print(f"    ({entry.get('criterion', '')})")

    print()


# ────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AQE Momentum Intelligence Backtest")
    parser.add_argument("--dry-run", action="store_true",
                        help="First 8 tickers only")
    parser.add_argument("--refresh", action="store_true",
                        help="Force re-pull all bars from FMP")
    args = parser.parse_args()

    if args.refresh:
        import shutil
        if CACHE_DIR.exists():
            n = len(list(CACHE_DIR.glob("*.parquet")))
            print(f"[momentum] --refresh: clearing {n} cached files")
            shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    run_backtest(dry_run=args.dry_run)
