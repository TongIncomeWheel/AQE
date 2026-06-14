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
from src.scanner.dsl import compute_initial_stop, compute_initial_stop_v15

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


def recent_pivot_lows(
    low: np.ndarray,
    dates: np.ndarray,
    close: float,
    k: int = PIVOT_K,
    window: int = SWING_WINDOW,
    n: int = 3,
) -> list[dict]:
    """The last `n` CONFIRMED fractal pivot lows sitting BELOW the current close —
    structural STOP candidates (charter §4.2 Step C "last 3 confirmed swing lows").

    A pivot low is a bar whose low is the minimum of the k bars on each side (an
    11-bar fractal at k=5), so it needs k bars to its right to confirm. Only lows
    below the close qualify (a long's stop sits below entry). Most-recent first.

    Returns [{price, date}], up to n.
    """
    nbars = len(low)
    if nbars < 2 * k + 1 or not (np.isfinite(close) and close > 0):
        return []
    start = max(0, nbars - window)
    l = low[start:]
    d = dates[start:]
    out: list[dict] = []
    for i in range(len(l) - k - 1, k - 1, -1):          # newest → oldest, confirmed only
        price = float(l[i])
        if price < close and l[i] <= l[i - k:i + k + 1].min():
            out.append({"price": round(price, 2),
                        "date": str(pd.Timestamp(d[i]).date())})
            if len(out) >= n:
                break
    return out


RESISTANCE_GAP_ATR = 0.5                   # cluster pivots closer than 0.5·ATR
RESISTANCE_MAX_LEVELS = 4


def overhead_resistance(
    high: np.ndarray,
    close: float,
    dates: np.ndarray,
    atr14: float,
    k: int = PIVOT_K,
    window: int = SWING_WINDOW,
    max_levels: int = RESISTANCE_MAX_LEVELS,
) -> list[dict]:
    """Prior CONFIRMED fractal pivot highs sitting ABOVE the current close — the
    true overhead resistance a long must clear, from multi-swing history (not just
    the current swing). A pivot high is a bar whose high is the max of the k bars
    on each side (an 11-bar fractal at k=5), so it needs k bars to its right to
    confirm — the live peak is excluded until it stops extending. Near-equal highs
    (within RESISTANCE_GAP_ATR·ATR) collapse to one level. Nearest-overhead first.

    Returns [{price, date}], up to max_levels.
    """
    n = len(high)
    if n < 2 * k + 1 or not (np.isfinite(close) and close > 0):
        return []
    start = max(0, n - window)
    h = high[start:]
    d = dates[start:]
    pivots: list[tuple[float, int]] = []
    for i in range(k, len(h) - k):
        if h[i] >= h[i - k:i + k + 1].max() and h[i] > close:
            pivots.append((float(h[i]), i))
    pivots.sort(key=lambda x: x[0])                # nearest overhead first
    gap = atr14 * RESISTANCE_GAP_ATR if (atr14 and np.isfinite(atr14)) else 0.0
    out: list[dict] = []
    last_price: float | None = None
    for price, idx in pivots:
        if last_price is not None and gap > 0 and (price - last_price) < gap:
            continue                               # cluster near-equal highs
        out.append({"price": round(price, 2),
                    "date": str(pd.Timestamp(d[idx]).date())})
        last_price = price
        if len(out) >= max_levels:
            break
    return out


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
    regime_level: str | None = None,
    elder_score: float | None = None,
) -> dict | None:
    """Full level bundle for one ticker from its OHLC arrays.

    close, atr14 -- latest values. highs, lows, dates -- full-history arrays
    in ascending date order.
    beta -- optional 30-day beta vs SPY.
    regime_level -- GREEN/YELLOW/ORANGE/RED from the pipeline regime header.
    elder_score -- latest Elder Impulse score (0–10) for this ticker.

    Uses DSL v1.5 dynamic ATR ratio: stop width adapts to regime, elder
    impulse, and intraday whippiness. The ratio is clamped to [1.0, 3.5]
    so no sub-ATR stops can occur.

    Returns the levels dict {entry, stop, risk, tp_1r, tp_2r, tp_3r, be,
    shares, rr_pct, rr_est, fib, dsl_atr_ratio, atr14, resistance, swing_lows},
    or None when inputs are invalid. `rr_est` and `fib` are None if no
    swing can be anchored.
    """
    if not (np.isfinite(close) and close > 0
            and np.isfinite(atr14) and atr14 > 0):
        return None
    if len(lows) < 5:
        return None

    # DSL v2.1: β-adjusted structural stop. Recent 5-session low − 0.5·ATR,
    # clamped to [0.75, upper] × ATR where upper = 2.5 / 2.25 / 2.0 for
    # β ≥ 2.0 / ≥ 1.5 / else. Wider room for high-β names so normal volatility
    # doesn't sweep the stop ahead of the move (charter-updated behaviour).
    stop, risk = compute_initial_stop(close, atr14, lows[-5:], beta=beta)
    if risk <= 0:
        return None
    atr_ratio = round(risk / atr14, 2) if atr14 > 0 else None

    levels = {
        "entry": round(close, 2),
        "stop": round(stop, 2),
        "risk": round(risk, 2),
        "tp_1r": round(close + risk, 2),
        "tp_2r": round(close + 2 * risk, 2),
        "tp_3r": round(close + 3 * risk, 2),
        "be": round(close + 0.5 * risk, 2),
        "rr_pct": round(risk / close * 100, 1),
        "atr14": round(atr14, 3),
        "dsl_atr_ratio": atr_ratio,   # effective stop width in ATRs (β-capped 2.0–2.5)
        "rr_est": None,
        "fib": None,
        # prior confirmed pivot highs above price — true overhead resistance
        "resistance": overhead_resistance(highs, close, dates, atr14),
        # last 3 confirmed pivot lows below price — structural stop candidates (§4.2 C)
        "swing_lows": recent_pivot_lows(lows, dates, close),
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
    regime_level: str | None = None,
) -> dict[str, dict]:
    """Per-ticker level bundle for the latest scored date.

    panel  -- daily OHLC panel with columns date, ticker, high, low.
    scores -- scores_daily with columns date, ticker, close, atr14,
              and optionally elder_score (used by DSL v1.5).
    betas  -- optional {ticker: {30: float, 60: float}} from load_betas().
    regime_level -- GREEN/YELLOW/ORANGE/RED from the pipeline regime header.
        Drives the DSL v1.5 dynamic ATR ratio base.

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
        # DSL v1.5: extract elder_score if available
        elder_val: float | None = None
        if "elder_score" in row.index and pd.notna(row.get("elder_score")):
            elder_val = float(row["elder_score"])
        levels = levels_for_ticker(
            float(row["close"]),
            float(row["atr14"]),
            grp["high"].astype(float).to_numpy(),
            grp["low"].astype(float).to_numpy(),
            grp["date"].to_numpy(),
            beta=beta,
            regime_level=regime_level,
            elder_score=elder_val,
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

def load_trade_levels(
    betas: dict | None = None,
    regime_level: str | None = None,
) -> dict[str, dict]:
    """Compute trade levels from the cached panel + scores parquet files.

    betas -- optional pre-loaded {ticker: {30: float, 60: float}} dict.
        Pass the result of load_betas() to enable β-adjusted initial stops.
    regime_level -- GREEN/YELLOW/ORANGE/RED. Drives DSL v1.5 dynamic ratio
        base. When None, defaults to GREEN (tightest reasonable stop).
    """
    if not PANEL_DAILY.exists() or not SCORES_DAILY.exists():
        return {}
    panel = pd.read_parquet(PANEL_DAILY, columns=["date", "ticker", "high", "low"])
    scores = pd.read_parquet(SCORES_DAILY, columns=["date", "ticker", "close", "atr14", "elder_score"])
    return compute_trade_levels(panel, scores, betas=betas, regime_level=regime_level)


def load_elder_history(n: int = ELDER_HISTORY_DAYS) -> dict[str, list[int]]:
    """Last `n` Elder scores per ticker from the cached scores parquet."""
    if not SCORES_DAILY.exists():
        return {}
    scores = pd.read_parquet(SCORES_DAILY, columns=["date", "ticker", "elder_score"])
    return compute_elder_history(scores, n=n)
