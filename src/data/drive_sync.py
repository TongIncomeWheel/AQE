"""Google Drive sync — export the daily scan to one Google Drive folder.

Single destination: the Drive folder pinned by ID in `gdrive_uploader.py`
(GDRIVE_FOLDER_ID, default = the linked AQE folder). Written via the Drive
REST API only — there are NO local Drive-mount writes.

  aqe_daily_export.json  (scan + SRM combined, overwritten each run)

The committee reads this one file. SRM grading is embedded as the export's
`srm` / `srm_gics` / `srm_signals` sections, so there is no separate SRM file.
A copy is also written to the local OUTPUT_DIR — that is the app's own working
file (read by the UI in cloud mode), not a user-facing Drive folder.

Each run overwrites the same filename so the Drive folder never clutters.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.analyzer.ptrs import compute_ptrs
from src.data.sector_mapper import (
    ETF_TO_NAME,
    SECTOR_MAP_DRIVE_FILENAME,
    SECTOR_MAP_FOLDER_ID,
    load_sector_map,
)
from src.engines.srm import (
    GICS_ETFS, get_sector_health, grade_all_sectors,
    enrich_sectors_intermarket, load_intermarket_cache,
)
from src.scanner.betas import load_betas
from src.scanner.levels import load_elder_history, load_trade_levels

from src.data.paths import OUTPUT_DIR, PROJECT_ROOT  # single source of truth

# Drive destination is the folder pinned in gdrive_uploader (by ID), reached
# via the REST API. No local Drive-mount path.
EXPORT_FILENAME = "aqe_daily_export.json"

# Sector RAG map (AQE Data Schema Spec v1.0 §6) — published as a SINGLE file to
# a dedicated Drive subfolder (the round-trip source of truth; folder + filename
# defined in sector_mapper). AQE restores it on startup, auto-sources GICS for
# any blank, and overwrites the one file each run. Version stamps the run date.
SECTOR_MAP_FILENAME = SECTOR_MAP_DRIVE_FILENAME


def _rank_explain(pipe_rank: float, floor: float, sc_mom: float,
                  pe_qualified: bool, ticker: str,
                  sm: dict, sector_grades: dict) -> str:
    """1-liner explaining why a ticker sits at its rank."""
    parts: list[str] = []
    pr = pipe_rank or 0
    fl = floor or 0
    if pr >= 80:
        parts.append(f"PipeRk {pr:.0f} leads")
    elif pr >= 60:
        parts.append(f"PipeRk {pr:.0f}")
    elif pr > 0:
        parts.append(f"PipeRk {pr:.0f} caps rank")
    else:
        parts.append("No PipeRk")
    if pe_qualified:
        parts.append("PE pick")
    if pr <= 0:
        parts.append(f"Floor {fl:.0f} sorts")
    elif fl >= 70 and pr < 70:
        parts.append(f"engines strong (Floor {fl:.0f})")
    elif fl < 45 and pr > 0:
        parts.append(f"Floor {fl:.0f} drags")
    etf = sm.get(ticker, "")
    grade = sector_grades.get(etf, {}).get("grade", "")
    if grade == "DEPLOY":
        parts.append("sector DEPLOY")
    elif grade == "AVOID":
        parts.append("sector AVOID")
    return "; ".join(parts) if parts else ""


def _build_srm_gics() -> tuple[list[dict], dict, dict, dict]:
    """Full 11-sector SRM grading with trend data + DSG-18/19 intermarket.

    Returns (srm_gics_array, srm_signals_dict, macro_weather_dict, intermarket_dict).
    srm_gics: one row per sector (sorted DEPLOY→AVOID) with grade, sh_value,
              roc20, roc5, divergence, above_sma20, sh_trend, grade_trend,
              + DSG-18 RRG fields + DSG-19 macro fields + combined gate.
    srm_signals: {deploy, hold, turning, watch, avoid, blocked} ETF lists.
    macro_weather: global macro weather summary.
    intermarket: §3A.6 COB intermarket brief (UUP/TLT/HYG/SPY-IWM + posture).
    """
    import pandas as pd
    from src.data.paths import PANEL_DAILY as panel_path

    empty_signals = {"deploy": [], "hold": [], "turning": [], "watch": [], "avoid": [], "blocked": []}

    if not panel_path.exists():
        return [], empty_signals, {}, {}
    panel = pd.read_parquet(panel_path, columns=["date", "ticker", "close"])
    etfs_plus = set(GICS_ETFS) | {"SPY"}
    panel = panel[panel["ticker"].isin(etfs_plus)]
    if panel.empty:
        return [], empty_signals, {}, {}

    graded = grade_all_sectors(panel, trend_days=10)

    # DSG-18: RRG from panel (SPY + sectors are in the panel)
    # DSG-19: macro from the intermarket cache saved by the orchestrator
    cache = load_intermarket_cache()
    macro_data_for_enrich = None  # we don't re-fetch; use cached results instead
    enrich_sectors_intermarket(graded, panel, macro_data_for_enrich)

    # Overlay cached macro results (orchestrator had the FMP macro data)
    if cache and cache.get("sectors"):
        for etf, cached_fields in cache["sectors"].items():
            if etf in graded:
                for k in ("macro_headwind_score", "macro_headwind_flag",
                          "entry_gate", "entry_gate_reason"):
                    if k in cached_fields:
                        graded[etf][k] = cached_fields[k]

    macro_weather = (cache or {}).get("macro_weather", {})
    intermarket = (cache or {}).get("intermarket", {})

    grade_order = {"DEPLOY": 0, "HOLD": 1, "TURNING": 2, "WATCH": 3, "AVOID": 4}

    rows = []
    for etf in GICS_ETFS:
        if etf in graded:
            info = graded[etf]
            rows.append({
                "etf": etf,
                "sector": ETF_TO_NAME.get(etf, etf),
                "grade": info.get("grade", "WATCH"),
                "trend_state": info.get("trend_state", ""),
                "sh_value": info.get("sh", 0),
                "roc20": info.get("roc20", 0.0),
                "roc5": info.get("roc5", 0.0),
                "divergence": info.get("divergence", 0.0),
                "above_sma20": info.get("above_sma20", False),
                "sh_trend": info.get("sh_trend", []),
                "grade_trend": info.get("grade_trend", []),
                "rrg_rs_ratio": info.get("rrg_rs_ratio"),
                "rrg_rs_momentum": info.get("rrg_rs_momentum"),
                "rrg_quadrant": info.get("rrg_quadrant"),
                "rrg_direction": info.get("rrg_direction"),
                "rrg_grade_override": info.get("rrg_grade_override"),
                "macro_headwind_score": info.get("macro_headwind_score"),
                "macro_headwind_flag": info.get("macro_headwind_flag"),
                "entry_gate": info.get("entry_gate"),
                "entry_gate_reason": info.get("entry_gate_reason"),
            })
        else:
            rows.append({
                "etf": etf,
                "sector": ETF_TO_NAME.get(etf, etf),
                "grade": "NO_DATA",
                "trend_state": "",
                "sh_value": -5,
                "roc20": 0.0,
                "roc5": 0.0,
                "divergence": 0.0,
                "above_sma20": False,
                "sh_trend": [],
                "grade_trend": [],
                "rrg_rs_ratio": None,
                "rrg_rs_momentum": None,
                "rrg_quadrant": "NO_DATA",
                "rrg_direction": "STABLE",
                "rrg_grade_override": None,
                "macro_headwind_score": None,
                "macro_headwind_flag": "NO_DATA",
                "entry_gate": "WATCH",
                "entry_gate_reason": "No data",
            })

    rows.sort(key=lambda r: grade_order.get(r["grade"], 3))

    signals: dict[str, list[str]] = {"deploy": [], "hold": [], "turning": [], "watch": [], "avoid": [], "blocked": []}
    for r in rows:
        g = r["grade"].lower()
        if g in signals:
            signals[g].append(r["etf"])
        if g == "avoid" or g == "no_data":
            signals["blocked"].append(r["etf"])
        if r.get("entry_gate") == "BLOCKED" and r["etf"] not in signals["blocked"]:
            signals["blocked"].append(r["etf"])

    return rows, signals, macro_weather, intermarket


def _compute_v21_lookups(sm: dict) -> dict:
    """Per-ticker lookups for AQE v2.1 fields. Defensive — returns {} on any error.

    Returns {rvol, rs, sma, corr, spy_roc_20d} where rvol/rs/sma are
    {ticker: float} and corr is {ticker: (corr, class)}.
    """
    out = {"rvol": {}, "rs": {}, "sma": {}, "ma": {}, "corr": {}, "spy_roc_20d": None}
    try:
        import numpy as np
        import pandas as pd
        from src.data.paths import PANEL_DAILY, SPY_DAILY

        if not PANEL_DAILY.exists():
            return out
        p = pd.read_parquet(PANEL_DAILY, columns=["date", "ticker", "close", "volume"])
        p["date"] = pd.to_datetime(p["date"]).dt.normalize()
        p = p.sort_values(["ticker", "date"])

        spy_roc = None
        if SPY_DAILY.exists():
            spy = pd.read_parquet(SPY_DAILY, columns=["date", "close"]).sort_values("date")
            if len(spy) >= 21 and float(spy["close"].iloc[-21]) > 0:
                spy_roc = (float(spy["close"].iloc[-1]) / float(spy["close"].iloc[-21]) - 1) * 100
        out["spy_roc_20d"] = round(float(spy_roc), 2) if spy_roc is not None else None

        # Daily returns pivot for sector correlation
        close_piv = p.pivot_table(index="date", columns="ticker", values="close")
        rets = close_piv.pct_change()

        for tk, g in p.groupby("ticker", sort=False):
            cl = g["close"].to_numpy(dtype=float)
            vol = g["volume"].to_numpy(dtype=float)
            # rvol = today / 20-day prior average
            if len(vol) >= 21:
                avg20 = float(np.nanmean(vol[-21:-1]))
                if avg20 > 0:
                    out["rvol"][tk] = round(float(vol[-1]) / avg20, 2)
            # sma_distance_pct vs 50D SMA
            if len(cl) >= 50:
                sma50 = float(np.nanmean(cl[-50:]))
                if sma50 > 0:
                    out["sma"][tk] = round((float(cl[-1]) / sma50 - 1) * 100, 2)
            # absolute MA ladder (20/50/100/200) — for live MA-support alerts
            ma = {}
            for w in (20, 50, 100, 200):
                if len(cl) >= w:
                    m = float(np.nanmean(cl[-w:]))
                    if m > 0:
                        ma[w] = round(m, 2)
            if ma:
                out["ma"][tk] = ma
            # rs_spy_20d = stock 20d ROC − SPY 20d ROC
            if len(cl) >= 21 and spy_roc is not None and cl[-21] > 0:
                roc = (float(cl[-1]) / float(cl[-21]) - 1) * 100
                out["rs"][tk] = round(roc - spy_roc, 2)
            # sector_corr = 60d Pearson corr of daily returns vs parent ETF
            etf = sm.get(tk)
            if etf and etf in rets.columns and tk in rets.columns:
                pair = rets[[tk, etf]].dropna().tail(60)
                if len(pair) >= 30:
                    c = float(pair[tk].corr(pair[etf]))
                    if np.isfinite(c):
                        cls = ("IDIOSYNCRATIC" if c < 0.30
                               else "MIXED" if c < 0.70 else "SECTOR_DEPENDENT")
                        out["corr"][tk] = (round(c, 2), cls)
    except Exception:  # noqa: BLE001 — never let enrichment break the export
        pass
    return out


def _v21_record_fields(tk: str, d: dict, lk: dict, sm: dict,
                       sector_grades: dict) -> dict:
    """AQE v2.1 / Data-Schema-v1.0 per-record fields. Bulletproof: returns a
    full key set with null values on any error, so the schema is always present.
    """
    fields = {
        "gics_sector": None, "gics_sector_name": None, "gics_gate": "CHECK",
        "sector_corr": None, "sector_corr_class": None,
        "rvol": None, "rs_spy_20d": None, "sma_distance_pct": None,
        "ma_20": None, "ma_50": None, "ma_100": None, "ma_200": None,
        "rr_tp1": None, "rr_tp2": None, "rr_tp3": None,
        "held": False,
    }
    try:
        etf = sm.get(tk)
        fields["gics_sector"] = etf
        fields["gics_sector_name"] = ETF_TO_NAME.get(etf) if etf else None
        grade = sector_grades.get(etf, {}).get("grade") if etf else None
        entry_gate = sector_grades.get(etf, {}).get("entry_gate") if etf else None
        if entry_gate:
            fields["gics_gate"] = entry_gate
        elif grade in ("DEPLOY", "HOLD"):
            fields["gics_gate"] = "PASS"
        elif grade == "AVOID":
            fields["gics_gate"] = "BLOCKED"
        elif grade:
            fields["gics_gate"] = "WATCH"
        else:
            fields["gics_gate"] = "CHECK"

        corr = (lk.get("corr") or {}).get(tk)
        if corr:
            fields["sector_corr"], fields["sector_corr_class"] = corr[0], corr[1]
        fields["rvol"] = (lk.get("rvol") or {}).get(tk)
        fields["rs_spy_20d"] = (lk.get("rs") or {}).get(tk)
        fields["sma_distance_pct"] = (lk.get("sma") or {}).get(tk)
        _ma = (lk.get("ma") or {}).get(tk) or {}
        for w in (20, 50, 100, 200):
            if _ma.get(w) is not None:
                fields[f"ma_{w}"] = _ma[w]
        fields["held"] = tk in (lk.get("held") or set())

        # R:R to each DSL target, measured from the internal +0.5R bracket point.
        be, stop = d.get("be"), d.get("stop")
        if be is not None and stop is not None and (be - stop) > 0:
            risk = be - stop
            for key, tp in (("rr_tp1", d.get("tp_1r")),
                            ("rr_tp2", d.get("tp_2r")),
                            ("rr_tp3", d.get("tp_3r"))):
                if tp is not None:
                    fields[key] = round((tp - be) / risk, 2)
    except Exception:  # noqa: BLE001
        pass
    return fields


def _num(v):
    """Return a clean float or None (drops NaN / non-numeric)."""
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _build_held_positions(held, dsl_all, betas, lk, sm, sector_grades, ptrs_fn):
    """Merge each PTJ held position with AQE's current engine read on it.

    Gives AIC, in one place: the trade (entry/qty/SL/TP/unrealised from the PTJ)
    + what the engine now says (scores, MP state, DSL bracket, sector, RS, …).
    """
    if not held:
        return []
    import pandas as pd
    from src.data.paths import SCORES_DAILY
    sc_lookup: dict = {}
    try:
        if SCORES_DAILY.exists():
            df = pd.read_parquet(SCORES_DAILY)
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            latest = df[df["date"] == df["date"].max()]
            sc_lookup = {r["ticker"]: r for _, r in latest.iterrows()}
    except Exception:  # noqa: BLE001
        sc_lookup = {}

    out = []
    for p in held:
        tk = p.get("ticker")
        if not tk:
            continue
        d = dsl_all.get(tk, {})
        s = sc_lookup.get(tk)
        sg = (lambda k: _num(s.get(k)) if s is not None else None)
        sc = sg("sc_momentum")
        v21 = _v21_record_fields(tk, d, lk, sm, sector_grades)
        out.append({
            "ticker": tk,
            # --- the trade (from PTJ) ---
            "qty": p.get("qty"),
            "entry": _num(p.get("entry")),
            "live_px": _num(p.get("livePx")),
            "held_sl": _num(p.get("sl")),
            "held_tp1": _num(p.get("tp1")),
            "held_tp2": _num(p.get("tp2")),
            "trade_date": p.get("tradeDate") or p.get("entryDate"),
            "unreal_usd": _num(p.get("unrealUsd")),
            "exposure": _num(p.get("exposure")),
            "ptj_sector": p.get("sector"),
            "ptj_srm_grade": p.get("srmGrade"),
            "notes": p.get("notes"),
            "held": True,
            # --- AQE engine read ---
            "sc_momentum": round(sc, 1) if sc is not None else None,
            "sc_momentum_raw": round(sg("sc_momentum_raw") or sc, 1) if (sg("sc_momentum_raw") or sc) is not None else None,
            "ptrs": ptrs_fn(sc, tk) if sc is not None else None,
            "pipe_rank": round(sg("pipe_rank"), 1) if sg("pipe_rank") is not None else None,
            "flow": round(sg("flow_100"), 0) if sg("flow_100") is not None else None,
            "energy": round(sg("energy_100"), 0) if sg("energy_100") is not None else None,
            "structure": round(sg("structure_100"), 0) if sg("structure_100") is not None else None,
            "mp": round(sg("mp_100"), 0) if sg("mp_100") is not None else None,
            "mp_state": (str(s.get("mp_state")) if s is not None and pd.notna(s.get("mp_state")) else None),
            "elder": round(sg("elder_score"), 1) if sg("elder_score") is not None else None,
            "beta_30d": (betas.get(tk) or {}).get(30),
            "beta_60d": (betas.get(tk) or {}).get(60),
            "dsl_stop": d.get("stop"), "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"), "dsl_tp_2r": d.get("tp_2r"), "dsl_tp_3r": d.get("tp_3r"),
            "dsl_atr_ratio": d.get("dsl_atr_ratio"), "atr_14d": d.get("atr14"),
            "gics_sector": v21["gics_sector"], "gics_gate": v21["gics_gate"],
            "sector_corr": v21["sector_corr"], "sector_corr_class": v21["sector_corr_class"],
            "rs_spy_20d": v21["rs_spy_20d"], "sma_distance_pct": v21["sma_distance_pct"],
            "rvol": v21["rvol"], "rr_tp1": v21["rr_tp1"], "rr_tp2": v21["rr_tp2"], "rr_tp3": v21["rr_tp3"],
            # absolute MA ladder + fib — so the live alert engine can evaluate
            # MA/Fib support on held names uniformly with candidates.
            "ma_20": v21["ma_20"], "ma_50": v21["ma_50"],
            "ma_100": v21["ma_100"], "ma_200": v21["ma_200"],
            "fib": d.get("fib"),
        })
    return out


def build_export(shortlist: dict | None = None) -> dict:
    """Build export from shortlist.json + scores_daily.parquet.

    Contains top_picks, edge_list, longlist, and watchlist.
    Every ticker is tagged with source (longlist / watchlist) and pe status.
    """
    if shortlist is None:
        sl_path = OUTPUT_DIR / "shortlist.json"
        if not sl_path.exists():
            return {}
        shortlist = json.loads(sl_path.read_text(encoding="utf-8"))

    sl = shortlist
    sgt = ZoneInfo("Asia/Singapore")
    now_sgt = datetime.now(sgt)

    # Auto-source GICS for any universe ticker missing from the map (via FMP),
    # up front, so BOTH the export's sector_map_gaps field and the published RAG
    # reflect the filled map — AIC should never see blanks AQE could resolve.
    try:
        from src.data.sector_mapper import build_sector_map, get_sector_map_gaps
        if get_sector_map_gaps():
            build_sector_map()
    except Exception:  # noqa: BLE001
        pass

    # Full 11-sector SRM grading + DSG-18/19 intermarket (spec §2)
    srm_gics, srm_signals, macro_weather, intermarket = _build_srm_gics()

    export: dict = {
        "date": sl.get("date", ""),
        "exported_at": now_sgt.strftime("%Y-%m-%d %H:%M:%S SGT"),
        "market": "US equities — close-of-day scan",
        "regime": sl.get("regime", {}),
        # §3A.6 COB intermarket brief — Druckenmiller's premarket opener.
        # Top-level, between regime and srm (per Alfred 11 Jun spec).
        "intermarket": intermarket,
        # Full SRM schema — combined into this one file (no separate SRM file).
        # `srm` is the list the AIC reader + protocols consume; `srm_gics` is
        # kept as an alias for existing callers.
        "srm": srm_gics,
        "srm_gics": srm_gics,
        "srm_signals": srm_signals,
        # Backward compat — derived from computed grades, not shortlist.json
        "srm_deploy": srm_signals.get("deploy", []),
        "srm_avoid": srm_signals.get("avoid", []),
        "macro_weather": macro_weather,
        "top_picks": [],
        "edge_list": [],
        "longlist": [],
        "watchlist": [],
    }

    # ---- Shared helpers (loaded once, used by all four lists) ----
    # PTRS = SC_MOM + SH (sector only). Regime handles VIX sizing separately.
    sector_grades = {r["etf"]: {"grade": r["grade"], "sh": r["sh_value"]} for r in srm_gics} if srm_gics else sl.get("srm_detail", {})

    def _ptrs(sc_mom, ticker):
        sh = get_sector_health(ticker, sector_grades)
        r = compute_ptrs(sc_mom, sh)
        v = r.get("ptrs")
        return round(v, 1) if v is not None and v == v else 0.0

    def _floor(rm):
        e = rm.get("engines", {})
        return min(e.get("flow", 0), e.get("energy", 0),
                   e.get("structure", 0), e.get("mp", 0))

    def _sc_from_engines(eng):
        """SC_MOM = Flow×0.30 + Energy×0.30 + Structure×0.20 + MP×0.20."""
        return round(
            eng.get("flow", 0) * 0.30 + eng.get("energy", 0) * 0.30
            + eng.get("structure", 0) * 0.20 + eng.get("mp", 0) * 0.20, 1
        )

    # Extract regime level for DSL v1.5 dynamic stop width
    regime_level = (sl.get("regime", {}).get("level") or "GREEN").upper()

    sm = load_sector_map()
    betas = load_betas()
    dsl_all = load_trade_levels(betas=betas, regime_level=regime_level)
    elder5 = load_elder_history()
    pe_tickers = {p["ticker"] for p in sl.get("precision_edge", [])}

    # ---- AQE v2.1 enrichment (rvol, rs_spy, sma_distance, sector_corr) ----
    _v21_lk = _compute_v21_lookups(sm)
    export["spy_roc_20d"] = _v21_lk.get("spy_roc_20d")
    from datetime import date as _date
    export["sector_map_version"] = _date.today().isoformat()
    try:
        from src.data.universe import load_universe
        _univ = load_universe(include_benchmark=False)
        export["sector_map_gaps"] = sorted([t for t in _univ if t not in sm])
    except Exception:  # noqa: BLE001
        export["sector_map_gaps"] = []

    # ---- Held positions (from the daily PTJ) + AQE engine read ----
    try:
        from src.data.ptj import load_held_positions
        _held = load_held_positions()
    except Exception:  # noqa: BLE001
        _held = []
    _v21_lk["held"] = {h.get("ticker") for h in _held if h.get("ticker")}
    export["held_positions"] = _build_held_positions(
        _held, dsl_all, betas, _v21_lk, sm, sector_grades, _ptrs)

    # mp_state lookup from scores_daily.parquet — authoritative source.
    # shortlist.json nests mp_state inside "diagnostics" for candidates and
    # omits it entirely from precision_edge, so we derive from the parquet.
    import pandas as pd
    from src.data.paths import SCORES_DAILY as _scores_path
    _mp_states: dict[str, str] = {}
    if _scores_path.exists():
        _sc = pd.read_parquet(_scores_path, columns=["date", "ticker", "mp_state"])
        _sc["date"] = pd.to_datetime(_sc["date"]).dt.normalize()
        _latest = _sc[_sc["date"] == _sc["date"].max()]
        _mp_states = dict(zip(_latest["ticker"], _latest["mp_state"].astype(str)))

    # Top Picks = candidates (PTRS-ranked shortlist) — SAME schema as longlist
    for c in sl.get("candidates", []):
        tk = c["ticker"]
        e = c["engines"]
        d = dsl_all.get(tk, {})
        sc_val = c.get("sc_momentum", 0) or 0
        floor = round(min(e["flow"], e["energy"], e["structure"], e["mp"]), 1)
        export["top_picks"].append({
            "rank": c["rank"],
            "ticker": tk,
            "sc_momentum": round(sc_val, 1),
            "sc_momentum_raw": round(c.get("sc_momentum_raw", sc_val), 1),
            "ptrs": round(c.get("ptrs", 0), 1),
            "pipe_rank": round(c.get("pipe_rank", 0), 1),
            "fip_spike_excluded": c.get("fip_spike_excluded", False),
            "fip_window_effective": c.get("fip_window_effective", 252),
            "floor": floor,
            "beta_30d": (betas.get(tk) or {}).get(30),
            "beta_60d": (betas.get(tk) or {}).get(60),
            "flow": round(e["flow"], 1),
            "energy": round(e["energy"], 1),
            "structure": round(e["structure"], 1),
            "mp": round(e["mp"], 1),
            "elder": e["elder"],
            "mp_state": _mp_states.get(tk, c.get("mp_state", "")),
            "entry": c["levels"].get("entry"),
            "stop": c["levels"].get("stop"),
            "dsl_stop": d.get("stop"),
            "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"),
            "dsl_tp_2r": d.get("tp_2r"),
            "dsl_tp_3r": d.get("tp_3r"),
            "dsl_rr_pct": d.get("rr_pct"),
            "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "atr_14d": d.get("atr14"),            "rr_est": d.get("rr_est"),
            "fib": d.get("fib"),
            "elder_5d": elder5.get(tk),
            "rank_explain": _rank_explain(
                c.get("pipe_rank", 0), floor, sc_val,
                tk in pe_tickers, tk, sm, sector_grades,
            ),
            "source": "top_picks",
            "pe": tk in pe_tickers,
            **_v21_record_fields(tk, d, _v21_lk, sm, sector_grades),
        })

    # Edge List = Precision Edge — SAME schema as longlist
    for ei, pe in enumerate(sl.get("precision_edge", []), 1):
        eng = pe["engines"]
        tk = pe["ticker"]
        d = dsl_all.get(tk, {})
        pe_sc = pe.get("sc_momentum") or _sc_from_engines(eng)
        pe_raw = pe.get("sc_momentum_raw") or pe_sc
        floor = round(min(eng["flow"], eng["energy"], eng["structure"], eng["mp"]), 1)
        export["edge_list"].append({
            "rank": ei,
            "ticker": tk,
            "sc_momentum": round(pe_sc, 1),
            "sc_momentum_raw": round(pe_raw, 1),
            "ptrs": _ptrs(pe_sc, tk),
            "pipe_rank": round(pe.get("pipe_rank", 0), 1),
            "fip_spike_excluded": pe.get("fip_spike_excluded", False),
            "fip_window_effective": pe.get("fip_window_effective", 252),
            "floor": floor,
            "beta_30d": (betas.get(tk) or {}).get(30),
            "beta_60d": (betas.get(tk) or {}).get(60),
            "flow": round(eng["flow"], 1),
            "energy": round(eng["energy"], 1),
            "structure": round(eng["structure"], 1),
            "mp": round(eng["mp"], 1),
            "elder": eng["elder"],
            "mp_state": _mp_states.get(tk, pe.get("mp_state", "")),
            "entry": pe["levels"].get("entry"),
            "stop": pe["levels"].get("stop"),
            "dsl_stop": d.get("stop"),
            "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"),
            "dsl_tp_2r": d.get("tp_2r"),
            "dsl_tp_3r": d.get("tp_3r"),
            "dsl_rr_pct": d.get("rr_pct"),
            "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "atr_14d": d.get("atr14"),            "rr_est": d.get("rr_est"),
            "fib": d.get("fib"),
            "elder_5d": elder5.get(tk),
            "rank_explain": _rank_explain(
                pe.get("pipe_rank", 0), floor, pe_sc,
                True, tk, sm, sector_grades,
            ),
            "source": "edge_list",
            "pe": True,
            **_v21_record_fields(tk, d, _v21_lk, sm, sector_grades),
        })
    longlist_tickers: set[str] = set()
    sorted_rm = sorted(sl.get("recipe_matches", []),
                       key=lambda rm: (
                           _ptrs(rm.get("sc_momentum", 0) or 0, rm["ticker"]),
                           rm.get("pipe_rank", 0),
                           _floor(rm),
                       ),
                       reverse=True)
    for i, rm in enumerate(sorted_rm, 1):
        e = rm["engines"]
        floor = round(min(e["flow"], e["energy"], e["structure"], e["mp"]), 1)
        sc_val = rm.get("sc_momentum", 0) or 0
        longlist_tickers.add(rm["ticker"])
        d = dsl_all.get(rm["ticker"], {})
        export["longlist"].append({
            "rank": i,
            "ticker": rm["ticker"],
            "sc_momentum": round(sc_val, 1),
            "sc_momentum_raw": round(rm.get("sc_momentum_raw", sc_val), 1),
            "ptrs": _ptrs(sc_val, rm["ticker"]),
            "pipe_rank": round(rm.get("pipe_rank", 0), 1),
            "fip_spike_excluded": rm.get("fip_spike_excluded", False),
            "fip_window_effective": rm.get("fip_window_effective", 252),
            "floor": floor,
            "beta_30d": (betas.get(rm["ticker"]) or {}).get(30),
            "beta_60d": (betas.get(rm["ticker"]) or {}).get(60),
            "flow": round(e["flow"], 1),
            "energy": round(e["energy"], 1),
            "structure": round(e["structure"], 1),
            "mp": round(e["mp"], 1),
            "elder": e["elder"],
            "mp_state": _mp_states.get(rm["ticker"], rm.get("mp_state", "")),
            "entry": rm["levels"].get("entry"),
            "stop": rm["levels"].get("stop"),
            "dsl_stop": d.get("stop"),
            "dsl_risk": d.get("risk"),
            "dsl_tp_1r": d.get("tp_1r"),
            "dsl_tp_2r": d.get("tp_2r"),
            "dsl_tp_3r": d.get("tp_3r"),
            "dsl_rr_pct": d.get("rr_pct"),
            "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "atr_14d": d.get("atr14"),            "rr_est": d.get("rr_est"),
            "fib": d.get("fib"),
            "elder_5d": elder5.get(rm["ticker"]),
            "rank_explain": _rank_explain(
                rm.get("pipe_rank", 0), floor, sc_val,
                rm.get("pe_qualified", False), rm["ticker"],
                sm, sector_grades,
            ),
            "source": "longlist",
            "pe": bool(rm.get("pe_qualified")),
            **_v21_record_fields(rm["ticker"], d, _v21_lk, sm, sector_grades),
        })

    # --- Watchlist: full universe above raw SC_MOM >= 70 ---
    import pandas as pd
    from src.data.paths import SCORES_DAILY as scores_path

    if scores_path.exists():
        wl_df = pd.read_parquet(scores_path)
        wl_df["date"] = pd.to_datetime(wl_df["date"]).dt.normalize()
        wl_latest = wl_df["date"].max()
        wl_df = wl_df[wl_df["date"] == wl_latest].copy()

        raw_col = (
            "sc_momentum_raw"
            if "sc_momentum_raw" in wl_df.columns
            else "sc_momentum"
        )
        wl_mask = wl_df[raw_col] >= 70
        _exclude = set(GICS_ETFS) | {"SPY"}
        wl_mask &= ~wl_df["ticker"].isin(_exclude)
        wl_df = wl_df[wl_mask].copy()

        if not wl_df.empty:
            for c in (
                "pipe_rank", "flow_100", "energy_100",
                "structure_100", "mp_100",
            ):
                if c in wl_df.columns:
                    wl_df[c] = pd.to_numeric(
                        wl_df[c], errors="coerce"
                    ).fillna(0)
            wl_df["_floor"] = wl_df[
                ["flow_100", "energy_100", "structure_100", "mp_100"]
            ].min(axis=1)

            # Vectorized PTRS
            wl_sh = wl_df["ticker"].map(
                lambda t: sector_grades.get(sm.get(t, ""), {}).get("sh", 0)
            )
            wl_df["_ptrs"] = (
                wl_df["sc_momentum"].fillna(0) + wl_sh.fillna(0)
            ).round(1)

            wl_df = wl_df.sort_values(
                ["_ptrs", "pipe_rank", "_floor"], ascending=[False, False, False]
            ).reset_index(drop=True)

            for wi, (_, wr) in enumerate(wl_df.iterrows(), 1):
                tk = wr["ticker"]
                d = dsl_all.get(tk, {})
                wfl = round(float(wr["_floor"]), 1)
                wsc = float(wr.get("sc_momentum", 0)) or 0
                wpr = float(wr.get("pipe_rank", 0))
                export["watchlist"].append({
                    "rank": wi,
                    "ticker": tk,
                    "sc_momentum": round(wsc, 1),
                    "sc_momentum_raw": round(
                        float(wr.get(raw_col, wsc)), 1
                    ),
                    "ptrs": round(float(wr["_ptrs"]), 1),
                    "pipe_rank": round(wpr, 1),
                    "fip_spike_excluded": bool(wr.get("fip_spike_excluded", False)),
                    "fip_window_effective": int(wr.get("fip_window_effective", 252)),
                    "floor": wfl,
                    "beta_30d": (betas.get(tk) or {}).get(30),
            "beta_60d": (betas.get(tk) or {}).get(60),
                    "flow": round(float(wr.get("flow_100", 0)), 1),
                    "energy": round(float(wr.get("energy_100", 0)), 1),
                    "structure": round(
                        float(wr.get("structure_100", 0)), 1
                    ),
                    "mp": round(float(wr.get("mp_100", 0)), 1),
                    "elder": round(float(wr.get("elder_score", 0)), 1),
                    "mp_state": _mp_states.get(tk, str(wr.get("mp_state", ""))),
                    "entry": d.get("entry"),
                    "stop": d.get("stop"),
                    "dsl_stop": d.get("stop"),
                    "dsl_risk": d.get("risk"),
                    "dsl_tp_1r": d.get("tp_1r"),
                    "dsl_tp_2r": d.get("tp_2r"),
                    "dsl_tp_3r": d.get("tp_3r"),
                    "dsl_rr_pct": d.get("rr_pct"),
                    "dsl_atr_ratio": d.get("dsl_atr_ratio"),
            "atr_14d": d.get("atr14"),                    "rr_est": d.get("rr_est"),
                    "fib": d.get("fib"),
                    "elder_5d": elder5.get(tk),
                    "rank_explain": _rank_explain(
                        wpr, wfl, wsc, tk in pe_tickers, tk,
                        sm, sector_grades,
                    ),
                    "source": "watchlist",
                    "pe": tk in pe_tickers,
                    "on_longlist": tk in longlist_tickers,
                    **_v21_record_fields(tk, d, _v21_lk, sm, sector_grades),
                })

    export["summary"] = {
        "top_picks_count": len(export["top_picks"]),
        "edge_count": len(export["edge_list"]),
        "longlist_count": len(export["longlist"]),
        "watchlist_count": len(export["watchlist"]),
    }

    # ---- Uniform schema across all four tiers (Data Schema Spec v1.0 §2.2) ----
    # "All four tiers carry an identical field set. Missing values are null."
    # Fill cross-tier fields, then rebuild every record with the SAME ordered
    # key set (canonical order = the richest tier's record), null-filling gaps.
    _tiers = [export["top_picks"], export["edge_list"],
              export["longlist"], export["watchlist"]]
    for _tier in _tiers:
        for _rec in _tier:
            if "on_longlist" not in _rec:
                _rec["on_longlist"] = _rec.get("ticker") in longlist_tickers
    _all_keys: set[str] = set()
    for _tier in _tiers:
        for _rec in _tier:
            _all_keys.update(_rec.keys())
    _canonical = (list(export["top_picks"][0].keys())
                  if export["top_picks"] else sorted(_all_keys))
    _order = _canonical + [k for k in sorted(_all_keys) if k not in _canonical]
    for _tier in _tiers:
        _tier[:] = [{k: _rec.get(k) for k in _order} for _rec in _tier]

    # ---- Permanent schema validation — BLOCKS export on missing fields ----
    _REQUIRED_FIELDS = [
        "ticker", "sc_momentum", "ptrs", "flow", "energy", "structure",
        "mp", "elder", "entry", "stop",
        "dsl_stop", "dsl_risk", "dsl_rr_pct",
        "dsl_atr_ratio", "atr_14d",
        "dsl_tp_1r", "dsl_tp_2r", "dsl_tp_3r",
        "beta_30d", "beta_60d", "rr_est", "elder_5d", "mp_state", "pe", "pipe_rank",
        "fib", "floor", "rank_explain",
    ]
    for _tier_name in ("top_picks", "edge_list", "longlist"):
        for _rec in export[_tier_name]:
            _missing = [f for f in _REQUIRED_FIELDS if f not in _rec]
            if _missing:
                raise ValueError(
                    f"SCHEMA VIOLATION: {_tier_name} record "
                    f"'{_rec.get('ticker', '?')}' missing fields: {_missing}"
                )

    return export


def _upload_file(filename: str, content: str) -> dict:
    """Upload to the pinned Drive folder via REST API. Returns result dict.

    Destination is the folder ID configured in gdrive_uploader
    (GDRIVE_FOLDER_ID, default = the linked AQE folder).
    """
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            return gdrive_uploader.upload_or_replace(
                filename, content, mime="application/json",
            )
        return {"ok": False, "reason": "not configured"}
    except Exception as exc:                                                    # noqa: BLE001
        return {"ok": False, "reason": f"uploader error: {exc}"}


def _upload_file_to_folder(filename: str, content: str, folder_id: str) -> dict:
    """Upload to a specific Drive folder ID via REST API. Returns result dict."""
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            return gdrive_uploader.upload_or_replace(
                filename, content, mime="application/json", folder_id=folder_id,
            )
        return {"ok": False, "reason": "not configured"}
    except Exception as exc:                                                    # noqa: BLE001
        return {"ok": False, "reason": f"uploader error: {exc}"}


def _build_sector_map_rich() -> dict:
    """Build the rich sector RAG map (Data Schema Spec v1.0 §6.2) for Drive.

    {version, ticker_count, tickers: {tk: {gics_etf, gics_sector_name,
    thematic_basket, source, confirmed_date}}, gaps}.

    AQE auto-sources GICS for any universe ticker missing from the map (via
    FMP profiles) BEFORE serializing, so the published RAG has no blanks — the
    user does not curate by hand; AQE fills the gaps.
    """
    from datetime import date as _date
    _ver = _date.today().isoformat()

    # Auto-fill blanks: resolve GICS for unmapped universe tickers via FMP
    # (incremental — only the gaps are fetched). Best-effort.
    try:
        from src.data.sector_mapper import build_sector_map, get_sector_map_gaps
        if get_sector_map_gaps():
            build_sector_map()
    except Exception:  # noqa: BLE001
        pass

    sm = load_sector_map()
    try:
        from src.data.universe import load_universe
        univ = load_universe(include_benchmark=False)
    except Exception:  # noqa: BLE001
        univ = list(sm.keys())

    tickers: dict[str, dict] = {}
    gaps: list[str] = []
    for t in sorted(set(univ) | set(sm.keys())):
        etf = sm.get(t)
        if etf:
            tickers[t] = {
                "gics_etf": etf,
                "gics_sector_name": ETF_TO_NAME.get(etf),
                "thematic_basket": None,
                "source": "AUTO",
                "confirmed_date": _ver,
            }
        else:
            tickers[t] = {
                "gics_etf": None, "gics_sector_name": None,
                "thematic_basket": None, "source": "UNKNOWN",
                "confirmed_date": None,
            }
            gaps.append(t)
    return {
        "version": _ver,
        "ticker_count": len(tickers),
        "tickers": tickers,
        "gaps": gaps,
    }


def export_to_drive(shortlist: dict | None = None) -> dict:
    """Build the combined export JSON and publish it to the Drive folder.

    Publishes ONE file, overwriting it each run so the folder never clutters:
      aqe_daily_export.json — scan + SRM combined (the committee's read)

    written via:
      - Local OUTPUT_DIR (the app's own working copy — always)
      - Drive REST API into the pinned folder (if OAuth configured)

    Returns dict with status and per-file results.
    """
    export = build_export(shortlist)
    if not export:
        return {"status": "skipped", "reason": "No shortlist data"}

    date_str = export.get("date", "unknown")
    written: list[str] = []
    drive_results: list[dict] = []

    # ---- AQE export ----
    aqe_content = json.dumps(export, indent=2)
    local_aqe = OUTPUT_DIR / EXPORT_FILENAME
    if local_aqe.exists():
        local_aqe.unlink()
    local_aqe.write_text(aqe_content, encoding="utf-8")
    written.append(str(local_aqe))

    r = _upload_file(EXPORT_FILENAME, aqe_content)
    drive_results.append({"file": EXPORT_FILENAME, "target": "AQE", **r})
    if r.get("ok"):
        written.append(f"gdrive:{EXPORT_FILENAME}")

    # ---- Sector RAG map → dedicated Drive subfolder (Schema v1.0 §6) ----
    # Best-effort; never affects the primary AQE export status.
    try:
        sector_rich = json.dumps(_build_sector_map_rich(), indent=2)
        sm_local = OUTPUT_DIR / SECTOR_MAP_FILENAME
        if sm_local.exists():
            sm_local.unlink()
        sm_local.write_text(sector_rich, encoding="utf-8")
        written.append(str(sm_local))
        rs = _upload_file_to_folder(SECTOR_MAP_FILENAME, sector_rich, SECTOR_MAP_FOLDER_ID)
        drive_results.append({"file": SECTOR_MAP_FILENAME, "target": "SectorMap", **rs})
        if rs.get("ok"):
            written.append(f"gdrive:{SECTOR_MAP_FILENAME}")
            # Keep the dedicated sector folder to a single file — trash any
            # duplicate/stale copies so AIC always reads exactly one RAG.
            try:
                from src.data import gdrive_uploader
                gdrive_uploader.keep_only_file(SECTOR_MAP_FOLDER_ID, rs.get("file_id"))
            except Exception:                                                   # noqa: BLE001
                pass
    except Exception as exc:                                                    # noqa: BLE001
        drive_results.append({"file": SECTOR_MAP_FILENAME, "ok": False, "reason": str(exc)})

    # Status: ok if the file reached Drive (beyond the local working copy)
    drive_written = [w for w in written if "gdrive:" in w]
    status = "ok" if drive_written else "partial"
    reason = None
    if status == "partial":
        reason = drive_results[0].get("reason") if drive_results else "Drive not published"

    return {
        "status": status,
        "date": date_str,
        "exported_at": export.get("exported_at", ""),
        "written": written,
        "drive_api_results": drive_results,
        **({"reason": reason} if reason else {}),
    }


# Legacy — keep for backward compat
def sync_to_drive(files: list[Path] | None = None) -> dict:
    """Export daily JSON to Google Drive (via local mount)."""
    return export_to_drive()
