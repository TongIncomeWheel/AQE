#!/usr/bin/env python3
"""Aegis PORTFOLIO LEDGER — the persistent day-by-day record of the sub-fund (D-114).

PM ruling 2026-09-06: "we will never have a proper portfolio trade journal but purely a daily
held book ... I can't manage a portfolio without that (and accurate YTD, MTD, WTD daily
portfolio stats published)."

WHAT EXISTED BEFORE THIS FILE, AND WHY IT WAS NOT A PORTFOLIO JOURNAL
  * data/journal/aegis_journal_DATE.json  — the held book for ONE day. Overwritten in meaning
    every close; nothing strings the days together.
  * data/persistent/aegis_trade_journal_ARCHIVE_master.json — the closed-trade ledger with
    REALISED-only rollups. Realised P&L on 13 closed trades is not portfolio performance: it
    ignores every open position, so a book that is down 10% mark-to-market with no closes shows
    "MTD 0".
  * data/persistent/dyncap_ledger.json — the CURRENT Aegis equity (allocation + cumulative
    realised + Aegis-only unrealised), one snapshot, no history.

WHAT THIS FILE ADDS: data/persistent/portfolio_ledger.json — an append-only series, one row per
CLOSE date, keyed by close date, idempotent (re-running a date overwrites that row, never
duplicates). Each row is read off files the close already wrote (the journal, the archive, the
broker account summary) — no new broker calls, no judgement (constitution law 4).

THE NAV THAT MATTERS. The Tiger account is co-mingled (whole-account NAV ~$104k, whole-account
unrealised ~-$91k on 2026-09-04). None of that is Aegis. The Aegis NAV is dynCap:
    aegis_nav = allocated_capital + cumulative realised (Aegis trades) + unrealised (Aegis-confirmed
                positions only)
which `tools/recompute_dyncap.py` writes into each journal's `dyncap.value` (D-99/D-41). This
ledger records that number per day and derives everything from it. The whole-account broker NAV
is stored on each row FOR REFERENCE ONLY, clearly labelled, and never enters an Aegis statistic.

PERIOD ARITHMETIC (total P&L, not realised-only):
    period P&L = NAV(latest close) - NAV(reference)
    NAV(reference) = the last row strictly BEFORE the period start; if no such row exists the
                     reference is the allocated capital (inception baseline) and the rollup says so
                     in `baseline`.
    realised in period = sum of archive closed trades with exitDate inside the period
    unrealised change  = period P&L - realised in period
    max drawdown       = worst peak-to-trough of NAV over the reference + the period's rows
Periods: WTD (ISO week, Monday start), MTD, QTD, YTD, inception. Plus a per-ISO-week table.

DATES. Rows are keyed by the CLOSE date a journal reflects, derived from WHEN the journal was built
(`broker_sync.last_sync_utc` in US/Eastern): built at/after 16:00 ET on a trading day = that close;
built before the open or on a weekend/holiday = the previous trading day's close; built intraday =
that day, flagged. Not from the journal's own label: through 2026-09-03 journals were labelled with
the close date, from 2026-09-04 with the next trading day. `journal_date` stays on the row.

Usage:
  python3 tools/portfolio_ledger.py update   --journal J --ledger L [--archive A] [--account-summary S] [--allocated 75000] [--out OUT]
  python3 tools/portfolio_ledger.py backfill --journal-dir data/journal --ledger L [--archive A] [--eod-dir data/eod] [--allocated 75000] [--out OUT]
  python3 tools/portfolio_ledger.py render   --ledger L [--out FILE.md]
  python3 tools/portfolio_ledger.py selftest
Exit codes: 0 ok · 1 nothing to record (journal has no dynCap and cannot be reconstructed) · 2 bad input.
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys
import tempfile

X_VERSION = "1.0.0"
AEGIS_STATUSES = ("confirmed", "pending_review")   # same inclusion rule as recompute_dyncap.py (D-99)


# ----------------------------------------------------------------------------- helpers
def _load(path):
    with open(path) as f:
        return json.load(f)


def _num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _prev_weekday(d):
    d = d - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def _iso_week_key(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _period_starts(d):
    monday = d - dt.timedelta(days=d.weekday())
    q_month = 3 * ((d.month - 1) // 3) + 1
    return {
        "WTD": monday,
        "MTD": d.replace(day=1),
        "QTD": d.replace(month=q_month, day=1),
        "YTD": d.replace(month=1, day=1),
    }


HOLIDAYS_PATH = os.path.join("data", "persistent", "market_holidays.json")


def _holidays(path=None):
    p = path or HOLIDAYS_PATH
    try:
        raw = _load(p)
        items = raw.get("holidays", raw) if isinstance(raw, dict) else raw
        return {str(x)[:10] for x in items}
    except (OSError, ValueError, AttributeError, TypeError):
        return set()


def _prev_trading_day(d, holidays=None):
    holidays = holidays if holidays is not None else _holidays()
    d = d - dt.timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in holidays:
        d -= dt.timedelta(days=1)
    return d


def _close_date_of(journal, holidays=None):
    """Close date a journal reflects, from WHEN it was built (broker_sync.last_sync_utc, in US/Eastern):
      built at/after 16:00 ET on a trading day  -> that day's close
      built during the session (09:30-16:00 ET) -> that day (an intraday snapshot; flagged by the caller)
      built before 09:30 ET, or on a weekend/holiday -> the previous trading day's close
    Falls back to the previous trading day before the journal's own date when there is no timestamp.
    Why not the journal's date: through 2026-09-03 journals were labelled with the close date itself
    (built ~17:39 ET the same day); from 2026-09-04 they are labelled with the NEXT trading day they
    serve as start-of-day book. The build timestamp is the one thing that is true under both."""
    holidays = holidays if holidays is not None else _holidays()
    ts = (journal.get("broker_sync") or {}).get("last_sync_utc")
    if ts:
        try:
            from zoneinfo import ZoneInfo
            et = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
            d = et.date()
            is_td = d.weekday() < 5 and d.isoformat() not in holidays
            if is_td and (et.hour, et.minute) >= (9, 30):
                return d
            return _prev_trading_day(d, holidays) if not is_td or (et.hour, et.minute) < (9, 30) else d
        except (ValueError, ImportError):
            pass
    return _prev_trading_day(dt.date.fromisoformat(journal["date"]), holidays)


def _built_intraday(journal, holidays=None):
    ts = (journal.get("broker_sync") or {}).get("last_sync_utc")
    if not ts:
        return False
    try:
        from zoneinfo import ZoneInfo
        et = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
        return et.weekday() < 5 and (9, 30) <= (et.hour, et.minute) < (16, 0)
    except (ValueError, ImportError):
        return False


def _trade_pnl(t):
    for k in ("pnlUsd", "realized_pnl_usd", "realised_usd", "pnl_usd"):
        if k in t and t[k] is not None:
            return _num(t[k])
    return 0.0


def _trade_exit(t):
    for k in ("exitDate", "exit_date", "closed_on", "date"):
        if t.get(k):
            return str(t[k])[:10]
    return None


def _archive_trades(archive):
    if not archive:
        return []
    return list(archive.get("closed_trades_ledger") or archive.get("trades") or [])


# ----------------------------------------------------------------------------- row
def build_row(journal, archive=None, account_summary=None, allocated=75000.0, source_name=None):
    """One ledger row from one journal. Returns (row, flags)."""
    flags = []
    jdate = dt.date.fromisoformat(journal["date"])
    close = _close_date_of(journal)
    if _built_intraday(journal):
        flags.append("built_intraday_before_close")

    opens = [p for p in journal.get("open_positions", [])
             if (p.get("aegis_status") or "confirmed") in AEGIS_STATUSES]
    unreal = round(sum(_num(p.get("unrealised_usd")) for p in opens), 2)

    # realised: archive is the source of truth by exit date; journal closes fill the gap for
    # trades the archive has not filed yet (same id rule as archive_ledger's merge).
    arch = _archive_trades(archive)
    arch_ids = {t.get("id") or f"{t.get('ticker')}-{_trade_exit(t)}" for t in arch}
    today_closes = []
    for t in journal.get("closed_trades", []) or []:
        tid = t.get("id") or f"{t.get('ticker')}-{_trade_exit(t) or close.isoformat()}"
        if tid not in arch_ids:
            today_closes.append(t)
    realised_today = round(sum(_trade_pnl(t) for t in arch if _trade_exit(t) == close.isoformat())
                           + sum(_trade_pnl(t) for t in today_closes), 2)
    realised_cum = round(sum(_trade_pnl(t) for t in arch if (_trade_exit(t) or "9999") <= close.isoformat())
                         + sum(_trade_pnl(t) for t in today_closes), 2)
    closed_today = sum(1 for t in arch if _trade_exit(t) == close.isoformat()) + len(today_closes)

    dyn = journal.get("dyncap") or {}
    nav = dyn.get("value")
    if nav is None:
        nav = round(float(allocated) + realised_cum + unreal, 2)
        flags.append("nav_reconstructed_no_dyncap")
    nav = round(_num(nav), 2)

    m = journal.get("metrics") or {}
    var = m.get("var") or {}
    row = {
        "as_of_close": close.isoformat(),
        "journal_date": jdate.isoformat(),
        "source_journal": source_name or f"aegis_journal_{jdate.isoformat()}.json",
        "allocated_capital_usd": float(allocated),
        "aegis_nav_usd": nav,
        "realised_cum_usd": realised_cum,
        "unrealised_usd": unreal,
        "realised_today_usd": realised_today,
        "closed_today": closed_today,
        "open_positions": len(opens),
        "gross_exposure_usd": m.get("gross_exposure_usd"),
        "leverage": m.get("leverage"),
        "nav_beta": m.get("nav_beta"),
        "var_95_1m_usd": var.get("var_95_1m_usd"),
        "sector_concentration_pct": m.get("sector_concentration_pct"),
        "one_r_usd": dyn.get("one_r"),
        "day_pnl_usd": None,          # filled by recompute() from the prior row
        "day_return_pct": None,
        "whole_account_ref": None,
        "flags": flags,
    }
    if account_summary:
        row["whole_account_ref"] = {
            "note": "WHOLE Tiger account, co-mingled — reference only, not Aegis",
            "nav_usd": account_summary.get("nav"),
            "unrealised_usd": account_summary.get("unrealized_pnl"),
            "cash_usd": account_summary.get("cash"),
        }
    return row, flags


# ----------------------------------------------------------------------------- rollups
def _sorted_rows(ledger):
    return [ledger["days"][k] for k in sorted(ledger["days"])]


def _period_stats(rows, start, end, allocated, arch):
    """rows: all rows sorted; period = rows with start <= as_of_close <= end."""
    before = [r for r in rows if r["as_of_close"] < start.isoformat()]
    inside = [r for r in rows if start.isoformat() <= r["as_of_close"] <= end.isoformat()]
    if not inside:
        return None
    if before:
        ref_nav, baseline = before[-1]["aegis_nav_usd"], f"NAV at {before[-1]['as_of_close']} close"
    else:
        ref_nav, baseline = float(allocated), "allocated capital (no row before period start)"
    end_nav = inside[-1]["aegis_nav_usd"]
    pnl = round(end_nav - ref_nav, 2)
    in_period = [t for t in arch if start.isoformat() <= (_trade_exit(t) or "") <= end.isoformat()]
    realised = round(sum(_trade_pnl(t) for t in in_period), 2)
    wins = sum(1 for t in in_period if _trade_pnl(t) > 0)
    losses = sum(1 for t in in_period if _trade_pnl(t) < 0)
    # max drawdown over ref + rows
    peak, mdd = ref_nav, 0.0
    for r in inside:
        peak = max(peak, r["aegis_nav_usd"])
        if peak > 0:
            mdd = min(mdd, (r["aegis_nav_usd"] - peak) / peak * 100.0)
    return {
        "start": start.isoformat(), "end": inside[-1]["as_of_close"],
        "start_ref_nav_usd": round(ref_nav, 2), "baseline": baseline,
        "end_nav_usd": round(end_nav, 2),
        "total_pnl_usd": pnl,
        "return_pct": round(pnl / ref_nav * 100.0, 2) if ref_nav else None,
        "realised_usd": realised,
        "unrealised_change_usd": round(pnl - realised, 2),
        "trades_closed": len(in_period), "wins": wins, "losses": losses,
        "win_rate_pct": round(wins / len(in_period) * 100.0, 1) if in_period else None,
        "max_drawdown_pct": round(mdd, 2),
        "trading_days": len(inside),
    }


def recompute(ledger, archive=None):
    rows = _sorted_rows(ledger)
    arch = _archive_trades(archive)
    prev = None
    for r in rows:
        if prev is None:
            r["day_pnl_usd"] = None
            r["day_return_pct"] = None
            if "series_start" not in r["flags"]:
                r["flags"].append("series_start")
        else:
            r["day_pnl_usd"] = round(r["aegis_nav_usd"] - prev["aegis_nav_usd"], 2)
            r["day_return_pct"] = (round(r["day_pnl_usd"] / prev["aegis_nav_usd"] * 100.0, 3)
                                   if prev["aegis_nav_usd"] else None)
            r["flags"] = [f for f in r["flags"] if f != "series_start"]
        prev = r
    if not rows:
        ledger["rollups"], ledger["weeks"] = {}, {}
        return ledger
    latest = dt.date.fromisoformat(rows[-1]["as_of_close"])
    allocated = rows[-1]["allocated_capital_usd"]
    roll = {}
    for name, start in _period_starts(latest).items():
        roll[name] = _period_stats(rows, start, latest, allocated, arch)
    first = dt.date.fromisoformat(rows[0]["as_of_close"])
    roll["inception"] = _period_stats(rows, first, latest, allocated, arch)
    ledger["rollups"] = roll
    weeks = {}
    for r in rows:
        d = dt.date.fromisoformat(r["as_of_close"])
        wk = _iso_week_key(d)
        if wk in weeks:
            continue
        monday = d - dt.timedelta(days=d.weekday())
        sunday = monday + dt.timedelta(days=6)
        weeks[wk] = _period_stats(rows, monday, sunday, allocated, arch)
    ledger["weeks"] = weeks
    ledger["latest_close"] = rows[-1]["as_of_close"]
    ledger["updated_at_utc"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return ledger


def _empty_ledger():
    return {
        "x_version": X_VERSION,
        "unit": "USD",
        "scope": ("AEGIS sub-fund only. aegis_nav_usd = dynCap = allocated capital + cumulative realised "
                  "+ unrealised on Aegis-confirmed positions (D-41/D-99). Whole-account Tiger figures are "
                  "reference only and never enter an Aegis statistic. Rows keyed by CLOSE date; idempotent."),
        "days": {}, "rollups": {}, "weeks": {},
    }


def _write(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".pl_", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


# ----------------------------------------------------------------------------- render
def _fmt(x, pct=False, signed=True):
    if x is None:
        return "—"
    if pct:
        return f"{x:+.2f}%" if signed else f"{x:.2f}%"
    return f"{x:+,.0f}" if signed else f"{x:,.0f}"


def render(ledger, last_days=10, last_weeks=8):
    rows = _sorted_rows(ledger)
    if not rows:
        return "# Aegis portfolio ledger\n\nNo rows yet.\n"
    L = rows[-1]
    out = [f"# Aegis portfolio — as of {L['as_of_close']} close",
           "",
           f"**Aegis NAV {L['aegis_nav_usd']:,.0f}** on {L['allocated_capital_usd']:,.0f} allocated · "
           f"day {_fmt(L['day_pnl_usd'])} ({_fmt(L['day_return_pct'], pct=True)}) · "
           f"realised cum {_fmt(L['realised_cum_usd'])} · unrealised {_fmt(L['unrealised_usd'])} · "
           f"{L['open_positions']} open",
           "", "## Periods (total P&L = NAV change, not realised-only)", "",
           "| Period | From | Start NAV | End NAV | Total P&L | Return | Realised | Unrealised Δ | Trades W/L | Max DD |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for name in ("WTD", "MTD", "QTD", "YTD", "inception"):
        p = (ledger.get("rollups") or {}).get(name)
        if not p:
            continue
        out.append(f"| {name} | {p['start']} | {p['start_ref_nav_usd']:,.0f} | {p['end_nav_usd']:,.0f} | "
                   f"{_fmt(p['total_pnl_usd'])} | {_fmt(p['return_pct'], pct=True)} | {_fmt(p['realised_usd'])} | "
                   f"{_fmt(p['unrealised_change_usd'])} | {p['trades_closed']} ({p['wins']}/{p['losses']}) | "
                   f"{p['max_drawdown_pct']:.2f}% |")
    bases = {n: p["baseline"] for n, p in (ledger.get("rollups") or {}).items() if p and "allocated" in p["baseline"]}
    if bases:
        out.append("")
        out.append("_Start NAV = allocated capital for: " + ", ".join(sorted(bases)) + " (series began inside the period)._")
    out += ["", "## Weeks", "",
            "| ISO week | Start NAV | End NAV | P&L | Return | Realised | Trades W/L | Max DD | Days |",
            "|---|---|---|---|---|---|---|---|---|"]
    for wk in sorted(ledger.get("weeks") or {})[-last_weeks:]:
        p = ledger["weeks"][wk]
        out.append(f"| {wk} | {p['start_ref_nav_usd']:,.0f} | {p['end_nav_usd']:,.0f} | {_fmt(p['total_pnl_usd'])} | "
                   f"{_fmt(p['return_pct'], pct=True)} | {_fmt(p['realised_usd'])} | {p['trades_closed']} ({p['wins']}/{p['losses']}) | "
                   f"{p['max_drawdown_pct']:.2f}% | {p['trading_days']} |")
    out += ["", f"## Last {last_days} closes", "",
            "| Close | NAV | Day P&L | Day % | Realised | Unrealised | Open | Gross exp | Lev | β | VaR 1m |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows[-last_days:]:
        out.append(f"| {r['as_of_close']} | {r['aegis_nav_usd']:,.0f} | {_fmt(r['day_pnl_usd'])} | "
                   f"{_fmt(r['day_return_pct'], pct=True)} | {_fmt(r['realised_today_usd'])} | {_fmt(r['unrealised_usd'])} | "
                   f"{r['open_positions']} | {_fmt(r['gross_exposure_usd'], signed=False)} | "
                   f"{r['leverage'] if r['leverage'] is not None else '—'} | "
                   f"{r['nav_beta'] if r['nav_beta'] is not None else '—'} | {_fmt(r['var_95_1m_usd'], signed=False)} |")
    flagged = [(r["as_of_close"], f) for r in rows for f in r["flags"] if f != "series_start"]
    if flagged:
        out += ["", "## Flags", ""] + [f"- {d}: {f}" for d, f in flagged]
    ref = L.get("whole_account_ref")
    if ref and ref.get("nav_usd") is not None:
        out += ["", f"_Whole Tiger account (reference only, not Aegis): NAV {ref['nav_usd']:,.0f}, "
                    f"unrealised {_fmt(ref.get('unrealised_usd'))}._"]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------- commands
def cmd_update(a):
    journal = _load(a.journal)
    archive = _load(a.archive) if a.archive and os.path.exists(a.archive) else None
    acct = _load(a.account_summary) if a.account_summary and os.path.exists(a.account_summary) else None
    ledger = _load(a.ledger) if os.path.exists(a.ledger) else _empty_ledger()
    row, flags = build_row(journal, archive, acct, a.allocated, os.path.basename(a.journal))
    if "nav_reconstructed_no_dyncap" in flags and not journal.get("broker_sync"):
        print(json.dumps({"ok": False, "reason": "journal carries no dynCap and no broker_sync — a seed file, not a close; nothing to record"}))
        return 1
    ledger["days"][row["as_of_close"]] = row
    recompute(ledger, archive)
    _write(a.out or a.ledger, ledger)
    r = ledger["days"][row["as_of_close"]]
    print(json.dumps({"ok": True, "as_of_close": r["as_of_close"], "aegis_nav_usd": r["aegis_nav_usd"],
                      "day_pnl_usd": r["day_pnl_usd"], "rows": len(ledger["days"]),
                      "WTD": (ledger["rollups"].get("WTD") or {}).get("total_pnl_usd"),
                      "MTD": (ledger["rollups"].get("MTD") or {}).get("total_pnl_usd"),
                      "YTD": (ledger["rollups"].get("YTD") or {}).get("total_pnl_usd"),
                      "flags": r["flags"], "out": a.out or a.ledger}))
    return 0


def cmd_backfill(a):
    archive = _load(a.archive) if a.archive and os.path.exists(a.archive) else None
    ledger = _load(a.ledger) if os.path.exists(a.ledger) else _empty_ledger()
    added, skipped = [], []
    for p in sorted(glob.glob(os.path.join(a.journal_dir, "aegis_journal_*.json"))):
        j = _load(p)
        if (j.get("dyncap") or {}).get("value") is None and not j.get("broker_sync"):
            skipped.append((os.path.basename(p), "no dynCap and no broker_sync — a seed/backfill file, not a real close"))
            continue
        acct = None
        if a.eod_dir:
            cand = os.path.join(a.eod_dir, j["date"], "broker_pull", "tiger_account_summary.json")
            acct = _load(cand) if os.path.exists(cand) else None
        row, _ = build_row(j, archive, acct, a.allocated, os.path.basename(p))
        ledger["days"][row["as_of_close"]] = row
        added.append(row["as_of_close"])
    recompute(ledger, archive)
    _write(a.out or a.ledger, ledger)
    print(json.dumps({"ok": True, "rows_written": added, "skipped": skipped, "total_rows": len(ledger["days"]),
                      "out": a.out or a.ledger}, indent=1))
    return 0


def cmd_render(a):
    ledger = _load(a.ledger)
    md = render(ledger)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w") as f:
            f.write(md)
    sys.stdout.write(md)
    return 0


# ----------------------------------------------------------------------------- selftest
def selftest():
    def J(date, sync, nav, opens, closes=()):
        return {"date": date, "broker_sync": {"last_sync_utc": sync + "T21:30:00Z"},
                "dyncap": {"value": nav, "one_r": 1000.0},
                "open_positions": [{"ticker": t, "unrealised_usd": u, "aegis_status": s} for t, u, s in opens],
                "closed_trades": list(closes),
                "metrics": {"gross_exposure_usd": 20000.0, "leverage": 0.3, "nav_beta": 0.2, "var": {"var_95_1m_usd": 900.0}}}
    # Wed 2026-09-02 close → journal 09-03 ; Thu 09-03 close → journal 09-04 ; Mon 09-07 close → journal 09-08 (new ISO week)
    arch = {"closed_trades_ledger": [
        {"id": "AAA-2026-09-03", "ticker": "AAA", "exitDate": "2026-09-03", "pnlUsd": -300.0},
        {"id": "BBB-2026-09-07", "ticker": "BBB", "exitDate": "2026-09-07", "pnlUsd": 500.0}]}
    j1 = J("2026-09-03", "2026-09-02", 75200.0, [("X", 200.0, "confirmed"), ("Z", 999.0, "excluded_non_aegis")])
    j2 = J("2026-09-04", "2026-09-03", 75100.0, [("X", 400.0, "confirmed")])
    j3 = J("2026-09-08", "2026-09-07", 75900.0, [("X", 700.0, "confirmed")])
    L = _empty_ledger()
    for j in (j1, j2, j3):
        row, _ = build_row(j, arch, {"nav": 100000.0, "unrealized_pnl": -5.0, "cash": 1.0}, 75000.0)
        L["days"][row["as_of_close"]] = row
    recompute(L, arch)
    d = L["days"]
    assert set(d) == {"2026-09-02", "2026-09-03", "2026-09-07"}, d.keys()
    assert d["2026-09-02"]["unrealised_usd"] == 200.0, "non-Aegis position must be excluded from unrealised"
    assert d["2026-09-02"]["day_pnl_usd"] is None and "series_start" in d["2026-09-02"]["flags"]
    assert d["2026-09-03"]["day_pnl_usd"] == -100.0 and d["2026-09-03"]["realised_today_usd"] == -300.0
    assert d["2026-09-03"]["realised_cum_usd"] == -300.0 and d["2026-09-07"]["realised_cum_usd"] == 200.0
    assert d["2026-09-07"]["day_pnl_usd"] == 800.0
    r = L["rollups"]
    # WTD for latest (Mon 09-07): reference = last row before Monday = 75100 → +800, realised +500, unrealised Δ +300
    assert r["WTD"]["start_ref_nav_usd"] == 75100.0 and r["WTD"]["total_pnl_usd"] == 800.0
    assert r["WTD"]["realised_usd"] == 500.0 and r["WTD"]["unrealised_change_usd"] == 300.0
    assert "NAV at 2026-09-03" in r["WTD"]["baseline"]
    # MTD (Sep 1 start, no row before) → baseline = allocation 75000 → +900 total, realised +200
    assert r["MTD"]["start_ref_nav_usd"] == 75000.0 and r["MTD"]["total_pnl_usd"] == 900.0
    assert r["MTD"]["realised_usd"] == 200.0 and r["MTD"]["trades_closed"] == 2 and r["MTD"]["wins"] == 1
    assert "allocated" in r["MTD"]["baseline"]
    assert r["YTD"]["total_pnl_usd"] == 900.0 and r["inception"]["total_pnl_usd"] == 900.0
    # drawdown: 75200 peak → 75100 trough = -0.133%
    assert abs(r["MTD"]["max_drawdown_pct"] - (-0.13)) < 0.02, r["MTD"]["max_drawdown_pct"]
    w = L["weeks"]
    assert set(w) == {"2026-W36", "2026-W37"}, w.keys()
    assert w["2026-W36"]["total_pnl_usd"] == 100.0 and w["2026-W37"]["total_pnl_usd"] == 800.0
    # idempotent: re-adding the same journal changes nothing
    row, _ = build_row(j2, arch, None, 75000.0)
    L["days"][row["as_of_close"]] = row
    recompute(L, arch)
    assert len(L["days"]) == 3 and L["rollups"]["WTD"]["total_pnl_usd"] == 800.0
    # a journal that has to be reconstructed (no dynCap) flags itself
    j4 = J("2026-09-09", "2026-09-08", None, [("X", 100.0, "confirmed")])
    row4, fl = build_row(j4, arch, None, 75000.0)
    assert "nav_reconstructed_no_dyncap" in fl and row4["aegis_nav_usd"] == 75000.0 + 200.0 + 100.0
    # whole-account figures never leak into Aegis numbers
    assert d["2026-09-07"]["whole_account_ref"]["nav_usd"] == 100000.0 and d["2026-09-07"]["aegis_nav_usd"] == 75900.0
    md = render(L)
    assert "| WTD |" in md and "| 2026-W37 |" in md and "reference only" in md
    print("portfolio_ledger selftest OK — rows keyed by close date, non-Aegis excluded from unrealised, day P&L "
          "from prior row, WTD/MTD/YTD are NAV change with realised split out and an honest baseline label, "
          "ISO-week table, idempotent re-run, reconstructed NAV flagged, whole-account NAV kept as reference only.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update"); u.add_argument("--journal", required=True); u.add_argument("--ledger", required=True)
    u.add_argument("--archive"); u.add_argument("--account-summary"); u.add_argument("--allocated", type=float, default=75000.0)
    u.add_argument("--out"); u.set_defaults(fn=cmd_update)
    b = sub.add_parser("backfill"); b.add_argument("--journal-dir", required=True); b.add_argument("--ledger", required=True)
    b.add_argument("--archive"); b.add_argument("--eod-dir"); b.add_argument("--allocated", type=float, default=75000.0)
    b.add_argument("--out"); b.set_defaults(fn=cmd_backfill)
    r = sub.add_parser("render"); r.add_argument("--ledger", required=True); r.add_argument("--out"); r.set_defaults(fn=cmd_render)
    s = sub.add_parser("selftest"); s.set_defaults(fn=lambda a: selftest())
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
