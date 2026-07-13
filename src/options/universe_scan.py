"""Universe theta scanner — sweep the whole AQE universe for CSPs to sell.

Loads the AQE universe (the already-liquid "fishing net"), pulls each name's put
chain from Alpaca in one call, runs the pure CSP engine per name, aggregates the
survivors into one ranked table, and writes `output/options_scan.json` for the
Streamlit page + downstream readers.

Throttle budget (Alpaca free 200 req/min): ~1 chain call per name + a handful of
batched spot calls → a 600-name sweep is ~3 minutes, no per-contract fan-out.

Recommend-only — it computes numbers; the AIC decides + sizes. The provider is
injectable so the orchestration unit-tests without network or API keys.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import config as C
from .scanner import scan_csps, rank
from .providers import alpaca


def scan_universe(tickers=None, today: date = None, dte_min=None, dte_max=None,
                  r=None, q=None, fill="mid", rank_key=None, filters=None,
                  fetch_spots=None, fetch_put_chain=None, log=print) -> dict:
    """Sweep `tickers` (default: the AQE universe) for sellable CSPs.

    `fetch_spots(symbols)->{sym:spot}` and `fetch_put_chain(tk, spot, today, dte_min,
    dte_max)->[contract]` default to the Alpaca provider; inject stubs to test.
    `filters` overrides the per-name `scan_csps` wheel filters. Returns the scan
    blob (also the shape written to disk).
    """
    today = today or date.today()
    dte_min = C.UNIVERSE_DTE_MIN if dte_min is None else dte_min
    dte_max = C.UNIVERSE_DTE_MAX if dte_max is None else dte_max
    rank_key = C.SCAN_RANK_KEY if rank_key is None else rank_key
    filters = filters or {}
    get_spots = fetch_spots or alpaca.fetch_spots
    get_chain = fetch_put_chain or alpaca.fetch_put_chain

    if tickers is None:
        from src.data.universe import load_universe
        tickers = load_universe(include_benchmark=False)

    spots = get_spots(list(tickers))
    log(f"[universe-scan] {len(tickers)} names, {len(spots)} spots, "
        f"DTE {dte_min}-{dte_max}")

    candidates, no_spot, errored = [], [], []
    for tk in tickers:
        spot = spots.get(tk)
        if not spot:
            no_spot.append(tk)
            continue
        try:
            chain = get_chain(tk, spot, today, dte_min, dte_max)
        except Exception as e:                          # one bad name never kills the run
            errored.append(tk)
            log(f"[universe-scan] {tk}: {type(e).__name__} {e}")
            continue
        res = scan_csps(chain, r=r, q=q, fill=fill,
                        dte_min=dte_min, dte_max=dte_max, min_oi=0, **filters)
        candidates.extend(res["passed"])

    ranked = rank(candidates, rank_key)
    blob = {
        "generated_for": today.isoformat(),
        "dte_window": [dte_min, dte_max],
        "universe_size": len(tickers), "priced": len(spots),
        "candidates_count": len(ranked),
        "names_no_spot": no_spot, "names_errored": errored,
        "rank_key": rank_key,
        "candidates": ranked,
    }
    log(f"[universe-scan] {len(ranked)} CSP candidates across "
        f"{len({c['ticker'] for c in ranked})} names")
    return blob


def write_scan(blob: dict, path: str = None) -> str:
    path = path or C.UNIVERSE_SCAN_FILE
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(blob, indent=2, default=str), encoding="utf-8")
    return str(p)


def export_scan_to_drive(blob: dict, path: str = None) -> dict:
    """Write the local copy, then overwrite the single CSP file in the dedicated
    Drive folder (like AQE's export). Always writes local first, then best-effort
    uploads — a broken Drive OAuth degrades to a local-only copy, never raises.
    Returns {"local": <path>, "drive": {...}}.
    """
    import os
    local = write_scan(blob, path)
    folder = os.environ.get("GDRIVE_CSP_FOLDER_ID", C.GDRIVE_CSP_FOLDER_ID)
    try:
        from src.data import gdrive_uploader
        content = json.dumps(blob, indent=2, default=str)
        res = gdrive_uploader.upload_or_replace(
            C.CSP_SCAN_FILENAME, content, folder_id=folder)
        if res.get("ok") and res.get("file_id"):
            gdrive_uploader.keep_only_file(folder, res["file_id"])   # keep exactly one
    except Exception as e:                                            # pragma: no cover
        res = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    return {"local": local, "drive": res}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="AQE universe CSP theta scanner (Alpaca)")
    ap.add_argument("--tickers", default=None, help="comma list (default: AQE universe)")
    ap.add_argument("--dte-min", type=int, default=None)
    ap.add_argument("--dte-max", type=int, default=None)
    ap.add_argument("--out", default=C.UNIVERSE_SCAN_FILE)
    ap.add_argument("--top", type=int, default=30)
    a = ap.parse_args(argv)

    tickers = [t.strip().upper() for t in a.tickers.split(",")] if a.tickers else None
    blob = scan_universe(tickers=tickers, dte_min=a.dte_min, dte_max=a.dte_max)
    path = write_scan(blob, a.out)
    print(f"\nWrote {blob['candidates_count']} candidates → {path}\n")
    hdr = f"{'TICKER':7} {'STRIKE':>7} {'DTE':>4} {'DELTA':>6} {'ANN.YLD':>8} {'POP':>6} {'CUSH':>6}"
    print(hdr); print("-" * len(hdr))
    for m in blob["candidates"][:a.top]:
        print(f"{m['ticker']:7} {m['strike']:>7} {m['dte']:>4} "
              f"{(m.get('abs_delta') or 0):>6.3f} {(m.get('annual_yield') or 0)*100:>7.1f}% "
              f"{(m.get('pop_not_assigned') or 0)*100:>5.1f}% {(m.get('downside_cushion') or 0)*100:>5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
