"""Unit tests for the Intraday Momentum & Bracket (IMB) layer — pure, synthetic."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from src.intraday import config as C
from src.intraday.momentum import intraday_momentum, normalize_bars
from src.intraday.bracket import operative_stop, entry_zone, build_bracket
from src.intraday.plan import intraday_plan, rank_plans


def mk_bars(day: date, closes, vols=None, start=(9, 30), step=5, spread=0.1):
    """Synthetic 5-min bars for one session from `closes`."""
    t0 = datetime(day.year, day.month, day.day, start[0], start[1])
    bars = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i > 0 else c
        hi = max(o, c) + spread
        lo = min(o, c) - spread
        v = vols[i] if vols else 1000.0
        bars.append({
            "date": (t0 + timedelta(minutes=step * i)).strftime("%Y-%m-%d %H:%M:%S"),
            "open": o, "high": hi, "low": lo, "close": c, "volume": v,
        })
    return bars


DAY = date(2026, 6, 16)


# ── momentum: VWAP / OR / RVOL exactness ────────────────────────────────────
def test_vwap_or_rvol_exact():
    closes = [100, 101, 102, 103, 104, 105, 106, 107]
    bars = mk_bars(DAY, closes, vols=[100] * 8, spread=0.0)
    m = intraday_momentum(bars, {})
    comp = m["components"]
    # VWAP = volume-weighted mean of typical price (h+l+c)/3 — match the definition.
    typ = [(b["high"] + b["low"] + b["close"]) / 3 for b in bars]
    exp_vwap = sum(t * b["volume"] for t, b in zip(typ, bars)) / sum(b["volume"] for b in bars)
    assert comp["vwap"] == pytest.approx(exp_vwap, abs=0.01)
    # OR window = first 30 min = first 6 bars (09:30–09:55). High of those = 105.
    assert comp["or_high"] == pytest.approx(105.0, abs=0.01)
    # Only one session present → no prior-day baseline → rvol_pace is None.
    assert comp["rvol_pace"] is None


def test_rvol_pace_two_days():
    prior = mk_bars(date(2026, 6, 15), [100] * 8, vols=[100] * 8)
    today = mk_bars(DAY, [100] * 8, vols=[200] * 8)
    m = intraday_momentum(prior + today, {})
    # Today paces 2x the prior day's cumulative volume by the same time.
    assert m["components"]["rvol_pace"] == pytest.approx(2.0, abs=0.05)


# ── momentum: state machine ─────────────────────────────────────────────────
def test_state_accelerating():
    closes = [100 + i * 0.6 for i in range(10)]            # steady rise
    m = intraday_momentum(mk_bars(DAY, closes), {})
    assert m["state"] == "ACCELERATING"
    assert 0 <= m["ims"] <= 100


def test_state_broken():
    closes = [105 - i * 0.6 for i in range(10)]            # steady decline
    m = intraday_momentum(mk_bars(DAY, closes), {})
    assert m["state"] == "BROKEN"
    assert m["components"]["price"] < m["components"]["vwap"]


def test_state_extended():
    closes = [100 + i * 1.8 for i in range(12)]            # steep ramp
    rec = {"entry": 100.0, "dsl_risk": 2.0}
    m = intraday_momentum(mk_bars(DAY, closes), rec)
    assert m["state"] == "EXTENDED"
    assert m["components"]["ext_r"] >= C.EXTENDED_R


def test_state_fading_below_vwap():
    closes = [101, 100.4, 99.8, 99.6, 99.7, 99.8, 99.75, 99.72, 99.71, 99.7]
    m = intraday_momentum(mk_bars(DAY, closes), {})
    # Price slipped below VWAP but holds above the opening-range low → FADING.
    assert m["state"] == "FADING"


def test_state_returns_valid_label_always():
    for closes in ([100] * 8, [100, 100.1, 100.05, 100.1, 100.08, 100.1, 100.09]):
        m = intraday_momentum(mk_bars(DAY, closes), {})
        assert m["state"] in {"ACCELERATING", "PULLBACK_HOLDING", "COILING",
                              "EXTENDED", "FADING", "BROKEN", "UNKNOWN"}


def test_insufficient_bars():
    m = intraday_momentum([{"date": "2026-06-16 09:30:00", "open": 1, "high": 1,
                            "low": 1, "close": 1, "volume": 1}], {})
    assert m["state"] == "UNKNOWN" and m["ims"] is None


# ── operative stop: 3 gates + tightest passing ──────────────────────────────
def _mom(price, vwap=None, or_low=None, iatr=1.0):
    return {"state": "ACCELERATING", "ims": 70,
            "components": {"price": price, "vwap": vwap, "or_low": or_low,
                           "intraday_atr": iatr}}


def test_operative_stop_tightest_valid():
    rec = {"atr_14d": 1.0, "dsl_tp_2r": 105.0, "dsl_stop": 98.0,
           "structural_levels": [
               {"type": "a", "price": 99.2},   # risk .8 → atr_ratio .8 < 1 → FAIL
               {"type": "b", "price": 98.8},   # risk 1.2, rr 4.17, .8% → VALID
               {"type": "c", "price": 97.0},   # risk 3, rr 1.67 < 2 → FAIL
           ]}
    op = operative_stop([], rec, _mom(100.0), planned_entry=100.0, regime="GREEN")
    assert op["valid"] and op["price"] == 98.8 and op["type"] == "aqe_b"


def test_operative_stop_regime_ceiling_blocks():
    # Only candidate passing ATR+R:R breaches the RED 4% ceiling → gated_out.
    rec = {"atr_14d": 1.0, "dsl_tp_2r": 110.0, "dsl_stop": 94.5,
           "structural_levels": [{"type": "x", "price": 95.0}]}  # risk 5 → 5% > 4%
    op = operative_stop([], rec, _mom(100.0), planned_entry=100.0, regime="RED")
    assert op["gated_out"] is True and op["valid"] is False
    assert op["ceiling_pct"] == 4.0


# ── entry zone: never chase past max_chase_tp2 ──────────────────────────────
def test_entry_zone_extended_stands_down_past_max_chase():
    rec = {"max_chase_tp2": 105.0}
    mom = {"state": "EXTENDED", "components": {"price": 112, "vwap": 108, "or_high": 110}}
    z = entry_zone(rec, mom)
    assert z["kind"] == "stand_down"      # even a VWAP pullback (108) > cap (105)


def test_entry_zone_accelerating_caps_high():
    rec = {"max_chase_tp2": 103.0}
    mom = {"state": "ACCELERATING", "components": {"price": 101, "vwap": 100}}
    z = entry_zone(rec, mom)
    assert z["kind"] == "now" and z["high"] <= 103.0


def test_entry_zone_pullback_zone():
    rec = {"max_chase_tp2": 105.0}
    mom = {"state": "PULLBACK_HOLDING", "components": {"price": 101, "vwap": 100}}
    z = entry_zone(rec, mom)
    assert z["kind"] == "limit" and z["low"] <= 100.0 <= z["high"] + 1e-9


def test_entry_zone_broken_stands_down():
    z = entry_zone({}, {"state": "BROKEN", "components": {"price": 99, "vwap": 100}})
    assert z["kind"] == "stand_down"


# ── full plan ───────────────────────────────────────────────────────────────
def test_plan_stand_down_when_broken():
    rec = {"ticker": "ZZZ", "entry": 105, "dsl_risk": 2, "atr_14d": 1,
           "dsl_tp_2r": 110, "dsl_stop": 102}
    closes = [105 - i * 0.6 for i in range(10)]
    p = intraday_plan(rec, mk_bars(DAY, closes), regime="GREEN")
    assert p["action"] == "STAND_DOWN" and p["ibkr_spec"] is None


def test_plan_enter_shape_and_ibkr_spec():
    rec = {"ticker": "AAA", "atr_14d": 1.0, "dsl_tp_2r": 106.0, "dsl_stop": 97.5,
           "max_chase_tp2": 104.0,
           "structural_levels": [{"type": "swing_low_1", "price": 99.5}],
           "structural_targets": [{"type": "r1", "price": 102.0},
                                  {"type": "r2", "price": 106.0}]}
    closes = [100 + i * 0.1 for i in range(10)]   # gentle rise, stays under max_chase
    p = intraday_plan(rec, mk_bars(DAY, closes), regime="GREEN", risk_budget=2100)
    assert p["action"] == "ENTER"
    assert p["operative_stop"]["price"] is not None
    assert p["shares"] >= 1
    spec = p["ibkr_spec"]
    assert spec and spec["action"] == "BUY" and spec["symbol"] == "AAA"
    assert spec["stop"] == p["operative_stop"]["price"]


def test_rank_plans_orders_enter_first():
    plans = [
        {"action": "STAND_DOWN", "ims": 90},
        {"action": "ENTER", "ims": 55},
        {"action": "CAUTION", "ims": 80},
        {"action": "ENTER", "ims": 70},
    ]
    ranked = rank_plans(plans)
    assert [p["action"] for p in ranked] == ["ENTER", "ENTER", "CAUTION", "STAND_DOWN"]
    assert ranked[0]["ims"] == 70  # higher IMS enter first
