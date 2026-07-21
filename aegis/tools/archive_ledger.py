#!/usr/bin/env python3
"""Aegis trade-journal archive ledger (BL-046 / D-68 — print-trade-journal successor, part 2).

D-67 moved PTJ EMISSION into the kernel (post_market writes aegis_trade_journal_[DATE]_PTJ.json
directly). This tool is the second half the retired standalone skill did: append newly CLOSED
Aegis trades into the running master ledger (`aegis_trade_journal_ARCHIVE_master.json`) and
recompute the rollups — deterministic (law 4), no model judgement, matches the schema already
live in Drive (built 2026-07-17, `archive_meta` + `closed_trades_ledger` + `metrics` blocks).

MERGE RULE (Golden Rule, preserved from the retired skill): if a trade's (ticker, exitDate)
already exists in the ledger, the NEWER value replaces it (idempotent re-runs never duplicate).

WHAT THIS DOES NOT DO: write to Drive. The orchestrating post_market session reads the current
archive via the Drive connector, calls this tool with that JSON + today's newly closed trades,
and writes the returned JSON back via mcp__Google_Drive__create_file. (No delete/overwrite tool
is exposed by the connector — see KNOWN LIMITATION below.)

KNOWN LIMITATION (D-68, surfaced not hidden): the Drive connector available to the kernel has
create/read/search but NO delete or true overwrite. Every archive write creates a NEW file with
the same title; "the archive" is always "the ARCHIVE_master.json with the latest modifiedTime"
in that folder. This is a real gap (it's exactly how the folder accumulated duplicate PTJ/archive
files before) — flagged to the PM as a housekeeping item, not silently worked around.

Usage:
  python3 tools/archive_ledger.py merge --archive archive.json --closed closed_trades.json [--out out.json]
  python3 tools/archive_ledger.py selftest
"""
import json
import argparse
import sys
from collections import defaultdict


def _normalize_trade(t):
    """Map a journal closed_trade record into the archive ledger's flat shape."""
    exit_date = t.get("exitDate") or t.get("exit_date")
    ticker = t.get("ticker")
    return {
        "id": t.get("id") or f"{ticker}-{exit_date}",
        "ticker": ticker,
        "type": t.get("type", "STK"),
        "exitDate": exit_date,
        "pnlUsd": round(float(t.get("pnlUsd", t.get("pnl_usd", 0.0))), 2),
        "winLoss": t.get("winLoss") or ("W" if t.get("pnlUsd", 0) > 0 else "L"),
        "sector": t.get("sector", "TBD"),
        "broker": t.get("broker", ""),
        "rRealised": t.get("rRealised", t.get("r_realised")),
        "note": t.get("note", ""),
    }


def _period_key(exit_date, granularity):
    y, m, d = exit_date.split("-")
    if granularity == "YTD":
        return f"YTD_{y}"
    if granularity == "QTD":
        q = (int(m) - 1) // 3 + 1
        return f"QTD_Q{q}_{y}"
    if granularity == "MTD":
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"MTD_{months[int(m)-1]}_{y}"


def _agg(trades):
    """Deterministic rollup: trade_count, wins, losses, win_rate_pct, realized_pnl_usd,
    avg_win_usd, avg_loss_usd, profit_factor. No model judgement — pure arithmetic."""
    wins = [t for t in trades if t["pnlUsd"] > 0]
    losses = [t for t in trades if t["pnlUsd"] <= 0]
    n = len(trades)
    realized = round(sum(t["pnlUsd"] for t in trades), 2)
    avg_win = round(sum(t["pnlUsd"] for t in wins) / len(wins), 2) if wins else 0.0
    avg_loss = round(sum(t["pnlUsd"] for t in losses) / len(losses), 2) if losses else 0.0
    gross_win = sum(t["pnlUsd"] for t in wins)
    gross_loss = abs(sum(t["pnlUsd"] for t in losses))
    profit_factor = round(gross_win / gross_loss, 3) if gross_loss > 0 else (None if not wins else 0.0)
    return {
        "trade_count": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(100.0 * len(wins) / n, 1) if n else 0.0,
        "realized_pnl_usd": realized,
        "avg_win_usd": avg_win,
        "avg_loss_usd": avg_loss,
        "profit_factor": profit_factor,
    }


def merge(archive, new_closed_trades, today):
    """Merge new_closed_trades into archive's closed_trades_ledger (Golden Rule dedupe),
    recompute all rollups, return the updated archive dict + a change summary."""
    ledger = {(t["ticker"], t["exitDate"]): t for t in archive.get("closed_trades_ledger", [])}
    if not new_closed_trades:
        # step 2i (retired skill's rule, kept): nothing new -> do not write a no-op copy
        return archive, {"added": 0, "replaced": 0, "no_op": True}

    added, replaced = 0, 0
    for raw in new_closed_trades:
        t = _normalize_trade(raw)
        key = (t["ticker"], t["exitDate"])
        if key in ledger:
            replaced += 1
        else:
            added += 1
        ledger[key] = t  # newer value always wins (Golden Rule)

    all_trades = list(ledger.values())

    year = today[:4]
    ytd = [t for t in all_trades if t["exitDate"].startswith(year)]
    qtd = [t for t in ytd if _period_key(t["exitDate"], "QTD") == _period_key(today, "QTD")]
    mtd = [t for t in ytd if t["exitDate"][:7] == today[:7]]

    by_sector = defaultdict(list)
    for t in ytd:
        by_sector[t["sector"]].append(t)
    by_day = defaultdict(list)
    for t in all_trades:
        by_day[t["exitDate"]].append(t)

    metrics = {
        "YTD_2026": _agg(ytd),
        "QTD_Q" + str((int(today[5:7]) - 1) // 3 + 1) + "_" + year: _agg(qtd),
        "MTD_" + today[:7]: _agg(mtd),
        "by_sector_YTD": {sec: _agg(ts) for sec, ts in sorted(by_sector.items())},
        "by_trading_day": {
            day: {**_agg(ts), "trades": [t["ticker"] for t in ts]}
            for day, ts in sorted(by_day.items())
        },
    }

    # integrity check (D-40 discipline: verify, don't assume)
    day_sum = round(sum(v["realized_pnl_usd"] for v in metrics["by_trading_day"].values()), 2)
    ytd_sum = metrics["YTD_2026"]["realized_pnl_usd"]
    if abs(day_sum - round(sum(t["pnlUsd"] for t in ytd), 2)) > 0.01:
        raise ValueError(f"INTEGRITY FAIL: by_trading_day sum {day_sum} != YTD-trades sum "
                          f"{round(sum(t['pnlUsd'] for t in ytd), 2)} — do not write, page the PM.")

    meta = dict(archive.get("archive_meta", {}))
    meta.update({
        "built_date": today,
        "coverage_through": today,
        "cumulative_trades_appended": len(all_trades),
    })

    updated = dict(archive)
    updated["archive_meta"] = meta
    updated["closed_trades_ledger"] = sorted(all_trades, key=lambda t: t["exitDate"])
    updated["metrics"] = metrics
    # carry forward unresolved items unchanged — never silently drop (old skill's rule, kept)
    updated["unresolved_pm_review_items"] = archive.get("unresolved_pm_review_items", [])

    return updated, {"added": added, "replaced": replaced, "no_op": False,
                      "total_trades": len(all_trades), "ytd_realized_pnl_usd": ytd_sum}


def _selftest():
    archive = {
        "archive_meta": {"coverage_through": "2026-07-17"},
        "closed_trades_ledger": [
            {"id": "CMG-20260714-20260717", "ticker": "CMG", "type": "STK", "exitDate": "2026-07-17",
             "pnlUsd": -717.30, "winLoss": "L", "sector": "XLY", "broker": "TIGER",
             "rRealised": -1.003, "note": "SL triggered"},
            {"id": "IBM_320C-20260713-20260714", "ticker": "IBM_320C", "type": "OPT",
             "exitDate": "2026-07-14", "pnlUsd": 683.36, "winLoss": "W", "sector": "XLK",
             "broker": "TIGER", "rRealised": 0.628, "note": "rolled"},
        ],
        "unresolved_pm_review_items": ["existing item — must survive the merge"],
    }
    # no new trades -> no_op
    updated, summary = merge(archive, [], "2026-07-20")
    assert summary["no_op"] is True, "expected no_op on empty input"
    # a genuinely new trade
    new = [{"ticker": "DDOG", "exitDate": "2026-07-20", "pnlUsd": 250.0, "sector": "XLK",
            "broker": "TIGER", "type": "STK"}]
    updated, summary = merge(archive, new, "2026-07-20")
    assert summary == {"added": 1, "replaced": 0, "no_op": False, "total_trades": 3,
                        "ytd_realized_pnl_usd": 216.06}, summary
    assert updated["unresolved_pm_review_items"] == ["existing item — must survive the merge"]
    assert updated["archive_meta"]["coverage_through"] == "2026-07-20"
    # idempotent re-run of the SAME trade -> replace, not duplicate
    updated2, summary2 = merge(updated, new, "2026-07-20")
    assert summary2["added"] == 0 and summary2["replaced"] == 1, summary2
    assert len(updated2["closed_trades_ledger"]) == 3, "must not duplicate on re-run"
    print("archive_ledger.py selftest: PASS")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge new closed trades into the Aegis archive ledger (BL-046/D-68)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("merge")
    m.add_argument("--archive", required=True, help="path to the current archive JSON")
    m.add_argument("--closed", required=True, help="path to today's closed_trades JSON (array)")
    m.add_argument("--today", help="YYYY-MM-DD, defaults to archive_meta.built_date+1 caller-supplied")
    m.add_argument("--out", help="write merged archive here (default: stdout)")

    sub.add_parser("selftest")

    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        _selftest()
        return

    archive = json.load(open(a.archive))
    closed = json.load(open(a.closed))
    if not a.today:
        print("ERROR: --today YYYY-MM-DD is required (the orchestrator supplies the session date)",
              file=sys.stderr)
        sys.exit(2)
    updated, summary = merge(archive, closed, a.today)
    out = json.dumps(updated, indent=1)
    if a.out:
        open(a.out, "w").write(out)
    else:
        print(out)
    print(json.dumps({"summary": summary}), file=sys.stderr)


if __name__ == "__main__":
    main()
