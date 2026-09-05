"""signal_hitrate.py — the (elder_pattern x structure_shift) forward-20-session
hit-rate table (spec: docs/specs/aqe_voice_packet_spec_2026-09-05.md §2,
`signal_hit_rate_20d` / `signal_n`, requested by thorp — "a measured edge").

Live-computed every run over the TRAILING 60 SESSIONS — deliberately NOT a
frozen quarterly table like QS/patterns. thorp's ask is "what has actually
happened recently in this cell", not a multi-year backtest average.

For every ticker with enough panel history, walks the trailing LOOKBACK
start-points that already have a HORIZON-session outcome, computing historical
elder_pattern and structure_shift AS OF each day using the exact same
functions the live daily row uses (`elder.compute`, `find_swing`,
`last_confirmed_pivot_high`) called on arrays TRUNCATED to that day — no
future bar ever leaks into an "as of" read. Every (ticker, day) sample is
bucketed globally by (elder_pattern, structure_shift), so two names in the
same cell today share the same denominator regardless of ticker.

A cell with zero samples returns (None, 0) — "no_analogues", never reported
as a measured zero (same discipline the removed PAT-3 pattern-calibration
table used — see src/engines/patterns.py's docstring; git show dd9bcdc).
"""

from __future__ import annotations

import pandas as pd

from src.data.drive_sync import BOS_MAX_EXTENSION_PCT
from src.engines import elder
from src.engines.elder_context import elder_pattern as _elder_pattern_of
from src.scanner.levels import PIVOT_K, SWING_WINDOW, find_swing, last_confirmed_pivot_high

LOOKBACK = 60      # trailing sessions sampled per ticker
HORIZON = 20       # forward sessions to the outcome
_MIN_PIVOT_BARS = 2 * PIVOT_K + 3          # find_swing's own floor
MIN_BARS = _MIN_PIVOT_BARS + LOOKBACK + HORIZON


def _structure_shift_asof(highs, lows, close_i: float, dates) -> str | None:
    """The same BOS/CHoCH/RANGE rule `_v21_record_fields` applies to today's
    row, evaluated on arrays already truncated to 'as of day i'."""
    lph = last_confirmed_pivot_high(highs, dates, k=PIVOT_K, window=SWING_WINDOW)
    confirmed_high = lph.get("price") if lph else None
    swing = find_swing(highs, lows, k=PIVOT_K, window=SWING_WINDOW)
    swing_low = swing.get("low") if swing else None
    if confirmed_high is not None and confirmed_high > 0 and close_i > confirmed_high:
        ext = round(100.0 * (close_i / confirmed_high - 1.0), 4)
        return "BULLISH_BOS" if ext <= BOS_MAX_EXTENSION_PCT else "ABOVE_STRUCTURE"
    if swing_low is not None and close_i < swing_low:
        return "BEARISH_CHOCH"
    if swing_low is not None:
        return "RANGE"
    return None


def ticker_samples(g: pd.DataFrame) -> list[tuple[str, str, bool]]:
    """[(elder_pattern, structure_shift, closed_higher_20d_later), ...] for one
    ticker's trailing LOOKBACK start-points that already have a HORIZON-day
    outcome. `g` needs columns date/open/high/low/close/volume, ascending
    date order, for a single ticker."""
    n = len(g)
    if n < MIN_BARS:
        return []
    highs = g["high"].to_numpy(dtype=float)
    lows = g["low"].to_numpy(dtype=float)
    closes = g["close"].to_numpy(dtype=float)
    dates = g["date"].to_numpy()

    try:
        elder_scores = elder.compute(
            g[["date", "open", "high", "low", "close", "volume"]]
        )["elder_score"].to_numpy(dtype=float)
    except Exception:  # noqa: BLE001 — one bad ticker never blocks the table
        return []

    out: list[tuple[str, str, bool]] = []
    last_start = n - 1 - HORIZON
    first_start = max(_MIN_PIVOT_BARS, last_start - LOOKBACK + 1)
    for i in range(first_start, last_start + 1):
        e5 = [int(round(v)) for v in elder_scores[max(0, i - 4):i + 1] if v == v]
        pat = _elder_pattern_of(e5)
        if pat is None:
            continue
        shift = _structure_shift_asof(highs[:i + 1], lows[:i + 1], float(closes[i]), dates[:i + 1])
        if shift is None:
            continue
        out.append((pat, shift, bool(closes[i + HORIZON] > closes[i])))
    return out


def build_table(panel_groups: dict) -> dict[tuple[str, str], tuple[int, int]]:
    """{(elder_pattern, structure_shift): (hits, n)} across every ticker with
    enough history in `panel_groups` ({ticker: DataFrame})."""
    counts: dict[tuple[str, str], list[int]] = {}
    for g in panel_groups.values():
        for pat, shift, higher in ticker_samples(g):
            cell = counts.setdefault((pat, shift), [0, 0])
            cell[1] += 1
            if higher:
                cell[0] += 1
    return {k: (v[0], v[1]) for k, v in counts.items()}


def lookup(table: dict, elder_pattern_val, structure_shift_val) -> tuple[float | None, int]:
    """(signal_hit_rate_20d, signal_n) for one row's own (elder_pattern,
    structure_shift). (None, 0) on a cell with no samples yet -- "no_analogues",
    never a measured-looking zero."""
    hits, n = table.get((elder_pattern_val, structure_shift_val), (0, 0))
    if n == 0:
        return None, 0
    return round(100.0 * hits / n, 1), n
