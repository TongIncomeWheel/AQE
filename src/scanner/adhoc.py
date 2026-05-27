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

import pandas as pd

from src.data.earnings import load_earnings
from src.data.fmp_client import FMPClient, FMPError, resample_to_weekly
from src.data.panel_builder import SPY_DAILY
from src.engines import bq, elder, energy, flow, k39, mp, pipeline_rank, scoring, structure
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
    if len(d) >= PIPE_RANK_MIN_BARS:
        try:
            pr_df = pipeline_rank.compute(d)
            if not pr_df.empty:
                pipe_rank = _last(pr_df["pipe_rank"])
                fip = _last(pr_df["fip_quality"])
        except Exception:
            pass

    # 4. SC_MOMENTUM gate (Elder>=6.5, Flow>=60, Energy>=60, Struct>=55, MP>=55).
    engine_vals = (eld, fl, en, stc, mpv)
    gate_pass = (
        all(v is not None for v in engine_vals)
        and eld >= SC_M_GATES["elder"] and fl >= SC_M_GATES["flow"]
        and en >= SC_M_GATES["energy"] and stc >= SC_M_GATES["structure"]
        and mpv >= SC_M_GATES["mp"]
    )

    # 5. Trade levels + Elder 5-day history.
    levels = None
    if close is not None and a14 is not None:
        levels = levels_for_ticker(
            close, a14,
            d["high"].astype(float).to_numpy(),
            d["low"].astype(float).to_numpy(),
            d["date"].to_numpy(),
        )
    elder_5d = [int(round(v)) for v in elder_df["elder_score"].tail(ELDER_HISTORY_DAYS)
                if pd.notna(v)]
    tk_betas = betas_for_ticker(d, spy)

    return {
        "ticker": ticker,
        "as_of": str(pd.Timestamp(d["date"].iloc[-1]).date()),
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
        "beta_30d": tk_betas.get(30),
        "beta_60d": tk_betas.get(60),
        "gate_pass": gate_pass,
        "elder_5d": elder_5d,
        "levels": levels,
    }
