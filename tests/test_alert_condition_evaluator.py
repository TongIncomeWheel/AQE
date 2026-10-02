"""Tests for src/alerts/condition_evaluator.py (AQE handoff D123/R21,
2026-10-02 §5/§9).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.alerts import condition_evaluator as E

_ET = ZoneInfo("America/New_York")


def _ctx(**overrides) -> dict:
    base = {"price": 100.0, "day_high": 101.0, "day_low": 98.0, "open": 99.0,
           "last_hourly_close": 100.0, "hourly_closes": [99.5, 100.0],
           "vwap": {"vwap": 99.8, "provisional": False}, "vol_x": {"so_far": 1.2},
           "rs_today": 1.0, "atr": 2.0, "is_final_cycle": False, "cob": {}}
    base.update(overrides)
    return base


# ------------------------------------------------------------- evaluate_word


def test_unknown_word_returns_unknown_word():
    assert E.evaluate_word({"w": "not_a_real_word"}, _ctx()) == "UNKNOWN_WORD"


def test_close_above_not_yet_before_final_cycle():
    out = E.evaluate_word({"w": "close_above", "level": 99.0}, _ctx(is_final_cycle=False))
    assert out == "NOT_YET"


def test_close_above_true_at_final_cycle():
    out = E.evaluate_word({"w": "close_above", "level": 99.0}, _ctx(is_final_cycle=True))
    assert out == "TRUE"


def test_close_below_false_at_final_cycle_when_price_above():
    out = E.evaluate_word({"w": "close_below", "level": 99.0}, _ctx(is_final_cycle=True))
    assert out == "FALSE"


def test_h1_close_above_true():
    out = E.evaluate_word({"w": "h1_close_above", "level": 99.5},
                          _ctx(last_hourly_close=100.0))
    assert out == "TRUE"


def test_h1_close_above_not_yet_without_hourly_close():
    out = E.evaluate_word({"w": "h1_close_above", "level": 99.5},
                          _ctx(last_hourly_close=None))
    assert out == "NOT_YET"


def test_trade_above_is_info_based_on_day_high():
    assert E.evaluate_word({"w": "trade_above", "level": 100.5},
                           _ctx(day_high=101.0)) == "TRUE"
    assert E.evaluate_word({"w": "trade_above", "level": 101.5},
                           _ctx(day_high=101.0)) == "FALSE"


def test_reclaim_true_when_dipped_below_then_closed_above():
    out = E.evaluate_word({"w": "reclaim", "level": 99.0},
                          _ctx(day_low=98.0, last_hourly_close=99.5))
    assert out == "TRUE"


def test_reject_true_when_poked_above_then_closed_below():
    out = E.evaluate_word({"w": "reject", "level": 100.0},
                          _ctx(day_high=101.0, last_hourly_close=99.0))
    assert out == "TRUE"


def test_in_zone_true_near_price():
    out = E.evaluate_word({"w": "in_zone", "level": 100.3},
                          _ctx(price=100.0, atr=2.0))  # within 0.25*ATR = 0.5
    assert out == "TRUE"


def test_in_zone_false_far_from_price():
    # Literal spec: "abs(price-L) <= 0.25*ATR, or day_low <= L + 0.25*ATR" --
    # the day_low leg only meaningfully gates for a level AT OR BELOW the
    # day's low (a support test); a level far ABOVE the day's low trivially
    # satisfies "day_low <= L + buffer" for any L above the low, so a
    # meaningful "far" case needs L below the low instead.
    out = E.evaluate_word({"w": "in_zone", "level": 50.0}, _ctx(price=100.0, day_low=98.0, atr=2.0))
    assert out == "FALSE"


def test_vol_x_ge_true_above_threshold():
    out = E.evaluate_word({"w": "vol_x_ge", "x": 1.0}, _ctx(vol_x={"so_far": 1.2}))
    assert out == "TRUE"


def test_vol_x_ge_not_yet_without_profile():
    out = E.evaluate_word({"w": "vol_x_ge", "x": 1.0}, _ctx(vol_x={"so_far": None}))
    assert out == "NOT_YET"


def test_above_vwap_s_not_yet_while_provisional():
    out = E.evaluate_word({"w": "above_vwap_s"},
                          _ctx(vwap={"vwap": 99.0, "provisional": True}))
    assert out == "NOT_YET"


def test_above_vwap_s_true_when_confirmed_and_above():
    out = E.evaluate_word({"w": "above_vwap_s"},
                          _ctx(last_hourly_close=100.0,
                              vwap={"vwap": 99.0, "provisional": False}))
    assert out == "TRUE"


def test_below_vwap_s_requires_n_consecutive_hours_under():
    entry = {"w": "below_vwap_s", "x": 2}
    ok = E.evaluate_word(entry, _ctx(hourly_closes=[98.0, 98.5],
                                     vwap={"vwap": 99.0, "provisional": False}))
    assert ok == "TRUE"
    not_enough = E.evaluate_word(entry, _ctx(hourly_closes=[98.5],
                                             vwap={"vwap": 99.0, "provisional": False}))
    assert not_enough == "NOT_YET"


def test_rs_today_gt_spy():
    assert E.evaluate_word({"w": "rs_today_gt_spy"}, _ctx(rs_today=0.5)) == "TRUE"
    assert E.evaluate_word({"w": "rs_today_gt_spy"}, _ctx(rs_today=-0.5)) == "FALSE"


def test_fade_atr_ge():
    # day_high 101, price 99, atr 2 -> fade = (101-99)/2 = 1.0
    out = E.evaluate_word({"w": "fade_atr_ge", "x": 1.0},
                          _ctx(day_high=101.0, price=99.0, atr=2.0))
    assert out == "TRUE"


def test_clv_not_yet_before_final_cycle():
    out = E.evaluate_word({"w": "clv_ge", "x": 0.5}, _ctx(is_final_cycle=False))
    assert out == "NOT_YET"


def test_clv_ge_true_at_final_cycle():
    # price 100, low 98, high 101 -> clv = 2/3 = 0.667
    out = E.evaluate_word({"w": "clv_ge", "x": 0.5},
                          _ctx(is_final_cycle=True, price=100.0, day_high=101.0, day_low=98.0))
    assert out == "TRUE"


def test_red_bar_not_yet_before_final_cycle():
    assert E.evaluate_word({"w": "red_bar"}, _ctx(is_final_cycle=False)) == "NOT_YET"


def test_red_bar_true_when_price_below_open_at_final():
    out = E.evaluate_word({"w": "red_bar"}, _ctx(is_final_cycle=True, price=98.0, open=99.0))
    assert out == "TRUE"


def test_cob_word_reported_as_given():
    assert E.evaluate_word({"w": "elder_5d"}, _ctx(cob={"elder_5d": True})) == "TRUE"
    assert E.evaluate_word({"w": "ma_above"}, _ctx(cob={"ma_above": False})) == "FALSE"


def test_cob_word_not_yet_when_absent():
    assert E.evaluate_word({"w": "choch_bearish"}, _ctx(cob={})) == "NOT_YET"


# ------------------------------------------------------- evaluate_conditions


def test_evaluate_conditions_returns_none_without_conditions_block():
    """§9 back-compat: a row with no `conditions` behaves exactly as
    today -- the evaluator must not invent anything."""
    row = {"ticker": "X", "triggers": []}
    assert E.evaluate_conditions(row, _ctx(), datetime(2026, 10, 2, 11, 0, tzinfo=_ET)) is None


def _row_with_conditions(**overrides) -> dict:
    row = {
        "ticker": "HPE",
        "conditions": {
            "shared": {
                "buy": [{"w": "h1_close_above", "level": 62.15, "seats": ["minervini"]}],
                "confirm": [{"w": "vol_x_ge", "x": 1.4, "seats": ["minervini"]}],
                "no_shared_buy": False,
                "chase": {"w": "close_above", "level": 70.0},
            },
            "exits": [{"w": "close_below", "value": 60.0, "seats": ["minervini"]}],
            "analysts": [
                {"seat": "minervini", "vote": "SUPPORT", "counts": True,
                 "buy": [{"w": "h1_close_above", "level": 62.15}],
                 "confirm": [{"w": "vol_x_ge", "x": 1.4}],
                 "wrong": [{"w": "fade_atr_ge", "x": 1.0}]},
            ],
        },
    }
    row["conditions"].update(overrides)
    return row


def test_buy_met_true_when_shared_buy_and_confirm_both_true():
    row = _row_with_conditions()
    live = _ctx(last_hourly_close=63.0, vol_x={"so_far": 1.6})
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    assert out["buy_met"] is True
    assert out["lit"] == ["minervini"]


def test_buy_met_false_when_confirm_not_met():
    row = _row_with_conditions()
    live = _ctx(last_hourly_close=63.0, vol_x={"so_far": 0.8})  # confirm fails
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    assert out["buy_met"] is False


def test_wrong_lit_removes_a_supporter_from_lit():
    row = _row_with_conditions()
    live = _ctx(last_hourly_close=63.0, vol_x={"so_far": 1.6},
               day_high=65.0, price=62.5, atr=2.0)  # fade = (65-62.5)/2 = 1.25 >= 1.0
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    assert "minervini" in out["wrong_lit"]
    assert "minervini" not in out["lit"]


def test_chased_true_when_chase_word_fires_at_final_cycle():
    row = _row_with_conditions()
    live = _ctx(price=71.0, is_final_cycle=True)
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 15, 50, tzinfo=_ET))
    assert out["chased"] is True


def test_exit_warn_on_hourly_close_below_exit_level():
    row = _row_with_conditions()
    live = _ctx(last_hourly_close=59.0)
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    assert out["exit_warn"] is not None
    assert out["exit_hit"] is None  # not final cycle yet


def test_exit_hit_only_at_final_cycle_on_daily_close():
    row = _row_with_conditions()
    live = _ctx(price=59.0, is_final_cycle=True)
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 15, 50, tzinfo=_ET))
    assert out["exit_hit"] is not None


def test_no_shared_buy_counts_majority_of_analysts():
    row = _row_with_conditions(no_shared_buy=True)
    row["conditions"]["analysts"].append(
        {"seat": "livermore", "vote": "SUPPORT", "counts": True,
         "buy": [{"w": "h1_close_above", "level": 62.15}], "confirm": [], "wrong": []})
    live = _ctx(last_hourly_close=63.0, vol_x={"so_far": 1.6})
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    # both analysts' own buy+confirm all true -> 2 of 2 lit -> majority -> buy_met
    assert out["buy_met"] is True


def test_advisory_supporter_never_counted():
    """R14: counts=False marks an advisory supporter -- shown, never
    counted in lit/wrong_lit or the denominator."""
    row = _row_with_conditions()
    row["conditions"]["analysts"].append(
        {"seat": "advisory_seat", "vote": "SUPPORT", "counts": False,
         "buy": [{"w": "h1_close_above", "level": 62.15}], "confirm": [], "wrong": []})
    live = _ctx(last_hourly_close=63.0, vol_x={"so_far": 1.6})
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    assert "advisory_seat" not in out["lit"]
    assert out["n_counting"] == 1


def test_unknown_word_is_collected_for_logging():
    row = _row_with_conditions()
    row["conditions"]["shared"]["confirm"] = [{"w": "totally_made_up_word", "x": 1.0}]
    live = _ctx(last_hourly_close=63.0)
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    assert "totally_made_up_word" in out["unknown_words"]


def test_unknown_word_never_completes_a_buy():
    row = _row_with_conditions()
    row["conditions"]["shared"]["confirm"] = [{"w": "totally_made_up_word", "x": 1.0}]
    row["conditions"]["analysts"][0]["confirm"] = [{"w": "totally_made_up_word", "x": 1.0}]
    live = _ctx(last_hourly_close=63.0)
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    assert out["buy_met"] is False
    assert out["lit"] == []


# ------------------------------------------------------------- §9 acceptance
# "The HPE 2026-09-30 bars... above the 62.15 pivot every hour, but
# above_vwap_s FALSE in 6 of 7 hours, and fade_atr_ge:1 almost true (a 0.90
# ATR fade). So no CONDITION MET is emitted on a rule that requires
# above_vwap_s." The real PMA run-folder bars aren't available in this
# session; this reconstructs the SAME invariant synthetically: pivot
# cleared, VWAP not reclaimed, a near-miss (not fired) ATR fade.


def test_hpe_like_scenario_above_vwap_s_blocks_buy_met_despite_pivot_cleared():
    row = {
        "ticker": "HPE",
        "conditions": {
            "shared": {
                "buy": [{"w": "h1_close_above", "level": 62.15}],
                "confirm": [{"w": "above_vwap_s"}],
                "no_shared_buy": False,
            },
            "exits": [],
            "analysts": [
                {"seat": "minervini", "counts": True,
                 "buy": [{"w": "h1_close_above", "level": 62.15}],
                 "confirm": [{"w": "above_vwap_s"}],
                 "wrong": [{"w": "fade_atr_ge", "x": 1.0}]},
            ],
        },
    }
    # Pivot cleared (last hourly close well above 62.15), but the close
    # sits BELOW session VWAP (63.80) -- above_vwap_s is FALSE, not TRUE.
    # Fade is 0.90 ATR -- "almost" 1.0 but genuinely under it: FALSE, not
    # wrong_lit.
    live = _ctx(last_hourly_close=64.20, day_high=65.00, price=64.20, atr=2.0,
               vwap={"vwap": 65.50, "provisional": False})  # h1 close UNDER vwap
    out = E.evaluate_conditions(row, live, datetime(2026, 9, 30, 11, 30, tzinfo=_ET))
    assert out["buy_met"] is False
    assert out["lit"] == []
    assert out["wrong_lit"] == []  # the fade didn't actually clear 1.0 ATR


def test_not_yet_never_fires_a_state():
    """A buy rule needing a word that reads NOT_YET must never read as
    TRUE -- _all_true() already treats anything but TRUE as failing, this
    locks that behaviour in explicitly for NOT_YET specifically."""
    row = _row_with_conditions()
    row["conditions"]["shared"]["confirm"] = [{"w": "vol_x_ge", "x": 1.4}]
    live = _ctx(last_hourly_close=63.0, vol_x={"so_far": None})  # NOT_YET
    out = E.evaluate_conditions(row, live, datetime(2026, 10, 2, 11, 0, tzinfo=_ET))
    assert out["buy_met"] is False
