"""Regression test for the 2026-09-04 incident: _write_marker() only ever
wrote the run-status marker (aqe_last_run.json) locally and, best-effort, to
Drive -- never to GitHub. That write happens in THIS process, after
daily_orchestrator's own subprocess (and its Step 8a-2 GitHub publish, which
runs mid-subprocess) has already exited, so nothing else was going to push it
either.

On a persistent HF Space container the local write is enough (the same
process keeps serving pages), which is why this went unnoticed. On a GitHub
Actions runner the local write is discarded the instant the job ends: a
genuinely successful 2026-09-03 backstop run (confirmed via its own job log:
'status=success ... exported_at=2026-09-03 14:38:31 SGT', and the real
aqe_daily_export.json on GitHub matching that timestamp exactly) left the
published aqe_last_run.json stuck on 2026-09-02 -- making a working backstop
look, from the one file anyone actually checks, like nothing had run in two
days."""

from __future__ import annotations

import json

from src.ui import daily_job as J


def test_write_marker_publishes_to_github_when_configured(tmp_path, monkeypatch):
    from src.data import paths as P
    monkeypatch.setattr(P, "OUTPUT_DIR", tmp_path)

    from src.data import github_sync as G
    monkeypatch.setattr(G, "is_configured", lambda: True)
    calls = []
    monkeypatch.setattr(G, "put_output",
                        lambda filename, content, message=None: calls.append(
                            (filename, content, message)) or {"ok": True})

    # Drive is best-effort and irrelevant to this test -- keep it a no-op.
    from src.data import gdrive_uploader as GD
    monkeypatch.setattr(GD, "is_configured", lambda: False)

    marker = {"date_sgt": "2026-09-04", "status": "success", "rc": 0}
    J._write_marker(marker)

    assert len(calls) == 1, "the marker must reach GitHub, not just local/Drive"
    filename, content, message = calls[0]
    assert filename == J.MARKER_FILENAME
    assert json.loads(content) == marker
    assert "2026-09-04" in (message or "")


def test_write_marker_never_raises_when_github_publish_fails(tmp_path, monkeypatch):
    from src.data import paths as P
    monkeypatch.setattr(P, "OUTPUT_DIR", tmp_path)

    from src.data import github_sync as G
    monkeypatch.setattr(G, "is_configured", lambda: True)

    def _boom(*a, **k):
        raise RuntimeError("network gone")
    monkeypatch.setattr(G, "put_output", _boom)

    from src.data import gdrive_uploader as GD
    monkeypatch.setattr(GD, "is_configured", lambda: False)

    J._write_marker({"date_sgt": "2026-09-04", "status": "failed"})  # must not raise

    # The local write must still have happened despite the GitHub failure.
    assert (tmp_path / J.MARKER_FILENAME).exists()


def test_write_marker_skips_github_cleanly_when_not_configured(tmp_path, monkeypatch):
    from src.data import paths as P
    monkeypatch.setattr(P, "OUTPUT_DIR", tmp_path)

    from src.data import github_sync as G
    monkeypatch.setattr(G, "is_configured", lambda: False)
    calls = []
    monkeypatch.setattr(G, "put_output", lambda *a, **k: calls.append(1))

    from src.data import gdrive_uploader as GD
    monkeypatch.setattr(GD, "is_configured", lambda: False)

    J._write_marker({"date_sgt": "2026-09-04", "status": "success"})

    assert calls == [], "must not attempt a GitHub write when GITHUB_TOKEN isn't set"
