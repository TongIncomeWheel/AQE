"""Tests for src/alerts/condition_ledger.py (AQE handoff D123/R21,
2026-10-02 §7).
"""

from __future__ import annotations

from src.alerts import condition_ledger as L


def test_build_ledger_line_shape():
    eval_result = {"buy_met": True, "lit": ["minervini"], "wrong_lit": [],
                   "chased": False, "exit_warn": None, "exit_hit": None}
    line = L.build_ledger_line("HPE", eval_result, ["CONDITION_MET"],
                               vol_x={"so_far": 1.6}, legacy_vol_pace=1.1)
    assert line["ticker"] == "HPE"
    assert line["fired_states"] == ["CONDITION_MET"]
    assert line["buy_met"] is True
    assert line["vol_x"] == {"so_far": 1.6}
    assert line["legacy_vol_pace"] == 1.1


def test_append_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LEDGER_DIR", tmp_path)
    eval_result = {"buy_met": False, "lit": [], "wrong_lit": [], "chased": False,
                  "exit_warn": None, "exit_hit": None}
    L.append_line("2026-10-02", L.build_ledger_line("A", eval_result, []))
    L.append_line("2026-10-02", L.build_ledger_line("B", eval_result, ["CHASED"]))
    lines = L.load_lines("2026-10-02")
    assert len(lines) == 2
    assert {ln["ticker"] for ln in lines} == {"A", "B"}


def test_load_lines_empty_when_file_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LEDGER_DIR", tmp_path)
    assert L.load_lines("2026-10-02") == []


def test_load_lines_skips_a_corrupt_line(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LEDGER_DIR", tmp_path)
    (tmp_path / "2026-10-02.jsonl").write_text(
        '{"ticker": "A"}\nnot valid json\n{"ticker": "B"}\n', encoding="utf-8")
    lines = L.load_lines("2026-10-02")
    assert [ln["ticker"] for ln in lines] == ["A", "B"]


def test_write_summary_groups_states_by_ticker(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LEDGER_DIR", tmp_path)
    eval_result = {"buy_met": True, "lit": [], "wrong_lit": [], "chased": False,
                  "exit_warn": None, "exit_hit": None}
    L.append_line("2026-10-02", L.build_ledger_line("HPE", eval_result, ["CONDITION_MET"]))
    L.append_line("2026-10-02", L.build_ledger_line("HPE", eval_result, []))
    L.append_line("2026-10-02", L.build_ledger_line("ABBV", eval_result, ["CHASED"]))
    summary = L.write_summary("2026-10-02")
    assert summary["n_cycles_logged"] == 3
    assert summary["tickers"] == ["ABBV", "HPE"]
    assert summary["states_by_ticker"]["HPE"] == ["CONDITION_MET"]  # de-duplicated
    assert summary["condition_met_tickers"] == ["HPE"]


def test_write_summary_persists_to_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LEDGER_DIR", tmp_path)
    L.write_summary("2026-10-02", lines=[])
    assert (tmp_path / "2026-10-02.summary.json").exists()
