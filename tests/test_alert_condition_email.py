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
    assert "BUY CONDITIONS MET" in plain
    assert "BUY CONDITIONS MET" in html


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
    assert "Structure: ✓ MET — an hourly candle closes above pivot_high 62.15" in plain
    assert "Volume: ✓ MET — volume at least 1.4x normal for the time of day" in plain


def test_a_not_yet_word_renders_as_watching_not_false():
    """NOT_YET must never be reported as NOT MET -- the condition isn't
    failed, the data behind it just isn't ready yet (handoff §5/§9)."""
    row = _row()
    ev = _eval_result(buy_met=False,
                      shared_buy_detail=[(row["conditions"]["shared"]["buy"][0], "NOT_YET")])
    _, plain, _ = E.build_condition_state_body("HPE", row, ev, ["FAILED_PUSH"], _live())
    assert "Structure: ◌ WATCHING" in plain
    assert "✗ NOT MET" not in plain


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
    assert "Entry readiness: ✓ MET" in plain_met

    _, plain_watch, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(buy_met=False), ["FAILED_PUSH"], _live())
    assert "Entry readiness: ◌ WATCHING" in plain_watch
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
    assert ("Exit line: closes below the committee stop 162.00 — DAILY close below it "
            "(confirmed).") in plain


def test_exit_line_card_says_hourly_vs_daily_in_words():
    """Only a HELD position's exit line is a card (PM 2026-10-03: "why
    would I care about an exit I don't own?"). Hourly-vs-daily close is
    stated in words on the body line and the summary."""
    row = {"ticker": "PLTR",
          "conditions": {"shared": {"buy": [], "confirm": [], "chase": None},
                        "exits": [{"w": "close_below", "value": 162.0,
                                   "plain": "closes below the committee stop 162.00"}]}}
    ex = {"w": "close_below", "value": 162.0,
         "plain": "closes below the committee stop 162.00"}
    base = {"buy_met": False, "lit": [], "wrong_lit": [], "chased": False,
           "n_counting": 0, "n_lit": 0, "no_shared_buy": False,
           "shared_buy_detail": [], "shared_confirm_detail": []}
    live = {"vol_x": {"so_far": 1.4}, "vwap": {"vwap": 165.3, "provisional": False},
           "last_hourly_close": 161.2}

    held_warn = dict(base, exit_warn=ex, exit_hit=None)
    _, plain, _ = E.build_condition_state_body("PLTR", row, held_warn, ["EXIT_LINE_HELD"], live)
    assert "EXIT LINE CROSSED — HELD POSITION" in plain
    assert "hourly close below it, not yet a daily close" in plain
    assert "A position you hold: an hourly close so far below the committee exit line 162.00." in plain

    held_hit = dict(base, exit_warn=None, exit_hit=ex)
    _, plain2, _ = E.build_condition_state_body("PLTR", row, held_hit, ["EXIT_LINE_HELD"], live)
    assert "DAILY close below it (confirmed)" in plain2
    assert "EXIT_LINE_WARN" not in E._CONDITION_STATE_LABEL   # never a card


def test_analysts_line_marks_lit_seats_with_a_tick_and_invalidated_with_a_cross():
    """PM 2026-10-03: an analyst failing is not an alert, it's a ✗ on the
    seat inside whichever card the name earns."""
    ev = _eval_result(buy_met=False, lit=["seow"], wrong_lit=["raschke"],
                      analyst_detail={"seow": {"counts": True}, "raschke": {"counts": True},
                                      "weis": {"counts": True}})
    _, plain, _ = E.build_condition_state_body("DKNG", _row(), ev, ["FAILED_PUSH"], _live())
    assert "Analysts: ✓ seow · ✗ raschke (invalidated) · ◌ weis" in plain
    assert "ANALYST INVALIDATED" not in plain


def test_each_voice_gets_its_own_criteria_line_with_marks():
    """PM 2026-10-03: PMA logs what each voice is looking for; AQE marks
    each word pass/fail on the card. Seat words have no `plain`, so the
    text comes from AQE's own vocabulary reading, never a raw word name."""
    row = _row()
    row["conditions"]["analysts"] = [
        {"seat": "minervini", "conviction": 3, "counts": True},
        {"seat": "detect-lens", "conviction": 4, "counts": True},
    ]
    detail = {
        "minervini": {"counts": True,
                      "buy": [({"w": "h1_close_above", "levels": [62.15]}, "TRUE")],
                      "confirm": [({"w": "vol_x_ge", "x": 1.4}, "FALSE")],
                      "wrong": [({"w": "close_below", "levels": [60.0]}, "NOT_YET")]},
        "detect-lens": {"counts": True,
                        "buy": [({"w": "rs_today_gt_spy"}, "TRUE"),
                                ({"w": "above_vwap_s"}, "TRUE")],
                        "confirm": [({"w": "vol_x_ge", "x": 1.0}, "TRUE")],
                        "wrong": [({"w": "choch_bearish"}, "NOT_YET")]},
    }
    ev = _eval_result(buy_met=False, lit=["detect-lens"], analyst_detail=detail)
    _, plain, _ = E.build_condition_state_body("HPE", row, ev, ["FAILED_PUSH"], _live())
    # highest conviction first
    assert ("  ✓ detect-lens (4) — buy ✓ outperforming SPY today, ✓ holds above today's VWAP"
            " · confirm ✓ volume ≥1× normal for the time of day"
            " · wrong ◌ bearish CHoCH on the daily (COB)") in plain
    assert ("  ◌ minervini (3) — buy ✓ hourly close above 62.15"
            " · confirm ✗ volume ≥1.4× normal for the time of day"
            " · wrong ◌ daily close below 60.00") in plain
    assert "h1_close_above" not in plain and "vol_x_ge" not in plain


def test_voice_lines_are_capped_and_the_rest_folded(monkeypatch):
    from src.alerts import config as C
    monkeypatch.setattr(C, "CONDITION_CARD_MAX_SEATS", 1)
    row = _row()
    row["conditions"]["analysts"] = [{"seat": "a", "conviction": 5, "counts": True},
                                     {"seat": "b", "conviction": 2, "counts": True},
                                     {"seat": "c", "conviction": 1, "counts": True}]
    detail = {s: {"counts": True, "buy": [({"w": "above_vwap_s"}, "TRUE")],
                  "confirm": [], "wrong": []} for s in ("a", "b", "c")}
    ev = _eval_result(lit=["a", "b"], wrong_lit=["c"], analyst_detail=detail)
    _, plain, _ = E.build_condition_state_body("HPE", row, ev, ["CONDITION_MET"], _live())
    assert "  ✓ a (5) — buy ✓ holds above today's VWAP" in plain
    assert "  +2 more: ✓ b · ✗ c" in plain
    assert "b (2)" not in plain


def test_card_summary_one_liner_sits_under_the_headline():
    """PM 2026-10-03: the one-liner under each example card read clearer
    than the card -- so the card now opens with one, built from its own
    numbers."""
    row = _row()
    ev = _eval_result(buy_met=False,
                      shared_confirm_detail=[(row["conditions"]["shared"]["confirm"][0], "FALSE")])
    _, plain, _ = E.build_condition_state_body("HPE", row, ev, ["FAILED_PUSH"], _live())
    assert plain.splitlines()[1] == (
        "Cleared 62.15, then an hourly close back under — Volume confirm never came. "
        "Still watched: it re-qualifies on the next hourly close back above 62.15.")
    _, plain_met, _ = E.build_condition_state_body(
        "HPE", row, _eval_result(), ["CONDITION_MET"], _live())
    assert plain_met.splitlines()[1] == "All buy conditions met — 2 of 3 analyst seats lit."


def test_digest_stacks_every_card_under_one_subject_and_one_footer():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime(2026, 10, 2, 14, 30, tzinfo=ZoneInfo("America/New_York"))
    row2 = dict(_row(), ticker="DELL")
    cards = [("HPE", _row(), _eval_result(), ["CONDITION_MET"], _live()),
             ("DELL", row2, _eval_result(buy_met=False), ["FAILED_PUSH"], _live())]
    subject, plain, html = E.build_condition_digest(cards, now)
    assert subject == "[AQE] 14:30 ET conditions · 2 cards · BUY MET 1 · BACK UNDER 1"
    assert "HPE ·" in plain and "DELL ·" in plain
    assert plain.count("Information only.") == 1
    assert html.count("Information only.") == 1
    assert "14:30 ET · 2 names changed state this cycle" in plain


def test_chased_label_reads_as_extended_past_the_chase_line():
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(chased=True), ["CHASED"], _live())
    assert "EXTENDED — past the chase line" in plain


def test_entry_readiness_still_shows_when_a_buy_side_exists():
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())
    assert "Entry readiness: ✓ MET" in plain


def test_failed_push_and_exit_line_labels_render():
    _, plain, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["FAILED_PUSH"], _live())
    assert "BACK UNDER THE LEVEL — breakout didn't hold" in plain
    _, plain2, _ = E.build_condition_state_body(
        "HPE", _row(), _eval_result(), ["EXIT_LINE_HELD"], _live())
    assert "EXIT LINE CROSSED — HELD POSITION" in plain2


def test_send_condition_digest_no_backend_configured(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("AQE_SMTP_PASSWORD", raising=False)
    res = E.send_condition_digest(
        [("HPE", _row(), _eval_result(), ["CONDITION_MET"], _live())],
        datetime(2026, 10, 2, 14, 30, tzinfo=ZoneInfo("America/New_York")))
    assert res["ok"] is False
