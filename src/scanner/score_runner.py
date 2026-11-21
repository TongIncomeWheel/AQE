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

import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.earnings import load_earnings, load_earnings_dates_full
from src.data.fmp_client import iter_with_progress
from src.data.paths import DATA_DIR, PANEL_DAILY, PANEL_WEEKLY, SCORES_DAILY, SPY_DAILY
from src.engines import anchored_vwap, bq, divergence, elder, energy, flow, health, k39, liquidity_sweep, mp, order_flow, pin_bar, pipeline_rank, price_volume_profile, readiness, scoring, smart_money_knn, squeeze_breakout, structure, vwap
from src.engines.utils import atr, spy_positional_misaligned_bars as U_spy_misaligned


# A FULL build (every scored ticker, all history) used to hold every ticker's frame in one Python list and pd.concat them: ~1.5 KB/row x ~3.2M rows = ~5 GB
# of frames plus the concat copy, which killed the hosted runner ("lost communication", run 44904664034) once the shadow v2 columns widened the frame. A full
# build now scores in chunks of SCORE_CHUNK_TICKERS, writes each chunk to a part file and streams the parts into ONE scores_daily.parquet (same columns, same
# values, same row order); peak memory is one chunk, not the universe. A targeted build (only_tickers) is small and keeps the in-memory upsert.
SCORE_CHUNK_TICKERS = int(os.environ.get("AQE_SCORE_CHUNK_TICKERS", "150"))


def _write_chunk(frames: list, parts_dir: Path, n: int):
    """Concat one chunk, drop rows with no sc_momentum (as the single-frame build did), write it as part n. Returns (rows, tickers) written."""
    chunk = pd.concat(frames, ignore_index=True).dropna(subset=["sc_momentum"]).reset_index(drop=True)
    if chunk.empty:
        return 0, set()
    parts_dir.mkdir(parents=True, exist_ok=True)
    chunk.to_parquet(parts_dir / f"part_{n:05d}.parquet", index=False)
    return len(chunk), set(chunk["ticker"].unique())


def _combine_parts(parts_dir: Path, dest: Path) -> None:
    """Stream the part files into one parquet at `dest`, one part in memory at a time. The result replaces `dest` atomically (a crash mid-combine leaves the
    previous scores_daily.parquet untouched). Schemas are unified (a column that was all-null in one chunk promotes to its real type)."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    parts = sorted(parts_dir.glob("part_*.parquet"))
    schemas = [pq.read_schema(p) for p in parts]
    try:
        unified = pa.unify_schemas(schemas, promote_options="permissive")
    except TypeError:                           # pyarrow < 14 has no promote_options (null promotes by default there)
        unified = pa.unify_schemas(schemas)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with pq.ParquetWriter(tmp, unified) as w:
            for p in parts:
                w.write_table(pq.read_table(p).cast(unified))
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()


SCORE_COLUMNS = [
    "date", "ticker",
    "close", "atr14",
    # ── Aggregate scores ──
    "flow_100", "energy_100", "structure_100", "mp_100", "elder_score",
    "bq_100", "k39_value", "k39_gate",
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
    # ── Readiness sub-components ──
    "rd_score", "rd_state", "rd_compression", "rd_trigger", "rd_pos_mod", "rd_rs_bonus",
    "rd_inside_bars", "rd_range_exp", "rd_vol_surge", "rd_close_str",
    # ── Health sub-components ──
    "hl_score", "hl_state", "hl_trend", "hl_flow", "hl_rs", "hl_risk",
    "hl_higher_lows", "hl_trend_bars", "hl_vol_updn", "hl_atr_spike",
    # ── Momentum acceleration (additive, MP engine) ──
    "mp_accel", "mp_accel_state",
    # ── Divergence (price vs RSI/MFI/CMF/MACD/OBV — last bar only) ──
    "div_state", "div_bull_count", "div_bear_count", "div_oscs", "div_date",
    # ── Pin Bar / Inside Bar pattern (last bar only) ──
    "pin_bar_state", "pin_bar_date", "pin_bar_level", "inside_bar", "pib_pattern",
    # ── Smart Money kNN — CHoCH + instance-based learning (last bar only) ──
    "choch_state", "choch_date", "knn_prob", "knn_threshold_clear",
    "knn_neighbors_used", "knn_tp1", "knn_tp2", "knn_tp3",
    # ── Squeeze Breakout + Volume (last bar only) ──
    "squeeze_breakout_state", "squeeze_breakout_date",
    "squeeze_breakout_volume_confirmed", "was_squeezed",
    # ── Rolling 14-day VWAP (last bar only) ──
    "vwap_14d", "vwap_14d_position",
    # ── Anchored VWAP — structure pivot + swing low (last bar only) ──
    "avwap_structure", "avwap_structure_date", "avwap_structure_position",
    "avwap_structure_bars", "avwap_swing", "avwap_swing_date",
    "avwap_swing_position", "avwap_swing_bars",
    # ── Price volume profile — POC + value area (last bar only) ──
    "pvp_poc", "pvp_vah", "pvp_val", "pvp_position", "pvp_bars_used",
    # ── Order-flow / tape-reading proxy (last bar only) ──
    "of_state", "of_pressure", "of_date", "of_rvol",
    # ── Liquidity sweep / stop run (last bar only) ──
    "ls_state", "ls_level", "ls_date", "ls_volume_confirmed",
    # ── SHADOW v2 (research-review 2026-11-21; PM: "Fix the indicator calculations", shipped as shadow fields) ──
    # Same pass, beside the live fields, which stay untouched. Nothing reads these in the export, the gates or the alerts: the PM decides any cutover
    # after a side-by-side. Added at the END so the section slices in research_extract._component_columns are unchanged.
    "ret_12m_pct_v2", "pr_ret_12m_v2", "pr_adx_score_v2", "momentum_composite_v2",
    "fip_quality_v2", "fip_raw_v2", "fip_spike_excluded_v2", "pipe_rank_v2", "pipe_tier_v2",
    "sc_momentum_v2", "sc_position_v2", "sc_m_gates_v2", "sc_p_gates_v2",
    "mp_score_v2", "abs_mom_score_v2", "rel_mom_score_v2", "rs_spy_score_v2", "rs_accel_score_v2", "wk_score_v2", "earn_score_v2",
    "rd_score_v2", "rd_rs_bonus_v2", "hl_score_v2", "hl_rs_v2", "hl_trend_v2", "k39_gate_v2", "k39_value_v2",
    "bq_100_v2", "bq_base_dur_v2", "bq_base_days_v2",
    "resist_score_v2", "structure_100_v2", "elder_score_v2", "hist_score_v2", "base_days_v2", "base_score_v2",
    "flow_100_v2", "flow_score_v2", "accum_score_v2", "atr_score_v2", "energy_100_v2",
]


def scoreable_tickers(panel_tickers, *, scan_universe, basket_constituents,
                      held_tickers=()) -> list[str]:
    """Which tickers in the panel actually get scored, sorted.

    Score the scan universe only. Thematic-basket constituents that aren't in
    the scan universe live in the panel purely for SECTOR grading — they must
    never reach a screen (longlist / watchlist / edge), so keep them out of
    the score cache (Thematic Basket Map v2.0: baskets don't add scan names).

    A held position is the one exception: it must NEVER be excluded here just
    because it also happens to be a thematic-basket constituent outside the
    scan universe — that would directly contradict panel_builder.py's own
    promise ("as long as we have the ticker, we can source this" for held
    names). Found 2026-08-21: GOLD and JPM, both held and both basket-only,
    silently scored as fully null in the export with no warning anywhere in
    the pipeline.
    """
    basket_only = (set(basket_constituents) - set(scan_universe)) - set(held_tickers)
    return sorted(t for t in panel_tickers if t not in basket_only)


def build_scores(only_tickers: list[str] | None = None) -> None:
    """Score the panel and write scores_daily.parquet.

    only_tickers=None (default, used by the full daily pipeline): score
    everything in the panel, replacing the whole file — unchanged behavior.

    only_tickers=[...]: score ONLY the given tickers and MERGE the result
    into the existing file (upsert by ticker — every other ticker's cached
    rows are left untouched). Every engine call in the scoring loop below
    operates on one ticker's own daily/weekly frame plus spy_daily; nothing
    here compares tickers to each other, so there is no correctness reason a
    targeted refresh needs to re-touch the other ~800 cached tickers. Added
    2026-08-21 for src/pipeline/refresh_held.py, which was re-scoring the
    entire cached universe just to refresh a dozen held names — correct, but
    far slower than "held book only" implies.
    """
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
    earn_full = load_earnings_dates_full()      # shadow v2 (items 12/13): historical report dates; {} -> earn_score_v2 is NaN everywhere (counted in the diagnostics)
    diag = {"tickers_scored": 0, "bars": 0, "spy_misaligned_tickers": 0, "spy_misaligned_bars": 0, "earn_dates_tickers": len(earn_full),
            "tickers_without_earn_dates": 0, "nan_v2_bars": {}}
    if earnings_cal:
        print(f"  Earnings calendar loaded: {len(earnings_cal)} tickers")

    from src.engines.srm import BASKET_CONSTITUENTS
    from src.data.universe import load_universe
    from src.valen import baskets as _vb
    try:
        from src.data.ptj import load_held_positions
        _held_tickers = {p.get("ticker") for p in load_held_positions()
                         if p.get("ticker") and p.get("type", "STK") == "STK"}
    except Exception:  # noqa: BLE001
        _held_tickers = set()
    tickers = scoreable_tickers(
        daily_groups.keys(), scan_universe=load_universe(include_benchmark=True),
        basket_constituents=set(BASKET_CONSTITUENTS) | _vb.context_only(), held_tickers=_held_tickers)
    if only_tickers is not None:
        _want = set(only_tickers)
        tickers = [t for t in tickers if t in _want]
    out_rows: list[pd.DataFrame] = []
    chunked = only_tickers is None                      # full build streams to disk; a targeted build upserts in memory
    parts_dir = SCORES_DAILY.with_name(SCORES_DAILY.stem + ".parts")
    if parts_dir.exists():
        shutil.rmtree(parts_dir)                         # stale parts from a crashed earlier build must never leak into this one
    n_parts, n_rows, seen = 0, 0, set()
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
                ticker=ticker, earn_dates_full=earn_full,
            )
            elder_df = elder.compute(d)
            bq_df = bq.compute(d)
            k39_gate_s, k39_val = k39.compute_k39_gate(w, d["date"])
            k39_gate_v2_s, k39_val_v2 = k39.compute_k39_gate(w, d["date"], week_complete=True)   # shadow v2 (item 18)
            rd_df = readiness.compute(d, spy_daily=spy_daily)
            hl_df = health.compute(d, spy_daily=spy_daily, weekly=w if not w.empty else None)
            # Divergence is a LAST-BAR read (non-repainting, freshness-gated);
            # persisted on the latest row only, NaN/None for history.
            div = divergence.compute_divergence(d)
            # Pin bar / inside bar is also a LAST-BAR read (pure geometry).
            pb = pin_bar.compute_pin_bar(d)
            # Smart Money CHoCH + kNN — also a LAST-BAR read (the latest CHoCH,
            # scored against the ticker's own historical CHoCH events).
            sm = smart_money_knn.compute_smart_money(d)
            # Squeeze breakout + volume, and rolling 14D VWAP — both LAST-BAR reads.
            sb = squeeze_breakout.compute_squeeze_breakout(d)
            vw = vwap.compute_vwap(d, length=14)
            avw = anchored_vwap.compute_anchored_vwap(d)
            pvp = price_volume_profile.compute_price_volume_profile(d)
            of = order_flow.compute_order_flow(d)
            ls = liquidity_sweep.compute_liquidity_sweep(d)
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

        # Shadow v2 composites (same weights and gates as the live ones, fed ONLY the v2 parts; a NaN part gives a NaN composite, never points).
        sc_m_v2 = scoring.compute(flow_df["flow_100_v2"], energy_df["energy_100_v2"], structure_df["structure_100_v2"], mp_df["mp_score_v2"], elder_df["elder_score_v2"])
        sc_p_v2 = scoring.compute_position(flow_df["flow_100_v2"], energy_df["energy_100_v2"], structure_df["structure_100_v2"], mp_df["mp_score_v2"],
                                           bq_df["bq_100_v2"], k39_gate_v2_s)
        sc_m_gates_v2 = scoring.gates_momentum(flow_df["flow_100_v2"], energy_df["energy_100_v2"], structure_df["structure_100_v2"], mp_df["mp_score_v2"],
                                               elder_df["elder_score_v2"])
        sc_p_gates_v2 = scoring.gates_position(flow_df["flow_100_v2"], energy_df["energy_100_v2"], structure_df["structure_100_v2"], mp_df["mp_score_v2"],
                                               bq_df["bq_100_v2"], k39_gate_v2_s)

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
            "flow_100_v2": flow_df["flow_100_v2"],               # shadow v2 (Flow items 1-3; Pine spec change, PM sign-off)
            "flow_score_v2": flow_df["flow_score_v2"],
            "accum_score_v2": flow_df["accum_score_v2"],
            "atr_score_v2": energy_df["atr_score_v2"],           # shadow v2 (Energy item 16; Pine spec change, PM sign-off)
            "energy_100_v2": energy_df["energy_100_v2"],
            "energy_100": energy_df["energy_100"],
            "structure_100": structure_df["structure_100"],
            "mp_100": mp_df["mp_score"],
            "elder_score": elder_df["elder_score"],
            "elder_score_v2": elder_df["elder_score_v2"],      # shadow v2 (item 15)
            "hist_score_v2": elder_df["hist_score_v2"],
            "bq_100": bq_df["bq_100"],
            "k39_value": k39_val,
            "k39_gate": k39_gate_s,          # weekly gate bool → SC_POSITION gate detail
            "sc_momentum_v2": sc_m_v2,                           # shadow v2 composites
            "sc_position_v2": sc_p_v2,
            "sc_m_gates_v2": sc_m_gates_v2,
            "sc_p_gates_v2": sc_p_gates_v2,
            "mp_score_v2": mp_df["mp_score_v2"],                 # shadow v2 (items 12, 14, 18, 13)
            "abs_mom_score_v2": mp_df["abs_mom_score_v2"],
            "rel_mom_score_v2": mp_df["rel_mom_score_v2"],
            "rs_spy_score_v2": structure_df["rs_spy_score_v2"],
            "rs_accel_score_v2": structure_df["rs_accel_score_v2"],
            "wk_score_v2": structure_df["wk_score_v2"],
            "earn_score_v2": structure_df["earn_score_v2"],
            "rd_score_v2": rd_df["rd_score_v2"],
            "rd_rs_bonus_v2": rd_df["rd_rs_bonus_v2"],
            "hl_score_v2": hl_df["hl_score_v2"],
            "hl_rs_v2": hl_df["hl_rs_v2"],
            "hl_trend_v2": hl_df["hl_trend_v2"],
            "k39_gate_v2": k39_gate_v2_s,
            "k39_value_v2": k39_val_v2,
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
            # Shadow v2 (Structure: item 11)
            "resist_score_v2": structure_df["resist_score_v2"],
            "base_days_v2": structure_df["base_days_v2"],         # item 10 (Pine spec change: PM sign-off)
            "base_score_v2": structure_df["base_score_v2"],
            "structure_100_v2": structure_df["structure_100_v2"],
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
            # Shadow v2 (BQ: items 7, 9)
            "bq_100_v2": bq_df["bq_100_v2"],
            "bq_base_dur_v2": bq_df["bq_base_dur_v2"],
            "bq_base_days_v2": bq_df["bq_base_days_v2"],
            # Pipeline Rank sub-components
            "momentum_composite": pr_df["momentum_composite"] if len(d) >= 252 else np.nan,
            "pipe_tier": pr_df["pipe_tier"] if len(d) >= 252 else "",
            "pr_ret_12m": pr_df["ret_12m_score"] if len(d) >= 252 else np.nan,
            "pr_adx_score": pr_df["adx_score"] if len(d) >= 252 else np.nan,
            "pr_rsi_score": pr_df["rsi_score"] if len(d) >= 252 else np.nan,
            "pr_vol_score": pr_df["vol_score"] if len(d) >= 252 else np.nan,
            "pr_ma_score": pr_df["ma_score"] if len(d) >= 252 else np.nan,
            # Shadow v2 (Pipeline Rank: items 4, 5, 6)
            "ret_12m_pct_v2": pr_df["ret_12m_pct_v2"] if len(d) >= 252 else np.nan,
            "pr_ret_12m_v2": pr_df["ret_12m_score_v2"] if len(d) >= 252 else np.nan,
            "pr_adx_score_v2": pr_df["adx_score_v2"] if len(d) >= 252 else np.nan,
            "momentum_composite_v2": pr_df["momentum_composite_v2"] if len(d) >= 252 else np.nan,
            "fip_quality_v2": pr_df["fip_quality_v2"] if len(d) >= 252 else np.nan,
            "fip_raw_v2": pr_df["fip_raw_v2"] if len(d) >= 252 else np.nan,
            "fip_spike_excluded_v2": pr_df["fip_spike_excluded_v2"] if len(d) >= 252 else False,
            "pipe_rank_v2": pr_df["pipe_rank_v2"] if len(d) >= 252 else np.nan,
            "pipe_tier_v2": pr_df["pipe_tier_v2"] if len(d) >= 252 else "",
            # Readiness sub-components
            "rd_score": rd_df["rd_score"],
            "rd_state": rd_df["rd_state"],
            "rd_compression": rd_df["rd_compression"],
            "rd_trigger": rd_df["rd_trigger"],
            "rd_pos_mod": rd_df["rd_pos_mod"],
            "rd_rs_bonus": rd_df["rd_rs_bonus"],
            "rd_inside_bars": rd_df["rd_inside_bars"],
            "rd_range_exp": rd_df["rd_range_exp"],
            "rd_vol_surge": rd_df["rd_vol_surge"],
            "rd_close_str": rd_df["rd_close_str"],
            # Health sub-components
            "hl_score": hl_df["hl_score"],
            "hl_state": hl_df["hl_state"],
            "hl_trend": hl_df["hl_trend"],
            "hl_flow": hl_df["hl_flow"],
            "hl_rs": hl_df["hl_rs"],
            "hl_risk": hl_df["hl_risk"],
            "hl_higher_lows": hl_df["hl_higher_lows"],
            "hl_trend_bars": hl_df["hl_trend_bars"],
            "hl_vol_updn": hl_df["hl_vol_updn"],
            "hl_atr_spike": hl_df["hl_atr_spike"],
            # Momentum acceleration (full series from the MP engine)
            "mp_accel": mp_df["mp_accel"],
            "mp_accel_state": mp_df["mp_accel_state"],
        })
        # Divergence — LAST BAR ONLY (the engine reads the trailing window at the
        # latest close; history rows carry NaN/None = "not computed", honest).
        _last_ix = row.index[-1]
        row["div_state"] = None
        row["div_oscs"] = None
        row["div_date"] = None
        row["div_bull_count"] = np.nan
        row["div_bear_count"] = np.nan
        row.loc[_last_ix, "div_state"] = div["div_state"]
        row.loc[_last_ix, "div_oscs"] = div["div_oscs"]
        row.loc[_last_ix, "div_date"] = div["div_date"]
        row.loc[_last_ix, "div_bull_count"] = float(div["div_bull_count"])
        row.loc[_last_ix, "div_bear_count"] = float(div["div_bear_count"])
        # Pin bar / inside bar — LAST BAR ONLY (pure geometry on the most recent
        # closed candle; history rows carry NaN/None = "not computed").
        row["pin_bar_state"] = None
        row["pin_bar_date"] = None
        row["pin_bar_level"] = np.nan
        row["inside_bar"] = None
        row["pib_pattern"] = None
        row.loc[_last_ix, "pin_bar_state"] = pb["pin_bar_state"]
        row.loc[_last_ix, "pin_bar_date"] = pb["pin_bar_date"]
        row.loc[_last_ix, "pin_bar_level"] = (
            float(pb["pin_bar_level"]) if pb["pin_bar_level"] is not None else np.nan)
        row.loc[_last_ix, "inside_bar"] = pb["inside_bar"]
        row.loc[_last_ix, "pib_pattern"] = pb["pib_pattern"]
        # Smart Money kNN — LAST BAR ONLY (the latest CHoCH + its neighbor score).
        row["choch_state"] = None
        row["choch_date"] = None
        row["knn_prob"] = np.nan
        row["knn_threshold_clear"] = None
        row["knn_neighbors_used"] = np.nan
        row["knn_tp1"] = np.nan
        row["knn_tp2"] = np.nan
        row["knn_tp3"] = np.nan
        row.loc[_last_ix, "choch_state"] = sm["choch_state"]
        row.loc[_last_ix, "choch_date"] = sm["choch_date"]
        row.loc[_last_ix, "knn_prob"] = (
            float(sm["knn_prob"]) if sm["knn_prob"] is not None else np.nan)
        row.loc[_last_ix, "knn_threshold_clear"] = sm["knn_threshold_clear"]
        row.loc[_last_ix, "knn_neighbors_used"] = float(sm["knn_neighbors_used"])
        row.loc[_last_ix, "knn_tp1"] = (
            float(sm["tp1"]) if sm["tp1"] is not None else np.nan)
        row.loc[_last_ix, "knn_tp2"] = (
            float(sm["tp2"]) if sm["tp2"] is not None else np.nan)
        row.loc[_last_ix, "knn_tp3"] = (
            float(sm["tp3"]) if sm["tp3"] is not None else np.nan)
        # Squeeze breakout — LAST BAR ONLY.
        row["squeeze_breakout_state"] = None
        row["squeeze_breakout_date"] = None
        row["squeeze_breakout_volume_confirmed"] = None
        row["was_squeezed"] = None
        row.loc[_last_ix, "squeeze_breakout_state"] = sb["squeeze_breakout_state"]
        row.loc[_last_ix, "squeeze_breakout_date"] = sb["squeeze_breakout_date"]
        row.loc[_last_ix, "squeeze_breakout_volume_confirmed"] = sb["squeeze_breakout_volume_confirmed"]
        row.loc[_last_ix, "was_squeezed"] = sb["was_squeezed"]
        # Rolling 14D VWAP — LAST BAR ONLY.
        row["vwap_14d"] = np.nan
        row["vwap_14d_position"] = None
        row.loc[_last_ix, "vwap_14d"] = (
            float(vw["vwap_14d"]) if vw["vwap_14d"] is not None else np.nan)
        row.loc[_last_ix, "vwap_14d_position"] = vw["vwap_14d_position"]
        # Anchored VWAP (structure pivot + swing low) — LAST BAR ONLY.
        row["avwap_structure"] = np.nan
        row["avwap_structure_date"] = None
        row["avwap_structure_position"] = None
        row["avwap_structure_bars"] = np.nan
        row["avwap_swing"] = np.nan
        row["avwap_swing_date"] = None
        row["avwap_swing_position"] = None
        row["avwap_swing_bars"] = np.nan
        row.loc[_last_ix, "avwap_structure"] = (
            float(avw["avwap_structure"]) if avw["avwap_structure"] is not None else np.nan)
        row.loc[_last_ix, "avwap_structure_date"] = avw["avwap_structure_date"]
        row.loc[_last_ix, "avwap_structure_position"] = avw["avwap_structure_position"]
        row.loc[_last_ix, "avwap_structure_bars"] = (
            float(avw["avwap_structure_bars"]) if avw["avwap_structure_bars"] is not None else np.nan)
        row.loc[_last_ix, "avwap_swing"] = (
            float(avw["avwap_swing"]) if avw["avwap_swing"] is not None else np.nan)
        row.loc[_last_ix, "avwap_swing_date"] = avw["avwap_swing_date"]
        row.loc[_last_ix, "avwap_swing_position"] = avw["avwap_swing_position"]
        row.loc[_last_ix, "avwap_swing_bars"] = (
            float(avw["avwap_swing_bars"]) if avw["avwap_swing_bars"] is not None else np.nan)
        # Classic price-level volume profile (POC + value area) — LAST BAR ONLY.
        row["pvp_poc"] = np.nan
        row["pvp_vah"] = np.nan
        row["pvp_val"] = np.nan
        row["pvp_position"] = None
        row["pvp_bars_used"] = np.nan
        row.loc[_last_ix, "pvp_poc"] = (
            float(pvp["pvp_poc"]) if pvp["pvp_poc"] is not None else np.nan)
        row.loc[_last_ix, "pvp_vah"] = (
            float(pvp["pvp_vah"]) if pvp["pvp_vah"] is not None else np.nan)
        row.loc[_last_ix, "pvp_val"] = (
            float(pvp["pvp_val"]) if pvp["pvp_val"] is not None else np.nan)
        row.loc[_last_ix, "pvp_position"] = pvp["pvp_position"]
        row.loc[_last_ix, "pvp_bars_used"] = (
            float(pvp["pvp_bars_used"]) if pvp["pvp_bars_used"] is not None else np.nan)
        # Order-flow / tape-reading PROXY (OHLCV-derived, never real tape) —
        # LAST BAR ONLY.
        row["of_state"] = None
        row["of_pressure"] = np.nan
        row["of_date"] = None
        row["of_rvol"] = np.nan
        row.loc[_last_ix, "of_state"] = of["of_state"]
        row.loc[_last_ix, "of_pressure"] = (
            float(of["of_pressure"]) if of["of_pressure"] is not None else np.nan)
        row.loc[_last_ix, "of_date"] = of["of_date"]
        row.loc[_last_ix, "of_rvol"] = (
            float(of["of_rvol"]) if of["of_rvol"] is not None else np.nan)
        # Liquidity sweep ("stop run") detection — LAST BAR ONLY.
        row["ls_state"] = None
        row["ls_level"] = np.nan
        row["ls_date"] = None
        row["ls_volume_confirmed"] = None
        row.loc[_last_ix, "ls_state"] = ls["ls_state"]
        row.loc[_last_ix, "ls_level"] = (
            float(ls["ls_level"]) if ls["ls_level"] is not None else np.nan)
        row.loc[_last_ix, "ls_date"] = ls["ls_date"]
        row.loc[_last_ix, "ls_volume_confirmed"] = ls["ls_volume_confirmed"]
        # Shadow v2 diagnostics (items 12/13/14): how many bars / tickers the live defaults and the positional SPY alignment touched.
        _mis = U_spy_misaligned(d["date"], spy_daily)
        diag["tickers_scored"] += 1
        diag["bars"] += int(len(row))
        diag["spy_misaligned_bars"] += _mis
        diag["spy_misaligned_tickers"] += int(_mis > 0)
        diag["tickers_without_earn_dates"] += int(not earn_full.get(ticker))
        _warm = row["structure_100"].notna()
        for _c in ("wk_score_v2", "earn_score_v2", "rs_spy_score_v2", "rs_accel_score_v2", "abs_mom_score_v2", "rel_mom_score_v2"):
            diag["nan_v2_bars"][_c] = diag["nan_v2_bars"].get(_c, 0) + int((row[_c].isna() & _warm).sum())
        out_rows.append(row[SCORE_COLUMNS])
        if chunked and len(out_rows) >= SCORE_CHUNK_TICKERS:
            _r, _t = _write_chunk(out_rows, parts_dir, n_parts)
            n_parts, n_rows = n_parts + 1, n_rows + _r
            seen |= _t
            out_rows.clear()

    if chunked and out_rows:
        _r, _t = _write_chunk(out_rows, parts_dir, n_parts)
        n_parts, n_rows = n_parts + 1, n_rows + _r
        seen |= _t
        out_rows.clear()
    if not out_rows and not (chunked and n_rows):
        print("No scores produced. Aborting.", file=sys.stderr)
        shutil.rmtree(parts_dir, ignore_errors=True)
        return

    if chunked:
        try:
            _combine_parts(parts_dir, SCORES_DAILY)
        finally:
            shutil.rmtree(parts_dir, ignore_errors=True)
        out = None
    else:
        out = pd.concat(out_rows, ignore_index=True)
        out = out.dropna(subset=["sc_momentum"]).reset_index(drop=True)

    if out is not None and only_tickers is not None and SCORES_DAILY.exists():
        # Upsert: keep every cached ticker NOT in this targeted run untouched,
        # replace the ones we just recomputed.
        prior = pd.read_parquet(SCORES_DAILY)
        prior = prior[~prior["ticker"].isin(set(out["ticker"]))]
        out = pd.concat([prior, out], ignore_index=True)

    if out is not None:
        out.to_parquet(SCORES_DAILY, index=False)
    try:        # shadow v2 diagnostics (research review items 12/13/14): a small side file, never read by the pipeline
        import json as _json
        diag["scope"] = "targeted" if only_tickers is not None else "full"
        diag["generated_at"] = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
        SCORES_DAILY.with_name("score_diagnostics_v2.json").write_text(_json.dumps(diag, indent=1), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"  (score diagnostics not written: {exc})", file=sys.stderr)

    elapsed = time.monotonic() - t0
    scope = f" ({len(only_tickers)} requested)" if only_tickers is not None else ""
    _rows, _tick = (n_rows, len(seen)) if out is None else (len(out), out["ticker"].nunique())
    print(
        f"Wrote {SCORES_DAILY.name}: {_rows:,} rows across "
        f"{_tick} tickers in {elapsed:.1f}s{scope}"
    )


if __name__ == "__main__":
    build_scores()
