"""Ad-hoc ticker scorer — score tickers on demand, beyond the cached universe.

The Scanner page's "Ad-hoc Ticker Scorer" section calls score_tickers() to
fetch fresh daily bars from FMP for up to 10 user-entered tickers and run the
full AQE engine suite + composites + Pipeline Rank + trade levels + Elder
history -- the same engines the daily pipeline uses.

Results are display-only: nothing is written to the universe or the score
cache. Tickers already in the universe can be scored too; this exists for
checking names that are not.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.data.earnings import load_earnings
from src.data.fmp_client import FMPClient, FMPError, resample_to_weekly
from src.data.panel_builder import SPY_DAILY
from src.engines import (bq, divergence, elder, energy, flow, health, k39, mp,
                         pin_bar, pipeline_rank, scoring, smart_money_knn, structure)
from src.engines.bracket_engine import compute_bracket, stamp_bracket_volume
from src.engines.elder_context import compute_elder_context, elder_pattern
from src.engines.scoring import SC_M_GATES
from src.engines.utils import atr
from src.scanner.betas import betas_for_ticker
from src.scanner.levels import ELDER_HISTORY_DAYS, levels_for_ticker

MAX_TICKERS = 10
MIN_BARS = 60                     # engines need >= 60 daily bars
PIPE_RANK_MIN_BARS = 252          # Pipeline Rank needs >= 252 daily bars

# History fetched per ticker. The longest engine input is Pipeline Rank's
# 252-bar FIP window plus its EMA(200); every other engine looks back <= 120
# bars. ~3 years (~750 bars) clears the 252-bar window with margin and fully
# warms the 200-EMA (its seed weight decays to ~0.05%) -- more history would
# not change the latest-bar score. The scorer only needs that latest bar.
HISTORY_YEARS = 3


def _load_spy() -> pd.DataFrame | None:
    if not SPY_DAILY.exists():
        return None
    spy = pd.read_parquet(SPY_DAILY)
    spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()
    return spy


def score_tickers(tickers: list[str]) -> list[dict]:
    """Fetch + score up to MAX_TICKERS ad-hoc tickers.

    Returns one dict per ticker, in input order. A successful result carries
    engine scores, composites, gate status, Elder 5-day history and trade
    levels; a failure carries {'ticker', 'error'}.
    """
    seen: list[str] = []
    for t in tickers:
        t = (t or "").strip().upper()
        if t and t not in seen:
            seen.append(t)
    tickers = seen[:MAX_TICKERS]
    if not tickers:
        return []

    spy = _load_spy()
    if spy is None:
        return [{"ticker": t, "error": "SPY price cache missing -- rebuild prices first."}
                for t in tickers]

    try:
        client = FMPClient()
    except FMPError as exc:
        return [{"ticker": t, "error": str(exc)} for t in tickers]

    earnings_cal = load_earnings() or None
    today = date.today()
    from_dt = today - timedelta(days=int(HISTORY_YEARS * 365.25))

    return [_score_one(t, client, spy, earnings_cal, from_dt, today) for t in tickers]


def _sma(close: pd.Series, n: int) -> float | None:
    return round(float(close.tail(n).mean()), 2) if len(close) >= n else None


def _panel_metrics(d: pd.DataFrame, spy: pd.DataFrame) -> dict:
    """Bar-derived fields the longlist rows carry but the engines don't emit:
    day_vol (was RVOL), RS vs SPY (20d), SMA-50 distance, MA ladder, 30d vol,
    252d beta. Each degrades to None on thin data — never raises.
    """
    out: dict = {"day_vol": None, "rs_spy_20d": None, "sma_distance_pct": None,
                 "ma": {}, "vol_30d_ann": None, "beta_252d": None}
    try:
        close = d["close"].astype(float)
        out["ma"] = {w: _sma(close, w) for w in (20, 50, 100, 200)
                     if _sma(close, w) is not None}
        sma50 = _sma(close, 50)
        if sma50:
            out["sma_distance_pct"] = round(
                (float(close.iloc[-1]) - sma50) / sma50 * 100, 1)
        if "volume" in d.columns and len(d) >= 20:
            vol = d["volume"].astype(float)
            avg20 = float(vol.tail(20).mean())
            if avg20 > 0:
                out["day_vol"] = round(float(vol.iloc[-1]) / avg20, 2)
        lr = np.log(close / close.shift(1)).dropna()
        if len(lr) >= 30:
            out["vol_30d_ann"] = round(float(lr.tail(30).std()) * float(np.sqrt(252)) * 100, 1)

        m = pd.merge(
            d[["date", "close"]].rename(columns={"close": "c_tk"}),
            spy[["date", "close"]].rename(columns={"close": "c_spy"}),
            on="date", how="inner").sort_values("date")
        if len(m) >= 21:
            tk20 = float(m["c_tk"].iloc[-1] / m["c_tk"].iloc[-21] - 1) * 100
            sp20 = float(m["c_spy"].iloc[-1] / m["c_spy"].iloc[-21] - 1) * 100
            out["rs_spy_20d"] = round(tk20 - sp20, 1)
        if len(m) >= 60:
            rt = np.log(m["c_tk"] / m["c_tk"].shift(1)).dropna().to_numpy()
            rs = np.log(m["c_spy"] / m["c_spy"].shift(1)).dropna().to_numpy()
            n = min(len(rt), len(rs), 252)
            rt, rs = rt[-n:], rs[-n:]
            var = float(np.var(rs))
            if var > 0:
                out["beta_252d"] = round(float(np.cov(rt, rs)[0, 1] / var), 2)
    except Exception:  # noqa: BLE001 — metrics are best-effort enrichment
        pass
    return out


def _last(series) -> float | None:
    """Latest finite value of a series, or None."""
    try:
        v = float(series.iloc[-1])
        return v if v == v else None      # NaN -> None
    except (IndexError, ValueError, TypeError):
        return None


def _score_one(ticker, client, spy, earnings_cal, from_dt, today) -> dict:
    # 1. Fetch daily bars from FMP.
    try:
        d = client.get_daily_bars(ticker, from_date=from_dt, to_date=today)
    except FMPError as exc:
        return {"ticker": ticker, "error": f"FMP: {exc}"}
    if d is None or d.empty:
        return {"ticker": ticker, "error": "no price data returned (check the symbol)."}
    if len(d) < MIN_BARS:
        return {"ticker": ticker, "error": f"only {len(d)} bars -- need {MIN_BARS}+ to score."}

    d = d.reset_index(drop=True)
    w = resample_to_weekly(d)

    # 2. Run the engine suite + composites.
    try:
        flow_df = flow.compute(d)
        energy_df = energy.compute(d)
        mp_df = mp.compute(d, spy_daily=spy)
        structure_df = structure.compute(
            d, spy_daily=spy, weekly=w, earnings_cal=earnings_cal, ticker=ticker,
        )
        elder_df = elder.compute(d)
        bq_df = bq.compute(d)
        k39_gate_s, _k39_val = k39.compute_k39_gate(w, d["date"])

        sc_m = scoring.compute(
            flow_score=flow_df["flow_100"], energy_score=energy_df["energy_100"],
            structure_score=structure_df["structure_100"], mp_score=mp_df["mp_score"],
            elder_score=elder_df["elder_score"],
        )
        sc_m_raw = scoring.compute_raw(
            flow_score=flow_df["flow_100"], energy_score=energy_df["energy_100"],
            structure_score=structure_df["structure_100"], mp_score=mp_df["mp_score"],
        )
        sc_p = scoring.compute_position(
            flow_score=flow_df["flow_100"], energy_score=energy_df["energy_100"],
            structure_score=structure_df["structure_100"], mp_score=mp_df["mp_score"],
            bq_score=bq_df["bq_100"], k39_gate=k39_gate_s,
        )
        atr14 = atr(d["high"].astype(float), d["low"].astype(float),
                    d["close"].astype(float), n=14)
    except Exception as exc:
        return {"ticker": ticker, "error": f"scoring failed: {exc}"}

    fl = _last(flow_df["flow_100"])
    en = _last(energy_df["energy_100"])
    stc = _last(structure_df["structure_100"])
    mpv = _last(mp_df["mp_score"])
    eld = _last(elder_df["elder_score"])
    bqv = _last(bq_df["bq_100"])
    close = _last(d["close"])
    a14 = _last(atr14)

    # 3. Pipeline Rank (needs >= 252 bars).
    pipe_rank = fip = None
    fip_spike_excluded = False
    fip_window_effective = 252
    pr_df = None
    if len(d) >= PIPE_RANK_MIN_BARS:
        try:
            pr_df = pipeline_rank.compute(d)
            if not pr_df.empty:
                pipe_rank = _last(pr_df["pipe_rank"])
                fip = _last(pr_df["fip_quality"])
                fip_spike_excluded = bool(pr_df["fip_spike_excluded"].iloc[-1])
                fip_window_effective = int(pr_df["fip_window_effective"].iloc[-1])
        except Exception:
            pr_df = None

    # 4. SC_MOMENTUM gate (Elder>=6.5, Flow>=60, Energy>=60, Struct>=55, MP>=55)
    # — legacy scalar flag, kept for backward compat. The FULL per-engine
    # breakdown (matching the daily feed's sc_m_gates/sc_p_gates exactly, same
    # scoring.gate_breakdown_* functions) is added at Step 6 below.
    engine_vals = (eld, fl, en, stc, mpv)
    gate_pass = (
        all(v is not None for v in engine_vals)
        and eld >= SC_M_GATES["elder"] and fl >= SC_M_GATES["flow"]
        and en >= SC_M_GATES["energy"] and stc >= SC_M_GATES["structure"]
        and mpv >= SC_M_GATES["mp"]
    )
    k39_bool = bool(_last(k39_gate_s)) if len(k39_gate_s) else False
    gm = scoring.gate_breakdown_momentum(fl, en, stc, mpv, eld)
    gp = scoring.gate_breakdown_position(fl, en, stc, mpv, bqv, k39_bool)

    # 5. Trade levels + Elder 5-day history.
    levels = None
    if close is not None and a14 is not None:
        levels = levels_for_ticker(
            close, a14,
            d["high"].astype(float).to_numpy(),
            d["low"].astype(float).to_numpy(),
            d["date"].to_numpy(),
            elder_score=eld,  # DSL v1.5: elder impulse adjustment
        )
    elder_5d = [int(round(v)) for v in elder_df["elder_score"].tail(ELDER_HISTORY_DAYS)
                if pd.notna(v)]
    tk_betas = betas_for_ticker(d, spy)

    # 5b. THE BRACKET — same engine, same volume-validation as the daily feed
    # (bracket_engine.compute_bracket + stamp_bracket_volume; PM ruling: one
    # suite everywhere). `levels` already carries the fib/resistance/swing_lows
    # shape compute_bracket expects; `pm["ma"]` (below) supplies the MA ladder.
    # regime_level defaults to None (GREEN ceiling) — ad-hoc scoring has no
    # regime context threaded in, matching how the Scanner's _v21_record_fields
    # call already behaves for ad-hoc records.
    pm = _panel_metrics(d, spy)
    bracket = None
    if levels:
        bracket = compute_bracket(levels, pm["ma"], None,
                                  price=levels.get("entry"), price_source="eod_close")
        stamp_bracket_volume(bracket, d["date"], d["volume"])

    # 5c. Health (hold-decision read) — same engine as held_positions, so an
    # ad-hoc preview of a name you're considering (or already hold) shows the
    # SAME trend-integrity read it would carry once in the held book.
    hl_score = hl_state = None
    hl_subs: dict = {}
    try:
        hl_df = health.compute(d, spy_daily=spy, weekly=w if not w.empty else None)
        hl_score = _last(hl_df["hl_score"])
        hl_state = (str(hl_df["hl_state"].iloc[-1])
                   if "hl_state" in hl_df and len(hl_df) else None)
        # Health SUB-scores. Not shown on the ad-hoc table (they stay held-only
        # in the export), but four QS recipes read them — without these the
        # recipes silently cannot fire and the ad-hoc hit count comes back
        # understated versus the same name scored in the nightly run.
        for _c in ("hl_flow", "hl_higher_lows", "hl_trend_bars", "hl_vol_updn"):
            if _c in hl_df:
                hl_subs[_c] = _last(hl_df[_c])
    except Exception:
        pass

    # 5c-2. Readiness sub-scores. The readiness COMPOSITE is retired from the
    # export, but the engine still runs nightly and two QS recipes read rd_*.
    # Run it here for the same reason as the health subs above: parity with a
    # universe name, not because readiness itself is surfaced.
    rd_subs: dict = {}
    try:
        from src.engines import readiness as _readiness
        _rd = _readiness.compute(d, spy_daily=spy)
        for _c in ("rd_compression", "rd_pos_mod"):
            if _c in _rd:
                rd_subs[_c] = _last(_rd[_c])
    except Exception:
        pass

    # 5d. The 3 TV-analysis engines (Phases 2/6/7) — divergence, pin bar /
    # inside bar, smart-money CHoCH+kNN. Same functions, same defaults as the
    # nightly score_runner.py path.
    div = divergence.compute_divergence(d)
    pb = pin_bar.compute_pin_bar(d)
    sm = smart_money_knn.compute_smart_money(d)

    # Parity enrichment so the ad-hoc table carries the SAME columns as the
    # longlist/elder tables: bar-derived panel metrics (computed at 5b above,
    # reused here) + the full elder_context block (elder_pattern + VWAP/volume/
    # VCP/exhaustion). Hourly bars aren't fetched here (no extra FMP call), so
    # the hourly VWAP fields stay None while the daily VCP / 20d-volume /
    # pattern fields populate.
    as_of = str(pd.Timestamp(d["date"].iloc[-1]).date())
    _resist = (levels or {}).get("resistance") or []
    _resist_price = _resist[0].get("price") if _resist else None
    try:
        elder_ctx = compute_elder_context(
            elder_5d, [], d.to_dict("records"),
            resistance_price=_resist_price, computed_date=as_of)
    except Exception:  # noqa: BLE001
        elder_ctx = None

    return {
        "ticker": ticker,
        "as_of": as_of,
        "n_bars": len(d),
        "close": close,
        "sc_momentum": _last(sc_m),
        "sc_momentum_raw": _last(sc_m_raw),
        "sc_position": _last(sc_p),
        "flow": fl, "energy": en, "structure": stc, "mp": mpv,
        "elder": eld, "bq": bqv,
        "mp_state": str(mp_df["mp_state"].iloc[-1]) if "mp_state" in mp_df else "",
        "impulse_state": (str(elder_df["impulse_state"].iloc[-1])
                          if "impulse_state" in elder_df else ""),
        "pipe_rank": pipe_rank,
        "fip_quality": fip,
        "fip_spike_excluded": fip_spike_excluded,
        "fip_window_effective": fip_window_effective,
        "beta_30d": tk_betas.get(30),
        "beta_60d": tk_betas.get(60),
        "gate_pass": gate_pass,
        "elder_5d": elder_5d,
        "levels": levels,
        # Parity fields (longlist schema)
        "day_vol": pm["day_vol"],
        "rs_spy_20d": pm["rs_spy_20d"],
        "sma_distance_pct": pm["sma_distance_pct"],
        "ma": pm["ma"],
        "vol_30d_ann": pm["vol_30d_ann"],
        "beta_252d": pm["beta_252d"],
        "elder_pattern": elder_pattern(elder_5d),
        "elder_context": elder_ctx,
        # THE BRACKET — same engine + volume-validation as the daily feed.
        "bracket": bracket,
        # SC gate qualification — overall bool + per-engine breakdown, same
        # scoring.gate_breakdown_* functions the daily feed uses.
        "sc_m_gates": gm["pass"], "sc_m_gate_detail": gm["detail"],
        "sc_p_gates": gp["pass"], "sc_p_gate_detail": gp["detail"],
        "k39_gate": k39_bool,
        # Health (hold-decision read) — same engine as held_positions.
        "hl_score": hl_score, "hl_state": hl_state,
        # ---- QS engine inputs -------------------------------------------
        # QS reads AQE's subcomponents under the names score_runner persists,
        # so the ad-hoc record has to speak the same vocabulary or its recipes
        # cannot fire. Aliases (not renames — the originals stay for the
        # existing table), plus the k39 VALUE, which was computed and thrown
        # away here while three QS recipes key on it.
        "elder_score": eld,
        "structure_100": stc,
        "k39_value": _last(_k39_val) if len(_k39_val) else None,
        **hl_subs,
        **rd_subs,
        # Divergence / pin-bar / smart-money kNN (TV-analysis Phases 2/6/7) —
        # merged verbatim, their dict keys already match the daily feed's names
        # (div_state/div_bull_count/.../pin_bar_state/.../choch_state/knn_prob/...).
        **div,
        **pb,
        "choch_state": sm["choch_state"], "choch_date": sm["choch_date"],
        "knn_prob": sm["knn_prob"], "knn_significant": sm["knn_significant"],
        "knn_neighbors_used": sm["knn_neighbors_used"],
        "knn_tp1": sm["tp1"], "knn_tp2": sm["tp2"], "knn_tp3": sm["tp3"],
        # Momentum acceleration (MP engine, additive columns).
        "mp_accel": _last(mp_df["mp_accel"]) if "mp_accel" in mp_df else None,
        "mp_accel_state": (str(mp_df["mp_accel_state"].iloc[-1])
                           if "mp_accel_state" in mp_df and len(mp_df) else None),
        # Engine SUBCOMPONENTS — raw scores_daily-named columns, so
        # drive_sync._subcomponents(r) can be called directly on this dict
        # (same key names, same function, zero duplicated extraction logic).
        "flow_score": _last(flow_df["flow_score"]), "accum_score": _last(flow_df["accum_score"]),
        "volume_score": _last(flow_df["volume_score"]), "skew_score": _last(flow_df["skew_score"]),
        "ext_score": _last(flow_df["ext_score"]), "mfi": _last(flow_df["mfi"]),
        "cmf": _last(flow_df["cmf"]), "ha_quality_count": _last(flow_df["ha_quality_count"]),
        "vp_position_score": _last(energy_df["vp_position_score"]),
        "price_action_score": _last(energy_df["price_action_score"]),
        "squeeze_score": _last(energy_df["squeeze_score"]),
        "exhaustion_score": _last(energy_df["exhaustion_score"]),
        "atr_score": _last(energy_df["atr_score"]), "en_pos50": _last(energy_df["en_pos50"]),
        "en_trend_bars": _last(energy_df["en_trend_bars"]),
        "rs_spy_score": _last(structure_df["rs_spy_score"]),
        "rs_accel_score": _last(structure_df["rs_accel_score"]),
        "base_score": _last(structure_df["base_score"]),
        "ms_pos_score": _last(structure_df["ms_pos_score"]),
        "resist_score": _last(structure_df["resist_score"]), "wk_score": _last(structure_df["wk_score"]),
        "earn_score": _last(structure_df["earn_score"]), "rs_vs_spy": _last(structure_df["rs_vs_spy"]),
        "rs_accel": _last(structure_df["rs_accel"]), "base_days": _last(structure_df["base_days"]),
        "bd_mode": (str(structure_df["bd_mode"].iloc[-1])
                   if "bd_mode" in structure_df and len(structure_df) else None),
        "abs_mom_score": _last(mp_df["abs_mom_score"]), "mp_adx_score": _last(mp_df["adx_score"]),
        "rel_mom_score": _last(mp_df["rel_mom_score"]), "trend_score": _last(mp_df["trend_score"]),
        "roc_zscore": _last(mp_df["roc_zscore"]), "excess_return": _last(mp_df["excess_return"]),
        "adx_val": _last(mp_df["adx_val"]),
        "di_bullish": (bool(mp_df["di_bullish"].iloc[-1])
                       if "di_bullish" in mp_df and len(mp_df) else None),
        "bq_range_tight": _last(bq_df["bq_range_tight"]), "bq_vol_dry": _last(bq_df["bq_vol_dry"]),
        "bq_base_dur": _last(bq_df["bq_base_dur"]), "bq_ema_conv": _last(bq_df["bq_ema_conv"]),
        "bq_base_days": _last(bq_df["bq_base_days"]),
        "pr_ret_12m": _last(pr_df["ret_12m_score"]) if pr_df is not None else None,
        "pr_adx_score": _last(pr_df["adx_score"]) if pr_df is not None else None,
        "pr_rsi_score": _last(pr_df["rsi_score"]) if pr_df is not None else None,
        "pr_vol_score": _last(pr_df["vol_score"]) if pr_df is not None else None,
        "pr_ma_score": _last(pr_df["ma_score"]) if pr_df is not None else None,
        "momentum_composite": _last(pr_df["momentum_composite"]) if pr_df is not None else None,
        "pipe_tier": (str(pr_df["pipe_tier"].iloc[-1])
                     if pr_df is not None and len(pr_df) else None),
    }
