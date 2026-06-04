"""Trade levels — DSL stop, TP ladder, Fibonacci, R/R, and Elder history.

One source of truth for the per-ticker level bundle shown on the Scanner
longlist / watchlist and exported to the Aegis Committee. The committee reads
these precomputed values instead of deriving them itself.

Per ticker (latest scored bar):
  - DSL v2.0 structural stop + 1R risk            (src.scanner.dsl)
  - TP ladder: +1R / +2R / +3R, breakeven at +0.5R, share size at 3% risk
  - Fibonacci retracements + extensions anchored on the most recent
    auto-detected swing (pivot low -> peak high)
  - Estimated R/R = reward to the 1.618 extension divided by 1R risk
  - Elder Impulse score over the last 5 trading days
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.paths import DATA_DIR, PANEL_DAILY, SCORES_DAILY
from src.scanner.dsl import compute_initial_stop

CAPITAL = 70_000
RISK_PCT = 0.03
RISK_BUDGET = CAPITAL * RISK_PCT          # $2100 per full trade (AQE charter)

# Fibonacci ratios, anchored on a swing low -> high:
#   retracement price = high - range * r   (support, sits between low and high)
#   extension price   = low  + range * e   (target, sits above the swing high)
RETRACEMENTS = {"0.236": 0.236, "0.382": 0.382, "0.5": 0.5,
                "0.618": 0.618, "0.786": 0.786}
EXTENSIONS = {"1.272": 1.272, "1.618": 1.618, "2.0": 2.0, "2.618": 2.618}
RR_EXTENSION = "1.618"                    # estimated R/R is measured to this

PIVOT_K = 5                               # fractal strength: 11-bar window
SWING_WINDOW = 120                        # bars searched for the recent swing
ELDER_HISTORY_DAYS = 5


# ---------------------------------------------------------------------------
# Swing pivot detection
# ---------------------------------------------------------------------------

def find_swing(
    high: np.ndarray,
    low: np.ndarray,
    k: int = PIVOT_K,
    window: int = SWING_WINDOW,
) -> dict | None:
    """Auto-detect the current up-swing: the most recent pivot low -> the peak.

    The swing high is the highest high in the recent window -- the peak of the
    current advance. A confirmed pivot high is deliberately not used for the
    high: it lags badly while a momentum name keeps printing new highs, which
    would anchor the Fibonacci levels on a stale swing. The swing low is the
    most recent pivot low preceding that peak (a bar whose low is the minimum
    of the k bars on each side -- an 11-bar fractal at k=5), i.e. the launchpad
    of the leg into the peak; it falls back to the lowest low before the peak
    when no confirmed pivot low exists.

    Returns {low, high, low_idx, high_idx} with absolute indices into the
    input arrays, or None when a valid up-swing cannot be formed.
    """
    n = len(high)
    if n < 2 * k + 3:
        return None

    start = max(0, n - window)
    h = high[start:]
    l = low[start:]
    m = len(h)

    hi_idx = int(np.argmax(h))                    # peak of the recent advance
    if hi_idx == 0:
        return None                               # no room for a launchpad

    piv_lo = [
        i for i in range(k, min(hi_idx, m - k))
        if l[i] <= l[i - k:i + k + 1].min()
    ]
    lo_idx = piv_lo[-1] if piv_lo else int(np.argmin(l[:hi_idx]))

    swing_low = float(l[lo_idx])
    swing_high = float(h[hi_idx])
    if swing_high <= swing_low:
        return None

    return {
        "low": swing_low,
        "high": swing_high,
        "low_idx": start + lo_idx,
        "high_idx": start + hi_idx,
    }


def fib_levels(swing_low: float, swing_high: float) -> dict:
    """Fibonacci retracements (support) and extensions (targets) for a swing."""
    rng = swing_high - swing_low
    return {
        "retracements": {
            k: round(swing_high - rng * r, 2) for k, r in RETRACEMENTS.items()
        },
        "extensions": {
            k: round(swing_low + rng * e, 2) for k, e in EXTENSIONS.items()
        },
    }


# ---------------------------------------------------------------------------
# Per-ticker level bundle
# ---------------------------------------------------------------------------

def levels_for_ticker(
    close: float,
    atr14: float,
    highs: np.ndarray,
    lows: np.ndarray,
    dates: np.ndarray,
    beta: float | None = None,
) -> dict | None:
    """Full level bundle for one ticker from its OHLC arrays.

    close, atr14 -- latest values. highs, lows, dates -- full-history arrays
    in ascending date order.
    beta -- optional 30-day beta vs SPY; passed to compute_initial_stop for
        β-adjusted ATR clamp (high-β names get wider initial stop room).

    Returns the levels dict {entry, stop, risk, tp_1r, tp_2r, tp_3r, be,
    shares, rr_pct, rr_est, fib}, or None when inputs are invalid (non-finite
    price/ATR, fewer than 5 bars, or non-positive risk). `rr_est` and `fib`
    are None if no swing can be anchored.
    """
    if not (np.isfinite(close) and close > 0
            and np.isfinite(atr14) and atr14 > 0):
        return None
    if len(lows) < 5:
        return None

    stop, risk = compute_initial_stop(close, atr14, lows[-5:], beta=beta)
    if risk <= 0:
        return None

    levels = {
        "entry": round(close, 2),
        "stop": round(stop, 2),
        "risk": round(risk, 2),
        "tp_1r": round(close + risk, 2),
        "tp_2r": round(close + 2 * risk, 2),
        "tp_3r": round(close + 3 * risk, 2),
        "be": round(close + 0.5 * risk, 2),
        "shares": int(RISK_BUDGET / risk),
        "rr_pct": round(risk / close * 100, 1),
        "rr_est": None,
        "fib": None,
    }

    swing = find_swing(highs, lows)
    if swing is not None:
        fib = fib_levels(swing["low"], swing["high"])
        ext_target = fib["extensions"][RR_EXTENSION]
        levels["rr_est"] = round((ext_target - close) / risk, 2)
        levels["fib"] = {
            "swing_low": round(swing["low"], 2),
            "swing_high": round(swing["high"], 2),
            "swing_low_date": str(pd.Timestamp(dates[swing["low_idx"]]).date()),
            "swing_high_date": str(pd.Timestamp(dates[swing["high_idx"]]).date()),
            **fib,
        }
    return levels


def compute_trade_levels(
    panel: pd.DataFrame,
    scores: pd.DataFrame,
    betas: dict | None = None,
) -> dict[str, dict]:
    """Per-ticker level bundle for the latest scored date.

    panel  -- daily OHLC panel with columns date, ticker, high, low.
    scores -- scores_daily with columns date, ticker, close, atr14.
    betas  -- optional {ticker: {30: float, 60: float}} from load_betas().
        When provided, uses 30-day beta for β-adjusted initial stop so
        high-β names (>1.5) get a wider ATR clamp and are not stopped
        out by normal intraday volatility.

    Returns {ticker: levels_for_ticker(...)} for every ticker that scores.
    """
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    scores = scores.copy()
    scores["date"] = pd.to_datetime(scores["date"]).dt.normalize()

    latest = scores["date"].max()
    latest_scores = scores[scores["date"] == latest]

    panel = panel.sort_values(["ticker", "date"])
    panel_groups = {t: g for t, g in panel.groupby("ticker", sort=False)}

    out: dict[str, dict] = {}
    for _, row in latest_scores.iterrows():
        ticker = row["ticker"]
        grp = panel_groups.get(ticker)
        if grp is None or len(grp) < 5:
            continue
        # Resolve 30-day beta for this ticker (None = standard clamp)
        beta: float | None = None
        if betas is not None:
            beta = (betas.get(ticker) or {}).get(30)
        levels = levels_for_ticker(
            float(row["close"]),
            float(row["atr14"]),
            grp["high"].astype(float).to_numpy(),
            grp["low"].astype(float).to_numpy(),
            grp["date"].to_numpy(),
            beta=beta,
        )
        if levels is not None:
            out[ticker] = levels

    return out


def compute_elder_history(
    scores: pd.DataFrame, n: int = ELDER_HISTORY_DAYS,
) -> dict[str, list[int]]:
    """Last `n` integer Elder Impulse scores per ticker, oldest -> newest."""
    if "elder_score" not in scores.columns:
        return {}
    df = scores[["date", "ticker", "elder_score"]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values(["ticker", "date"])

    out: dict[str, list[int]] = {}
    for ticker, grp in df.groupby("ticker", sort=False):
        seq = [int(round(v)) for v in grp["elder_score"].tail(n) if pd.notna(v)]
        if seq:
            out[ticker] = seq
    return out


# ---------------------------------------------------------------------------
# Parquet loaders — the standard cached panel + scores files
# ---------------------------------------------------------------------------

def load_trade_levels(betas: dict | None = None) -> dict[str, dict]:
    """Compute trade levels from the cached panel + scores parquet files.

    betas -- optional pre-loaded {ticker: {30: float, 60: float}} dict.
        Pass the result of load_betas() to enable β-adjusted initial stops.
        When None, standard ATR clamp is used (backward-compatible).
    """
    if not PANEL_DAILY.exists() or not SCORES_DAILY.exists():
        return {}
    panel = pd.read_parquet(PANEL_DAILY, columns=["date", "ticker", "high", "low"])
    scores = pd.read_parquet(SCORES_DAILY, columns=["date", "ticker", "close", "atr14"])
    return compute_trade_levels(panel, scores, betas=betas)


def load_elder_history(n: int = ELDER_HISTORY_DAYS) -> dict[str, list[int]]:
    """Last `n` Elder scores per ticker from the cached scores parquet."""
    if not SCORES_DAILY.exists():
        return {}
    scores = pd.read_parquet(SCORES_DAILY, columns=["date", "ticker", "elder_score"])
    return compute_elder_history(scores, n=n)
