"""AQE Subcomponent Correlation Backtest — find the real recipe.

Decomposes ALL 7 AQE engines into their raw subcomponents (47 level features +
14 rate-of-change features + 4 computed composites = 65 total), then
mathematically measures which ones actually predict forward outcomes.

The goal: discover which subcomponent mix drives upward momentum, independent
of AQE's current weighting. This informs the enrichment layer's PTRS recipe.

Usage:
    python -m src.mathlab.backtest_subcomponents
    python -m src.mathlab.backtest_subcomponents --dry-run
    python -m src.mathlab.backtest_subcomponents --refresh
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
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
COOLDOWN = 5

CACHE_DIR = Path("data/mathlab_cache")
OUTPUT_DIR = Path("output")

# ────────────────────────────────────────────────────────────────────────────
# Subcomponent taxonomy — every raw score in the AQE engine stack
# (name, engine, source_column, type_tag, description)
# ────────────────────────────────────────────────────────────────────────────
SUBCOMPONENT_SPEC = [
    # ── Flow engine ──
    ("fl_flow_score", "flow", "flow_score", "FLOW", "MFI + CMF + HA quality (0-17)"),
    ("fl_accum", "flow", "accum_score", "FLOW", "A/D linreg acceleration (0-7.5)"),
    ("fl_volume", "flow", "volume_score", "VOLUME", "Volume trend + spike (0-7.5)"),
    ("fl_skew", "flow", "skew_score", "VOLUME", "Up/down volume ratio 10-bar (0-3.5)"),
    ("fl_ext", "flow", "ext_score", "MOMENTUM", "Extension penalty/bonus (-8 to +5)"),
    ("fl_mfi", "flow", "mfi", "FLOW", "Money Flow Index 10-bar (0-100)"),
    ("fl_cmf", "flow", "cmf", "FLOW", "Chaikin Money Flow 10-bar (-1 to +1)"),
    ("fl_ha_quality", "flow", "ha_quality_count", "QUALITY", "HA small-body count in 10 bars"),
    ("fl_100", "flow", "flow_100", "COMPOSITE", "Flow composite (0-100)"),

    # ── Energy engine ──
    ("en_vp_pos", "energy", "vp_position_score", "POSITION", "VP range position proxy 50d (0-17.5)"),
    ("en_pa", "energy", "price_action_score", "STRUCTURE", "Structure + tightness + pullback"),
    ("en_squeeze", "energy", "squeeze_score", "VOLATILITY", "BB/KC squeeze score (0-12.5)"),
    ("en_exhaust", "energy", "exhaustion_score", "MOMENTUM", "Trend exhaustion (0-10, penalties subtract)"),
    ("en_atr", "energy", "atr_score", "VOLATILITY", "ATR expansion goldilocks zone (0-7)"),
    ("en_pos50", "energy", "en_pos50", "POSITION", "Raw 50d range position % (0-100)"),
    ("en_trend_bars", "energy", "en_trend_bars", "MOMENTUM", "Consecutive bars above EMA20"),
    ("en_100", "energy", "energy_100", "COMPOSITE", "Energy composite (0-100)"),

    # ── Structure engine ──
    ("st_rs_spy", "structure", "rs_spy_score", "RELATIVE_STRENGTH", "RS vs SPY 60d tier (0-15)"),
    ("st_rs_accel", "structure", "rs_accel_score", "RELATIVE_STRENGTH", "RS acceleration 20d vs 60d (0-15)"),
    ("st_base", "structure", "base_score", "QUALITY", "Base formation quality + duration (0-15)"),
    ("st_ms_pos", "structure", "ms_pos_score", "POSITION", "Market structure position 50d (0-15)"),
    ("st_resist", "structure", "resist_score", "STRUCTURE", "Distance to 50d resistance (0-10)"),
    ("st_wk", "structure", "wk_score", "TREND", "Weekly trend alignment (0-15)"),
    ("st_earn", "structure", "earn_score", "EVENT", "Earnings proximity (0-10)"),
    ("st_rs_raw", "structure", "rs_vs_spy", "RELATIVE_STRENGTH", "Raw RS vs SPY % (continuous)"),
    ("st_rs_accel_raw", "structure", "rs_accel", "RELATIVE_STRENGTH", "Raw RS acceleration % (continuous)"),
    ("st_base_days", "structure", "base_days", "QUALITY", "Raw base days count"),
    ("st_p50", "structure", "ms_p50", "POSITION", "Raw 50d range position % (continuous)"),
    ("st_100", "structure", "structure_100", "COMPOSITE", "Structure composite (0-100)"),

    # ── MP engine ──
    ("mp_abs", "mp", "abs_mom_score", "MOMENTUM", "Absolute momentum z-score tier (0-30)"),
    ("mp_adx", "mp", "adx_score", "TREND", "ADX trend strength tier (0-25)"),
    ("mp_rel", "mp", "rel_mom_score", "RELATIVE_STRENGTH", "Relative momentum vs SPY tier (0-25)"),
    ("mp_trend", "mp", "trend_score", "TREND", "MA structure alignment (0-20)"),
    ("mp_roc_z", "mp", "roc_zscore", "MOMENTUM", "Raw ROC(20) z-score (continuous)"),
    ("mp_excess", "mp", "excess_return", "RELATIVE_STRENGTH", "Raw excess return vs SPY % (continuous)"),
    ("mp_adx_val", "mp", "adx_val", "TREND", "Raw ADX(14) value (continuous)"),
    ("mp_100", "mp", "mp_score", "COMPOSITE", "MP composite (0-100)"),

    # ── Elder engine ──
    ("el_score", "elder", "elder_score", "MOMENTUM", "Elder Impulse total (0-10)"),

    # ── BQ engine ──
    ("bq_range", "bq", "bq_range_tight", "VOLATILITY", "Range tightness ATR5/ATR20 (0-30)"),
    ("bq_vol", "bq", "bq_vol_dry", "VOLUME", "Volume dry-up SMA5/SMA20 (0-25)"),
    ("bq_dur", "bq", "bq_base_dur", "QUALITY", "Base duration inverted-U (0-20)"),
    ("bq_ema", "bq", "bq_ema_conv", "STRUCTURE", "EMA 8/13/21 convergence (0-25)"),
    ("bq_100", "bq", "bq_100", "COMPOSITE", "BQ composite (0-100)"),

    # ── Pipeline Rank engine ──
    ("pr_ret12m", "pipeline_rank", "ret_12m_score", "MOMENTUM", "12-month return tier (0-20)"),
    ("pr_adx", "pipeline_rank", "adx_score", "TREND", "ADX trend tier (0-20)"),
    ("pr_rsi", "pipeline_rank", "rsi_score", "MOMENTUM", "RSI momentum zone (0-20)"),
    ("pr_vol", "pipeline_rank", "vol_score", "VOLUME", "Volume confirmation SMA5/SMA20 (0-20)"),
    ("pr_ma", "pipeline_rank", "ma_score", "TREND", "MA structure alignment (0-20)"),
    ("pr_fip", "pipeline_rank", "fip_quality", "QUALITY", "FIP path quality (0-100)"),
    ("pr_100", "pipeline_rank", "pipe_rank", "COMPOSITE", "Pipeline Rank composite (0-100)"),
]

SC_M_WEIGHTS = {"fl_100": 0.30, "en_100": 0.30, "st_100": 0.20, "mp_100": 0.20}
SC_P_WEIGHTS = {"fl_100": 0.10, "en_100": 0.30, "st_100": 0.20, "mp_100": 0.05, "bq_100": 0.35}

COMPOSITE_KEYS = ["fl_100", "en_100", "st_100", "mp_100", "el_score", "bq_100", "pr_100"]
ROC_WINDOWS = [3, 5]

TYPE_TAGS = sorted(set(s[3] for s in SUBCOMPONENT_SPEC))


# ────────────────────────────────────────────────────────────────────────────
# Data loading
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
    except Exception as e:
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


def _daily_to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.set_index("date").sort_index()
    weekly = d.resample("W-FRI").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"
    }).dropna(subset=["close"])
    return weekly.reset_index()


# ────────────────────────────────────────────────────────────────────────────
# Engine computation
# ────────────────────────────────────────────────────────────────────────────

def compute_all_subcomponents(
    ticker: str,
    daily: pd.DataFrame,
    spy_daily: pd.DataFrame,
) -> pd.DataFrame | None:
    """Compute all engine subcomponents for a single ticker.

    Returns a wide DataFrame indexed by date, with one column per subcomponent.
    Returns None if computation fails.
    """
    from src.engines import flow, energy, structure, mp, elder, bq, pipeline_rank

    d = daily.sort_values("date").reset_index(drop=True)
    if len(d) < 100:
        return None

    weekly = _daily_to_weekly(d)

    engine_dfs = {}
    try:
        engine_dfs["flow"] = flow.compute(d)
    except Exception as e:
        print(f"  [!] {ticker} flow: {e}")

    try:
        engine_dfs["energy"] = energy.compute(d)
    except Exception as e:
        print(f"  [!] {ticker} energy: {e}")

    try:
        engine_dfs["structure"] = structure.compute(
            d, spy_daily, weekly, ticker=ticker)
    except Exception as e:
        print(f"  [!] {ticker} structure: {e}")

    try:
        engine_dfs["mp"] = mp.compute(d, spy_daily)
    except Exception as e:
        print(f"  [!] {ticker} mp: {e}")

    try:
        engine_dfs["elder"] = elder.compute(d)
    except Exception as e:
        print(f"  [!] {ticker} elder: {e}")

    try:
        engine_dfs["bq"] = bq.compute(d)
    except Exception as e:
        print(f"  [!] {ticker} bq: {e}")

    try:
        engine_dfs["pipeline_rank"] = pipeline_rank.compute(d)
    except Exception as e:
        print(f"  [!] {ticker} pipeline_rank: {e}")

    if not engine_dfs:
        return None

    result = d[["date"]].copy()

    for name, engine_key, src_col, _type_tag, _desc in SUBCOMPONENT_SPEC:
        edf = engine_dfs.get(engine_key)
        if edf is not None and src_col in edf.columns:
            vals = edf[src_col].values
            if len(vals) == len(result):
                result[name] = vals
            else:
                result[name] = np.nan
        else:
            result[name] = np.nan

    # SC_MOMENTUM and SC_POSITION
    result["sc_mom"] = sum(
        result[k] * w for k, w in SC_M_WEIGHTS.items() if k in result.columns
    )
    result["sc_pos"] = sum(
        result[k] * w for k, w in SC_P_WEIGHTS.items() if k in result.columns
    )

    # ROC features: 3d and 5d change for each composite
    roc_cols = COMPOSITE_KEYS + ["sc_mom", "sc_pos"]
    for col in roc_cols:
        if col in result.columns:
            for w in ROC_WINDOWS:
                result[f"{col}_d{w}"] = result[col] - result[col].shift(w)

    return result


# ────────────────────────────────────────────────────────────────────────────
# All feature names (for iteration)
# ────────────────────────────────────────────────────────────────────────────

def _all_feature_names() -> list[str]:
    names = [s[0] for s in SUBCOMPONENT_SPEC]
    names += ["sc_mom", "sc_pos"]
    roc_cols = COMPOSITE_KEYS + ["sc_mom", "sc_pos"]
    for col in roc_cols:
        for w in ROC_WINDOWS:
            names.append(f"{col}_d{w}")
    return names


def _feature_meta(name: str) -> dict:
    """Return type tag and description for a feature."""
    for n, _eng, _col, tag, desc in SUBCOMPONENT_SPEC:
        if n == name:
            return {"type": tag, "engine": _eng, "description": desc}
    if name == "sc_mom":
        return {"type": "COMPOSITE", "engine": "scoring",
                "description": "SC_MOMENTUM = Fl30+En30+St20+Mp20"}
    if name == "sc_pos":
        return {"type": "COMPOSITE", "engine": "scoring",
                "description": "SC_POSITION = Fl10+En30+St20+Mp5+Bq35"}
    if name.endswith("_d3") or name.endswith("_d5"):
        base = name.rsplit("_", 1)[0]
        w = name.rsplit("_d", 1)[1]
        base_meta = _feature_meta(base)
        return {"type": "RATE_OF_CHANGE", "engine": base_meta.get("engine", ""),
                "description": f"{w}-day change in {base}"}
    return {"type": "UNKNOWN", "engine": "", "description": name}


# ────────────────────────────────────────────────────────────────────────────
# Bracket + forward scan (reused from existing backtest)
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
    sl_hit: bool = False
    first_event: str = "NONE"
    max_dd_pct: float = 0.0
    returns: dict = field(default_factory=dict)


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
        for h in (1, 2, 3, 5, 7, 10):
            if n == h:
                r.returns[f"T+{h}"] = round(ret, 3)
        if not r.tp1_hit:
            worst_low = min(worst_low, bar_lo)
        if not r.sl_hit and bar_lo <= sl:
            r.sl_hit = True
            if r.first_event == "NONE":
                r.first_event = "SL"
        if not r.tp1_hit and bar_hi >= tp1:
            r.tp1_hit = True
            r.tp1_day = n
            if r.first_event == "NONE":
                r.first_event = "TP1"
    r.max_dd_pct = round((worst_low - entry) / entry * 100, 3)
    return r


# ────────────────────────────────────────────────────────────────────────────
# Correlation + quintile analysis
# ────────────────────────────────────────────────────────────────────────────

def _spearman(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Spearman rank correlation + p-value, handling NaN."""
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 30:
        return 0.0, 1.0
    from scipy.stats import spearmanr
    rho, p = spearmanr(x[mask], y[mask])
    return round(float(rho), 4), round(float(p), 6)


def _quintile_analysis(values: np.ndarray, tp1_hits: np.ndarray,
                       t5_returns: np.ndarray, t10_returns: np.ndarray,
                       dd: np.ndarray) -> dict:
    """Split values into 5 equal-count groups, measure outcomes per group."""
    mask = ~np.isnan(values)
    if mask.sum() < 100:
        return {}

    v = values[mask]
    tp1 = tp1_hits[mask]
    t5 = t5_returns[mask]
    t10 = t10_returns[mask]
    d = dd[mask]

    ranks = pd.Series(v).rank(method="first")
    n = len(ranks)
    quintile_size = n // 5
    labels = np.zeros(n, dtype=int)
    for i in range(5):
        lo_rank = i * quintile_size + 1
        hi_rank = (i + 1) * quintile_size if i < 4 else n + 1
        labels[(ranks >= lo_rank) & (ranks < hi_rank)] = i + 1
    labels[labels == 0] = 5

    result = {}
    for q in range(1, 6):
        qm = labels == q
        qn = int(qm.sum())
        if qn == 0:
            continue
        result[f"Q{q}"] = {
            "n": qn,
            "val_lo": round(float(np.nanmin(v[qm])), 3),
            "val_hi": round(float(np.nanmax(v[qm])), 3),
            "val_median": round(float(np.nanmedian(v[qm])), 3),
            "tp1_rate": round(float(tp1[qm].mean()), 4),
            "avg_t5": round(float(np.nanmean(t5[qm])), 3),
            "avg_t10": round(float(np.nanmean(t10[qm])), 3),
            "avg_dd": round(float(np.nanmean(d[qm])), 3),
        }

    if "Q5" in result and "Q1" in result:
        result["q5_q1_tp1_spread"] = round(
            result["Q5"]["tp1_rate"] - result["Q1"]["tp1_rate"], 4)
        rates = [result[f"Q{i}"]["tp1_rate"] for i in range(1, 6) if f"Q{i}" in result]
        result["monotonic_up"] = all(rates[i] <= rates[i + 1] for i in range(len(rates) - 1))
        result["monotonic_down"] = all(rates[i] >= rates[i + 1] for i in range(len(rates) - 1))
    else:
        result["q5_q1_tp1_spread"] = 0.0
        result["monotonic_up"] = False
        result["monotonic_down"] = False

    return result


# ────────────────────────────────────────────────────────────────────────────
# Type-group analysis
# ────────────────────────────────────────────────────────────────────────────

def _type_group_summary(feature_results: dict) -> dict:
    """Aggregate results by type tag — which CATEGORY of features predicts best?"""
    groups: dict[str, list[dict]] = {}
    for name, data in feature_results.items():
        tag = data.get("type", "UNKNOWN")
        groups.setdefault(tag, []).append(data)

    summary = {}
    for tag, features in sorted(groups.items()):
        spreads = [f["q5_q1_tp1_spread"] for f in features
                   if f.get("q5_q1_tp1_spread") is not None]
        corrs_tp1 = [abs(f["correlation"]["tp1_hit"]["rho"])
                     for f in features if f.get("correlation")]
        corrs_t10 = [abs(f["correlation"]["t10_return"]["rho"])
                     for f in features if f.get("correlation")]
        summary[tag] = {
            "n_features": len(features),
            "feature_names": [f["name"] for f in features],
            "avg_abs_spread": round(float(np.mean([abs(s) for s in spreads])), 4) if spreads else 0,
            "max_spread": round(float(max(spreads, key=abs)), 4) if spreads else 0,
            "best_feature": max(features, key=lambda f: abs(f.get("q5_q1_tp1_spread", 0)))["name"] if features else "",
            "avg_abs_corr_tp1": round(float(np.mean(corrs_tp1)), 4) if corrs_tp1 else 0,
            "avg_abs_corr_t10": round(float(np.mean(corrs_t10)), 4) if corrs_t10 else 0,
        }
    return summary


# ────────────────────────────────────────────────────────────────────────────
# Main runner
# ────────────────────────────────────────────────────────────────────────────

def run_backtest(tickers: list[str] | None = None,
                 dry_run: bool = False) -> dict:
    if tickers is None:
        tickers = load_universe()
    if dry_run:
        tickers = tickers[:8]

    print(f"[subcomp] Universe: {len(tickers)} tickers")
    print(f"[subcomp] BT window: {BT_START} -> {BT_END}")

    # ── Phase 1: Pull bars ──
    print("\n-- Phase 1: Pulling daily bars --")
    all_bars: dict[str, pd.DataFrame] = {}
    failed: list[str] = []

    # SPY first
    print("  SPY...", end=" ", flush=True)
    spy_bars = pull_daily_bars("SPY")
    if spy_bars.empty:
        print("EMPTY — Structure/MP will degrade")
        spy_bars = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    else:
        print(f"{len(spy_bars)} bars")

    for i, tk in enumerate(tickers, 1):
        print(f"  [{i}/{len(tickers)}] {tk}...", end=" ", flush=True)
        df = pull_daily_bars(tk)
        if df.empty:
            print("EMPTY")
            failed.append(tk)
        else:
            all_bars[tk] = df
            print(f"{len(df)} bars")

    # ── Phase 2: Compute all engine subcomponents ──
    print(f"\n-- Phase 2: Computing engines ({len(all_bars)} tickers) --")
    all_wide: dict[str, pd.DataFrame] = {}

    for i, (tk, bars) in enumerate(all_bars.items(), 1):
        if i <= 3 or i % 30 == 0 or i == len(all_bars):
            print(f"  [{i}/{len(all_bars)}] {tk}...", end=" ", flush=True)

        wide = compute_all_subcomponents(tk, bars, spy_bars)
        if wide is not None:
            all_wide[tk] = wide
            if i <= 3 or i % 30 == 0 or i == len(all_bars):
                valid = wide.drop(columns=["date"]).notna().sum(axis=0)
                n_valid = int((valid > 0).sum())
                print(f"{n_valid} features valid")
        else:
            if i <= 3 or i % 30 == 0 or i == len(all_bars):
                print("SKIP (too few bars)")

    print(f"  Engines computed: {len(all_wide)}/{len(all_bars)} tickers")

    # ── Phase 3: Build events ──
    print(f"\n-- Phase 3: Building events --")
    bt_start = pd.Timestamp(BT_START)
    bt_end = pd.Timestamp(BT_END)

    feature_names = _all_feature_names()
    rows: list[dict] = []
    total_dates = 0

    for tk, wide in all_wide.items():
        bars = all_bars[tk]
        wide["date"] = pd.to_datetime(wide["date"]).dt.normalize()
        bt_mask = (wide["date"] >= bt_start) & (wide["date"] <= bt_end)
        bt_rows = wide[bt_mask]

        last_trigger = None
        for _, row in bt_rows.iterrows():
            dt = row["date"]
            total_dates += 1

            # Cooldown
            if last_trigger is not None and (dt - last_trigger).days < COOLDOWN:
                continue

            bracket = bracket_from_bars(bars, dt)
            if bracket is None:
                continue
            entry, sl, tp1, tp2, risk, atr14 = bracket
            fwd = scan_forward(bars, dt, entry, sl, tp1, tp2)

            ev = {
                "ticker": tk,
                "date": str(dt.date()),
                "tp1_hit": 1 if fwd.first_event == "TP1" else 0,
                "sl_hit": 1 if fwd.first_event == "SL" else 0,
                "t5_return": fwd.returns.get("T+5", np.nan),
                "t10_return": fwd.returns.get("T+10", np.nan),
                "max_dd": fwd.max_dd_pct,
            }
            for fn in feature_names:
                ev[fn] = float(row[fn]) if fn in row.index and not pd.isna(row.get(fn)) else np.nan

            rows.append(ev)
            last_trigger = dt

    print(f"  Total dates scanned: {total_dates:,}")
    print(f"  Events (with cooldown): {len(rows):,}")

    if len(rows) < 100:
        print("  [!] Too few events for analysis")
        return {"error": "insufficient_data", "n_events": len(rows)}

    # ── Phase 4: Correlation + quintile analysis ──
    print(f"\n-- Phase 4: Correlation + quintile analysis --")

    tp1_arr = np.array([r["tp1_hit"] for r in rows], dtype=float)
    t5_arr = np.array([r.get("t5_return", np.nan) for r in rows], dtype=float)
    t10_arr = np.array([r.get("t10_return", np.nan) for r in rows], dtype=float)
    dd_arr = np.array([r["max_dd"] for r in rows], dtype=float)

    baseline_tp1 = float(tp1_arr.mean())
    baseline_t5 = float(np.nanmean(t5_arr))
    baseline_t10 = float(np.nanmean(t10_arr))
    baseline_dd = float(np.nanmean(dd_arr))

    print(f"  Baseline: TP1={baseline_tp1*100:.1f}%  T+5={baseline_t5:.3f}%  "
          f"T+10={baseline_t10:.3f}%  DD={baseline_dd:.2f}%")

    feature_results: dict[str, dict] = {}
    for fn in feature_names:
        vals = np.array([r.get(fn, np.nan) for r in rows], dtype=float)
        n_valid = int(np.sum(~np.isnan(vals)))

        if n_valid < 100:
            continue

        meta = _feature_meta(fn)

        rho_tp1, p_tp1 = _spearman(vals, tp1_arr)
        rho_t5, p_t5 = _spearman(vals, t5_arr)
        rho_t10, p_t10 = _spearman(vals, t10_arr)
        rho_dd, p_dd = _spearman(vals, dd_arr)

        quint = _quintile_analysis(vals, tp1_arr, t5_arr, t10_arr, dd_arr)

        feature_results[fn] = {
            "name": fn,
            "type": meta["type"],
            "engine": meta["engine"],
            "description": meta["description"],
            "n_valid": n_valid,
            "correlation": {
                "tp1_hit": {"rho": rho_tp1, "p": p_tp1},
                "t5_return": {"rho": rho_t5, "p": p_t5},
                "t10_return": {"rho": rho_t10, "p": p_t10},
                "max_drawdown": {"rho": rho_dd, "p": p_dd},
            },
            "quintiles": quint,
            "q5_q1_tp1_spread": quint.get("q5_q1_tp1_spread", 0.0),
            "monotonic_up": quint.get("monotonic_up", False),
            "monotonic_down": quint.get("monotonic_down", False),
        }

    # ── Phase 5: Rank + summarize ──
    print(f"\n-- Phase 5: Ranking {len(feature_results)} features --")

    ranked_by_spread = sorted(
        feature_results.values(),
        key=lambda f: abs(f.get("q5_q1_tp1_spread", 0)),
        reverse=True,
    )

    ranked_by_t10_corr = sorted(
        feature_results.values(),
        key=lambda f: abs(f.get("correlation", {}).get("t10_return", {}).get("rho", 0)),
        reverse=True,
    )

    type_summary = _type_group_summary(feature_results)

    # Print top 20 by spread
    print(f"\n  {'Rank':>4s}  {'Feature':25s}  {'Type':18s}  {'Engine':10s}  "
          f"{'Q5-Q1':>7s}  {'rho_TP1':>8s}  {'rho_T10':>8s}  {'Mono':>4s}  {'n':>6s}")
    print("  " + "-" * 110)
    for i, f in enumerate(ranked_by_spread[:25], 1):
        mono = "UP" if f["monotonic_up"] else ("DN" if f["monotonic_down"] else "  ")
        rho_tp1 = f["correlation"]["tp1_hit"]["rho"]
        rho_t10 = f["correlation"]["t10_return"]["rho"]
        spread = f["q5_q1_tp1_spread"]
        print(f"  {i:>4d}  {f['name']:25s}  {f['type']:18s}  {f['engine']:10s}  "
              f"{spread*100:>+6.2f}%  {rho_tp1:>+7.4f}  {rho_t10:>+7.4f}  {mono:>4s}  "
              f"{f['n_valid']:>6,}")

    # Print type group summary
    print(f"\n  TYPE GROUP SUMMARY:")
    print(f"  {'Type':18s}  {'#Feat':>5s}  {'AvgAbsSpread':>12s}  {'MaxSpread':>10s}  "
          f"{'BestFeature':25s}  {'AvgCorrTP1':>10s}")
    print("  " + "-" * 95)
    for tag, data in sorted(type_summary.items(),
                             key=lambda x: abs(x[1]["avg_abs_spread"]),
                             reverse=True):
        print(f"  {tag:18s}  {data['n_features']:>5d}  "
              f"{data['avg_abs_spread']*100:>11.2f}%  "
              f"{data['max_spread']*100:>+9.2f}%  "
              f"{data['best_feature']:25s}  "
              f"{data['avg_abs_corr_tp1']:>9.4f}")

    # Print quintile detail for top 5
    print(f"\n  QUINTILE DETAIL (top 5 by spread):")
    for f in ranked_by_spread[:5]:
        print(f"\n  {f['name']} ({f['type']}, {f['engine']}): "
              f"Q5-Q1 = {f['q5_q1_tp1_spread']*100:+.2f}pp")
        quint = f.get("quintiles", {})
        for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
            qd = quint.get(q, {})
            if qd:
                print(f"    {q}: n={qd['n']:>5,}  "
                      f"val=[{qd['val_lo']:.1f}-{qd['val_hi']:.1f}]  "
                      f"TP1={qd['tp1_rate']*100:>5.1f}%  "
                      f"T+5={qd['avg_t5']:>+6.2f}%  "
                      f"T+10={qd['avg_t10']:>+6.2f}%  "
                      f"DD={qd['avg_dd']:>+6.2f}%")

    # ── Build result ──
    result = {
        "run_date": str(pd.Timestamp.now().date()),
        "universe_size": len(tickers),
        "bt_window": {"from": BT_START, "to": BT_END},
        "total_events": len(rows),
        "data_unavailable": failed,
        "baseline": {
            "tp1_rate": round(baseline_tp1, 4),
            "avg_t5": round(baseline_t5, 3),
            "avg_t10": round(baseline_t10, 3),
            "avg_dd": round(baseline_dd, 3),
        },
        "n_features_tested": len(feature_results),
        "features": {k: v for k, v in feature_results.items()},
        "ranked_by_tp1_spread": [
            {"name": f["name"], "type": f["type"], "engine": f["engine"],
             "q5_q1_spread": f["q5_q1_tp1_spread"],
             "rho_tp1": f["correlation"]["tp1_hit"]["rho"],
             "rho_t10": f["correlation"]["t10_return"]["rho"],
             "monotonic": f["monotonic_up"] or f["monotonic_down"],
             "n": f["n_valid"]}
            for f in ranked_by_spread
        ],
        "ranked_by_t10_corr": [
            {"name": f["name"], "type": f["type"],
             "rho_t10": f["correlation"]["t10_return"]["rho"],
             "q5_q1_spread": f["q5_q1_tp1_spread"],
             "n": f["n_valid"]}
            for f in ranked_by_t10_corr
        ],
        "type_summary": type_summary,
    }

    _save_result(result)
    return result


def _save_result(result: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "mathlab_subcomponents.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  Results -> {out_path}")


# ────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="AQE Subcomponent Correlation Backtest")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run on 8 tickers only")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-pull all daily bars from FMP")
    args = parser.parse_args()

    if args.refresh:
        import shutil
        if CACHE_DIR.exists():
            n = len(list(CACHE_DIR.glob("*.parquet")))
            print(f"[subcomp] --refresh: clearing {n} cached files")
            shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    run_backtest(dry_run=args.dry_run)
