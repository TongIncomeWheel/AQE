"""Continuation pivot, extension bracket, and the rejected-by-gate summary (PM 2026-11-04). Data only; nothing replaces
pivot_high or bracket."""
from src.engines import bracket_engine as B
from src.engines import continuation as K


def _trend_then_coil():
    # 30 rising bars (range 1.0), then a 5-bar tight coil with an inside bar, atr ~1.0
    highs = [100 + i * 1.0 + 0.5 for i in range(30)]
    lows = [100 + i * 1.0 - 0.5 for i in range(30)]
    top = highs[-1]
    for hh, ll in ((top + 0.4, top - 0.4), (top + 0.3, top - 0.3), (top + 0.2, top - 0.2), (top + 0.35, top - 0.1), (top + 0.3, top - 0.05)):
        highs.append(hh); lows.append(ll)
    return highs, lows


def test_the_most_recent_tight_window_is_found():
    h, l = _trend_then_coil()
    c = K.continuation_pivot(h, l, 1.0)
    assert c and c["ended_bars_ago"] == 0 and 3 <= c["bars"] <= 10
    assert c["pivot"] == round(max(h[-c["bars"]:]), 2) and c["low"] == round(min(l[-c["bars"]:]), 2)


def test_no_window_in_a_straight_run_and_bad_input_is_none():
    h = [100 + i * 3.0 + 1 for i in range(40)]; l = [100 + i * 3.0 - 1 for i in range(40)]
    assert K.continuation_pivot(h, l, 1.0) is None            # every 3-bar window spans > 2.5 ATR
    assert K.continuation_pivot(h, l, None) is None
    assert K.continuation_pivot(h[:5], l[:5], 1.0) is None


def test_state_bands():
    assert K.state_vs_pivot(-0.1) == "BELOW" and K.state_vs_pivot(0) == "BUY_ZONE"
    assert K.state_vs_pivot(5.0) == "BUY_ZONE" and K.state_vs_pivot(5.01) == "EXTENDED" and K.state_vs_pivot(None) is None


def test_extension_bracket_is_labelled_gated_and_never_silently_absent():
    cont = {"pivot": 110.0, "low": 108.0, "bars": 5, "ended_bars_ago": 0}
    b = K.extension_bracket(110.5, 1.0, 90.0, 110.0, cont, "GREEN")
    assert b["available"] and "beside the structural bracket" in b["label"]
    assert b["stop"] == 108.0 or b["stop"] == round(110.5 - 1.0, 2) or b["stop"] <= 109.5   # lower of low and 1 ATR under
    assert b["stop"] == min(108.0, 109.5)
    assert [t["tp"] for t in b["targets"]] == ["TP1", "TP2"]
    assert b["targets"][1]["price"] == round(90 + 1.618 * 20, 2)
    assert set(b["gates"]) == {"atr_floor", "rr_min", "regime_ceiling"} and b["passed"] == all(b["gates"].values())
    for args, why in (((110.5, 1.0, None, None, cont, "GREEN"), "impulse"), ((110.5, 1.0, 90, 110, None, "GREEN"), "continuation"),
                      ((None, 1.0, 90, 110, cont, "GREEN"), "price")):
        r = K.extension_bracket(*args)
        assert r["available"] is False and why in r["reason"]
    # extensions below price -> unavailable, with the reason
    assert "not above price" in K.extension_bracket(200.0, 1.0, 90.0, 110.0, cont, "GREEN")["reason"]


def test_rejected_by_gate_names_the_gate_and_flags_an_unreachable_tp2():
    lv = {"atr14": 1.0, "fib": {"retracements": {"0.618": 95.0, "0.786": 97.0}, "swing_low": 90},
          "swing_lows": [], "resistance": [{"price": 101.0, "date": "2026-01-01"}, {"price": 101.5, "date": "2026-01-02"}]}
    b = B.compute_bracket(lv, {20: 98.5}, "GREEN", 100.0)
    g = b["rejected_by_gate"]
    assert b["valid"] is False and g["tp2_too_near"] is True and g["tp2_reach_atr"] == 1.5
    assert g["fail_rr_min"] == g["n_candidates"] and g["passed_all"] == 0
