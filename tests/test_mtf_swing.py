"""Swing structure in the MTF grid (PM 2026-11-05): strict fractal pivots replace the 3-bar hh_hl_3. KO fixture = the real FMP daily bars
(2026-09-14 .. 2026-11-04); expected values are the PM's test case (swing_structure_testcase.md): daily HH/HL, swing highs 95.37 / 94.10, swing
lows 90.58 / 85.13, close +0.45% vs the last swing high."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mtf_sw", ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "mtf.py")
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)

# date, open, high, low, close
KO = [
 ("2026-09-14", 90, 90.36, 88.87, 89.35), ("2026-09-15", 88.53, 88.9, 87.8, 88.71), ("2026-09-16", 88.48, 88.66, 87.74, 87.87),
 ("2026-09-17", 88.08, 88.33, 87.51, 88.06), ("2026-09-18", 87.8, 88.29, 87.52, 88.25), ("2026-09-21", 88.32, 88.5, 87.12, 87.12),
 ("2026-09-22", 87.6, 88.97, 87.46, 88.61), ("2026-09-23", 88.95, 89, 87.61, 88.09), ("2026-09-24", 88.82, 89.36, 88.1, 88.1),
 ("2026-09-25", 88.16, 88.32, 87.56, 87.81), ("2026-09-28", 87.61, 87.7, 86.89, 87.18), ("2026-09-29", 86.56, 87.28, 86.56, 86.84),
 ("2026-09-30", 87.35, 87.52, 86.07, 86.08), ("2026-10-01", 86.23, 86.68, 85.72, 86.1), ("2026-10-02", 86.3, 86.45, 85.17, 85.65),
 ("2026-10-05", 85.87, 86.57, 85.13, 86.51), ("2026-10-06", 86.6, 87.29, 86.16, 86.17), ("2026-10-07", 86.73, 86.96, 85.67, 85.82),
 ("2026-10-08", 86.26, 88.04, 86.08, 87.77), ("2026-10-09", 87.6, 88.48, 87.39, 88.05), ("2026-10-12", 88.42, 89.8, 88.42, 89.79),
 ("2026-10-13", 90.56, 90.56, 89.67, 90.11), ("2026-10-14", 90.9, 91.93, 90.55, 91.78), ("2026-10-15", 93.15, 94.1, 91.72, 92),
 ("2026-10-16", 92.99, 93.9, 92.81, 93.9), ("2026-10-19", 92.56, 93.99, 92.56, 93.42), ("2026-10-20", 93.68, 93.96, 92.64, 93.49),
 ("2026-10-21", 93.11, 93.46, 92.55, 92.68), ("2026-10-22", 93.85, 95.37, 93.6, 95.34), ("2026-10-23", 95.01, 95.05, 92.64, 92.71),
 ("2026-10-26", 92.69, 92.88, 91.94, 92.7), ("2026-10-27", 90.82, 92.95, 90.81, 91.18), ("2026-10-28", 90.84, 92.36, 90.58, 91.73),
 ("2026-10-29", 92.8, 93.16, 92.03, 92.82), ("2026-10-30", 94.52, 95.08, 93.95, 94.08), ("2026-11-02", 94.28, 96.26, 94.28, 95.83),
 ("2026-11-03", 94.88, 95.49, 94.18, 94.8), ("2026-11-04", 96.3, 96.555, 94.35, 95.8),
]
KO_BARS = [{"date": d, "open": o, "high": h, "low": l, "close": c, "volume": 1.0} for d, o, h, l, c in KO]


def test_ko_daily_matches_the_pms_test_case_exactly():
    sw = M.swing_structure(KO_BARS, "D")
    assert sw["cls"] == "HH/HL"
    assert (sw["last_swing_high"], sw["prev_swing_high"]) == ({"price": 95.37, "date": "2026-10-22"}, {"price": 94.1, "date": "2026-10-15"})
    assert (sw["last_swing_low"], sw["prev_swing_low"]) == ({"price": 90.58, "date": "2026-10-28"}, {"price": 85.13, "date": "2026-10-05"})
    assert sw["close_vs_swing_high_pct"] == 0.45
    assert "3 bars each side" in sw["rule"]


def test_an_unconfirmed_recent_peak_is_not_a_swing_high():
    """2 Nov's 96.26 high has only two bars after it: not a pivot yet, so the latest swing high stays 95.37 (never a look-ahead)."""
    hs, _ = M.pivots(KO_BARS, 3)
    assert all(KO_BARS[i]["date"] != "2026-11-02" for i in hs)


def test_a_steady_trend_has_no_swings_and_says_so_instead_of_inventing_a_class():
    bars = [{"date": f"2026-01-{i + 1:02d}", "open": 100 + i, "high": 100.5 + i, "low": 99.5 + i, "close": 100 + i, "volume": 1.0} for i in range(30)]
    sw = M.swing_structure(bars, "D")
    assert sw["cls"] is None and "two of each are needed" in sw["reason"]
    assert M.swing_plain(None) == "no clear swing structure"


def test_mixed_reads_name_the_leg_and_plain_words_follow():
    # highs rise (HH) while lows fall (LL): "HH but LL"
    H = [10, 11, 12, 13, 12, 11, 10, 11, 12, 14, 12, 11, 10, 9, 8, 7]
    L = [8, 9, 10, 11, 10, 9, 6, 9, 10, 12, 10, 9, 5, 6, 6, 6]
    bars = [{"date": f"2026-02-{i + 1:02d}", "open": h, "high": h, "low": l, "close": l, "volume": 1.0} for i, (h, l) in enumerate(zip(H, L))]
    sw = M.swing_structure(bars, "D")
    assert sw["cls"] == "HH but LL" and sw["high_leg"] == "HH" and sw["low_leg"] == "LL"
    assert M.swing_plain("HH but LL") == "higher highs but lower lows" and M.swing_plain("LH but HL") == "lower highs but higher lows"
    assert M.swing_plain("HH/HL") == "higher highs and higher lows" and M.swing_plain("LH/LL") == "lower highs and lower lows"


def test_the_weekly_frame_uses_two_bars_each_side_and_leaves_the_open_week_out():
    assert M.SWING_K == {"W": 2, "D": 3, "H1": 3}
    wk = M.weekly(KO_BARS)
    sw_all = M.swing_structure(wk, "W")
    sw_open = M.swing_structure(wk, "W", completed=wk[:-1])
    assert "open week left out" in sw_open["rule"] and "open week" not in sw_all["rule"]
    # the open week is never a pivot candidate when left out
    assert sw_open["last_swing_high"] is None or sw_open["last_swing_high"]["date"] <= wk[-2]["date"][:10]


def test_frame_carries_swing_fields_and_no_hh_hl_3():
    bars = [{"date": b["date"], "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"], "volume": b["volume"]} for b in KO_BARS]
    # pad earlier history so the EMA21 minimum is met
    pad = [{"date": f"2026-08-{d:02d}", "open": 88, "high": 89, "low": 87, "close": 88, "volume": 1.0} for d in range(3, 31) if dt_ok(d)]
    f = M.frame(pad + bars, "D")
    assert f["served"] and f["swing_class"] == "HH/HL" and "hh_hl_3" not in f
    assert f["swing"]["close_vs_swing_high_pct"] == 0.45
    assert "swing HH/HL, 0.5% above the last swing high" in M.frame_text("D", f)
    assert f["high_20bar"] == 96.555 and f["high_20bar_date"] == "2026-11-04"


def dt_ok(d):
    import datetime as dt
    return dt.date(2026, 8, d).weekday() < 5


def _row(w_cls, d_cls, d_pct):
    sw = lambda c, p=None: {"served": True, "swing_class": c, "swing": {"close_vs_swing_high_pct": p}}
    return {"W": sw(w_cls), "D": sw(d_cls, d_pct)}


def test_the_flag_is_weekly_and_daily_hh_hl_only_the_distance_is_read_in_atr_by_the_cards():
    assert M.momentum_flag(_row("HH/HL", "HH/HL", 1.0))["flag"] is True
    assert M.momentum_flag(_row("HH/HL", "HH/HL", 5.8))["flag"] is True                # no fixed % cut-off any more (PM 2026-11-05)
    r = M.momentum_flag(_row("LH/LL", "HH/HL", 0.5))
    assert r["flag"] is False and "weekly swing is LH/LL" in r["reasons"][0]
    assert M.momentum_flag({"W": {"served": False}, "D": {"served": True}})["flag"] is False
    assert M.momentum_flag(_row(None, "HH/HL", 0.5))["reasons"][0].startswith("weekly swing is not readable")
    assert not hasattr(M, "MOMENTUM_NEAR_PCT")


def test_swing_counts_summarise_the_room():
    names = {"A": {"served": True, "W": {"swing_class": "HH/HL"}, "D": {"swing_class": "HH/HL"}, "H1": {"swing_class": "HH/HL"}},
             "B": {"served": True, "W": {"swing_class": "LH/LL"}, "D": {"swing_class": "HH/HL"}, "H1": {"swing_class": None}},
             "C": {"served": False}}
    assert M.swing_counts(names) == {"n": 2, "weekly_hh_hl": 1, "daily_hh_hl": 2, "hourly_hh_hl": 1, "weekly_and_daily": 1, "all_three": 1}


def test_weekly_and_daily_20_bar_highs_are_separate_computations_that_agree_only_for_a_stock_at_its_highs():
    """Audit item 3 (PM 2026-11-05): W dist_to_20bar_high_pct equals D's on every name that is at its highs because the highest high of the last 20
    WEEKS and of the last 20 SESSIONS is then the same bar; it is not copied. A stock whose 20-week high is older than 20 sessions differs."""
    import datetime as dt
    d = dt.date(2025, 6, 2); bars = []
    for i in range(300):
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        px = 100 + (60 if i == 200 else 0) + (i * 0.05)          # a single high spike at session 200, then drift
        bars.append({"date": d.isoformat(), "open": px, "high": px + 1, "low": px - 1, "close": px, "volume": 1.0}); d += dt.timedelta(days=1)
    row = M.build_name("TST", {"daily": bars}, bars[-1]["date"])
    assert row["W"]["high_20bar"] != row["D"]["high_20bar"] or row["W"]["dist_to_20bar_high_pct"] != row["D"]["dist_to_20bar_high_pct"]
    top = [dict(b) for b in bars]
    for b in top[-5:]:
        b["high"] = 400.0; b["close"] = 399.0                      # now both windows end at the same recent high
    row2 = M.build_name("TST", {"daily": top}, top[-1]["date"])
    assert row2["W"]["high_20bar"] == row2["D"]["high_20bar"] == 400.0
    assert row2["W"]["high_20bar_date"] == row2["D"]["high_20bar_date"]
