import json
import sys
import types

import pytest

from src.alerts import condition_ledger as CL


class FakeDrive(types.ModuleType):
    def __init__(self, configured=True, fail=False):
        super().__init__("src.data.gdrive_uploader")
        self.files, self.configured, self.fail, self.uploads = {}, configured, fail, 0

    def is_configured(self): return self.configured
    def download_text(self, name, folder_id=None):
        if self.fail: raise OSError("drive down")
        return self.files.get(name)
    def upload_or_replace(self, name, content, mime="x", **k):
        self.files[name] = content; self.uploads += 1


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(CL, "LEDGER_DIR", tmp_path)
    drive = FakeDrive()
    import src.data as data_pkg
    monkeypatch.setitem(sys.modules, "src.data.gdrive_uploader", drive)
    monkeypatch.setattr(data_pkg, "gdrive_uploader", drive, raising=False)
    return drive


def L(ts, t="AAA"): return {"ts": ts, "ticker": t, "fired_states": []}


def test_publish_then_restore_after_container_wipe(env, tmp_path):
    for i in range(3): CL.append_line("2026-11-02", L(f"2026-11-02T22:{30+i}:00+08:00"))
    assert CL.sync_with_drive("2026-11-02")["ok"] is True
    name = "aqe_condition_ledger_2026-11-02.jsonl"
    assert len(env.files[name].strip().splitlines()) == 3
    (tmp_path / "2026-11-02.jsonl").unlink()                 # container rebuilt: disk gone
    r = CL.sync_with_drive("2026-11-02")                      # start of next cycle
    assert r["ok"] and len(CL.load_lines("2026-11-02")) == 3
    CL.append_line("2026-11-02", L("2026-11-02T23:30:00+08:00"))
    CL.sync_with_drive("2026-11-02")
    assert len(env.files[name].strip().splitlines()) == 4     # NOT overwritten by a shorter copy


def test_two_pollers_union_without_duplicates(env, tmp_path):
    env.files["aqe_condition_ledger_2026-11-02.jsonl"] = json.dumps(L("2026-11-02T22:35:00+08:00", "HF")) + "\n"
    CL.append_line("2026-11-02", L("2026-11-02T22:30:00+08:00", "GH"))
    CL.sync_with_drive("2026-11-02"); CL.sync_with_drive("2026-11-02")
    lines = CL.load_lines("2026-11-02")
    assert [l["ticker"] for l in lines] == ["GH", "HF"]       # ordered by ts, no dupes


def test_drive_failure_is_loud_and_local_file_untouched(env, tmp_path):
    CL.append_line("2026-11-02", L("2026-11-02T22:30:00+08:00"))
    env.fail = True
    r = CL.sync_with_drive("2026-11-02")
    assert r["ok"] is False and "drive down" in r["error"]
    assert len(CL.load_lines("2026-11-02")) == 1


def test_not_configured_is_declared_not_ok(env):
    env.configured = False
    assert CL.sync_with_drive("2026-11-02") == {"ok": None, "skipped": "drive not configured"}
