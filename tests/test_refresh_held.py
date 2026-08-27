"""Tests for src/pipeline/refresh_held.py — the fast, held-book-only
incident-response path built after the 2026-08-21 incident where a full
~800-ticker pipeline run died mid-pull and took the held-book refresh (which
only needed a dozen names) down with it.

These test the ORCHESTRATION only (which steps run, in what order, on what
inputs) by mocking every downstream module — the downstream modules
(ptj.refresh_held_positions, panel_builder.pull_tickers, score_runner.
build_scores, drive_sync.export_to_drive, github_sync.publish_daily_outputs)
each have their own test coverage."""

from __future__ import annotations

import pytest

from src.pipeline import refresh_held as rh


@pytest.fixture(autouse=True)
def _warm_state_by_default(monkeypatch):
    """Step 0 (2026-08-27) calls src.ui.bootstrap.autoload_state -- without a
    mock every test would hit the real local filesystem (and, on a genuinely
    cold machine, the real network) depending on ambient state, which is
    exactly the non-determinism this file's own docstring says these tests
    avoid by mocking every downstream module. Default to "already warm";
    the two tests below override this to exercise the cold/failed paths."""
    from src.ui import bootstrap
    monkeypatch.setattr(bootstrap, "autoload_state", lambda: {"state": "warm"})


def test_no_held_equity_tickers_skips_pricing_and_export(monkeypatch):
    """An option-only or genuinely flat book must not trigger a price pull,
    score recompute, or export rebuild — there is nothing to refresh."""
    from src.data import ptj
    monkeypatch.setattr(ptj, "refresh_held_positions",
                        lambda: [{"ticker": "IBM_320C", "type": "OPT"}])
    monkeypatch.setattr(ptj, "ptj_status", lambda: "live")

    def _boom(*a, **k):
        raise AssertionError("must not be called when there is nothing held")
    from src.data import panel_builder
    monkeypatch.setattr(panel_builder, "pull_tickers", _boom)

    result = rh.refresh_held()
    assert result["ok"] is True
    assert result["tickers"] == []
    assert result["priced"] is None


def test_held_equity_tickers_run_the_full_chain_in_order(monkeypatch):
    calls = []

    from src.data import ptj
    monkeypatch.setattr(ptj, "refresh_held_positions", lambda: [
        {"ticker": "IBM", "type": "STK"},
        {"ticker": "OXY", "type": "STK"},
        {"ticker": "IBM_320C", "type": "OPT"},  # option leg — never priced
    ])
    monkeypatch.setattr(ptj, "ptj_status", lambda: "live")
    monkeypatch.setattr(ptj, "load_ptj_cache", lambda: {})

    from src.data import panel_builder
    def _pull(tickers, **k):
        calls.append(("pull", tuple(sorted(tickers))))
        return {"pulled": len(tickers), "skipped_current": 0, "failed": [],
                "total_tickers": len(tickers)}
    monkeypatch.setattr(panel_builder, "pull_tickers", _pull)

    from src.scanner import score_runner
    def _scores(only_tickers=None):
        calls.append(("scores", tuple(only_tickers or ())))
    monkeypatch.setattr(score_runner, "build_scores", _scores)

    from src.data import drive_sync
    def _export(*a, **k):
        calls.append(("export",))
        return {"status": "ok"}
    monkeypatch.setattr(drive_sync, "export_to_drive", _export)

    from src.data import github_sync
    def _publish(names=None, **k):
        calls.append(("publish", tuple(names or ())))
        return {"ok": True, "written": len(names or ())}
    monkeypatch.setattr(github_sync, "publish_daily_outputs", _publish)

    result = rh.refresh_held()

    assert result["ok"] is True
    assert result["tickers"] == ["IBM", "OXY"]  # option leg excluded, sorted
    steps = [c[0] for c in calls]
    assert steps == ["pull", "scores", "export", "publish"]
    assert calls[0] == ("pull", ("IBM", "OXY", "SPY"))  # SPY: the scoring benchmark
    assert calls[1] == ("scores", ("IBM", "OXY"))  # scoped, no SPY, no wider universe
    assert calls[3] == ("publish", ("aqe_daily_export.json", "held_positions.json"))


def test_a_stale_fetch_rejection_is_surfaced_but_does_not_abort(monkeypatch):
    """When ptj's monotonic guard rejects this run's own fetch as stale, the
    module must keep going (the already-published book is still valid held
    data) rather than treat it as a hard failure."""
    from src.data import ptj
    monkeypatch.setattr(ptj, "refresh_held_positions",
                        lambda: [{"ticker": "OXY", "type": "STK"}])
    monkeypatch.setattr(ptj, "ptj_status", lambda: "stale_fetch_rejected")
    monkeypatch.setattr(ptj, "load_ptj_cache", lambda: {
        "rejected_fetch": {"source_file": "old.json", "modified": "2026-01-01",
                           "reason": "older than the already-published book"}})

    from src.data import panel_builder
    monkeypatch.setattr(panel_builder, "pull_tickers",
                        lambda tickers, **k: {"pulled": 1, "skipped_current": 0,
                                              "failed": [], "total_tickers": 1})
    from src.scanner import score_runner
    monkeypatch.setattr(score_runner, "build_scores", lambda only_tickers=None: None)
    from src.data import drive_sync
    monkeypatch.setattr(drive_sync, "export_to_drive", lambda *a, **k: {"status": "ok"})
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "publish_daily_outputs",
                        lambda names=None, **k: {"ok": True, "written": len(names or ())})

    result = rh.refresh_held()
    assert result["ok"] is True
    assert result["tickers"] == ["OXY"]


def test_a_ticker_left_unscored_after_build_scores_is_warned_loudly(monkeypatch, capsys, tmp_path):
    """2026-08-21 incident: build_scores() silently produced zero rows for
    every held ticker on a runner with no SPY benchmark data, and nothing in
    the pipeline said so — the gap was only visible later, in the export's
    data_quality block. This is the check that would have caught it in the
    run's own log, immediately."""
    from src.data import ptj
    monkeypatch.setattr(ptj, "refresh_held_positions",
                        lambda: [{"ticker": "GOLD", "type": "STK"}])
    monkeypatch.setattr(ptj, "ptj_status", lambda: "live")
    monkeypatch.setattr(ptj, "load_ptj_cache", lambda: {})

    from src.data import panel_builder
    monkeypatch.setattr(panel_builder, "pull_tickers",
                        lambda tickers, **k: {"pulled": len(tickers), "skipped_current": 0,
                                              "failed": [], "total_tickers": len(tickers)})
    from src.scanner import score_runner
    monkeypatch.setattr(score_runner, "build_scores", lambda only_tickers=None: None)  # writes nothing

    import pandas as pd
    from src.data import paths
    scores_path = tmp_path / "scores_daily.parquet"
    pd.DataFrame({"ticker": []}).to_parquet(scores_path, index=False)  # 0 rows
    monkeypatch.setattr(paths, "SCORES_DAILY", scores_path)

    from src.data import drive_sync
    monkeypatch.setattr(drive_sync, "export_to_drive", lambda *a, **k: {"status": "ok"})
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "publish_daily_outputs",
                        lambda names=None, **k: {"ok": True, "written": len(names or ())})

    result = rh.refresh_held()
    assert result["ok"] is True
    out = capsys.readouterr().out
    assert "GOLD" in out and "NO score row" in out


def test_a_cold_container_is_restored_before_anything_else_runs(monkeypatch, capsys):
    """2026-08-27 incident: refresh-held.yml runs on a bare GitHub Actions
    runner with no persisted data/ at all. build_scores(only_tickers=...)
    then wrote a scores_daily.parquet holding ONLY the held tickers (nothing
    to merge into), and the export rebuild computed daily_list from that --
    publishing a ~6-name list (5 of them the held book) over the real
    ~200-name one. Step 0 must run, and run FIRST, so a cold container
    restores the real universe before the narrow held-ticker update ever
    touches scores_daily.parquet."""
    calls = []
    from src.ui import bootstrap
    def _autoload():
        calls.append("restore")
        return {"state": "restored", "store": "github_release", "files": 6}
    monkeypatch.setattr(bootstrap, "autoload_state", _autoload)

    from src.data import ptj
    monkeypatch.setattr(ptj, "refresh_held_positions",
                        lambda: (calls.append("ptj") or [{"ticker": "OXY", "type": "STK"}]))
    monkeypatch.setattr(ptj, "ptj_status", lambda: "live")

    from src.data import panel_builder
    monkeypatch.setattr(panel_builder, "pull_tickers",
                        lambda tickers, **k: (calls.append("pull") or
                                              {"pulled": 1, "skipped_current": 0,
                                               "failed": [], "total_tickers": 1}))
    from src.scanner import score_runner
    monkeypatch.setattr(score_runner, "build_scores",
                        lambda only_tickers=None: calls.append("scores"))
    from src.data import drive_sync
    monkeypatch.setattr(drive_sync, "export_to_drive",
                        lambda *a, **k: (calls.append("export") or {"status": "ok"}))
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "publish_daily_outputs",
                        lambda names=None, **k: (calls.append("publish") or
                                                 {"ok": True, "written": len(names or ())}))

    result = rh.refresh_held()
    assert result["ok"] is True
    assert calls[0] == "restore", "state restore must run before PTJ/pull/scores/export"
    out = capsys.readouterr().out
    assert "restored from github_release" in out


def test_a_failed_restore_on_a_cold_container_is_warned_loudly(monkeypatch, capsys):
    """If the restore itself fails (both stores unreachable), that must not
    be swallowed -- the run proceeds (per existing behaviour: a degraded
    held-book refresh is still better than none), but the log must say,
    unambiguously, that daily_list may come out collapsed as a result."""
    from src.ui import bootstrap
    monkeypatch.setattr(bootstrap, "autoload_state",
                        lambda: {"state": "failed", "reason": "both stores unreachable"})

    from src.data import ptj
    monkeypatch.setattr(ptj, "refresh_held_positions",
                        lambda: [{"ticker": "OXY", "type": "STK"}])
    monkeypatch.setattr(ptj, "ptj_status", lambda: "live")
    from src.data import panel_builder
    monkeypatch.setattr(panel_builder, "pull_tickers",
                        lambda tickers, **k: {"pulled": 1, "skipped_current": 0,
                                              "failed": [], "total_tickers": 1})
    from src.scanner import score_runner
    monkeypatch.setattr(score_runner, "build_scores", lambda only_tickers=None: None)
    from src.data import drive_sync
    monkeypatch.setattr(drive_sync, "export_to_drive", lambda *a, **k: {"status": "ok"})
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "publish_daily_outputs",
                        lambda names=None, **k: {"ok": True, "written": len(names or ())})

    result = rh.refresh_held()
    assert result["ok"] is True  # degrades, does not abort
    out = capsys.readouterr().out
    assert "both stores unreachable" in out
    assert "collapse" in out
