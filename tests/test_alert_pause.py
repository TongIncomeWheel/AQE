"""PM order 2026-11-12: one reversible switch pauses every alert path."""
import json
from datetime import datetime, timezone

from src.alerts import engine, heartbeat, pause


class FakeDrive:
    def __init__(self, text=None, boom=False):
        self.files, self.boom = ({pause.FLAG_FILENAME: text} if text else {}), boom
    def is_configured(self): return True
    def download_text(self, name, folder_id=None):
        if self.boom: raise OSError("drive down")
        return self.files.get(name)
    def upload_or_replace(self, name, content, mime=None): self.files[name] = content


def _drive(monkeypatch, fake):
    import src.data.gdrive_uploader as G
    for n in ("is_configured", "download_text", "upload_or_replace"):
        monkeypatch.setattr(G, n, getattr(fake, n))


def test_pause_resume_roundtrip_reads_back(monkeypatch):
    monkeypatch.delenv("ALERTS_PAUSED", raising=False)
    fake = FakeDrive(); _drive(monkeypatch, fake)
    assert pause.status()["paused"] is False                       # no file = running
    st = pause.set_paused(True, "PM order")
    assert st["paused"] and st["why"] == "PM order" and json.loads(fake.files[pause.FLAG_FILENAME])["paused"] is True
    st = pause.set_paused(False, "PM resumed")
    assert st["paused"] is False and pause.FLAG_FILENAME in fake.files        # rewritten, never deleted


def test_env_var_pauses_one_process(monkeypatch):
    _drive(monkeypatch, FakeDrive()); monkeypatch.setenv("ALERTS_PAUSED", "true")
    assert pause.is_paused()


def test_an_unreadable_flag_does_not_turn_the_alerts_off_and_says_so(monkeypatch):
    monkeypatch.delenv("ALERTS_PAUSED", raising=False)
    _drive(monkeypatch, FakeDrive(boom=True))
    st = pause.status()
    assert st["paused"] is False and "unreadable" in st["problem"]


def test_a_paused_cycle_pulls_nothing_sends_nothing_and_does_not_beat(monkeypatch):
    monkeypatch.delenv("ALERTS_PAUSED", raising=False)
    _drive(monkeypatch, FakeDrive(json.dumps({"paused": True, "reason": "PM order", "since": "2026-11-12T10:00:00+00:00"})))
    called = []
    monkeypatch.setattr(engine, "_run_alert_cycle", lambda **k: called.append("cycle") or {})
    monkeypatch.setattr(heartbeat, "beat", lambda *a, **k: called.append("beat"))
    s = engine.run_alert_cycle(send_email=True, force=True)               # even a forced/manual cycle
    assert called == [] and s["paused"] and s["ok"] and not s["emailed"] and "PAUSED" in s["reason"]


def test_running_cycle_is_untouched(monkeypatch):
    monkeypatch.delenv("ALERTS_PAUSED", raising=False)
    _drive(monkeypatch, FakeDrive())
    monkeypatch.setattr(engine, "_run_alert_cycle", lambda **k: {"ok": True, "reason": "ran"})
    assert engine.run_alert_cycle()["reason"] == "ran"


def test_deadman_does_not_alarm_while_paused(monkeypatch):
    monkeypatch.delenv("ALERTS_PAUSED", raising=False)
    _drive(monkeypatch, FakeDrive(json.dumps({"paused": True, "since": "2026-11-12T10:00:00+00:00"})))
    st = heartbeat.check_and_alarm(send=True, now_utc=datetime(2026, 11, 12, 16, 0, tzinfo=timezone.utc))
    assert st["stale"] is False and st["paused"] and st["alarm_sent"] is False


def test_no_drive_configured_is_cannot_verify_never_running(monkeypatch, capsys):
    """Conductor 2026-11-19: a container with no Drive credentials reported RUNNING while the real flag was PAUSED. A flag that was not read is never 'not paused'."""
    monkeypatch.delenv("ALERTS_PAUSED", raising=False)
    import src.data.gdrive_uploader as G
    monkeypatch.setattr(G, "is_configured", lambda: False)
    st = pause.status()
    assert st["paused"] is False and st["verified"] is False and "CANNOT VERIFY" in st["problem"]
    from scripts import alerts_pause
    rc = alerts_pause.main(["status"])
    out = capsys.readouterr().out
    assert rc != 0 and "CANNOT VERIFY" in out and "RUNNING" not in out


def test_a_verified_flag_still_prints_running_or_paused(monkeypatch, capsys):
    monkeypatch.delenv("ALERTS_PAUSED", raising=False)
    from scripts import alerts_pause
    _drive(monkeypatch, FakeDrive(json.dumps({"paused": False, "reason": "resumed"})))
    assert alerts_pause.main(["status"]) == 0 and "RUNNING" in capsys.readouterr().out
    _drive(monkeypatch, FakeDrive(json.dumps({"paused": True, "since": "2026-11-12T10:00:00+00:00"})))
    assert alerts_pause.main(["status"]) == 0 and "PAUSED" in capsys.readouterr().out
