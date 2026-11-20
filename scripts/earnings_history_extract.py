"""One-off RESEARCH extract: historical earnings table (backtest review request 2026-11-20). READ-ONLY against production.

One row per ticker per report, 2020-11 to today, for every ticker in the stored score history (the research extract's universe).
Source: FMP /stable/earnings per symbol (report date, EPS actual/estimate, revenue actual/estimate). BMO/AMC is NOT in that endpoint: it
comes only from /stable/earnings-calendar?includeReportTimes=true, which the Starter plan serves for RECENT windows only, so `time` is filled
for the weeks the plan allows and left null (time_source = none) everywhere else. The meta note names exactly where it stops.

Like scripts/research_extract.py: AQE_DATA_DIR / AQE_OUTPUT_DIR point at a scratch dir BEFORE any src import, the snapshot is restored INTO the
scratch dir and never saved, and the only outside writes are two new Drive files (aqe_research_earnings_*) plus the Actions artifact.

    python -m scripts.earnings_history_extract [--since 2020-11-01] [--calendar-weeks 60]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SCRATCH = Path(os.environ.get("RESEARCH_SCRATCH") or tempfile.mkdtemp(prefix="aqe_earn_"))
os.environ["AQE_DATA_DIR"] = str(SCRATCH / "data")        # must be set before ANY src import
os.environ["AQE_OUTPUT_DIR"] = str(SCRATCH / "output")
(SCRATCH / "data").mkdir(parents=True, exist_ok=True)
(SCRATCH / "output").mkdir(parents=True, exist_ok=True)
OUT = Path(os.environ.get("RESEARCH_OUT") or "research_out")

import pandas as pd  # noqa: E402

COLUMNS = ["ticker", "report_date", "time", "time_source", "eps_actual", "eps_estimate", "revenue_actual", "revenue_estimate",
           "fiscal_period", "fiscal_year", "period_ending", "reported", "last_updated"]
PER_SYMBOL_LIMIT = 100          # ~25 years of quarters; the 2020-11 floor is applied after
NOT_PIT = ("estimates are FMP's latest consensus-at-report as stored by FMP, not an audited point-in-time snapshot; restated actuals may differ from what was "
           "first printed; the ticker list is today's universe applied backwards (survivorship)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _num(v):
    return None if v is None else float(v)


def row_from(ticker: str, r: dict) -> dict:
    return {"ticker": ticker, "report_date": str(r.get("date"))[:10], "time": None, "time_source": "none",
            "eps_actual": _num(r.get("epsActual")), "eps_estimate": _num(r.get("epsEstimated")),
            "revenue_actual": _num(r.get("revenueActual")), "revenue_estimate": _num(r.get("revenueEstimated")),
            "fiscal_period": None, "fiscal_year": None, "period_ending": None,
            "reported": r.get("epsActual") is not None or r.get("revenueActual") is not None,
            "last_updated": r.get("lastUpdated")}


def pull_symbols(client, tickers, since: str, stable: str, clock=time.monotonic, budget_s: float = 3 * 3600) -> dict:
    """-> {"rows": [...], "failed": {ticker: reason}, "empty": [...], "aborted": reason|None}. A quota error stops the run LOUDLY, never silently."""
    from src.data.fmp_client import FMPError, FMPQuotaError
    rows, failed, empty, aborted = [], {}, [], None
    t0 = clock()
    for i, t in enumerate(tickers):
        if clock() - t0 > budget_s:
            aborted = f"time budget {budget_s:.0f}s reached after {i} of {len(tickers)} tickers"
            break
        try:
            data = client._get_json(f"{stable}/earnings", {"symbol": t, "limit": PER_SYMBOL_LIMIT, "apikey": client.config.api_key})
        except FMPQuotaError as e:
            aborted = f"FMP quota/denial after {i} of {len(tickers)} tickers: {e}"
            break
        except FMPError as e:
            failed[t] = f"{e.__class__.__name__}: {str(e)[:160]}"
            continue
        got = [row_from(t, r) for r in (data if isinstance(data, list) else []) if str(r.get("date") or "")[:10] >= since]
        if not got:
            empty.append(t)
        rows += got
    return {"rows": rows, "failed": failed, "empty": empty, "aborted": aborted}


def fill_times(client, df: pd.DataFrame, stable: str, weeks: int, today: date | None = None) -> dict:
    """Walk weekly earnings-calendar windows back from today (includeReportTimes) and stamp `time` onto matching (ticker, date) rows.
    Stops at the first window the plan refuses and says so. Mutates df in place."""
    from src.data.fmp_client import FMPError
    today = today or date.today()
    key = {(a, b): i for i, (a, b) in enumerate(zip(df["ticker"], df["report_date"]))}
    info = {"weeks_requested": weeks, "weeks_served": 0, "oldest_window_served": None, "stopped": None, "rows_timed": 0}
    end = today + timedelta(days=14)
    for w in range(weeks):
        start = end - timedelta(days=6)
        try:
            data = client._get_json(f"{stable}/earnings-calendar", {"from": start.isoformat(), "to": end.isoformat(),
                                                                    "includeReportTimes": "true", "apikey": client.config.api_key})
        except FMPError as e:
            info["stopped"] = f"plan/API refused the window {start}..{end}: {str(e)[:160]}"
            break
        for r in data if isinstance(data, list) else []:
            i = key.get((r.get("symbol"), str(r.get("date"))[:10]))
            if i is None:
                continue
            tm = (r.get("time") or "").lower() or None
            if tm:
                df.at[i, "time"], df.at[i, "time_source"] = tm, "fmp_calendar"
            df.at[i, "fiscal_period"], df.at[i, "fiscal_year"], df.at[i, "period_ending"] = r.get("fiscalPeriod"), r.get("fiscalYear"), r.get("periodEnding")
        info["weeks_served"] += 1
        info["oldest_window_served"] = start.isoformat()
        end = start - timedelta(days=1)
    info["rows_timed"] = int((df["time_source"] == "fmp_calendar").sum())
    return info


def build_meta(df: pd.DataFrame, tickers, pulled: dict, cal: dict, since: str) -> dict:
    d = pd.to_datetime(df["report_date"]) if len(df) else pd.Series(dtype="datetime64[ns]")
    per_t = df.groupby("ticker").size() if len(df) else pd.Series(dtype=int)
    late = [] if not len(df) else sorted(df.groupby("ticker")["report_date"].min().loc[lambda s: s > "2021-06-30"].index)
    no_est = None if not len(df) else round(float(df["eps_estimate"].isna().mean()), 3)
    status = "failed" if not len(df) else ("partial" if (pulled["failed"] or pulled["aborted"] or pulled["empty"]) else "ok")
    return {"schema": "aqe_research_earnings_history.v1", "generated_at": _now(), "status": status, "since": since,
            "tickers_requested": len(tickers), "tickers_with_rows": int(per_t.shape[0]), "rows": int(len(df)),
            "rows_reported": int(df["reported"].sum()) if len(df) else 0, "rows_upcoming_unreported": int((~df["reported"]).sum()) if len(df) else 0,
            "date_min": str(d.min().date()) if len(df) else None, "date_max": str(d.max().date()) if len(df) else None,
            "rows_by_year": {str(k): int(v) for k, v in d.dt.year.value_counts().sort_index().items()} if len(df) else {},
            "eps_estimate_null_share": no_est,
            "revenue_estimate_null_share": None if not len(df) else round(float(df["revenue_estimate"].isna().mean()), 3),
            "time_coverage": cal | {"note": "BMO/AMC is not in /stable/earnings; the calendar serves report times for recent windows only on the Starter plan. Rows outside them have time null / time_source none. Infer timing from the price gap if needed."},
            "gaps": {"aborted": pulled["aborted"], "failed_tickers": pulled["failed"], "tickers_with_no_rows_since_floor": sorted(pulled["empty"]),
                     "first_report_after_2021_06_30": late, "rows_per_ticker_min": int(per_t.min()) if len(per_t) else 0,
                     "rows_per_ticker_median": float(per_t.median()) if len(per_t) else 0},
            "not_point_in_time": NOT_PIT}


def load_tickers() -> list[str]:
    from src.data import persist
    res = persist.load_snapshot_best(only=["scores_daily.parquet"])
    if not res.get("ok"):
        raise SystemExit(f"RESTORE FAILED (loud, no silent empty): {res.get('reason')}")
    s = pd.read_parquet(SCRATCH / "data" / "scores_daily.parquet", columns=["ticker"])
    return sorted(s["ticker"].dropna().unique().tolist())


def _drive_put(name: str, blob: bytes, mime: str) -> dict:
    from src.data import gdrive_uploader
    r = gdrive_uploader.upload_or_replace(name, blob, mime=mime)
    if not r.get("ok"):
        print(f"DRIVE UPLOAD FAILED for {name}: {r.get('reason')}", file=sys.stderr)
    return {"name": name, "ok": bool(r.get("ok")), "file_id": r.get("file_id"), "reason": r.get("reason"), "bytes": len(blob)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2020-11-01")
    ap.add_argument("--calendar-weeks", type=int, default=60)
    a = ap.parse_args(argv)
    from src.data.fmp_client import FMPClient
    from src.data.earnings import FMP_STABLE
    tickers = load_tickers()
    print(f"[earnings_history] {len(tickers)} tickers; floor {a.since}", flush=True)
    client = FMPClient()
    pulled = pull_symbols(client, tickers, a.since, FMP_STABLE)
    df = pd.DataFrame(pulled["rows"], columns=COLUMNS).drop_duplicates(["ticker", "report_date"]).sort_values(["ticker", "report_date"]).reset_index(drop=True)
    cal = fill_times(client, df, FMP_STABLE, a.calendar_weeks) if len(df) else {"stopped": "no rows to time"}
    meta = build_meta(df, tickers, pulled, cal, a.since)
    OUT.mkdir(parents=True, exist_ok=True)
    pq, mp = OUT / "aqe_research_earnings_history.parquet", OUT / "aqe_research_earnings_history_meta.json"
    df.to_parquet(pq, index=False)
    mp.write_text(json.dumps(meta, indent=1, default=str))
    ids = [_drive_put(pq.name, pq.read_bytes(), "application/octet-stream"), _drive_put(mp.name, mp.read_bytes(), "application/json")]
    (OUT / "drive_ids.json").write_text(json.dumps({x["name"]: x for x in ids}, indent=1))
    print(json.dumps({k: meta[k] for k in ("status", "tickers_requested", "tickers_with_rows", "rows", "date_min", "date_max")} | {"drive": ids}, default=str), flush=True)
    print(f"[earnings_history] gaps: aborted={meta['gaps']['aborted']} failed={len(meta['gaps']['failed_tickers'])} empty={len(meta['gaps']['tickers_with_no_rows_since_floor'])} calendar={cal}", flush=True)
    return 0 if meta["status"] != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
