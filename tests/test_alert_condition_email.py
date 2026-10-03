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


def _eval_result(**overrides):
    row = _row()
    shared = row["conditions"]["shared"]
    base = {"buy_met": True, "lit": ["minervini", "detect-lens"], "wrong_lit": [],
           "chased": False, "exit_warn": None, "exit_hit": None, "n_counting": 3,
           "n_lit": 2, "no_shared_buy": False,
           "shared_buy_detail": [(e, "TRUE") for e in shared["buy"]],
           "shared_confirm_detail": [(e, "TRUE") for e in shared["confirm"]]}
    base.update(overrides)
    return base


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
    for banned in ("buy now", "sell now", "position size", "enter now"):
        assert banned not in plain.lower()
        assert banned not in html.lower()


def test_each_committee_word_renders_as_a_labeled_scan_line():
    """PM ask (2026-10-03): simple labeled lines, not a flowing paragraph --
    'MA levels...met or bounced', 'Vwap...hit or not', 'Liquidity and
    volume...met or not with numbers'. Each shared word gets its own
    Category: VERDICT line."""
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())
    assert "Structure: MET — an hourly candle closes above pivot_high 62.15" in plain
    assert "Volume: MET — volume at least 1.4x normal for the time of day" in plain


def test_a_not_yet_word_renders_as_watching_not_false():
    """NOT_YET must never be reported as NOT MET -- the condition isn't
    failed, the data behind it just isn't ready yet (handoff §5/§9)."""
    row = _row()
    ev = _eval_result(buy_met=False,
                      shared_buy_detail=[(row["conditions"]["shared"]["buy"][0], "NOT_YET")])
    _, plain, _ = E.build_condition_state_body("HPE", row, ev, ["FAILED_PUSH"], _live())
    assert "Structure: WATCHING" in plain
    assert "Structure: NOT MET" not in plain


def test_bracket_line_shows_entry_stop_target_and_rr():
    row = _row()
    row["levels"] = {"stop": 60.00, "tp": [64.00, 68.00]}
    _, plain, _ = E.build_condition_state_body(
        "HPE", row, _eval_result(), ["CONDITION_MET"], _live())
    # entry 62.15, stop 60.00 -> risk 2.15; first target above entry is 64.00
    # -> reward 1.85 -> R:R 0.9.
    assert "Bracket: entry 62.15 · stop 60.00 · target 64.00 · R:R 0.9" in plain


def test_bracket_line_omitted_when_levels_are_missing():
    """Never a partial or fabricated bracket -- omitted entirely rather
    than showing entry with no stop/target."""
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())
    assert "Bracket:" not in plain


def test_entry_readiness_reports_a_state_never_an_instruction():
    """AQE makes no decisions (CLAUDE.md) -- this must read as a state
    (MET/WATCHING), never tell anyone to act."""
    _, plain_met, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(buy_met=True), ["CONDITION_MET"], _live())
    assert "Entry readiness: MET" in plain_met

    _, plain_watch, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(buy_met=False), ["FAILED_PUSH"], _live())
    assert "Entry readiness: WATCHING" in plain_watch
    for banned in ("enter now", "watch for entry", "buy now"):
        assert banned not in plain_watch.lower()


def test_entry_readiness_omitted_on_a_pure_exit_only_row():
    """A row with only `exits` and no shared buy / analysts is a HELD
    position with nothing prospective to enter -- 'Entry readiness:
    WATCHING' on an EXIT LINE notice would misname what's going on."""
    row = {"ticker": "PLTR",
          "conditions": {"shared": {"buy": [], "confirm": [], "chase": None},
                        "exits": [{"w": "close_below", "value": 162.0,
                                   "plain": "closes below the committee stop 162.00"}]}}
    ev = {"buy_met": False, "lit": [], "wrong_lit": [], "chased": False,
         "exit_warn": None,
         "exit_hit": {"w": "close_below", "value": 162.0,
                     "plain": "closes below the committee stop 162.00"},
         "n_counting": 0, "n_lit": 0, "no_shared_buy": False,
         "shared_buy_detail": [], "shared_confirm_detail": []}
    live = {"vol_x": {"so_far": 1.4}, "vwap": {"vwap": 165.3, "provisional": False},
           "last_hourly_close": 160.5}
    _, plain, _ = E.build_condition_state_body("PLTR", row, ev, ["EXIT_LINE_HELD"], live)
    assert "Entry readiness" not in plain
    assert "Exit line: closes below the committee stop 162.00." in plain


def test_entry_readiness_still_shows_when_a_buy_side_exists():
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())
    assert "Entry readiness: MET" in plain


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
