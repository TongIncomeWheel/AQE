"""What actually happened after each historical cup — the half that makes the
pattern lens worth reading.

A detector on its own is decoration. Loose rules find cups on everything, the
output looks plausible, and a chart pattern has no ground truth on the row, so
nobody can tell. The only honest answer to "is this worth acting on" comes from
running the SAME detector across the panel's history and counting outcomes.

Same discipline as QS: a frozen table of historical look-alikes, read at
runtime, never fitted on the fly.

THE OUTCOME DEFINITION, stated plainly because it is a choice:

  from the day the pattern is detected, look forward HORIZON sessions
    CLEARED   close went above the rim (the trigger)                    then
    WORKED    ...and after clearing, reached rim + TARGET_ATR x ATR14
              BEFORE closing below the invalidation
    FAILED    closed below the invalidation without ever clearing

"Worked" deliberately requires the target to come AFTER the break, and the
invalidation to be checked the whole way. Counting "price was higher 20 days
later" would flatter every detection made in a rising market.

NO LOOK-AHEAD. Each detection is made on bars[:i] only — the detector never
sees a bar past the day it is called on — and the outcome is measured strictly
on bars after i. The pivot definition already refuses to confirm a turn until
5 clean bars have passed, so a formation cannot be recognised on the day it
completes; that lag is real and is preserved here rather than assumed away.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.engines.patterns import detect_cup_handle

HORIZON = 20                  # sessions to resolve an outcome
TARGET_ATR = 2.0              # "worked" = rim + 2 x ATR14, the QS yardstick
STEP = 3                      # detect every N bars — a cup does not change daily
MIN_BARS = 160                # need the window plus room to resolve

# Fit bands the runtime looks up. Coarse ON PURPOSE: three bands over a few
# hundred samples is already thin, and finer buckets would report differences
# that are noise.
FIT_BANDS = ((0.0, 0.5, "0-0.5"), (0.5, 0.7, "0.5-0.7"), (0.7, 1.01, "0.7-1"))

CALIBRATION_FILENAME = "calibration.json"


def fit_band(fit: float | None) -> str | None:
    if fit is None:
        return None
    for lo, hi, name in FIT_BANDS:
        if lo <= fit < hi:
            return name
    return None


def _atr14(high, low, close, i):
    """ATR14 as of bar i, from completed bars only."""
    if i < 15:
        return None
    h, l, c = high[i - 14:i + 1], low[i - 14:i + 1], close[i - 15:i]
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[1:]),
                                              np.abs(l[1:] - c[1:])))
    v = float(np.nanmean(tr))
    return v if np.isfinite(v) and v > 0 else None


def resolve(high, low, close, i, trigger, invalidation, atr,
            horizon=HORIZON, target_atr=TARGET_ATR) -> str:
    """Outcome of a detection made at bar i. See the module docstring."""
    end = min(len(close), i + 1 + horizon)
    target = trigger + target_atr * atr
    cleared = False
    for j in range(i + 1, end):
        if not cleared and close[j] > trigger:
            cleared = True
        if close[j] < invalidation:
            return "cleared_then_failed" if cleared else "failed"
        if cleared and high[j] >= target:
            return "worked"
    return "cleared_unresolved" if cleared else "unresolved"


def sweep_ticker(high, low, close, dates, volume,
                 step=STEP, horizon=HORIZON) -> list[dict]:
    """Every DISTINCT formation in one name's history, with its outcome.

    Deduped by (pattern_start, trigger): a cup is visible for weeks, and
    counting it once per bar would report one lucky formation as forty wins.
    """
    n = len(close)
    out: list[dict] = []
    seen: set[tuple] = set()
    if n < MIN_BARS:
        return out
    for i in range(MIN_BARS, n - horizon, step):
        r = detect_cup_handle(high[:i + 1], low[:i + 1], close[:i + 1],
                              dates[:i + 1], volume[:i + 1] if volume is not None else None)
        if not r.get("pattern"):
            continue
        key = (r["pattern_start"], r["pattern_trigger"])
        if key in seen:
            continue
        atr = _atr14(high, low, close, i)
        if atr is None or r["pattern_invalidation"] >= r["pattern_trigger"]:
            continue
        seen.add(key)
        out.append({
            "stage": r["pattern_stage"],
            "fit": r["pattern_fit"],
            "band": fit_band(r["pattern_fit"]),
            "days": r["pattern_days"],
            "outcome": resolve(high, low, close, i, r["pattern_trigger"],
                               r["pattern_invalidation"], atr, horizon),
        })
    return out


def aggregate(rows: list[dict]) -> dict:
    """Hit rates per (stage, fit band). Unresolved rows are EXCLUDED from the
    rate and REPORTED separately — folding them into the denominator would
    quietly depress every number, and into the numerator would inflate it."""
    cells: dict[str, dict] = {}
    for r in rows:
        if not r["band"] or not r["stage"]:
            continue
        key = f"{r['stage']}|{r['band']}"
        c = cells.setdefault(key, {"n": 0, "worked": 0, "failed": 0,
                                   "cleared": 0, "unresolved": 0})
        if r["outcome"] in ("unresolved", "cleared_unresolved"):
            c["unresolved"] += 1
            if r["outcome"] == "cleared_unresolved":
                c["cleared"] += 1
            continue
        c["n"] += 1
        if r["outcome"] == "worked":
            c["worked"] += 1
            c["cleared"] += 1
        elif r["outcome"] == "cleared_then_failed":
            c["failed"] += 1
            c["cleared"] += 1
        else:
            c["failed"] += 1
    for c in cells.values():
        c["p_worked"] = round(c["worked"] / c["n"], 3) if c["n"] else None
        c["p_cleared"] = round(c["cleared"] / c["n"], 3) if c["n"] else None
    return cells


def _calibration_path() -> Path:
    """DATA_DIR first, then the repo copy — same fallback as qs_daily, which
    broke on HF persistent storage where AQE_DATA_DIR holds no config."""
    from src.data.paths import DATA_DIR, PROJECT_ROOT
    for base in (DATA_DIR, PROJECT_ROOT / "data"):
        p = Path(base) / "patterns" / CALIBRATION_FILENAME
        if p.exists():
            return p
    return Path(PROJECT_ROOT) / "data" / "patterns" / CALIBRATION_FILENAME


_CACHE: dict | None = None


def load_calibration(force: bool = False) -> dict | None:
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE
    try:
        p = _calibration_path()
        if p.exists():
            _CACHE = json.loads(p.read_text(encoding="utf-8"))
            return _CACHE
    except Exception:  # noqa: BLE001
        pass
    return None


def lookup(stage: str | None, fit: float | None) -> dict:
    """{hit_rate, n, status} for a live detection.

    status is the point of this function. An UNCALIBRATED lens must say so:
    a null hit rate that looks like "we measured and it was nothing" would be
    a lie, and the whole reason this module exists is that a detector without
    outcomes is decoration.
    """
    cal = load_calibration()
    if not cal:
        return {"hit_rate": None, "n": None, "status": "uncalibrated"}
    band = fit_band(fit)
    cell = (cal.get("cells") or {}).get(f"{stage}|{band}")
    if not cell or not cell.get("n"):
        return {"hit_rate": None, "n": 0, "status": "no_analogues"}
    return {"hit_rate": cell.get("p_worked"), "n": cell.get("n"),
            "cleared_rate": cell.get("p_cleared"), "status": "ok",
            "measured_on": cal.get("built"), "horizon": cal.get("horizon")}
