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

from . import explain, spec, weather

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
