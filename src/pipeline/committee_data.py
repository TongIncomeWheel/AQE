"""The committee's FMP inputs, fetched by CODE inside the daily AQE run (PM 2026-11-03).

Before this, three things the Aegis committee reads were pulled by model "couriers" at GATHER: the weekly /
daily / 1-hour grid's bars, the scorecard's closes, and the fundamentals pack. On 3 Nov the couriers cost 1.51M
of the 3.25M metered tokens (46%) and caused real defects: hand-transcribed fundamentals, hourly series matched
to tickers by best price fit, parallel-call filename collisions, 15-minute pulls loaded into the conductor's
context. Fetching is mechanical. It belongs in code, run where the secret is (this job has FMP_API_KEY; the
conductor's sandbox has none).

WHAT IT WRITES  (aegis/output/committee_data/, read by the conductor by path; schemas in
aegis/plugin/aegis-core/contracts/committee_data/)
  fundamentals_pack.json   fundamentals_pack.v1  one entry per export name, the same fields the couriers returned
  mtf_grid.json            mtf_grid.v1           the W / D / H1 row for every export name (mtf.py build_name)
  closes_scorecard.json    closes_scorecard.v1   {ticker: {date: close}} exactly as pma_scorecard.py --closes reads it
  manifest.json            committee_data_manifest.v1  written LAST: per file sha256 / bytes / rows / served / unserved
                                                       / as_of, the run's status, every error, the FMP call count

SCOPE.  The room is only known after RANK, hours after this runs, so this fetches a SUPERSET: every export row
(daily_list) plus every held position, about 258 names. Trade-off, stated: ~258 hourly calls plus the
fundamentals refresh (below) is about 5 minutes on the Actions runner's 80 calls/min, against a post-RANK
workflow dispatch that would fetch ~50 names but needs the conductor to trigger and wait for a workflow in the
middle of its run (a new failure mode, and dispatch rights it does not need). The superset wins; the
fundamentals carry-forward keeps the cost down.

FUNDAMENTALS CARRY-FORWARD.  Ratios and growth move quarterly. An entry from the previous pack that is fully
served and younger than FUND_MAX_AGE_DAYS is carried (status "carried", its own pulled_on date kept, so its age
is never hidden); a partial, unserved, new or older name is refetched. First run with no previous pack: every
name is fetched (~13 min at 80 calls/min), inside TIME_BUDGET_S.

LOUD, NEVER SILENT.  Every symbol carries a status. A call that errors, a payload of the wrong shape, an empty
answer and an exhausted time budget are each recorded against the symbol with the reason; nothing is filled from
memory or from a neighbour. The manifest's status is OK only when every file is above MIN_COVERAGE; PARTIAL when a
file is produced but thin; FAILED when it could not run at all - and FAILED still writes a manifest, so a failed
run is a file that says so, not a missing one. tools/check.py (daily-check) turns each of these into a FAIL line.

Nothing here places an order, sizes a position or forms a view.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.data.paths import OUTPUT_DIR, DATA_DIR, PROJECT_ROOT

REPO_DIR = "aegis/output/committee_data"
LOCAL_DIR = OUTPUT_DIR / "committee_data"
FILES = {"fundamentals_pack.json": "fundamentals_pack.v1",
         "mtf_grid.json": "mtf_grid.v1",
         "closes_scorecard.json": "closes_scorecard.v1"}
MANIFEST = "manifest.json"
MANIFEST_SCHEMA = "committee_data_manifest.v1"

FUND_MAX_AGE_DAYS = 5          # a fully served entry younger than this is carried, with its own date
MIN_COVERAGE = 0.95            # ONE rule (conductor + engineering 2026-11-03): any file under 95% served = PARTIAL = check.py FAILs (stop and page); at or above it, per-name gaps are declared and the run proceeds
TIME_BUDGET_S = 900            # stop fetching after this; the rest are declared, not dropped quietly
HOURLY_LOOKBACK_DAYS = 45      # ~30 sessions of 1-hour bars (7 per session)
DAILY_SESSIONS = 300           # for the weekly bars
DAILY_FETCH_DAYS = 470         # calendar days asked of FMP for a name the panel does not hold
CLOSES_LOOKBACK_DAYS = 45
BENCH = "SPY"

PROFILE_KEEP = ("sector", "industry", "marketCap", "beta", "range")
RATIO_KEEP = ("priceToEarningsRatioTTM", "priceToBookRatioTTM", "debtToEquityRatioTTM", "dividendYieldTTM",
              "grossProfitMarginTTM", "operatingProfitMarginTTM", "netProfitMarginTTM",
              "priceToFreeCashFlowRatioTTM")
GROWTH_KEEP = ("date", "growthRevenue", "growthEPS")
GROWTH_YEARS = 3

SGT = ZoneInfo("Asia/Singapore")


# ------------------------------------------------------------------------------------------ helpers
def _mtf():
    """mtf.py is plugin code; the nightly job imports the generated runtime copy by path (like pma_pipeline)."""
    for rel in ("aegis/skills/premarket-analysis/tools/mtf.py",
                "aegis/plugin/aegis-core/skills/pma/tools/mtf.py"):
        p = PROJECT_ROOT / rel
        if p.exists():
            spec = importlib.util.spec_from_file_location("committee_mtf", p)
            m = importlib.util.module_from_spec(spec)
            sys.modules["committee_mtf"] = m
            spec.loader.exec_module(m)
            return m
    raise RuntimeError("mtf.py not found (aegis/skills/premarket-analysis/tools or the plugin tree)")


def dumps(doc) -> bytes:
    """The bytes written AND hashed: compact, sorted keys, so the same content is the same sha256."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_of(obj) -> str:
    return hashlib.sha256(dumps(obj)).hexdigest()


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def scope_of(export: dict) -> list[str]:
    """Every export row plus every held position: the superset the room will be drawn from."""
    out = {r.get("ticker") for r in (export.get("daily_list") or []) if isinstance(r, dict)}
    out |= {r.get("ticker") for r in (export.get("held_positions") or []) if isinstance(r, dict)}
    return sorted(t for t in out if t)


class Fetcher:
    """One FMP session: counts calls, enforces the time budget, turns every failure into a reason string."""

    def __init__(self, client, budget_s: float = TIME_BUDGET_S, clock=time.monotonic):
        self.client, self.budget_s, self.clock = client, budget_s, clock
        self.t0 = clock()
        self.calls = 0
        self.errors: list[str] = []
        self.quota_hit = False
        self._budget_noted = False

    def exhausted(self) -> bool:
        return self.clock() - self.t0 > self.budget_s

    def get(self, path: str, **params):
        """-> (payload, None) or (None, reason). Never raises."""
        if self.quota_hit:
            return None, "FMP quota/key refused earlier in this run"
        if self.exhausted():
            if not self._budget_noted:
                self._budget_noted = True
                self.errors.append(f"time budget {self.budget_s:.0f}s exhausted after {self.calls} calls; "
                                   f"every later symbol is declared unserved, not fetched")
            return None, f"time budget {self.budget_s:.0f}s exhausted before this call"
        from src.data.fmp_client import FMP_BASE_STABLE, FMPError, FMPQuotaError
        self.calls += 1
        try:
            payload = self.client._get_json(f"{FMP_BASE_STABLE}/{path}",
                                            params={**params, "apikey": self.client.config.api_key})
        except FMPQuotaError as e:
            self.quota_hit = True
            self.errors.append(f"{path} {params.get('symbol', '')}: {e}")
            return None, f"FMP quota/key: {e}"
        except FMPError as e:
            self.errors.append(f"{path} {params.get('symbol', '')}: {e}")
            return None, str(e)[:200]
        except Exception as e:  # noqa: BLE001 - a fetch bug must not take the daily run down
            self.errors.append(f"{path} {params.get('symbol', '')}: {e.__class__.__name__}: {e}")
            return None, f"{e.__class__.__name__}: {e}"[:200]
        return payload, None


# ------------------------------------------------------------------------------------ fundamentals
def fetch_fundamentals_one(f: Fetcher, t: str, today: str) -> dict:
    """The same three parts the couriers returned: profile, ratios_ttm, growth_3y - plus a status."""
    raw, missing, reasons = {}, [], {}
    for part, path, params in (("profile", "profile", {"symbol": t}),
                               ("ratios_ttm", "ratios-ttm", {"symbol": t}),
                               ("growth_3y", "income-statement-growth", {"symbol": t, "limit": GROWTH_YEARS})):
        payload, err = f.get(path, **params)
        if err is None and not (isinstance(payload, list) and payload and isinstance(payload[0], dict)):
            err = "empty or unexpected payload"
        if err:
            missing.append(part)
            reasons[part] = err
        else:
            raw[part] = payload
    entry: dict = {"pulled_on": today}
    if "profile" in raw:
        p = raw["profile"][0]
        entry["profile"] = {**{k: p.get(k) for k in PROFILE_KEEP}, "source": "FMP profile", "date": today}
    if "ratios_ttm" in raw:
        r = raw["ratios_ttm"][0]
        entry["ratios_ttm"] = {**{k: r.get(k) for k in RATIO_KEEP}, "source": "FMP ratios-ttm"}
    if "growth_3y" in raw:
        entry["growth_3y"] = [{k: g.get(k) for k in GROWTH_KEEP} for g in raw["growth_3y"][:GROWTH_YEARS]]
    entry["unserved"] = len(raw) == 0
    entry["status"] = ("unserved" if not raw else ("partial" if missing else "served"))
    if missing:
        entry["missing"] = missing
        entry["reasons"] = reasons
    entry["sha256"] = sha256_of(raw)
    return entry


def build_fundamentals(f: Fetcher, tickers: list[str], today: str, previous: dict | None) -> dict:
    prev = (previous or {}).get("tickers") or {}
    out, carried = {}, 0
    for t in tickers:
        old = prev.get(t)
        if isinstance(old, dict) and old.get("status") in ("served", "carried") and old.get("pulled_on"):
            try:
                age = (date.fromisoformat(today) - date.fromisoformat(old["pulled_on"])).days
            except ValueError:
                age = 10 ** 6
            if 0 <= age < FUND_MAX_AGE_DAYS:
                out[t] = {**old, "status": "carried", "age_days": age}
                carried += 1
                continue
        out[t] = fetch_fundamentals_one(f, t, today)
    served = sum(1 for e in out.values() if e["status"] in ("served", "carried"))
    partial = sorted(t for t, e in out.items() if e["status"] == "partial")
    unserved = sorted(t for t, e in out.items() if e["status"] == "unserved")
    return {"schema": "fundamentals_pack.v1", "run_date": today, "as_of": today,
            "source": "FMP stable REST (profile, ratios-ttm, income-statement-growth) via src/pipeline/committee_data.py",
            "coverage": {"requested": len(tickers), "served": served, "carried": carried, "partial": len(partial),
                         "unserved": len(unserved), "partial_names": partial, "unserved_names": unserved},
            "tickers": out}


# ---------------------------------------------------------------------------------------- bars / grid
def load_panel_daily(tickers: list[str], sessions: int = DAILY_SESSIONS) -> dict[str, list[dict]]:
    """Daily bars the nightly job already holds (panel_daily.parquet): no FMP call for names it carries."""
    import pandas as pd
    p = DATA_DIR / "panel_daily.parquet"
    if not p.exists():
        return {}
    df = pd.read_parquet(p, columns=["date", "ticker", "open", "high", "low", "close", "volume"])
    df = df[df["ticker"].isin(set(tickers))]
    out = {}
    for t, g in df.groupby("ticker"):
        g = g.sort_values("date").tail(sessions)
        out[t] = [{"date": str(d)[:10], "open": float(o), "high": float(h), "low": float(l), "close": float(c),
                   "volume": float(v)} for d, o, h, l, c, v in
                  zip(g["date"], g["open"], g["high"], g["low"], g["close"], g["volume"])]
    return out


def fetch_daily_one(f: Fetcher, t: str, run_date: str) -> tuple[list[dict], dict]:
    frm = (date.fromisoformat(run_date) - timedelta(days=DAILY_FETCH_DAYS)).isoformat()
    payload, err = f.get("historical-price-eod/full", symbol=t, **{"from": frm, "to": run_date})
    if err or not isinstance(payload, list) or not payload:
        return [], {"source": "fmp", "rows": 0, "error": err or "empty or unexpected payload"}
    bars = [{"date": b.get("date"), "open": b.get("open"), "high": b.get("high"), "low": b.get("low"),
             "close": b.get("close"), "volume": b.get("volume")} for b in payload if isinstance(b, dict)]
    bars.sort(key=lambda b: str(b["date"]))
    return bars, {"source": "fmp", "rows": len(bars), "last_bar": bars[-1]["date"], "sha256": sha256_of(payload)}


def fetch_hourly_one(f: Fetcher, t: str, run_date: str, mtf) -> tuple[list[dict], dict]:
    """Native 1hour first (FMP's own :30-anchored bars); on an error or an empty answer, 15-minute bars rolled up
    by mtf.rollup_hourly. The source used is recorded so nobody has to guess which one a reading came from."""
    frm = (date.fromisoformat(run_date) - timedelta(days=HOURLY_LOOKBACK_DAYS)).isoformat()
    payload, err = f.get("historical-chart/1hour", symbol=t, **{"from": frm, "to": run_date})
    if err is None and isinstance(payload, list) and payload:
        bars = mtf._clean(payload)
        return bars, {"source": "1hour", "rows": len(bars), "last_bar": bars[-1]["date"] if bars else None,
                      "sha256": sha256_of(payload)}
    why = err or "empty answer"
    payload, err2 = f.get("historical-chart/15min", symbol=t, **{"from": frm, "to": run_date})
    if err2 is None and isinstance(payload, list) and payload:
        bars, dropped = mtf.rollup_hourly(mtf._clean(payload))
        return bars, {"source": "15min_rollup", "rows": len(bars), "last_bar": bars[-1]["date"] if bars else None,
                      "fallback_because": f"1hour: {why}", "m15_bars_not_used": dropped, "sha256": sha256_of(payload)}
    return [], {"source": "none", "rows": 0, "error": f"1hour: {why}; 15min: {err2 or 'empty answer'}"}


def build_grid(f: Fetcher, tickers: list[str], run_date: str, export: dict, panel: dict, mtf,
               daily_cache: dict | None = None) -> dict:
    """`daily_cache`, when given, is filled with each name's daily bars so the closes step reuses them instead of
    paying for the same FMP call twice (the runner is limited to ~80 calls a minute)."""
    closes = {r.get("ticker"): r.get("entry") for r in (export.get("daily_list") or []) if isinstance(r, dict)}
    names, daily_src = {}, {"panel": 0, "fmp": 0, "none": 0}
    for t in tickers:
        daily, dmeta = (panel.get(t) or []), {"source": "panel", "rows": len(panel.get(t) or [])}
        if daily:
            dmeta["last_bar"] = daily[-1]["date"]
        else:
            daily, dmeta = fetch_daily_one(f, t, run_date)
        if daily_cache is not None and daily and dmeta["source"] != "panel":
            daily_cache[t] = daily          # only bars FMP gave us; panel bars are read from the panel again, labelled so
        daily_src[dmeta["source"] if daily else "none"] += 1
        hourly, hmeta = fetch_hourly_one(f, t, run_date, mtf)
        if not daily and not hourly:
            row = mtf._not_served(f"no daily and no hourly bars could be fetched for {t} "
                                  f"(daily: {dmeta.get('error')}; hourly: {hmeta.get('error')})")
        else:
            row = mtf.build_name(t, {"daily": daily, "h1": hourly}, run_date, closes.get(t))
        row["fetch"] = {"daily": dmeta, "hourly": hmeta}
        names[t] = row
    served = sum(1 for r in names.values() if r["served"])
    complete = sum(1 for r in names.values() if r.get("complete"))
    return {"schema": "mtf_grid.v1", "run_date": run_date, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "frames": list(mtf.FRAMES), "names": names,
            "sha256_of_names": sha256_of(names),
            "coverage": {"requested": len(tickers), "served": served, "complete": complete,
                         "not_served": len(tickers) - served,
                         "not_served_names": sorted(t for t, r in names.items() if not r["served"]),
                         "daily_source": daily_src,
                         "hourly_native": sum(1 for r in names.values() if r["fetch"]["hourly"]["source"] == "1hour"),
                         "hourly_rolled_up": sum(1 for r in names.values() if r["fetch"]["hourly"]["source"] == "15min_rollup"),
                         "hourly_none": sum(1 for r in names.values() if r["fetch"]["hourly"]["source"] == "none")}}


# ------------------------------------------------------------------------------------------- closes
def ledger_tickers(run_date: str, lookback_days: int = CLOSES_LOOKBACK_DAYS,
                   path: Path | None = None) -> list[str]:
    p = path or (PROJECT_ROOT / "data" / "pma" / "verdict_ledger.json")
    if not p.exists():
        return []
    try:
        L = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return []
    rows = L.get("rows") if isinstance(L, dict) else L
    start = (date.fromisoformat(run_date) - timedelta(days=lookback_days)).isoformat()
    return sorted({r.get("ticker") for r in rows or [] if isinstance(r, dict) and r.get("ticker")
                   and str(r.get("date", ""))[:10] >= start})


def build_closes(f: Fetcher, tickers: list[str], run_date: str, panel_all: dict,
                 fetched: dict | None = None) -> tuple[dict, dict]:
    """-> ({ticker: {date: close}, "_missing": [...]}, detail{ticker: source}).
    Source order, each labelled truthfully: the panel; the daily bars the grid step already fetched from FMP
    (`fetched`, no second call); a fresh FMP call."""
    start = (date.fromisoformat(run_date) - timedelta(days=CLOSES_LOOKBACK_DAYS)).isoformat()
    out, detail, missing = {}, {}, []
    for t in tickers:
        bars = [b for b in (panel_all.get(t) or []) if start <= b["date"] <= run_date]
        src = "panel"
        if not bars:
            bars = [b for b in ((fetched or {}).get(t) or []) if start <= str(b["date"])[:10] <= run_date]
            src = "fmp"
        if not bars:
            raw, err = f.get("historical-price-eod/full", symbol=t, **{"from": start, "to": run_date})
            if err is None and isinstance(raw, list) and raw:
                bars = [{"date": b.get("date"), "close": b.get("close")} for b in raw if isinstance(b, dict)]
                src = "fmp"
            else:
                detail[t] = {"source": "none", "error": err or "empty answer"}
                missing.append(t)
                continue
        closes = {str(b["date"])[:10]: round(float(b["close"]), 4) for b in bars if _num(b.get("close"))}
        if not closes:
            detail[t] = {"source": src, "error": "no numeric closes"}
            missing.append(t)
            continue
        out[t] = dict(sorted(closes.items()))
        detail[t] = {"source": src, "rows": len(closes), "last": max(closes)}
    out["_missing"] = sorted(missing)
    return out, detail


# ----------------------------------------------------------------------------------------- manifest
def _file_entry(name: str, body: bytes, schema: str, rows: int, served: int, unserved: int, as_of: str) -> dict:
    return {"schema": schema, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "rows": rows,
            "served": served, "unserved": unserved, "as_of": as_of}


def status_of(files: dict) -> str:
    """OK only when every file is above MIN_COVERAGE; PARTIAL when thin; FAILED when a file is absent."""
    if not files or any(n not in files for n in FILES):
        return "FAILED"
    for e in files.values():
        total = e["served"] + e["unserved"]
        if total and e["served"] / total < MIN_COVERAGE:
            return "PARTIAL"
    return "OK"


def failed_manifest(run_date: str, reason: str, f: Fetcher | None = None) -> dict:
    return {"schema": MANIFEST_SCHEMA, "run_date": run_date, "status": "FAILED", "reason": reason,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "files": {},
            "fmp_calls": f.calls if f else 0, "errors": (f.errors[:50] if f else [])}


def run(export: dict, run_date: str | None = None, client=None, panel: dict | None = None,
        previous_pack: dict | None = None, ledger: list[str] | None = None,
        budget_s: float = TIME_BUDGET_S, clock=time.monotonic) -> dict:
    """Fetch, build and return {manifest, files{name: bytes}}. Never raises: any failure is a FAILED manifest."""
    run_date = run_date or datetime.now(SGT).date().isoformat()
    f = None
    try:
        if client is None:
            from src.data.fmp_client import FMPClient
            client = FMPClient()
        f = Fetcher(client, budget_s=budget_s, clock=clock)
        mtf = _mtf()
        tickers = scope_of(export)
        if not tickers:
            return {"manifest": failed_manifest(run_date, "the export has no daily_list rows to fetch for", f), "files": {}}
        panel = panel if panel is not None else load_panel_daily(sorted(set(tickers) | {BENCH} | set(ledger or [])))
        fund = build_fundamentals(f, tickers, run_date, previous_pack)
        daily_cache: dict = {}
        grid = build_grid(f, tickers, run_date, export, panel, mtf, daily_cache)
        led = ledger if ledger is not None else ledger_tickers(run_date)
        # the closes step prefers the bars already in hand (panel, else the daily series the grid just fetched)
        closes, cdetail = build_closes(f, sorted(set(led) | set(tickers) | {BENCH}), run_date, panel, daily_cache)
        bodies = {"fundamentals_pack.json": dumps(fund), "mtf_grid.json": dumps(grid), "closes_scorecard.json": dumps(closes)}
        fc, gc = fund["coverage"], grid["coverage"]
        n_closes = len([k for k in closes if k != "_missing"])
        files = {
            "fundamentals_pack.json": _file_entry("fundamentals_pack.json", bodies["fundamentals_pack.json"], "fundamentals_pack.v1",
                                                  fc["requested"], fc["served"], fc["unserved"] + fc["partial"], run_date),
            # "served" here is COMPLETE rows (W, D and H1 all read): daily bars come from the panel, so a total
            # hourly failure would otherwise still read as 100% served.
            "mtf_grid.json": _file_entry("mtf_grid.json", bodies["mtf_grid.json"], "mtf_grid.v1",
                                         gc["requested"], gc["complete"], gc["requested"] - gc["complete"], run_date),
            "closes_scorecard.json": _file_entry("closes_scorecard.json", bodies["closes_scorecard.json"], "closes_scorecard.v1",
                                                 n_closes + len(closes["_missing"]), n_closes, len(closes["_missing"]), run_date)}
        status = status_of(files)
        # A refused key or an exhausted budget is NOT a status of its own: it shows up as unserved names. The status is
        # the coverage test alone (under 95% on any file = PARTIAL); the two flags ride in the manifest and the WARN line.
        manifest = {"schema": MANIFEST_SCHEMA, "run_date": run_date, "status": status,
                    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "scope": {"requested": len(tickers), "from": "export daily_list + held_positions"},
                    "files": files, "fmp_calls": f.calls, "elapsed_s": round(clock() - f.t0, 1),
                    "time_budget_exhausted": f.exhausted(), "quota_hit": f.quota_hit,
                    "closes_detail": cdetail, "errors": f.errors[:50], "errors_total": len(f.errors)}
        return {"manifest": manifest, "files": bodies}
    except Exception as e:  # noqa: BLE001 - FAILED is a file that says so; it must not take the export down
        return {"manifest": failed_manifest(run_date, f"{e.__class__.__name__}: {e}", f), "files": {}}


# ---------------------------------------------------------------------------------------- publishing
def write_local(result: dict, out_dir: Path | None = None) -> Path:
    d = Path(out_dir or LOCAL_DIR)
    d.mkdir(parents=True, exist_ok=True)
    for name, body in result["files"].items():
        (d / name).write_bytes(body)
    (d / MANIFEST).write_bytes(dumps(result["manifest"]))     # last: the marker that the set is complete
    return d


def publish(result: dict, put_file=None) -> dict:
    """Push the files, then the manifest LAST, to aegis/output/committee_data/ on main. A file that does not
    land is named; if the manifest does not land the whole publish is failed (a stale manifest beside new files
    would pass for a consistent set)."""
    if put_file is None:
        from src.data import github_sync
        if not github_sync.is_configured():
            return {"ok": False, "reason": "GitHub not configured", "written": 0, "total": 0,
                    "failed": ["GitHub not configured - nothing was published"], "manifest_landed": False}
        put_file = github_sync.put_file
    run_date = result["manifest"].get("run_date")
    items = list(result["files"].items()) + [(MANIFEST, dumps(result["manifest"]))]
    written, failed = 0, []
    for name, body in items:
        try:
            r = put_file(f"{REPO_DIR}/{name}", body.decode("utf-8"), f"committee data {run_date}: {name}")
        except Exception as e:  # noqa: BLE001
            r = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        if r.get("ok"):
            written += 1
        else:
            failed.append(f"{name}: {r.get('error') or r.get('reason') or 'put failed'}")
    return {"ok": not failed, "written": written, "total": len(items), "failed": failed,
            "manifest_landed": not any(x.startswith(MANIFEST) for x in failed)}


def summary_line(result: dict, pub: dict | None = None) -> str:
    m = result["manifest"]
    if m["status"] == "FAILED":
        return f"Committee data FAILED: {m.get('reason')}"
    fl = m["files"]
    s = (f"Committee data {m['status']}: fundamentals {fl['fundamentals_pack.json']['served']}/{m['scope']['requested']}, "
         f"mtf {fl['mtf_grid.json']['served']}/{m['scope']['requested']}, "
         f"closes {fl['closes_scorecard.json']['served']}/{fl['closes_scorecard.json']['rows']}, "
         f"{m['fmp_calls']} FMP calls, {m['elapsed_s']}s")
    if pub is not None:
        s += f"; published {pub['written']}/{pub['total']}" + (f" (FAILED: {'; '.join(pub['failed'])})" if pub["failed"] else "")
    return s


def describe(result: dict, top: int = 15) -> str:
    """The numbers for a job log / a report: per file served / partial / unserved, where the hourly bars came from,
    how many hourly bars per name, which fundamentals fields are filled, the errors, the run time. Plain text."""
    import statistics
    m = result["manifest"]
    L = [f"COMMITTEE DATA {m['status']}  run_date {m['run_date']}  generated {m.get('generated_at')}"]
    if m["status"] == "FAILED":
        return "\n".join(L + [f"  FAILED: {m.get('reason')}", f"  FMP calls: {m.get('fmp_calls')}"])
    L.append(f"  scope {m['scope']['requested']} names ({m['scope']['from']}); {m['fmp_calls']} FMP calls in {m['elapsed_s']}s"
             f"; quota_hit={m.get('quota_hit')} time_budget_exhausted={m.get('time_budget_exhausted')}")
    for name, e in m["files"].items():
        L.append(f"  {name:24s} served {e['served']:>4}  unserved/partial {e['unserved']:>4}  of {e['rows']:>4}  {e['bytes']:>9,} bytes  sha256 {e['sha256'][:12]}")
    docs = {n: json.loads(b) for n, b in result["files"].items()}
    F, G = docs["fundamentals_pack.json"], docs["mtf_grid.json"]
    fc = F["coverage"]
    L.append(f"  FUNDAMENTALS  served {fc['served']} (carried {fc['carried']}), partial {fc['partial']}, unserved {fc['unserved']}"
             + (f"; partial: {fc['partial_names'][:top]}" if fc["partial_names"] else "")
             + (f"; unserved: {fc['unserved_names'][:top]}" if fc["unserved_names"] else ""))
    ents = [e for e in F["tickers"].values() if e.get("status") in ("served", "carried", "partial")]
    if ents:
        fill = {}
        for part, keys in (("profile", PROFILE_KEEP), ("ratios_ttm", RATIO_KEEP)):
            for k in keys:
                have = sum(1 for e in ents if isinstance((e.get(part) or {}).get(k), (int, float, str)) and (e.get(part) or {}).get(k) not in ("", None))
                fill[f"{part}.{k}"] = have
        g_have = sum(1 for e in ents if e.get("growth_3y") and all(x.get("growthRevenue") is not None and x.get("growthEPS") is not None for x in e["growth_3y"]))
        fill["growth_3y (3 yrs, revenue+EPS)"] = g_have
        L.append(f"  fundamentals fields filled (of {len(ents)} names with any part): " + ", ".join(f"{k} {v}" for k, v in fill.items()))
    gc = G["coverage"]
    L.append(f"  MTF GRID  complete {gc['complete']}/{gc['requested']}, with a gap {gc['served'] - gc['complete']}, not served {gc['not_served']}"
             f"; hourly: {gc['hourly_native']} native, {gc['hourly_rolled_up']} rolled up from 15-min, {gc['hourly_none']} none; daily from {gc['daily_source']}")
    rows = [r["fetch"]["hourly"]["rows"] for r in G["names"].values() if r["fetch"]["hourly"]["source"] != "none"]
    if rows:
        L.append(f"  hourly bars per name: min {min(rows)} / median {int(statistics.median(rows))} / max {max(rows)}")
    gaps = {t: r["gaps"] for t, r in G["names"].items() if r.get("gaps")}
    if gaps:
        L.append(f"  names with a frame gap ({len(gaps)}): " + ", ".join(f"{t} {g}" for t, g in list(gaps.items())[:top]))
    C = docs["closes_scorecard.json"]
    L.append(f"  CLOSES  {len([k for k in C if k != '_missing'])} tickers, SPY last {max(C['SPY']) if 'SPY' in C else None}, missing {C['_missing'][:top]}")
    for e in (m.get("errors") or [])[:top]:
        L.append(f"  ERROR: {e}")
    if m.get("errors_total", 0) > top:
        L.append(f"  ... {m['errors_total']} errors in total (first {top} shown; all in manifest.json)")
    return "\n".join(L)
