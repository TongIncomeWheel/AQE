"""MOMENTUM HIGH: build the export section from the price panel. Additive: returns the two top-level values and touches nothing else.

`momentum_high_status` is never silent: 'live' (computed), 'degraded' (computed but the panel is stale or SPY is short, reason given) or 'error' (nothing computed,
reason given; `momentum_high` is then null, which means NOT READ, not "no members").
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from . import engine, spec as S

STALE_DAYS = 4          # the export date vs the panel's last session (a long weekend is 3-4 calendar days)


def build_section(daily_tickers: list[str], export_date: str | None = None, panel=None, spy=None) -> tuple[dict | None, dict]:
    if panel is None or spy is None:
        from src.data.paths import PANEL_DAILY, SPY_DAILY
        if not PANEL_DAILY.exists() or not SPY_DAILY.exists():
            return None, {"status": "error", "reason": f"price panel or SPY file missing ({PANEL_DAILY.name} / {SPY_DAILY.name})"}
        panel = pd.read_parquet(PANEL_DAILY, columns=["date", "ticker", "high", "low", "close"])
        spy = pd.read_parquet(SPY_DAILY, columns=["date", "close"])
    panel = panel.assign(date=pd.to_datetime(panel["date"]).dt.normalize())
    if len(spy.dropna(subset=["close"])) < S.SMA200 + S.RS_LOOKBACK:
        return None, {"status": "error", "reason": f"SPY history too short ({len(spy)} bars) for the 200-day trend and 63-day relative strength"}
    res = engine.compute(panel, spy, daily_tickers or None)
    as_of = res.members.index[-1]
    rows = engine.rows_at(res, as_of)
    m = res.market.loc[as_of]
    reasons = []
    if export_date:
        try:
            lag = (date.fromisoformat(str(export_date)[:10]) - as_of.date()).days
            if lag > STALE_DAYS:
                reasons.append(f"price panel's last session {as_of.date()} is {lag} days before the export date {export_date}")
        except ValueError:
            pass
    if pd.isna(m["spy_above_200d"]) or pd.isna(m["breadth_pct_above_50d"]):
        reasons.append("market check incomplete (SPY 200-day average or breadth not computable)")
    n_short = int(res.feat["short_history"].sum())
    status = {"status": "degraded" if reasons else "live", "reason": "; ".join(reasons) or None, "as_of": str(as_of.date()),
              "universe_n": int(res.feat["close"].shape[1]), "eligible_n": int(m["eligible_n"]), "members_n": len(rows),
              "first_day_n": sum(1 for r in rows if r["first_day"]), "names_under_253_bars": n_short,
              "gate_counts_in_order": {k: int(v) for k, v in res.counts.loc[as_of].items()}}
    section = {
        "what_it_is": S.WHAT_IT_IS, "as_of": str(as_of.date()),
        "market_check": {"as_of": str(as_of.date()), "spy_above_200d": None if pd.isna(m["spy_above_200d"]) else bool(m["spy_above_200d"]),
                         "breadth_pct_above_50d": None if pd.isna(m["breadth_pct_above_50d"]) else round(float(m["breadth_pct_above_50d"]), 1),
                         "market_ok": bool(m["market_ok"]), "eligible_n": int(m["eligible_n"]),
                         "note": "market_ok = SPY above its 200-day average AND at least 50% of eligible names (price >= $5, ATR14 1.5-15% of close) above their own 50-day average. "
                                 "Members below are listed whether or not market_ok is true; this section filters nothing itself."},
        "members": rows, "stop_note": S.STOP_NOTE, "measured_odds": S.MEASURED_ODDS, "rules": S.RULES,
        "note": "A reading of what is already working, computed from raw prices. Not a forecast, not a buy list, not sizing; the trade decision is the PM's.",
    }
    return section, status
