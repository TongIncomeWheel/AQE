"""universe_enrichment.py -- hourly-bar context and the M&A flag for the Standard Scan's screened universe-only names (PM 2026-11-19).

THE GAP (19 Nov NOT_SERVED audit): the nightly pulls hourly bars (elder_context VWAP / volume trend / up-bar ratio) only for the longlist and Elder list, and scans M&A
only for the daily_list and the held book. A name the Standard Scan's screens seat from the WHOLE universe therefore reaches a seat with elder_context.vwap_5d.*,
volume.vol_trend_5d / up_bar_vol_ratio and ma_status / ma_note blank (88-100% of universe-only rows). A blank ma_status reads as "no deal"; it must never.

THE FIX, sized to what the seats will actually see: the screens are deterministic (committee_topup.screen_picks), so the nightly (Step 8a-4) and the CI top-up know the
~117 screened names. This module pulls hourly bars and the M&A scan for exactly those names (a few hundred FMP calls, not 3,000), under a wall-clock budget, and writes
universe_enrichment.json beside the committee data. `pma_pipeline.py augment-export --enrichment` merges it into the universe_only rows; a name it did not reach is
set to ma_status UNKNOWN with a plain note, never left blank. Status is LOUD: ok | partial | failed, with the counts and the names not served.

Read-only on every AQE artifact; nothing here scores, gates or sizes.
"""
from __future__ import annotations

import time
from datetime import date

SCHEMA = "universe_enrichment.v1"
FILENAME = "universe_enrichment.json"
BUDGET_S = 600.0            # wall clock for the hourly pull; the M&A scan is bounded by MAX_MA_NAMES (one news call each)
MAX_MA_NAMES = 400


def _row_e5(r: dict):
    return r.get("elder_5d") or []


def _resistance(r: dict):
    t = ((r.get("bracket") or {}).get("targets")) or []
    return t[0].get("price") if t and isinstance(t[0], dict) else None


def build(names, rows, run_date: str, client, daily=None, budget_s: float = BUDGET_S, clock=time.monotonic, ma_refresh=None, cache_path=None) -> dict:
    """-> the universe_enrichment document. Never raises: every failure is a counted, named reason in the document."""
    from src.engines.elder_context import compute_elder_context
    names = sorted({t for t in names if t})
    by_t = {r["ticker"]: r for r in (rows or []) if isinstance(r, dict) and r.get("ticker")}
    errors, out = [], {t: {"elder_context": None, "hourly_bars": 0, "ma_status": None, "ma_note": None, "ma_evidence": None} for t in names}
    if daily is None:
        try:
            from src.pipeline import committee_data as cd
            daily = cd.load_panel_daily(names, 20)
        except Exception as e:  # noqa: BLE001
            daily = {}
            errors.append(f"daily bars unavailable ({e.__class__.__name__}: {e}); elder_context daily fields blank")
    # ---- hourly bars -> elder_context ----
    t0 = clock()
    served = empty = skipped = 0
    for t in names:
        if clock() - t0 > budget_s:
            skipped += 1
            continue
        try:
            hb = client.get_intraday_bars(t, interval="1hour") or []
        except Exception as e:  # noqa: BLE001
            hb = []
            errors.append(f"{t}: hourly bars failed ({e.__class__.__name__})")
        r = by_t.get(t) or {}
        try:
            ctx = compute_elder_context(_row_e5(r), hb, (daily or {}).get(t) or [], resistance_price=_resistance(r))
        except Exception as e:  # noqa: BLE001
            ctx = None
            errors.append(f"{t}: elder_context failed ({e.__class__.__name__}: {e})")
        out[t]["elder_context"], out[t]["hourly_bars"] = ctx, len(hb)
        if hb:
            served += 1
        else:
            empty += 1
    elder = {"requested": len(names), "served": served, "no_hourly_bars": empty, "skipped_over_budget": skipped, "budget_s": budget_s,
             "elapsed_s": round(clock() - t0, 1)}
    # ---- M&A ----
    ma = {"requested": len(names), "scan_status": "not_run", "n_scanned": 0, "n_failed": 0, "n_flagged": 0, "unscanned": []}
    scan = names[:MAX_MA_NAMES]
    if len(names) > MAX_MA_NAMES:
        ma["unscanned"] = names[MAX_MA_NAMES:]
        errors.append(f"M&A scan capped at {MAX_MA_NAMES} names; {len(names) - MAX_MA_NAMES} not scanned (declared UNKNOWN)")
    try:
        if ma_refresh is None:
            from src.data import ma_flag
            from src.data.paths import DATA_DIR
            ma_refresh = lambda tk, cl, today: ma_flag.refresh(tk, cl, today=today, cache_path=cache_path or (DATA_DIR / "ma_flags_universe.json"))   # noqa: E731
        art = ma_refresh(scan, client, date.fromisoformat(str(run_date)[:10]))
        for t, fl in (art.get("tickers") or {}).items():
            if t in out:
                out[t]["ma_status"], out[t]["ma_note"], out[t]["ma_evidence"] = fl.get("ma_status"), fl.get("ma_note"), fl.get("ma_evidence")
        ma.update({k: art.get(k) for k in ("scan_status", "n_scanned", "n_failed", "n_flagged")})
        if art.get("reason"):
            ma["reason"] = art["reason"]
    except Exception as e:  # noqa: BLE001
        ma["scan_status"] = "failed"
        errors.append(f"M&A scan failed ({e.__class__.__name__}: {e}); every enriched name is UNKNOWN, never NONE")
    for t in names:                                              # a name the scan did not reach is UNKNOWN, loud, never blank
        if out[t]["ma_status"] is None:
            out[t]["ma_status"], out[t]["ma_note"] = "UNKNOWN", "M&A scan did not reach this universe-only name; treat as unscanned, never as no deal"
            if t not in ma["unscanned"]:
                ma["unscanned"].append(t)
    ma["unscanned"] = sorted(ma["unscanned"])
    problems = skipped or (names and served == 0) or ma["scan_status"] in ("failed", "not_run") or ma["unscanned"]
    status = "failed" if names and served == 0 and ma["scan_status"] in ("failed", "not_run") else ("partial" if problems or ma["scan_status"] == "partial" else "ok")
    return {"schema": SCHEMA, "date": str(run_date)[:10], "status": status, "requested": len(names), "elder": elder, "ma": ma, "errors": errors[:50],
            "errors_total": len(errors), "tickers": out}


def summary_line(doc: dict) -> str:
    e, m = doc["elder"], doc["ma"]
    return (f"Universe enrichment {doc['status'].upper()}: {doc['requested']} screened names; hourly bars {e['served']}/{e['requested']} "
            f"({e['no_hourly_bars']} none, {e['skipped_over_budget']} over budget); M&A {m['scan_status']} {m['n_scanned']} scanned, {m['n_flagged']} flagged, "
            f"{len(m['unscanned'])} unscanned (UNKNOWN)")
