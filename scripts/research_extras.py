"""One-off RESEARCH extracts #2-#5 for the backtest review (2026-11-20, PM-approved "ask ENG for what you need provided it's on FMP"). READ-ONLY against production.

Stages (one per run): 
  fundamentals  quarterly income statements, point-in-time keys (period end, filing date, SEC accepted timestamp), revenue / net income / EPS
  profile       FMP sector + industry per ticker (current), plus current float / shares outstanding
  intraday      1-hour bars, 2020-11 to today (per-year parquets)
  mcap          historical daily market cap per ticker

Same safety as scripts/research_extract.py: scratch AQE_DATA_DIR/AQE_OUTPUT_DIR set before any src import, the snapshot restored INTO scratch and never
saved, only new Drive files `aqe_research_*` plus the Actions artifact. Every stage writes a meta note that names every gap: failed tickers, tickers with
no rows, quota aborts, time-budget stops. Nothing is substituted for a missing value.

    python -m scripts.research_extras fundamentals|profile|intraday|mcap [--since 2020-11-01]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from scripts import earnings_history_extract as EH     # scratch env + load_tickers + _drive_put (sets AQE_DATA_DIR before any src import)

import pandas as pd  # noqa: E402

STABLE = "https://financialmodelingprep.com/stable"
OUT = EH.OUT
NOT_PIT = {
    "fundamentals": "FMP returns the latest RESTATED statements, not the first print: revenue / net income / EPS can differ from what was announced. filing_date and accepted_ts are the "
                   "dates the (latest) filing was public; a restated period can carry a later filing date than its first release.",
    "profile": "sector, industry, float and shares outstanding are CURRENT values applied backwards: not point-in-time.",
    "intraday": "bars are exchange-time (America/New_York) session bars stamped at the bar START, regular hours only; today's universe applied backwards (survivorship).",
    "mcap": "FMP's own daily market-cap series (shares x price as FMP computes it); today's universe applied backwards.",
}


def _meta_common(stage: str, tickers, since: str, pulled: dict, rows: int, extra: dict | None = None) -> dict:
    status = "failed" if rows == 0 else ("partial" if (pulled["failed"] or pulled["aborted"] or pulled["empty"]) else "ok")
    return {"schema": f"aqe_research_{stage}.v1", "generated_at": EH._now(), "status": status, "since": since, "tickers_requested": len(tickers), "rows": rows,
            "gaps": {"aborted": pulled["aborted"], "failed_tickers": pulled["failed"], "tickers_with_no_rows": sorted(pulled["empty"])},
            "not_point_in_time": NOT_PIT[stage]} | (extra or {})


def _loop(client, tickers, one, budget_s: float, clock=time.monotonic) -> dict:
    """Run `one(ticker) -> list[row]` for every ticker. A quota error aborts LOUDLY; any other FMP error names the ticker. Never silent."""
    from src.data.fmp_client import FMPError, FMPQuotaError
    rows, failed, empty, aborted = [], {}, [], None
    t0 = clock()
    for i, t in enumerate(tickers):
        if clock() - t0 > budget_s:
            aborted = f"time budget {budget_s:.0f}s reached after {i} of {len(tickers)} tickers"
            break
        try:
            got = one(t)
        except FMPQuotaError as e:
            aborted = f"FMP quota/denial after {i} of {len(tickers)} tickers: {e}"
            break
        except FMPError as e:
            failed[t] = f"{e.__class__.__name__}: {str(e)[:160]}"
            continue
        if not got:
            empty.append(t)
        rows += got
        if (i + 1) % 200 == 0:
            print(f"[research_extras] {i + 1}/{len(tickers)} tickers, {len(rows)} rows", flush=True)
    return {"rows": rows, "failed": failed, "empty": empty, "aborted": aborted}


# ---------------------------------------------------------------- fundamentals
def fundamentals_rows(client, t: str, since: str) -> list[dict]:
    data = client._get_json(f"{STABLE}/income-statement", {"symbol": t, "period": "quarter", "limit": 40, "apikey": client.config.api_key})
    out = []
    for r in data if isinstance(data, list) else []:
        if str(r.get("date") or "") < since:
            continue
        out.append({"ticker": t, "period_end": r.get("date"), "fiscal_year": r.get("fiscalYear"), "fiscal_period": r.get("period"),
                    "filing_date": r.get("filingDate"), "accepted_ts": r.get("acceptedDate"), "revenue": r.get("revenue"), "net_income": r.get("netIncome"),
                    "eps": r.get("eps"), "eps_diluted": r.get("epsDiluted"), "reported_currency": r.get("reportedCurrency")})
    return out


# ---------------------------------------------------------------- profile (+ current float)
def profile_rows(client, t: str) -> list[dict]:
    p = client._get_json(f"{STABLE}/profile", {"symbol": t, "apikey": client.config.api_key})
    p = p[0] if isinstance(p, list) and p else {}
    f = client._get_json(f"{STABLE}/shares-float", {"symbol": t, "apikey": client.config.api_key})
    f = f[0] if isinstance(f, list) and f else {}
    if not p and not f:
        return []
    return [{"ticker": t, "company_name": p.get("companyName"), "sector": p.get("sector"), "industry": p.get("industry"), "exchange": p.get("exchange"),
             "country": p.get("country"), "ipo_date": p.get("ipoDate"), "is_etf": p.get("isEtf"), "is_adr": p.get("isAdr"), "market_cap_current": p.get("marketCap"),
             "float_shares": f.get("floatShares"), "shares_outstanding": f.get("outstandingShares"), "free_float_pct": f.get("freeFloat"), "float_as_of": f.get("date")}]


# ---------------------------------------------------------------- intraday (adaptive windows: a capped response is detected, never trusted)
def fetch_range(client, t: str, start: date, end: date, interval: str = "1hour", max_loops: int = 12) -> list[dict]:
    """Bars for [start, end], newest-first as FMP returns them. If the OLDEST returned bar is more than 7 days after `start`, either the name listed later or FMP capped
    the response: re-ask for [start, oldest-1]. An empty answer means a real start of history. So a cap can never silently truncate a window."""
    rows, cur_end = [], end
    for _ in range(max_loops):
        data = client._get_json(f"{STABLE}/historical-chart/{interval}", {"symbol": t, "from": start.isoformat(), "to": cur_end.isoformat(), "apikey": client.config.api_key})
        data = data if isinstance(data, list) else []
        if not data:
            break
        rows += data
        oldest = min(str(r["date"])[:10] for r in data)
        od = date.fromisoformat(oldest)
        if (od - start).days > 7:
            cur_end = od - timedelta(days=1)
            continue
        break
    return rows


def year_windows(since: str, today: date | None = None) -> list[tuple[date, date]]:
    today = today or date.today()
    s = date.fromisoformat(since)
    out = []
    while s <= today:
        e = min(date(s.year + 1, 1, 1) - timedelta(days=1), today) if s.month == 1 and s.day == 1 else min(date(s.year, 12, 31), today)
        out.append((s, e))
        s = date(e.year + 1, 1, 1)
    return out


def intraday_rows(client, t: str, since: str, today: date | None = None) -> list[tuple]:
    out = []
    for s, e in year_windows(since, today):
        for r in fetch_range(client, t, s, e):
            out.append((t, str(r["date"]), r.get("open"), r.get("high"), r.get("low"), r.get("close"), r.get("volume")))
    return out


# ---------------------------------------------------------------- historical market cap
def mcap_rows(client, t: str, since: str, today: date | None = None) -> list[dict]:
    out = []
    for s, e in year_windows(since, today):
        data = client._get_json(f"{STABLE}/historical-market-cap", {"symbol": t, "from": s.isoformat(), "to": e.isoformat(), "limit": 400, "apikey": client.config.api_key})
        out += [{"ticker": t, "date": r.get("date"), "market_cap": r.get("marketCap")} for r in (data if isinstance(data, list) else [])]
    return out


def _write(df: pd.DataFrame, name: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    df.to_parquet(p, index=False, compression="zstd")
    return EH._drive_put(name, p.read_bytes(), "application/octet-stream")


def run(stage: str, since: str, budget_h: float) -> int:
    from src.data.fmp_client import FMPClient
    tickers = EH.load_tickers()
    client = FMPClient()
    budget = budget_h * 3600
    print(f"[research_extras] {stage}: {len(tickers)} tickers, since {since}", flush=True)
    ids, extra = [], {}
    if stage == "fundamentals":
        pulled = _loop(client, tickers, lambda t: fundamentals_rows(client, t, since), budget)
        df = pd.DataFrame(pulled["rows"]).sort_values(["ticker", "period_end"]).reset_index(drop=True) if pulled["rows"] else pd.DataFrame()
        n = len(df)
        if n:
            ids.append(_write(df, "aqe_research_fundamentals_quarterly.parquet"))
            extra = {"date_min": str(df["period_end"].min()), "date_max": str(df["period_end"].max()), "rows_by_period_year": {str(k): int(v) for k, v in pd.to_datetime(df["period_end"]).dt.year.value_counts().sort_index().items()},
                     "filing_date_null_share": round(float(df["filing_date"].isna().mean()), 3), "accepted_ts_null_share": round(float(df["accepted_ts"].isna().mean()), 3)}
    elif stage == "profile":
        pulled = _loop(client, tickers, lambda t: profile_rows(client, t), budget)
        df = pd.DataFrame(pulled["rows"])
        n = len(df)
        if n:
            ids.append(_write(df, "aqe_research_profile.parquet"))
            extra = {"sector_null": int(df["sector"].isna().sum()), "industry_null": int(df["industry"].isna().sum()), "n_industries": int(df["industry"].nunique()), "n_sectors": int(df["sector"].nunique())}
    elif stage == "mcap":
        pulled = _loop(client, tickers, lambda t: mcap_rows(client, t, since), budget)
        df = pd.DataFrame(pulled["rows"])
        n = len(df)
        if n:
            ids.append(_write(df, "aqe_research_market_cap_daily.parquet"))
            extra = {"date_min": str(df["date"].min()), "date_max": str(df["date"].max())}
    elif stage == "intraday":
        pulled = _loop(client, tickers, lambda t: intraday_rows(client, t, since), budget)
        n = len(pulled["rows"])
        if n:
            df = pd.DataFrame(pulled["rows"], columns=["ticker", "ts_et", "open", "high", "low", "close", "volume"])
            df["ts_et"] = pd.to_datetime(df["ts_et"])
            df = df.drop_duplicates(["ticker", "ts_et"]).sort_values(["ticker", "ts_et"]).reset_index(drop=True)
            n = len(df)
            for yr, g in df.groupby(df["ts_et"].dt.year):
                ids.append(_write(g.reset_index(drop=True), f"aqe_research_bars_1h_{yr}.parquet"))
            per_t = df.groupby("ticker")["ts_et"].min()
            extra = {"bars_by_year": {str(k): int(v) for k, v in df["ts_et"].dt.year.value_counts().sort_index().items()}, "interval": "1hour",
                     "tickers_first_bar_after_2020_12": sorted(per_t[per_t > pd.Timestamp("2020-12-31")].index.tolist())}
    else:
        raise SystemExit(f"unknown stage {stage}")
    meta = _meta_common(stage, tickers, since, pulled, n, extra) | {"drive": ids}
    OUT.mkdir(parents=True, exist_ok=True)
    mp = OUT / f"aqe_research_{stage}_meta.json"
    mp.write_text(json.dumps(meta, indent=1, default=str))
    ids.append(EH._drive_put(mp.name, mp.read_bytes(), "application/json"))
    (OUT / "drive_ids.json").write_text(json.dumps({x["name"]: x for x in ids}, indent=1))
    print(json.dumps({k: meta[k] for k in ("status", "tickers_requested", "rows")} | {"drive": ids}, default=str), flush=True)
    print(f"[research_extras] gaps: aborted={meta['gaps']['aborted']} failed={len(meta['gaps']['failed_tickers'])} none={len(meta['gaps']['tickers_with_no_rows'])}", flush=True)
    return 0 if meta["status"] != "failed" else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["fundamentals", "profile", "intraday", "mcap"])
    ap.add_argument("--since", default=None)
    ap.add_argument("--budget-hours", type=float, default=5.0)
    a = ap.parse_args(argv)
    since = a.since or {"fundamentals": "2018-01-01", "profile": "2020-11-01", "intraday": "2020-11-01", "mcap": "2020-11-01"}[a.stage]
    return run(a.stage, since, a.budget_hours)


if __name__ == "__main__":
    raise SystemExit(main())
