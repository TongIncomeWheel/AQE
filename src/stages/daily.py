"""Stage Weather — nightly orchestration (daily Step 8a-1c).

Wrapped exactly like Crown / VALEN: an ADDITION to a working real-money
pipeline, never allowed to take the export down. Runs after Step 8 so the
held book and daily_list it reports on are this run's, not yesterday's.

Two files, same split as every macro artifact:
  output/stage_weather.json       full detail incl. every panel name's stage
  output/aqe_stage_weather.json   plain English first, published copy
                                  (GitHub aegis/output + Daily Persist)

Loud, never silently empty: if the export can't be read, `held_status` /
`daily_list_status` say UNAVAILABLE with the reason; if the weekly panel is
missing the whole artifact is `status: UNAVAILABLE`.
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.data.paths import OUTPUT_DIR, PANEL_DAILY, PANEL_WEEKLY

from . import explain, spec, ticker, weather

LOCAL_PATH = OUTPUT_DIR / "stage_weather.json"
PUBLISHED_PATH = OUTPUT_DIR / "aqe_stage_weather.json"
EXPORT_PATH = OUTPUT_DIR / "aqe_daily_export.json"


def _names_from_export(export_path) -> tuple[list, list, str, str]:
    try:
        ex = json.loads(export_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        why = f"UNAVAILABLE - export unreadable ({exc})"
        return [], [], why, why
    dl = [r.get("ticker") for r in ex.get("daily_list") or [] if r.get("ticker")]
    held = [r.get("ticker") for r in ex.get("held_positions") or [] if r.get("ticker")]
    hs = ex.get("held_positions_status") or "unknown"
    return dl, held, ("OK" if dl else "EMPTY - export has no daily_list rows"), f"held_positions_status={hs}"


def run_stage_weather(panel_weekly=PANEL_WEEKLY, panel_daily=PANEL_DAILY,
                      export_path=EXPORT_PATH) -> dict:
    now = datetime.now(ZoneInfo("Asia/Singapore"))
    base = {"date": now.date().isoformat(), "exported_at": now.isoformat(timespec="seconds"),
            "source": "Weinstein four-stage analysis on weekly bars (src/stages/spec.py)"}
    if not panel_weekly.exists():
        art = {**base, "status": "UNAVAILABLE", "reason": f"{panel_weekly.name} not found"}
        art["plain_english"] = explain.build(art)
        return art
    from src.engines.srm import GICS_ETFS
    dl, held, dl_status, held_status = _names_from_export(export_path)
    art = {**base, **weather.compute(panel_weekly, panel_daily, GICS_ETFS, held=held, daily_list=dl)}
    art["daily_list_status"] = dl_status
    art["held_status"] = held_status
    art["population_note"] = (f"Breadth counts every single name on AQE's own weekly panel "
                              f"({spec.POPULATION_PANEL}), not the whole US market.")
    ok_mkt = (art.get("market_read") or {}).get("status") == "OK"
    art["status"] = "OK" if ok_mkt and (art.get("breadth") or {}).get("status") == "OK" else (
        "DEGRADED" if ok_mkt else "UNAVAILABLE")
    art["plain_english"] = explain.build(art)
    return art


def write_artifacts(art: dict) -> dict:
    art = {k: v for k, v in art.items() if not k.startswith("_")}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_PATH.write_text(json.dumps(art, indent=2, default=str), encoding="utf-8")
    keep = ("date", "exported_at", "status", "reason", "as_of_session", "source", "market_read",
            "market", "sectors", "sector_groups", "breadth", "held", "held_status",
            "held_changes", "daily_list_status", "daily_list_changes", "all_confirmed_this_week",
            "population_note")
    published = {"read_me_first": art.get("plain_english"),
                 **{k: art[k] for k in keep if k in art}}
    PUBLISHED_PATH.write_text(json.dumps(published, indent=2, default=str), encoding="utf-8")
    return {"local": str(LOCAL_PATH), "published": str(PUBLISHED_PATH)}


def load_stage_weather() -> dict | None:
    if not LOCAL_PATH.exists():
        return None
    try:
        return json.loads(LOCAL_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def attach_to_export(daily_list: list[dict], held_positions: list[dict] | None = None, *,
                     panel_weekly=PANEL_WEEKLY, panel_daily=PANEL_DAILY) -> tuple[dict, dict]:
    """Stamp ticker-level stage columns on every daily_list + held row and build
    the export's top-level `stage_market` block (market + sectors + breadth).

    Same weather.compute() / classify() the Stage Weather artifact uses, on the
    same panel, so a row's stage and the breadth count can never disagree.
    Never raises. Returns (stage_status, stage_market); on failure rows are left
    untouched and the status says why (LOUD, never an empty column)."""
    from src.engines.srm import GICS_ETFS
    held_positions = held_positions or []
    rows = list(daily_list) + list(held_positions)
    try:
        if not panel_weekly.exists():
            raise FileNotFoundError(f"{panel_weekly.name} not found")
        tks = sorted({r.get("ticker") for r in rows if r.get("ticker")})
        w = weather.compute(panel_weekly, panel_daily, GICS_ETFS,
                            held=[r.get("ticker") for r in held_positions if r.get("ticker")],
                            daily_list=[r.get("ticker") for r in daily_list if r.get("ticker")],
                            extra=tks)
        daily = w.pop("_daily")
        reads = w.pop("_reads")
        slopes = ticker.ma200_slope(daily, tks) if daily is not None else {}
        sector_stage = {t: r.get("stage") for t, r in (w.get("sectors") or {}).items()}
        mkt = (w.get("market_read") or {}).get("stage")
        counts = ticker.stamp_rows(rows, reads, slopes, sector_stage, mkt)
    except Exception as exc:  # noqa: BLE001 -- additive, never takes the export down
        return {"status": "error", "reason": str(exc), "stamped": 0}, {"status": "UNAVAILABLE", "reason": str(exc)}

    dl = [r for r in daily_list if r.get("stage") is not None]
    status = {
        "status": "live", **counts,
        "unreadable": sorted(r.get("ticker") for r in rows if r.get("stage") is None),
        "daily_list_by_stage": {f"stage_{s}": sum(1 for r in dl if r["stage"] == s) for s in spec.STAGES},
        "trend_template_pass": sorted(r["ticker"] for r in daily_list if r.get("trend_template") == "PASS"),
        "stage2_confirmed": sorted(r["ticker"] for r in daily_list if r.get("stage2_confirmed")),
        "changed_this_week": sorted(r["ticker"] for r in rows if r.get("stage_transition")),
        "rule": "Weinstein stage on weekly bars vs the 30-week average (src/stages/spec.py); Trend Template = "
                "Minervini C3, Stage 2 confirmation = Minervini C2. Readings only.",
    }
    art = {**w, "as_of_session": w.get("as_of_session")}
    stage_market = {
        "status": "OK" if (w.get("market_read") or {}).get("status") == "OK" else "UNAVAILABLE",
        "as_of_session": w.get("as_of_session"),
        "headline": explain.build(art).get("headline"),
        "market_read": w.get("market_read"),
        "market": w.get("market"),
        "sectors": w.get("sectors"),
        "sector_groups": w.get("sector_groups"),
        "breadth": w.get("breadth"),
        "population_note": f"Breadth counts every single name on AQE's weekly panel ({spec.POPULATION_PANEL}).",
    }
    return status, stage_market
