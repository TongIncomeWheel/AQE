"""AQE Readiness Score — Backtest Harness.

Tests the readiness score across the AQE universe at multiple trigger
thresholds. Measures TP1 win rate, ride quality, capital velocity, and
time profile vs a random-entry baseline. Validates reference cases.

Usage:
    python -m src.mathlab.backtest_readiness
    python -m src.mathlab.backtest_readiness --dry-run
    python -m src.mathlab.backtest_readiness --refresh
    python -m src.mathlab.backtest_readiness --reference-only
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

import numpy as np
import pandas as pd

from src.mathlab.readiness import (
    DEFAULT_WEIGHTS,
    classify_stage,
    classify_trajectory,
    readiness_for_bars,
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

THRESHOLDS = [50, 60, 70, 75, 80, 85, 90]
RETURN_HORIZONS = (1, 2, 3, 5, 7, 10)

CACHE_DIR = Path("data/mathlab_cache")
OUTPUT_DIR = Path("output")

REFERENCE_TICKERS = ["VSCO", "BROS", "CAT"]
REFERENCE_START = "2026-06-10"
REFERENCE_END = "2026-06-30"

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
                print(f"STALE({n_bt})→re-pull ", end="", flush=True)
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
        print(f"  [!] {ticker}: FMP error — {e}")
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
# Bracket + forward scan (same as v3.1)
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
# Stats (same structure as v3.1)
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
# Reference case validation
# ────────────────────────────────────────────────────────────────────────────

def _validate_reference_cases(all_bars: dict[str, pd.DataFrame]) -> dict:
    ref = {}
    for tk in REFERENCE_TICKERS:
        bars = all_bars.get(tk)
        if bars is None or bars.empty:
            ref[tk] = {"status": "NO_DATA"}
            continue

        scores = readiness_for_bars(bars)
        if not scores:
            ref[tk] = {"status": "NO_SCORES"}
            continue

        ref_start = pd.Timestamp(REFERENCE_START)
        ref_end = pd.Timestamp(REFERENCE_END)
        window = [s for s in scores if ref_start <= s["date"] <= ref_end]

        if not window:
            ref[tk] = {"status": "NO_DATA_IN_WINDOW", "score_count": len(scores),
                       "date_range": f"{scores[0]['date']} to {scores[-1]['date']}"}
            continue

        daily = []
        for s in window:
            daily.append({
                "date": str(s["date"].date()) if hasattr(s["date"], "date") else str(s["date"]),
                "score": s["score"],
                "stage": s["stage"],
                "components": s["components"],
                "failed_breakout": s.get("failed_breakout", False),
            })

        scores_list = [d["score"] for d in daily]
        trajectory = classify_trajectory(scores_list[-5:]) if len(scores_list) >= 5 else "INSUFFICIENT"

        checks = {}
        if tk == "VSCO":
            if len(daily) >= 2:
                last_two = [d["score"] for d in daily[-2:]]
                checks["breakout_day_higher_than_prior"] = last_two[-1] >= last_two[-2]
            checks["last_day_stage"] = daily[-1]["stage"]
            checks["trajectory"] = trajectory
            checks["not_monitoring_day_before_last"] = (
                daily[-2]["stage"] not in ("MONITORING", "BASE_FORMING")
                if len(daily) >= 2 else None
            )
        elif tk == "BROS":
            jun22_entries = [d for d in daily if "2026-06-22" in d["date"]]
            jun26_entries = [d for d in daily if "2026-06-26" in d["date"]]
            if jun22_entries and jun26_entries:
                checks["jun22_failed_bo_detected"] = jun22_entries[0].get("failed_breakout", False)
                checks["jun26_higher_than_jun22"] = jun26_entries[0]["score"] > jun22_entries[0]["score"]
                checks["jun22_not_ready"] = jun22_entries[0]["stage"] not in ("READY", "TRIGGERED")
        elif tk == "CAT":
            if daily:
                checks["not_ready_or_approaching"] = daily[-1]["stage"] not in ("READY", "TRIGGERED", "APPROACHING")
                checks["last_score"] = daily[-1]["score"]

        ref[tk] = {
            "status": "OK",
            "daily": daily,
            "trajectory": trajectory,
            "checks": checks,
        }

    return ref


# ────────────────────────────────────────────────────────────────────────────
# Component importance analysis
# ────────────────────────────────────────────────────────────────────────────

def _component_importance(all_events: list[dict], baseline_tp1: float) -> dict:
    """Which components correlate with TP1 outcomes?"""
    components = list(DEFAULT_WEIGHTS.keys())
    importance = {}

    for comp in components:
        vals = []
        tp1_hits = []
        for ev in all_events:
            c_val = ev.get("components", {}).get(comp, 0)
            vals.append(c_val)
            tp1_hits.append(1 if ev["fwd"].first_event == "TP1" else 0)

        if len(vals) < 50:
            importance[comp] = {"n": len(vals), "correlation": None, "edge_when_high": None}
            continue

        vals_arr = np.array(vals)
        tp1_arr = np.array(tp1_hits)

        if np.std(vals_arr) < 1e-10:
            importance[comp] = {"n": len(vals), "correlation": 0, "edge_when_high": None}
            continue

        corr = float(np.corrcoef(vals_arr, tp1_arr)[0, 1])
        if np.isnan(corr):
            corr = 0.0

        p75 = float(np.percentile(vals_arr, 75))
        high_mask = vals_arr >= p75
        if np.sum(high_mask) > 0:
            high_tp1 = float(np.mean(tp1_arr[high_mask]))
            low_tp1 = float(np.mean(tp1_arr[~high_mask]))
            edge = high_tp1 - low_tp1
        else:
            edge = 0.0

        importance[comp] = {
            "n": len(vals),
            "correlation": round(corr, 4),
            "tp1_rate_when_high": round(high_tp1, 4) if np.sum(high_mask) > 0 else None,
            "tp1_rate_when_low": round(low_tp1, 4) if np.sum(~high_mask) > 0 else None,
            "edge_when_high": round(edge, 4),
            "p75_threshold": round(p75, 1),
        }

    return importance


# ────────────────────────────────────────────────────────────────────────────
# Main runner
# ────────────────────────────────────────────────────────────────────────────

def run_backtest(tickers: list[str] | None = None,
                 dry_run: bool = False,
                 reference_only: bool = False) -> dict:
    if tickers is None:
        tickers = load_universe()
    # Always include reference tickers
    for rt in REFERENCE_TICKERS:
        if rt not in tickers:
            tickers.append(rt)
    print(f"[readiness] Universe: {len(tickers)} tickers")
    print(f"[readiness] BT window: {BT_START} → {BT_END}")
    print(f"[readiness] Thresholds: {THRESHOLDS}")

    # Phase 1: Pull bars
    print("\n── Phase 1: Pulling daily bars ──")
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
        if dry_run and i >= 6:
            break

    # Phase 2: Compute daily readiness for every ticker
    print(f"\n── Phase 2: Computing readiness scores ({len(all_bars)} tickers) ──")
    all_readiness: dict[str, list[dict]] = {}
    for i, (tk, bars) in enumerate(all_bars.items(), 1):
        scores = readiness_for_bars(bars)
        all_readiness[tk] = scores
        if i <= 3 or i % 30 == 0:
            n_bt = sum(1 for s in scores
                       if pd.Timestamp(BT_START) <= s["date"] <= pd.Timestamp(BT_END))
            print(f"  [{i}/{len(all_bars)}] {tk}: {len(scores)} total, {n_bt} in BT window")

    # Phase 2b: Reference case validation (always runs)
    print("\n── Phase 2b: Reference case validation ──")
    ref_results = _validate_reference_cases(all_bars)
    for tk, ref in ref_results.items():
        status = ref.get("status", "?")
        if status == "OK":
            checks = ref.get("checks", {})
            check_str = ", ".join(f"{k}={v}" for k, v in checks.items())
            scores = [d["score"] for d in ref.get("daily", [])]
            print(f"  {tk}: {scores}")
            print(f"    checks: {check_str}")
        else:
            print(f"  {tk}: {status}")

    if reference_only:
        result = {
            "run_date": str(pd.Timestamp.now().date()),
            "mode": "reference_only",
            "reference_cases": ref_results,
            "weights": DEFAULT_WEIGHTS,
        }
        _save_result(result)
        return result

    # Phase 3: Build trigger events per threshold + baseline
    print(f"\n── Phase 3: Trigger events + baseline ──")
    bt_start = pd.Timestamp(BT_START)
    bt_end = pd.Timestamp(BT_END)

    # Baseline: every (ticker, date) pair
    baseline_events: list[dict] = []
    # All scored events (for component importance)
    all_scored_events: list[dict] = []
    # Per-threshold triggers
    threshold_triggers: dict[int, list[dict]] = {t: [] for t in THRESHOLDS}

    total_dates = 0
    total_brackets = 0

    for tk, scores in all_readiness.items():
        bars = all_bars[tk]
        bt_scores = [s for s in scores if bt_start <= s["date"] <= bt_end]
        if not bt_scores:
            continue

        # Per-threshold: track last trigger date for cooldown
        last_trigger: dict[int, pd.Timestamp | None] = {t: None for t in THRESHOLDS}

        for s in bt_scores:
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
                "score": s["score"],
                "stage": s["stage"],
                "components": s["components"],
                "fwd": fwd,
            }

            baseline_events.append(ev)
            all_scored_events.append(ev)

            # Check threshold crossings
            score = s["score"]
            for t in THRESHOLDS:
                if score >= t:
                    lt = last_trigger[t]
                    if lt is None or (dt - lt).days >= COOLDOWN:
                        threshold_triggers[t].append(ev)
                        last_trigger[t] = dt

    print(f"  Total dates scanned: {total_dates:,}")
    print(f"  Valid brackets: {total_brackets:,}")
    print(f"  Baseline events: {len(baseline_events):,}")
    for t in THRESHOLDS:
        print(f"  Threshold {t}: {len(threshold_triggers[t]):,} triggers")

    # Phase 4: Compute stats
    print(f"\n── Phase 4: Stats ──")
    bl_stats = _bucket_stats(baseline_events)
    bl_tp1 = bl_stats["tp1_win_rate"]

    threshold_results = {}
    best_threshold = None
    best_edge = -999

    for t in THRESHOLDS:
        evs = threshold_triggers[t]
        stats = _bucket_stats(evs, bl_tp1)
        tp = _time_profile(evs)

        # Trajectory cross-test within this threshold
        traj_buckets: dict[str, list[dict]] = {
            "BUILDING": [], "STABLE": [], "CHOPPY": [], "DEGRADING": [],
        }
        for ev in evs:
            tk_scores = all_readiness.get(ev["ticker"], [])
            ev_date = pd.Timestamp(ev["date"])
            idx = None
            for si, s in enumerate(tk_scores):
                if s["date"] == ev_date:
                    idx = si
                    break
            if idx is not None and idx >= 4:
                s5 = [tk_scores[idx - 4 + j]["score"] for j in range(5)]
                traj = classify_trajectory(s5)
            else:
                traj = "CHOPPY"
            if traj in traj_buckets:
                traj_buckets[traj].append(ev)

        traj_stats = {k: _bucket_stats(v, bl_tp1) for k, v in traj_buckets.items()}

        threshold_results[str(t)] = {
            "stats": stats,
            "time_profile": tp,
            "trajectory": traj_stats,
        }

        edge = stats["edge_vs_baseline"]
        if stats["n"] >= 50 and edge > best_edge:
            best_edge = edge
            best_threshold = t

    # Phase 5: Component importance
    print(f"\n── Phase 5: Component importance ──")
    importance = _component_importance(all_scored_events, bl_tp1)
    for comp, imp in importance.items():
        corr = imp.get("correlation", 0) or 0
        edge = imp.get("edge_when_high", 0) or 0
        print(f"  {comp:15s}  corr={corr:+.3f}  edge_high={edge:+.3f}")

    # Phase 6: Build result
    print(f"\n── Phase 6: Results ──")

    # Pass/fail
    pf: dict = {}
    if best_threshold is not None:
        bt = threshold_results[str(best_threshold)]
        bt_stats = bt["stats"]
        pf["readiness_signal"] = {
            "criterion": f"Threshold {best_threshold}: TP1 win >= baseline+5pp, n>=50, "
                         f"days_to_tp1 4-8, drawdown shallower than baseline",
            "verdict": "PASS" if (
                bt_stats["edge_vs_baseline"] >= 0.05
                and bt_stats["n"] >= 50
                and 4 <= bt_stats["avg_days_to_tp1"] <= 8
                and bt_stats["avg_dd_pct"] > bl_stats["avg_dd_pct"]
            ) else "FAIL",
            "best_threshold": best_threshold,
            "edge": bt_stats["edge_vs_baseline"],
            "n": bt_stats["n"],
        }

        # Trajectory adds edge?
        bld = bt["trajectory"].get("BUILDING", {})
        chp = bt["trajectory"].get("CHOPPY", {})
        pf["trajectory_filter"] = {
            "criterion": "BUILDING adds >= 3pp edge over CHOPPY within best threshold",
            "verdict": "PASS" if (
                bld.get("n", 0) >= 30
                and bld.get("tp1_win_rate", 0) - chp.get("tp1_win_rate", 0) >= 0.03
            ) else "FAIL",
        }
    else:
        pf["readiness_signal"] = {
            "criterion": "No threshold with n>=50",
            "verdict": "FAIL",
            "best_threshold": None,
        }
        pf["trajectory_filter"] = {"criterion": "N/A", "verdict": "FAIL"}

    result = {
        "run_date": str(pd.Timestamp.now().date()),
        "universe_size": len(tickers),
        "date_range": {"from": BT_START, "to": BT_END},
        "bracket_method": "ATR14 x 2.0 DSL, TP1 = 1.5R, TP2 = 2.0R",
        "max_forward_days": FORWARD_SESSIONS,
        "cooldown_sessions": COOLDOWN,
        "weights": DEFAULT_WEIGHTS,
        "total_dates_scanned": total_dates,
        "total_brackets": total_brackets,
        "data_unavailable": failed,
        "baseline": bl_stats,
        "baseline_time_profile": _time_profile(baseline_events),
        "thresholds": threshold_results,
        "best_threshold": best_threshold,
        "component_importance": importance,
        "reference_cases": ref_results,
        "pass_fail": pf,
    }

    _save_result(result)
    _print_summary(result)
    return result


def _save_result(result: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "mathlab_readiness.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  Results → {out_path}")


def _print_summary(result: dict) -> None:
    bl = result.get("baseline", {})
    bl_tp1 = bl.get("tp1_win_rate", 0) * 100

    print("\n" + "=" * 78)
    print("  AQE READINESS SCORE — BACKTEST RESULTS")
    print("=" * 78)
    print(f"  Universe: {result['universe_size']} tickers | "
          f"Dates: {result['total_dates_scanned']:,} | "
          f"Brackets: {result['total_brackets']:,}")
    print(f"  Baseline TP1: {bl_tp1:.1f}% | SL: {bl.get('sl_hit_rate',0)*100:.1f}% | "
          f"DD: {bl.get('avg_dd_pct',0):+.2f}%")

    print(f"\n── THRESHOLD RESULTS ──")
    print(f"  {'Thresh':>6s}  {'N':>6s}  {'TP1%':>6s}  {'Edge':>6s}  {'SL%':>6s}  "
          f"{'DD%':>7s}  {'d→TP1':>5s}  {'TP1→2':>5s}")
    for t in THRESHOLDS:
        ts = result["thresholds"].get(str(t), {}).get("stats", {})
        edge = ts.get("edge_vs_baseline", 0) * 100
        marker = " ◀" if t == result.get("best_threshold") else ""
        print(f"  {t:>6d}  {ts.get('n',0):>6d}  "
              f"{ts.get('tp1_win_rate',0)*100:>5.1f}%  "
              f"{edge:>+5.1f}  "
              f"{ts.get('sl_hit_rate',0)*100:>5.1f}%  "
              f"{ts.get('avg_dd_pct',0):>+6.2f}%  "
              f"{ts.get('avg_days_to_tp1',0):>5.1f}  "
              f"{ts.get('tp1_then_tp2_rate',0)*100:>5.1f}%{marker}")

    bt = result.get("best_threshold")
    if bt:
        traj = result["thresholds"][str(bt)].get("trajectory", {})
        print(f"\n── TRAJECTORY CROSS-TEST (threshold={bt}) ──")
        for tr in ("BUILDING", "STABLE", "CHOPPY", "DEGRADING"):
            ts = traj.get(tr, {})
            print(f"  {tr:15s}  n={ts.get('n',0):>5d}  "
                  f"TP1={ts.get('tp1_win_rate',0)*100:>5.1f}%  "
                  f"Edge={ts.get('edge_vs_baseline',0)*100:>+5.1f}pp")

    # Time profile for best threshold
    if bt:
        tp = result["thresholds"][str(bt)].get("time_profile", {})
        bl_tp = result.get("baseline_time_profile", {})
        print(f"\n── TIME PROFILE (threshold={bt} vs baseline) ──")
        header = f"  {'':15s}"
        for h in RETURN_HORIZONS:
            header += f"  T+{h:>2d}"
        print(header)
        row_sig = f"  {'Signal':15s}"
        row_bl = f"  {'Baseline':15s}"
        for h in RETURN_HORIZONS:
            k = f"T+{h}"
            row_sig += f"  {tp.get(k,{}).get('avg_return_pct',0):>+5.2f}"
            row_bl += f"  {bl_tp.get(k,{}).get('avg_return_pct',0):>+5.2f}"
        print(row_sig)
        print(row_bl)

    # Component importance
    print(f"\n── COMPONENT IMPORTANCE ──")
    imp = result.get("component_importance", {})
    sorted_imp = sorted(imp.items(), key=lambda x: abs(x[1].get("correlation", 0) or 0), reverse=True)
    for comp, data in sorted_imp:
        corr = data.get("correlation", 0) or 0
        edge = data.get("edge_when_high", 0) or 0
        print(f"  {comp:15s}  corr={corr:+.4f}  edge_high={edge:+.4f}")

    # Reference cases
    print(f"\n── REFERENCE CASES ──")
    for tk in REFERENCE_TICKERS:
        ref = result.get("reference_cases", {}).get(tk, {})
        if ref.get("status") == "OK":
            daily = ref.get("daily", [])
            scores = [d["score"] for d in daily]
            stages = [d["stage"] for d in daily[-3:]] if len(daily) >= 3 else []
            checks = ref.get("checks", {})
            pass_checks = sum(1 for v in checks.values() if v is True)
            total_checks = sum(1 for v in checks.values() if v is not None)
            print(f"  {tk}: {scores}")
            print(f"    Last 3 stages: {stages}")
            print(f"    Checks: {pass_checks}/{total_checks} pass — {checks}")
        else:
            print(f"  {tk}: {ref.get('status', '?')}")

    # Pass/fail
    print(f"\n── PASS / FAIL ──")
    pf = result.get("pass_fail", {})
    for key, entry in pf.items():
        v = entry.get("verdict", "?")
        marker = "✓" if v == "PASS" else "✗"
        print(f"  {marker} {key}: {v}")
        print(f"    ({entry.get('criterion', '')})")

    print()


# ────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AQE Readiness Score Backtest")
    parser.add_argument("--dry-run", action="store_true",
                        help="First 6 tickers only (incl. reference)")
    parser.add_argument("--refresh", action="store_true",
                        help="Force re-pull all bars from FMP")
    parser.add_argument("--reference-only", action="store_true",
                        help="Only compute reference cases (VSCO/BROS/CAT)")
    args = parser.parse_args()

    if args.refresh:
        import shutil
        if CACHE_DIR.exists():
            n = len(list(CACHE_DIR.glob("*.parquet")))
            print(f"[readiness] --refresh: clearing {n} cached files")
            shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    run_backtest(dry_run=args.dry_run, reference_only=args.reference_only)
