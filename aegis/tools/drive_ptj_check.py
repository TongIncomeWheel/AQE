#!/usr/bin/env python3
"""Drive PTJ freshness check (D-69) — independent verification that the day's PTJ actually
landed in Drive, not just that the kernel BELIEVED it wrote it.

WHY THIS EXISTS: the PM asked why Design & Review's own assurance layer (auditor,
daily_flow_audit.py) never caught the 07-18→07-20 stale-PTJ gap. Answer: every kernel audit
tool reads local repo files only — it checks "did post_market's OWN write succeed", never
"does Drive actually show a fresh file". That is a real blind spot: if a future Drive write
silently errors (wrong folder id, auth hiccup, API 500) the kernel could believe it wrote a
PTJ while Drive shows nothing new — and nothing would catch it, same failure class as before
just one layer deeper. This tool closes that gap by treating the Drive listing as the ground
truth, not the kernel's own belief about what it did.

SPLIT OF RESPONSIBILITY (matches archive_ledger.py's pattern): this tool does NOT call Drive
itself (plain python has no MCP access). The orchestrating session (post_market step 3, the
auditor) runs `mcp__Google_Drive__search_files` for `parentId = '<PTJ folder>' and title
contains 'PTJ'`, saves the raw result JSON, and calls this tool on it. The tool is pure
deterministic verdict logic (law 4) — given a listing + a target date, decide FRESH / STALE /
MISSING, and separately count files for the >10 housekeeping flag (BL-046).

Usage:
  python3 tools/drive_ptj_check.py check --listing drive_search_result.json --date 2026-07-21 [--out out.json]
  python3 tools/drive_ptj_check.py selftest
"""
import json
import argparse
import sys
import re

PTJ_TITLE_RE = re.compile(r"^aegis_trade_journal_(\d{4}-\d{2}-\d{2})_PTJ\.json$")


def evaluate(files, target_date):
    """files: list of Drive file dicts (must have 'title'; 'modifiedTime' optional).
    Returns a verdict dict. Never raises on malformed entries — a bad record is skipped,
    not fatal (an audit check must not itself become a new failure mode)."""
    ptj_files = []
    for f in files:
        title = f.get("title") or f.get("name") or ""
        m = PTJ_TITLE_RE.match(title)
        if m:
            ptj_files.append({"title": title, "date": m.group(1),
                               "modifiedTime": f.get("modifiedTime"), "id": f.get("id")})

    dated = sorted(ptj_files, key=lambda x: x["date"], reverse=True)
    latest = dated[0] if dated else None

    if latest is None:
        status = "MISSING"
    elif latest["date"] == target_date:
        status = "FRESH"
    else:
        status = "STALE"  # a PTJ exists but not for the target date

    return {
        "status": status,
        "target_date": target_date,
        "latest_ptj_date": latest["date"] if latest else None,
        "latest_ptj_title": latest["title"] if latest else None,
        "latest_ptj_modified": latest["modifiedTime"] if latest else None,
        "total_ptj_files_in_folder": len(ptj_files),
        "housekeeping_flag": len(ptj_files) > 10,
        "note": ("no PTJ file for today found in Drive — the kernel's write either failed "
                 "silently or landed somewhere unexpected; page the PM" if status != "FRESH"
                 else "today's PTJ confirmed present in Drive (independent of the write step's own report)"),
    }


def _selftest():
    files = [
        {"title": "aegis_trade_journal_2026-07-20_PTJ.json", "modifiedTime": "2026-07-21T02:28:39Z", "id": "x1"},
        {"title": "aegis_trade_journal_2026-07-17_PTJ.json", "modifiedTime": "2026-07-17T04:20:41Z", "id": "x2"},
        {"title": "aegis_trade_journal_ARCHIVE_master.json", "modifiedTime": "2026-07-17T04:20:15Z", "id": "x3"},  # not a PTJ file, must be ignored
        {"title": "some_unrelated_file.json", "modifiedTime": "2026-07-20T00:00:00Z", "id": "x4"},
    ]
    fresh = evaluate(files, "2026-07-20")
    assert fresh["status"] == "FRESH", fresh
    assert fresh["total_ptj_files_in_folder"] == 2, fresh

    stale = evaluate(files, "2026-07-21")
    assert stale["status"] == "STALE" and stale["latest_ptj_date"] == "2026-07-20", stale

    missing = evaluate([], "2026-07-21")
    assert missing["status"] == "MISSING", missing

    many = [{"title": f"aegis_trade_journal_2026-07-{d:02d}_PTJ.json", "modifiedTime": "x"} for d in range(1, 13)]
    hk = evaluate(many, "2026-07-12")
    assert hk["housekeeping_flag"] is True and hk["total_ptj_files_in_folder"] == 12, hk
    print("drive_ptj_check.py selftest: PASS")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify today's PTJ actually landed in Drive (D-69)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("--listing", required=True, help="path to the raw Drive search_files JSON result")
    c.add_argument("--date", required=True, help="YYYY-MM-DD, today's session date")
    c.add_argument("--out", help="write verdict JSON here (default: stdout)")

    sub.add_parser("selftest")

    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        _selftest()
        return

    raw = json.load(open(a.listing))
    files = raw.get("files", raw) if isinstance(raw, dict) else raw
    verdict = evaluate(files, a.date)
    out = json.dumps(verdict, indent=1)
    if a.out:
        open(a.out, "w").write(out)
    print(out)
    if verdict["status"] != "FRESH":
        sys.exit(1)  # non-zero so a calling shell step notices without parsing JSON


if __name__ == "__main__":
    main()
