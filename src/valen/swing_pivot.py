"""Momentum AT THE PIVOT, as data on every export row (PM 2026-11-05, "momentum at the pivot" door).

Per daily_list row / held position:
  swing_pivot        True  = weekly AND daily swing structure are both higher highs / higher lows AND the daily close is within
                             ATR_NEAR (1) daily ranges, either side, of the latest confirmed daily swing high
                     False = a reading exists and the name is not that
                     None  = the swing could not be read (too little history / no ATR): never a silent False
  swing_atr_dist     (daily close - latest confirmed daily swing high) / atr_14d, positive = above (None when not readable)
  swing_weekly / swing_daily   the swing class ("HH/HL", "HH but LL", ...)
  swing_high / swing_high_date the level the distance is measured from

Data only: not a gate, not a vote, not sizing (R1). The edge ATR_NEAR is NOT defined here: it is read from card_extras.py (the one place the
PM changes it). The swing code is mtf.py's own (strict fractal pivots, 2 weekly bars with the open week left out, 3 daily bars each side), loaded
by path exactly as committee_data does, so this column and the Cards' strip cannot disagree. Bars come from the price panel the export build
already loads: no extra FMP call.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = ("aegis/skills/premarket-analysis/tools", "aegis/plugin/aegis-core/skills/pma/tools")
HISTORY_BARS = 470          # the same daily depth the committee grid fetches (committee_data.DAILY_FETCH_DAYS)


@lru_cache(maxsize=None)
def _load(name: str):
    """Load a plugin tool (mtf.py / card_extras.py) by path. The generated runtime copy first, the plugin tree second."""
    for rel in _TOOLS:
        p = PROJECT_ROOT / rel / f"{name}.py"
        if p.exists():
            spec = importlib.util.spec_from_file_location(f"swing_pivot_{name}", p)
            m = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = m
            spec.loader.exec_module(m)
            return m
    raise RuntimeError(f"{name}.py not found under {' or '.join(_TOOLS)}")


def atr_near() -> float:
    return float(_load("card_extras").ATR_NEAR)


def _blank(reason: str) -> dict:
    return {"swing_pivot": None, "swing_atr_dist": None, "swing_weekly": None, "swing_daily": None,
            "swing_high": None, "swing_high_date": None, "swing_note": reason}


def read_one(bars: list[dict], atr, run_date: str) -> dict:
    """The swing columns for one name from its daily bars (dicts with date/open/high/low/close/volume) and its atr_14d."""
    mtf = _load("mtf")
    daily = [b for b in mtf._clean(bars) if b["date"][:10] <= run_date]
    if len(daily) < mtf.MIN_BARS:
        return _blank(f"only {len(daily)} daily bars")
    wk = mtf.weekly(daily)
    partial = bool(wk) and wk[-1]["week"] == "{}-W{:02d}".format(*dt.date.fromisoformat(run_date).isocalendar()[:2])
    W = mtf.frame(wk, "W", completed=wk[:-1] if partial else wk)
    D = mtf.frame(daily, "D")
    if not (W.get("served") and D.get("served")):
        return _blank("weekly or daily frame not served")
    sh = ((D.get("swing") or {}).get("last_swing_high") or {})
    out = {"swing_weekly": W.get("swing_class"), "swing_daily": D.get("swing_class"),
           "swing_high": sh.get("price"), "swing_high_date": sh.get("date"), "swing_atr_dist": None}
    if not isinstance(atr, (int, float)) or isinstance(atr, bool) or atr <= 0 or not isinstance(sh.get("price"), (int, float)) or sh["price"] <= 0:
        return {**out, "swing_pivot": None, "swing_note": "no daily swing high or no atr_14d to measure against"}
    d = (D["close"] - sh["price"]) / atr
    out["swing_atr_dist"] = round(d, 2)
    hh = W.get("swing_class") == "HH/HL" and D.get("swing_class") == "HH/HL"
    out["swing_pivot"] = bool(hh and abs(d) <= atr_near())
    return out


def attach_swing_pivot(daily_list: list[dict], held_positions: list[dict] | None = None, *, panel=None, run_date: str | None = None) -> dict:
    """Stamp the swing columns on every row. Returns the status block for the export (`swing_pivot_status`): a failure is LOUD
    (status error + reason), never an empty column that reads like no name qualifies."""
    rows = list(daily_list) + list(held_positions or [])
    try:
        if panel is None:
            import pandas as pd
            from src.data.paths import PANEL_DAILY
            panel = pd.read_parquet(PANEL_DAILY, columns=["ticker", "date", "open", "high", "low", "close", "volume"])
        run_date = run_date or dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
        want = {r.get("ticker") for r in rows if r.get("ticker")}
        by_tk = {}
        for tk, df in panel[panel["ticker"].isin(want)].groupby("ticker", sort=False):
            df = df.sort_values("date").tail(HISTORY_BARS)
            by_tk[tk] = [{"date": str(d)[:10], "open": o, "high": h, "low": l, "close": c, "volume": v}
                         for d, o, h, l, c, v in zip(df["date"], df["open"], df["high"], df["low"], df["close"], df["volume"])]
        stamped = 0
        for r in rows:
            tk = r.get("ticker")
            r.update(read_one(by_tk[tk], r.get("atr_14d"), run_date) if tk in by_tk else _blank("not in the price panel"))
            stamped += 1
    except Exception as exc:  # noqa: BLE001 -- additive column, never takes the export down
        return {"status": "error", "reason": str(exc), "stamped": 0}
    hits = sorted(r["ticker"] for r in daily_list if r.get("swing_pivot") is True)
    return {"status": "live", "stamped": stamped, "at_the_pivot": len(hits), "at_the_pivot_names": hits,
            "atr_near": atr_near(), "unreadable": sorted(r["ticker"] for r in daily_list if r.get("swing_pivot") is None),
            "rule": "weekly HH/HL and daily HH/HL and the daily close within atr_near ATR either side of the latest confirmed daily swing high (data only)"}
