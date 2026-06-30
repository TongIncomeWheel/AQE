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
ENGINES_CACHE_DIR = CACHE_DIR / "engines"
EVENTS_CACHE_PATH = CACHE_DIR / "events_table.parquet"
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
# Persistence — cache events table + per-ticker engine output
# ────────────────────────────────────────────────────────────────────────────

def _engine_cache_path(ticker: str) -> Path:
    return ENGINES_CACHE_DIR / f"{ticker}_wide.parquet"


def _load_cached_engines(ticker: str) -> pd.DataFrame | None:
    p = _engine_cache_path(ticker)
    if p.exists():
        try:
            df = pd.read_parquet(p)
            if not df.empty and len(df.columns) > 10:
                return df
        except Exception:
            pass
    return None


def _save_engine_cache(ticker: str, wide: pd.DataFrame) -> None:
    ENGINES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wide.to_parquet(_engine_cache_path(ticker), index=False)


def _save_events_table(rows: list[dict], tickers: list[str]) -> None:
    """Persist the events table so Phases 1-3 can be skipped on re-runs."""
    df = pd.DataFrame(rows)
    df.attrs["universe"] = ",".join(sorted(tickers))
    df.attrs["bt_start"] = BT_START
    df.attrs["bt_end"] = BT_END
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(EVENTS_CACHE_PATH, index=False)
    # Also save universe metadata alongside (parquet attrs not always preserved)
    meta = {
        "tickers": sorted(tickers),
        "bt_start": BT_START,
        "bt_end": BT_END,
        "n_events": len(rows),
        "n_tickers": len(tickers),
    }
    meta_path = CACHE_DIR / "events_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Events table cached -> {EVENTS_CACHE_PATH} ({len(rows):,} events)")


def _load_events_table(tickers: list[str] | None = None) -> tuple[list[dict], list[str]] | None:
    """Load cached events table. Returns (rows, tickers) or None if stale/missing."""
    if not EVENTS_CACHE_PATH.exists():
        return None
    meta_path = CACHE_DIR / "events_meta.json"
    if not meta_path.exists():
        return None
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        cached_bt = (meta.get("bt_start"), meta.get("bt_end"))
        if cached_bt != (BT_START, BT_END):
            print(f"  [cache] BT window changed ({cached_bt} -> {(BT_START, BT_END)}), rebuilding")
            return None
        cached_tickers = meta.get("tickers", [])
        if tickers is not None:
            requested = set(tickers)
            cached = set(cached_tickers)
            missing = requested - cached
            if missing:
                print(f"  [cache] {len(missing)} new tickers not in cache, rebuilding")
                return None
        df = pd.read_parquet(EVENTS_CACHE_PATH)
        if df.empty:
            return None
        rows = df.to_dict("records")
        print(f"  [cache] Loaded {len(rows):,} events from cache "
              f"({meta['n_tickers']} tickers, {meta['bt_start']}→{meta['bt_end']})")
        return rows, cached_tickers
    except Exception as e:
        print(f"  [cache] Failed to load: {e}")
        return None


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
    """Real DSL v2.1 bracket: lowest(low,5) - 0.5×ATR, clamped [0.75, 2.0]×ATR."""
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
    struct_low = float(np.min(lo[-5:]))
    buffered_stop = struct_low - 0.5 * atr14
    raw_distance = entry - buffered_stop
    upper_clamp = atr14 * 2.0
    risk = max(min(raw_distance, upper_clamp), atr14 * 0.75)
    sl = entry - risk
    tp1 = entry + risk * 1.5
    tp2 = entry + risk * 2.0
    return entry, sl, tp1, tp2, risk, atr14


@dataclass
class ForwardResult:
    tp1_hit: bool = False
    tp1_day: int | None = None
    tp2_hit: bool = False
    tp2_day: int | None = None
    sl_hit: bool = False
    sl_day: int | None = None
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
            r.sl_day = n
            if r.first_event == "NONE":
                r.first_event = "SL"
        if not r.tp1_hit and bar_hi >= tp1:
            r.tp1_hit = True
            r.tp1_day = n
            if r.first_event == "NONE":
                r.first_event = "TP1"
        if not r.tp2_hit and bar_hi >= tp2:
            r.tp2_hit = True
            r.tp2_day = n
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
                       dd: np.ndarray,
                       tp2_hits: np.ndarray | None = None,
                       sl_hits: np.ndarray | None = None) -> dict:
    """Split values into 5 equal-count groups, measure outcomes per group."""
    mask = ~np.isnan(values)
    if mask.sum() < 100:
        return {}

    v = values[mask]
    tp1 = tp1_hits[mask]
    t5 = t5_returns[mask]
    t10 = t10_returns[mask]
    d = dd[mask]
    tp2 = tp2_hits[mask] if tp2_hits is not None else None
    sl = sl_hits[mask] if sl_hits is not None else None

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
        qd = {
            "n": qn,
            "val_lo": round(float(np.nanmin(v[qm])), 3),
            "val_hi": round(float(np.nanmax(v[qm])), 3),
            "val_median": round(float(np.nanmedian(v[qm])), 3),
            "tp1_rate": round(float(tp1[qm].mean()), 4),
            "avg_t5": round(float(np.nanmean(t5[qm])), 3),
            "avg_t10": round(float(np.nanmean(t10[qm])), 3),
            "avg_dd": round(float(np.nanmean(d[qm])), 3),
        }
        if tp2 is not None:
            qd["tp2_rate"] = round(float(tp2[qm].mean()), 4)
        if sl is not None:
            qd["sl_rate"] = round(float(sl[qm].mean()), 4)
        result[f"Q{q}"] = qd

    if "Q5" in result and "Q1" in result:
        result["q5_q1_tp1_spread"] = round(
            result["Q5"]["tp1_rate"] - result["Q1"]["tp1_rate"], 4)
        if tp2 is not None:
            result["q5_q1_tp2_spread"] = round(
                result["Q5"].get("tp2_rate", 0) - result["Q1"].get("tp2_rate", 0), 4)
        if sl is not None:
            result["q5_q1_sl_spread"] = round(
                result["Q5"].get("sl_rate", 0) - result["Q1"].get("sl_rate", 0), 4)
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
# Phase 6: Recipe discovery — Lasso + Random Forest + Forward Stepwise
#           + Walk-Forward validation
# ────────────────────────────────────────────────────────────────────────────

WALK_FORWARD_SPLIT = "2025-10-01"
MIN_FEATURE_N = 200


def _build_feature_matrix(rows: list[dict], feature_names: list[str]
                          ) -> tuple[pd.DataFrame, list[str]]:
    """Build a clean feature matrix from event rows. Returns (df, valid_cols)."""
    df = pd.DataFrame(rows)
    valid_cols = []
    for fn in feature_names:
        if fn in df.columns:
            n_valid = int(df[fn].notna().sum())
            if n_valid >= MIN_FEATURE_N:
                valid_cols.append(fn)
    return df, valid_cols


def _impute_and_scale(X: np.ndarray) -> np.ndarray:
    """Median-impute NaN, then standardize each column to zero-mean unit-variance."""
    X = X.copy()
    for j in range(X.shape[1]):
        col = X[:, j]
        nan_mask = np.isnan(col)
        if nan_mask.any():
            med = float(np.nanmedian(col))
            col[nan_mask] = med
        mu = col.mean()
        sigma = col.std()
        if sigma > 1e-10:
            X[:, j] = (col - mu) / sigma
        else:
            X[:, j] = 0.0
    return X


def _run_lasso(X: np.ndarray, y: np.ndarray, feature_names: list[str],
               target_name: str, alphas: list[float] | None = None) -> dict:
    """L1-penalized logistic regression — dual output: full + sparse recipe.

    Full: best training accuracy (may select many features).
    Sparse: fewest features within 1pp of the best accuracy — the usable recipe.
    """
    from sklearn.linear_model import LogisticRegression

    X_clean = _impute_and_scale(X.copy())

    if alphas is None:
        alphas = [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
                  1.0, 2.0, 5.0, 10.0, 20.0, 50.0]

    all_fits = []
    for a in alphas:
        C = 1.0 / a
        try:
            lr = LogisticRegression(
                penalty="l1", C=C, solver="saga", max_iter=5000,
                class_weight="balanced", random_state=42,
            )
            lr.fit(X_clean, y)
            score = lr.score(X_clean, y)
            n_nonzero = int(np.sum(np.abs(lr.coef_[0]) > 1e-6))
            if n_nonzero >= 2:
                all_fits.append({"model": lr, "C": C, "alpha": a,
                                 "score": score, "n_features": n_nonzero})
        except Exception:
            continue

    if not all_fits:
        return {"selected": [], "coefficients": {}, "accuracy": 0, "C": 0,
                "sparse": None}

    best_fit = max(all_fits, key=lambda x: x["score"])
    best_score = best_fit["score"]

    # Sparse: fewest features within 1pp of the best accuracy
    candidates = [f for f in all_fits if f["score"] >= best_score - 0.01]
    sparse_fit = min(candidates, key=lambda x: x["n_features"])

    def _extract(fit):
        coefs = fit["model"].coef_[0]
        selected = []
        for i, fn in enumerate(feature_names):
            if abs(coefs[i]) > 1e-6:
                selected.append({
                    "feature": fn,
                    "coefficient": round(float(coefs[i]), 6),
                    "abs_coef": round(abs(float(coefs[i])), 6),
                })
        selected.sort(key=lambda x: x["abs_coef"], reverse=True)
        coef_dict = {s["feature"]: s["coefficient"] for s in selected}
        total_abs = sum(s["abs_coef"] for s in selected)
        recipe_weights = {}
        if total_abs > 0:
            for s in selected:
                recipe_weights[s["feature"]] = round(s["abs_coef"] / total_abs, 4)
        return {
            "selected": selected,
            "coefficients": coef_dict,
            "recipe_weights": recipe_weights,
            "n_selected": len(selected),
            "accuracy": round(float(fit["score"]), 4),
            "C": round(float(fit["C"]), 4),
        }

    full = _extract(best_fit)
    full["target"] = target_name

    if sparse_fit is not best_fit:
        sparse = _extract(sparse_fit)
        sparse["target"] = f"{target_name} (sparse)"
        full["sparse"] = sparse
        print(f"    {target_name} sparse: {sparse['n_selected']} features "
              f"(C={sparse['C']:.4f}, acc={sparse['accuracy']:.3f} "
              f"vs full {full['accuracy']:.3f})")
    else:
        full["sparse"] = None

    return full


def _run_random_forest(X: np.ndarray, y: np.ndarray,
                       feature_names: list[str],
                       target_name: str) -> dict:
    """Random Forest feature importance. Returns ranked features."""
    from sklearn.ensemble import RandomForestClassifier

    X_clean = _impute_and_scale(X.copy())

    rf = RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=50,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    rf.fit(X_clean, y)

    importances = rf.feature_importances_
    ranked = []
    for i, fn in enumerate(feature_names):
        ranked.append({
            "feature": fn,
            "importance": round(float(importances[i]), 6),
        })
    ranked.sort(key=lambda x: x["importance"], reverse=True)

    accuracy = round(float(rf.score(X_clean, y)), 4)

    return {
        "target": target_name,
        "ranked": ranked,
        "top_10": [r["feature"] for r in ranked[:10]],
        "accuracy": accuracy,
    }


def _run_forward_stepwise(X: np.ndarray, y: np.ndarray,
                          feature_names: list[str],
                          target_name: str,
                          max_features: int = 8) -> dict:
    """Greedy forward stepwise: add the feature that most improves TP1 prediction.

    NOTE: Bias-prone — the greedy path may miss globally better combos.
    Included as a directional signal, not a definitive answer.
    """
    from sklearn.linear_model import LogisticRegression

    X_clean = _impute_and_scale(X.copy())
    n_feat = X_clean.shape[1]

    selected_idx = []
    selected_names = []
    steps = []
    best_score = 0.0

    for step in range(min(max_features, n_feat)):
        best_candidate = -1
        best_candidate_score = best_score

        for j in range(n_feat):
            if j in selected_idx:
                continue
            trial_idx = selected_idx + [j]
            X_trial = X_clean[:, trial_idx]
            try:
                lr = LogisticRegression(
                    penalty="l2", C=1.0, solver="lbfgs", max_iter=2000,
                    class_weight="balanced", random_state=42,
                )
                lr.fit(X_trial, y)
                score = lr.score(X_trial, y)
                if score > best_candidate_score:
                    best_candidate_score = score
                    best_candidate = j
            except Exception:
                continue

        if best_candidate < 0 or best_candidate_score <= best_score + 0.001:
            break

        selected_idx.append(best_candidate)
        selected_names.append(feature_names[best_candidate])
        best_score = best_candidate_score
        steps.append({
            "step": step + 1,
            "added": feature_names[best_candidate],
            "accuracy": round(best_candidate_score, 4),
            "features_so_far": list(selected_names),
        })

    return {
        "target": target_name,
        "selected": selected_names,
        "n_selected": len(selected_names),
        "final_accuracy": round(best_score, 4),
        "steps": steps,
        "note": "Greedy — may miss globally better combos. Directional only.",
    }


def _walk_forward_validate(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    recipe_weights: dict[str, float],
    split_date: str,
    baseline_rate: float,
) -> dict:
    """Walk-forward validation: train on data before split, test after.

    Builds a weighted composite from recipe_weights, splits into quintiles
    on the TRAIN set, then applies the same thresholds to TEST and measures
    whether the edge holds out-of-sample.
    """
    df = df.copy()
    df["_date"] = pd.to_datetime(df["date"])
    split = pd.Timestamp(split_date)

    train = df[df["_date"] < split]
    test = df[df["_date"] >= split]

    if len(train) < 200 or len(test) < 100:
        return {"error": "insufficient_data", "n_train": len(train), "n_test": len(test)}

    # Build composite score using recipe weights
    feats_in_recipe = [f for f in recipe_weights if f in feature_cols]
    if not feats_in_recipe:
        return {"error": "no_features_in_recipe"}

    def _build_composite(subset: pd.DataFrame) -> np.ndarray:
        composite = np.zeros(len(subset))
        total_w = sum(recipe_weights[f] for f in feats_in_recipe)
        for fn in feats_in_recipe:
            vals = subset[fn].values.astype(float)
            nan_mask = np.isnan(vals)
            if nan_mask.any():
                vals[nan_mask] = float(np.nanmedian(vals))
            mu = np.nanmean(vals)
            sigma = np.nanstd(vals)
            if sigma > 1e-10:
                normed = (vals - mu) / sigma
            else:
                normed = np.zeros_like(vals)
            composite += normed * (recipe_weights[fn] / total_w)
        return composite

    # Train: build composite, find quintile thresholds
    train_composite = _build_composite(train)
    thresholds = [np.percentile(train_composite, p) for p in [20, 40, 60, 80]]

    def _quintile_label(val):
        if val < thresholds[0]:
            return 1
        elif val < thresholds[1]:
            return 2
        elif val < thresholds[2]:
            return 3
        elif val < thresholds[3]:
            return 4
        return 5

    # Test: apply TRAIN thresholds to test data
    test_composite = _build_composite(test)
    test_quintiles = np.array([_quintile_label(v) for v in test_composite])
    test_target = test[target_col].values.astype(float)

    # Also get train quintile rates for comparison
    train_quintiles = np.array([_quintile_label(v) for v in train_composite])
    train_target = train[target_col].values.astype(float)

    result_quintiles = {}
    for q in range(1, 6):
        train_mask = train_quintiles == q
        test_mask = test_quintiles == q
        n_train_q = int(train_mask.sum())
        n_test_q = int(test_mask.sum())

        train_rate = float(train_target[train_mask].mean()) if n_train_q > 10 else None
        test_rate = float(test_target[test_mask].mean()) if n_test_q > 10 else None

        result_quintiles[f"Q{q}"] = {
            "n_train": n_train_q,
            "n_test": n_test_q,
            "train_rate": round(train_rate, 4) if train_rate is not None else None,
            "test_rate": round(test_rate, 4) if test_rate is not None else None,
        }

    # Overall metrics
    train_top = train_quintiles == 5
    test_top = test_quintiles == 5
    train_bot = train_quintiles == 1
    test_bot = test_quintiles == 1

    in_sample_top = float(train_target[train_top].mean()) if train_top.sum() > 10 else 0
    out_sample_top = float(test_target[test_top].mean()) if test_top.sum() > 10 else 0
    in_sample_bot = float(train_target[train_bot].mean()) if train_bot.sum() > 10 else 0
    out_sample_bot = float(test_target[test_bot].mean()) if test_bot.sum() > 10 else 0

    return {
        "split_date": split_date,
        "n_train": len(train),
        "n_test": len(test),
        "target": target_col,
        "recipe_features": feats_in_recipe,
        "recipe_weights": {f: round(recipe_weights[f], 4) for f in feats_in_recipe},
        "in_sample": {
            "top_quintile_rate": round(in_sample_top, 4),
            "bot_quintile_rate": round(in_sample_bot, 4),
            "spread_pp": round((in_sample_top - in_sample_bot) * 100, 2),
            "edge_vs_baseline_pp": round((in_sample_top - baseline_rate) * 100, 2),
        },
        "out_of_sample": {
            "top_quintile_rate": round(out_sample_top, 4),
            "bot_quintile_rate": round(out_sample_bot, 4),
            "spread_pp": round((out_sample_top - out_sample_bot) * 100, 2),
            "edge_vs_baseline_pp": round((out_sample_top - baseline_rate) * 100, 2),
        },
        "edge_survived": out_sample_top > baseline_rate,
        "spread_survived": (out_sample_top - out_sample_bot) > 0,
        "quintiles": result_quintiles,
    }


def _find_best_combinations(
    rows: list[dict],
    feature_names: list[str],
    feature_results: dict[str, dict],
    tp1_arr: np.ndarray,
    tp2_arr: np.ndarray,
    sl_arr: np.ndarray,
    t5_arr: np.ndarray,
    t10_arr: np.ndarray,
    dd_arr: np.ndarray,
    baseline_tp1: float,
    baseline_tp2: float,
    baseline_sl: float,
) -> dict:
    """Phase 6: Multi-method recipe discovery.

    6A — Lasso logistic regression (L1): fits all features at once, zeros out
         the useless ones. Coefficients = the recipe weights.
    6B — Random Forest: tree-based feature importance. Captures non-linear
         interactions that Lasso misses.
    6C — Forward stepwise: greedy feature addition. Bias-prone but directional.
    6D — Walk-forward validation: train before Oct 2025, test after. Any recipe
         that works in-sample but fails out-of-sample is overfitting.
    """
    print(f"\n-- Phase 6: Multi-method recipe discovery --")

    df, valid_cols = _build_feature_matrix(rows, feature_names)
    X = df[valid_cols].values.astype(float)
    tp1_y = df["tp1_hit"].values.astype(int)
    tp2_y = df["tp2_hit"].values.astype(int)
    sl_y = df["sl_hit"].values.astype(int)

    print(f"  Feature matrix: {X.shape[0]} events × {X.shape[1]} features")

    # ═══════════════════════════════════════════════════════════════════
    # 6A: Lasso logistic regression
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n  ── 6A: Lasso Logistic Regression ──")

    lasso_tp1 = _run_lasso(X, tp1_y, valid_cols, "TP1")
    print(f"    TP1: {lasso_tp1['n_selected']} features selected "
          f"(accuracy={lasso_tp1['accuracy']:.3f})")
    for s in lasso_tp1["selected"][:10]:
        sign = "+" if s["coefficient"] > 0 else "-"
        w = lasso_tp1["recipe_weights"].get(s["feature"], 0)
        print(f"      {sign} {s['feature']:25s}  coef={s['coefficient']:+.4f}  "
              f"weight={w:.1%}")

    lasso_tp2 = _run_lasso(X, tp2_y, valid_cols, "TP2")
    print(f"    TP2: {lasso_tp2['n_selected']} features selected "
          f"(accuracy={lasso_tp2['accuracy']:.3f})")
    for s in lasso_tp2["selected"][:10]:
        sign = "+" if s["coefficient"] > 0 else "-"
        print(f"      {sign} {s['feature']:25s}  coef={s['coefficient']:+.4f}")

    lasso_sl = _run_lasso(X, sl_y, valid_cols, "SL (toxic)")
    print(f"    SL:  {lasso_sl['n_selected']} features selected "
          f"(accuracy={lasso_sl['accuracy']:.3f})")
    for s in lasso_sl["selected"][:10]:
        sign = "+" if s["coefficient"] > 0 else "-"
        print(f"      {sign} {s['feature']:25s}  coef={s['coefficient']:+.4f}")

    # ═══════════════════════════════════════════════════════════════════
    # 6B: Random Forest feature importance
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n  ── 6B: Random Forest Feature Importance ──")

    rf_tp1 = _run_random_forest(X, tp1_y, valid_cols, "TP1")
    print(f"    TP1 accuracy={rf_tp1['accuracy']:.3f}")
    print(f"    Top 10: {rf_tp1['top_10']}")
    for r in rf_tp1["ranked"][:10]:
        print(f"      {r['feature']:25s}  importance={r['importance']:.4f}")

    rf_tp2 = _run_random_forest(X, tp2_y, valid_cols, "TP2")
    print(f"    TP2 top 10: {rf_tp2['top_10']}")

    rf_sl = _run_random_forest(X, sl_y, valid_cols, "SL")
    print(f"    SL top 10: {rf_sl['top_10']}")

    # ═══════════════════════════════════════════════════════════════════
    # 6C: Forward stepwise (directional, bias-prone)
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n  ── 6C: Forward Stepwise (directional, bias caveat) ──")

    stepwise_tp1 = _run_forward_stepwise(X, tp1_y, valid_cols, "TP1")
    print(f"    TP1: {stepwise_tp1['n_selected']} features, "
          f"accuracy={stepwise_tp1['final_accuracy']:.3f}")
    for step in stepwise_tp1["steps"]:
        print(f"      Step {step['step']}: +{step['added']} → {step['accuracy']:.3f}")

    stepwise_sl = _run_forward_stepwise(X, sl_y, valid_cols, "SL")
    print(f"    SL:  {stepwise_sl['n_selected']} features, "
          f"accuracy={stepwise_sl['final_accuracy']:.3f}")

    # ═══════════════════════════════════════════════════════════════════
    # 6D: Walk-forward validation
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n  ── 6D: Walk-Forward Validation (split={WALK_FORWARD_SPLIT}) ──")

    # Validate the Lasso TP1 recipe
    wf_lasso_tp1 = _walk_forward_validate(
        df, valid_cols, "tp1_hit",
        lasso_tp1["recipe_weights"], WALK_FORWARD_SPLIT, baseline_tp1,
    )
    if "error" not in wf_lasso_tp1:
        ins = wf_lasso_tp1["in_sample"]
        oos = wf_lasso_tp1["out_of_sample"]
        survived = "YES" if wf_lasso_tp1["edge_survived"] else "NO"
        print(f"    Lasso TP1 recipe:")
        print(f"      In-sample:  top Q={ins['top_quintile_rate']*100:.1f}%  "
              f"edge={ins['edge_vs_baseline_pp']:+.1f}pp  "
              f"spread={ins['spread_pp']:+.1f}pp")
        print(f"      Out-sample: top Q={oos['top_quintile_rate']*100:.1f}%  "
              f"edge={oos['edge_vs_baseline_pp']:+.1f}pp  "
              f"spread={oos['spread_pp']:+.1f}pp  "
              f"SURVIVED={survived}")
    else:
        print(f"    Lasso TP1: {wf_lasso_tp1['error']}")

    # Validate the Lasso TP2 recipe
    wf_lasso_tp2 = _walk_forward_validate(
        df, valid_cols, "tp2_hit",
        lasso_tp2["recipe_weights"], WALK_FORWARD_SPLIT, baseline_tp2,
    )
    if "error" not in wf_lasso_tp2:
        ins = wf_lasso_tp2["in_sample"]
        oos = wf_lasso_tp2["out_of_sample"]
        survived = "YES" if wf_lasso_tp2["edge_survived"] else "NO"
        print(f"    Lasso TP2 recipe:")
        print(f"      In-sample:  top Q={ins['top_quintile_rate']*100:.1f}%  "
              f"edge={ins['edge_vs_baseline_pp']:+.1f}pp  "
              f"spread={ins['spread_pp']:+.1f}pp")
        print(f"      Out-sample: top Q={oos['top_quintile_rate']*100:.1f}%  "
              f"edge={oos['edge_vs_baseline_pp']:+.1f}pp  "
              f"spread={oos['spread_pp']:+.1f}pp  "
              f"SURVIVED={survived}")

    # Validate the Lasso SL recipe
    wf_lasso_sl = _walk_forward_validate(
        df, valid_cols, "sl_hit",
        lasso_sl["recipe_weights"], WALK_FORWARD_SPLIT, baseline_sl,
    )
    if "error" not in wf_lasso_sl:
        ins = wf_lasso_sl["in_sample"]
        oos = wf_lasso_sl["out_of_sample"]
        survived = "YES" if wf_lasso_sl["edge_survived"] else "NO"
        print(f"    Lasso SL recipe:")
        print(f"      In-sample:  top Q={ins['top_quintile_rate']*100:.1f}%  "
              f"spread={ins['spread_pp']:+.1f}pp")
        print(f"      Out-sample: top Q={oos['top_quintile_rate']*100:.1f}%  "
              f"spread={oos['spread_pp']:+.1f}pp  "
              f"SURVIVED={survived}")

    # Validate the SPARSE Lasso TP1 recipe (if different from full)
    wf_sparse_tp1 = {}
    if lasso_tp1.get("sparse") and lasso_tp1["sparse"]["recipe_weights"]:
        wf_sparse_tp1 = _walk_forward_validate(
            df, valid_cols, "tp1_hit",
            lasso_tp1["sparse"]["recipe_weights"], WALK_FORWARD_SPLIT, baseline_tp1,
        )
        if "error" not in wf_sparse_tp1:
            ins = wf_sparse_tp1["in_sample"]
            oos = wf_sparse_tp1["out_of_sample"]
            survived = "YES" if wf_sparse_tp1["edge_survived"] else "NO"
            n_sp = lasso_tp1["sparse"]["n_selected"]
            print(f"    Sparse Lasso TP1 ({n_sp} features):")
            print(f"      In-sample:  top Q={ins['top_quintile_rate']*100:.1f}%  "
                  f"edge={ins['edge_vs_baseline_pp']:+.1f}pp  "
                  f"spread={ins['spread_pp']:+.1f}pp")
            print(f"      Out-sample: top Q={oos['top_quintile_rate']*100:.1f}%  "
                  f"edge={oos['edge_vs_baseline_pp']:+.1f}pp  "
                  f"spread={oos['spread_pp']:+.1f}pp  "
                  f"SURVIVED={survived}")

    # Validate the RF top features as an equal-weight recipe
    rf_top_feats = rf_tp1["top_10"][:5]
    rf_recipe = {f: 0.2 for f in rf_top_feats}
    wf_rf_tp1 = _walk_forward_validate(
        df, valid_cols, "tp1_hit",
        rf_recipe, WALK_FORWARD_SPLIT, baseline_tp1,
    )
    if "error" not in wf_rf_tp1:
        ins = wf_rf_tp1["in_sample"]
        oos = wf_rf_tp1["out_of_sample"]
        survived = "YES" if wf_rf_tp1["edge_survived"] else "NO"
        print(f"    RF top-5 equal-weight:")
        print(f"      In-sample:  top Q={ins['top_quintile_rate']*100:.1f}%  "
              f"edge={ins['edge_vs_baseline_pp']:+.1f}pp  "
              f"spread={ins['spread_pp']:+.1f}pp")
        print(f"      Out-sample: top Q={oos['top_quintile_rate']*100:.1f}%  "
              f"edge={oos['edge_vs_baseline_pp']:+.1f}pp  "
              f"spread={oos['spread_pp']:+.1f}pp  "
              f"SURVIVED={survived}")

    # ═══════════════════════════════════════════════════════════════════
    # Cross-method agreement — features that appear across methods
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n  ── Cross-Method Agreement ──")

    lasso_set = set(lasso_tp1["coefficients"].keys())
    rf_set = set(rf_tp1["top_10"])
    step_set = set(stepwise_tp1["selected"])

    agreement_all = lasso_set & rf_set & step_set
    agreement_2of3 = (lasso_set & rf_set) | (lasso_set & step_set) | (rf_set & step_set)

    print(f"    All 3 methods agree on: {sorted(agreement_all) if agreement_all else 'none'}")
    print(f"    At least 2 of 3 agree on: {sorted(agreement_2of3)}")

    # SL agreement
    lasso_sl_set = set(lasso_sl["coefficients"].keys())
    rf_sl_set = set(rf_sl["top_10"])
    step_sl_set = set(stepwise_sl["selected"])
    sl_agreement = (lasso_sl_set & rf_sl_set) | (lasso_sl_set & step_sl_set) | (rf_sl_set & step_sl_set)
    print(f"    SL toxic (2+ agree): {sorted(sl_agreement)}")

    return {
        "lasso": {
            "tp1": lasso_tp1,
            "tp2": lasso_tp2,
            "sl": lasso_sl,
        },
        "random_forest": {
            "tp1": rf_tp1,
            "tp2": rf_tp2,
            "sl": rf_sl,
        },
        "forward_stepwise": {
            "tp1": stepwise_tp1,
            "sl": stepwise_sl,
        },
        "walk_forward": {
            "lasso_tp1": wf_lasso_tp1,
            "lasso_tp2": wf_lasso_tp2,
            "lasso_sl": wf_lasso_sl,
            "sparse_lasso_tp1": wf_sparse_tp1,
            "rf_tp1": wf_rf_tp1,
        },
        "cross_method_agreement": {
            "tp1_all_3": sorted(agreement_all),
            "tp1_2_of_3": sorted(agreement_2of3),
            "sl_2_of_3": sorted(sl_agreement),
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# Main runner
# ────────────────────────────────────────────────────────────────────────────

def run_backtest(tickers: list[str] | None = None,
                 dry_run: bool = False,
                 rebuild: bool = False) -> dict:
    if tickers is None:
        tickers = load_universe()
    if dry_run:
        tickers = tickers[:8]

    print(f"[subcomp] Universe: {len(tickers)} tickers")
    print(f"[subcomp] BT window: {BT_START} -> {BT_END}")

    feature_names = _all_feature_names()
    failed: list[str] = []

    # ── Try loading cached events table (skip Phases 1-3) ──
    rows = None
    if not rebuild:
        cached = _load_events_table(tickers)
        if cached is not None:
            rows, cached_tickers = cached
            failed = [t for t in tickers if t not in set(cached_tickers)]
            print(f"  Skipping Phases 1-3 (data loaded from cache)")

    if rows is None:
        # ── Phase 1: Pull bars ──
        print("\n-- Phase 1: Pulling daily bars --")
        all_bars: dict[str, pd.DataFrame] = {}

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
            log_this = i <= 3 or i % 30 == 0 or i == len(all_bars)
            if log_this:
                print(f"  [{i}/{len(all_bars)}] {tk}...", end=" ", flush=True)

            # Check engine cache first
            if not rebuild:
                cached_wide = _load_cached_engines(tk)
                if cached_wide is not None:
                    all_wide[tk] = cached_wide
                    if log_this:
                        print("cached")
                    continue

            wide = compute_all_subcomponents(tk, bars, spy_bars)
            if wide is not None:
                all_wide[tk] = wide
                _save_engine_cache(tk, wide)
                if log_this:
                    valid = wide.drop(columns=["date"]).notna().sum(axis=0)
                    n_valid = int((valid > 0).sum())
                    print(f"{n_valid} features")
            else:
                if log_this:
                    print("SKIP (too few bars)")

        print(f"  Engines computed: {len(all_wide)}/{len(all_bars)} tickers")

        # ── Phase 3: Build events ──
        print(f"\n-- Phase 3: Building events --")
        bt_start = pd.Timestamp(BT_START)
        bt_end = pd.Timestamp(BT_END)

        rows = []
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
                    "tp2_hit": 1 if fwd.tp2_hit and fwd.first_event != "SL" else 0,
                    "sl_hit": 1 if fwd.first_event == "SL" else 0,
                    "sl_first": 1 if fwd.sl_hit else 0,
                    "outcome": fwd.first_event,
                    "t5_return": fwd.returns.get("T+5", np.nan),
                    "t10_return": fwd.returns.get("T+10", np.nan),
                    "max_dd": fwd.max_dd_pct,
                    "risk_atr_ratio": round(risk / atr14, 4) if atr14 > 0 else np.nan,
                }
                for fn in feature_names:
                    ev[fn] = float(row[fn]) if fn in row.index and not pd.isna(row.get(fn)) else np.nan

                rows.append(ev)
                last_trigger = dt

        print(f"  Total dates scanned: {total_dates:,}")
        print(f"  Events (with cooldown): {len(rows):,}")

        # Persist the events table for future runs
        _save_events_table(rows, list(all_wide.keys()))

    if len(rows) < 100:
        print("  [!] Too few events for analysis")
        return {"error": "insufficient_data", "n_events": len(rows)}

    # ── Phase 4: Univariate correlation + quintile analysis ──
    print(f"\n-- Phase 4: Univariate correlation + quintile analysis --")

    tp1_arr = np.array([r["tp1_hit"] for r in rows], dtype=float)
    tp2_arr = np.array([r["tp2_hit"] for r in rows], dtype=float)
    sl_arr = np.array([r["sl_hit"] for r in rows], dtype=float)
    sl_first_arr = np.array([r["sl_first"] for r in rows], dtype=float)
    t5_arr = np.array([r.get("t5_return", np.nan) for r in rows], dtype=float)
    t10_arr = np.array([r.get("t10_return", np.nan) for r in rows], dtype=float)
    dd_arr = np.array([r["max_dd"] for r in rows], dtype=float)

    baseline_tp1 = float(tp1_arr.mean())
    baseline_tp2 = float(tp2_arr.mean())
    baseline_sl = float(sl_arr.mean())
    baseline_t5 = float(np.nanmean(t5_arr))
    baseline_t10 = float(np.nanmean(t10_arr))
    baseline_dd = float(np.nanmean(dd_arr))

    print(f"  Baseline: TP1={baseline_tp1*100:.1f}%  TP2={baseline_tp2*100:.1f}%  "
          f"SL={baseline_sl*100:.1f}%  T+5={baseline_t5:.3f}%  "
          f"T+10={baseline_t10:.3f}%  DD={baseline_dd:.2f}%")

    # ── Filtered baseline: does screening by SC_MOM actually help? ──
    sc_mom_arr = np.array([r.get("sc_mom", np.nan) for r in rows], dtype=float)
    filtered_baselines = {}
    for threshold in [0, 50, 60, 70, 75, 80]:
        mask = sc_mom_arr >= threshold if threshold > 0 else np.ones(len(rows), dtype=bool)
        n = int(mask.sum())
        if n < 50:
            continue
        fb = {
            "threshold": threshold,
            "n": n,
            "tp1_rate": round(float(tp1_arr[mask].mean()), 4),
            "tp2_rate": round(float(tp2_arr[mask].mean()), 4),
            "sl_rate": round(float(sl_arr[mask].mean()), 4),
            "avg_t5": round(float(np.nanmean(t5_arr[mask])), 3),
            "avg_t10": round(float(np.nanmean(t10_arr[mask])), 3),
        }
        filtered_baselines[threshold] = fb

    if filtered_baselines:
        print(f"\n  FILTERED BASELINES (by SC_MOM threshold):")
        print(f"  {'SC_MOM≥':>8s}  {'n':>6s}  {'TP1':>6s}  {'TP2':>6s}  "
              f"{'SL':>6s}  {'T+5':>7s}  {'T+10':>7s}")
        print("  " + "-" * 56)
        for thr, fb in sorted(filtered_baselines.items()):
            label = "ALL" if thr == 0 else f"{thr}"
            print(f"  {label:>8s}  {fb['n']:>6,}  {fb['tp1_rate']*100:>5.1f}%  "
                  f"{fb['tp2_rate']*100:>5.1f}%  {fb['sl_rate']*100:>5.1f}%  "
                  f"{fb['avg_t5']:>+6.2f}%  {fb['avg_t10']:>+6.2f}%")

    # ── Risk stats: what's the typical 1R in ATR terms? ──
    risk_arr = np.array([r.get("risk_atr_ratio", np.nan) for r in rows], dtype=float)
    valid_risk = risk_arr[~np.isnan(risk_arr)]
    if len(valid_risk) > 0:
        print(f"\n  DSL bracket stats: median 1R = {np.median(valid_risk):.2f}×ATR  "
              f"mean = {np.mean(valid_risk):.2f}×ATR  "
              f"range [{np.min(valid_risk):.2f}, {np.max(valid_risk):.2f}]")

    feature_results: dict[str, dict] = {}
    for fn in feature_names:
        vals = np.array([r.get(fn, np.nan) for r in rows], dtype=float)
        n_valid = int(np.sum(~np.isnan(vals)))

        if n_valid < 100:
            continue

        meta = _feature_meta(fn)

        rho_tp1, p_tp1 = _spearman(vals, tp1_arr)
        rho_tp2, p_tp2 = _spearman(vals, tp2_arr)
        rho_sl, p_sl = _spearman(vals, sl_arr)
        rho_t5, p_t5 = _spearman(vals, t5_arr)
        rho_t10, p_t10 = _spearman(vals, t10_arr)
        rho_dd, p_dd = _spearman(vals, dd_arr)

        quint = _quintile_analysis(vals, tp1_arr, t5_arr, t10_arr, dd_arr,
                                   tp2_hits=tp2_arr, sl_hits=sl_arr)

        feature_results[fn] = {
            "name": fn,
            "type": meta["type"],
            "engine": meta["engine"],
            "description": meta["description"],
            "n_valid": n_valid,
            "correlation": {
                "tp1_hit": {"rho": rho_tp1, "p": p_tp1},
                "tp2_hit": {"rho": rho_tp2, "p": p_tp2},
                "sl_hit": {"rho": rho_sl, "p": p_sl},
                "t5_return": {"rho": rho_t5, "p": p_t5},
                "t10_return": {"rho": rho_t10, "p": p_t10},
                "max_drawdown": {"rho": rho_dd, "p": p_dd},
            },
            "quintiles": quint,
            "q5_q1_tp1_spread": quint.get("q5_q1_tp1_spread", 0.0),
            "q5_q1_tp2_spread": quint.get("q5_q1_tp2_spread", 0.0),
            "q5_q1_sl_spread": quint.get("q5_q1_sl_spread", 0.0),
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

    ranked_by_sl = sorted(
        feature_results.values(),
        key=lambda f: abs(f.get("q5_q1_sl_spread", 0)),
        reverse=True,
    )

    type_summary = _type_group_summary(feature_results)

    # Print top 25 by TP1 spread
    print(f"\n  TOP 25 by TP1 quintile spread:")
    print(f"  {'Rank':>4s}  {'Feature':25s}  {'Type':18s}  {'Engine':10s}  "
          f"{'Q5-Q1 TP1':>9s}  {'Q5-Q1 TP2':>9s}  {'Q5-Q1 SL':>8s}  "
          f"{'rho_TP1':>8s}  {'Mono':>4s}  {'n':>6s}")
    print("  " + "-" * 130)
    for i, f in enumerate(ranked_by_spread[:25], 1):
        mono = "UP" if f["monotonic_up"] else ("DN" if f["monotonic_down"] else "  ")
        rho_tp1 = f["correlation"]["tp1_hit"]["rho"]
        tp1_sp = f["q5_q1_tp1_spread"]
        tp2_sp = f.get("q5_q1_tp2_spread", 0)
        sl_sp = f.get("q5_q1_sl_spread", 0)
        print(f"  {i:>4d}  {f['name']:25s}  {f['type']:18s}  {f['engine']:10s}  "
              f"{tp1_sp*100:>+8.2f}%  {tp2_sp*100:>+8.2f}%  {sl_sp*100:>+7.2f}%  "
              f"{rho_tp1:>+7.4f}  {mono:>4s}  {f['n_valid']:>6,}")

    # Print SL toxicity ranking
    print(f"\n  TOP 15 SL TOXICITY (features most correlated with stop-loss hits):")
    print(f"  {'Rank':>4s}  {'Feature':25s}  {'Type':18s}  {'Q5-Q1 SL':>8s}  "
          f"{'rho_SL':>8s}  {'Q5 SL%':>7s}  {'Q1 SL%':>7s}")
    print("  " + "-" * 100)
    for i, f in enumerate(ranked_by_sl[:15], 1):
        rho_sl = f["correlation"]["sl_hit"]["rho"]
        sl_sp = f.get("q5_q1_sl_spread", 0)
        q5_sl = f.get("quintiles", {}).get("Q5", {}).get("sl_rate", 0)
        q1_sl = f.get("quintiles", {}).get("Q1", {}).get("sl_rate", 0)
        print(f"  {i:>4d}  {f['name']:25s}  {f['type']:18s}  "
              f"{sl_sp*100:>+7.2f}%  {rho_sl:>+7.4f}  "
              f"{q5_sl*100:>6.1f}%  {q1_sl*100:>6.1f}%")

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
    print(f"\n  QUINTILE DETAIL (top 5 by TP1 spread):")
    for f in ranked_by_spread[:5]:
        print(f"\n  {f['name']} ({f['type']}, {f['engine']}): "
              f"Q5-Q1 TP1={f['q5_q1_tp1_spread']*100:+.2f}pp  "
              f"TP2={f.get('q5_q1_tp2_spread',0)*100:+.2f}pp  "
              f"SL={f.get('q5_q1_sl_spread',0)*100:+.2f}pp")
        quint = f.get("quintiles", {})
        for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
            qd = quint.get(q, {})
            if qd:
                tp2_s = f"  TP2={qd.get('tp2_rate',0)*100:>5.1f}%" if "tp2_rate" in qd else ""
                sl_s = f"  SL={qd.get('sl_rate',0)*100:>5.1f}%" if "sl_rate" in qd else ""
                print(f"    {q}: n={qd['n']:>5,}  "
                      f"val=[{qd['val_lo']:.1f}-{qd['val_hi']:.1f}]  "
                      f"TP1={qd['tp1_rate']*100:>5.1f}%{tp2_s}{sl_s}  "
                      f"T+5={qd['avg_t5']:>+6.2f}%  "
                      f"T+10={qd['avg_t10']:>+6.2f}%  "
                      f"DD={qd['avg_dd']:>+6.2f}%")

    # ── Phase 6: Combination finder ──
    combo_results = _find_best_combinations(rows, feature_names, feature_results,
                                            tp1_arr, tp2_arr, sl_arr, t5_arr,
                                            t10_arr, dd_arr, baseline_tp1,
                                            baseline_tp2, baseline_sl)

    # ── Build result ──
    result = {
        "run_date": str(pd.Timestamp.now().date()),
        "universe_size": len(tickers),
        "bt_window": {"from": BT_START, "to": BT_END},
        "total_events": len(rows),
        "data_unavailable": failed,
        "baseline": {
            "tp1_rate": round(baseline_tp1, 4),
            "tp2_rate": round(baseline_tp2, 4),
            "sl_rate": round(baseline_sl, 4),
            "avg_t5": round(baseline_t5, 3),
            "avg_t10": round(baseline_t10, 3),
            "avg_dd": round(baseline_dd, 3),
        },
        "filtered_baselines": filtered_baselines if filtered_baselines else {},
        "bracket_stats": {
            "median_risk_atr": round(float(np.median(valid_risk)), 4) if len(valid_risk) > 0 else None,
            "mean_risk_atr": round(float(np.mean(valid_risk)), 4) if len(valid_risk) > 0 else None,
            "min_risk_atr": round(float(np.min(valid_risk)), 4) if len(valid_risk) > 0 else None,
            "max_risk_atr": round(float(np.max(valid_risk)), 4) if len(valid_risk) > 0 else None,
            "note": "1R in ATR multiples; TP1 = 1.5R above entry, TP2 = 2.0R above entry",
        },
        "n_features_tested": len(feature_results),
        "features": {k: v for k, v in feature_results.items()},
        "ranked_by_tp1_spread": [
            {"name": f["name"], "type": f["type"], "engine": f["engine"],
             "q5_q1_tp1_spread": f["q5_q1_tp1_spread"],
             "q5_q1_tp2_spread": f.get("q5_q1_tp2_spread", 0),
             "q5_q1_sl_spread": f.get("q5_q1_sl_spread", 0),
             "rho_tp1": f["correlation"]["tp1_hit"]["rho"],
             "rho_tp2": f["correlation"]["tp2_hit"]["rho"],
             "rho_sl": f["correlation"]["sl_hit"]["rho"],
             "rho_t10": f["correlation"]["t10_return"]["rho"],
             "monotonic": f["monotonic_up"] or f["monotonic_down"],
             "n": f["n_valid"]}
            for f in ranked_by_spread
        ],
        "ranked_by_sl_toxicity": [
            {"name": f["name"], "type": f["type"],
             "q5_q1_sl_spread": f.get("q5_q1_sl_spread", 0),
             "rho_sl": f["correlation"]["sl_hit"]["rho"],
             "q5_sl_rate": f.get("quintiles", {}).get("Q5", {}).get("sl_rate", 0),
             "q1_sl_rate": f.get("quintiles", {}).get("Q1", {}).get("sl_rate", 0),
             "n": f["n_valid"]}
            for f in ranked_by_sl
        ],
        "ranked_by_t10_corr": [
            {"name": f["name"], "type": f["type"],
             "rho_t10": f["correlation"]["t10_return"]["rho"],
             "q5_q1_tp1_spread": f["q5_q1_tp1_spread"],
             "n": f["n_valid"]}
            for f in ranked_by_t10_corr
        ],
        "type_summary": type_summary,
        "combinations": combo_results,
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
                        help="Re-pull all daily bars from FMP (clears bar cache)")
    parser.add_argument("--rebuild", action="store_true",
                        help="Rebuild events table + engines from scratch (ignores all caches)")
    parser.add_argument("--analysis-only", action="store_true",
                        help="Skip Phases 1-3, load cached events, re-run analysis only (Phases 4-6)")
    args = parser.parse_args()

    rebuild = args.rebuild
    if args.refresh:
        import shutil
        if CACHE_DIR.exists():
            n = len(list(CACHE_DIR.glob("*.parquet")))
            print(f"[subcomp] --refresh: clearing ALL cached files ({n})")
            shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        rebuild = True

    if args.analysis_only:
        cached = _load_events_table()
        if cached is None:
            print("[subcomp] No cached events table found. Run without --analysis-only first.")
        else:
            print("[subcomp] --analysis-only: skipping Phases 1-3")

    run_backtest(dry_run=args.dry_run, rebuild=rebuild)
