"""Record when each external feed actually posts its newest session (conductor Q1, 2026-11-04).

Each nightly appends one entry: every Cboe core file's Last-Modified and newest row, and the CFTC weekly file's Last-Modified
and report date. Last-Modified shows only the LATEST publish, so history can only be built by recording it every night; after a
week the 'first posted' times for the last sessions are a file, not a guess. Never raises into the run.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.data.paths import OUTPUT_DIR, PROJECT_ROOT

CBOE = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{s}_History.csv"
CBOE_CORE = ("VIX", "VIXEQ", "VIX3M", "VIX9D", "DSPX", "COR1M")
CFTC = "https://www.cftc.gov/dea/newcot/deafut.txt"
KEEP = 120
FILE = "feed_timing.json"
REPO_COPY = PROJECT_ROOT / "aegis" / "output" / FILE


def probe(get=None) -> dict:
    import requests
    get = get or (lambda u: requests.get(u, timeout=45, headers={"User-Agent": "Mozilla/5.0"}))
    out = {"cboe": {}, "cftc": {}}
    for s in CBOE_CORE:
        try:
            r = get(CBOE.format(s=s))
            rows = [x for x in r.text.strip().splitlines() if x[:1].isdigit()]
            out["cboe"][s] = {"http": r.status_code, "last_modified": r.headers.get("Last-Modified"),
                              "newest_row_date": rows[-1].split(",")[0] if rows else None}
        except Exception as e:  # noqa: BLE001
            out["cboe"][s] = {"error": f"{e.__class__.__name__}: {e}"}
    try:
        r = get(CFTC)
        first = r.text.splitlines()[0] if r.text else ""
        parts = first.split(",")
        out["cftc"] = {"http": r.status_code, "last_modified": r.headers.get("Last-Modified"),
                       "report_date": parts[2].strip() if len(parts) > 2 else None}
    except Exception as e:  # noqa: BLE001
        out["cftc"] = {"error": f"{e.__class__.__name__}: {e}"}
    return out


def record(run_date: str, *, legs: list | None = None, out_dir: Path | None = None, previous_path: Path | None = None, get=None) -> dict:
    """Append this run's probe to the history and write feed_timing.json. -> the whole document (never raises)."""
    out_dir = Path(out_dir or OUTPUT_DIR)
    prev = []
    for p in (previous_path, REPO_COPY, out_dir / FILE):
        try:
            if p and Path(p).exists():
                prev = (json.loads(Path(p).read_text(encoding="utf-8")) or {}).get("history") or []
                break
        except Exception:  # noqa: BLE001
            continue
    try:
        entry = {"run_date": run_date, "probed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **probe(get)}
    except Exception as e:  # noqa: BLE001
        entry = {"run_date": run_date, "error": f"{e.__class__.__name__}: {e}"}
    if legs:       # the legs table of this run, so 'behind two nights running' is answerable from this one file
        entry["legs"] = [{"leg": r.get("leg"), "as_of": r.get("as_of"), "reason": r.get("reason")} for r in legs]
    hist = [h for h in prev if h.get("run_date") != run_date] + [entry]
    doc = {"schema": "feed_timing.v1", "note": "Last-Modified of each feed at the time of each nightly probe; first-posted times accumulate here",
           "history": hist[-KEEP:]}
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / FILE).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return doc
