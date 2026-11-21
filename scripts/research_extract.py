"""One-off RESEARCH extract of AQE's component / sub-component scores (conductor 2026-11-19, PM ask).

Run only from .github/workflows/research-extract.yml (workflow_dispatch). It is read-only against production:
  * every read and write happens in a SCRATCH data/output dir (AQE_DATA_DIR / AQE_OUTPUT_DIR are pointed at it
    BEFORE any src import, so src.data.paths resolves there);
  * it restores the nightly snapshot INTO that scratch dir, and never calls save_snapshot*;
  * the only outside writes are two new Drive files (aqe_research_*) and the Actions artifact.
No scoring, export or alert path is touched.

    python -m scripts.research_extract inventory
    python -m scripts.research_extract extract [--years 6] [--recompute] [--rescore]
    python -m scripts.research_extract truncation [--sample 20] [--lag 40]

NOT POINT-IN-TIME (stamped into the extract's meta and every inventory):
  survivorship (today's universe applied backwards), market cap (current only), sector (current map),
  and cross-sectional ranks (ranked inside today's universe). Weekly-bar leakage is TESTED by `truncation`.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRATCH = Path(os.environ.get("RESEARCH_SCRATCH") or tempfile.mkdtemp(prefix="aqe_research_"))
os.environ["AQE_DATA_DIR"] = str(SCRATCH / "data")        # must be set before ANY src import
os.environ["AQE_OUTPUT_DIR"] = str(SCRATCH / "output")
(SCRATCH / "data").mkdir(parents=True, exist_ok=True)
(SCRATCH / "output").mkdir(parents=True, exist_ok=True)
OUT = Path(os.environ.get("RESEARCH_OUT") or "research_out")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

NOT_POINT_IN_TIME = {
    "universe": "survivorship: today's universe screen (mcap >= $2B, 10d vol >= 500K, listed) applied backwards; the stored scores carry no history of who was in the universe on a given day",
    "market_cap": "mcap_current_not_pit is the CURRENT market cap; FMP gives no historical series here. dollar_vol_20d_pit (close x 20d avg volume) IS point-in-time",
    "sector": "current GICS ETF mapping from sector_map.json applied backwards",
    "cross_sectional": "any field ranked inside the universe (pipeline rank etc.) is ranked inside TODAY's universe",
    "weekly_bars": "see the `truncation` stage result for whether a forming weekly bar leaks into daily rows",
}
HORIZONS = (1, 5, 10, 20)
SNAPSHOT_FILES = ["panel_daily.parquet", "panel_weekly.parquet", "spy_daily.parquet", "scores_daily.parquet",
                  "sector_map.json", "aqe.db", "universe.txt", "earnings_history.json"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _restore() -> dict:
    from src.data import persist
    res = persist.load_snapshot_best(only=SNAPSHOT_FILES)
    if not res.get("ok"):
        raise SystemExit(f"RESTORE FAILED (loud, no silent empty): {res.get('reason')}")
    return {k: res.get(k) for k in ("store", "saved_at", "count", "tried")} | {"files": res.get("files")}


def _drive_put(name: str, blob: bytes, mime: str) -> dict:
    from src.data import gdrive_uploader
    r = gdrive_uploader.upload_or_replace(name, blob, mime=mime)
    if not r.get("ok"):
        print(f"DRIVE UPLOAD FAILED for {name}: {r.get('reason')}", file=sys.stderr)
    return {"name": name, "ok": bool(r.get("ok")), "file_id": r.get("file_id"), "reason": r.get("reason"), "bytes": len(blob)}


def _write_ids(entry: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "drive_ids.json"
    cur = json.loads(p.read_text()) if p.exists() else {}
    cur[entry["name"]] = entry
    p.write_text(json.dumps(cur, indent=1))


# ------------------------------------------------------------------------------------------------ inventory
def _parquet_facts(path: Path, extra_cols: list[str] | None = None) -> dict:
    if not path.exists():
        return {"present": False}
    df = pd.read_parquet(path)
    d = pd.to_datetime(df["date"]).dt.normalize()
    if "ticker" not in df.columns:                     # spy_daily.parquet is one series with no ticker column
        df = df.assign(ticker="SPY")
    per_date = df.groupby(d)["ticker"].nunique()
    facts = {"present": True, "rows": int(len(df)), "tickers": int(df["ticker"].nunique()),
             "date_min": str(d.min().date()), "date_max": str(d.max().date()), "sessions": int(d.nunique()),
             "rows_by_year": {str(k): int(v) for k, v in d.dt.year.value_counts().sort_index().items()},
             "names_per_date": {"min": int(per_date.min()), "median": int(per_date.median()), "max": int(per_date.max())},
             "columns": list(df.columns)}
    if extra_cols:
        by_year = {}
        for c in extra_cols:
            if c in df.columns:
                by_year[c] = {str(y): round(float(df.loc[d.dt.year == y, c].notna().mean()), 3) for y in sorted(d.dt.year.unique())}
        facts["non_null_share_by_year"] = by_year
    return facts


def inventory() -> dict:
    snap = _restore()
    data = SCRATCH / "data"
    from src.scanner.score_runner import SCORE_COLUMNS
    comp = _component_columns(SCORE_COLUMNS)
    def safe(path, **kw):
        """One unreadable file is reported loudly in the inventory, it never takes the whole inventory down."""
        try:
            return _parquet_facts(path, **kw)
        except Exception as exc:  # noqa: BLE001
            print(f"INVENTORY ERROR {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return {"present": path.exists(), "error": f"{type(exc).__name__}: {exc}"}
    inv = {"generated_at": _now(), "snapshot": snap, "not_point_in_time": NOT_POINT_IN_TIME,
           "panel_daily": safe(data / "panel_daily.parquet"),
           "panel_weekly": safe(data / "panel_weekly.parquet"),
           "spy_daily": safe(data / "spy_daily.parquet"),
           "scores_daily": safe(data / "scores_daily.parquet", extra_cols=comp["aggregate"] + comp["sub"]),
           "component_columns_requested": comp, "universe_txt_names": None, "universe_mcap_json_present": (data / "universe_mcap.json").exists(),
           "aqe_db": {}}
    u = data / "universe.txt"
    if u.exists():
        inv["universe_txt_names"] = sum(1 for l in u.read_text().splitlines() if l.strip() and not l.startswith("#"))
    db = data / "aqe.db"
    if db.exists():
        con = sqlite3.connect(str(db))
        for (t,) in con.execute("select name from sqlite_master where type='table' order by name"):
            try:
                n = con.execute(f'select count(*) from "{t}"').fetchone()[0]
            except Exception as exc:  # noqa: BLE001
                n = f"error: {exc}"
            inv["aqe_db"][t] = n
        con.close()
    pd_ = inv["panel_daily"]
    if pd_.get("present"):
        yrs = (pd.Timestamp(pd_["date_max"]) - pd.Timestamp(pd_["date_min"])).days / 365.25
        inv["verdict"] = {"panel_years": round(yrs, 2), "can_extract_from_stored_scores": bool(inv["scores_daily"].get("present")),
                          "needs_recompute_for_6y": bool(yrs < 5.5),
                          "note": "scored history starts about 1 year after the panel starts (engine warmup)"}
    OUT.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(inv, indent=1, default=str).encode()
    (OUT / "inventory.json").write_bytes(blob)
    _write_ids(_drive_put("aqe_research_inventory.json", blob, "application/json"))
    print(json.dumps({k: v for k, v in inv.items() if k not in ("component_columns_requested",)}, indent=1, default=str)[:6000])
    return inv


# ------------------------------------------------------------------------------------------------ extract
def _component_columns(score_columns: list[str]) -> dict:
    """COMPONENT + SUB-COMPONENT columns, composites as reference only, no list flags, no last-bar-only DETECT columns."""
    cols = list(score_columns)
    a0, a1 = cols.index("flow_100"), cols.index("impulse_state")
    s0, s1 = cols.index("flow_score"), cols.index("mp_accel_state")
    assert a0 < a1 and s0 < s1, "SCORE_COLUMNS layout changed: re-read the section order before extracting"
    ref = [c for c in ("sc_momentum", "sc_momentum_raw", "sc_position", "sc_position_raw", "sc_m_gates", "sc_p_gates", "pipe_rank") if c in cols]
    shadow = [c for c in cols if c.endswith("_v2")]            # research review 2026-11-21: shadow fields shipped beside the live ones (scores_daily tail)
    return {"aggregate": cols[a0:a1 + 1], "sub": cols[s0:s1 + 1], "reference_composites": ref, "shadow_v2": shadow}


def _recompute(years: int) -> None:
    """Longer panel + engines into the SCRATCH dir (production untouched): same code as the nightly."""
    from src.data import panel_builder
    from src.scanner import score_runner
    (SCRATCH / "data" / "universe.txt").exists() or sys.exit("universe.txt missing in scratch: restore first")
    panel_builder.build_panel(history_years=years)
    score_runner.build_scores()


def _rescore(keep: list[str], n_shards: int = 12) -> dict:
    """Re-run the CURRENT engines (live + shadow v2) over the RESTORED panel into the scratch dir: the stored scores_daily predates the _v2 columns.
    First pulls every report date per ticker (earn_score_v2 needs the history: earnings_dates_full.json lives in scratch only).
    Scored in SHARDS, each reduced to the extract's columns as float32 before the next starts: scoring all ~1,600 tickers x 6y in one
    process held ~250 full-width float64 columns and the runner was killed (run 44904664034, 'lost communication' at 1h24m). Production untouched."""
    from src.data import earnings as E
    from src.data.fmp_client import FMPClient
    from src.scanner import score_runner
    panel = pd.read_parquet(SCRATCH / "data" / "panel_daily.parquet", columns=["ticker"])
    tickers = sorted(panel["ticker"].dropna().unique().tolist())
    del panel
    print(f"RESCORE: pulling report dates for {len(tickers)} tickers, then scoring in {n_shards} shards in scratch", flush=True)
    pulled = E.pull_earnings_dates_full(FMPClient(), tickers)
    print(f"  report dates: {pulled['tickers']} tickers, {len(pulled['failed'])} failed, aborted={pulled['aborted']}", flush=True)
    parts_dir = SCRATCH / "rescore_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    diag_total: dict = {}
    parts = []
    orig = score_runner.SCORES_DAILY
    try:
        for k in range(n_shards):
            sub = tickers[k::n_shards]
            if not sub:
                continue
            d = parts_dir / f"shard{k:02d}"
            d.mkdir(parents=True, exist_ok=True)
            score_runner.SCORES_DAILY = d / "scores_daily.parquet"           # no prior file -> no merge, and the diagnostics land beside it
            print(f"  shard {k + 1}/{n_shards}: {len(sub)} tickers", flush=True)
            score_runner.build_scores(only_tickers=sub)
            df = pd.read_parquet(score_runner.SCORES_DAILY)
            missing = [c for c in keep if c not in df.columns]
            if missing:
                raise SystemExit(f"rescored scores are missing expected columns (loud): {missing}")
            df = df[keep]
            for c in df.columns:
                if df[c].dtype == "float64":
                    df[c] = df[c].astype("float32")
            pp = parts_dir / f"part{k:02d}.parquet"
            df.to_parquet(pp, index=False)
            parts.append(pp)
            diag_p = d / "score_diagnostics_v2.json"
            if diag_p.exists():
                _merge_diag(diag_total, json.loads(diag_p.read_text()))
            (d / "scores_daily.parquet").unlink(missing_ok=True)
            del df
    finally:
        score_runner.SCORES_DAILY = orig
    return {"parts": [str(x) for x in parts],
            "earnings_dates": {k: v for k, v in pulled.items() if k != "failed"} | {"failed_tickers": pulled["failed"]},
            "score_diagnostics": diag_total or None, "shards": n_shards}


def _merge_diag(total: dict, part: dict) -> None:
    """Sum the per-shard score diagnostics (ints add, dicts of ints add by key); anything else keeps the latest value."""
    for k, v in part.items():
        if isinstance(v, bool) or not isinstance(v, (int, dict)):
            total[k] = v
        elif isinstance(v, int):
            total[k] = total.get(k, 0) + v
        else:
            cur = total.setdefault(k, {})
            for kk, vv in v.items():
                cur[kk] = cur.get(kk, 0) + vv if isinstance(vv, int) else vv


def _shadow_report(scores: pd.DataFrame) -> dict:
    """Distributions and null shares of the shadow v2 fields next to their live counterparts (the numbers the PRs promised)."""
    def shares(col):
        v = scores[col].dropna()
        return {str(k): round(float(x), 4) for k, x in v.value_counts(normalize=True).sort_index().items()} if len(v) else {}
    rep = {"rows": int(len(scores)), "null_share": {c: round(float(scores[c].isna().mean()), 4) for c in scores.columns if c.endswith("_v2")},
           "atr_score_value_shares": {"live": shares("atr_score"), "v2": shares("atr_score_v2")},
           "base_days": {"live": scores["base_days"].describe(percentiles=[.5, .9]).round(2).to_dict(),
                         "v2": scores["base_days_v2"].describe(percentiles=[.5, .9]).round(2).to_dict()} if "base_days_v2" in scores.columns else None}
    pairs = [("flow_100", "flow_100_v2"), ("energy_100", "energy_100_v2"), ("structure_100", "structure_100_v2"), ("mp_100", "mp_score_v2"),
             ("elder_score", "elder_score_v2"), ("bq_100", "bq_100_v2"), ("pipe_rank", "pipe_rank_v2"), ("sc_momentum", "sc_momentum_v2"), ("sc_position", "sc_position_v2")]
    rep["live_vs_v2"] = {}
    for a, b in pairs:
        if a in scores.columns and b in scores.columns:
            ok = scores[a].notna() & scores[b].notna()
            rep["live_vs_v2"][f"{a} -> {b}"] = {"n": int(ok.sum()), "corr": round(float(scores.loc[ok, a].corr(scores.loc[ok, b])), 4) if ok.sum() > 10 else None,
                                                "mean_abs_diff": round(float((scores.loc[ok, a] - scores.loc[ok, b]).abs().mean()), 3) if ok.sum() else None}
    return rep


def extract(years: int, recompute: bool, rescore: bool = False) -> dict:
    snap = _restore()
    data = SCRATCH / "data"
    rescore_info = None
    if recompute:
        print(f"RECOMPUTE over {years}y into scratch {data}", flush=True)
        _recompute(years)
    from src.scanner.score_runner import SCORE_COLUMNS
    comp = _component_columns(SCORE_COLUMNS)
    keep = ["date", "ticker"] + comp["aggregate"] + comp["sub"] + comp["reference_composites"] + (comp["shadow_v2"] if rescore else [])
    if rescore:
        rescore_info = _rescore(keep)
        scores = pd.concat([pd.read_parquet(x) for x in rescore_info.pop("parts")], ignore_index=True)
        scores = scores.dropna(subset=["sc_momentum"]).reset_index(drop=True)
    else:
        scores = pd.read_parquet(data / "scores_daily.parquet")
    missing = [c for c in keep if c not in scores.columns]
    if missing:
        raise SystemExit(f"scores_daily is missing expected columns (loud): {missing}")
    scores = scores[keep].copy()
    scores["date"] = pd.to_datetime(scores["date"]).dt.normalize()

    panel = pd.read_parquet(data / "panel_daily.parquet", columns=["date", "ticker", "close", "volume"])
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    px = panel.pivot_table(index="date", columns="ticker", values="close").sort_index()
    vol = panel.pivot_table(index="date", columns="ticker", values="volume").sort_index()
    spy = pd.read_parquet(data / "spy_daily.parquet")
    spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()
    spy_close = spy.set_index("date")["close"].sort_index().reindex(px.index)

    logret = np.log(px).diff()
    vol20 = (logret.rolling(20).std() * np.sqrt(252)).stack().rename("vol_20d_ann_pit")
    dv20 = (px * vol).rolling(20).mean().stack().rename("dollar_vol_20d_pit")
    scored_mask = scores.set_index(["date", "ticker"]).index
    out = scores.set_index(["date", "ticker"])
    out = out.join(px.stack().rename("close_panel")).join(vol20).join(dv20)

    # forward returns on the global session calendar, from the signal date's close
    for h in HORIZONS:
        f = (px.shift(-h) / px - 1.0)
        fs = (spy_close.shift(-h) / spy_close - 1.0)
        s = f.stack().rename(f"fwd{h}")
        out = out.join(s)
        # equal-weight universe = mean forward return over the names AQE scored THAT day (with a forward return)
        tmp = out[[f"fwd{h}"]].dropna().reset_index()
        ew = tmp.groupby("date")[f"fwd{h}"].mean().rename(f"ew_fwd{h}")
        out = out.join(ew, on="date")
        out[f"spy_fwd{h}"] = fs.reindex(out.index.get_level_values("date")).to_numpy()
        out[f"fwd{h}_vs_spy"] = out[f"fwd{h}"] - out[f"spy_fwd{h}"]
        out[f"fwd{h}_vs_ew"] = out[f"fwd{h}"] - out[f"ew_fwd{h}"]
    out = out.reset_index()

    sm = json.loads((data / "sector_map.json").read_text()) if (data / "sector_map.json").exists() else {}
    out["sector_etf_current"] = out["ticker"].map(sm)
    mc_path = data / "universe_mcap.json"
    mc = (json.loads(mc_path.read_text()).get("mcap") or {}) if mc_path.exists() else {}
    out["mcap_current_not_pit"] = out["ticker"].map(mc) if mc else np.nan

    # float32 for the numeric columns keeps the file size sane; identifiers and strings untouched
    for c in out.columns:
        if out[c].dtype == "float64":
            out[c] = out[c].astype("float32")
    out = out.sort_values(["date", "ticker"]).reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tag = "_v2" if rescore else ""
    pq = OUT / f"aqe_research_extract{tag}_{stamp}.parquet"
    out.to_parquet(pq, index=False, compression="zstd")
    spy_out = spy[["date", "close"]].rename(columns={"close": "spy_close"})
    spy_out.to_csv(OUT / f"aqe_research_spy_{stamp}.csv", index=False)
    meta = {"generated_at": _now(), "snapshot": snap, "rows": int(len(out)), "tickers": int(out["ticker"].nunique()),
            "date_min": str(out["date"].min().date()), "date_max": str(out["date"].max().date()),
            "recomputed": bool(recompute), "rescored_with_shadow_v2": bool(rescore), "requested_years": years, "columns": {"identifiers": ["date", "ticker", "sector_etf_current"],
            **comp, "market": ["close_panel", "vol_20d_ann_pit", "dollar_vol_20d_pit", "mcap_current_not_pit"],
            "forward": [f"{p}{h}{s}" for h in HORIZONS for p, s in (("fwd", ""), ("fwd", "_vs_spy"), ("fwd", "_vs_ew"), ("spy_fwd", ""), ("ew_fwd", ""))]},
            "forward_return_definition": "close of signal date -> close h sessions later on the panel's own session calendar; vs_spy = stock minus SPY; vs_ew = stock minus the equal-weight mean over names scored that date; last h sessions are null",
            "mcap_note": "mcap_current_not_pit empty (no universe_mcap.json in the snapshot)" if not mc else "current market cap, not point-in-time",
            "not_point_in_time": NOT_POINT_IN_TIME, "composites_note": "sc_*/pipe_rank are reference columns only; no list flags (longlist/elder/qs) are included"}
    if rescore:
        meta["shadow_v2"] = {"note": "every *_v2 column is a SHADOW calculation beside its live field (live code unchanged); see the PRs #134-#13x for each definition. "
                                     "A NaN v2 value is a missing input, never a default credit. Items 1, 2, 3, 10, 16 are Pine spec changes awaiting PM sign-off.",
                             "rescore": rescore_info, "report": _shadow_report(out)}
    (OUT / "extract_meta.json").write_text(json.dumps(meta, indent=1, default=str))
    meta_name = f"aqe_research_extract{tag}_meta.json"
    ids = [_drive_put(pq.name, pq.read_bytes(), "application/octet-stream"),
           _drive_put(meta_name, (OUT / "extract_meta.json").read_bytes(), "application/json"),
           _drive_put((OUT / f"aqe_research_spy_{stamp}.csv").name, (OUT / f"aqe_research_spy_{stamp}.csv").read_bytes(), "text/csv")]
    for e in ids:
        _write_ids(e)
    print(json.dumps({"meta": {k: meta[k] for k in ("rows", "tickers", "date_min", "date_max", "recomputed")}, "drive": ids}, indent=1))
    return meta


# ------------------------------------------------------------------------------------------------ truncation test
def truncation(sample: int, lag: int) -> dict:
    """Does the engine stack give the SAME component values on date D when it only ever saw data up to D?
    Recompute a sample of tickers on a panel truncated at D (weekly bars RE-resampled from the truncated daily bars,
    so a forming week ends at D) and diff against the full-history scores at D."""
    snap = _restore()
    data = SCRATCH / "data"
    from src.scanner.score_runner import SCORE_COLUMNS
    comp = _component_columns(SCORE_COLUMNS)
    cols = comp["aggregate"] + comp["sub"]
    full = pd.read_parquet(data / "scores_daily.parquet")
    full["date"] = pd.to_datetime(full["date"]).dt.normalize()
    dates = sorted(full["date"].unique())
    d_cut = pd.Timestamp(dates[-1 - lag])
    # a mid-week session on purpose: the forming weekly bar is the leakage suspect
    for k in range(lag, lag + 10):
        cand = pd.Timestamp(dates[-1 - k])
        if cand.weekday() in (1, 2, 3):
            d_cut = cand
            break
    rng = np.random.default_rng(7)
    avail = sorted(full.loc[full["date"] == d_cut, "ticker"].unique())
    pick = sorted(rng.choice(avail, size=min(sample, len(avail)), replace=False).tolist())
    tdir = SCRATCH / "trunc"
    (tdir / "data").mkdir(parents=True, exist_ok=True)
    (tdir / "output").mkdir(parents=True, exist_ok=True)
    from src.data.fmp_client import resample_to_weekly
    pdl = pd.read_parquet(data / "panel_daily.parquet")
    pdl["date"] = pd.to_datetime(pdl["date"]).dt.normalize()
    pdl = pdl[pdl["ticker"].isin(pick + ["SPY"]) & (pdl["date"] <= d_cut)]
    pdl.to_parquet(tdir / "data" / "panel_daily.parquet", index=False)
    wk = []
    for t, g in pdl.groupby("ticker"):
        w = resample_to_weekly(g[["date", "open", "high", "low", "close", "volume"]].sort_values("date"))
        w["ticker"] = t
        wk.append(w[["date", "ticker", "open", "high", "low", "close", "volume"]])
    pd.concat(wk).to_parquet(tdir / "data" / "panel_weekly.parquet", index=False)
    sp = pd.read_parquet(data / "spy_daily.parquet")
    sp["date"] = pd.to_datetime(sp["date"]).dt.normalize()
    sp[sp["date"] <= d_cut].to_parquet(tdir / "data" / "spy_daily.parquet", index=False)
    for f in ("universe.txt", "sector_map.json", "earnings_history.json"):
        if (data / f).exists():
            (tdir / "data" / f).write_bytes((data / f).read_bytes())
    env = dict(os.environ, AQE_DATA_DIR=str(tdir / "data"), AQE_OUTPUT_DIR=str(tdir / "output"))
    code = f"from src.scanner.score_runner import build_scores; build_scores(only_tickers={pick!r})"
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    if r.returncode != 0 or not (tdir / "data" / "scores_daily.parquet").exists():
        raise SystemExit(f"truncated rescoring failed (loud): rc={r.returncode}\n{r.stderr[-2000:]}")
    tr = pd.read_parquet(tdir / "data" / "scores_daily.parquet")
    tr["date"] = pd.to_datetime(tr["date"]).dt.normalize()
    a = full[(full["date"] == d_cut) & full["ticker"].isin(pick)].set_index("ticker")
    b = tr[tr["date"] == d_cut].set_index("ticker")
    common = sorted(set(a.index) & set(b.index))
    per_col = {}
    for c in cols:
        if c not in a.columns or c not in b.columns:
            continue
        x, y = a.loc[common, c], b.loc[common, c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            diff = (x.astype(float) - y.astype(float)).abs()
            bad = diff.fillna(0) > 1e-6
            nanmis = x.isna() != y.isna()
            n = int((bad | nanmis).sum())
            if n:
                per_col[c] = {"rows_differing": n, "max_abs_diff": float(diff.max()) if diff.notna().any() else None}
        else:
            n = int((x.astype(str) != y.astype(str)).sum())
            if n:
                per_col[c] = {"rows_differing": n, "kind": "label"}
    res = {"generated_at": _now(), "snapshot": snap, "cut_date": str(d_cut.date()), "weekday": int(d_cut.weekday()),
           "tickers_compared": len(common), "columns_checked": len(cols), "columns_that_differ": per_col,
           "verdict": "NO LOOK-AHEAD detected in the sampled columns" if not per_col else
                      "DIFFERENCES: those columns use information after the date (or a universe-wide input): do not trust them as point-in-time until explained",
           "sample": pick}
    OUT.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(res, indent=1).encode()
    (OUT / "truncation_test.json").write_bytes(blob)
    _write_ids(_drive_put("aqe_research_truncation_test.json", blob, "application/json"))
    print(json.dumps(res, indent=1)[:5000])
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventory")
    e = sub.add_parser("extract"); e.add_argument("--years", type=int, default=6); e.add_argument("--recompute", action="store_true"); e.add_argument("--rescore", action="store_true")
    t = sub.add_parser("truncation"); t.add_argument("--sample", type=int, default=20); t.add_argument("--lag", type=int, default=40)
    a = ap.parse_args(argv)
    if a.cmd == "inventory":
        inventory()
    elif a.cmd == "extract":
        extract(min(a.years, 6), a.recompute, a.rescore)
    else:
        truncation(a.sample, a.lag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
