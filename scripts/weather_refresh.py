"""Refresh ONLY the macro weather (Crown, scenarios, macro pack, Valen, feed timing) from current data and republish those files.

PM 2026-11-04 (stale Crown/VIX/COT/breadth): the weather legs get fresher after the nightly started (Cboe posts VIX/VIXEQ ~10:11 SGT,
DSPX ~10:41 SGT), so they can be refreshed later in the day without redoing the export. This restores the whole state snapshot (the
panel job persists the whole-market panel), reruns steps 6f-6i, writes the artifacts and publishes ONLY the weather files. It never
touches the export, the packets, the committee data, the committee run files, or the nightly's run marker; it writes its own marker
`aqe_weather_refresh.json`. Exit 0 always prints the legs table so the caller sees which legs are CURRENT.
    python -m scripts.weather_refresh
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WEATHER_FILES = ("aqe_crown_macro.json", "crown_macro.json", "macro_scenarios.json", "aqe_macro_pack.json",
                 "aqe_valen_dashboard.json", "valen_dashboard.json", "feed_timing.json", "aqe_weather_refresh.json")


def main() -> int:
    from src.data.paths import OUTPUT_DIR
    stamp = datetime.now(ZoneInfo("Asia/Singapore"))
    marker = {"at": stamp.strftime("%Y-%m-%d %H:%M:%S SGT"), "steps": {}}
    try:
        from src.data import persist
        got = persist.load_snapshot_github()
        if not (got or {}).get("ok"):
            got = persist.load_snapshot()
        marker["steps"]["restore"] = "ok" if (got or {}).get("ok") else f"FAILED: {(got or {}).get('reason')}"
    except Exception as e:  # noqa: BLE001
        marker["steps"]["restore"] = f"FAILED: {e}"
    print("restore:", marker["steps"]["restore"])

    cr = sc = vl = None
    try:
        from src.macro.crown.daily import run_crown
        cr = run_crown(with_gamma=True)
        marker["steps"]["crown"] = cr.get("crown_status")
    except Exception as e:  # noqa: BLE001
        marker["steps"]["crown"] = f"FAILED: {e}"
    try:
        from src.macro.scenarios import run_scenarios
        sc = run_scenarios()
        marker["steps"]["scenarios"] = sc.get("status")
    except Exception as e:  # noqa: BLE001
        marker["steps"]["scenarios"] = f"FAILED: {e}"
    try:
        from src.macro.crown.export import publish_reading_copy
        pub = publish_reading_copy(cr, sc)
        marker["steps"]["crown_reading_copy"] = "ok" if pub.get("ok") else f"FAILED: {pub.get('reason')}"
    except Exception as e:  # noqa: BLE001
        marker["steps"]["crown_reading_copy"] = f"FAILED: {e}"
    try:
        from src.valen.daily import run_valen, write_artifacts
        vl = run_valen()
        write_artifacts(vl)
        marker["steps"]["valen"] = vl.get("status")
    except Exception as e:  # noqa: BLE001
        marker["steps"]["valen"] = f"FAILED: {e}"
    try:
        from src.macro.pack import run_pack
        pk = run_pack(write=True)
        marker["steps"]["macro_pack"] = pk.get("pack_status")
    except Exception as e:  # noqa: BLE001
        marker["steps"]["macro_pack"] = f"FAILED: {e}"
    legs = ((vl or {}).get("data_freshness") or {})
    try:
        from src.data import feed_timing
        from src.macro import legs as L
        feed_timing.record(stamp.date().isoformat(), legs=legs.get("legs_table"))
        marker["legs"] = L.one_line(legs.get("legs_table") or [])
        marker["expected_session"] = legs.get("expected_session")
        marker["current"] = [r["leg"] for r in legs.get("legs_table") or [] if r["reason"] == "CURRENT"]
        marker["not_current"] = [{"leg": r["leg"], "as_of": r["as_of"], "reason": r["reason"]} for r in legs.get("legs_table") or [] if r["reason"] != "CURRENT"]
    except Exception as e:  # noqa: BLE001
        marker["legs"] = f"FAILED: {e}"
    (OUTPUT_DIR / "aqe_weather_refresh.json").write_text(json.dumps(marker, indent=1), encoding="utf-8")
    print("legs:", marker.get("legs"))
    print("CURRENT:", marker.get("current"))
    print("NOT CURRENT:", marker.get("not_current"))
    try:
        from src.data import github_sync
        res = github_sync.publish_daily_outputs(stamp=stamp.strftime("%Y-%m-%d"), names=list(WEATHER_FILES))
        print("published:", {k: res.get(k) for k in ("written", "total", "failed", "absent")})
        return 0 if not res.get("failed") else 1
    except Exception as e:  # noqa: BLE001
        print(f"publish FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
