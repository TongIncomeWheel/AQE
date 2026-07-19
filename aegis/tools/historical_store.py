#!/usr/bin/env python3
"""Kernel accessor + self-heal for the layered historical store (D-32 / D-40).

The store is a data-objects DB LAYERED AWAY from the daily feed — monthly OHLC per
ticker, queried ON DEMAND to ANCHOR judgement (DoR empirical return distribution,
forward-return context, sizing sanity). Never bulk-streamed into the agents' daily read.

MAINTENANCE (D-40 — who seeds a new ticker, and when):
  PRIMARY owner   = AQE (Engineering & Change desk). AQE already pulls FMP for the whole
                    universe daily; it creates/appends each universe name's monthly entry
                    as part of that pipeline. That is the durable home.
  SELF-HEAL (kernel) = the premarket orchestrator (control plane, a TOOL call — no agent)
                    reconciles the deliberation-set + held book against the store BEFORE
                    committee/Risk anchor on it. Any miss/stale name is seeded on the spot
                    from FMP. So a name never reaches deliberation un-anchored.

  WHEN:
    - New ticker  -> full-history backfill the first time it is reconciled (one FMP pull).
    - Monthly     -> a name is STALE once its last stored month is older than the last
                     completed month; the reconcile refreshes it (≈ once/month, lazily).
    - Too-new     -> < min_months (12) of history is recorded deferred and auto-included
                     once it seasons; no source can fabricate history it doesn't have.

  Seeding is DETERMINISTIC data-plane code (constitution law 4). This tool never calls a
  model and never calls a broker. FMP is the ONLY price source (matches the DoR mandate).

Data source for `seed`: daily bars JSON piped in — env-agnostic. In-session the orchestrator
pulls them via the FMP MCP (`historical-price-eod-full`); on the PC AQE uses FMP REST. Either
way the SAME resample/stats logic below is the single source of truth.

Path: env AEGIS_HIST_DIR, else data/historical/.
Usage:
  historical_store.py                         -> coverage()
  historical_store.py <TICKER>                -> stats + n_returns for one name
  historical_store.py check --list A,B,C      -> {missing, stale, ok, deferred} (read-only)
  historical_store.py check --universe <f>    -> same, tickers read from a universe.json
  historical_store.py seed <TICKER> --bars <daily.json> [--source ...]  -> write/refresh one name
"""
import json, os, sys, math
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST_DIR = os.environ.get("AEGIS_HIST_DIR", os.path.join(ROOT, "data", "historical"))
MIN_MONTHS = 12   # floor for a usable monthly return distribution


# ---------------------------------------------------------------- read API
def get(ticker):
    p = os.path.join(HIST_DIR, f"{ticker}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def monthly_returns(ticker):
    """List of month-over-month close returns (%) — the DoR/anchoring input. [] if absent."""
    o = get(ticker)
    return [m["ret_pct"] for m in o["monthly"] if m.get("ret_pct") is not None] if o else []


def stats(ticker):
    """Anchoring stats (n_months, mean, std, ann_vol) or None if the ticker isn't in the store."""
    o = get(ticker)
    return o["stats"] if o else None


def coverage():
    man = os.path.join(HIST_DIR, "manifest.json")
    return json.load(open(man)) if os.path.exists(man) else {}


# ---------------------------------------------------------------- staleness / reconcile
def _last_completed_month(today=None):
    """YYYY-MM of the most recent CLOSED month (the current month is not yet complete)."""
    today = today or date.today()
    y, m = today.year, today.month - 1
    if m == 0:
        y, m = y - 1, 12
    return f"{y:04d}-{m:02d}"


def is_stale(ticker, today=None):
    """True if the name is present but its last stored month predates the last completed month."""
    o = get(ticker)
    if not o or not o.get("monthly"):
        return False   # absent is 'missing', not 'stale'
    return o["monthly"][-1]["month"] < _last_completed_month(today)


def _deferred_set():
    """Names already known too-new (recorded in the manifest) — don't re-pull FMP daily for these."""
    return set((coverage().get("deferred_too_new") or {}).keys()) - {"note"}


def needs(tickers, today=None, with_deferred=False):
    """Reconcile a list against the store. Returns which names need a seed and why.
    missing = not in store · stale = last month too old · deferred = known too-new (< MIN_MONTHS)
    · ok = current & sufficient. seed candidates = missing + stale, PLUS deferred when
    with_deferred=True (the monthly pass, to catch names that have finally seasoned)."""
    known_new = _deferred_set()
    missing, stale, deferred, ok = [], [], [], []
    for t in tickers:
        o = get(t)
        if not o:
            (deferred if (t in known_new and not with_deferred) else missing).append(t)
        elif is_stale(t, today):
            stale.append(t)
        elif o["stats"].get("n_months", 0) < MIN_MONTHS:
            deferred.append(t)
        else:
            ok.append(t)
    return {"missing": missing, "stale": stale, "deferred": deferred, "ok": ok}


# ---------------------------------------------------------------- seed / write (shared logic)
def _norm_bars(daily):
    """Accept FMP full ({date,open,high,low,close,volume}) or light ({date,price,volume});
    return sorted list of {date, o,h,l,c, v}. Light -> o=h=l=c=price (range unknown)."""
    out = []
    for r in daily:
        d = r.get("date") or r.get("datetime")
        if not d:
            continue
        d = str(d)[:10]
        if "close" in r or "open" in r:
            o, h, l, c = r.get("open"), r.get("high"), r.get("low"), r.get("close")
        else:
            p = r.get("price"); o = h = l = c = p
        if c is None:
            continue
        out.append({"date": d, "o": o, "h": h, "l": l, "c": c, "v": r.get("volume")})
    out.sort(key=lambda x: x["date"])
    return out


def _monthly_from_daily(daily):
    """Resample normalised daily bars to month-end OHLC + MoM close return. Single source of
    truth — identical semantics to the original signal-ledger seed."""
    bars = _norm_bars(daily)
    months = {}
    for b in bars:
        ym = b["date"][:7]
        m = months.setdefault(ym, {"open": b["o"], "high": b["h"], "low": b["l"],
                                    "close": b["c"], "vol": 0.0})
        if b["h"] is not None:
            m["high"] = b["h"] if m["high"] is None else max(m["high"], b["h"])
        if b["l"] is not None:
            m["low"] = b["l"] if m["low"] is None else min(m["low"], b["l"])
        m["close"] = b["c"]                 # last close in the month
        if b["v"]:
            m["vol"] += b["v"]
    rows = []
    prev_close = None
    for ym in sorted(months):
        m = months[ym]
        ret = None if prev_close in (None, 0) else round((m["close"] - prev_close) / prev_close * 100.0, 4)
        rng = round((m["high"] - m["low"]) / m["low"] * 100.0, 4) if (m["low"] and m["high"] is not None) else None
        rows.append({"month": ym,
                     "open": round(float(m["open"]), 4) if m["open"] is not None else None,
                     "high": round(float(m["high"]), 4) if m["high"] is not None else None,
                     "low": round(float(m["low"]), 4) if m["low"] is not None else None,
                     "close": round(float(m["close"]), 4),
                     "ret_pct": ret, "range_pct": rng})
        prev_close = m["close"]
    return rows


def _stats_from_rows(rows):
    rets = [r["ret_pct"] for r in rows if r["ret_pct"] is not None]
    n = len(rets)
    if n > 1:
        mean = sum(rets) / n
        std = math.sqrt(sum((x - mean) ** 2 for x in rets) / (n - 1))   # ddof=1
    else:
        mean = rets[0] if n else None
        std = None
    return {"n_months": len(rows), "n_returns": n,
            "mean_ret_pct": round(mean, 4) if mean is not None else None,
            "std_ret_pct": round(std, 4) if std is not None else None,
            "ann_vol_pct": round(std * math.sqrt(12), 4) if std is not None else None,
            "min_ret_pct": round(min(rets), 4) if n else None,
            "max_ret_pct": round(max(rets), 4) if n else None}


def _update_manifest(ticker):
    man = os.path.join(HIST_DIR, "manifest.json")
    m = coverage() or {"tickers": [], "n_tickers": 0}
    tk = set(m.get("tickers", []))
    if ticker not in tk:
        tk.add(ticker)
        m["tickers"] = sorted(tk)
        m["n_tickers"] = len(tk)
    if ticker in (m.get("deferred_too_new") or {}):   # it finally seasoned — graduate it
        m["deferred_too_new"].pop(ticker, None)
    m["last_self_heal"] = date.today().isoformat()
    json.dump(m, open(man, "w"), indent=1)


def write_from_daily(ticker, daily, source="fmp self-heal (D-40)"):
    """Resample daily bars -> monthly and write/refresh the store entry. Returns a status dict.
    Refuses to write a below-floor sample as a usable entry (records it deferred instead)."""
    rows = _monthly_from_daily(daily)
    if len(rows) < MIN_MONTHS:
        # record it so the daily reconcile stops re-pulling FMP for a name with no 12mo yet;
        # the monthly pass (--with-deferred) re-checks and graduates it once seasoned.
        man = os.path.join(HIST_DIR, "manifest.json")
        m = coverage() or {}
        dn = m.get("deferred_too_new") or {}
        dn[ticker] = f"{len(rows)}mo as of {date.today().isoformat()} (<{MIN_MONTHS}mo floor)"
        m["deferred_too_new"] = dn
        os.makedirs(HIST_DIR, exist_ok=True)
        json.dump(m, open(man, "w"), indent=1)
        return {"ticker": ticker, "written": False, "reason": "deferred_too_new",
                "n_months": len(rows)}
    st = _stats_from_rows(rows)
    obj = {"ticker": ticker, "source": source,
           "date_range": [rows[0]["month"], rows[-1]["month"]], "stats": st, "monthly": rows}
    os.makedirs(HIST_DIR, exist_ok=True)
    json.dump(obj, open(os.path.join(HIST_DIR, f"{ticker}.json"), "w"), separators=(",", ":"))
    _update_manifest(ticker)
    return {"ticker": ticker, "written": True, "n_months": st["n_months"],
            "ann_vol_pct": st["ann_vol_pct"], "range": obj["date_range"]}


# ---------------------------------------------------------------- CLI
def _tickers_from_args(argv):
    if "--list" in argv:
        return [t.strip().upper() for t in argv[argv.index("--list") + 1].split(",") if t.strip()]
    if "--universe" in argv:
        u = json.load(open(argv[argv.index("--universe") + 1]))
        rows = u.get("names") or u.get("universe") or u.get("daily_list") or u
        return [r["ticker"] if isinstance(r, dict) else r for r in rows]
    return []


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(json.dumps({"coverage": coverage()}, indent=1)); sys.exit(0)

    if a[0] == "check":
        wd = "--with-deferred" in a   # monthly pass: also re-attempt known too-new names
        rep = needs(_tickers_from_args(a), with_deferred=wd)
        rep["seed_needed"] = rep["missing"] + rep["stale"] + (rep["deferred"] if wd else [])
        print(json.dumps(rep, indent=1)); sys.exit(0)

    if a[0] == "seed":
        ticker = a[1].upper()
        bars_path = a[a.index("--bars") + 1]
        source = a[a.index("--source") + 1] if "--source" in a else "fmp self-heal (D-40)"
        daily = json.load(open(bars_path))
        if isinstance(daily, dict):
            daily = daily.get("historical") or daily.get("bars") or daily.get("data") or []
        res = write_from_daily(ticker, daily, source)
        print(json.dumps(res, indent=1)); sys.exit(0 if res["written"] else 1)

    # default: stats for one ticker
    t = a[0].upper()
    s = stats(t)
    if not s:
        print(f"{t}: not in historical store — reconcile will seed it from FMP (D-40)"); sys.exit(1)
    print(json.dumps({"ticker": t, "stats": s, "n_returns": len(monthly_returns(t))}, indent=1))
