#!/usr/bin/env python3
"""Aegis TRADE JOURNAL — the persistent trade-level record (D-115).

PM ruling 2026-09-06: "what you don't have is a persistent trade-level trade journal. I can't go
back in time and see what trades were bought and sold at what prices, qty, dates, P&L — like a
simple mechanical record of things."

WHAT THIS IS. Three tables, kept forever in data/persistent/trade_journal.json, rebuilt
deterministically from raw broker fills (constitution law 4 — no judgement, no model):

  fills   — EVERY fill the broker ever reported, keyed by the broker's own fill id, so re-reading
            the same pull a hundred times adds nothing. Stock, option and multi-leg alike. Time,
            ticker, side, qty, price, commission, GST, the broker's own realised P&L where it gave
            one. Nothing is filtered out of this table — it is the record.
  trades  — stock round-trips built from `fills` by FIFO lot matching per ticker: date in, entry
            price (weighted over the lots consumed), qty, date out, exit price, gross P&L, fees,
            net P&L, %, holding days, R-multiple where the stop at entry is known, partial flag.
            One row per exit fill.
  open    — the lots still open, with cost and days held.

WHERE THE FILLS COME FROM. Tiger's `get_filled_orders` returns a rolling window, and PTJ saves it
every close as data/eod/<DATE>/broker_pull/tiger_filled_orders.json. The union of those daily
snapshots, keyed by fill id, is a complete fill history from the first day PTJ ran (2026-08-12
onward as of the first seed). `backfill` walks every snapshot on disk; `update` adds today's.

POSITIONS OLDER THAN THE FILL WINDOW. A sell whose buy pre-dates the first snapshot (AVAV, PRU,
GE, OXY in Aug-2026) is matched against a SEED lot taken from the earliest journal that carried
the position (`entry`, `entry_date`, `qty`). Seeds are flagged `journal_seed` on the trade row and
their `entry_date` is "first seen in a journal", not a fill time — the row says so. This is
mechanical and honest; it is not a claim the fill happened that day.

AEGIS ONLY (PM ruling 2026-09-06: "I only want Aegis trades captured for closed and open trades").
The Tiger account is co-mingled, so every fill is tagged on ingest — `non_aegis` if the ticker is on
data/persistent/non_aegis_exclusions.json, `aegis` if on data/persistent/aegis_membership.json, in the
archive ledger, or carried as confirmed in any journal, else `unclassified` — and ONLY Aegis rows are
rendered, counted, or flagged. Non-Aegis and option fills stay in the raw store solely so FIFO matching
is complete and idempotent; they never print.

CROSS-CHECK. Given --archive, the Aegis net realised total is compared with the archive ledger's
closed-trade total and any difference is printed and flagged — two independent paths to the same
number, or a finding.

Usage:
  python3 tools/trade_journal.py update   --pull data/eod/DATE/broker_pull --journal-dir data/journal --store data/persistent/trade_journal.json [--archive A] [--out OUT]
  python3 tools/trade_journal.py backfill --eod-dir data/eod --journal-dir data/journal --store data/persistent/trade_journal.json [--archive A] [--out OUT]
  python3 tools/trade_journal.py render   --store data/persistent/trade_journal.json [--out FILE.md] [--fills 60]
  python3 tools/trade_journal.py selftest
Exit codes: 0 ok · 2 bad input.
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys
import tempfile

X_VERSION = "1.0.0"
MEMBERSHIP = os.path.join("data", "persistent", "aegis_membership.json")
EXCLUSIONS = os.path.join("data", "persistent", "non_aegis_exclusions.json")


# ----------------------------------------------------------------------------- io
def _load(p):
    with open(p) as f:
        return json.load(f)


def _write(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tj_", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def _num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _empty_store():
    return {"x_version": X_VERSION,
            "scope": ("Every broker fill ever seen (keyed by broker fill id, idempotent), stock round-trips by FIFO "
                      "per ticker, open lots, Aegis-only stats. Fills tagged aegis / non_aegis / unclassified from "
                      "the membership + exclusion files and the journals. Seeds = positions older than the fill "
                      "window, taken from the earliest journal that carried them, flagged on the row."),
            "fills": {}, "seeds": {}, "trades": [], "open_lots": [], "stats": {}, "flags": []}


# ----------------------------------------------------------------------------- fills
def _pull_rows(path):
    d = _load(path)
    r = d.get("result", d) if isinstance(d, dict) else d
    if isinstance(r, dict):
        r = r.get("orders") or r.get("items") or r.get("data") or []
    return r or []


def normalize_fill(x, source):
    t_ms = x.get("trade_time") or x.get("filled_time") or x.get("order_time")
    when = dt.datetime.fromtimestamp(t_ms / 1000, dt.timezone.utc) if t_ms else None
    qty = _num(x.get("filled"), None)
    if qty in (None, 0):
        qty = _num(x.get("quantity"), 0.0)
    return {
        "id": str(x.get("id") or x.get("order_id")),
        "broker": "TIGER",
        "time_utc": when.replace(microsecond=0).isoformat() if when else None,
        "date": when.date().isoformat() if when else None,
        "ticker": x.get("symbol"),
        "sec_type": x.get("sec_type") or x.get("secType"),
        "action": (x.get("action") or x.get("side") or "").upper(),
        "qty": float(qty or 0),
        "price": _num(x.get("avg_fill_price"), _num(x.get("limit_price"), None)),
        "commission": _num(x.get("commission"), 0.0) or 0.0,
        "gst": _num(x.get("gst"), 0.0) or 0.0,
        "broker_realized_pnl": _num(x.get("realized_pnl"), None),
        "right": x.get("right"), "strike": x.get("strike"), "expiry": x.get("expiry"),
        "order_type": x.get("order_type"), "fill_type": x.get("fill_type"),
        "first_seen_in": source,
    }


def ingest_pull(store, pull_dir, source_label=None):
    p = os.path.join(pull_dir, "tiger_filled_orders.json")
    if not os.path.exists(p):
        return 0
    new = 0
    for x in _pull_rows(p):
        f = normalize_fill(x, source_label or pull_dir)
        if f["id"] not in store["fills"]:
            store["fills"][f["id"]] = f
            new += 1
    return new


# ----------------------------------------------------------------------------- tagging + seeds
def _tagger(journal_dir, membership_path=MEMBERSHIP, exclusions_path=EXCLUSIONS, archive=None):
    members, excluded, seen = set(), set(), {}
    for t in (archive or {}).get("closed_trades_ledger", []) or []:
        if t.get("ticker"):
            members.add(t["ticker"])   # filed in the Aegis closed-trade ledger = Aegis, by definition
    try:
        members |= set(_load(membership_path))
    except (OSError, ValueError, TypeError):
        pass
    try:
        ex = _load(exclusions_path)
        excluded = set(ex.keys() if isinstance(ex, dict) else ex)
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    for jp in sorted(glob.glob(os.path.join(journal_dir, "aegis_journal_*.json"))) if journal_dir else []:
        try:
            j = _load(jp)
        except (OSError, ValueError):
            continue
        for pos in j.get("open_positions", []):
            st = pos.get("aegis_status")
            if st and pos.get("ticker") not in seen:
                seen[pos["ticker"]] = st

    def tag(ticker):
        if ticker in excluded:
            return "non_aegis"
        if ticker in members:
            return "aegis"
        st = seen.get(ticker)
        if st in ("confirmed", "pending_review", "staged"):
            return "aegis"
        if st == "excluded_non_aegis":
            return "non_aegis"
        return "unclassified"
    return tag


def collect_seeds(journal_dir):
    """Earliest journal appearance per ticker: qty, entry, entry_date, first stop_reference seen."""
    seeds, stops = {}, {}
    for jp in sorted(glob.glob(os.path.join(journal_dir, "aegis_journal_*.json"))) if journal_dir else []:
        try:
            j = _load(jp)
        except (OSError, ValueError):
            continue
        for pos in j.get("open_positions", []):
            tk = pos.get("ticker")
            if not tk:
                continue
            if tk not in seeds and pos.get("entry") is not None and pos.get("qty"):
                seeds[tk] = {"ticker": tk, "qty": float(pos["qty"]), "price": float(pos["entry"]),
                             "date": pos.get("entry_date") or j.get("date"),
                             "source_journal": os.path.basename(jp),
                             "entry_date_is_first_seen": (pos.get("entry_date") or j.get("date")) == j.get("date")}
            if tk not in stops and pos.get("stop_reference") is not None:
                stops[tk] = float(pos["stop_reference"])
    return seeds, stops


# ----------------------------------------------------------------------------- matching
def _fee(f):
    return (f.get("commission") or 0.0) + (f.get("gst") or 0.0)


def journal_booked_closes(journal_dir, fills):
    """Closes a journal booked (closed_trades) for which NO broker sell fill exists on record — e.g. a
    D-100 recovery where the exit came from get_transactions and the fill never reached a saved pull.
    Returned as synthetic SELL fills so the trade table matches the position truth; each is flagged."""
    out = []
    have = {}
    for f in fills:
        if f["action"] == "SELL":
            have.setdefault((f["ticker"], f["date"]), 0.0)
            have[(f["ticker"], f["date"])] += f["qty"]
    for jp in sorted(glob.glob(os.path.join(journal_dir, "aegis_journal_*.json"))) if journal_dir else []:
        try:
            j = _load(jp)
        except (OSError, ValueError):
            continue
        for c in j.get("closed_trades", []) or []:
            tk, d, q = c.get("ticker"), c.get("closed_date") or c.get("exitDate"), _num(c.get("qty"), 0.0)
            if not tk or not d or not q or c.get("exit") is None:
                continue
            if have.get((tk, d), 0.0) + 1e-9 >= q:
                continue
            key = f"journal:{tk}:{d}"
            if any(o["id"] == key for o in out):
                continue
            out.append({"id": key, "broker": "TIGER", "time_utc": f"{d}T20:00:00+00:00", "date": d, "ticker": tk,
                        "sec_type": "STK", "action": "SELL", "qty": float(q), "price": float(c["exit"]),
                        "commission": 0.0, "gst": 0.0, "broker_realized_pnl": _num(c.get("realised_usd"), None),
                        "synthetic_from_journal": os.path.basename(jp)})
    return out


def build_trades(store, seeds, stops, tag, journal_dir=None):
    fills = sorted((f for f in store["fills"].values() if f["sec_type"] == "STK" and f["time_utc"]),
                   key=lambda f: (f["time_utc"], f["id"]))
    booked = journal_booked_closes(journal_dir, fills)
    store["journal_booked_closes"] = booked
    fills = sorted(fills + booked, key=lambda f: (f["time_utc"], f["id"]))
    lots, trades, flags = {}, [], []
    first_buy_date = {}
    for f in fills:
        if f["action"] == "BUY":
            first_buy_date.setdefault(f["ticker"], f["date"])
    # journal seeds: a position the journals carried whose BUY pre-dates the saved fill window. Inserted
    # as the oldest lot ONLY when no BUY fill exists on or before the seed's date (else it would double
    # count a buy we do have). Never sold = it stays an open lot, flagged.
    for tk, sd in seeds.items():
        fb = first_buy_date.get(tk)
        if fb is None or (sd["date"] or "9999") < fb:
            lots.setdefault(tk, []).insert(0, {"qty": sd["qty"], "price": sd["price"], "date": sd["date"], "time": None,
                                              "fill_id": None, "fee": 0.0, "seed": True, "seed_source": sd["source_journal"],
                                              "entry_date_is_first_seen": sd.get("entry_date_is_first_seen", False)})
    for f in fills:
        tk = f["ticker"]
        book = lots.setdefault(tk, [])
        if f["action"] == "BUY":
            book.append({"qty": f["qty"], "price": f["price"], "date": f["date"], "time": f["time_utc"],
                         "fill_id": f["id"], "fee": _fee(f), "seed": False})
            continue
        if f["action"] != "SELL":
            continue
        remaining, consumed = f["qty"], []
        while remaining > 1e-9 and book:
            lot = book[0]
            take = min(lot["qty"], remaining)
            consumed.append({**lot, "take": take})
            lot["qty"] -= take
            remaining -= take
            if lot["qty"] <= 1e-9:
                book.pop(0)
        matched = f["qty"] - remaining
        row = {"ticker": tk, "tag": tag(tk), "exit_date": f["date"], "exit_time_utc": f["time_utc"],
               "exit_price": f["price"], "exit_fill_id": f["id"], "qty": f["qty"],
               "broker_realized_pnl": f.get("broker_realized_pnl"), "flags": []}
        if matched <= 1e-9:
            row.update({"entry_date": None, "entry_price": None, "gross_pnl_usd": None, "fees_usd": round(_fee(f), 2),
                        "net_pnl_usd": f.get("broker_realized_pnl"), "pnl_pct": None, "holding_days": None,
                        "r_multiple": None, "partial": False, "entry_fill_ids": []})
            row["flags"].append("unmatched_sell_no_entry_on_record" + (" (broker P&L used)" if f.get("broker_realized_pnl") is not None else ""))
            trades.append(row)
            if tag(tk) == "aegis":
                flags.append(f"{tk} {f['date']}: sell of {f['qty']:g} with no entry on record")
            continue
        cost = sum(c["take"] * c["price"] for c in consumed)
        entry_px = cost / matched
        entry_fee = sum(c["fee"] * (c["take"] / c["qty"]) if c["qty"] else 0.0 for c in consumed)  # c["qty"] = lot size before this take
        gross = round((f["price"] - entry_px) * matched, 2)
        fees = round(entry_fee + _fee(f), 2)
        entry_dates = [c["date"] for c in consumed if c["date"]]
        entry_date = min(entry_dates) if entry_dates else None
        hold = ((dt.date.fromisoformat(f["date"]) - dt.date.fromisoformat(entry_date)).days
                if entry_date and f["date"] else None)
        stop = stops.get(tk)
        risk = (entry_px - stop) * matched if stop is not None and entry_px > stop else None
        row.update({"entry_date": entry_date, "entry_price": round(entry_px, 4), "qty": matched,
                    "gross_pnl_usd": gross, "fees_usd": fees, "net_pnl_usd": round(gross - fees, 2),
                    "pnl_pct": round((f["price"] / entry_px - 1.0) * 100.0, 2) if entry_px else None,
                    "holding_days": hold,
                    "stop_at_entry": stop, "r_multiple": round((gross - fees) / risk, 2) if risk else None,
                    "partial": bool(book) or len(consumed) > 1,
                    "entry_fill_ids": [c["fill_id"] for c in consumed if c["fill_id"]]})
        if f.get("synthetic_from_journal"):
            row["flags"].append(f"exit_from_journal_no_broker_fill_on_record ({f['synthetic_from_journal']}) — confirm via get_transactions")
        if any(c["seed"] for c in consumed):
            row["flags"].append("journal_seed")
            if any(c.get("entry_date_is_first_seen") for c in consumed):
                row["flags"].append("entry_date_is_first_seen_in_journal_not_fill_time")
        if remaining > 1e-9:
            row["flags"].append(f"sold {f['qty']:g}, only {matched:g} matched to entries on record")
            if tag(tk) == "aegis":
                flags.append(f"{tk} {f['date']}: sold {f['qty']:g}, only {matched:g} matched")
        if f.get("broker_realized_pnl") is not None and abs(f["broker_realized_pnl"] - row["net_pnl_usd"]) > max(2.0, abs(row["net_pnl_usd"]) * 0.02):
            row["flags"].append(f"broker P&L {f['broker_realized_pnl']:+.2f} differs from computed {row['net_pnl_usd']:+.2f}")
        trades.append(row)
    open_lots = []
    for tk, book in lots.items():
        for l in book:
            if l["qty"] > 1e-9:
                days = (dt.date.today() - dt.date.fromisoformat(l["date"])).days if l["date"] else None
                open_lots.append({"ticker": tk, "tag": tag(tk), "qty": l["qty"], "entry_price": l["price"],
                                  "entry_date": l["date"], "cost_usd": round(l["qty"] * l["price"], 2),
                                  "days_held": days, "fill_id": l["fill_id"],
                                  "flags": (["journal_seed — entry from the earliest journal that carried it, not a fill"] if l["seed"] else [])})
    trades.sort(key=lambda r: (r["exit_time_utc"] or "", r["ticker"]))
    return trades, open_lots, flags


def compute_stats(trades, only_tag="aegis"):
    rows = [t for t in trades if t["tag"] == only_tag and t.get("net_pnl_usd") is not None]
    if not rows:
        return {"trades": 0}
    wins = [t["net_pnl_usd"] for t in rows if t["net_pnl_usd"] > 0]
    losses = [t["net_pnl_usd"] for t in rows if t["net_pnl_usd"] < 0]
    gp, gl = sum(wins), -sum(losses)
    holds = [t["holding_days"] for t in rows if t.get("holding_days") is not None]
    rs = [t["r_multiple"] for t in rows if t.get("r_multiple") is not None]
    return {"trades": len(rows), "wins": len(wins), "losses": len(losses),
            "win_rate_pct": round(len(wins) / len(rows) * 100.0, 1),
            "net_pnl_usd": round(sum(t["net_pnl_usd"] for t in rows), 2),
            "gross_pnl_usd": round(sum(t["gross_pnl_usd"] or 0.0 for t in rows), 2),
            "fees_usd": round(sum(t["fees_usd"] or 0.0 for t in rows), 2),
            "avg_win_usd": round(gp / len(wins), 2) if wins else None,
            "avg_loss_usd": round(-gl / len(losses), 2) if losses else None,
            "profit_factor": round(gp / gl, 2) if gl else None,
            "expectancy_usd": round(sum(t["net_pnl_usd"] for t in rows) / len(rows), 2),
            "avg_holding_days": round(sum(holds) / len(holds), 1) if holds else None,
            "avg_r": round(sum(rs) / len(rs), 2) if rs else None, "r_known": len(rs),
            "best_usd": round(max(t["net_pnl_usd"] for t in rows), 2),
            "worst_usd": round(min(t["net_pnl_usd"] for t in rows), 2)}


def rebuild(store, journal_dir, archive=None):
    tag = _tagger(journal_dir, archive=archive)
    seeds, stops = collect_seeds(journal_dir)
    for f in store["fills"].values():
        f["tag"] = tag(f["ticker"])
    store["seeds"] = seeds
    trades, open_lots, flags = build_trades(store, seeds, stops, tag, journal_dir)
    store["trades"], store["open_lots"] = trades, open_lots
    store["stats"] = {"aegis": compute_stats(trades, "aegis")}
    # reconciliation 1: fills-derived open Aegis lots vs the latest journal's open positions
    recon = {"vs_latest_journal": [], "vs_archive": []}
    jps = sorted(glob.glob(os.path.join(journal_dir, "aegis_journal_*.json"))) if journal_dir else []
    if jps:
        try:
            latest = _load(jps[-1])
            jpos = {p["ticker"]: float(p.get("qty") or 0) for p in latest.get("open_positions", [])
                    if (p.get("aegis_status") or "confirmed") in ("confirmed", "pending_review", "staged")}
            lots = {}
            for l in open_lots:
                if l["tag"] == "aegis":
                    lots[l["ticker"]] = lots.get(l["ticker"], 0.0) + l["qty"]
            for tk in sorted(set(jpos) | set(lots)):
                a, b = lots.get(tk, 0.0), jpos.get(tk, 0.0)
                if abs(a - b) > 1e-6:
                    recon["vs_latest_journal"].append({"ticker": tk, "open_per_fills": a, "open_per_journal": b,
                                                       "journal": os.path.basename(jps[-1]),
                                                       "note": ("a SELL fill is missing from the saved broker pulls (position gone per journal)" if a > b
                                                                else "a BUY fill is missing from the saved broker pulls (position present per journal)")})
                    flags.append(f"{tk}: {a:g} open per fills vs {b:g} per {os.path.basename(jps[-1])}")
        except (OSError, ValueError, KeyError):
            pass
    if archive:
        arch = archive.get("closed_trades_ledger") or []
        A = {(t.get("ticker"), str(t.get("exitDate"))[:10]): _num(t.get("pnlUsd"), 0.0) for t in arch}
        T = {(t["ticker"], t["exit_date"]): t for t in trades if t["tag"] == "aegis"}
        for k in sorted(set(A) | set(T), key=lambda k: (k[1] or "", k[0] or "")):
            av, tv = A.get(k), T.get(k)
            if av is None:
                recon["vs_archive"].append({"ticker": k[0], "exit_date": k[1], "archive_usd": None, "journal_net_usd": tv["net_pnl_usd"], "note": "in trade journal, NOT in archive"})
            elif tv is None:
                recon["vs_archive"].append({"ticker": k[0], "exit_date": k[1], "archive_usd": av, "journal_net_usd": None, "note": "in archive, NO trade in journal"})
            else:
                diff = round((tv["net_pnl_usd"] or 0.0) - av, 2)
                if abs(diff) > max(1.0, abs(tv.get("fees_usd") or 0.0) + 1.0):
                    recon["vs_archive"].append({"ticker": k[0], "exit_date": k[1], "archive_usd": av, "journal_net_usd": tv["net_pnl_usd"],
                                                "journal_gross_usd": tv["gross_pnl_usd"], "diff_usd": diff,
                                                "note": "material difference beyond fees — archive entry price or qty differs from the fills"})
                    flags.append(f"{k[0]} {k[1]}: archive {av:+.2f} vs fills net {tv['net_pnl_usd']:+.2f} (diff {diff:+.2f})")
    store["reconciliation"] = recon
    if archive:
        a_total = round(sum(_num(t.get("pnlUsd"), 0.0) for t in arch), 2)
        j_total = store["stats"]["aegis"].get("net_pnl_usd", 0.0)
        store["stats"]["cross_check"] = {"archive_closed_trades": len(arch), "archive_realised_usd": a_total,
                                         "journal_aegis_net_usd": j_total, "difference_usd": round(j_total - a_total, 2),
                                         "archive_trade_count_vs_journal": [len(arch), store["stats"]["aegis"].get("trades", 0)]}
        if abs(j_total - a_total) > 1.0:
            flags.append(f"cross-check: trade journal Aegis net {j_total:+.2f} vs archive {a_total:+.2f} (diff {j_total - a_total:+.2f})")
    store["flags"] = flags
    times = [f["time_utc"] for f in store["fills"].values() if f["time_utc"]]
    store["latest_fill_utc"] = max(times) if times else None
    store["fill_count"] = len(store["fills"])
    store["updated_at_utc"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return store


# ----------------------------------------------------------------------------- render
def _f(x, d=2, signed=True):
    if x is None:
        return "—"
    return f"{x:+,.{d}f}" if signed else f"{x:,.{d}f}"


def render(store, fills_n=60):
    """The record, AEGIS ONLY (PM ruling 2026-09-06): closed trades, open lots, Aegis stock fills.
    Non-Aegis names and option legs never print — they exist in the store solely so lot matching is
    complete and idempotent."""
    st = store.get("stats", {}).get("aegis", {})
    trades = [t for t in store.get("trades", []) if t["tag"] == "aegis"]
    lots = [l for l in store.get("open_lots", []) if l["tag"] == "aegis"]
    out = [f"# Aegis trade journal — fills through {(store.get('latest_fill_utc') or '—')[:16]} UTC", ""]
    if st.get("trades"):
        out += ["## Closed-trade stats (net of fees)", "",
                "| Trades | W / L | Win rate | Net P&L | Gross | Fees | Avg win | Avg loss | Profit factor | Expectancy | Avg hold | Avg R (n) | Best | Worst |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
                f"| {st['trades']} | {st['wins']} / {st['losses']} | {st['win_rate_pct']}% | {_f(st['net_pnl_usd'])} | {_f(st['gross_pnl_usd'])} | "
                f"{_f(st['fees_usd'], signed=False)} | {_f(st['avg_win_usd'])} | {_f(st['avg_loss_usd'])} | {st['profit_factor'] if st['profit_factor'] is not None else '—'} | "
                f"{_f(st['expectancy_usd'])} | {st['avg_holding_days'] if st['avg_holding_days'] is not None else '—'}d | "
                f"{st['avg_r'] if st['avg_r'] is not None else '—'} ({st['r_known']}) | {_f(st['best_usd'])} | {_f(st['worst_usd'])} |", ""]
    cc = store.get("stats", {}).get("cross_check")
    if cc:
        out += [f"_Cross-check vs archive ledger: trade journal net {_f(cc['journal_aegis_net_usd'])} on {cc['archive_trade_count_vs_journal'][1]} trades · "
                f"archive {_f(cc['archive_realised_usd'])} on {cc['archive_closed_trades']} trades · difference {_f(cc['difference_usd'])}._", ""]
    out += ["## Closed trades (newest first)", "",
            "| Out | In | Ticker | Qty | Entry | Exit | Gross | Fees | Net P&L | % | Days | R | Notes |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in reversed(trades):
        notes = "; ".join(t.get("flags", [])) + (" partial" if t.get("partial") and "partial" not in "".join(t.get("flags", [])) else "")
        out.append(f"| {t['exit_date'] or '—'} | {t['entry_date'] or '—'} | {t['ticker']} | {t['qty']:g} | {_f(t['entry_price'], 4, False)} | "
                   f"{_f(t['exit_price'], 4, False)} | {_f(t['gross_pnl_usd'])} | {_f(t['fees_usd'], signed=False)} | {_f(t['net_pnl_usd'])} | "
                   f"{_f(t['pnl_pct'])} | {t['holding_days'] if t['holding_days'] is not None else '—'} | "
                   f"{t.get('r_multiple') if t.get('r_multiple') is not None else '—'} | {notes.strip() or ''} |")
    out += ["", "## Open positions", "", "| Ticker | Qty | Entry | Entry date | Days | Cost | Notes |", "|---|---|---|---|---|---|---|"]
    for l in sorted(lots, key=lambda l: l["entry_date"] or ""):
        out.append(f"| {l['ticker']} | {l['qty']:g} | {_f(l['entry_price'], 4, False)} | {l['entry_date'] or '—'} | "
                   f"{l['days_held'] if l['days_held'] is not None else '—'} | {_f(l['cost_usd'], signed=False)} | {'; '.join(l.get('flags', []))} |")
    fills = sorted((f for f in store.get("fills", {}).values() if f.get("tag") == "aegis" and f.get("sec_type") == "STK"),
                   key=lambda f: (f["time_utc"] or ""), reverse=True)
    shown = fills[:fills_n]
    out += ["", f"## Fills — last {len(shown)} of {len(fills)} Aegis stock fills on record (newest first)", "",
            "| Time UTC | Ticker | Side | Qty | Price | Comm+GST | Broker P&L |", "|---|---|---|---|---|---|---|"]
    for f in shown:
        out.append(f"| {(f['time_utc'] or '—')[:16]} | {f['ticker']} | {f['action']} | {f['qty']:g} | {_f(f['price'], 4, False)} | "
                   f"{_f(_fee(f), signed=False)} | {_f(f.get('broker_realized_pnl'))} |")
    rc = store.get("reconciliation") or {}
    if rc.get("vs_latest_journal") or rc.get("vs_archive"):
        out += ["", "## Reconciliation — findings, not corrections (the PM rules on these)", ""]
        for r in rc.get("vs_latest_journal", []):
            out.append(f"- **{r['ticker']}**: {r['open_per_fills']:g} open per fills vs {r['open_per_journal']:g} per {r['journal']} — {r['note']}")
        for r in rc.get("vs_archive", []):
            a = _f(r.get("archive_usd")); j = _f(r.get("journal_net_usd"))
            out.append(f"- **{r['ticker']} {r['exit_date']}**: archive {a} · trade journal net {j}" + (f" (gross {_f(r.get('journal_gross_usd'))})" if r.get("journal_gross_usd") is not None else "") + f" — {r['note']}")
        out.append("")
        out.append("_The archive ledger books P&L off the journal's average cost (buy commission included, sell commission not); this trade journal books FIFO lots net of all fees, which is what the broker's own realised P&L reports. Small differences are fees; large ones are findings._")
    if store.get("flags"):
        out += ["", "## Flags", ""] + [f"- {x}" for x in store["flags"]]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------- commands
def cmd_update(a):
    store = _load(a.store) if os.path.exists(a.store) else _empty_store()
    new = ingest_pull(store, a.pull, os.path.basename(os.path.dirname(a.pull.rstrip("/"))) or a.pull)
    archive = _load(a.archive) if a.archive and os.path.exists(a.archive) else None
    rebuild(store, a.journal_dir, archive)
    _write(a.out or a.store, store)
    st = store["stats"]["aegis"]
    print(json.dumps({"ok": True, "new_fills": new, "fills_on_record": store["fill_count"],
                      "closed_trades": len(store["trades"]), "open_lots": len(store["open_lots"]),
                      "aegis_net_pnl_usd": st.get("net_pnl_usd"), "aegis_trades": st.get("trades"),
                      "cross_check_diff_usd": (store["stats"].get("cross_check") or {}).get("difference_usd"),
                      "flags": len(store["flags"]), "out": a.out or a.store}))
    return 0


def cmd_backfill(a):
    store = _load(a.store) if os.path.exists(a.store) else _empty_store()
    per = {}
    for d in sorted(glob.glob(os.path.join(a.eod_dir, "*", "broker_pull"))):
        per[d.split(os.sep)[-2]] = ingest_pull(store, d, d.split(os.sep)[-2])
    archive = _load(a.archive) if a.archive and os.path.exists(a.archive) else None
    rebuild(store, a.journal_dir, archive)
    _write(a.out or a.store, store)
    print(json.dumps({"ok": True, "new_fills_per_pull": per, "fills_on_record": store["fill_count"],
                      "closed_trades": len(store["trades"]), "open_lots": len(store["open_lots"]),
                      "stats": store["stats"], "flags": store["flags"], "out": a.out or a.store}, indent=1))
    return 0


def cmd_render(a):
    md = render(_load(a.store), a.fills)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w") as f:
            f.write(md)
    sys.stdout.write(md)
    return 0


# ----------------------------------------------------------------------------- selftest
def selftest():
    import shutil
    tmp = tempfile.mkdtemp(prefix="tj_")
    try:
        ms = lambda s: int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        def fill(i, sym, act, q, px, t, pnl=None, comm=1.0, sec="STK"):
            return {"id": i, "symbol": sym, "action": act, "filled": q, "quantity": q, "avg_fill_price": px,
                    "trade_time": ms(t), "commission": comm, "gst": 0.0, "realized_pnl": pnl, "sec_type": sec}
        day1 = [fill(1, "AAA", "BUY", 100, 10.0, "2026-09-01T14:00"),
                fill(2, "ZZZ", "SELL", 50, 20.0, "2026-09-01T15:00", pnl=250.0),     # pre-window entry → seed
                fill(9, "OPT1", "BUY", 1, 1.5, "2026-09-01T16:00", sec="OPT")]
        day2 = day1 + [fill(3, "AAA", "BUY", 100, 12.0, "2026-09-02T14:00"),
                       fill(4, "AAA", "SELL", 150, 13.0, "2026-09-03T14:00", pnl=349.0),
                       fill(5, "NNN", "BUY", 10, 5.0, "2026-09-03T15:00"),
                       fill(6, "NNN", "SELL", 10, 4.0, "2026-09-04T15:00", pnl=-12.0)]
        for d, rows in (("2026-09-02", day1), ("2026-09-05", day2)):
            os.makedirs(os.path.join(tmp, "eod", d, "broker_pull"))
            json.dump({"result": rows}, open(os.path.join(tmp, "eod", d, "broker_pull", "tiger_filled_orders.json"), "w"))
        os.makedirs(os.path.join(tmp, "journal"))
        json.dump({"date": "2026-09-01", "open_positions": [
            {"ticker": "ZZZ", "qty": 50, "entry": 15.0, "entry_date": "2026-08-20", "aegis_status": "confirmed", "stop_reference": 14.0},
            {"ticker": "AAA", "qty": 100, "entry": 10.0, "entry_date": "2026-09-01", "aegis_status": "confirmed", "stop_reference": 9.0},
            {"ticker": "NNN", "qty": 10, "entry": 5.0, "entry_date": "2026-09-03", "aegis_status": "excluded_non_aegis"}]},
            open(os.path.join(tmp, "journal", "aegis_journal_2026-09-01.json"), "w"))
        store = _empty_store()
        for d in sorted(glob.glob(os.path.join(tmp, "eod", "*", "broker_pull"))):
            ingest_pull(store, d, d)
        assert store["fills"] and len(store["fills"]) == 7, len(store["fills"])          # union, no duplicates
        archive = {"closed_trades_ledger": [{"pnlUsd": 249.0}, {"pnlUsd": 349.0}]}
        rebuild(store, os.path.join(tmp, "journal"), archive)
        T = {(t["ticker"], t["exit_date"]): t for t in store["trades"]}
        z = T[("ZZZ", "2026-09-01")]
        assert "journal_seed" in z["flags"] and z["entry_price"] == 15.0 and z["gross_pnl_usd"] == 250.0 and z["net_pnl_usd"] == 249.0
        assert z["r_multiple"] == round(249.0 / ((15.0 - 14.0) * 50), 2)
        a = T[("AAA", "2026-09-03")]
        # FIFO: 100@10 + 50@12 → entry 10.6667, gross (13-10.6667)*150 = 350
        assert abs(a["entry_price"] - 10.6667) < 1e-3 and a["gross_pnl_usd"] == 350.0 and a["partial"] is True
        assert a["entry_date"] == "2026-09-01" and a["holding_days"] == 2 and a["tag"] == "aegis"
        n = T[("NNN", "2026-09-04")]
        assert n["tag"] == "non_aegis" and n["net_pnl_usd"] == -12.0
        lots = {l["ticker"]: l for l in store["open_lots"]}
        assert lots["AAA"]["qty"] == 50 and lots["AAA"]["entry_price"] == 12.0
        st = store["stats"]["aegis"]
        assert st["trades"] == 2 and st["wins"] == 2 and st["net_pnl_usd"] == round(249.0 + (350.0 - a["fees_usd"]), 2)
        assert store["stats"]["cross_check"]["archive_closed_trades"] == 2
        assert all(f["tag"] for f in store["fills"].values())
        # idempotent: ingest the same pulls again → nothing new, same trades
        n0 = len(store["fills"]); t0 = json.dumps(store["trades"], sort_keys=True)
        for d in sorted(glob.glob(os.path.join(tmp, "eod", "*", "broker_pull"))):
            assert ingest_pull(store, d, d) == 0
        rebuild(store, os.path.join(tmp, "journal"), archive)
        assert len(store["fills"]) == n0 and json.dumps(store["trades"], sort_keys=True) == t0
        md = render(store)
        assert "| ZZZ |" in md and "journal_seed" in md and "## Open positions" in md and "NNN" not in md and "OPT" not in md
        print("trade_journal selftest OK — fills unioned by broker id (idempotent), FIFO round-trips with weighted "
              "entry/partials/fees/R, pre-window sells matched to a flagged journal seed, non-Aegis kept and tagged, "
              "Aegis-only stats, archive cross-check, options kept in the fills log, render complete.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update"); u.add_argument("--pull", required=True); u.add_argument("--journal-dir", required=True)
    u.add_argument("--store", required=True); u.add_argument("--archive"); u.add_argument("--out"); u.set_defaults(fn=cmd_update)
    b = sub.add_parser("backfill"); b.add_argument("--eod-dir", required=True); b.add_argument("--journal-dir", required=True)
    b.add_argument("--store", required=True); b.add_argument("--archive"); b.add_argument("--out"); b.set_defaults(fn=cmd_backfill)
    r = sub.add_parser("render"); r.add_argument("--store", required=True); r.add_argument("--out"); r.add_argument("--fills", type=int, default=60)
    r.set_defaults(fn=cmd_render)
    s = sub.add_parser("selftest"); s.set_defaults(fn=lambda a: selftest())
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
