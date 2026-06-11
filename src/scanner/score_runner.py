"""Run all engines + composites across the cached price panel.

Reads:
    data/panel_daily.parquet
    data/panel_weekly.parquet
    data/spy_daily.parquet

Writes:
    data/scores_daily.parquet

Run from a fresh shell:
    python -m src.scanner.score_runner
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.earnings import load_earnings
from src.data.fmp_client import iter_with_progress
from src.data.paths import DATA_DIR, PANEL_DAILY, PANEL_WEEKLY, SCORES_DAILY, SPY_DAILY
from src.engines import bq, elder, energy, flow, k39, mp, pipeline_rank, scoring, structure
from src.engines.utils import atr


SCORE_COLUMNS = [
    "date", "ticker",
    "close", "atr14",
    # ── Aggregate scores ──
    "flow_100", "energy_100", "structure_100", "mp_100", "elder_score",
    "bq_100", "k39_value",
    "mp_state", "impulse_state",
    "sc_momentum", "sc_momentum_raw", "sc_position", "sc_position_raw",
    "sc_m_gates", "sc_p_gates",
    "pipe_rank", "fip_quality", "fip_raw", "fip_spike_excluded", "fip_window_effective",
    # ── Flow sub-components ──
    "flow_score", "accum_score", "volume_score", "skew_score", "ext_score",
    "mfi", "cmf", "ha_quality_count",
    # ── Energy sub-components ──
    "vp_position_score", "price_action_score", "squeeze_score",
    "exhaustion_score", "atr_score", "en_pos50", "en_trend_bars",
    # ── Structure sub-components ──
    "rs_spy_score", "rs_accel_score", "base_score", "ms_pos_score",
    "resist_score", "wk_score", "earn_score",
    "base_days", "bd_mode", "ms_p50", "rs_vs_spy", "rs_accel",
    # ── MP sub-components ──
    "abs_mom_score", "mp_adx_score", "rel_mom_score", "trend_score",
    "roc_zscore", "excess_return", "adx_val", "di_bullish",
    # ── BQ sub-components ──
    "bq_range_tight", "bq_vol_dry", "bq_base_dur", "bq_ema_conv", "bq_base_days",
    # ── Pipeline Rank sub-components ──
    "momentum_composite", "pipe_tier",
    "pr_ret_12m", "pr_adx_score", "pr_rsi_score", "pr_vol_score", "pr_ma_score",
]


def build_scores() -> None:
    if not PANEL_DAILY.exists():
        print(f"ERROR: {PANEL_DAILY} does not exist. Run build_panel.bat first.", file=sys.stderr)
        return
    panel_daily = pd.read_parquet(PANEL_DAILY)
    panel_daily["date"] = pd.to_datetime(panel_daily["date"]).dt.normalize()

    if PANEL_WEEKLY.exists():
        panel_weekly = pd.read_parquet(PANEL_WEEKLY)
        panel_weekly["date"] = pd.to_datetime(panel_weekly["date"]).dt.normalize()
    else:
        panel_weekly = pd.DataFrame()

    if SPY_DAILY.exists():
        spy_daily = pd.read_parquet(SPY_DAILY)
        spy_daily["date"] = pd.to_datetime(spy_daily["date"]).dt.normalize()
    else:
        spy_daily = panel_daily.loc[panel_daily["ticker"] == "SPY"].copy()

    daily_groups = {t: g.sort_values("date").reset_index(drop=True) for t, g in panel_daily.groupby("ticker", sort=False)}
    if not panel_weekly.empty:
        weekly_groups = {t: g.sort_values("date").reset_index(drop=True) for t, g in panel_weekly.groupby("ticker", sort=False)}
    else:
        weekly_groups = {}

    earnings_cal = load_earnings()
    if earnings_cal:
        print(f"  Earnings calendar loaded: {len(earnings_cal)} tickers")

    tickers = sorted(daily_groups.keys())
    out_rows: list[pd.DataFrame] = []
    t0 = time.monotonic()
    for ticker in iter_with_progress(tickers, label="score"):
        d = daily_groups[ticker]
        if len(d) < 60:
            continue
        w = weekly_groups.get(ticker, pd.DataFrame())

        try:
            flow_df = flow.compute(d)
            energy_df = energy.compute(d)
            mp_df = mp.compute(d, spy_daily=spy_daily)
            structure_df = structure.compute(
                d, spy_daily=spy_daily, weekly=w,
                earnings_cal=earnings_cal if earnings_cal else None,
                ticker=ticker,
            )
            elder_df = elder.compute(d)
            bq_df = bq.compute(d)
            k39_gate_s, k39_val = k39.compute_k39_gate(w, d["date"])
        except Exception as exc:
            print(f"  !! {ticker}: {exc}", file=sys.stderr)
            continue

        sc_m = scoring.compute(
            flow_score=flow_df["flow_100"],
            energy_score=energy_df["energy_100"],
            structure_score=structure_df["structure_100"],
            mp_score=mp_df["mp_score"],
            elder_score=elder_df["elder_score"],
        )

        sc_m_raw = scoring.compute_raw(
            flow_score=flow_df["flow_100"],
            energy_score=energy_df["energy_100"],
            structure_score=structure_df["structure_100"],
            mp_score=mp_df["mp_score"],
        )

        sc_p = scoring.compute_position(
            flow_score=flow_df["flow_100"],
            energy_score=energy_df["energy_100"],
            structure_score=structure_df["structure_100"],
            mp_score=mp_df["mp_score"],
            bq_score=bq_df["bq_100"],
            k39_gate=k39_gate_s,
        )

        sc_p_raw = scoring.compute_position_raw(
            flow_score=flow_df["flow_100"],
            energy_score=energy_df["energy_100"],
            structure_score=structure_df["structure_100"],
            mp_score=mp_df["mp_score"],
            bq_score=bq_df["bq_100"],
        )

        # v1.8.0 gate flags (Pine SC_M_GATES / SC_P_GATES) — qualification
        # booleans, NOT score caps. sc_momentum/sc_position above are uncapped.
        sc_m_gates = scoring.gates_momentum(
            flow_score=flow_df["flow_100"],
            energy_score=energy_df["energy_100"],
            structure_score=structure_df["structure_100"],
            mp_score=mp_df["mp_score"],
            elder_score=elder_df["elder_score"],
        )
        sc_p_gates = scoring.gates_position(
            flow_score=flow_df["flow_100"],
            energy_score=energy_df["energy_100"],
            structure_score=structure_df["structure_100"],
            mp_score=mp_df["mp_score"],
            bq_score=bq_df["bq_100"],
            k39_gate=k39_gate_s,
        )

        atr14 = atr(d["high"].astype(float), d["low"].astype(float), d["close"].astype(float), n=14)

        if len(d) >= 252:
            pr_df = pipeline_rank.compute(d)
            pr_pipe = pr_df["pipe_rank"]
            pr_fip = pr_df["fip_quality"]
            pr_fip_raw = pr_df["fip_raw"]
            pr_fip_spike = pr_df["fip_spike_excluded"]
            pr_fip_window = pr_df["fip_window_effective"]
        else:
            pr_pipe = pd.Series(np.nan, index=d.index)
            pr_fip = pd.Series(np.nan, index=d.index)
            pr_fip_raw = pd.Series(np.nan, index=d.index)
            pr_fip_spike = pd.Series(False, index=d.index)
            pr_fip_window = pd.Series(252, index=d.index, dtype=int)

        row = pd.DataFrame({
            "date": d["date"],
            "ticker": ticker,
            "close": d["close"].astype(float),
            "atr14": atr14,
            # Aggregate scores
            "flow_100": flow_df["flow_100"],
            "energy_100": energy_df["energy_100"],
            "structure_100": structure_df["structure_100"],
            "mp_100": mp_df["mp_score"],
            "elder_score": elder_df["elder_score"],
            "bq_100": bq_df["bq_100"],
            "k39_value": k39_val,
            "mp_state": mp_df["mp_state"],
            "impulse_state": elder_df["impulse_state"],
            "sc_momentum": sc_m,
            "sc_momentum_raw": sc_m_raw,
            "sc_position": sc_p,
            "sc_position_raw": sc_p_raw,
            "sc_m_gates": sc_m_gates,
            "sc_p_gates": sc_p_gates,
            "pipe_rank": pr_pipe,
            "fip_quality": pr_fip,
            "fip_raw": pr_fip_raw,
            "fip_spike_excluded": pr_fip_spike,
            "fip_window_effective": pr_fip_window,
            # Flow sub-components
            "flow_score": flow_df["flow_score"],
            "accum_score": flow_df["accum_score"],
            "volume_score": flow_df["volume_score"],
            "skew_score": flow_df["skew_score"],
            "ext_score": flow_df["ext_score"],
            "mfi": flow_df["mfi"],
            "cmf": flow_df["cmf"],
            "ha_quality_count": flow_df["ha_quality_count"],
            # Energy sub-components
            "vp_position_score": energy_df["vp_position_score"],
            "price_action_score": energy_df["price_action_score"],
            "squeeze_score": energy_df["squeeze_score"],
            "exhaustion_score": energy_df["exhaustion_score"],
            "atr_score": energy_df["atr_score"],
            "en_pos50": energy_df["en_pos50"],
            "en_trend_bars": energy_df["en_trend_bars"],
            # Structure sub-components
            "rs_spy_score": structure_df["rs_spy_score"],
            "rs_accel_score": structure_df["rs_accel_score"],
            "base_score": structure_df["base_score"],
            "ms_pos_score": structure_df["ms_pos_score"],
            "resist_score": structure_df["resist_score"],
            "wk_score": structure_df["wk_score"],
            "earn_score": structure_df["earn_score"],
            "base_days": structure_df["base_days"],
            "bd_mode": structure_df["bd_mode"],
            "ms_p50": structure_df["ms_p50"],
            "rs_vs_spy": structure_df["rs_vs_spy"],
            "rs_accel": structure_df["rs_accel"],
            # MP sub-components
            "abs_mom_score": mp_df["abs_mom_score"],
            "mp_adx_score": mp_df["adx_score"],
            "rel_mom_score": mp_df["rel_mom_score"],
            "trend_score": mp_df["trend_score"],
            "roc_zscore": mp_df["roc_zscore"],
            "excess_return": mp_df["excess_return"],
            "adx_val": mp_df["adx_val"],
            "di_bullish": mp_df["di_bullish"],
            # BQ sub-components
            "bq_range_tight": bq_df["bq_range_tight"],
            "bq_vol_dry": bq_df["bq_vol_dry"],
            "bq_base_dur": bq_df["bq_base_dur"],
            "bq_ema_conv": bq_df["bq_ema_conv"],
            "bq_base_days": bq_df["bq_base_days"],
            # Pipeline Rank sub-components
            "momentum_composite": pr_df["momentum_composite"] if len(d) >= 252 else np.nan,
            "pipe_tier": pr_df["pipe_tier"] if len(d) >= 252 else "",
            "pr_ret_12m": pr_df["ret_12m_score"] if len(d) >= 252 else np.nan,
            "pr_adx_score": pr_df["adx_score"] if len(d) >= 252 else np.nan,
            "pr_rsi_score": pr_df["rsi_score"] if len(d) >= 252 else np.nan,
            "pr_vol_score": pr_df["vol_score"] if len(d) >= 252 else np.nan,
            "pr_ma_score": pr_df["ma_score"] if len(d) >= 252 else np.nan,
        })
        out_rows.append(row[SCORE_COLUMNS])

    if not out_rows:
        print("No scores produced. Aborting.", file=sys.stderr)
        return

    out = pd.concat(out_rows, ignore_index=True)
    out = out.dropna(subset=["sc_momentum"]).reset_index(drop=True)
    out.to_parquet(SCORES_DAILY, index=False)

    elapsed = time.monotonic() - t0
    print(
        f"Wrote {SCORES_DAILY.name}: {len(out):,} rows across "
        f"{out['ticker'].nunique()} tickers in {elapsed:.1f}s"
    )


if __name__ == "__main__":
    build_scores()
