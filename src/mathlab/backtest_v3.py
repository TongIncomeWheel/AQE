"""AQE Math Lab — Backtest v3.1 (Final).

One question: does the signal increase the probability of hitting TP1
within 10 sessions, with less pain on the way there?

Five signal dimensions:
  1. setup_state  (BREAKOUT-READY / CONTINUATION-READY / BASING / EXTENDED)
  2. rs_leadership_v2  (green-on-red: stock UP when SPY DOWN)
  3. breakout_conviction_v2  (A / B / C on expansion bars)
  4. sector_context  (IDIOSYNCRATIC / MIXED / SECTOR_DEPENDENT)
  5. conviction_trend  (BUILDING / STABLE / CHOPPY / DEGRADING)

Bracket: ATR14 × 2.0 DSL, TP1 = 1.5R, TP2 = 2.0R.
Baseline: every (ticker, date) in the universe — no signal filter.

Data: reuses v2 FMP daily cache + 11 sector ETF pulls.
Universe: current AQE longlist + elder_list.

Usage:
    python -m src.mathlab.backtest_v3
    python -m src.mathlab.backtest_v3 --dry-run
    python -m src.mathlab.backtest_v3 --tickers VSCO BROS CAT
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from statistics import median

import numpy as np
import pandas as pd

# ────────────────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────────────────
WARMUP_START = "2024-10-01"
BT_START = "2025-01-01"
BT_END = "2026-05-30"
PULL_END = "2026-06-30"
FORWARD_SESSIONS = 10

EXPANSION_THRESHOLD = 1.3
BASE_LOOKBACK = 15

CACHE_DIR = Path("data/mathlab_cache")
OUTPUT_DIR = Path("output")

SECTOR_ETFS = ["XLK", "XLF", "XLI", "XLV", "XLY", "XLC", "XLE", "XLU", "XLP", "XLB", "XLRE"]

RETURN_HORIZONS = (1, 2, 3, 5, 7, 10)

# ────────────────────────────────────────────────────────────────────────────
# Data pulling + caching (reuses v2 cache)
# ────────────────────────────────────────────────────────────────────────────

def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}_daily.parquet"


def pull_daily_bars(ticker: str, force: bool = False) -> pd.DataFrame:
    p = _cache_path(ticker)
    if p.exists() and not force:
        df = pd.read_parquet(p)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            bt_start_ts = pd.Timestamp(BT_START)
            bt_end_ts = pd.Timestamp(BT_END)
            n_bt = int(((df["date"] >= bt_start_ts) & (df["date"] <= bt_end_ts)).sum())
            if n_bt < 200 and not force:
                print(f"STALE({n_bt} bt-dates)→re-pull ", end="", flush=True)
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


def load_sector_map() -> dict[str, str]:
    """Load ticker → GICS sector ETF mapping from the AQE sector map."""
    p = Path("data/sector_map.json")
    if not p.exists():
        return {}
    with open(p) as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        mapping = {}
        for tk, v in raw.items():
            if isinstance(v, str):
                mapping[tk] = v
            elif isinstance(v, dict):
                etf = v.get("etf") or v.get("sector_etf") or v.get("gics_sector")
                if etf:
                    mapping[tk] = etf
        return mapping
    return {}


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _bars_up_to(df: pd.DataFrame, date_t: pd.Timestamp, n: int) -> pd.DataFrame:
    return df[df["date"] <= date_t].tail(n)


def _trading_dates(bars: pd.DataFrame) -> list[pd.Timestamp]:
    start, end = pd.Timestamp(BT_START), pd.Timestamp(BT_END)
    return sorted(d for d in bars["date"].unique() if start <= d <= end)


# ────────────────────────────────────────────────────────────────────────────
# Bracket (ATR-based, per spec v3.1)
# ────────────────────────────────────────────────────────────────────────────

def bracket_from_bars(bars: pd.DataFrame, date_t: pd.Timestamp):
    """Compute ATR14-based bracket. Returns (entry, sl, tp1, tp2, risk, atr14) or None."""
    b = _bars_up_to(bars, date_t, 20)
    if len(b) < 15:
        return None

    hi = b["high"].to_numpy(dtype=float)
    lo = b["low"].to_numpy(dtype=float)
    cl = b["close"].to_numpy(dtype=float)

    entry = float(cl[-1])
    if entry <= 0:
        return None

    trs = []
    for i in range(1, len(b)):
        h, l, pc = float(hi[i]), float(lo[i]), float(cl[i - 1])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr14 = float(np.mean(trs[-14:])) if len(trs) >= 14 else float(np.mean(trs))

    if atr14 <= 0:
        return None

    risk = atr14 * 2.0
    sl = entry - risk
    tp1 = entry + risk * 1.5
    tp2 = entry + risk * 2.0

    return entry, sl, tp1, tp2, risk, atr14


# ────────────────────────────────────────────────────────────────────────────
# Forward scan (per spec v3.1)
# ────────────────────────────────────────────────────────────────────────────

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
    max_drawdown_before_tp1_pct: float = 0.0
    forward_returns: dict = field(default_factory=dict)


def scan_forward(bars: pd.DataFrame, date_t: pd.Timestamp,
                 entry: float, sl: float, tp1: float, tp2: float,
                 max_days: int = FORWARD_SESSIONS) -> ForwardResult:
    fwd = bars[bars["date"] > date_t].head(max_days)
    r = ForwardResult()
    if fwd.empty:
        return r

    worst_low = entry
    hi = fwd["high"].to_numpy(dtype=float)
    lo = fwd["low"].to_numpy(dtype=float)
    cl = fwd["close"].to_numpy(dtype=float)

    for n_idx in range(len(fwd)):
        n = n_idx + 1
        bar_hi, bar_lo, bar_cl = float(hi[n_idx]), float(lo[n_idx]), float(cl[n_idx])

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

    r.max_drawdown_before_tp1_pct = round((worst_low - entry) / entry * 100, 3)

    if r.first_event == "NONE":
        r.first_event = "NONE"

    return r


# ────────────────────────────────────────────────────────────────────────────
# Signal 1: setup_state (same logic as v2)
# ────────────────────────────────────────────────────────────────────────────

def reconstruct_setup_state(bars: pd.DataFrame, date_t: pd.Timestamp) -> str:
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

    tr = np.maximum(hi[1:] - lo[1:],
                    np.maximum(np.abs(hi[1:] - cl[:-1]),
                               np.abs(lo[1:] - cl[:-1])))
    atr14 = float(np.mean(tr[-14:])) if len(tr) >= 14 else float(np.mean(tr))
    range_5d = float(np.mean(hi[-5:] - lo[-5:]))
    atr_op = max(atr14, range_5d) if atr14 > 0 else range_5d

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
    if len(base_hi) < 3:
        return "BASING"

    base_high = float(np.max(base_hi))
    near_base_high = (base_high - last_close) / base_high * 100 < 2.5 if base_high > 0 else False

    base_max_vol = float(np.max(base_vol[:-1])) if len(base_vol) > 1 else float(base_vol[0])
    vcr = float(vol[-1]) / base_max_vol if base_max_vol > 0 else 1.0
    base_avg_range = float(np.mean(base_hi - lo[base_start:]))
    range_compression = base_avg_range / atr_op if atr_op > 0 else 1.0

    tp_today = (float(hi[-1]) + float(lo[-1]) + last_close) / 3
    vwap_above = last_close > tp_today

    if (vcr < 0.65 and range_compression < 1.3 and near_base_high
            and ma_stack and vwap_above):
        return "BREAKOUT-READY"

    if ma_stack and abs(price_vs_ma10) < 2.5:
        return "CONTINUATION-READY"

    return "BASING"


# ────────────────────────────────────────────────────────────────────────────
# Signal 2: rs_leadership v2 (green-on-red: stock UP when SPY DOWN)
# ────────────────────────────────────────────────────────────────────────────

def reconstruct_rs_leadership_v2(ticker_bars: pd.DataFrame,
                                 spy_bars: pd.DataFrame,
                                 date_t: pd.Timestamp) -> tuple[float | None, str]:
    tb = _bars_up_to(ticker_bars, date_t, 21)
    sb = _bars_up_to(spy_bars, date_t, 21)
    if len(tb) < 21 or len(sb) < 21:
        return None, "INSUFFICIENT"

    tc = tb["close"].to_numpy(dtype=float)
    sc = sb["close"].to_numpy(dtype=float)

    tk_ret = np.diff(tc) / tc[:-1]
    sp_ret = np.diff(sc) / sc[:-1]

    down_mask = sp_ret < 0
    n_down = int(np.sum(down_mask))
    if n_down == 0:
        return None, "NO_DOWN_DAYS"

    green_on_red = int(np.sum(tk_ret[down_mask] > 0))
    pct = green_on_red / n_down * 100

    if pct >= 50:
        return round(pct, 1), "LEADER"
    elif pct >= 30:
        return round(pct, 1), "IN-LINE"
    else:
        return round(pct, 1), "LAGGARD"


# ────────────────────────────────────────────────────────────────────────────
# Signal 3: breakout_conviction (A/B/C — D merged into C)
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class BreakoutResult:
    score: int | None = None
    grade: str | None = None
    pattern: str | None = None


def reconstruct_breakout_conviction(bars: pd.DataFrame,
                                    date_t: pd.Timestamp) -> BreakoutResult:
    b = _bars_up_to(bars, date_t, 30)
    if len(b) < 16:
        return BreakoutResult()

    hi = b["high"].to_numpy(dtype=float)
    lo = b["low"].to_numpy(dtype=float)
    cl = b["close"].to_numpy(dtype=float)
    op = b["open"].to_numpy(dtype=float)
    vol = b["volume"].to_numpy(dtype=float)

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

    t1_range = t1_h - t1_l
    t1_cir = (t1_c - t1_l) / t1_range if t1_range > 0 else 0.5
    t1_mid = (t1_h + t1_l + t1_c) / 3
    t1_vwap_pos = (t1_c - t1_mid) / t1_mid if t1_mid > 0 else 0

    ref_idx = max(0, len(cl) - 6)
    ref_close = float(cl[ref_idx])
    approach = (t1_c - ref_close) / ref_close if ref_close > 0 else 0

    bo_cir = (t0_c - t0_l) / t0_range if t0_range > 0 else 0.5
    base_vols = vol[-11:-1]
    avg_base_vol = float(np.mean(base_vols)) if len(base_vols) > 0 else 1.0
    vol_exp = t0_v / avg_base_vol if avg_base_vol > 0 else 1.0

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

    score = 0.0
    score += min(25, t1_cir * 20 + (10 if t1_vwap_pos > 0 else 3))
    score += min(15, max(0, approach * 300)) if approach > 0 else 5
    score += min(25, bo_cir * 25)
    score += min(20, vol_exp / 4 * 20)
    score += min(10, t0_range / base_avg_range * 5)
    if absorption:
        score += 10
    score = min(100.0, score)

    grade = "A" if score >= 80 else "B" if score >= 65 else "C"
    return BreakoutResult(score=round(score), grade=grade, pattern=pattern)


# ────────────────────────────────────────────────────────────────────────────
# Signal 4: sector_context (20d correlation with sector ETF)
# ────────────────────────────────────────────────────────────────────────────

def reconstruct_sector_context(ticker_bars: pd.DataFrame,
                               sector_etf_bars: pd.DataFrame | None,
                               date_t: pd.Timestamp) -> tuple[float | None, str]:
    if sector_etf_bars is None or sector_etf_bars.empty:
        return None, "MIXED"

    tb = _bars_up_to(ticker_bars, date_t, 21)
    sb = _bars_up_to(sector_etf_bars, date_t, 21)
    if len(tb) < 21 or len(sb) < 21:
        return None, "MIXED"

    tc = tb["close"].to_numpy(dtype=float)
    sc = sb["close"].to_numpy(dtype=float)

    tk_ret = np.diff(tc) / tc[:-1]
    se_ret = np.diff(sc) / sc[:-1]

    if len(tk_ret) < 10 or len(se_ret) < 10:
        return None, "MIXED"

    min_len = min(len(tk_ret), len(se_ret))
    tk_ret = tk_ret[-min_len:]
    se_ret = se_ret[-min_len:]

    if np.std(tk_ret) < 1e-10 or np.std(se_ret) < 1e-10:
        return None, "MIXED"

    corr = float(np.corrcoef(tk_ret, se_ret)[0, 1])
    if np.isnan(corr):
        return None, "MIXED"

    corr = round(corr, 3)
    if corr < 0.3:
        return corr, "IDIOSYNCRATIC"
    elif corr < 0.6:
        return corr, "MIXED"
    else:
        return corr, "SECTOR_DEPENDENT"


# ────────────────────────────────────────────────────────────────────────────
# Signal 5: conviction_trend (5-day lookback of conviction scores)
# ────────────────────────────────────────────────────────────────────────────

def reconstruct_conviction_trend(bars: pd.DataFrame,
                                 date_t: pd.Timestamp,
                                 all_dates: list[pd.Timestamp]) -> str:
    t_idx = None
    for i, d in enumerate(all_dates):
        if d == date_t:
            t_idx = i
            break
    if t_idx is None or t_idx < 4:
        return "CHOPPY"

    scores = []
    for offset in range(-4, 1):
        d = all_dates[t_idx + offset]
        bo = reconstruct_breakout_conviction(bars, d)
        scores.append(bo.score if bo.score is not None else 0)

    if scores[4] > scores[3] > scores[2]:
        return "BUILDING"
    elif scores[4] < scores[3] < scores[2]:
        return "DEGRADING"
    elif max(scores) - min(scores) < 10:
        return "STABLE"
    else:
        return "CHOPPY"


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
    sector_context: str
    sector_corr: float | None
    conviction_trend: str
    forward: ForwardResult | None = None


# ────────────────────────────────────────────────────────────────────────────
# Bucket stats (per spec v3.1)
# ────────────────────────────────────────────────────────────────────────────

def _bucket_stats(events: list[TriggerEvent],
                  baseline_tp1_rate: float = 0.0) -> dict:
    n = len(events)
    if n == 0:
        return {
            "n": 0, "tp1_win_rate": 0.0, "avg_days_to_tp1": 0.0,
            "median_days_to_tp1": 0.0, "sl_hit_rate": 0.0,
            "ambiguous_rate": 0.0, "none_in_10d_rate": 0.0,
            "avg_drawdown_before_tp1_pct": 0.0, "tp1_then_tp2_rate": 0.0,
            "avg_return_T5_pct": 0.0, "avg_return_T10_pct": 0.0,
            "edge_vs_baseline_tp1_win": 0.0,
        }

    tp1_wins = [e for e in events if e.forward and e.forward.first_event == "TP1"]
    sl_hits = [e for e in events if e.forward and e.forward.first_event == "SL"]
    ambiguous = [e for e in events if e.forward and e.forward.first_event == "AMBIGUOUS"]
    nones = [e for e in events if e.forward and e.forward.first_event == "NONE"]

    tp1_win_rate = len(tp1_wins) / n

    days_tp1 = [e.forward.tp1_day for e in tp1_wins if e.forward and e.forward.tp1_day]
    avg_d = float(np.mean(days_tp1)) if days_tp1 else 0.0
    med_d = float(median(days_tp1)) if days_tp1 else 0.0

    drawdowns = [e.forward.max_drawdown_before_tp1_pct for e in events if e.forward]
    avg_dd = float(np.mean(drawdowns)) if drawdowns else 0.0

    tp1_then_tp2 = sum(1 for e in tp1_wins if e.forward and e.forward.tp2_hit)
    tp1_tp2_rate = tp1_then_tp2 / len(tp1_wins) if tp1_wins else 0.0

    t5 = [e.forward.forward_returns.get("T+5", 0) for e in events
          if e.forward and "T+5" in e.forward.forward_returns]
    t10 = [e.forward.forward_returns.get("T+10", 0) for e in events
           if e.forward and "T+10" in e.forward.forward_returns]

    return {
        "n": n,
        "tp1_win_rate": round(tp1_win_rate, 4),
        "avg_days_to_tp1": round(avg_d, 1),
        "median_days_to_tp1": round(med_d, 1),
        "sl_hit_rate": round(len(sl_hits) / n, 4),
        "ambiguous_rate": round(len(ambiguous) / n, 4),
        "none_in_10d_rate": round(len(nones) / n, 4),
        "avg_drawdown_before_tp1_pct": round(avg_dd, 3),
        "tp1_then_tp2_rate": round(tp1_tp2_rate, 4),
        "avg_return_T5_pct": round(float(np.mean(t5)), 3) if t5 else 0.0,
        "avg_return_T10_pct": round(float(np.mean(t10)), 3) if t10 else 0.0,
        "edge_vs_baseline_tp1_win": round(tp1_win_rate - baseline_tp1_rate, 4),
    }


def _time_profile(events: list[TriggerEvent]) -> dict:
    """Forward return curve at each horizon."""
    profile = {}
    for h in RETURN_HORIZONS:
        key = f"T+{h}"
        rets = [e.forward.forward_returns.get(key) for e in events
                if e.forward and key in e.forward.forward_returns]
        rets = [r for r in rets if r is not None]
        if rets:
            profile[key] = {
                "avg_return_pct": round(float(np.mean(rets)), 3),
                "pct_profitable": round(sum(1 for r in rets if r > 0) / len(rets), 4),
            }
        else:
            profile[key] = {"avg_return_pct": 0, "pct_profitable": 0}
    return profile


# ────────────────────────────────────────────────────────────────────────────
# Main runner
# ────────────────────────────────────────────────────────────────────────────

def run_backtest(tickers: list[str] | None = None,
                 dry_run: bool = False) -> dict:
    if tickers is None:
        tickers = load_universe()
    print(f"[mathlab-v3] Universe: {len(tickers)} tickers")
    print(f"[mathlab-v3] Date range: {BT_START} → {BT_END}")
    print(f"[mathlab-v3] Bracket: ATR14 × 2.0, TP1 = 1.5R, TP2 = 2.0R")

    # Phase 1: pull + cache all bars
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

    # Sector ETFs
    print("\n── Phase 1b: Pulling sector ETFs ──")
    sector_etf_bars: dict[str, pd.DataFrame] = {}
    for etf in SECTOR_ETFS:
        print(f"  [{etf}]...", end=" ", flush=True)
        df = pull_daily_bars(etf)
        if df.empty:
            print("EMPTY")
        else:
            sector_etf_bars[etf] = df
            print(f"{len(df)} bars")

    sector_map = load_sector_map()

    # Phase 1c: data coverage summary
    bt_start_ts = pd.Timestamp(BT_START)
    bt_end_ts = pd.Timestamp(BT_END)
    bar_counts = []
    for tk, bars in all_bars.items():
        n_bt = int(((bars["date"] >= bt_start_ts) & (bars["date"] <= bt_end_ts)).sum())
        bar_counts.append((tk, len(bars), n_bt))
    bar_counts.sort(key=lambda x: x[2])
    total_bt_dates = sum(c[2] for c in bar_counts)
    print(f"\n── Data coverage ──")
    print(f"  Total bars in BT window: {total_bt_dates:,} across {len(bar_counts)} tickers")
    print(f"  Expected: ~{len(bar_counts) * 350:,} (182 × ~350 trading days)")
    if bar_counts:
        p10 = bar_counts[len(bar_counts) // 10]
        p50 = bar_counts[len(bar_counts) // 2]
        print(f"  BT-window dates per ticker: min={bar_counts[0][2]} "
              f"p10={p10[2]} median={p50[2]} max={bar_counts[-1][2]}")
        short = [c for c in bar_counts if c[2] < 200]
        if short:
            print(f"  ⚠ {len(short)} tickers with < 200 BT dates (short coverage):")
            for tk, total, bt in short[:10]:
                print(f"    {tk}: {bt} bt-dates ({total} total bars)")
            if len(short) > 10:
                print(f"    ... and {len(short) - 10} more")

    # Phase 2: reconstruct signals + record triggers
    print(f"\n── Phase 2: Signal reconstruction ({len(all_bars)} tickers) ──")
    triggers: list[TriggerEvent] = []
    baseline_events: list[TriggerEvent] = []
    ticker_count = 0
    total_dates_seen = 0
    total_bracket_ok = 0
    total_bracket_fail = 0

    for tk, bars in all_bars.items():
        ticker_count += 1
        dates = _trading_dates(bars)
        if not dates:
            continue
        total_dates_seen += len(dates)
        if ticker_count % 20 == 0 or ticker_count <= 3:
            print(f"  [{ticker_count}/{len(all_bars)}] {tk}: {len(dates)} dates")

        sector_etf = sector_map.get(tk)
        se_bars = sector_etf_bars.get(sector_etf) if sector_etf else None

        for dt in dates:
            bracket = bracket_from_bars(bars, dt)
            if bracket is None:
                total_bracket_fail += 1
                continue
            total_bracket_ok += 1

            entry, sl, tp1, tp2, risk, atr14 = bracket
            fwd = scan_forward(bars, dt, entry, sl, tp1, tp2)

            state = reconstruct_setup_state(bars, dt)
            rs_val, rs_lead = reconstruct_rs_leadership_v2(bars, spy_bars, dt)
            bo = reconstruct_breakout_conviction(bars, dt)
            sc_corr, sc_ctx = reconstruct_sector_context(bars, se_bars, dt)
            ct = reconstruct_conviction_trend(bars, dt, dates)

            ev = TriggerEvent(
                ticker=tk, date=str(dt.date()),
                setup_state=state,
                rs_leadership=rs_lead, rs_value=rs_val,
                breakout_grade=bo.grade,
                breakout_pattern=bo.pattern,
                breakout_score=bo.score,
                sector_context=sc_ctx,
                sector_corr=sc_corr,
                conviction_trend=ct,
                forward=fwd,
            )
            triggers.append(ev)

            # Baseline: every (ticker, date) pair
            bl_ev = TriggerEvent(
                ticker=tk, date=str(dt.date()),
                setup_state="BASELINE", rs_leadership="BASELINE",
                rs_value=None, breakout_grade=None,
                breakout_pattern=None, breakout_score=None,
                sector_context="BASELINE", sector_corr=None,
                conviction_trend="BASELINE",
                forward=fwd,
            )
            baseline_events.append(bl_ev)

        if dry_run and ticker_count >= 4:
            break

    print(f"\n── Phase 2 summary ──")
    print(f"  Total trading dates scanned: {total_dates_seen:,}")
    print(f"  Bracket OK: {total_bracket_ok:,} | Bracket rejected: {total_bracket_fail:,}")
    if total_dates_seen > 0:
        print(f"  Bracket pass rate: {total_bracket_ok / total_dates_seen * 100:.1f}%")
    print(f"\n── Phase 3: Aggregation ({len(triggers)} signal events, "
          f"{len(baseline_events)} baseline events) ──")

    result = _build_result(triggers, baseline_events, tickers, failed)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "mathlab_backtest_v3.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n✓ Results written to {out_path}")

    _print_summary(result)
    return result


def _build_result(triggers: list[TriggerEvent],
                  baseline: list[TriggerEvent],
                  universe: list[str],
                  failed: list[str]) -> dict:
    from datetime import date as _date

    # Baseline stats first (needed for edge computation)
    bl_stats = _bucket_stats(baseline)
    bl_tp1 = bl_stats["tp1_win_rate"]

    result: dict = {
        "run_date": _date.today().isoformat(),
        "universe_size": len(universe),
        "date_range": {"from": BT_START, "to": BT_END},
        "bracket_method": "ATR14 × 2.0 DSL, TP1 = 1.5R, TP2 = 2.0R",
        "max_forward_days": FORWARD_SESSIONS,
        "total_signal_events": len(triggers),
        "total_baseline_events": len(baseline),
        "data_unavailable": failed,
        "baseline": bl_stats,
    }

    # ── setup_state ──
    ss_buckets: dict[str, list[TriggerEvent]] = {
        "BREAKOUT-READY": [], "CONTINUATION-READY": [],
        "BASING": [], "EXTENDED": [],
    }
    for ev in triggers:
        if ev.setup_state in ss_buckets:
            ss_buckets[ev.setup_state].append(ev)
    result["setup_state"] = {k: _bucket_stats(v, bl_tp1) for k, v in ss_buckets.items()}

    # ── rs_leadership_v2 ──
    rs_buckets: dict[str, list[TriggerEvent]] = {
        "LEADER": [], "IN-LINE": [], "LAGGARD": [],
    }
    for ev in triggers:
        if ev.rs_leadership in rs_buckets:
            rs_buckets[ev.rs_leadership].append(ev)
    result["rs_leadership_v2"] = {k: _bucket_stats(v, bl_tp1) for k, v in rs_buckets.items()}

    # ── breakout_conviction_v2 (expansion bars only, D merged into C) ──
    bc_buckets: dict[str, list[TriggerEvent]] = {"A": [], "B": [], "C": []}
    for ev in triggers:
        if ev.breakout_grade and ev.breakout_grade in bc_buckets:
            bc_buckets[ev.breakout_grade].append(ev)
    result["breakout_conviction_v2"] = {k: _bucket_stats(v, bl_tp1) for k, v in bc_buckets.items()}

    # ── sector_context ──
    sc_buckets: dict[str, list[TriggerEvent]] = {
        "IDIOSYNCRATIC": [], "MIXED": [], "SECTOR_DEPENDENT": [],
    }
    for ev in triggers:
        if ev.sector_context in sc_buckets:
            sc_buckets[ev.sector_context].append(ev)
    result["sector_context"] = {k: _bucket_stats(v, bl_tp1) for k, v in sc_buckets.items()}

    # ── conviction_trend ──
    ct_buckets: dict[str, list[TriggerEvent]] = {
        "BUILDING": [], "STABLE": [], "CHOPPY": [], "DEGRADING": [],
    }
    for ev in triggers:
        if ev.conviction_trend in ct_buckets:
            ct_buckets[ev.conviction_trend].append(ev)
    result["conviction_trend"] = {k: _bucket_stats(v, bl_tp1) for k, v in ct_buckets.items()}

    # ── combined_signal (cross all 5 dimensions, n >= 30 only) ──
    combined: dict[str, list[TriggerEvent]] = {}
    for ev in triggers:
        parts = [
            ev.rs_leadership if ev.rs_leadership not in ("INSUFFICIENT", "NO_DOWN_DAYS") else "UNK",
            ev.setup_state,
            ev.breakout_grade or "NONE",
            ev.sector_context,
            ev.conviction_trend,
        ]
        key = "_".join(parts)
        combined.setdefault(key, []).append(ev)

    combined_out = {}
    for key, evs in sorted(combined.items(), key=lambda x: -len(x[1])):
        if len(evs) >= 30:
            combined_out[key] = _bucket_stats(evs, bl_tp1)
    result["combined_signal"] = {
        "description": "Crosses all five dimensions. Only combinations with n >= 30 shown.",
        "buckets": combined_out,
    }

    # ── time_profile ──
    result["time_profile"] = {
        "description": "Forward return curve per signal group",
        "BREAKOUT-READY": _time_profile(ss_buckets["BREAKOUT-READY"]),
        "CONTINUATION-READY": _time_profile(ss_buckets["CONTINUATION-READY"]),
        "BASING": _time_profile(ss_buckets["BASING"]),
        "EXTENDED": _time_profile(ss_buckets["EXTENDED"]),
        "BASELINE": _time_profile(baseline),
    }

    # ── pass/fail ──
    pf: dict = {}

    # setup_state: BREAKOUT-READY > baseline by 5pp + shallower drawdown
    br = result["setup_state"].get("BREAKOUT-READY", {})
    pf["setup_state"] = {
        "criterion": "BREAKOUT-READY tp1_win_rate > baseline by >= 5pp AND shallower drawdown",
        "verdict": "PASS" if (
            br.get("tp1_win_rate", 0) - bl_tp1 >= 0.05
            and br.get("avg_drawdown_before_tp1_pct", -999) > bl_stats.get("avg_drawdown_before_tp1_pct", 0)
            and br.get("n", 0) >= 30
        ) else "FAIL",
    }

    # rs_leadership_v2: LEADER > IN-LINE by 5pp
    ld = result["rs_leadership_v2"].get("LEADER", {})
    il = result["rs_leadership_v2"].get("IN-LINE", {})
    pf["rs_leadership_v2"] = {
        "criterion": "LEADER tp1_win_rate > IN-LINE by >= 5pp",
        "verdict": "PASS" if (
            ld.get("tp1_win_rate", 0) - il.get("tp1_win_rate", 0) >= 0.05
            and ld.get("n", 0) >= 30
        ) else "FAIL",
    }

    # breakout_conviction_v2: A > B > C monotonic
    grades_data = result["breakout_conviction_v2"]
    g_rates = [grades_data.get(g, {}).get("tp1_win_rate", 0) for g in ("A", "B", "C")]
    g_ns = [grades_data.get(g, {}).get("n", 0) for g in ("A", "B", "C")]
    monotonic = all(g_rates[i] >= g_rates[i + 1]
                    for i in range(len(g_rates) - 1)
                    if g_ns[i] > 0 and g_ns[i + 1] > 0)
    pf["breakout_conviction_v2"] = {
        "criterion": "Grade A > B > C tp1_win_rate (monotonic)",
        "verdict": "PASS" if (monotonic and all(n >= 30 for n in g_ns if n > 0)) else "FAIL",
    }

    # sector_context: IDIOSYNCRATIC > SECTOR_DEPENDENT by 3pp OR shallower drawdown
    idio = result["sector_context"].get("IDIOSYNCRATIC", {})
    sect = result["sector_context"].get("SECTOR_DEPENDENT", {})
    pf["sector_context"] = {
        "criterion": "IDIOSYNCRATIC tp1_win_rate > SECTOR_DEPENDENT by >= 3pp OR shallower drawdown",
        "verdict": "PASS" if (
            idio.get("n", 0) >= 30
            and sect.get("n", 0) >= 30
            and (
                idio.get("tp1_win_rate", 0) - sect.get("tp1_win_rate", 0) >= 0.03
                or idio.get("avg_drawdown_before_tp1_pct", -999) > sect.get("avg_drawdown_before_tp1_pct", 0)
            )
        ) else "FAIL",
    }

    # conviction_trend: BUILDING > CHOPPY by 5pp
    bld = result["conviction_trend"].get("BUILDING", {})
    chp = result["conviction_trend"].get("CHOPPY", {})
    pf["conviction_trend"] = {
        "criterion": "BUILDING tp1_win_rate > CHOPPY by >= 5pp",
        "verdict": "PASS" if (
            bld.get("tp1_win_rate", 0) - chp.get("tp1_win_rate", 0) >= 0.05
            and bld.get("n", 0) >= 30
        ) else "FAIL",
    }

    # combined_best: best bucket > baseline by 8pp
    best_bucket = None
    best_tp1 = 0.0
    for bk, bs in combined_out.items():
        if bs["tp1_win_rate"] > best_tp1:
            best_tp1 = bs["tp1_win_rate"]
            best_bucket = bk
    pf["combined_best"] = {
        "criterion": "Best combined bucket tp1_win_rate > baseline by >= 8pp",
        "verdict": "PASS" if (best_tp1 - bl_tp1 >= 0.08 and best_bucket is not None) else "FAIL",
        "best_bucket": best_bucket,
        "best_tp1_win_rate": round(best_tp1, 4),
        "baseline_tp1_win_rate": round(bl_tp1, 4),
    }

    result["pass_fail"] = pf

    # ── sample warnings ──
    warnings = []
    for dim_name, dim_data in [
        ("setup_state", result["setup_state"]),
        ("rs_leadership_v2", result["rs_leadership_v2"]),
        ("breakout_conviction_v2", result["breakout_conviction_v2"]),
        ("sector_context", result["sector_context"]),
        ("conviction_trend", result["conviction_trend"]),
    ]:
        for bucket, stats in dim_data.items():
            n = stats.get("n", 0)
            if 0 < n < 30:
                warnings.append(f"{dim_name}/{bucket}: only {n} events (< 30 min for significance)")
    result["sample_warnings"] = warnings

    return result


# ────────────────────────────────────────────────────────────────────────────
# Summary printer
# ────────────────────────────────────────────────────────────────────────────

def _print_summary(result: dict) -> None:
    bl = result.get("baseline", {})
    bl_tp1 = bl.get("tp1_win_rate", 0) * 100

    print("\n" + "=" * 78)
    print("  AQE MATH LAB — BACKTEST v3.1 RESULTS")
    print("=" * 78)
    print(f"  Universe: {result['universe_size']} tickers")
    print(f"  Date range: {result['date_range']['from']} → {result['date_range']['to']}")
    print(f"  Signal events: {result['total_signal_events']:,}")
    print(f"  Baseline events: {result['total_baseline_events']:,}")
    print(f"  Baseline TP1 win: {bl_tp1:.1f}% | "
          f"SL: {bl.get('sl_hit_rate',0)*100:.1f}% | "
          f"DD: {bl.get('avg_drawdown_before_tp1_pct',0):+.2f}%")

    for dim_name, dim_key in [
        ("SETUP STATE", "setup_state"),
        ("RS LEADERSHIP v2", "rs_leadership_v2"),
        ("BREAKOUT CONVICTION v2", "breakout_conviction_v2"),
        ("SECTOR CONTEXT", "sector_context"),
        ("CONVICTION TREND", "conviction_trend"),
    ]:
        print(f"\n── {dim_name} ──")
        dim = result.get(dim_key, {})
        for bucket, stats in dim.items():
            edge = stats.get("edge_vs_baseline_tp1_win", 0) * 100
            sign = "+" if edge >= 0 else ""
            print(f"  {bucket:25s}  n={stats.get('n',0):6d}  "
                  f"TP1={stats.get('tp1_win_rate',0)*100:5.1f}%  "
                  f"SL={stats.get('sl_hit_rate',0)*100:5.1f}%  "
                  f"DD={stats.get('avg_drawdown_before_tp1_pct',0):+5.2f}%  "
                  f"d2TP1={stats.get('avg_days_to_tp1',0):4.1f}  "
                  f"Edge={sign}{edge:.1f}pp")

    # Combined best
    cs = result.get("combined_signal", {})
    buckets = cs.get("buckets", {})
    if buckets:
        print(f"\n── COMBINED SIGNAL (top 5 by TP1 win) ──")
        sorted_b = sorted(buckets.items(), key=lambda x: -x[1].get("tp1_win_rate", 0))
        for bk, bs in sorted_b[:5]:
            edge = bs.get("edge_vs_baseline_tp1_win", 0) * 100
            print(f"  {bk:45s}  n={bs['n']:5d}  "
                  f"TP1={bs['tp1_win_rate']*100:5.1f}%  Edge=+{edge:.1f}pp")

    # Time profile
    tp = result.get("time_profile", {})
    if tp:
        print(f"\n── TIME PROFILE (avg return %) ──")
        header = f"  {'Signal':25s}"
        for h in RETURN_HORIZONS:
            header += f"  T+{h:>2d}"
        print(header)
        for sig in ("BREAKOUT-READY", "CONTINUATION-READY", "BASING", "EXTENDED", "BASELINE"):
            sp = tp.get(sig, {})
            row = f"  {sig:25s}"
            for h in RETURN_HORIZONS:
                val = sp.get(f"T+{h}", {}).get("avg_return_pct", 0)
                row += f"  {val:+5.2f}"
            print(row)

    # Pass/fail
    print("\n── PASS / FAIL ──")
    pf = result.get("pass_fail", {})
    for key in ("setup_state", "rs_leadership_v2", "breakout_conviction_v2",
                "sector_context", "conviction_trend", "combined_best"):
        entry = pf.get(key, {})
        v = entry.get("verdict", "?")
        marker = "✓" if v == "PASS" else "✗"
        crit = entry.get("criterion", "")
        extra = ""
        if key == "combined_best" and entry.get("best_bucket"):
            extra = f" [{entry['best_bucket']}]"
        print(f"  {marker} {key}: {v}{extra}")
        print(f"    ({crit})")

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
    parser = argparse.ArgumentParser(description="AQE Math Lab Backtest v3.1")
    parser.add_argument("--dry-run", action="store_true",
                        help="First 4 tickers only")
    parser.add_argument("--tickers", nargs="+",
                        help="Specific tickers to test")
    parser.add_argument("--refresh", action="store_true",
                        help="Force re-pull all bars from FMP (ignore cache)")
    args = parser.parse_args()

    if args.refresh:
        import shutil
        if CACHE_DIR.exists():
            n_cached = len(list(CACHE_DIR.glob("*.parquet")))
            print(f"[mathlab-v3] --refresh: clearing {n_cached} cached bar files")
            shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    tickers = args.tickers
    if tickers:
        tickers = [t.upper() for t in tickers]
    run_backtest(tickers=tickers, dry_run=args.dry_run)
