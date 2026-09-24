"""VALEN whole-market breadth — piece 01's four instruments, computed for
real from the ~2000-ticker universe `src.scanner.ma_scanner` already pulls
DAILY via the HF Space's own in-app scheduler (`src/ui/daily_job.py::
_run_ma_scan_and_record`, `data/ma_panel.parquet`). No new FMP pull — this
module only reads what already exists.

**Why this needs a restore step, not just a file read.** `ma_panel.parquet`
is built by the in-app scheduler running INSIDE the HF Space's own Streamlit
process. The nightly GitHub Actions pipeline (where VALEN's Step 6i runs) is
a completely separate, ephemeral checkout with no access to that file
unless it is pulled down from the Daily Persist snapshot first — the exact
same restore `_run_ma_scan_and_record` itself does
(`persist.load_snapshot(only=["ma_panel.parquet"])`) before it scans.
`ensure_ma_panel()` below does that restore; every compute_* function here
is a pure function of an already-loaded DataFrame so it can be unit-tested
without Drive access at all.

Population: `spec.POPULATION_US_WIDE` — all US NASDAQ/NYSE names over $1B
market cap (`ma_scanner.get_ma_universe`), an order of magnitude closer to
the whole tape than AQE's own curated scan universe. Still not the full
~7,000-name market the handbook's absolute thresholds (350 monthly risers,
20/80 on T2108) were calibrated against — see
docs/AQE_VALEN_DASHBOARD_PROPOSAL.md §2.2. Every value below carries
`population` + `n` so a reader can never mistake which tape it describes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import spec as S


def ensure_ma_panel(ma_panel_path) -> pd.DataFrame | None:
    """The market-wide bar panel, restoring it from the Daily Persist
    snapshot if this run's checkout doesn't have it locally. Returns None
    (never raises) if it's unavailable by any path.

    Uses `persist.load_snapshot_best()` — checks the GitHub release asset
    (the PRIMARY store per persist.py's own docstring) before falling back
    to Drive (the backup). `_run_ma_scan_and_record`'s own restore call
    (the precedent this mirrors) only checks Drive via plain
    `load_snapshot()`; if the freshest snapshot happens to live in the
    GitHub release instead, that call would miss it too — worth fixing
    there as well if this turns out to be the actual gap."""
    if ma_panel_path.exists():
        try:
            return pd.read_parquet(ma_panel_path)
        except Exception:  # noqa: BLE001
            pass
    try:
        from src.data import persist
        res = persist.load_snapshot_best(only=["ma_panel.parquet"])
        if res.get("ok") and ma_panel_path.exists():
            return pd.read_parquet(ma_panel_path)
    except Exception:  # noqa: BLE001
        pass
    return None


def _unavailable(reason: str) -> dict:
    return {"status": "UNAVAILABLE", "reason": reason,
            "population_needed": S.POPULATION_US_WIDE}


def pct_above_ma(panel: pd.DataFrame, window: int) -> dict:
    """% of the wide universe trading above their own `window`-day SMA."""
    df = panel.sort_values(["ticker", "date"])
    above, total = 0, 0
    for _tk, g in df.groupby("ticker", sort=False):
        c = pd.to_numeric(g["close"], errors="coerce").dropna()
        if len(c) < window:
            continue
        sma = float(c.tail(window).mean())
        if not np.isfinite(sma) or sma <= 0:
            continue
        total += 1
        if float(c.iloc[-1]) > sma:
            above += 1
    if total == 0:
        return _unavailable(f"no ticker had {window} bars")
    pct = round(100.0 * above / total, 1)
    return {"status": "OK", "value": pct, "n": total, "n_above": above,
            "population": S.POPULATION_US_WIDE}


def daily_mover_counts(panel: pd.DataFrame, pct: float) -> dict:
    """Today's count: stocks up `pct`%+ vs down `pct`%+, single session."""
    df = panel.sort_values(["ticker", "date"])
    up = down = 0
    for _tk, g in df.groupby("ticker", sort=False):
        c = pd.to_numeric(g["close"], errors="coerce").dropna()
        if len(c) < 2:
            continue
        chg = (float(c.iloc[-1]) / float(c.iloc[-2]) - 1.0) * 100.0
        if chg >= pct:
            up += 1
        elif chg <= -pct:
            down += 1
    if up + down == 0:
        return _unavailable("no mover-sized session found")
    return {"status": "OK", "up": up, "down": down, "green": bool(up > down),
            "population": S.POPULATION_US_WIDE}


def window_mover_ratio(panel: pd.DataFrame, pct: float, days: int) -> dict:
    """5-day / 10-day count: sum of up-4%+ vs down-4%+ days over the
    trailing `days` sessions, as a ratio. Undefined-denominator convention:
    zero down-days reads as (up_total + 1.0) so "no sellers at all" still
    clears every "1.00 or better" threshold without a literal infinity."""
    df = panel.sort_values(["ticker", "date"])
    piv = df.pivot_table(index="date", columns="ticker", values="close").sort_index()
    if len(piv) < days + 1:
        return _unavailable(f"fewer than {days + 1} sessions in the panel")
    pct_chg = piv.pct_change() * 100.0
    recent = pct_chg.tail(days)
    up_total = int((recent >= pct).sum().sum())
    down_total = int((recent <= -pct).sum().sum())
    if down_total == 0:
        ratio = float(up_total) + 1.0 if up_total > 0 else 1.0
    else:
        ratio = round(up_total / down_total, 2)
    return {"status": "OK", "value": round(ratio, 2), "up_total": up_total,
            "down_total": down_total, "population": S.POPULATION_US_WIDE}


def cumulative_mover_counts(panel: pd.DataFrame, pct: float, sessions: int) -> dict:
    """Month/quarter big movers: up/down `pct`%+ over the trailing
    `sessions` sessions. `value` = the RISER count (what stance's
    `monthly_risers` rule reads)."""
    df = panel.sort_values(["ticker", "date"])
    up = down = 0
    for _tk, g in df.groupby("ticker", sort=False):
        c = pd.to_numeric(g["close"], errors="coerce").dropna()
        if len(c) < sessions + 1:
            continue
        chg = (float(c.iloc[-1]) / float(c.iloc[-1 - sessions]) - 1.0) * 100.0
        if chg >= pct:
            up += 1
        elif chg <= -pct:
            down += 1
    if up + down == 0:
        return _unavailable(f"no ticker had {sessions + 1} bars")
    return {"status": "OK", "value": up, "up": up, "down": down,
            "population": S.POPULATION_US_WIDE}


def net_high_low(panel: pd.DataFrame, high_window: int) -> dict:
    """52-week (or whatever history is available, min 40 sessions) new
    highs minus new lows, smoothed by an 8-day and a 20-day average.
    `green` = the 8-day average above the 20-day — "breakouts are being
    rewarded"."""
    df = panel.sort_values(["ticker", "date"])
    piv = df.pivot_table(index="date", columns="ticker", values="close").sort_index()
    if len(piv) < 40:
        return _unavailable("fewer than 40 sessions in the panel")
    window = min(high_window, len(piv))
    rolling_high = piv.rolling(window, min_periods=20).max()
    rolling_low = piv.rolling(window, min_periods=20).min()
    is_new_high = piv.ge(rolling_high) & piv.notna()
    is_new_low = piv.le(rolling_low) & piv.notna()
    daily_net = is_new_high.sum(axis=1) - is_new_low.sum(axis=1)
    avg8 = daily_net.rolling(S.NET_HIGH_LOW_FAST, min_periods=S.NET_HIGH_LOW_FAST).mean()
    avg20 = daily_net.rolling(S.NET_HIGH_LOW_SLOW, min_periods=S.NET_HIGH_LOW_SLOW).mean()
    if avg8.dropna().empty or avg20.dropna().empty:
        return _unavailable("not enough sessions to smooth 8d/20d")
    last8, last20 = float(avg8.iloc[-1]), float(avg20.iloc[-1])
    return {"status": "OK", "avg8": round(last8, 2), "avg20": round(last20, 2),
            "green": bool(last8 > last20), "latest_net": int(daily_net.iloc[-1]),
            "population": S.POPULATION_US_WIDE,
            "window_used": window}


def compute_breadth(panel: pd.DataFrame | None) -> dict:
    """Returns the shape stance.py requires for its four keys, plus two
    extra instruments (ten_day_count, quarterly_movers, net_high_low) for
    display only — stance.py's flip rules only read the four named ones."""
    reason = "market-wide panel unavailable (ma_panel.parquet not restored)"
    if panel is None or panel.empty:
        keys = ("pct_above_40d", "monthly_risers", "five_day_count", "daily_count_green")
        out = {k: _unavailable(reason) for k in keys}
        out["ten_day_count"] = _unavailable(reason)
        out["quarterly_movers"] = _unavailable(reason)
        out["net_high_low"] = _unavailable(reason)
        return out

    pct40 = pct_above_ma(panel, S.T2108_MA_WINDOW)
    daily = daily_mover_counts(panel, S.MOVER_UP_PCT)
    five_day = window_mover_ratio(panel, S.MOVER_UP_PCT, S.MOVER_COUNT_WINDOWS[0])
    ten_day = window_mover_ratio(panel, S.MOVER_UP_PCT, S.MOVER_COUNT_WINDOWS[1])
    month = cumulative_mover_counts(panel, S.BIG_MOVER_MONTH_PCT, 21)
    quarter = cumulative_mover_counts(panel, S.BIG_MOVER_QUARTER_PCT, 63)
    nhnl = net_high_low(panel, S.NET_HIGH_LOW_LOOKBACK_WEEKS * 5)

    daily_count_green = (
        {"status": "OK", "value": daily["green"], "up": daily["up"], "down": daily["down"]}
        if daily.get("status") == "OK" else daily
    )

    return {
        "pct_above_40d": pct40,
        "monthly_risers": month,
        "five_day_count": five_day,
        "daily_count_green": daily_count_green,
        "ten_day_count": ten_day,
        "quarterly_movers": quarter,
        "net_high_low": nhnl,
    }
