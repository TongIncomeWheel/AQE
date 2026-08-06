"""Freeze the cup & handle hit-rate table from the panel's own history.

Double-click `pattern_calibrate.bat` — no terminal, per the standing rule.

Runs the SAME detector the daily export runs, walking each ticker's history
forward and recording what happened next. Writes data/patterns/calibration.json,
which the export then reads at runtime. Re-run it occasionally (quarterly is
plenty — the table describes years of history, not this week).

Runtime is a few minutes on the full panel: pure numpy over data already on
disk, ZERO FMP calls.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engines.pattern_calibration import (  # noqa: E402
    HORIZON, STEP, TARGET_ATR, aggregate, sweep_ticker,
)

SGT = ZoneInfo("Asia/Singapore")


def main() -> int:
    import pandas as pd
    from src.data.paths import PANEL_DAILY, PROJECT_ROOT

    if not PANEL_DAILY.exists():
        print(f"[FAIL] no panel at {PANEL_DAILY} — run the daily pipeline first.")
        return 2

    print(f"[1/3] reading {PANEL_DAILY} ...")
    p = pd.read_parquet(PANEL_DAILY,
                        columns=["date", "ticker", "high", "low", "close", "volume"])
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    p = p.sort_values(["ticker", "date"])
    tickers = p["ticker"].unique()
    print(f"      {len(p):,} bars across {len(tickers):,} tickers")

    print(f"[2/3] sweeping (step={STEP}, horizon={HORIZON}d, "
          f"target={TARGET_ATR}xATR) ...")
    rows, done, t0 = [], 0, time.time()
    for tk, g in p.groupby("ticker", sort=False):
        try:
            rows += sweep_ticker(g["high"].to_numpy(dtype=float),
                                 g["low"].to_numpy(dtype=float),
                                 g["close"].to_numpy(dtype=float),
                                 g["date"].to_numpy(),
                                 g["volume"].to_numpy(dtype=float))
        except Exception as exc:  # noqa: BLE001
            print(f"      [skip] {tk}: {type(exc).__name__}: {exc}")
        done += 1
        if done % 100 == 0:
            print(f"      {done}/{len(tickers)} tickers · {len(rows)} formations "
                  f"· {time.time() - t0:.0f}s")

    if not rows:
        print("[FAIL] zero formations found across the whole panel. That is a "
              "detector problem, not a market problem — do NOT ship an empty table.")
        return 3

    cells = aggregate(rows)
    payload = {
        "built": datetime.now(SGT).strftime("%Y-%m-%d %H:%M:%S SGT"),
        "horizon": HORIZON, "target_atr": TARGET_ATR, "step": STEP,
        "formations": len(rows),
        "tickers": int(len(tickers)),
        "outcome_definition": (
            "worked = closed above the rim within the horizon AND then reached "
            "rim + 2xATR14 before closing below the invalidation. failed = closed "
            "below the invalidation. Unresolved rows are excluded from the rate "
            "and reported separately."),
        "cells": cells,
    }
    out = Path(PROJECT_ROOT) / "data" / "patterns" / "calibration.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"[3/3] wrote {out}")
    print(f"\n{'CELL':28} {'n':>5} {'worked':>7} {'cleared':>8} {'unres':>6}")
    for k in sorted(cells):
        c = cells[k]
        print(f"{k:28} {c['n']:>5} "
              f"{(str(c['p_worked']) if c['p_worked'] is not None else '—'):>7} "
              f"{(str(c['p_cleared']) if c['p_cleared'] is not None else '—'):>8} "
              f"{c['unresolved']:>6}")
    print(f"\n{len(rows)} formations · {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
