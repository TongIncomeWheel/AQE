"""Smart-Money CHoCH + kNN Confidence Engine — instance-based learning over
a ticker's own CHoCH history.

Ports the DETERMINISTIC parts of a TradingView "ML Smart Money Concepts"
indicator to Python: change-of-character (CHoCH) trend-flip detection on
confirmed swing pivots, plus a genuine (if intentionally simple)
k-nearest-neighbors classifier that scores the CURRENT CHoCH's odds of
"winning" against every PAST CHoCH of the same direction on this ticker.

Be precise about what this is: a real instance-based learner (k-NN,
brute-force Euclidean distance) over 3 hand-picked features (volume-delta,
displacement, velocity) and a lookahead-resolved binary outcome label. It is
NOT deep learning, there is no external model file, and there is no
randomness anywhere — the same input bars always produce the same output
(covered by a determinism test). "ML" here means "a small, transparent,
reproducible nearest-neighbor lookup on the ticker's own history", not a
trained network.

Algorithm
---------
1. Swings + CHoCH (bar-by-bar state machine — this mirrors the Pine
   original's sequential model and genuinely needs the loop):
   a confirmed pivot high at index p needs `swing_len` bars printed on
   both sides (`high[p] == max(high[p-swing_len : p+swing_len+1])`, and
   mirrored for pivot lows); it becomes *known* at bar `p + swing_len` (the
   bar where its right-side window finishes printing) — non-repainting.
   Walking bars in order, `last_swing_high` / `last_swing_low` track the
   most recently KNOWN pivots. A BULLISH CHoCH fires when `trend <= 0` and
   `close > last_swing_high` (trend -> 1); a BEARISH CHoCH mirrors on
   `last_swing_low` (trend -> -1). Every flip is recorded as an event.
2. Feature vector per CHoCH event (vs. the PRIOR CHoCH event, or bar 0 if
   this is the ticker's first CHoCH in the window): `vol_delta` (mean
   volume-weighted buy/sell imbalance over the interval, normalised by mean
   volume), `displacement` (ATR-normalised price move since the prior
   event), `velocity` (displacement / bars elapsed).
3. Self-labeling: an event is "resolved" once `lookahead` bars have printed
   after it. `outcome=1` if the favorable excursion (MFE) in the CHoCH's
   direction beat the adverse excursion (MAE), else 0; `favorable_run` is
   the (non-negative) MFE, kept for the TP projection.
4. kNN query: the LATEST CHoCH event is scored against the pool of past,
   RESOLVED, SAME-DIRECTION events within `window_len` bars of it —
   brute-force Euclidean distance in the 3-feature space, k nearest (or
   fewer if the pool is smaller), `knn_prob` = the neighbors' mean
   outcome. TP1/2/3 project the neighbors' `favorable_run` distribution
   (mean*0.5 / median / p75) from TODAY's close, signed by direction.

Judgment calls (the spec had a couple of intentionally loose spots):
  * "prev_i far/absent" (vol_delta windowing): the interval `[prev_i, i]`
    is used verbatim UNLESS there is no real prior event, or the gap to it
    exceeds `swing_len * 2` bars — in either case we fall back to just the
    last `min(swing_len*2, i)` bars ending at `i`. This keeps the volume
    feature from silently averaging over an unbounded stretch on a
    ticker's first CHoCH (where "prev_i" defaults to bar 0).
  * Pivot ties: "is the max/min of the window" is applied non-strictly (a
    flat top/bottom can produce more than one adjacent pivot bar) — this
    matches Pine's `ta.pivothigh`/`ta.pivotlow`, which is also non-strict.
  * Empty kNN pool vs. no CHoCH at all: the Return-dict field description
    ("`knn_prob`: ... None if pool empty/insufficient") is treated as
    authoritative over the looser Step-4 prose — an empty pool degrades
    ONLY the kNN fields (`knn_prob`/`knn_significant`/`knn_neighbors_used`/
    `tp1-3`) to their null values, while `choch_state`/`choch_date` still
    report the real, detected CHoCH. The FULL null result (`choch_state`
    also "NONE") is reserved for when no CHoCH was ever detected, or the
    input itself is degenerate (short/malformed/exception).

Pure and deterministic. Never raises: any malformed input, short history,
or internal error degrades to the null result.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U

_REQUIRED_COLS = {"date", "open", "high", "low", "close", "volume"}
_MIN_BARS = 60


def _null_result() -> dict:
    return {
        "choch_state": "NONE",
        "choch_date": None,
        "knn_prob": None,
        "knn_significant": False,
        "knn_neighbors_used": 0,
        "tp1": None,
        "tp2": None,
        "tp3": None,
    }


def compute_smart_money(
    daily,
    *,
    swing_len: int = 5,
    lookahead: int = 20,
    window_len: int = 500,
    k: int = 5,
    min_score: float = 0.60,
    atr_len: int = 14,
) -> dict:
    """Detect the latest CHoCH and score it via kNN over the ticker's own
    past CHoCH events.

    `daily`: pd.DataFrame with columns date, open, high, low, close, volume
    (single ticker, ascending date order). Only the trailing bars needed to
    cover `window_len` + `lookahead` + pivot-confirmation margin are used
    for speed. Returns a flat, export/parquet-friendly dict (see
    `_null_result` for the null shape). Never raises.
    """
    try:
        if daily is None or len(daily) < _MIN_BARS:
            return _null_result()
        if not _REQUIRED_COLS.issubset(set(daily.columns)):
            return _null_result()

        tail_n = window_len + lookahead + max(60, swing_len * 4)
        d = daily.tail(tail_n).reset_index(drop=True).copy() if len(daily) > tail_n else daily.reset_index(drop=True).copy()
        n = len(d)
        if n < _MIN_BARS:
            return _null_result()

        high = d["high"].astype(float)
        low = d["low"].astype(float)
        close = d["close"].astype(float)
        volume = d["volume"].astype(float)
        dates = d["date"]

        high_a = high.to_numpy()
        low_a = low.to_numpy()
        close_a = close.to_numpy()
        volume_a = volume.to_numpy()

        atr_a = U.atr(high, low, close, atr_len).to_numpy()

        pivot_highs = _confirmed_pivots(high_a, swing_len, mode="high")
        pivot_lows = _confirmed_pivots(low_a, swing_len, mode="low")

        # confirm_bar -> pivot price, ascending by confirm_bar (index-monotonic).
        high_confirm = [(p + swing_len, high_a[p]) for p in pivot_highs]
        low_confirm = [(p + swing_len, low_a[p]) for p in pivot_lows]

        events = _detect_choch(n, close_a, dates, high_confirm, low_confirm)
        if not events:
            return _null_result()

        query = events[-1]
        query_state = "BULLISH" if query["direction"] == 1 else "BEARISH"
        query_date = query["date"]
        query_idx = query["index"]

        feats = _event_features(events, high_a, low_a, close_a, volume_a, atr_a, swing_len)
        labels = _event_labels(events, n, high_a, low_a, lookahead)

        query_feat = feats[-1]

        pool_idx = []
        for j in range(len(events) - 1):
            ev = events[j]
            if ev["index"] >= query_idx:
                continue
            if ev["direction"] != query["direction"]:
                continue
            if labels[j] is None:
                continue
            if query_idx - ev["index"] > window_len:
                continue
            pool_idx.append(j)

        if not pool_idx:
            return {
                "choch_state": query_state,
                "choch_date": query_date,
                "knn_prob": None,
                "knn_significant": False,
                "knn_neighbors_used": 0,
                "tp1": None,
                "tp2": None,
                "tp3": None,
            }

        dists = []
        for j in pool_idx:
            fv = feats[j]
            dist = float(np.sqrt(sum((fv[m] - query_feat[m]) ** 2 for m in range(3))))
            dists.append((dist, j))
        dists.sort(key=lambda t: (t[0], t[1]))

        actual_k = min(k, len(dists))
        nearest = dists[:actual_k]

        outcomes = [labels[j]["outcome"] for _, j in nearest]
        knn_prob = round(float(np.mean(outcomes)), 3)
        significant = bool(knn_prob >= min_score or knn_prob <= (1.0 - min_score))

        favorable_runs = [labels[j]["favorable_run"] for _, j in nearest]
        current_close = float(close_a[-1])
        sign = 1.0 if query["direction"] == 1 else -1.0
        mean_fr = float(np.mean(favorable_runs))
        median_fr = float(np.median(favorable_runs))
        p75_fr = float(np.percentile(favorable_runs, 75))

        tp1 = round(current_close + sign * mean_fr * 0.5, 2)
        tp2 = round(current_close + sign * median_fr, 2)
        tp3 = round(current_close + sign * p75_fr, 2)

        return {
            "choch_state": query_state,
            "choch_date": query_date,
            "knn_prob": knn_prob,
            "knn_significant": significant,
            "knn_neighbors_used": actual_k,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
        }
    except Exception:
        return _null_result()


# ---------- helpers ----------


def _confirmed_pivots(arr: np.ndarray, swing_len: int, mode: str) -> list[int]:
    """Confirmed (non-repainting) fractal pivots on `arr`.

    Index i is a pivot HIGH (mode="high") iff arr[i] is the max of
    arr[i-swing_len : i+swing_len+1] (mirror pivot LOW on the min). Applied
    non-strictly (ties allowed), matching Pine's `ta.pivothigh`/
    `ta.pivotlow`. Only indices with `swing_len` bars already printed on
    both sides are considered.
    """
    n = len(arr)
    if n < swing_len * 2 + 1:
        return []
    pivots: list[int] = []
    for i in range(swing_len, n - swing_len):
        window = arr[i - swing_len : i + swing_len + 1]
        if np.isnan(window).any():
            continue
        center = arr[i]
        if mode == "high":
            if center >= window.max():
                pivots.append(i)
        else:
            if center <= window.min():
                pivots.append(i)
    return pivots


def _fmt_date(x) -> str:
    return pd.Timestamp(x).strftime("%Y-%m-%d")


def _detect_choch(
    n: int,
    close_a: np.ndarray,
    dates: pd.Series,
    high_confirm: list[tuple[int, float]],
    low_confirm: list[tuple[int, float]],
) -> list[dict]:
    """Bar-by-bar CHoCH state machine. Sequential by construction (trend
    and last-known-swing state must be carried forward bar to bar)."""
    events: list[dict] = []
    trend = 0
    last_high = None
    last_low = None
    hi_ptr = 0
    lo_ptr = 0
    n_hi = len(high_confirm)
    n_lo = len(low_confirm)

    for j in range(n):
        while hi_ptr < n_hi and high_confirm[hi_ptr][0] == j:
            last_high = high_confirm[hi_ptr][1]
            hi_ptr += 1
        while lo_ptr < n_lo and low_confirm[lo_ptr][0] == j:
            last_low = low_confirm[lo_ptr][1]
            lo_ptr += 1

        if last_high is None or last_low is None:
            continue

        c = close_a[j]
        if trend <= 0 and c > last_high:
            trend = 1
            events.append(
                {"index": j, "date": _fmt_date(dates.iloc[j]), "direction": 1, "entry_price": float(c)}
            )
        elif trend >= 0 and c < last_low:
            trend = -1
            events.append(
                {"index": j, "date": _fmt_date(dates.iloc[j]), "direction": -1, "entry_price": float(c)}
            )
    return events


def _event_features(
    events: list[dict],
    high_a: np.ndarray,
    low_a: np.ndarray,
    close_a: np.ndarray,
    volume_a: np.ndarray,
    atr_a: np.ndarray,
    swing_len: int,
) -> list[tuple[float, float, float]]:
    """3-feature vector per event: (vol_delta, displacement, velocity)."""
    feats: list[tuple[float, float, float]] = []
    for idx, ev in enumerate(events):
        i = ev["index"]
        has_prev = idx > 0
        prev_i = events[idx - 1]["index"] if has_prev else 0
        gap = i - prev_i

        fallback = (not has_prev) or (gap > swing_len * 2)
        if fallback:
            w = min(swing_len * 2, i)
            seg_start = max(0, i - w)
        else:
            seg_start = max(0, prev_i)

        h_seg = high_a[seg_start : i + 1]
        l_seg = low_a[seg_start : i + 1]
        c_seg = close_a[seg_start : i + 1]
        v_seg = volume_a[seg_start : i + 1]

        rng = h_seg - l_seg
        safe_rng = np.where(rng > 0, rng, 1.0)
        buy_frac = np.where(rng > 0, (c_seg - l_seg) / safe_rng, 0.5)
        signed_vol = v_seg * (2.0 * buy_frac - 1.0)

        mean_vol = float(np.mean(v_seg)) if len(v_seg) else 0.0
        if mean_vol > 0 and np.isfinite(mean_vol):
            vol_delta = float(np.mean(signed_vol)) / mean_vol
        else:
            vol_delta = 0.0
        if not np.isfinite(vol_delta):
            vol_delta = 0.0

        atr_i = atr_a[i] if i < len(atr_a) else np.nan
        if np.isfinite(atr_i) and atr_i > 0:
            displacement = abs(close_a[i] - close_a[prev_i]) / atr_i
        else:
            displacement = 0.0

        velocity = displacement / max(1, i - prev_i)

        feats.append((float(vol_delta), float(displacement), float(velocity)))
    return feats


def _event_labels(
    events: list[dict],
    n: int,
    high_a: np.ndarray,
    low_a: np.ndarray,
    lookahead: int,
) -> list[dict | None]:
    """Lookahead-resolved outcome label per event; None if unresolved."""
    labels: list[dict | None] = []
    for ev in events:
        i = ev["index"]
        entry = ev["entry_price"]
        if i + lookahead > n - 1:
            labels.append(None)
            continue
        fut_high = high_a[i + 1 : i + lookahead + 1]
        fut_low = low_a[i + 1 : i + lookahead + 1]
        if ev["direction"] == 1:
            mfe = float(np.max(fut_high)) - entry
            mae = entry - float(np.min(fut_low))
        else:
            mfe = entry - float(np.min(fut_low))
            mae = float(np.max(fut_high)) - entry
        outcome = 1 if mfe > mae else 0
        favorable_run = max(mfe, 0.0)
        labels.append({"outcome": outcome, "favorable_run": favorable_run})
    return labels
