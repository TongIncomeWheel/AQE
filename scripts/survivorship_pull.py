"""One-off RESEARCH pull: a PARTIAL survivorship set for the backtest review (2026-11-21, conductor-approved: no spend, no plan upgrade). READ-ONLY.

Today's universe applied backwards flatters every backtest. This pulls what we CAN reach of the names that left it, inside the 2021-03 .. today window:
  * daily OHLCV for every delisted name found,
  * month-end historical market cap for those same names (NOT the current universe).

THE LIST IS PARTIAL. FMP Starter returns only the 100 most recent delistings (page 0) and refuses every later page, so the candidate list is the union of:
  fmp_page0         FMP /delisted-companies page 0 (latest 100 delistings, with their delisted date)
  alpaca_inactive   Alpaca inactive US assets (list only, no delist date). THIN BEFORE ~2019 AND MISSES SOME MERGERS.
  aqe_panel_stale   tickers in AQE's own restored price panel whose last bar is old (names the daily pipeline once carried that have since gone)
  aqe_git_universe  names that ever appeared in data/universe.txt in git history, minus today's universe (the file has only 2 commits, so this adds little)
A complete list needs FMP Premium. Every output file carries PARTIAL in its name and the meta says so; nothing is substituted for a missing value, and every
failure/gap is named in the meta.

Same safety as scripts/research_extras.py: scratch AQE_DATA_DIR/AQE_OUTPUT_DIR set before any src import, the snapshot restored INTO scratch and never saved, only new
Drive files `aqe_research_*` plus the Actions artifact.

    python -m scripts.survivorship_pull list
    python -m scripts.survivorship_pull pull [--shard i/n] [--since 2021-03-01] [--budget-hours 5]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from scripts import earnings_history_extract as EH     # scratch env + _drive_put (sets AQE_DATA_DIR before any src import)
from scripts import research_extras as RX               # _loop, shard, mcap_rows, STABLE

import pandas as pd  # noqa: E402

OUT = EH.OUT
SCRATCH = EH.SCRATCH
SINCE_DEFAULT = "2021-03-01"
US_EXCHANGES = {"NASDAQ", "NYSE", "AMEX", "ARCA", "BATS", "CBOE", "NYSEARCA", "NYSEMKT"}
MCAP_ENDPOINTS = ("historical-market-capitalization", "historical-market-cap")
STALE_DAYS = 10            # a name whose last bar is within this many days of today is still trading, not delisted
DERIVATIVE_NAME = re.compile(r"\b(warrants?|units?|rights?)\b|\bTEST\b", re.I)
DERIVATIVE_SYMBOL = re.compile(r"^[A-Z]{4}[WRU]$")          # only used when a source gives no name
PARTIAL_NOTE = ("PARTIAL survivorship set. The candidate list is the union of FMP delisted-companies page 0 (the latest 100 only: Starter refuses later pages), Alpaca inactive "
                "US assets, AQE's own price-panel tickers that have gone stale, and names from AQE's data/universe.txt git history. Alpaca's inactive list is THIN BEFORE ~2019 "
                "AND MISSES SOME MERGERS, so delistings are under-counted, most of all the older ones. A complete list needs FMP Premium. Bars are FMP's (split/dividend adjusted "
                "as FMP serves them); market cap is FMP's own daily series reduced to the last row of each month.")


def _now() -> str:
    return EH._now()


def norm_symbol(s) -> str:
    """Upper/strip; a one-letter class suffix 'BRK.B' becomes FMP's 'BRK-B'. Exchange suffixes (VBNK.TO) are kept as-is (those names are excluded as non-US anyway)."""
    t = str(s or "").strip().upper()
    return t[:-2] + "-" + t[-1] if len(t) > 2 and t[-2] == "." else t


# ------------------------------------------------------------------ candidate sources (each returns (rows, error|None); a failed source is named, never silent)
def src_fmp_page0(client) -> tuple[list[dict], str | None]:
    try:
        data = client._get_json(f"{RX.STABLE}/delisted-companies", {"page": 0, "limit": 100, "apikey": client.config.api_key})
    except Exception as e:  # noqa: BLE001
        return [], f"{e.__class__.__name__}: {str(e)[:160]}"
    rows = [{"symbol": r.get("symbol"), "name": r.get("companyName"), "exchange": r.get("exchange"), "delisted_date": r.get("delistedDate"), "source": "fmp_page0"}
            for r in (data if isinstance(data, list) else [])]
    return rows, None


def src_alpaca_inactive(client=None) -> tuple[list[dict], str | None]:
    try:
        import requests
        from src.options import config as C
        from src.options.providers import alpaca as A
        last = None
        for host in (C.ALPACA_TRADING_URL, C.ALPACA_PAPER_TRADING_URL):
            r = requests.get(f"{host}/v2/assets", params={"status": "inactive", "asset_class": "us_equity"}, headers=A._auth_headers(), timeout=120)
            if r.status_code in (401, 403):
                last = f"{host}: HTTP {r.status_code}"
                continue
            r.raise_for_status()
            return [{"symbol": a.get("symbol"), "name": a.get("name"), "exchange": a.get("exchange"), "delisted_date": None, "source": "alpaca_inactive"} for a in r.json()], None
        return [], f"Alpaca refused both hosts ({last})"
    except Exception as e:  # noqa: BLE001
        return [], f"{e.__class__.__name__}: {str(e)[:160]}"


def src_aqe_panel_stale(client=None) -> tuple[list[dict], str | None]:
    try:
        from src.data import persist
        res = persist.load_snapshot_best(only=["panel_daily.parquet"])
        if not res.get("ok"):
            return [], f"snapshot restore failed: {res.get('reason')}"
        p = pd.read_parquet(SCRATCH / "data" / "panel_daily.parquet", columns=["ticker", "date"])
        last = p.groupby("ticker")["date"].max()
        cut = pd.Timestamp(last.max()) - pd.Timedelta(days=STALE_DAYS)
        stale = last[pd.to_datetime(last) < cut]
        return [{"symbol": t, "name": None, "exchange": None, "delisted_date": str(pd.Timestamp(d).date()), "source": "aqe_panel_stale"} for t, d in stale.items()], None
    except Exception as e:  # noqa: BLE001
        return [], f"{e.__class__.__name__}: {str(e)[:160]}"


def src_aqe_git_universe(client=None) -> tuple[list[dict], str | None]:
    try:
        cur = {ln.strip().upper() for ln in Path("data/universe.txt").read_text().splitlines() if ln.strip() and not ln.startswith("#")}
        log = subprocess.run(["git", "log", "-p", "--format=", "--", "data/universe.txt"], capture_output=True, text=True, check=True).stdout
        ever = {ln[1:].strip().upper() for ln in log.splitlines() if ln.startswith("+") and not ln.startswith("+++") and ln[1:].strip() and not ln[1:].startswith("#")}
        return [{"symbol": t, "name": None, "exchange": None, "delisted_date": None, "source": "aqe_git_universe"} for t in sorted(ever - cur)], None
    except Exception as e:  # noqa: BLE001
        return [], f"{e.__class__.__name__}: {str(e)[:160]}"


def build_candidates(client, sources=None) -> tuple[pd.DataFrame, dict]:
    """Union of the four sources, one row per symbol with every source that named it. Non-US exchanges and warrant/unit/right debris are excluded and COUNTED."""
    sources = sources or {"fmp_page0": src_fmp_page0, "alpaca_inactive": src_alpaca_inactive, "aqe_panel_stale": src_aqe_panel_stale, "aqe_git_universe": src_aqe_git_universe}
    info: dict = {"sources": {}, "excluded": {"non_us_exchange": 0, "derivative_name_or_symbol": 0, "blank_symbol": 0}}
    merged: dict[str, dict] = {}
    for name, fn in sources.items():
        rows, err = fn(client)
        info["sources"][name] = {"rows": len(rows), "error": err}
        for r in rows:
            sym = norm_symbol(r.get("symbol"))
            if not sym:
                info["excluded"]["blank_symbol"] += 1
                continue
            ex = (r.get("exchange") or "").upper()
            if ex and ex not in US_EXCHANGES:
                info["excluded"]["non_us_exchange"] += 1
                continue
            nm = r.get("name") or ""
            if (nm and DERIVATIVE_NAME.search(nm)) or (not nm and DERIVATIVE_SYMBOL.match(sym)):
                info["excluded"]["derivative_name_or_symbol"] += 1
                continue
            m = merged.setdefault(sym, {"symbol": sym, "name": None, "exchange": None, "delisted_date_listed": None, "sources": []})
            m["name"] = m["name"] or nm or None
            m["exchange"] = m["exchange"] or ex or None
            m["delisted_date_listed"] = m["delisted_date_listed"] or r.get("delisted_date")
            if name not in m["sources"]:
                m["sources"].append(name)
    df = pd.DataFrame(sorted(merged.values(), key=lambda m: m["symbol"]))
    if len(df):
        df["sources"] = df["sources"].map(lambda s: ",".join(s))
    else:
        df = pd.DataFrame(columns=["symbol", "name", "exchange", "delisted_date_listed", "sources"])
    info["candidates"] = int(len(df))
    info["by_source_after_filters"] = {n: int(df["sources"].str.contains(n).sum()) for n in info["sources"]} if len(df) else {}
    return df, info


# ------------------------------------------------------------------ per-name pull
class FMP404(Exception):
    pass


def _get_retry(client, url: str, params: dict, tries: int = 3, wait_s: float = 5.0, sleep=None):
    """FMP 404 -> FMP404 (unknown symbol, not a failure); 5xx -> retry (a transient 502 lost a name in the first shard run); anything else propagates."""
    import time
    from src.data.fmp_client import FMPError, FMPQuotaError
    for k in range(tries):
        try:
            return client._get_json(url, params)
        except FMPQuotaError:
            raise
        except FMPError as e:
            msg = str(e)
            if "HTTP 404" in msg or "HTTP 402" in msg:      # 404 = unknown symbol / empty window; 402 'Premium Query Parameter' = a symbol FMP gates (preferreds, when-issued)
                raise FMP404(msg) from e
            if "HTTP 5" in msg and k < tries - 1:
                (sleep or time.sleep)(wait_s)
                continue
            raise


def bars_frame(client, t: str, since: str, today: date) -> pd.DataFrame:
    data = _get_retry(client, f"{RX.STABLE}/historical-price-eod/full", {"symbol": t, "from": since, "to": today.isoformat(), "apikey": client.config.api_key})
    data = data if isinstance(data, list) else []
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    keep = [c for c in ("date", "open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for c in ("open", "high", "low", "close"):
        if c in df.columns:
            df[c] = df[c].astype("float64")
    df["volume"] = df["volume"].fillna(0).astype("int64") if "volume" in df.columns else 0
    df.insert(0, "ticker", t)
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def month_end(rows: list[dict]) -> pd.DataFrame:
    """Reduce a daily market-cap series to the last available row of each month."""
    if not rows:
        return pd.DataFrame(columns=["ticker", "date", "market_cap"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.dropna(subset=["market_cap"]).sort_values("date")
    df["ym"] = df["date"].dt.to_period("M")
    return df.groupby(["ticker", "ym"], as_index=False).tail(1).drop(columns="ym").reset_index(drop=True)


def classify(df_bars: pd.DataFrame, today: date) -> str:
    if df_bars.empty:
        return "no_bars_in_window"
    last = df_bars["date"].max().date()
    return "still_trading" if (today - last).days <= STALE_DAYS else "delisted_with_bars"


def mcap_windows(client, t: str, since: str, last: date, diag: dict | None = None) -> list[dict]:
    """Daily market cap per year window up to the name's last bar. A 404 on a window is an EMPTY window (FMP serves 404 where it has no rows), never a failure of the name;
    the first cut let one empty window fail the whole name (all 234 delisted names in shard 1 lost their market cap, run 44922269216). The first cut called /historical-market-cap, which FMP does not serve on REST (the MCP
    tool's name, not the path): the documented path is /historical-market-capitalization. Every window's outcome is tallied in `diag` so the meta shows which path answered."""
    out = []
    d = diag if diag is not None else {}
    for a, b in RX.year_windows(since, last):
        base = {"symbol": t, "from": a.isoformat(), "to": b.isoformat(), "limit": 400, "apikey": client.config.api_key}
        d["windows"] = d.get("windows", 0) + 1
        data, hit = None, False
        for ep in MCAP_ENDPOINTS:                  # the documented path first; the old guess second (kept only so the meta shows which one answers)
            try:
                data = _get_retry(client, f"{RX.STABLE}/{ep}", base)
                d[f"ok_{ep}"] = d.get(f"ok_{ep}", 0) + 1
                hit = True
                break
            except FMP404:
                continue
        if not hit:
            d["empty_404"] = d.get("empty_404", 0) + 1
            d.setdefault("first_404", f"{a}..{b}")
            continue
        out += [{"ticker": t, "date": r.get("date"), "market_cap": r.get("marketCap")} for r in (data if isinstance(data, list) else [])]
    return out


def pull_one(client, t: str, since: str, today: date, cls: dict):
    try:
        b = bars_frame(client, t, since, today)
    except FMP404 as e:                      # FMP does not serve this symbol (CUSIP-style Alpaca ids, preferreds, when-issued): counted, with the reason
        cls[t] = {"class": "no_bars_in_window", "first_bar": None, "last_bar": None, "bars": 0, "reason": ("fmp_402_premium_symbol" if "HTTP 402" in str(e) else "fmp_404_unknown_symbol")}
        return []
    c = classify(b, today)
    cls[t] = {"class": c, "first_bar": str(b["date"].min().date()) if len(b) else None, "last_bar": str(b["date"].max().date()) if len(b) else None, "bars": int(len(b)),
              "reason": None if len(b) else "fmp_empty_response"}
    if c != "delisted_with_bars":
        return []
    last = b["date"].max().date()
    dg: dict = {}
    m = month_end(mcap_windows(client, t, since, last, dg))
    cls[t]["mcap_months"] = int(len(m))
    cls[t]["mcap_diag"] = json.dumps(dg)
    return [{"ticker": t, "bars": b, "mcap": m}]


def _write(df: pd.DataFrame, name: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    df.to_parquet(p, index=False, compression="zstd")
    return EH._drive_put(name, p.read_bytes(), "application/octet-stream")


def run(stage: str, since: str, budget_h: float, shard: tuple[int, int]) -> int:
    from src.data.fmp_client import FMPClient
    client = FMPClient()
    cand, info = build_candidates(client)
    suffix = f"_s{shard[0]}of{shard[1]}" if shard[1] > 1 else ""
    ids = [_write(cand, f"aqe_research_survivorship_PARTIAL_candidates{suffix}.parquet")]
    meta = {"schema": "aqe_research_survivorship.v1", "partial_survivorship": True, "PARTIAL": PARTIAL_NOTE, "generated_at": _now(), "stage": stage, "since": since,
            "shard": list(shard), "list_sources": info["sources"], "candidates_total": info["candidates"], "candidates_by_source_after_filters": info["by_source_after_filters"],
            "excluded": info["excluded"],
            "thin_list_warning": "Alpaca's inactive list is thin before ~2019 and misses some mergers; FMP Starter gives only the latest 100 delistings."}
    if all(v["error"] for v in info["sources"].values()):
        meta["status"] = "failed"
        print("EVERY candidate source failed (loud)", file=sys.stderr)
    elif stage == "list":
        meta["status"] = "ok" if not any(v["error"] for v in info["sources"].values()) else "partial"
    else:
        today = date.today()
        names = RX.shard(cand["symbol"].tolist(), *shard)
        cls: dict = {}
        pulled = RX._loop(client, names, lambda t: pull_one(client, t, since, today, cls), budget_h * 3600)
        objs = pulled["rows"]
        bars = pd.concat([o["bars"] for o in objs], ignore_index=True) if objs else pd.DataFrame()
        mcap = pd.concat([o["mcap"] for o in objs if len(o["mcap"])], ignore_index=True) if any(len(o["mcap"]) for o in objs) else pd.DataFrame()
        if len(bars):
            bars["ticker"] = bars["ticker"].astype("category")
            ids.append(_write(bars, f"aqe_research_survivorship_PARTIAL_bars_daily{suffix}.parquet"))
        if len(mcap):
            ids.append(_write(mcap, f"aqe_research_survivorship_PARTIAL_mcap_monthend{suffix}.parquet"))
        tally = pd.Series([v["class"] for v in cls.values()]).value_counts().to_dict() if cls else {}
        ids.append(_write(pd.DataFrame([{"symbol": k} | v for k, v in cls.items()]), f"aqe_research_survivorship_PARTIAL_classification{suffix}.parquet")) if cls else None
        last_years = pd.Series([v["last_bar"][:4] for v in cls.values() if v["class"] == "delisted_with_bars"]).value_counts().sort_index().to_dict() if cls else {}
        meta |= {"names_in_this_shard": len(names), "classification": tally,
                 "delisted_names_with_bars_in_window": int(tally.get("delisted_with_bars", 0)),
                 "still_trading_excluded": int(tally.get("still_trading", 0)), "no_bars_in_window": int(tally.get("no_bars_in_window", 0)),
                 "delisted_by_last_bar_year": {str(k): int(v) for k, v in last_years.items()},
                 "no_bars_reasons": {str(k): int(v) for k, v in pd.Series([v.get("reason") for v in cls.values() if v["class"] == "no_bars_in_window"]).value_counts().items()} if cls else {},
                 "mcap_window_outcomes": {k: int(sum(json.loads(v.get("mcap_diag") or "{}").get(k, 0) for v in cls.values())) for k in ("windows", "empty_404") + tuple(f"ok_{e}" for e in MCAP_ENDPOINTS)} if cls else {},
                 "mcap_first_404_examples": [{"symbol": k, "window": json.loads(v["mcap_diag"]).get("first_404")} for k, v in list(cls.items()) if v.get("mcap_diag") and json.loads(v["mcap_diag"]).get("first_404")][:10],
                 "delisted_without_mcap": sorted(k for k, v in cls.items() if v["class"] == "delisted_with_bars" and not v.get("mcap_months")),
                 "bar_rows": int(len(bars)), "mcap_monthend_rows": int(len(mcap)),
                 "gaps": {"aborted": pulled["aborted"], "failed_tickers": pulled["failed"], "tickers_with_no_rows_or_excluded": len(pulled["empty"])}}
        meta["status"] = "failed" if not len(bars) else ("partial" if (pulled["failed"] or pulled["aborted"]) else "ok")
    OUT.mkdir(parents=True, exist_ok=True)
    mp = OUT / f"aqe_research_survivorship_PARTIAL_meta{suffix}.json"
    mp.write_text(json.dumps(meta, indent=1, default=str))
    ids.append(EH._drive_put(mp.name, mp.read_bytes(), "application/json"))
    (OUT / "drive_ids.json").write_text(json.dumps({x["name"]: x for x in ids if x}, indent=1))
    print(json.dumps({k: meta.get(k) for k in ("status", "candidates_total", "delisted_names_with_bars_in_window", "still_trading_excluded", "no_bars_in_window")} | {"drive": ids}, default=str), flush=True)
    return 0 if meta["status"] != "failed" else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["list", "pull"])
    ap.add_argument("--since", default=SINCE_DEFAULT)
    ap.add_argument("--budget-hours", type=float, default=5.0)
    ap.add_argument("--shard", default="1/1")
    a = ap.parse_args(argv)
    i, n = (int(x) for x in a.shard.split("/"))
    assert 1 <= i <= n, a.shard
    return run(a.stage, a.since, a.budget_hours, (i, n))


if __name__ == "__main__":
    raise SystemExit(main())
