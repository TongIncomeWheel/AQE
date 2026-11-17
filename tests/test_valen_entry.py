"""PM 2026-11-17: Valen's entry methods (stop fit, volume gate, 30-minute pivot, opening-range break in SHADOW) as facts; never a gate, never a size."""
import json

import pandas as pd

from src.alerts import live_entry as LEN
from src.valen import entry as VE
from src.valen import spec as S


def bar(hhmm, o, h, l, c, v):
    return {"date": f"2026-11-17 {hhmm}:00", "open": o, "high": h, "low": l, "close": c, "volume": v}


def day(prices):
    """prices: list of (o,h,l,c,v) for consecutive 15-min slots from 09:30."""
    out = []
    for i, (o, h, l, c, v) in enumerate(prices):
        m = 570 + 15 * i
        out.append(bar(f"{m // 60:02d}:{m % 60:02d}", o, h, l, c, v))
    return out


def test_stop_fit_is_the_arithmetic_with_a_tick_and_one_atr_cap():
    g = VE.stop_fit(100.0, 99.0, 2.0)                      # stop 98.99, risk 1.01, 0.5 ATR, lod 0.5
    assert g["stop"] == 98.99 and g["risk"] == 1.01 and g["atr_multiple"] == 0.51 and g["fit"] == VE.GOOD and g["within_cap"]
    assert VE.stop_fit(100.0, 98.5, 2.0)["fit"] == VE.OK            # lod 0.75: past the 0.70 preference, inside the 1.0 cap
    far = VE.stop_fit(100.0, 97.0, 2.0)
    assert far["fit"] == VE.TOO_FAR and not far["within_cap"] and far["atr_multiple"] > S.ENTRY_STOP_CAP_ATR
    assert VE.stop_fit(100.0, 99.0, 0)["fit"] == VE.NA and VE.stop_fit(None, 99, 2)["fit"] == VE.NA     # missing input is NA, never a pass
    assert "too far" in VE.plain(far) and "not read" in VE.plain({"fit": VE.NA, "reason": "no ATR"})


def test_entry_last_day_uses_the_house_atr_and_marks_short_history_na():
    rows = [{"ticker": "AAA", "atr_14d": 2.0}, {"ticker": "BBB"}]
    d = pd.date_range("2026-09-01", periods=30, freq="B")
    panel = pd.concat([pd.DataFrame({"ticker": "AAA", "date": d, "open": 99.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1e6}),
                       pd.DataFrame({"ticker": "BBB", "date": d[:5], "open": 9.0, "high": 10.0, "low": 9.0, "close": 9.5, "volume": 1e6})])
    out = VE.entry_last_day(panel, rows)
    assert out["AAA"]["stop_fit"]["atr"] == 2.0 and out["AAA"]["stop_fit"]["fit"] == VE.GOOD and out["AAA"]["stop_fit"]["as_of"]
    assert out["BBB"]["stop_fit"]["fit"] == VE.NA


def test_volume_gate_reads_each_mark_at_its_completed_bar_and_never_passes_without_a_profile():
    profile = {k: 100.0 for k in range(26)}                # a normal day = 2,600
    bars = day([(10, 10.2, 9.9, 10.1, 400), (10.1, 10.3, 10.0, 10.2, 700)])      # 400/2600=15% at 09:45, 1100/2600=42% at 10:00
    g = LEN.volume_gate(bars, profile)
    m = {x["mark"]: x for x in g["marks"]}
    assert m["09:35"]["read_at"] == "09:45" and m["09:35"]["state"] == LEN.FAIL and m["09:35"]["share"] == 0.154
    assert m["10:00"]["read_at"] == "10:00" and m["10:00"]["state"] == LEN.PASS and g["state"] == LEN.PASS
    assert LEN.volume_gate(bars[:1], profile)["marks"][1]["state"] == LEN.NOT_YET
    assert LEN.volume_gate(bars, {})["state"] == LEN.UNKNOWN and LEN.volume_gate(bars, None)["reason"]


def test_pivot_30m_first_green_candle_after_the_undercut_sets_pivot_and_stop():
    # candle0 (09:30-10:00) dips under the 56.08 level and is red; candle1 is green with high 56.60 low 55.86; later bar breaks 56.60
    bars = day([(56.5, 56.6, 56.0, 56.2, 1), (56.2, 56.3, 55.9, 55.95, 1),          # candle 0: low 55.9 < level, red
                (55.95, 56.4, 55.86, 56.3, 1), (56.3, 56.6, 56.2, 56.55, 1),         # candle 1: green, high 56.6, low 55.86
                (56.55, 56.7, 56.5, 56.65, 1)])                                        # later bar: high 56.7 > 56.6 -> trigger
    p = LEN.pivot_30m(bars, 56.08, atr=1.0)
    assert p["state"] == "TRIGGERED" and p["pivot"] == 56.6 and p["stop"] == 55.85 and p["entry"] == 56.61
    assert p["stop_fit"]["atr_multiple"] == 0.76 and p["stop_fit"]["fit"] == VE.OK
    assert LEN.pivot_30m(bars[:4], 56.08)["state"] == "ARMED"
    assert LEN.pivot_30m(bars[:2], 56.08)["state"] == "WAIT_GREEN"
    assert LEN.pivot_30m(bars, 50.0)["state"] == "NO_UNDERCUT" and LEN.pivot_30m(bars, None)["state"] == "NO_LEVEL"
    assert LEN.candles_30m(bars[:3])[0]["slot"] == 0 and len(LEN.candles_30m(bars[:3])) == 1          # a half-built candle is not a candle


def test_orb_is_shadow_only_never_in_the_card_line_and_logged_in_the_ledger_line():
    bars = day([(10, 10.5, 9.9, 10.1, 1), (10.1, 10.9, 10.0, 10.8, 1)])
    o = LEN.orb(bars)
    assert o["state"] == "BROKE_UP" and o["high"] == 10.5 and "15 minutes" in o["basis"]
    assert LEN.orb([])["state"] == "NOT_READY"
    b = LEN.build(bars, {k: 100.0 for k in range(26)}, 10.8, 9.9, 1.0, level=None)
    assert set(b["visible"]) == {"stop_fit", "volume_gate", "pivot_30m"} and "orb" in b["shadow"] and "orb" not in b["visible"]
    line = LEN.plain_line(b["visible"]) or ""
    assert "opening" not in line.lower() and "orb" not in line.lower() and "break" not in line.lower().replace("broken", "")
    import inspect
    from src.alerts import condition_cycle as CC
    src = inspect.getsource(CC)
    assert 'line["shadow_entry"]' in src and "shadow_entry" not in inspect.getsource(__import__("src.alerts.emailer", fromlist=["x"]))


def test_orb_break_for_a_ready_name_needs_the_break_the_daily_pivot_and_the_volume_gate_shadow_only():
    prof = {k: 100.0 for k in range(26)}
    bars = day([(10, 10.5, 9.9, 10.1, 1200), (10.1, 10.9, 10.0, 10.8, 1200)])            # 2400/2600 = 92%: gate passes
    rp = LEN.ready_pivot([{"setup": "VCP", "status": "READY", "pivot": 10.6}, {"setup": "High tight flag", "status": "WATCH", "pivot": 99}])
    assert rp == {"setup": "VCP", "pivot": 10.6} and LEN.ready_pivot([{"setup": "Undercut and rally", "status": "READY", "pivot": 5}]) is None
    b = LEN.build(bars, prof, 10.8, 9.9, 1.0, pivot=10.6)
    o = b["shadow"]["orb"]
    assert o["state"] == "ORB_BREAK" and o["orb_break"] and o["above_pivot"] and o["volume_gate"] == LEN.PASS
    assert LEN.build(bars, prof, 10.8, 9.9, 1.0, pivot=10.95)["shadow"]["orb"]["state"] == "BROKE_UP"          # under the daily pivot: not a break
    thin = day([(10, 10.5, 9.9, 10.1, 10), (10.1, 10.9, 10.0, 10.8, 10)])
    assert LEN.build(thin, prof, 10.8, 9.9, 1.0, pivot=10.6)["shadow"]["orb"]["orb_break"] is False            # volume gate not met


def test_a_failing_part_is_one_error_not_a_lost_card():
    b = LEN.build("not bars", None, None, None, None)
    assert b["visible"]["stop_fit"]["fit"] == VE.NA and b["visible"]["volume_gate"]["state"] == LEN.UNKNOWN
    assert json.dumps(b)                                      # serialisable for the ledger line
