"""AQE Math Lab — Backtest v2.0 (FMP-Native).

Validates three enrichment signals over history:
  1. setup_state  (BREAKOUT-READY / CONTINUATION-READY vs BASING / EXTENDED)
  2. rs_down_day_20d  (LEADER vs IN-LINE vs LAGGARD)
  3. breakout_conviction  (Grade A > B > C > D monotonicity)

Data: FMP daily OHLCV only — all signals reconstructed from price/volume.
Universe: current AQE longlist + elder_list (~22–156 names).
Date range: 2025-01-01 → 2026-05-30 (warm-up from 2024-10-01).

Usage:
    python -m src.mathlab.backtest_v2                    # full run
    python -m src.mathlab.backtest_v2 --dry-run          # reference cases only
    python -m src.mathlab.backtest_v2 --tickers VSCO BROS CAT  # subset
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ────────────────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────────────────
WARMUP_START = "2024-10-01"
BT_START = "2025-01-01"
BT_END = "2026-05-30"
FORWARD_SESSIONS = 10

STOP_PCT = 0.05           # 5% proxy stop
TP1_PCT = 0.07            # 7% proxy TP1

EXPANSION_THRESHOLD = 1.3  # range > 1.3× base avg = breakout bar
BASE_LOOKBACK = 15

CACHE_DIR = Path("data/mathlab_cache")
OUTPUT_DIR = Path("output")

# ────────────────────────────────────────────────────────────────────────────
# Data pulling + caching
# ────────────────────────────────────────────────────────────────────────────

def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}_daily.parquet"


def pull_daily_bars(ticker: str, force: bool = False) -> pd.DataFrame:
    """Pull daily OHLCV from FMP and cache to disk. Returns empty on failure."""
    p = _cache_path(ticker)
    if p.exists() and not force:
        return pd.read_parquet(p)

    from src.data.fmp_client import FMPClient, FMPError
    try:
        fc = FMPClient()
        df = fc.get_daily_bars(ticker, from_date=WARMUP_START, to_date=BT_END)
        if df.empty:
            return df
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p, index=False)
        return df
    except FMPError as e:
        print(f"  [!] {ticker}: FMP error — {e}")
        return pd.DataFrame()


def load_universe() -> list[str]:
    """Load tickers from the current AQE export."""
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
# Signal reconstruction (from raw bars — no elder_context available)
# ────────────────────────────────────────────────────────────────────────────

def _bars_up_to(df: pd.DataFrame, date_t: pd.Timestamp, n: int) -> pd.DataFrame:
    mask = df["date"] <= date_t
    return df[mask].tail(n)


def reconstruct_rs_down_day(ticker_bars: pd.DataFrame,
                            spy_bars: pd.DataFrame,
                            date_t: pd.Timestamp) -> tuple[float | None, str]:
    """RS down-day from raw bars. Returns (value, leadership)."""
    tb = _bars_up_to(ticker_bars, date_t, 21)
    sb = _bars_up_to(spy_bars, date_t, 21)
    if len(tb) < 21 or len(sb) < 21:
        return None, "INSUFFICIENT"

    tc = tb["close"].to_numpy(dtype=float)
    sc = sb["close"].to_numpy(dtype=float)

    tk_ret = np.diff(tc) / tc[:-1]
    sp_ret = np.diff(sc) / sc[:-1]

    down = sp_ret < 0
    if not np.any(down):
        return None, "INSUFFICIENT"

    outperf = tk_ret[down] - sp_ret[down]
    avg = float(np.mean(outperf))
    if avg > 0.0025:
        leadership = "LEADER"
    elif avg < -0.0025:
        leadership = "LAGGARD"
    else:
        leadership = "IN-LINE"
    return round(avg * 100, 2), leadership


def reconstruct_setup_state(bars: pd.DataFrame,
                            date_t: pd.Timestamp) -> str:
    """Setup state from raw daily bars (VCP proxy, no elder_context)."""
    b = _bars_up_to(bars, date_t, 60)
    if len(b) < 20:
        return "BASING"

    cl = b["close"].to_numpy(dtype=float)
    hi = b["high"].to_numpy(dtype=float)
    lo = b["low"].to_numpy(dtype=float)
    vol = b["volume"].to_numpy(dtype=float)

    last_close = float(cl[-1])
    ma10 = float(np.mean(cl[-10:]))
    ma20 = float(np.mean(cl[-20:]))
    ma50 = float(np.mean(cl[-min(50, len(cl)):])) if len(cl) >= 10 else ma20

    price_vs_ma10 = (last_close - ma10) / ma10 * 100 if ma10 > 0 else 0

    if price_vs_ma10 > 8:
        return "EXTENDED"

    ma_stack = ma10 > ma20 > ma50

    # ATR proxy
    tr = np.maximum(hi[1:] - lo[1:],
                    np.maximum(np.abs(hi[1:] - cl[:-1]),
                               np.abs(lo[1:] - cl[:-1])))
    atr14 = float(np.mean(tr[-14:])) if len(tr) >= 14 else float(np.mean(tr))
    range_5d = float(np.mean(hi[-5:] - lo[-5:]))
    atr_op = max(atr14, range_5d) if atr14 > 0 else range_5d

    # Dynamic base detection: walk back for last thrust bar
    base_start = len(b) - 1
    for i in range(len(b) - 2, max(0, len(b) - 30) - 1, -1):
        r = float(hi[i] - lo[i])
        if atr_op > 0 and r > 2 * atr_op:
            base_start = i + 1
            break
    else:
        base_start = max(0, len(b) - 20)

    base_start = max(base_start, 0)
    if base_start >= len(b):
        base_start = max(0, len(b) - 10)

    base_hi = hi[base_start:]
    base_vol = vol[base_start:]
    base_lo = lo[base_start:]

    if len(base_hi) < 3:
        return "BASING"

    base_high = float(np.max(base_hi))
    near_base_high = (base_high - last_close) / base_high * 100 < 2.5 if base_high > 0 else False

    # VCP proxy: volume compression + range compression
    base_max_vol = float(np.max(base_vol[:-1])) if len(base_vol) > 1 else float(base_vol[0])
    vcr = float(vol[-1]) / base_max_vol if base_max_vol > 0 else 1.0
    base_avg_range = float(np.mean(base_hi - base_lo))
    range_compression = base_avg_range / atr_op if atr_op > 0 else 1.0

    # VWAP proxy: use typical price as VWAP approximation
    tp_today = (float(hi[-1]) + float(lo[-1]) + last_close) / 3
    vwap_above = last_close > tp_today

    if (vcr < 0.65 and range_compression < 1.3 and near_base_high
            and ma_stack and vwap_above):
        return "BREAKOUT-READY"

    if ma_stack and abs(price_vs_ma10) < 2.5:
        return "CONTINUATION-READY"

    return "BASING"


@dataclass
class BreakoutResult:
    score: int | None = None
    grade: str | None = None
    pattern: str | None = None


def reconstruct_breakout_conviction(bars: pd.DataFrame,
                                    date_t: pd.Timestamp) -> BreakoutResult:
    """Breakout conviction from raw bars. Only fires on expansion bars."""
    b = _bars_up_to(bars, date_t, 30)
    if len(b) < 16:
        return BreakoutResult()

    hi = b["high"].to_numpy(dtype=float)
    lo = b["low"].to_numpy(dtype=float)
    cl = b["close"].to_numpy(dtype=float)
    op = b["open"].to_numpy(dtype=float)
    vol = b["volume"].to_numpy(dtype=float)

    # Base avg range (last 15 bars before today)
    base_ranges = hi[:-1] - lo[:-1]
    base_avg_range = float(np.mean(base_ranges[-BASE_LOOKBACK:]))
    if base_avg_range <= 0:
        return BreakoutResult()

    today_range = float(hi[-1] - lo[-1])
    if today_range < EXPANSION_THRESHOLD * base_avg_range:
        return BreakoutResult()

    t0_o, t0_h, t0_l, t0_c = float(op[-1]), float(hi[-1]), float(lo[-1]), float(cl[-1])
    t0_v = float(vol[-1])
    t1_h, t1_l, t1_c = float(hi[-2]), float(lo[-2]), float(cl[-2])
    t0_range = t0_h - t0_l

    # Five inputs
    t1_range = t1_h - t1_l
    t1_cir = (t1_c - t1_l) / t1_range if t1_range > 0 else 0.5
    t1_mid = (t1_h + t1_l + t1_c) / 3
    t1_vwap_pos = (t1_c - t1_mid) / t1_mid if t1_mid > 0 else 0

    # Approach: 4-bar drift
    ref_idx = max(0, len(cl) - 6)
    ref_close = float(cl[ref_idx])
    approach = (t1_c - ref_close) / ref_close if ref_close > 0 else 0

    bo_cir = (t0_c - t0_l) / t0_range if t0_range > 0 else 0.5
    base_vols = vol[-11:-1]
    avg_base_vol = float(np.mean(base_vols)) if len(base_vols) > 0 else 1.0
    vol_exp = t0_v / avg_base_vol if avg_base_vol > 0 else 1.0

    # Pattern detection
    gap = (t0_o - t1_c) / t1_c if t1_c > 0 else 0
    absorption = gap < -0.005 and bo_cir > 0.90
    telegraphed = t1_cir > 0.70 and approach > 0.01

    if absorption:
        pattern = "ABSORPTION_REVERSAL"
    elif telegraphed:
        pattern = "TELEGRAPHED_CONTINUATION"
    elif t1_cir < 0.40 and not absorption:
        pattern = "SURPRISE_THRUST"
    else:
        pattern = "STANDARD_BREAKOUT"

    # Score
    score = 0.0
    score += min(25, t1_cir * 20 + (10 if t1_vwap_pos > 0 else 3))
    score += min(15, max(0, approach * 300)) if approach > 0 else 5
    score += min(25, bo_cir * 25)
    score += min(20, vol_exp / 4 * 20)
    score += min(10, t0_range / base_avg_range * 5)
    if absorption:
        score += 10
    score = min(100.0, score)

    grade = "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"
    return BreakoutResult(score=round(score), grade=grade, pattern=pattern)


# ────────────────────────────────────────────────────────────────────────────
# Outcome measurement
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class Outcome:
    result: str         # HIT_TP1 / STOPPED / OPEN
    days: int | None
    mfe_pct: float      # max favourable excursion %
    mae_pct: float      # max adverse excursion %


def measure_outcome(bars: pd.DataFrame, date_t: pd.Timestamp,
                    entry: float) -> Outcome:
    """Scan forward up to FORWARD_SESSIONS from trigger date."""
    fwd = bars[bars["date"] > date_t].head(FORWARD_SESSIONS)
    if fwd.empty:
        return Outcome("OPEN", None, 0.0, 0.0)

    sl = entry * (1 - STOP_PCT)
    tp1 = entry * (1 + TP1_PCT)

    highs = fwd["high"].to_numpy(dtype=float)
    lows = fwd["low"].to_numpy(dtype=float)

    mfe = float(np.max(highs) - entry) / entry * 100 if len(highs) > 0 else 0
    mae = float(np.min(lows) - entry) / entry * 100 if len(lows) > 0 else 0

    for i in range(len(fwd)):
        if float(lows[i]) <= sl:
            return Outcome("STOPPED", i + 1, mfe, mae)
        if float(highs[i]) >= tp1:
            return Outcome("HIT_TP1", i + 1, mfe, mae)

    return Outcome("OPEN", None, mfe, mae)


# ────────────────────────────────────────────────────────────────────────────
# Trigger event
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class TriggerEvent:
    ticker: str
    date: str
    setup_state: str
    rs_leadership: str
    rs_value: float | None
    breakout_grade: str | None
    breakout_pattern: str | None
    breakout_score: int | None
    outcome: Outcome | None = None


# ────────────────────────────────────────────────────────────────────────────
# Main runner
# ────────────────────────────────────────────────────────────────────────────

def _trading_dates(bars: pd.DataFrame) -> list[pd.Timestamp]:
    """Trading dates in the backtest window."""
    start = pd.Timestamp(BT_START)
    end = pd.Timestamp(BT_END)
    dates = bars["date"].unique()
    return sorted(d for d in dates if start <= d <= end)


def run_backtest(tickers: list[str] | None = None,
                 dry_run: bool = False) -> dict:
    """Run the full backtest. Returns the result dict per spec."""
    if tickers is None:
        tickers = load_universe()
    print(f"[mathlab] Universe: {len(tickers)} tickers")
    print(f"[mathlab] Date range: {BT_START} → {BT_END}")
    print(f"[mathlab] Proxies: stop={STOP_PCT*100:.0f}%, TP1={TP1_PCT*100:.0f}%")

    # Phase 1: pull + cache all daily bars
    print("\n── Phase 1: Pulling daily bars ──")
    all_bars: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for i, tk in enumerate(tickers, 1):
        print(f"  [{i}/{len(tickers)}] {tk}...", end=" ", flush=True)
        df = pull_daily_bars(tk)
        if df.empty:
            print("EMPTY")
            failed.append(tk)
        else:
            all_bars[tk] = df
            print(f"{len(df)} bars")

    # SPY
    print("  [SPY]...", end=" ", flush=True)
    spy_bars = pull_daily_bars("SPY")
    print(f"{len(spy_bars)} bars" if not spy_bars.empty else "EMPTY")

    if spy_bars.empty:
        raise RuntimeError("Cannot run without SPY data")

    # Phase 2: reconstruct signals + record triggers
    print(f"\n── Phase 2: Signal reconstruction ({len(all_bars)} tickers) ──")
    triggers: list[TriggerEvent] = []
    ticker_count = 0

    for tk, bars in all_bars.items():
        ticker_count += 1
        dates = _trading_dates(bars)
        if not dates:
            continue
        if ticker_count % 20 == 0 or ticker_count <= 3:
            print(f"  [{ticker_count}/{len(all_bars)}] {tk}: {len(dates)} dates")

        for dt in dates:
            state = reconstruct_setup_state(bars, dt)
            rs_val, rs_lead = reconstruct_rs_down_day(bars, spy_bars, dt)
            bo = reconstruct_breakout_conviction(bars, dt)

            # Always record a setup_state trigger
            ev = TriggerEvent(
                ticker=tk, date=str(dt.date()),
                setup_state=state,
                rs_leadership=rs_lead, rs_value=rs_val,
                breakout_grade=bo.grade,
                breakout_pattern=bo.pattern,
                breakout_score=bo.score,
            )

            # Outcome measurement
            entry = float(bars[bars["date"] == dt]["close"].iloc[0])
            ev.outcome = measure_outcome(bars, dt, entry)
            triggers.append(ev)

        if dry_run and ticker_count >= 4:
            break

    print(f"\n── Phase 3: Aggregation ({len(triggers)} trigger events) ──")

    # Phase 3: aggregate
    result = _build_result(triggers, tickers, failed)

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "mathlab_backtest_v2.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n✓ Results written to {out_path}")

    # Print summary
    _print_summary(result)
    return result


def _build_result(triggers: list[TriggerEvent],
                  universe: list[str],
                  failed: list[str]) -> dict:
    """Aggregate triggers into the spec output format."""
    from datetime import date as _date

    result: dict = {
        "run_date": _date.today().isoformat(),
        "universe_size": len(universe),
        "date_range": {"from": BT_START, "to": BT_END},
        "stop_proxy": f"{STOP_PCT*100:.0f}% below entry",
        "tp1_proxy": f"{TP1_PCT*100:.0f}% above entry",
        "total_trigger_events": len(triggers),
        "data_unavailable": failed,
    }

    # ── setup_state ──
    setup_buckets: dict[str, list[TriggerEvent]] = {
        "BREAKOUT-READY": [], "CONTINUATION-READY": [],
        "BASING": [], "EXTENDED": [],
    }
    for ev in triggers:
        if ev.setup_state in setup_buckets:
            setup_buckets[ev.setup_state].append(ev)

    result["setup_state"] = {}
    for state, evs in setup_buckets.items():
        result["setup_state"][state] = _bucket_stats(evs)

    # ── rs_leadership ──
    rs_buckets: dict[str, list[TriggerEvent]] = {
        "LEADER": [], "IN-LINE": [], "LAGGARD": [],
    }
    for ev in triggers:
        if ev.rs_leadership in rs_buckets:
            rs_buckets[ev.rs_leadership].append(ev)

    result["rs_leadership"] = {}
    for lead, evs in rs_buckets.items():
        result["rs_leadership"][lead] = _bucket_stats(evs)

    # ── breakout_conviction_grade (expansion bars only) ──
    grade_buckets: dict[str, list[TriggerEvent]] = {
        "A": [], "B": [], "C": [], "D": [],
    }
    for ev in triggers:
        if ev.breakout_grade and ev.breakout_grade in grade_buckets:
            grade_buckets[ev.breakout_grade].append(ev)

    result["breakout_conviction_grade"] = {}
    for grade, evs in grade_buckets.items():
        result["breakout_conviction_grade"][grade] = _bucket_stats(evs)

    # ── breakout_pattern ──
    pattern_buckets: dict[str, list[TriggerEvent]] = {
        "TELEGRAPHED_CONTINUATION": [],
        "ABSORPTION_REVERSAL": [],
        "SURPRISE_THRUST": [],
        "STANDARD_BREAKOUT": [],
    }
    for ev in triggers:
        if ev.breakout_pattern and ev.breakout_pattern in pattern_buckets:
            pattern_buckets[ev.breakout_pattern].append(ev)

    result["breakout_pattern"] = {}
    for pat, evs in pattern_buckets.items():
        result["breakout_pattern"][pat] = _bucket_stats(evs)

    # ── sample warnings ──
    warnings = []
    for state, evs in setup_buckets.items():
        if 0 < len(evs) < 30:
            warnings.append(f"{state}: only {len(evs)} events (< 30 min for significance)")
    for grade, evs in grade_buckets.items():
        if 0 < len(evs) < 30:
            warnings.append(f"Grade {grade}: only {len(evs)} events (< 30 min)")
    result["sample_warnings"] = warnings

    # ── reference cases ──
    ref = {}
    ref_cases = [
        ("VSCO", "2026-06-26", {
            "expected_setup_state": "BREAKOUT-READY",
            "expected_rs_leadership": "LEADER",
            "expected_breakout_grade": "A",
            "expected_breakout_pattern": "TELEGRAPHED_CONTINUATION",
        }),
        ("BROS", "2026-06-26", {
            "expected_setup_state": "BREAKOUT-READY or CONTINUATION-READY",
            "expected_rs_leadership": "LEADER",
            "expected_breakout_grade": "B or C",
            "expected_breakout_pattern": "ABSORPTION_REVERSAL",
        }),
        ("BROS", "2026-06-18", {
            "expected_breakout_grade": "C or D",
            "expected_outcome": "STOPPED",
            "note": "Fake breakout — should score lower than Jun 26",
        }),
        ("CAT", "2026-06-26", {
            "expected_rs_leadership": "LAGGARD",
            "expected_setup_state": "EXTENDED",
            "note": "Fell 3.3% on market down day",
        }),
    ]
    for tk, dt, expected in ref_cases:
        key = f"{tk}_{dt}"
        matching = [e for e in triggers
                    if e.ticker == tk and e.date == dt]
        if matching:
            ev = matching[0]
            ref[key] = {
                "setup_state": ev.setup_state,
                "rs_leadership": ev.rs_leadership,
                "breakout_grade": ev.breakout_grade,
                "breakout_pattern": ev.breakout_pattern,
                "outcome": ev.outcome.result if ev.outcome else None,
                **expected,
            }
        else:
            ref[key] = {"actual": "NO DATA (ticker not in universe or date out of range)", **expected}
    result["reference_cases"] = ref

    # ── pass/fail ──
    pf: dict = {}
    ss = result["setup_state"]
    br_hit = ss.get("BREAKOUT-READY", {}).get("hit_tp1", 0)
    bs_hit = ss.get("BASING", {}).get("hit_tp1", 0)
    br_n = ss.get("BREAKOUT-READY", {}).get("n", 0)
    pf["setup_state_hypothesis"] = (
        "PASS" if (br_hit - bs_hit) >= 0.10 and br_n >= 30 else "FAIL"
    )

    rs = result["rs_leadership"]
    ld_hit = rs.get("LEADER", {}).get("hit_tp1", 0)
    il_hit = rs.get("IN-LINE", {}).get("hit_tp1", 0)
    ld_n = rs.get("LEADER", {}).get("n", 0)
    pf["rs_leadership_hypothesis"] = (
        "PASS" if (ld_hit - il_hit) >= 0.08 and ld_n >= 30 else "FAIL"
    )

    grades = ["A", "B", "C", "D"]
    grade_hits = [result["breakout_conviction_grade"].get(g, {}).get("hit_tp1", 0)
                  for g in grades]
    grade_ns = [result["breakout_conviction_grade"].get(g, {}).get("n", 0)
                for g in grades]
    monotonic = all(grade_hits[i] >= grade_hits[i + 1]
                    for i in range(len(grade_hits) - 1)
                    if grade_ns[i] > 0 and grade_ns[i + 1] > 0)
    sufficient = all(n >= 30 for n in grade_ns if n > 0)
    pf["breakout_conviction_hypothesis"] = (
        "PASS" if monotonic and sufficient else "FAIL"
    )
    pf["notes"] = ""
    result["pass_fail"] = pf

    return result


def _bucket_stats(events: list[TriggerEvent]) -> dict:
    """Compute hit rates and averages for a bucket of trigger events."""
    n = len(events)
    if n == 0:
        return {"n": 0, "hit_tp1": 0.0, "stopped": 0.0, "open": 0.0,
                "avg_mfe_pct": 0.0, "avg_mae_pct": 0.0, "avg_days_to_tp1": 0.0}

    hit = sum(1 for e in events if e.outcome and e.outcome.result == "HIT_TP1")
    stopped = sum(1 for e in events if e.outcome and e.outcome.result == "STOPPED")
    open_ = sum(1 for e in events if e.outcome and e.outcome.result == "OPEN")

    mfes = [e.outcome.mfe_pct for e in events if e.outcome]
    maes = [e.outcome.mae_pct for e in events if e.outcome]
    days_tp1 = [e.outcome.days for e in events
                if e.outcome and e.outcome.result == "HIT_TP1" and e.outcome.days]

    return {
        "n": n,
        "hit_tp1": round(hit / n, 3),
        "stopped": round(stopped / n, 3),
        "open": round(open_ / n, 3),
        "avg_mfe_pct": round(float(np.mean(mfes)), 2) if mfes else 0.0,
        "avg_mae_pct": round(float(np.mean(maes)), 2) if maes else 0.0,
        "avg_days_to_tp1": round(float(np.mean(days_tp1)), 1) if days_tp1 else 0.0,
    }


def _print_summary(result: dict) -> None:
    """Print a human-readable summary."""
    print("\n" + "=" * 72)
    print("  AQE MATH LAB — BACKTEST v2.0 RESULTS")
    print("=" * 72)
    print(f"  Universe: {result['universe_size']} tickers")
    print(f"  Date range: {result['date_range']['from']} → {result['date_range']['to']}")
    print(f"  Total trigger events: {result['total_trigger_events']}")

    print("\n── SETUP STATE ──")
    for state in ("BREAKOUT-READY", "CONTINUATION-READY", "BASING", "EXTENDED"):
        s = result["setup_state"].get(state, {})
        print(f"  {state:22s}  n={s.get('n',0):5d}  "
              f"TP1={s.get('hit_tp1',0)*100:5.1f}%  "
              f"Stop={s.get('stopped',0)*100:5.1f}%  "
              f"MFE={s.get('avg_mfe_pct',0):+5.1f}%  "
              f"MAE={s.get('avg_mae_pct',0):+5.1f}%")

    print("\n── RS LEADERSHIP ──")
    for lead in ("LEADER", "IN-LINE", "LAGGARD"):
        s = result["rs_leadership"].get(lead, {})
        print(f"  {lead:12s}  n={s.get('n',0):5d}  "
              f"TP1={s.get('hit_tp1',0)*100:5.1f}%  "
              f"Stop={s.get('stopped',0)*100:5.1f}%  "
              f"MFE={s.get('avg_mfe_pct',0):+5.1f}%")

    print("\n── BREAKOUT CONVICTION GRADE ──")
    for grade in ("A", "B", "C", "D"):
        s = result["breakout_conviction_grade"].get(grade, {})
        print(f"  Grade {grade}  n={s.get('n',0):5d}  "
              f"TP1={s.get('hit_tp1',0)*100:5.1f}%  "
              f"Stop={s.get('stopped',0)*100:5.1f}%  "
              f"Days→TP1={s.get('avg_days_to_tp1',0):4.1f}")

    print("\n── BREAKOUT PATTERN ──")
    for pat in ("TELEGRAPHED_CONTINUATION", "ABSORPTION_REVERSAL",
                "SURPRISE_THRUST", "STANDARD_BREAKOUT"):
        s = result["breakout_pattern"].get(pat, {})
        print(f"  {pat:30s}  n={s.get('n',0):5d}  "
              f"TP1={s.get('hit_tp1',0)*100:5.1f}%  "
              f"MFE={s.get('avg_mfe_pct',0):+5.1f}%")

    print("\n── REFERENCE CASES ──")
    for key, rc in result.get("reference_cases", {}).items():
        actual_state = rc.get("setup_state", "?")
        actual_rs = rc.get("rs_leadership", "?")
        actual_grade = rc.get("breakout_grade", "?")
        actual_outcome = rc.get("outcome", "?")
        print(f"  {key}: state={actual_state}  rs={actual_rs}  "
              f"grade={actual_grade}  outcome={actual_outcome}")

    print("\n── PASS / FAIL ──")
    pf = result.get("pass_fail", {})
    for hyp in ("setup_state_hypothesis", "rs_leadership_hypothesis",
                "breakout_conviction_hypothesis"):
        verdict = pf.get(hyp, "?")
        marker = "✓" if verdict == "PASS" else "✗"
        print(f"  {marker} {hyp}: {verdict}")

    if result.get("sample_warnings"):
        print("\n── WARNINGS ──")
        for w in result["sample_warnings"]:
            print(f"  ⚠ {w}")

    print()


# ────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AQE Math Lab Backtest v2.0")
    parser.add_argument("--dry-run", action="store_true",
                        help="Reference cases only (first 4 tickers)")
    parser.add_argument("--tickers", nargs="+",
                        help="Specific tickers to test")
    args = parser.parse_args()

    tickers = args.tickers
    if tickers:
        tickers = [t.upper() for t in tickers]
    run_backtest(tickers=tickers, dry_run=args.dry_run)
