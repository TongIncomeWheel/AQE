"""Bring the whole-market ma_panel to the last completed US session inside the nightly run (2026-11-03).

The Valen breadth reads this panel. It used to be refreshed only by a weekly job or a manual click, so on most mornings it was
at least one session behind and the old guard let that pass. Now the nightly refreshes it under its OWN time budget, then the
strict guard (valen/breadth.py freshness) decides: fully current = fresh, anything else = STALE, loudly. Nothing here ever
passes a stale panel off as current, and it never raises into the daily run.

Cost: one FMP call per ticker that is behind (~4,300 tickers; 80 calls/min on the runner = ~54 min if every ticker is a
session behind). The budget caps the nightly's spend; a panel the pre-step workflow (.github/workflows/ma-panel.yml) already
brought current costs ~0 calls here.
"""
from __future__ import annotations

import os
import time

MA_REFRESH_BUDGET_S = 20 * 60


def refresh_for_breadth(budget_s: float | None = None, *, client=None, panel_path=None, expected=None) -> dict:
    """-> {status: FRESH|REFRESHED|PARTIAL|FAILED, before, after, budget_s, elapsed_s, reason}. Never raises."""
    t0 = time.time()
    budget = float(os.environ.get("MA_REFRESH_BUDGET_S", budget_s if budget_s is not None else MA_REFRESH_BUDGET_S))
    out = {"status": "FAILED", "budget_s": budget, "before": None, "after": None, "elapsed_s": 0.0, "reason": None}
    try:
        from src.scanner import ma_scanner
        from src.valen import breadth as B
        path = panel_path or ma_scanner.MA_PANEL
        panel = B.ensure_ma_panel(path)
        if panel is None or panel.empty:
            out["reason"] = "no ma_panel by any path (local, GitHub release, Drive)"
        else:
            before = B.freshness(panel, expected)
            out["before"] = before
            if not before["stale"]:
                out.update(status="FRESH", after=before)
            else:
                if client is None:
                    from src.data.fmp_client import FMPClient
                    client = FMPClient()
                new = ma_scanner.build_ma_panel(None, client, max_runtime_seconds=budget)
                after = B.freshness(new, expected) if new is not None and not new.empty else None
                out["after"] = after
                if after is None:
                    out["reason"] = "refresh produced no panel"
                elif not after["stale"]:
                    out["status"] = "REFRESHED"
                else:
                    out["status"] = "PARTIAL"
                    out["reason"] = after["reason"]
    except Exception as e:  # noqa: BLE001
        out["reason"] = f"{e.__class__.__name__}: {e}"
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


def summary_line(r: dict) -> str:
    a = r.get("after") or r.get("before") or {}
    base = (f"MA panel refresh {r['status']}: as of {a.get('as_of')}, {a.get('current')}/{a.get('total')} tickers carry "
            f"{a.get('expected')}, {r['elapsed_s']}s of {r['budget_s']:.0f}s budget")
    return base + (f" - {r['reason']}" if r.get("reason") else "")
