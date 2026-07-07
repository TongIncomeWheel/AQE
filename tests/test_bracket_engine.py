"""Unit tests for the Bracketing Engine — the single source of truth for brackets.

Synthetic level bundles with known geometry so the expected stop / targets / R:R /
validity are hand-computable. No FMP, no parquets.
"""
from __future__ import annotations

from src.engines import bracket_engine as be


def _levels(atr=2.0, swing_low=92.0, swing_lows=None, rets=None, exts=None,
            resistance=None, swing_high=None):
    """Build a structural levels bundle like levels.levels_for_ticker() emits."""
    return {
        "atr14": atr,
        "fib": {
            "swing_low": swing_low,
            "swing_high": swing_high,
            "retracements": ({"0.618": 96.0, "0.786": 93.0}
                             if rets is None else rets),
            "extensions": exts if exts is not None else {},
        },
        "swing_lows": swing_lows if swing_lows is not None else [
            {"price": 97.0}, {"price": 94.0}, {"price": 90.0}],
        "resistance": resistance if resistance is not None else [
            {"price": 108.0}, {"price": 112.0}],
    }


MA = {20: 98.0, 50: 95.0, 100: 90.0, 200: 85.0}


# ---------------------------------------------------------------------------
def test_valid_bracket_picks_tightest_valid_stop():
    b = be.compute_bracket(_levels(), MA, "GREEN", price=100.0)
    assert b["valid"] is True
    # Candidates valid at price 100, atr 2, TP2=112: ma20(98), fib_618(96),
    # swing_low_1(97), swing_low_2(94), ma50(95). Tightest (highest) = ma20 @ 98.
    assert b["stop"] == 98.0
    assert b["stop_type"] == "ma20"
    assert b["risk"] == 2.0
    assert b["stop_atr_dist"] == 1.0            # 2 / 2 ATR — ATR-relative (item 6)
    assert b["rr"] == 6.0                        # (112-100)/2
    assert b["price_source"] == "eod_close"
    assert b["invalid_reason"] is None


def test_targets_nearest_first_with_r_and_atr_dist():
    b = be.compute_bracket(_levels(), MA, "GREEN", price=100.0)
    tps = b["targets"]
    assert [t["price"] for t in tps] == [108.0, 112.0]      # nearest-first
    assert tps[0]["r"] == 4.0 and tps[1]["r"] == 6.0        # (p-100)/risk(2)
    assert tps[0]["atr_dist"] == 4.0 and tps[1]["atr_dist"] == 6.0


def test_no_resistance_above_price_is_unbracketable():
    lv = _levels(resistance=[], exts={})       # nothing above
    b = be.compute_bracket(lv, MA, "GREEN", price=100.0)
    assert b["valid"] is False
    assert "no structural resistance above price" in b["invalid_reason"]


def test_no_support_passes_gates_is_unbracketable():
    # Resistance very close → R:R to TP2 can't reach 2.0 for any support.
    lv = _levels(resistance=[{"price": 101.0}, {"price": 102.0}],
                 swing_lows=[{"price": 99.5}], rets={"0.618": 99.0}, swing_low=99.0)
    b = be.compute_bracket(lv, {20: 99.8}, "GREEN", price=100.0)
    assert b["valid"] is False
    assert "no structural support passes the 3 gates" in b["invalid_reason"]
    # targets still surfaced for context, with atr_dist
    assert b["targets"] and b["targets"][0]["atr_dist"] is not None


def test_missing_price_or_atr_degrades_cleanly():
    b = be.compute_bracket(_levels(atr=0.0), MA, "GREEN", price=100.0)
    assert b["valid"] is False and "missing price/ATR" in b["invalid_reason"]
    b2 = be.compute_bracket(_levels(), MA, "GREEN", price=0.0)
    assert b2["valid"] is False


def test_price_source_reprices_rr():
    """Same fixed levels, different price → different risk + R:R (the daily-EOD vs
    live-15min distinction)."""
    lv = _levels()
    eod = be.compute_bracket(lv, MA, "GREEN", price=100.0, price_source="eod_close")
    live = be.compute_bracket(lv, MA, "GREEN", price=101.0, price_source="live_15min")
    assert eod["price"] == 100.0 and live["price"] == 101.0
    assert live["price_source"] == "live_15min"
    # Levels are identical; only the reference price moved → risk/rr differ.
    assert live["risk"] != eod["risk"] or live["rr"] != eod["rr"]


def test_regime_ceiling_tightens_validity():
    # A 10%-risk stop with rr≥2: valid under GREEN(12%), invalid under RED(4%).
    lv = _levels(resistance=[{"price": 125.0}], swing_lows=[{"price": 90.0}],
                 rets={}, swing_low=None)
    green = be.compute_bracket(lv, {}, "GREEN", price=100.0)
    red = be.compute_bracket(lv, {}, "RED", price=100.0)
    assert green["valid"] is True and green["stop"] == 90.0
    assert green["risk_pct"] == 10.0
    assert red["valid"] is False               # 10% > RED ceiling 4%
    assert green["regime_ceiling_pct"] == 12.0 and red["regime_ceiling_pct"] == 4.0


def test_dedup_first_label_wins():
    # swing_low_1 and fib_618 at the SAME price → one candidate, swing label first.
    lv = _levels(swing_lows=[{"price": 96.0}], rets={"0.618": 96.0})
    b = be.compute_bracket(lv, MA, "GREEN", price=100.0)
    at96 = [c for c in b["candidates"] if c["price"] == 96.0]
    assert len(at96) == 1 and at96[0]["type"] == "swing_low_1"


def test_no_mechanical_dsl_stop_candidate():
    """The mechanical `dsl_stop` is retired — it must never appear as a candidate."""
    lv = _levels()
    lv["stop"] = 91.234                          # a stray mechanical field, if present
    b = be.compute_bracket(lv, MA, "GREEN", price=100.0)
    assert all(c["type"] != "dsl_stop" for c in b["candidates"])


def test_regime_ceiling_helper():
    assert be.regime_stop_ceiling("green") == 12.0
    assert be.regime_stop_ceiling("RED") == 4.0
    assert be.regime_stop_ceiling(None) == 12.0
    assert be.regime_stop_ceiling("weird") == 12.0
