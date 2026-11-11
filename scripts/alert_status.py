"""Read-only alert status for a human question 'are the alerts alive and what did the last cycles do?' (conductor/PM 2026-11-11).

    python -m scripts.alert_status

Prints, from Drive (needs the Google OAuth secrets): the poller heartbeat, the last SUCCESSFUL digest send, the latest cockpit notice (cycle time, seq, email result, engine),
and the condition-state summary (run dates, how many names carry a fired state). Sends nothing, writes nothing. Each block says plainly if it could not be read."""
import json
import sys
from datetime import datetime, timezone


def _blk(title, fn):
    print(f"--- {title}")
    try:
        print(fn())
    except Exception as exc:  # noqa: BLE001 - a block that cannot be read says so, it never hides the others
        print(f"UNREADABLE: {type(exc).__name__}: {exc}")


def _heartbeat():
    from src.alerts import heartbeat
    hb, why = heartbeat.load()
    return json.dumps({"why_unreadable": why, "heartbeat": hb}, indent=1, default=str)


def _digest():
    from src.alerts import state
    d = state.load_last_digest_sent()
    now = datetime.now(timezone.utc)
    return f"last successful digest send: {d.isoformat() if d else 'NONE on record'}" + (f" ({(now - d).total_seconds() / 3600:.1f} h ago)" if d else "")


def _notice():
    from src.data import gdrive_uploader
    txt = gdrive_uploader.download_text("aqe_alert_notice.json") if gdrive_uploader.is_configured() else None
    if not txt:
        return "no aqe_alert_notice.json on Drive (or Drive not configured)"
    n = json.loads(txt)
    return json.dumps({k: n.get(k) for k in ("session_date", "seq", "cycle_at_utc", "cycle_at_sgt", "source", "actionable", "quiet_line", "email", "engine", "data", "market", "suppressed")}, indent=1, default=str)


def _cond():
    from src.alerts import condition_state
    st = condition_state.load_condition_state() or {}
    runs, emailed = {}, {}
    for k, v in st.items():
        d, _, tk = str(k).partition(":")
        r = runs.setdefault(d, {"entries": 0, "past_watching": 0, "emailed": 0})
        r["entries"] += 1
        if isinstance(v, dict):
            if v.get("stage") not in (None, "WATCHING"):
                r["past_watching"] += 1
            if v.get("emailed_today"):
                r["emailed"] += 1
                emailed.setdefault(d, []).append(f"{tk}:{','.join(v['emailed_today'])}")
    last = sorted(runs)[-3:]
    return json.dumps({"by_run_date": {d: runs[d] for d in sorted(runs)}, "names_emailed_on_the_last_3_run_dates": {d: emailed.get(d, []) for d in last}}, indent=1)


def main():
    _blk("poller heartbeat", _heartbeat)
    _blk("last digest sent", _digest)
    _blk("latest cockpit notice (Drive)", _notice)
    _blk("condition state", _cond)
    return 0


if __name__ == "__main__":
    sys.exit(main())
