#!/usr/bin/env python3
"""Nomination Ledger — every voice's and the committee's nominations, tracked against price.

The system's outcome memory (constitution law 7). Three commands:

  record  --date D --nominations-dir data/committee/DATE/   append the day's nominations
  track   --prices data/prices.json                          update d1..d15 / max gain / max drawdown
  report  [--days 15] [--voice lynch]                        hit rates & expectancy per voice

Ledger continuity (RB:universe.ledger_continuity): names that leave the daily screen
stay tracked until their 15-day window closes.
Storage: data/ledger/ledger.jsonl (append-only; one JSON object per line, schema contracts/ledger.schema.json).
"""
import argparse, json, os, sys, glob
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.environ.get("AEGIS_LEDGER", os.path.join(ROOT, "data", "persistent", "ledger.jsonl"))  # QA-F12: ROOT-anchored, persistent shelf
WINDOW_DAYS = 15
CHECKPOINTS = [1, 3, 5, 10, 15]


def _load():
    if not os.path.exists(LEDGER):
        return []
    return [json.loads(l) for l in open(LEDGER) if l.strip()]


def _save(rows):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def record(args):
    rows = _load()
    seen = {(r["date"], r["voice"], r["ticker"]) for r in rows}
    added = 0
    skipped = 0
    for path in glob.glob(os.path.join(args.nominations_dir, "*.json")):
        try:
            nom = json.load(open(path))
            if "nominations" not in nom or "date" not in nom or "voice" not in nom:
                skipped += 1; continue
        except Exception:
            skipped += 1; continue
        for n in nom["nominations"]:
            key = (nom["date"], nom["voice"], n["ticker"])
            if key in seen:
                continue
            rows.append({
                "date": nom["date"], "voice": nom["voice"], "ticker": n["ticker"],
                "conviction": n.get("conviction"), "reason": n.get("reason", ""),
                "price_at_nomination": n.get("price_at_nomination"),
                "deliberated": n.get("deliberated", False),
                "committee_position": n.get("committee_position"),
                "actioned": n.get("actioned", False),
                "in_universe": True,
                "tracking": {"closed": False},
            })
            seen.add(key)
            added += 1
    _save(rows)
    print(f"recorded {added} nominations ({skipped} malformed files skipped); ledger now {len(rows)} rows")


def track(args):
    """prices file: {"TICKER": {"YYYY-MM-DD": close, ...}, ...} — produced by the data hub daily."""
    prices = json.load(open(args.prices))
    rows = _load()
    today = date.today()
    updated = 0
    for r in rows:
        t = r["tracking"]
        if t.get("closed"):
            continue
        series = prices.get(r["ticker"], {})
        base = r.get("price_at_nomination")
        path = sorted((d, p) for d, p in series.items() if d >= r["date"])
        if base is None and path:
            base = path[0][1]   # DS-F4: anchor at first bar >= nomination date, explicitly d0
            r["price_at_nomination"] = base
        if not base or not path:
            t["no_data"] = True   # DS-F4: excluded rows are COUNTED, not silently dropped
            updated += 1
            continue
        closes = [p for _, p in path]
        t["max_gain_pct"] = round((max(closes) / base - 1) * 100, 2)
        t["max_drawdown_pct"] = round((min(closes) / base - 1) * 100, 2)
        for cp in CHECKPOINTS:
            if len(path) > cp:                       # DS-F1: TRADING-day indexed, no calendar gate
                t[f"d{cp}"] = round((path[cp][1] / base - 1) * 100, 2)
        if len(path) > WINDOW_DAYS:                  # DS-F1: close after 15 TRADING bars — d15 now reachable
            t["closed"] = True
        updated += 1
    _save(rows)
    print(f"tracked {updated} open rows")


def report(args):
    rows = _load()
    if args.voice:
        rows = [r for r in rows if r["voice"] == args.voice]
    byv = {}
    for r in rows:
        t = r["tracking"]
        if t.get("d5") is None:
            continue
        v = byv.setdefault(r["voice"], {"n": 0, "wins5": 0, "sum5": 0.0, "sum_maxg": 0.0})
        v["n"] += 1
        v["sum5"] += t["d5"]
        v["sum_maxg"] += t.get("max_gain_pct") or 0
        if t["d5"] > 0:
            v["wins5"] += 1
    excl = sum(1 for r in rows if r["tracking"].get("no_data"))
    print(f"(excluded for missing price data: {excl} rows — survivorship note DS-F4)")
    print(f"{'voice':<15}{'n':>5}{'hit%@d5':>9}{'avg d5%':>9}{'avg maxG%':>10}")
    for v, s in sorted(byv.items(), key=lambda kv: -(kv[1]['sum5'] / max(kv[1]['n'], 1))):
        n = s["n"]
        print(f"{v:<15}{n:>5}{100*s['wins5']/n:>8.1f}%{s['sum5']/n:>8.2f}%{s['sum_maxg']/n:>9.2f}%")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record"); r.add_argument("--date"); r.add_argument("--nominations-dir", required=True)
    t = sub.add_parser("track"); t.add_argument("--prices", required=True)
    p = sub.add_parser("report"); p.add_argument("--days", type=int, default=15); p.add_argument("--voice")
    a = ap.parse_args()
    {"record": record, "track": track, "report": report}[a.cmd](a)
