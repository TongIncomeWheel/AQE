#!/usr/bin/env python3
"""Overnight brief (D-108, PM ruling 2026-09-06).

PM, verbatim: "although PTJ runs smoothly, I don't know what was sold or changed overnight
unless I use my cognitive memory or check my broker, what is the book's realised MTD, WTD and
YTD profit/loss, I don't know what is my open risk, book beta and book exposure."

WHAT THIS ACTUALLY FIXES, AND WHAT IT DOESN'T: book beta (`nav_beta`) and book exposure
(`gross_exposure_usd`, `leverage`) were ALREADY computed into the journal's `metrics` block by
`portfolio_metrics.py` every run — that was never a missing number, only a missing line in what
got relayed to the PM on screen. Same story for MTD/YTD in the archive ledger (WTD was a genuine
gap, closed by D-107 in `archive_ledger.py`). The one number that did not exist anywhere before
this tool is OPEN RISK — dollars at stake if every held position's live stop were hit today —
and OVERNIGHT CHANGES had no single assembled view: closed_trades already lived in the journal,
a newly-opened position was only visible by diffing today's open_positions against yesterday's
by hand, and a stop-level change was only visible by diffing stop_live_broker the same way.

This tool does not compute anything the batch (`run_post_market.sh`) doesn't already have on
disk by the time it runs — it is a pure READ + ASSEMBLE step over: today's journal (already
built, membership-classified, dynCap-recomputed, metrics-computed), the prior day's journal
(for the overnight diff), and the archive ledger (for the realised rollups). Deterministic
(law 4) — no model, no network, no broker call of its own.

BUNDLING (the PM's other ask, "combine PTJ with /aegis-premarket ... run it at the same time,
in a bundle"): `/premarket` already runs PTJ CLOSE mode as its own Step 0, in the same session,
before doing anything else (see `skills/ptj/SKILL.md` MODE C and `skills/premarket/SKILL.md`
Step 0) — there was never a second command to merge. This tool's natural home is therefore
inside that already-bundled run: `run_post_market.sh` calls it right after job 9
(portfolio_metrics.py compute) and before the second git push, so the brief is written,
verified and pushed as part of the SAME run PTJ already does, not a second pass.

WHAT COUNTS AS "OPEN RISK": for a held position, risk_usd = the dollar loss if its live stop
filled right now — (mark - stop) * qty for a long, (stop - mark) * qty for a short — floored at
0 (a position already through its stop on a stale mark shows 0 fresh risk, not a negative
number that would net against everything else). A position with no live broker stop AND no
stop_reference floor is NOT counted as zero risk — that would understate the book — it is named
in `unknown_stop` and excluded from the total, exactly like every other "excluded, named, never
guessed" number in this kernel (portfolio_metrics.py's own rule, reused here on purpose so the
book has one convention for "we don't know" instead of two).

Non-Aegis positions (`aegis_status: excluded_non_aegis` — should not exist in open_positions by
the time this runs, since classify already drops them, but checked defensively) and options
legs are out of scope here; open risk is equity-only, matching what a broker stop order can
actually protect. Option risk is a Greeks/premium question, not a stop-distance one, and belongs
to the hedge-coverage assessment in `/premarket`, not here.

Usage:
  python3 tools/overnight_brief.py build --journal today.json [--prior prior.json] [--archive archive.json] [--out out.json]
  python3 tools/overnight_brief.py selftest
"""
import json
import argparse


def _by_ticker(positions, aegis_only=False):
    out = {}
    for p in positions or []:
        t = p.get("ticker")
        if not t:
            continue
        if aegis_only and p.get("aegis_status") not in (None, "confirmed", "pending_review"):
            continue  # excluded_non_aegis or similar — not this book's overnight story
        out[t] = p
    return out


def diff_overnight(today_journal, prior_journal):
    """What changed since the prior journal: names newly opened, today's closes (already
    computed by journal_build.py — this just reads them back out in one place), and any equity
    whose live broker stop moved (raised, lowered, newly staged, or pulled). A stop_live_broker
    of None on BOTH sides is not a change (never had one, still don't); None on one side only
    IS a change worth a line (a stop just got staged, or just vanished).

    Non-Aegis legs (aegis_status excluded_non_aegis) are filtered out here the same way
    open_risk() filters them — a non-Aegis position appearing or disappearing is not part of
    this book's overnight story, and counting it as "opened" would be misleading."""
    today_pos = _by_ticker(today_journal.get("open_positions"), aegis_only=True)
    prior_pos = _by_ticker((prior_journal or {}).get("open_positions"), aegis_only=True)

    opened = sorted(set(today_pos) - set(prior_pos))

    closed = []
    for c in today_journal.get("closed_trades") or []:
        closed.append({
            "ticker": c.get("ticker"),
            "realised_usd": c.get("pnlUsd", c.get("realised_usd", c.get("realized_usd"))),
            "exit_date": c.get("exitDate", c.get("closed_date")),
        })

    stop_changed = []
    for t, pos in today_pos.items():
        prior = prior_pos.get(t)
        if not prior:
            continue
        new_stop = pos.get("stop_live_broker")
        old_stop = prior.get("stop_live_broker")
        if new_stop != old_stop:
            stop_changed.append({"ticker": t, "old_stop": old_stop, "new_stop": new_stop})

    return {"opened": opened, "closed": closed, "stop_changed": stop_changed}


def open_risk(today_journal):
    """Dollars at stake if every held equity's live stop filled right now. See module docstring
    for the exact convention (floored at 0, unknown-stop names excluded and listed, never
    guessed)."""
    rows, unknown = [], []
    total = 0.0
    for p in today_journal.get("open_positions") or []:
        if p.get("aegis_status") not in (None, "confirmed", "pending_review"):
            continue  # excluded_non_aegis or similar — not this book's risk to carry
        if (p.get("sec_type") or "STK").upper() not in ("STK", "STOCK", "EQUITY"):
            continue  # equity-only; option risk is a Greeks question, not a stop-distance one
        ticker = p.get("ticker")
        qty = p.get("qty")
        mark = p.get("mark_price")
        stop = p.get("stop_live_broker")
        if stop is None:
            stop = p.get("stop_reference")
        if not ticker or qty in (None, 0) or mark is None or stop is None:
            if ticker:
                unknown.append(ticker)
            continue
        qty = float(qty)
        if qty > 0:
            risk = max(0.0, (float(mark) - float(stop)) * qty)
        else:
            risk = max(0.0, (float(stop) - float(mark)) * abs(qty))
        risk = round(risk, 2)
        rows.append({"ticker": ticker, "qty": qty, "mark": mark, "stop": stop, "risk_usd": risk})
        total += risk

    rows.sort(key=lambda r: -r["risk_usd"])
    return {"positions": rows, "total_open_risk_usd": round(total, 2),
            "unknown_stop": sorted(unknown)}


def realized_rollup(archive, today=None):
    """Pull the four period aggregates archive_ledger.py already computes (D-107 added
    WTD_current; YTD/QTD/MTD_current existed but nothing read them). An absent/empty archive
    (first-ever run) reads as all-zero, not an error — there is nothing realised yet, which is a
    true fact, not a missing one.

    FALLBACK, not just the happy path: the `_current` aliases only exist in an archive that has
    been through a merge() since D-107 shipped (2026-09-06). The real production archive on disk
    right now predates that — it has YTD_2026 / QTD_Q3_2026 / MTD_2026-09 but no `_current` keys
    at all — and a day with zero closed trades is a no_op in merge() (D-102's rule: never write a
    no-op copy), so those keys would stay absent for however many days pass before the next real
    close. Reading that as "$0 realised MTD/YTD" would be a FALSE zero — the exact "guessed
    instead of named" failure this kernel's open_risk() convention exists to avoid — not an
    honest gap. So when `_current` is missing, reconstruct today's dated key and read that
    instead; only report 0.0 when neither form is on file, which is the true first-ever-run case.
    Tolerant of both MTD label shapes seen in this repo's history (`MTD_Sep_2026` and
    `MTD_2026-09`) rather than assuming archive_ledger.py's current `_period_key()` is the only
    format any archive on disk was ever written with."""
    metrics = (archive or {}).get("metrics") or {}
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def _dated_candidates(period):
        if not today:
            return []
        y, m, d = (int(x) for x in today.split("-"))
        if period == "YTD":
            return [f"YTD_{y}"]
        if period == "QTD":
            return [f"QTD_Q{(m - 1) // 3 + 1}_{y}"]
        if period == "MTD":
            return [f"MTD_{months[m - 1]}_{y}", f"MTD_{y}-{m:02d}"]
        if period == "WTD":
            import datetime as _dt
            iso_year, iso_week, _ = _dt.date(y, m, d).isocalendar()
            return [f"WTD_{iso_year}-W{iso_week:02d}"]
        return []

    def _pnl(period):
        for key in [f"{period}_current"] + _dated_candidates(period):
            if key in metrics:
                return metrics[key].get("realized_pnl_usd", 0.0)
        return 0.0

    return {
        "ytd_realized_pnl_usd": _pnl("YTD"),
        "qtd_realized_pnl_usd": _pnl("QTD"),
        "mtd_realized_pnl_usd": _pnl("MTD"),
        "wtd_realized_pnl_usd": _pnl("WTD"),
    }


def build(today_journal, prior_journal, archive):
    metrics = today_journal.get("metrics") or {}
    dyncap = today_journal.get("dyncap") or {}
    var = metrics.get("var") or {}
    return {
        "date": today_journal.get("date"),
        "overnight_changes": diff_overnight(today_journal, prior_journal),
        "realized_pnl": realized_rollup(archive, today=today_journal.get("date")),
        "open_risk": open_risk(today_journal),
        "book": {
            "dyncap_usd": dyncap.get("value"),
            "one_r_usd": dyncap.get("one_r"),
            "gross_exposure_usd": metrics.get("gross_exposure_usd"),
            "leverage": metrics.get("leverage"),
            "net_beta_dollar": metrics.get("net_beta_dollar"),
            "book_beta": metrics.get("nav_beta"),
            "var_95_1m_usd": var.get("var_95_1m_usd"),
        },
    }


# --------------------------------------------------------------------------- CLI
def cmd_build(args):
    today_journal = json.load(open(args.journal))
    prior_journal = json.load(open(args.prior)) if args.prior else None
    archive = json.load(open(args.archive)) if args.archive else None
    brief = build(today_journal, prior_journal, archive)
    out = json.dumps(brief, indent=1)
    if args.out:
        open(args.out, "w").write(out)
    else:
        print(out)


def _selftest():
    prior_journal = {
        "date": "2026-09-04",
        "open_positions": [
            {"ticker": "AAA", "qty": 100, "mark_price": 50.0, "stop_live_broker": 47.0,
             "stop_reference": 47.0, "aegis_status": "confirmed"},
            {"ticker": "BBB", "qty": 50, "mark_price": 20.0, "stop_live_broker": 18.0,
             "aegis_status": "confirmed"},
        ],
    }
    today_journal = {
        "date": "2026-09-05",
        "dyncap": {"value": 100000.0, "one_r": 1500.0},
        "metrics": {
            "gross_exposure_usd": 60000.0, "leverage": 0.6,
            "net_beta_dollar": 30000.0, "nav_beta": 0.3,
            "var": {"var_95_1m_usd": 4500.0},
        },
        "open_positions": [
            # AAA: stop raised 47 -> 49 overnight, mark rallied -> real open risk shrinks
            {"ticker": "AAA", "qty": 100, "mark_price": 55.0, "stop_live_broker": 49.0,
             "stop_reference": 49.0, "aegis_status": "confirmed"},
            # BBB: stopped out overnight -> vanished from open_positions, shows in closed_trades
            # CCC: brand new position, no live stop staged yet -> unknown_stop
            {"ticker": "CCC", "qty": 200, "mark_price": 10.0, "stop_live_broker": None,
             "stop_reference": None, "aegis_status": "confirmed"},
            # DDD: a short, stop above mark
            {"ticker": "DDD", "qty": -40, "mark_price": 30.0, "stop_live_broker": 33.0,
             "aegis_status": "confirmed"},
            # a non-Aegis leg must never enter open risk
            {"ticker": "ZZZ", "qty": 10, "mark_price": 5.0, "stop_live_broker": 4.0,
             "aegis_status": "excluded_non_aegis"},
        ],
        "closed_trades": [
            {"ticker": "BBB", "pnlUsd": -100.0, "exitDate": "2026-09-05"},
        ],
    }
    archive = {
        "metrics": {
            "YTD_current": {"realized_pnl_usd": -1520.98},
            "QTD_current": {"realized_pnl_usd": -863.70},
            "MTD_current": {"realized_pnl_usd": -100.0},
            "WTD_current": {"realized_pnl_usd": -100.0},
        }
    }

    brief = build(today_journal, prior_journal, archive)

    oc = brief["overnight_changes"]
    # DDD and CCC are new Aegis-confirmed names since the prior journal; ZZZ is non-Aegis and
    # must not show up as "opened" even though it's new too (see diff_overnight's aegis_only filter)
    assert oc["opened"] == ["CCC", "DDD"], oc
    assert oc["closed"] == [{"ticker": "BBB", "realised_usd": -100.0, "exit_date": "2026-09-05"}], oc
    assert oc["stop_changed"] == [{"ticker": "AAA", "old_stop": 47.0, "new_stop": 49.0}], oc

    rp = brief["realized_pnl"]
    assert rp == {"ytd_realized_pnl_usd": -1520.98, "qtd_realized_pnl_usd": -863.70,
                  "mtd_realized_pnl_usd": -100.0, "wtd_realized_pnl_usd": -100.0}, rp

    orsk = brief["open_risk"]
    # AAA: (55-49)*100 = 600 ; DDD short: (33-30)*40 = 120 ; CCC unknown (no stop anywhere)
    assert {"ticker": "AAA", "qty": 100.0, "mark": 55.0, "stop": 49.0, "risk_usd": 600.0} in orsk["positions"], orsk
    assert {"ticker": "DDD", "qty": -40.0, "mark": 30.0, "stop": 33.0, "risk_usd": 120.0} in orsk["positions"], orsk
    assert orsk["unknown_stop"] == ["CCC"], orsk
    assert orsk["total_open_risk_usd"] == 720.0, orsk
    assert all(p["ticker"] != "ZZZ" for p in orsk["positions"]), \
        "a non-Aegis leg must never be counted in open risk"

    book = brief["book"]
    assert book == {"dyncap_usd": 100000.0, "one_r_usd": 1500.0, "gross_exposure_usd": 60000.0,
                     "leverage": 0.6, "net_beta_dollar": 30000.0, "book_beta": 0.3,
                     "var_95_1m_usd": 4500.0}, book

    # D-108 fallback: a real archive that predates D-107 has YTD_2026/QTD_Q3_2026/MTD_2026-09
    # but no "_current" keys — must NOT silently read as $0. today_journal's date is 2026-09-05:
    # QTD_Q3_2026, MTD in EITHER legacy label shape, WTD_2026-W36 (isocalendar confirmed).
    legacy_archive = {
        "metrics": {
            "YTD_2026": {"realized_pnl_usd": -1520.98},
            "QTD_Q3_2026": {"realized_pnl_usd": -863.70},
            "MTD_2026-09": {"realized_pnl_usd": -100.0},
        }
    }
    legacy_rp = realized_rollup(legacy_archive, today="2026-09-05")
    assert legacy_rp == {"ytd_realized_pnl_usd": -1520.98, "qtd_realized_pnl_usd": -863.70,
                          "mtd_realized_pnl_usd": -100.0, "wtd_realized_pnl_usd": 0.0}, legacy_rp
    legacy_archive_alt_mtd = {
        "metrics": {
            "YTD_2026": {"realized_pnl_usd": -1520.98},
            "MTD_Sep_2026": {"realized_pnl_usd": -100.0},
            "WTD_2026-W36": {"realized_pnl_usd": -50.0},
        }
    }
    legacy_rp2 = realized_rollup(legacy_archive_alt_mtd, today="2026-09-05")
    assert legacy_rp2["mtd_realized_pnl_usd"] == -100.0, legacy_rp2
    assert legacy_rp2["wtd_realized_pnl_usd"] == -50.0, legacy_rp2
    assert legacy_rp2["qtd_realized_pnl_usd"] == 0.0, legacy_rp2  # genuinely absent -> honest zero

    # no prior journal (first-ever run) and no archive (nothing realised yet) -> honest zeros/empties, not a crash
    brief2 = build(today_journal, None, None)
    # every Aegis-confirmed held name reads as "opened" with no prior book (correct, not a bug) —
    # but ZZZ (non-Aegis) must still never show up, exactly as when a prior book IS present
    assert brief2["overnight_changes"]["opened"] == ["AAA", "CCC", "DDD"], brief2
    assert brief2["realized_pnl"] == {"ytd_realized_pnl_usd": 0.0, "qtd_realized_pnl_usd": 0.0,
                                       "mtd_realized_pnl_usd": 0.0, "wtd_realized_pnl_usd": 0.0}, brief2

    print("overnight_brief.py selftest: PASS")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Overnight brief: what changed, realised P&L "
                                              "rollups, open risk, book beta/exposure (D-108)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--journal", required=True, help="today's journal")
    b.add_argument("--prior", help="prior day's journal, for the overnight diff")
    b.add_argument("--archive", help="data/persistent/aegis_trade_journal_ARCHIVE_master.json")
    b.add_argument("--out", help="write the brief here (default: stdout)")

    sub.add_parser("selftest")

    args = ap.parse_args(argv)
    if args.cmd == "selftest":
        _selftest()
        return
    cmd_build(args)


if __name__ == "__main__":
    main()
