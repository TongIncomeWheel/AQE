from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.alerts import heartbeat as H

ET = ZoneInfo("America/New_York")


def _utc(h, m, day=2):        # Mon 2026-11-02, ET = UTC-5
    return datetime(2026, 11, day, h, m, tzinfo=timezone.utc)


def _hb(minutes_ago, now):
    return {"last_primary_utc": (now - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")}


def test_outside_window_never_stale():
    now = _utc(12, 0)                                   # 07:00 ET
    assert H.deadman_status(None, now)["stale"] is False


def test_window_just_opened_not_due():
    now = _utc(14, 50)                                  # 09:50 ET
    st = H.deadman_status(None, now)
    assert st["stale"] is False and "not yet due" in st["reason"]


def test_missing_heartbeat_in_window_is_stale_and_loud():
    st = H.deadman_status(None, _utc(16, 0), load_problem="heartbeat unreadable from Drive: boom")
    assert st["stale"] and "no primary-poller heartbeat" in st["reason"] and "boom" in st["reason"]


def test_fresh_beat_alive_old_beat_stale():
    now = _utc(16, 0)
    assert H.deadman_status(_hb(35, now), now)["stale"] is False
    st = H.deadman_status(_hb(46, now), now)
    assert st["stale"] and st["age_min"] == 46.0


def test_backstop_beat_does_not_mask_a_dead_primary(monkeypatch, tmp_path):
    monkeypatch.setattr(H, "LOCAL_PATH", tmp_path / "hb.json")
    monkeypatch.setattr(H, "load", lambda: (None, None))
    hb = H.beat({"ok": True}, now_utc=_utc(16, 0), source="gha")
    assert "last_backstop_utc" in hb and "last_primary_utc" not in hb
    assert H.deadman_status(hb, _utc(16, 1))["stale"] is True


def test_primary_beat_recorded_and_seq_increments(monkeypatch, tmp_path):
    monkeypatch.setattr(H, "LOCAL_PATH", tmp_path / "hb.json")
    store = {}
    monkeypatch.setattr(H, "load", lambda: (dict(store) or None, None))
    for i in range(2):
        store.update(H.beat({"ok": True, "checked": 5}, now_utc=_utc(16, i), source="hf"))
    assert store["seq"] == 2 and store["primary_source"] == "hf" and store["checked"] == 5


def test_alarm_sent_once_per_day(monkeypatch, tmp_path):
    monkeypatch.setattr(H, "LOCAL_PATH", tmp_path / "hb.json")
    store = {"last_primary_utc": _utc(14, 50).isoformat()}
    monkeypatch.setattr(H, "load", lambda: (dict(store), None))
    monkeypatch.setattr(H, "_save", lambda hb: store.update(hb))
    sent = []
    import src.alerts.notice as N
    monkeypatch.setattr(N, "publish_alarm", lambda r, **k: sent.append(r) or {"publish": {"drive": "ok"}})
    a = H.check_and_alarm(now_utc=_utc(16, 0))
    b = H.check_and_alarm(now_utc=_utc(16, 10))
    assert a["alarm_sent"] and not b["alarm_sent"] and len(sent) == 1 and b["stale"]


def test_failed_send_does_not_mark_the_day_so_it_retries(monkeypatch):
    store = {"last_primary_utc": _utc(14, 50).isoformat()}
    monkeypatch.setattr(H, "load", lambda: (dict(store), None))
    monkeypatch.setattr(H, "_save", lambda hb: store.update(hb))
    import src.alerts.notice as N
    monkeypatch.setattr(N, "publish_alarm", lambda r, **k: {"publish": {"drive": "failed: x", "github_latest": "failed: y"}})
    st = H.check_and_alarm(now_utc=_utc(16, 0))
    assert not st["alarm_sent"] and "alarm_day" not in store and "not published" in st["alarm_detail"]


def test_no_email_backend_is_ever_used_for_the_alarm():
    import src.alerts.emailer as EM
    assert not hasattr(EM, "send_deadman_alarm")


def test_engine_wrapper_beats_only_when_gate_passed(monkeypatch):
    from src.alerts import engine as E
    beats = []
    monkeypatch.setattr(H, "beat", lambda s, **k: beats.append(s) or {})
    monkeypatch.setattr(E, "_run_alert_cycle", lambda **k: {"ok": True, "in_window": True})
    E.run_alert_cycle()
    monkeypatch.setattr(E, "_run_alert_cycle", lambda **k: {"ok": False, "reason": "outside US market hours"})
    E.run_alert_cycle()
    assert len(beats) == 1


def test_engine_wrapper_survives_a_crashed_cycle(monkeypatch):
    from src.alerts import engine as E
    beats = []
    monkeypatch.setattr(H, "beat", lambda s, **k: beats.append(s) or {})
    def boom(**k): raise RuntimeError("x")
    monkeypatch.setattr(E, "_run_alert_cycle", boom)
    s = E.run_alert_cycle()
    assert s["ok"] is False and "crashed" in s["reason"] and beats and beats[0]["crashed"]


def test_crashed_cycle_does_not_count_as_alive(monkeypatch, tmp_path):
    monkeypatch.setattr(H, "LOCAL_PATH", tmp_path / "hb.json")
    monkeypatch.setattr(H, "load", lambda: ({"last_primary_utc": _utc(14, 50).isoformat()}, None))
    hb = H.beat({"ok": False, "crashed": True, "reason": "cycle crashed: X"}, now_utc=_utc(16, 0), source="hf")
    assert hb["last_primary_utc"] == _utc(14, 50).isoformat() and hb["last_crash_reason"]
    assert H.deadman_status(hb, _utc(16, 1))["stale"] is True


def test_beat_records_email_outcome_and_notice_problem(tmp_path, monkeypatch):
    """A failed card-digest send must leave a trace the status check can read."""
    monkeypatch.setattr(H, "LOCAL_PATH", tmp_path / "hb.json")
    monkeypatch.setattr(H, "load", lambda: (__import__("json").loads((tmp_path / "hb.json").read_text())
                                            if (tmp_path / "hb.json").exists() else None, None))
    monkeypatch.setattr(H, "_save", lambda hb: (tmp_path / "hb.json").write_text(__import__("json").dumps(hb)) and None)
    bad = {"ok": True, "_notice": {"email": {"ok": False, "reason": "resend HTTP 403: nope", "subject": "S"}}}
    hb = H.beat(bad, now_utc=_utc(16, 0), source="hf")
    assert hb["last_email_ok"] is False and "403" in hb["last_email_reason"]
    assert "last_email_sent_utc" not in hb
    good = {"ok": True, "_notice": {"email": {"ok": True, "subject": "S2"}}}
    hb = H.beat(good, now_utc=_utc(16, 15), source="hf")
    assert hb["last_email_ok"] is True and hb["last_email_sent_utc"].startswith("2026-11-02T16:15")
    quiet = H.beat({"ok": True}, now_utc=_utc(16, 30), source="hf")
    assert quiet["last_email_sent_utc"].startswith("2026-11-02T16:15")     # a quiet cycle keeps the last send
    H.note_notice_problem("notice publish: {'drive': 'failed: x'}", now_utc=_utc(16, 31))
    assert "failed" in H.load()[0]["last_notice_problem"]
