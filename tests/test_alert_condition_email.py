"""Tests for the condition state-change email (AQE handoff D123/R21,
2026-10-02 §6) -- src/alerts/emailer.py's build_condition_state_body()/
send_condition_state_email().
"""

from __future__ import annotations

from src.alerts import emailer as E


def _row():
    return {
        "ticker": "HPE",
        "conditions": {
            "shared": {
                "buy": [{"w": "h1_close_above", "level": 62.15,
                        "plain": "an hourly candle closes above pivot_high 62.15"}],
                "confirm": [{"w": "vol_x_ge", "x": 1.4,
                            "plain": "volume at least 1.4x normal for the time of day"}],
                "chase": {"w": "close_above", "level": 65.26,
                         "plain": "closes above pivot_high+5pct 65.26"},
            },
            "exits": [],
        },
    }


def _eval_result():
    return {"buy_met": True, "lit": ["minervini", "detect-lens"], "wrong_lit": [],
           "chased": False, "exit_warn": None, "exit_hit": None, "n_counting": 3}


def _live():
    return {"vol_x": {"so_far": 1.6}, "vwap": {"vwap": 63.80, "provisional": False},
           "last_hourly_close": 64.20}


def test_build_condition_state_body_includes_ticker_and_state():
    subject, plain, html = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())
    assert "HPE" in subject
    assert "CONDITION MET" in plain
    assert "CONDITION MET" in html


def test_build_condition_state_body_shows_analyst_count():
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())
    assert "2 of 3 analysts" in plain


def test_build_condition_state_body_includes_committee_plain_text():
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())
    assert "pivot_high 62.15" in plain
    assert "1.4x normal" in plain


def test_build_condition_state_body_includes_volume_and_vwap():
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())
    assert "1.6" in plain and "normal" in plain.lower()
    assert "63.8" in plain
    assert "Above" in plain


def test_build_condition_state_body_includes_chase_line():
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())
    assert "65.26" in plain


def test_build_condition_state_body_never_renders_a_sizing_claim():
    _, plain, html = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())
    assert "placed, changed, cancelled or sized" in plain.lower()
    for banned in ("buy now", "sell now", "position size"):
        assert banned not in plain.lower()
        assert banned not in html.lower()


def test_failed_push_and_exit_line_labels_render():
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["FAILED_PUSH"], _live())
    assert "FAILED PUSH" in plain
    _, plain2, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["EXIT_LINE_HELD"], _live())
    assert "EXIT LINE" in plain2


def test_send_condition_state_email_no_backend_configured(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("AQE_SMTP_PASSWORD", raising=False)
    res = E.send_condition_state_email("HPE", _row(), _eval_result(),
                                       ["CONDITION_MET"], _live())
    assert res["ok"] is False
