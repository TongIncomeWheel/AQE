"""Snapshot restore-scope tests.

A snapshot restore OVERWRITES. That is correct after a container recycle,
where there is nothing to lose, and wrong mid-session, where it silently rolls
freshly-pulled bars back to whenever the zip was written and forces a re-pull
nobody asked for. These tests pin both behaviours.
"""

from __future__ import annotations

import pytest

from src.data import persist as P


@pytest.fixture
def snap(tmp_path, monkeypatch):
    data, out = tmp_path / "data", tmp_path / "output"
    data.mkdir()
    out.mkdir()
    monkeypatch.setattr(P, "DATA_DIR", data)
    monkeypatch.setattr(P, "OUTPUT_DIR", out)
    (data / "panel_daily.parquet").write_bytes(b"OLD-PANEL")
    (data / "scores_daily.parquet").write_bytes(b"OLD-SCORES")
    (data / "ma_panel.parquet").write_bytes(b"OLD-MA")
    (data / "aqe.db").write_bytes(b"OLD-DB")
    (data / "universe.txt").write_text("# AQE Universe — updated 2026-05-28\n\nOLD\n")
    (out / "qs_daily.json").write_text('{"date":"old"}')
    built = P.build_snapshot_bytes()
    assert built["ok"]
    return {"blob": built["blob"], "data": data, "out": out}


def test_snapshot_captures_the_qs_artifacts(snap):
    """QS memory (aqe.db) and its daily artifact must both ride the snapshot."""
    arcs = [arc for _, arc in P._members()]
    assert "data/aqe.db" in arcs
    assert "output/qs_daily.json" in arcs
    assert "data/universe.txt" in arcs


def test_full_restore_brings_everything_back(snap):
    """The post-recycle case — nothing on disk is worth keeping."""
    res = P.restore_snapshot_bytes(snap["blob"])
    assert res["ok"] and res["count"] >= 6
    assert (snap["data"] / "aqe.db").read_bytes() == b"OLD-DB"
    assert (snap["out"] / "qs_daily.json").exists()


def test_scoped_restore_leaves_fresher_files_alone(snap):
    """The mid-session case, and the one that silently costs a re-pull.

    The MA scan wants ma_panel back. It must not also roll panel_daily,
    scores_daily and universe.txt back to snapshot time — the pipeline has run
    since, and those bars would have to be pulled again.
    """
    data = snap["data"]
    data.joinpath("panel_daily.parquet").write_bytes(b"FRESH-PANEL")
    data.joinpath("scores_daily.parquet").write_bytes(b"FRESH-SCORES")
    data.joinpath("universe.txt").write_text("# AQE Universe — updated 2026-08-04\n\nNEW\n")

    res = P.restore_snapshot_bytes(snap["blob"], only=["ma_panel.parquet"])
    assert res["ok"]
    assert res["files"] == ["data/ma_panel.parquet"]
    assert data.joinpath("panel_daily.parquet").read_bytes() == b"FRESH-PANEL"
    assert data.joinpath("scores_daily.parquet").read_bytes() == b"FRESH-SCORES"
    assert "2026-08-04" in data.joinpath("universe.txt").read_text()
    assert data.joinpath("ma_panel.parquet").read_bytes() == b"OLD-MA"


def test_scoped_restore_reports_what_it_skipped(snap):
    res = P.restore_snapshot_bytes(snap["blob"], only=["ma_panel.parquet"])
    assert len(res["skipped"]) >= 4


def test_scope_matching_no_member_fails_loudly(snap):
    res = P.restore_snapshot_bytes(snap["blob"], only=["nothing_here.parquet"])
    assert res["ok"] is False
    assert "no member matched" in res["reason"]


def test_the_ma_scan_restores_only_its_own_state():
    """Guard the call site, not just the capability."""
    import inspect

    from src.ui import daily_job
    src = inspect.getsource(daily_job)
    idx = src.index("MA scan starting")
    window = src[idx:idx + 1200]
    assert "load_snapshot(only=" in window, \
        "the MA scan must scope its restore, or it rolls back the daily pull"
    assert "ma_panel.parquet" in window
