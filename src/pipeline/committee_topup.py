"""committee_topup.py -- give every name Report B screens the same committee data the export names get (conductor defect 2026-11-10).

Report B's screens read the whole universe (~1,100 rows) but committee_data (fundamentals pack, W/D/H1 grid, closes) is built for the export's daily_list
(~470 names). A screened name outside it had NO MTF and NO fundamentals, so seats could only say CANNOT_SEE and the name was dropped on a data gap,
not on merit. This step runs AFTER `screens`: it takes the names (from seat_sets.json, an explicit list, or by re-running the deterministic seat
screens over the universe rows), finds the ones missing from the three committee_data files, pulls them with the SAME fetchers committee_data uses,
merges them in, refreshes the manifest, and (with --publish) pushes the files to aegis/output/committee_data/ on main.

LOUD: if any requested name still has no fundamentals, no served MTF row or no closes after the pull, the step prints the names, writes
topup_report.json and exits 2. Never silent.

    python -m src.pipeline.committee_topup --names AMPL,BRZE --screens --publish
    python -m src.pipeline.committee_topup --seat-sets aegis/output/pma/run/<date>-B/seat_sets.json --publish
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

from src.data.paths import PROJECT_ROOT
from src.pipeline import committee_data as cd

DEFAULT_DIR = PROJECT_ROOT / "aegis" / "output" / "committee_data"
UNIVERSE_ROWS_REPO = PROJECT_ROOT / "aegis" / "output" / "aqe_universe_rows.json"
SCREEN_TOP = 10          # Report B reads the top 10 per seat (PM 2026-11-10)
FUND_OK = ("served", "carried", "partial")


def _screens_mod():
    for rel in ("aegis/skills/premarket-analysis/tools/seat_screens.py", "aegis/plugin/aegis-core/skills/pma/tools/seat_screens.py"):
        p = PROJECT_ROOT / rel
        if p.exists():
            spec = importlib.util.spec_from_file_location("committee_topup_screens", p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    raise RuntimeError("seat_screens.py not found")


def load_universe_rows(path: Path | None = None) -> list[dict]:
    d = cd._read_json(path or UNIVERSE_ROWS_REPO)
    rows = d.get("rows") if isinstance(d, dict) else d
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("ticker")]


def screen_picks(rows: list[dict], top: int = SCREEN_TOP) -> list[str]:
    """The names the seven Report B screens would seat (deterministic, same code as `pma_pipeline.py screens`)."""
    if not rows:
        return []
    res = _screens_mod().all_screens(rows, top)
    return sorted({x["ticker"] for v in res.values() for x in v})


def names_from_seat_sets(path: Path) -> list[str]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return sorted({x["ticker"] for v in (d.get("seats") or {}).values() for x in v})


def missing(names, fund: dict, grid: dict, closes: dict) -> dict:
    ft, gn = fund.get("tickers") or {}, grid.get("names") or {}
    cmiss = set(closes.get("_missing") or [])
    return {"fundamentals": [t for t in names if (ft.get(t) or {}).get("status") not in FUND_OK],
            "mtf": [t for t in names if not (gn.get(t) or {}).get("served")],
            "closes": [t for t in names if t not in closes or t in cmiss]}


def _fund_cov(fund: dict) -> dict:
    ft = fund["tickers"]
    c = fund.get("coverage") or {}
    partial = sorted(t for t, e in ft.items() if e["status"] == "partial")
    unserved = sorted(t for t, e in ft.items() if e["status"] == "unserved")
    return {**c, "requested": len(ft), "served": sum(1 for e in ft.values() if e["status"] in ("served", "carried")),
            "carried": sum(1 for e in ft.values() if e["status"] == "carried"), "partial": len(partial), "unserved": len(unserved),
            "partial_names": partial, "unserved_names": unserved}


def _grid_cov(grid: dict) -> dict:
    n = grid["names"]
    c = grid.get("coverage") or {}
    return {**c, "requested": len(n), "served": sum(1 for r in n.values() if r["served"]), "complete": sum(1 for r in n.values() if r.get("complete")),
            "not_served": sum(1 for r in n.values() if not r["served"]), "not_served_names": sorted(t for t, r in n.items() if not r["served"])}


def topup(names, run_date: str, fund: dict, grid: dict, closes: dict, universe_rows: list[dict], client, panel: dict | None = None,
          mtf=None, budget_s: float = 1800.0) -> dict:
    """Pull what is missing for `names` and merge it into fund / grid / closes IN PLACE. -> report dict (never raises on a fetch failure)."""
    names = sorted({t for t in names if t})
    before = missing(names, fund, grid, closes)
    f = cd.Fetcher(client, budget_s=budget_s)
    mtf = mtf or cd._mtf()
    last_close = {r["ticker"]: r.get("last_close") or r.get("entry") for r in universe_rows}
    todo = sorted(set(before["fundamentals"]) | set(before["mtf"]) | set(before["closes"]))
    panel = panel if panel is not None else cd.load_panel_daily(sorted(set(todo) | {cd.BENCH}))
    for t in before["fundamentals"]:
        fund.setdefault("tickers", {})[t] = cd.fetch_fundamentals_one(f, t, run_date)
    daily_cache: dict = {}
    if before["mtf"]:
        sub = cd.build_grid(f, before["mtf"], run_date, {"daily_list": [{"ticker": t, "entry": last_close.get(t)} for t in before["mtf"]]},
                            panel, mtf, daily_cache)
        grid.setdefault("names", {}).update(sub["names"])
    if before["closes"]:
        new, detail = cd.build_closes(f, before["closes"], run_date, panel, daily_cache)
        still = set(new.pop("_missing", []))
        closes.update(new)
        closes["_missing"] = sorted((set(closes.get("_missing") or []) - set(before["closes"])) | still)
    fund["coverage"], grid["coverage"] = _fund_cov(fund), _grid_cov(grid)
    after = missing(names, fund, grid, closes)
    return {"run_date": run_date, "names": len(names), "pulled": len(todo), "fmp_calls": f.calls, "errors": f.errors[:50],
            "missing_before": before, "still_missing": after, "ok": not any(after.values()),
            "unserved_names": sorted(set().union(*after.values()))}


def verify(names, fund: dict, grid: dict, closes: dict) -> None:
    """The regression gate: every named ticker has a fundamentals row, a served MTF row and closes, or this raises."""
    m = missing(names, fund, grid, closes)
    if any(m.values()):
        raise RuntimeError("committee data does not cover the screened names: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in m.items() if v))


def _manifest(fund, grid, closes, base: dict, run_date: str, rep: dict) -> tuple[dict, dict]:
    bodies = {"fundamentals_pack.json": cd.dumps(fund), "mtf_grid.json": cd.dumps(grid), "closes_scorecard.json": cd.dumps(closes)}
    fc, gc = fund["coverage"], grid["coverage"]
    nc = len([k for k in closes if k != "_missing"])
    files = {"fundamentals_pack.json": cd._file_entry("fundamentals_pack.json", bodies["fundamentals_pack.json"], "fundamentals_pack.v1",
                                                      fc["requested"], fc["served"], fc["unserved"] + fc["partial"], run_date),
             "mtf_grid.json": cd._file_entry("mtf_grid.json", bodies["mtf_grid.json"], "mtf_grid.v1",
                                             gc["requested"], gc["complete"], gc["requested"] - gc["complete"], run_date),
             "closes_scorecard.json": cd._file_entry("closes_scorecard.json", bodies["closes_scorecard.json"], "closes_scorecard.v1",
                                                     nc + len(closes["_missing"]), nc, len(closes["_missing"]), run_date)}
    m = {**base, "files": files, "status": cd.status_of(files), "fmp_calls": (base.get("fmp_calls") or 0) + rep["fmp_calls"],
         "scope": {**(base.get("scope") or {}), "requested": fc["requested"], "from": "export daily_list + held_positions + Report B screened names (topup)"},
         "topup": {"names": rep["names"], "pulled": rep["pulled"], "fmp_calls": rep["fmp_calls"], "unserved_names": rep["unserved_names"]}}
    return m, bodies


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--names", default="", help="comma-separated tickers")
    ap.add_argument("--seat-sets", default=None)
    ap.add_argument("--screens", action="store_true", help="add the names the seven Report B screens seat (top 10 per seat) over the universe rows")
    ap.add_argument("--universe-rows", default=None)
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    ap.add_argument("--date", default=None)
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args(argv)
    d = Path(a.dir)
    fund, grid, closes = (cd._read_json(d / n) for n in ("fundamentals_pack.json", "mtf_grid.json", "closes_scorecard.json"))
    base = cd._read_json(d / cd.MANIFEST) or {}
    if not (isinstance(fund, dict) and isinstance(grid, dict) and isinstance(closes, dict)):
        print("[topup] FAILED: the committee_data files are missing or unreadable in", d)
        return 2
    run_date = a.date or grid.get("run_date")
    rows = load_universe_rows(Path(a.universe_rows) if a.universe_rows else None)
    names = {t.strip().upper() for t in a.names.split(",") if t.strip()}
    if a.seat_sets:
        names |= set(names_from_seat_sets(Path(a.seat_sets)))
    if a.screens:
        if not rows:
            print("[topup] FAILED: --screens needs the universe rows file and it is missing or empty")
            return 2
        names |= set(screen_picks(rows))
    if not names:
        print("[topup] FAILED: no names given (--names / --seat-sets / --screens)")
        return 2
    miss = missing(sorted(names), fund, grid, closes)
    print(f"[topup] {len(names)} names; missing before: fundamentals {len(miss['fundamentals'])}, mtf {len(miss['mtf'])}, closes {len(miss['closes'])}")
    if not any(miss.values()):
        print("[topup] nothing missing: every requested name already has fundamentals, MTF and closes")
        return 0
    if not (d / "mtf_grid.json").exists():
        return 2
    from src.data.fmp_client import FMPClient
    if cd.DATA_DIR and not (cd.DATA_DIR / "panel_daily.parquet").exists():
        try:
            from src.data import persist
            print("[topup] restoring the panel:", persist.load_snapshot_best(only=["panel_daily.parquet"]).get("ok"))
        except Exception as exc:  # noqa: BLE001 - without the panel the daily bars are fetched from FMP instead
            print(f"[topup] panel restore skipped ({exc}); daily bars will come from FMP")
    rep = topup(sorted(names), run_date, fund, grid, closes, rows, FMPClient())
    manifest, bodies = _manifest(fund, grid, closes, base, run_date, rep)
    for n, body in bodies.items():
        (d / n).write_bytes(body)
    (d / cd.MANIFEST).write_bytes(cd.dumps(manifest))
    (d / "topup_report.json").write_bytes(cd.dumps(rep))
    print(f"[topup] pulled {rep['pulled']} names, {rep['fmp_calls']} FMP calls; still missing: {rep['still_missing']}")
    if a.publish:
        pub = cd.publish({"manifest": manifest, "files": {**bodies, "topup_report.json": cd.dumps(rep)}})
        print("[topup] publish:", {k: pub.get(k) for k in ("ok", "written", "total", "failed")})
        if not pub.get("ok"):
            return 2
    if not rep["ok"]:
        print("[topup] LOUD: these screened names STILL have no full committee data:", ", ".join(rep["unserved_names"]))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
