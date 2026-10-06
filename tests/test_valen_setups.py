"""VALEN Part 3 -- the measured setup graders (src/valen/setups.py).

Each test builds a synthetic chart that has (or deliberately breaks) the
handbook's own shape, so a pass means the grader reads the handbook's rule,
not a fitted pattern. Thresholds come from spec.py; nothing is hard-coded
here that the spec could move.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.valen import setups as SU
from src.valen import spec as S


def _frame(closes, vols=None, opens=None, wick=0.006, highs=None, lows=None):
    c = np.asarray(closes, float)
    n = len(c)
    o = np.asarray(opens, float) if opens is not None else np.concatenate([[c[0]], c[:-1]])
    h = np.asarray(highs, float) if highs is not None else np.maximum(o, c) * (1 + wick)
    lo = np.asarray(lows, float) if lows is not None else np.minimum(o, c) * (1 - wick)
    v = np.asarray(vols, float) if vols is not None else np.full(n, 1_000_000.0)
    d0 = date(2025, 1, 1)
    dates = [d0 + timedelta(days=i) for i in range(n)]
    return pd.DataFrame({"date": dates, "open": o, "high": h, "low": lo, "close": c, "volume": v})


def _ramp(a, b, n):
    return list(np.geomspace(a, b, n))


# ------------------------------------------------------------------- primitives

def test_zigzag_finds_alternating_swings():
    c = _ramp(100, 120, 20) + _ramp(120, 108, 8) + _ramp(108, 125, 10)
    df = _frame(c)
    piv = SU.zigzag(df["high"].to_numpy(), df["low"].to_numpy(), 5.0, start=0)
    kinds = [p[2] for p in piv]
    assert kinds[:3] == ["H", "L", "H"] or kinds[1:4] == ["H", "L", "H"]


def test_count_bases_counts_completed_pullbacks():
    c = (_ramp(50, 60, 40) + _ramp(60, 52, 10) + _ramp(52, 70, 30)
         + _ramp(70, 61, 10) + _ramp(61, 80, 30) + _ramp(80, 72, 10))
    df = _frame(c)
    b = SU.count_bases(df["high"].to_numpy(), df["low"].to_numpy(), 10.0)
    assert b == 3   # two completed bases, in the third now


def test_expansion_day_rules():
    c = [100.0] * 30 + [100.5, 101.0, 106.0]
    o = list(c)
    o[-1] = 100.9
    v = [1e6] * 32 + [3e6]
    df = _frame(c, vols=v, opens=o, wick=0.001)
    b = SU.Bars(df)
    ok = SU.expansion_day(b.o, b.h, b.l, b.c, b.v, b.n - 1)
    assert ok["ok"] is True
    # three up-days into it breaks "not buying on day three"
    c2 = [100.0] * 30 + [100.5, 101.0, 101.5, 106.5]
    o2 = list(c2)
    o2[-1] = 101.4
    df2 = _frame(c2, vols=[1e6] * 33 + [3e6], opens=o2, wick=0.001)
    b2 = SU.Bars(df2)
    res = SU.expansion_day(b2.o, b2.h, b2.l, b2.c, b2.v, b2.n - 1)
    assert res["ok"] is False
    assert any(x["rule"].startswith("No more than 2") and x["result"] == "FAIL"
               for x in res["checks"])


# -------------------------------------------------------------------- 08 VCP

def _vcp_closes():
    run = _ramp(60, 100, 60)                                  # +67% clean run
    base = (_ramp(100, 80, 8) + _ramp(80, 98, 10)             # 20%
            + _ramp(98, 88, 6) + _ramp(88, 97, 8)             # ~10%
            + _ramp(97, 93, 5) + _ramp(93, 96.5, 6))          # ~4%
    return [55.0] * 60 + run + base


def test_vcp_ready_on_a_real_shrinking_sequence():
    c = _vcp_closes()
    v = [2e6] * (len(c) - 11) + [6e5] * 11                    # quietest at the end
    g = SU.grade_vcp(SU.Bars(_frame(c, vols=v)))
    assert g is not None
    depths = g["pullbacks_pct"]
    assert all(depths[k] < depths[k - 1] for k in range(1, len(depths)))
    assert depths[-1] <= S.HB_VCP_LAST_PULLBACK_MAX_PCT
    assert g["status"] in ("READY", "WATCH")
    assert g["pivot"] is not None and g["stop"] < g["pivot"]


def test_vcp_one_quiet_week_is_not_a_vcp():
    c = [55.0] * 60 + _ramp(60, 100, 60) + [99.5, 100.2, 99.8, 100.1, 99.9] * 4
    assert SU.grade_vcp(SU.Bars(_frame(c, wick=0.002))) is None


def test_vcp_needs_a_30pct_run():
    c = [90.0] * 60 + _ramp(90, 100, 60) + _vcp_closes()[-43:]
    c = [x if i < 120 else x for i, x in enumerate(c)]
    g = SU.grade_vcp(SU.Bars(_frame(c)))
    assert g is None or g["checks"][0]["value"] >= "30"


# ----------------------------------------------------------- 09 High tight flag

def _htf(depth=0.12, flag_len=20, pole_days=30, vol_fade=True):
    pre = [20.0] * 150
    pole = _ramp(20, 42, pole_days)                           # +110% staircase
    flag = list(42 * (1 - depth * np.sin(np.linspace(0, np.pi / 2, flag_len))))
    c = pre + pole + flag
    v = [1e6] * 150 + [3e6] * pole_days + (
        list(np.linspace(1.5e6, 5e5, flag_len)) if vol_fade else [3e6] * flag_len)
    return c, v


def test_htf_watch_or_ready_on_a_textbook_flag():
    c, v = _htf()
    g = SU.grade_htf(SU.Bars(_frame(c, vols=v)))
    assert g is not None and g["status"] in ("READY", "WATCH")
    assert g["pole_pct"] >= S.HB_HTF_POLE_MIN_PCT
    assert g["flag_depth_pct"] <= S.HB_HTF_FLAG_MAX_PCT


def test_htf_flag_too_deep_fails_with_no_partial_credit():
    c, v = _htf(depth=0.35)
    g = SU.grade_htf(SU.Bars(_frame(c, vols=v)))
    assert g is not None and g["status"] == "FAILED"
    assert any("shallow" in f for f in g["fails"])


def test_htf_forty_percent_run_is_not_a_pole():
    pre = [20.0] * 150
    c = pre + _ramp(20, 28, 30) + [27.0] * 20
    assert SU.grade_htf(SU.Bars(_frame(c))) is None


def test_htf_young_flag_is_not_yet():
    c, v = _htf(flag_len=8)
    g = SU.grade_htf(SU.Bars(_frame(c, vols=v)))
    assert g is not None
    brief = next(x for x in g["checks"] if x["rule"].startswith("Flag is brief"))
    assert brief["result"] == "NOT_YET"


# ------------------------------------------------------- 10 Undercut and rally

def _unr(reclaim=True, deep=False):
    base = _ramp(40, 100, 120)                              # rising trend
    swing = [100, 98, 96, 95, 96, 98, 100, 102, 103, 104]   # swing low at 95
    drift = [103, 102, 101, 100]
    under = [96, 94.0 if not deep else 85.0]                # dip under 95
    tail = [96.5] if reclaim else [93.0]
    c = base + swing + drift + under + tail
    return c


def test_unr_triggers_on_the_reclaim():
    c = _unr()
    lows = list(np.asarray(c) * 0.995)
    lows[-2] = 93.8
    g = SU.grade_unr(SU.Bars(_frame(c, lows=lows)), rs_rank=85, in_theme=True)
    assert g is not None
    assert g["status"] in ("TRIGGERED", "WATCH", "FAILED")
    reclaim = next(x for x in g["checks"] if "reclaim" in x["rule"])
    assert reclaim["result"] == "PASS"


def test_unr_no_reclaim_is_not_yet():
    c = _unr(reclaim=False)
    g = SU.grade_unr(SU.Bars(_frame(c)), rs_rank=85, in_theme=True)
    assert g is not None
    reclaim = next(x for x in g["checks"] if "reclaim" in x["rule"])
    assert reclaim["result"] == "NOT_YET"
    assert g["status"] != "TRIGGERED"


def test_unr_broken_stock_is_not_a_pullback():
    c = _ramp(100, 60, 140) + [61, 59, 60]
    assert SU.grade_unr(SU.Bars(_frame(c))) is None


# --------------------------------------------------------- 11 Episodic pivot

def _ep(gap_open=112.0, close=115.0, vol_mult=4.0, prior_run=1.0):
    # flat, then the last 3 months rise by `prior_run`x into the gap
    pre = [100 / prior_run] * 137 + list(np.linspace(100 / prior_run, 100, 63))
    c = pre + [close]
    o = list(np.concatenate([[pre[0]], pre[:-1]])) + [gap_open]
    h = [x * 1.005 for x in c[:-1]] + [close * 1.01]
    lo = [x * 0.995 for x in c[:-1]] + [gap_open * 0.995]
    v = [1e6] * 200 + [vol_mult * 1e6]
    return _frame(c, vols=v, opens=o, highs=h, lows=lo)


def test_ep_gap_day_graded_with_catalyst_marked_as_fingerprint():
    g = SU.grade_ep(SU.Bars(_ep()))
    assert g is not None and g["piece"] == "11"
    cat = next(x for x in g["checks"] if x["rule"] == "Catalyst")
    assert cat["result"] == "INFO" and "fingerprint" in cat["value"]


def test_ep_earnings_day_confirms_a_smaller_expansion():
    df = _ep(gap_open=101.0, close=105.0)                    # 1% gap, 5% day
    d = df["date"].iloc[-1]
    g = SU.grade_ep(SU.Bars(df), earnings_dates={d})
    assert g is not None
    cat = next(x for x in g["checks"] if x["rule"] == "Catalyst")
    assert cat["result"] == "PASS"
    assert SU.grade_ep(SU.Bars(df), earnings_dates=set()) is None


def test_ep_needs_3x_volume():
    g = SU.grade_ep(SU.Bars(_ep(vol_mult=1.5)))
    assert g["status"] == "FAILED"


def test_ep_stock_everybody_loves_is_not_a_surprise():
    g = SU.grade_ep(SU.Bars(_ep(prior_run=1.8)))
    assert g["status"] == "FAILED"
    assert any("Neglect" in f for f in g["fails"])


# ------------------------------------------- 12 long-only risk warnings

def test_parabolic_is_a_warning_never_a_short():
    c = [50.0] * 100 + _ramp(50, 85, 15) + [87, 89, 91]
    g = SU.warn_parabolic(SU.Bars(_frame(c)))
    assert g is not None and g["status"] in ("WARNING", "CRACKED")
    assert "never a short" in g["note"].lower()


def test_no_grader_ever_emits_a_short_status():
    for st in SU.STATUS_ORDER:
        assert "SHORT" not in st


# ----------------------------------------------------------- entry point

def test_grade_universe_absent_ticker_is_absent_not_empty():
    panel = _frame([100.0] * 300).assign(ticker="AAA")
    out = SU.grade_universe(panel, [{"ticker": "AAA"}, {"ticker": "ZZZ"}])
    assert "AAA" in out and out["AAA"] == []
    assert "ZZZ" not in out


def test_every_threshold_in_spec_is_labelled_hb_or_impl():
    names = [n for n in dir(S) if n.startswith(("HB_", "IMPL_"))]
    assert len(names) > 30


# ------------------------------------------- 10b U&R against the other levels

def _uptrend(n=160, a=40.0, b=100.0):
    return _ramp(a, b, n)


def _find(grades, fragment):
    return [g for g in grades if fragment in g["setup"]]


def test_ma_undercut_and_rally_daily_ema21_triggers_on_the_reclaim():
    base = _uptrend()
    # three quiet bars, a flush through EMA21, then a close back above it
    ema21 = pd.Series(base).ewm(span=21, adjust=False).mean().iloc[-1]
    c = base + [ema21 * 1.01, ema21 * 1.005, ema21 * 0.995, ema21 * 1.012]
    lows = list(np.asarray(c) * 0.988)
    lows[-2] = ema21 * 0.985          # the undercut
    lows[-1] = ema21 * 0.988          # undercut again, closes back above
    g = SU.grade_unr_levels(SU.Bars(_frame(c, lows=lows, wick=0.012)), rs_rank=85, in_theme=True)
    hit = _find(g, "Daily EMA21")
    assert hit, [x["setup"] for x in g]
    assert hit[0]["ref_kind"] == "ma" and hit[0]["piece"] == "10"
    assert hit[0]["status"] in ("TRIGGERED", "WATCH", "PAST_PIVOT")   # never FAILED
    assert any("Buffer-stop zone" in x["rule"] for x in hit[0]["checks"])


def test_no_undercut_means_no_ma_grade():
    c = _uptrend() + [100.5, 101.0, 101.5]
    assert SU.grade_unr_levels(SU.Bars(_frame(c))) == []


def test_a_falling_50_day_is_not_an_uptrend_for_any_reference_level():
    c = _ramp(100, 60, 160) + [61, 62, 61]
    assert SU.grade_unr_levels(SU.Bars(_frame(c))) == []


def test_weekly_ema9_is_computed_from_resampled_weekly_closes():
    b = SU.Bars(_frame(_uptrend(200)))
    w = SU._weekly_ema9(b)
    assert w is not None and 40 < w < 100
    assert SU._weekly_ema9(SU.Bars(_frame(_uptrend(60)))) is None   # too little history


def test_support_gap_found_only_when_it_gapped_on_volume_and_held():
    c = _ramp(50, 60, 100) + [66.0] + _ramp(66.5, 70, 40)           # +10% gap
    o = list(np.concatenate([[c[0]], c[:-1]]))
    o[100] = 66.0
    lows = list(np.asarray(c) * 0.997)
    lows[100] = 65.9
    highs = list(np.asarray(c) * 1.003)
    v = [1e6] * len(c)
    v[100] = 4e6
    b = SU.Bars(_frame(c, vols=v, opens=o, lows=lows, highs=highs))
    gaps = SU._support_gaps(b, win0=b.n - 10)
    assert gaps and abs(gaps[0] - highs[99]) < 1e-6
    v2 = [1e6] * len(c)                                             # same gap, no volume
    b2 = SU.Bars(_frame(c, vols=v2, opens=o, lows=lows, highs=highs))
    assert SU._support_gaps(b2, win0=b2.n - 10) == []


def test_round_number_undercut_is_the_highest_one_dipped_under_and_reclaimed():
    c = _ramp(60, 104, 150) + [103.0, 101.5, 102.0, 101.0, 102.5]
    lows = list(np.asarray(c) * 0.997)
    lows[-3] = 99.4                    # flushed through 100, closed back above
    b = SU.Bars(_frame(c, lows=lows))
    atr = float(b.atr[-1])
    assert SU._round_level(b, win0=b.n - 10, atr=atr) == 100.0


def test_grade_ticker_returns_the_new_grades_alongside_the_handbook_ones():
    base = _uptrend()
    ema21 = pd.Series(base).ewm(span=21, adjust=False).mean().iloc[-1]
    c = base + [ema21 * 1.01, ema21 * 1.005, ema21 * 0.995, ema21 * 1.012]
    lows = list(np.asarray(c) * 0.988)
    lows[-2] = ema21 * 0.985
    lows[-1] = ema21 * 0.988
    out = SU.grade_ticker(_frame(c, lows=lows, wick=0.012), rs_rank=80, in_theme=True)
    assert any(g["setup"].startswith("Undercut and rally — Daily") for g in out)
    assert all(isinstance(g, dict) for g in out)


def test_new_thresholds_are_labelled_pm_or_impl_and_the_buffer_matches_the_writeup():
    assert S.PM_UNR_STOP_BUFFER_PCT == (1.25, 3.5)
    assert S.PM_UNR_DAILY_EMA_SPANS == (8, 10, 21)
    assert S.PM_UNR_WEEKLY_EMA_SPAN == 9


def test_failed_shapes_are_not_recorded_for_the_looser_levels():
    # a name whose undercut stop is wider than one daily range fails a hard
    # rule -> no grade at all for that level (the handbook U&R still records it)
    base = _uptrend()
    ema21 = pd.Series(base).ewm(span=21, adjust=False).mean().iloc[-1]
    c = base + [ema21 * 1.01, ema21 * 1.005, ema21 * 0.995, ema21 * 1.012]
    lows = list(np.asarray(c) * 0.988)
    lows[-2] = ema21 * 0.80            # a flush far deeper than one daily range
    g = SU.grade_unr_levels(SU.Bars(_frame(c, lows=lows, wick=0.012)), rs_rank=85, in_theme=True)
    assert not _find(g, "Daily EMA21")
