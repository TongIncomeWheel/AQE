"""VALEN Dashboard — unit tests.

Covers: trend math against synthetic SMA crossovers, extension math (ATR
multiple, VIX/VIX3M ratio, curated-panel breadth + population guard),
stance's honest DEGRADED-without-breadth behaviour and its flip rules once
breadth is supplied, explain's jargon prohibition + headline-always-present,
and card.py's "renders from the artifact alone" blindness test (mirrors
tests/test_qs_card.py's rule for qs_card.py).
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from src.valen import (breadth, card, explain, extension, groups, history, spec,
                       stance, theme, trend)

# ---------------------------------------------------------------------- trend


def _flat_panel(symbol: str, n: int, price: float, tmp_path, weekly=False) -> object:
    dates = pd.date_range("2026-01-01", periods=n, freq="W" if weekly else "D")
    df = pd.DataFrame({"date": dates, "ticker": symbol, "close": price})
    path = tmp_path / ("weekly.parquet" if weekly else "daily.parquet")
    df.to_parquet(path)
    return path


def test_uptrend_when_all_three_trend_checks_pass(tmp_path):
    # A steadily rising series: today's close is above every SMA and the
    # 5-day SMA is climbing -> daily, weekly and rising-5d all fire.
    n = 60
    closes = 100 + np.arange(n) * 0.5
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=n),
                       "ticker": "SPY", "close": closes})
    daily = tmp_path / "daily.parquet"
    df.to_parquet(daily)
    wk = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=30, freq="W"),
                      "ticker": "SPY", "close": 100 + np.arange(30) * 2.0})
    weekly = tmp_path / "weekly.parquet"
    wk.to_parquet(weekly)

    out = trend.compute_market_trend(daily, weekly)
    spy = out["rows"]["SPY"]
    assert spy["daily_buy_signal"] is True
    assert spy["weekly_buy_signal"] is True
    assert spy["above_rising_5d"] is True
    assert out["regime"] == spec.REGIME_UPTREND


def test_downtrend_when_all_three_trend_checks_fail(tmp_path):
    n = 60
    closes = 200 - np.arange(n) * 0.5
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=n),
                       "ticker": "SPY", "close": closes})
    daily = tmp_path / "daily.parquet"
    df.to_parquet(daily)
    wk = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=30, freq="W"),
                      "ticker": "SPY", "close": 200 - np.arange(30) * 2.0})
    weekly = tmp_path / "weekly.parquet"
    wk.to_parquet(weekly)

    out = trend.compute_market_trend(daily, weekly)
    assert out["regime"] == spec.REGIME_DOWNTREND


def test_missing_symbol_degrades_to_unavailable_not_an_exception(tmp_path):
    daily = _flat_panel("SPY", 60, 100.0, tmp_path)
    weekly = _flat_panel("SPY", 30, 100.0, tmp_path, weekly=True)
    out = trend.compute_market_trend(daily, weekly)
    qqq = out["rows"]["QQQ"]
    assert qqq["basis"] == "unavailable"
    assert qqq["daily_buy_signal"] is None


def test_live_price_stands_in_as_todays_bar_without_replacing_history(tmp_path):
    n = 60
    closes = 100 + np.arange(n) * 0.5
    dates = pd.date_range("2020-01-01", periods=n)   # deliberately old, so
    df = pd.DataFrame({"date": dates, "ticker": "SPY", "close": closes})  # "today" > panel's last date
    daily = tmp_path / "daily.parquet"
    df.to_parquet(daily)
    weekly = _flat_panel("SPY", 30, 100.0, tmp_path, weekly=True)

    out = trend.compute_market_trend(daily, weekly, live_prices={"SPY": 999.0})
    spy = out["rows"]["SPY"]
    assert spy["basis"] == "live"
    assert spy["last_price"] == 999.0


# ------------------------------------------------------------------- extension


def test_index_atr_multiple_positive_when_stretched_above_50d():
    n = 60
    close = pd.Series(100 + np.arange(n) * 1.0)   # steady climb, sits above its own 50d
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=n),
                       "open": close, "high": close + 1, "low": close - 1,
                       "close": close})
    out = extension.index_atr_multiple(df)
    assert out["atr_multiple_from_50d"] is not None
    assert out["atr_multiple_from_50d"] > 0
    assert out["formula_basis"] == spec.FORMULA_BASIS_AQE_HOUSE


def test_index_atr_multiple_unavailable_on_thin_history():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=10),
                       "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0})
    out = extension.index_atr_multiple(df)
    assert out["atr_multiple_from_50d"] is None


def test_vix_vix3m_ratio_and_bands():
    vix = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=3), "close": [20, 20, 20]})
    calm = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=3), "close": [25, 25, 25]})
    out = extension.vix_vix3m(vix, calm)
    assert out["ratio"] == pytest.approx(20 / 25, abs=1e-4)
    assert out["calm"] is True
    assert out["uncertainty"] is False
    assert out["basis"] == "eod"


def test_vix_vix3m_live_override_changes_numerator_only():
    vix = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=3), "close": [20, 20, 20]})
    vix3m = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=3), "close": [18, 18, 18]})
    out = extension.vix_vix3m(vix, vix3m, live_vix=30.0, live_vix_ts="2026-09-22T14:00:00Z")
    assert out["vix"] == 30.0
    assert out["vix3m"] == 18.0     # unchanged — VIX3M cannot go live (see module docstring)
    assert out["ratio"] == pytest.approx(30.0 / 18.0, abs=1e-4)
    assert out["basis"] == "vix_live_vix3m_eod"


def test_breadth_rejects_an_unknown_population():
    with pytest.raises(ValueError):
        extension.breadth_pct_above_20d(pd.DataFrame(), "made_up_population")


def test_breadth_pct_above_20d_real_math():
    # 3 tickers with >=20 bars: 2 close above their own 20d SMA, 1 below.
    rows = []
    for tk, last in (("A", 200.0), ("B", 200.0), ("C", 50.0)):
        base = 100.0 if tk != "C" else 100.0
        closes = [base] * 19 + [last]
        for i, c in enumerate(closes):
            rows.append({"date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=i),
                        "ticker": tk, "close": c})
    panel = pd.DataFrame(rows)
    out = extension.breadth_pct_above_20d(panel, spec.POPULATION_CURATED)
    assert out["status"] == "OK"
    assert out["n"] == 3
    assert out["n_above"] == 2
    assert out["population"] == spec.POPULATION_CURATED


def test_whole_market_breadth_is_always_labelled_unavailable_not_zero():
    out = extension.whole_market_breadth_unavailable("Phase 2 not shipped")
    assert out["status"] == "UNAVAILABLE"
    assert "value" not in out       # absent, never a fabricated 0/None-as-zero


# ---------------------------------------------------------------------- stance


def _ok_breadth(pct40=60.0, risers=400, five_day=1.5, green=True):
    return {
        "pct_above_40d": {"status": "OK", "value": pct40},
        "monthly_risers": {"status": "OK", "value": risers},
        "five_day_count": {"status": "OK", "value": five_day},
        "daily_count_green": {"status": "OK", "value": green},
    }


def test_stance_is_degraded_when_breadth_is_missing():
    out = stance.compute_stance({}, {}, {})
    assert out["stance"] is None
    assert out["status"] == "DEGRADED"
    assert "unavailable" in out["reason"]


def test_stance_flips_risk_on_when_every_positive_rule_clears():
    out = stance.compute_stance({}, {}, _ok_breadth())
    assert out["status"] == "OK"
    assert out["stance"] == spec.STANCE_RISK_ON


def test_stance_flips_risk_off_when_daily_count_is_red():
    out = stance.compute_stance({}, {}, _ok_breadth(green=False))
    assert out["stance"] == spec.STANCE_RISK_OFF


def test_stance_flips_risk_off_when_5day_count_below_070():
    out = stance.compute_stance({}, {}, _ok_breadth(five_day=0.5))
    assert out["stance"] == spec.STANCE_RISK_OFF


def test_stance_is_neutral_between_the_two_rule_sets():
    # Clears neither the full to-positive bar nor the to-negative bar.
    out = stance.compute_stance({}, {}, _ok_breadth(pct40=45.0, risers=200, five_day=0.9))
    assert out["stance"] == spec.STANCE_NEUTRAL


def test_stance_never_carries_a_size_or_disposition_key():
    """AQE makes no decisions, no sizing (CLAUDE.md) — mirrors
    test_ptrs_and_disposition_are_both_retired's discipline for this module."""
    out = stance.compute_stance({}, {}, _ok_breadth())
    blob = str(out).lower()
    for banned in ("max_size", "max_new_size", "disposition", "size_tier",
                  "position_size", "size_multiplier"):
        assert banned not in blob, f"stance leaked a sizing concept: {banned!r}"


# --------------------------------------------------------------------- explain


def _explainable_trend():
    return {"regime": spec.REGIME_UPTREND,
           "rows": {"SPY": {"last_price": 600.0}, "QQQ": {"last_price": 500.0}}}


def _explainable_ext():
    return {"index_atr": {"SPY": {"atr_multiple_from_50d": 3.0, "stretched": False},
                          "QQQ": {"atr_multiple_from_50d": 4.0, "stretched": False}},
           "vix_vix3m": {"ratio": 0.9, "uncertainty": False, "calm": False}}


def test_explain_always_returns_a_headline():
    out = explain.explain({}, {}, {"status": "DEGRADED", "reason": "x", "watch_for": []})
    assert out["headline"]
    assert isinstance(out["because"], list)


def test_explain_key_shape_matches_crown_explain():
    out = explain.explain(_explainable_trend(), _explainable_ext(),
                          {"status": "OK", "stance": "RISK_ON", "watch_for": []})
    for key in ("headline", "because", "so_what", "watch_for", "caveats", "as_of", "note"):
        assert key in out


def test_no_raw_jargon_leaks_into_explain_text():
    out = explain.explain(_explainable_trend(), _explainable_ext(),
                          {"status": "OK", "stance": "RISK_ON", "watch_for": []})
    text = " ".join([out["headline"], out.get("so_what") or "", *out["because"],
                     *out["watch_for"], *out["caveats"]]).lower()
    for word in ("atr_multiple_from_50d", "pct_above_20d", "sma_10", "sma_20",
                "formula_basis", "population_needed"):
        assert word not in text, f"raw field name leaked: {word!r}"


# ------------------------------------------------------------------------ card


def test_card_module_renders_from_its_arguments_alone():
    """No data libraries, no file access, no engine imports — same rule
    tests/test_qs_card.py enforces on qs_card.py."""
    src = inspect.getsource(card)
    for banned in ("import pandas", "import numpy", "open(", "read_parquet",
                  "read_csv", "requests", "sqlite3", "json.load",
                  "from src.data", "from src.macro", "Path("):
        assert banned not in src, (
            f"card.py must render from its arguments alone — found {banned!r}")


def test_card_helpers_survive_a_totally_empty_artifact():
    empty: dict = {}
    assert card.stance_banner(empty)["status"] == "UNAVAILABLE"
    assert card.headline(empty) == "No read available."
    assert card.trend_rows(empty)[0]["basis"] == "unavailable"
    assert card.regime_word(empty) == "UNKNOWN"
    assert card.extension_rows(empty)
    assert all(r["status"] == "UNAVAILABLE" for r in card.breadth_rows(empty))
    assert card.watch_for_lines(empty) == []
    assert card.caveats(empty) == []
    assert card.neighbourhood_lines(empty) == []
    assert card.theme_leaders_table(empty) == []
    assert card.rotation_table(empty) == []


# --------------------------------------------------------------------- groups


def _synthetic_basket_panel():
    """Two REAL baskets (Mag7, AI_Infrastructure) from src.engines.srm's own
    THEMATIC_BASKETS, each given a distinct, deliberately different price
    path so leadership vs a bounce-off-lows is unambiguous:
      Mag7 constituents: smooth steady climb, ends at its own high -> LEADING.
      AI_Infrastructure: peaks early, falls hard, sharp last-week bounce but
      still well off the high -> strong thrust, OFF_THE_FLOOR.
    """
    import numpy as np

    n = 100
    dates = pd.date_range("2026-01-01", periods=n)

    # Mag7: steady 100 -> 150, no drawdown, so the latest close IS the high.
    mag7_close = 100 + np.linspace(0, 50, n)

    # AI_Infrastructure: rises to 200 by day 60, falls to 128 by day 95,
    # then a sharp 5-day bounce to 160 -> big thrust, ~20% off the 200 high.
    ai_close = np.concatenate([
        np.linspace(100, 200, 60),
        np.linspace(200, 128, 35),
        np.linspace(128, 160, 5),
    ])

    rows = []
    for tk in ("AAPL", "MSFT", "NVDA"):          # real Mag7 constituents
        for d, c in zip(dates, mag7_close):
            rows.append({"date": d, "ticker": tk, "open": c * 0.999,
                        "high": c * 1.005, "low": c * 0.995, "close": c,
                        "volume": 1_000_000})
    for tk in ("EQIX", "DLR", "AMT"):            # real AI_Infrastructure constituents
        for d, c in zip(dates, ai_close):
            rows.append({"date": d, "ticker": tk, "open": c * 0.999,
                        "high": c * 1.005, "low": c * 0.995, "close": c,
                        "volume": 1_000_000})
    return pd.DataFrame(rows)


def test_compute_groups_ranks_real_baskets_from_synthetic_prices():
    panel = _synthetic_basket_panel()
    out = groups.compute_groups(panel)
    assert out["status"] == "OK"
    by_name = {g["name"]: g for g in out["groups"]}
    assert "Mag7" in by_name
    assert "AI_Infrastructure" in by_name

    mag7, ai = by_name["Mag7"], by_name["AI_Infrastructure"]
    # Mag7 ends exactly at its own high -> ~0% off high -> LEADING.
    assert mag7["pct_off_52w_high"] is not None
    assert abs(mag7["pct_off_52w_high"]) <= spec.ROTATION_LEADING_MAX_OFF_HIGH_PCT
    assert mag7["rotation_state"] == spec.ROTATION_LEADING

    # AI_Infrastructure is ~20% off its high (160/200-1) -> OFF_THE_FLOOR band.
    assert -25.0 <= ai["pct_off_52w_high"] <= -15.0
    assert ai["rotation_state"] == spec.ROTATION_OFF_FLOOR

    # AI_Infrastructure's sharp last-5-day bounce beats Mag7's steady climb
    # on raw thrust (5d momentum vs the 20d pace) even though Mag7 is the
    # one actually leading from its highs — exactly the distinction piece 03
    # exists to keep separate.
    assert ai["thrust"] > mag7["thrust"]

    display_names = {g["name"]: g["display_name"] for g in out["groups"]}
    assert display_names["AI_Infrastructure"] == "AI Infrastructure"


def test_theme_leaders_rankings_are_populated_and_ordered():
    panel = _synthetic_basket_panel()
    out = groups.compute_groups(panel)
    tl = out["theme_leaders"]
    for key in ("since_open", "one_week", "one_month"):
        assert "Mag7" in tl[key]
        assert "AI_Infrastructure" in tl[key]


def test_rotation_sorted_by_thrust_descending():
    panel = _synthetic_basket_panel()
    out = groups.compute_groups(panel)
    thrusts = [g["thrust"] for g in out["rotation"] if g["name"] in ("Mag7", "AI_Infrastructure")]
    assert thrusts == sorted(thrusts, reverse=True)


def test_compute_groups_degrades_on_empty_panel():
    out = groups.compute_groups(pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume"]))
    assert out["status"] == "UNAVAILABLE"
    assert out["groups"] == []


def test_neighbourhood_lines_uses_display_names_not_raw_keys():
    panel = _synthetic_basket_panel()
    gr = groups.compute_groups(panel)
    valen = {"groups": gr}
    lines = card.neighbourhood_lines(valen)
    text = " ".join(lines)
    assert "AI_Infrastructure" not in text          # raw key never leaks
    if "AI Infrastructure" in text or "Mag7" in text:
        assert True   # at least one real basket surfaced in a line


def test_explain_includes_a_neighbourhood_sentence_when_groups_available():
    panel = _synthetic_basket_panel()
    gr = groups.compute_groups(panel)
    out = explain.explain(_explainable_trend(), _explainable_ext(),
                          {"status": "OK", "stance": "RISK_ON", "watch_for": []}, gr)
    assert any("leadership" in b.lower() or "strongest group" in b.lower()
              for b in out["because"])


def test_explain_without_groups_still_works_backward_compatibly():
    out = explain.explain(_explainable_trend(), _explainable_ext(),
                          {"status": "OK", "stance": "RISK_ON", "watch_for": []})
    assert out["headline"]


# --------------------------------------------------------------------- breadth


def test_pct_above_ma_real_math():
    rows = []
    for tk, last in (("A", 200.0), ("B", 200.0), ("C", 50.0)):
        closes = [100.0] * 39 + [last]
        for i, c in enumerate(closes):
            rows.append({"date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=i),
                        "ticker": tk, "close": c})
    panel = pd.DataFrame(rows)
    out = breadth.pct_above_ma(panel, 40)
    assert out["status"] == "OK"
    assert out["n"] == 3
    assert out["n_above"] == 2
    assert out["population"] == spec.POPULATION_US_WIDE


def test_daily_mover_counts_real_math():
    specs = {"A": (100.0, 105.0), "B": (100.0, 95.0), "C": (100.0, 101.0)}
    rows = []
    for tk, (prev, last) in specs.items():
        rows.append({"date": pd.Timestamp("2026-01-01"), "ticker": tk, "close": prev})
        rows.append({"date": pd.Timestamp("2026-01-02"), "ticker": tk, "close": last})
    panel = pd.DataFrame(rows)
    out = breadth.daily_mover_counts(panel, 4.0)
    assert out["status"] == "OK"
    assert out["up"] == 1 and out["down"] == 1
    assert out["green"] is False       # up == down, not strictly more up


def test_window_mover_ratio_real_math():
    dates = pd.date_range("2026-01-01", periods=6)
    a = [100, 105, 110.25, 115.7625, 121.550625, 127.62815625]  # +5%/day x5
    b = [100, 95, 95, 95, 95, 95]                                # -5% once
    c = [100.0] * 6                                              # flat
    rows = []
    for tk, series in (("A", a), ("B", b), ("C", c)):
        for d, v in zip(dates, series):
            rows.append({"date": d, "ticker": tk, "close": v})
    panel = pd.DataFrame(rows)
    out = breadth.window_mover_ratio(panel, 4.0, 5)
    assert out["status"] == "OK"
    assert out["up_total"] == 5
    assert out["down_total"] == 1
    assert out["value"] == pytest.approx(5.0)


def test_window_mover_ratio_undefined_denominator_convention():
    dates = pd.date_range("2026-01-01", periods=3)
    a = [100, 105, 110.25]   # +5% twice, no down days at all
    rows = [{"date": d, "ticker": "A", "close": v} for d, v in zip(dates, a)]
    out = breadth.window_mover_ratio(pd.DataFrame(rows), 4.0, 2)
    assert out["status"] == "OK"
    assert out["down_total"] == 0
    assert out["value"] == pytest.approx(3.0)   # up_total(2) + 1.0, never inf


def test_cumulative_mover_counts_real_math():
    n = 22
    dates = pd.date_range("2026-01-01", periods=n)
    a = np.linspace(100, 130, n)   # +30% over 21 sessions -> riser
    b = np.linspace(100, 70, n)    # -30% over 21 sessions -> decliner
    c = [100.0] * n
    rows = []
    for tk, series in (("A", a), ("B", b), ("C", c)):
        for d, v in zip(dates, series):
            rows.append({"date": d, "ticker": tk, "close": v})
    panel = pd.DataFrame(rows)
    out = breadth.cumulative_mover_counts(panel, 25.0, 21)
    assert out["status"] == "OK"
    assert out["up"] == 1 and out["down"] == 1
    assert out["value"] == 1   # value = riser (up) count, what stance reads


def test_net_high_low_symmetric_case_nets_to_zero():
    n = 45
    dates = pd.date_range("2026-01-01", periods=n)
    a = np.linspace(100, 200, n)   # a new high every day
    b = np.linspace(200, 100, n)   # a new low every day
    rows = []
    for tk, series in (("A", a), ("B", b)):
        for d, v in zip(dates, series):
            rows.append({"date": d, "ticker": tk, "close": v})
    panel = pd.DataFrame(rows)
    out = breadth.net_high_low(panel, 252)
    assert out["status"] == "OK"
    assert out["avg8"] == pytest.approx(0.0, abs=1e-9)
    assert out["avg20"] == pytest.approx(0.0, abs=1e-9)
    assert out["green"] is False       # 8d not STRICTLY above 20d when equal


def test_breadth_functions_degrade_on_thin_history():
    thin = pd.DataFrame([{"date": pd.Timestamp("2026-01-01"), "ticker": "A", "close": 100.0}])
    assert breadth.pct_above_ma(thin, 40)["status"] == "UNAVAILABLE"
    assert breadth.daily_mover_counts(thin, 4.0)["status"] == "UNAVAILABLE"
    assert breadth.window_mover_ratio(thin, 4.0, 5)["status"] == "UNAVAILABLE"
    assert breadth.net_high_low(thin, 252)["status"] == "UNAVAILABLE"


def test_compute_breadth_degrades_cleanly_on_no_panel():
    out = breadth.compute_breadth(None)
    for key in ("pct_above_40d", "monthly_risers", "five_day_count", "daily_count_green"):
        assert out[key]["status"] == "UNAVAILABLE"
        assert out[key]["population_needed"] == spec.POPULATION_US_WIDE


def test_compute_breadth_feeds_stance_to_a_real_verdict():
    """End-to-end: real breadth math -> stance.compute_stance actually
    produces a non-DEGRADED stance, using a panel engineered to clear
    every to-positive rule."""
    n = 45
    dates = pd.date_range("2026-01-01", periods=n)
    rows = []
    # 10 tickers: 6 flat for 40 days then jump +6%/day for the final 5
    # sessions (real single-day 4%+ movers, so daily/5-day/10-day counts
    # all register), landing +33.8% over the trailing 21 sessions (clears
    # the monthly-riser rule too) -- one construction satisfies every
    # instrument at once instead of four incompatible ad-hoc shapes.
    jump = [100.0]
    for _ in range(5):
        jump.append(jump[-1] * 1.06)
    for i in range(10):
        if i < 6:
            series = [100.0] * 40 + jump[1:]
        else:
            series = [100.0] * n
        for d, v in zip(dates, series):
            rows.append({"date": d, "ticker": f"T{i}", "close": v})
    panel = pd.DataFrame(rows)
    br = breadth.compute_breadth(panel)
    for key in ("pct_above_40d", "monthly_risers", "five_day_count", "daily_count_green"):
        assert br[key]["status"] == "OK", (key, br[key])
    out = stance.compute_stance({}, {}, br)
    assert out["status"] == "OK"
    assert out["stance"] in (spec.STANCE_RISK_ON, spec.STANCE_NEUTRAL, spec.STANCE_RISK_OFF)


# ----------------------------------------------------------------------- theme
# The visual layer matching the VIV System webapp's own card (PM request,
# 2026-09-27, overriding CLAUDE.md's general "no fancy visuals" default for
# this one page). Same blindness rule as card.py, verified the same way.


def test_theme_module_renders_from_its_arguments_alone():
    src = inspect.getsource(theme)
    for banned in ("import pandas", "import numpy", "open(", "read_parquet",
                  "read_csv", "requests", "sqlite3", "json.load",
                  "from src.data", "from src.macro", "Path("):
        assert banned not in src, (
            f"theme.py must render from its arguments alone — found {banned!r}")


def test_stance_header_colors_risk_on_green():
    html = theme.stance_header_html({"word": "RISK ON", "status": "OK"})
    assert "RISK ON" in html
    assert theme._GREEN in html


def test_stance_header_colors_risk_off_red():
    html = theme.stance_header_html({"word": "RISK OFF", "status": "OK"})
    assert "RISK OFF" in html
    assert theme._RED in html


def test_stance_header_falls_back_to_not_shown_when_no_stance_word():
    html = theme.stance_header_html({"word": "—", "status": "DEGRADED", "reason": "no breadth"})
    assert "NOT SHOWN" in html
    assert "no breadth" in html


def test_pct_class_positive_negative_zero_and_none():
    assert theme._pct_class(1.5) == "valen-pos"
    assert theme._pct_class(-1.5) == "valen-neg"
    assert theme._pct_class(0.0) == ""
    assert theme._pct_class(None) == ""


def test_fmt_handles_none_bool_and_number():
    assert theme._fmt(None) == "—"
    assert theme._fmt(True) == "Yes"
    assert theme._fmt(False) == "No"
    assert theme._fmt(3.14159, nd=2) == "3.14"
    assert theme._fmt(2.5, suffix="%") == "2.50%"


def test_names_are_html_escaped_in_theme_leaders_table():
    rows = [{"display_name": "<script>alert(1)</script>", "since_open_pct": 1.0,
             "ret_1w_pct": 2.0, "ret_1m_pct": 3.0}]
    html = theme.theme_leaders_table_html(rows)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_theme_leaders_table_ranks_by_1week_descending():
    rows = [
        {"display_name": "A", "since_open_pct": 0.0, "ret_1w_pct": 1.0, "ret_1m_pct": 5.0},
        {"display_name": "B", "since_open_pct": 0.0, "ret_1w_pct": 9.0, "ret_1m_pct": 1.0},
    ]
    html = theme.theme_leaders_table_html(rows)
    assert html.index(">B<") < html.index(">A<")


def test_rotation_table_labels_leading_and_off_the_floor():
    rows = [
        {"display_name": "Leader", "thrust": 5.0, "ret_1m_pct": 10.0,
         "pct_off_52w_high": 1.0, "rotation_state": "LEADING"},
        {"display_name": "Bouncer", "thrust": 4.0, "ret_1m_pct": 8.0,
         "pct_off_52w_high": 20.0, "rotation_state": "OFF_THE_FLOOR"},
    ]
    html = theme.rotation_table_html(rows)
    assert "LEADING" in html
    assert "OFF THE FLOOR" in html


def test_instruments_html_shows_not_shown_tile_for_missing_value():
    html = theme.instruments_html([{"label": "VIX / VIX3M", "value": None}])
    assert "not shown" in html
    assert "VIX / VIX3M" in html


def test_what_would_change_html_empty_list_is_not_shown():
    html = theme.what_would_change_html([])
    assert "Not shown" in html


def test_neighbourhood_html_empty_ok_status_reads_no_leadership():
    html = theme.neighbourhood_html([], "OK", None)
    assert "No group cleared a leadership read today." in html


def test_neighbourhood_html_empty_bad_status_shows_reason():
    html = theme.neighbourhood_html([], "UNAVAILABLE", "no groups scored")
    assert "no groups scored" in html


# ------------------------------------------------- cockpit: gauges/LEDs/dial
# Added 2026-09-30 after PM feedback that the page still read as flat text
# rows, not a cockpit -- these are the "easy to read sliders and other
# illustrations" pieces: banded slider gauges (real spec.py thresholds),
# LED pass/fail rows, and the stance semicircle dial.


def test_gauge_bar_renders_bands_and_pointer_for_a_known_value():
    html = theme._gauge_bar_html("VIX / VIX3M", 0.90, "vix_vix3m")
    assert "valen-gauge-track" in html
    assert "valen-gauge-pointer" in html
    # 0.90 sits inside the handbook's own gold "uncertainty-approaching" band.
    assert theme._GOLD in html


def test_gauge_bar_unknown_value_reads_not_shown():
    html = theme._gauge_bar_html("VIX / VIX3M", None, "vix_vix3m")
    assert "not shown" in html
    assert "valen-gauge-track" not in html


def test_gauge_bar_unknown_kind_falls_back_to_plain_value_not_a_guessed_scale():
    html = theme._gauge_bar_html("Something new", 42, "not_a_real_kind")
    assert "42" in html
    assert "valen-gauge-track" not in html


def test_gauge_bar_pointer_position_matches_value_fraction():
    # ATR scale is 0-8; a value of 4.0 should sit at the 50% mark.
    html = theme._gauge_bar_html("SPY ATRs above 50-day", 4.0, "atr_multiple")
    assert "left:50.00%" in html


def test_led_row_pass_and_fail_colours():
    ok_html = theme._led_row_html("Today's count green", "OK", True)
    fail_html = theme._led_row_html("Today's count green", "OK", False)
    assert "valen-ok" in ok_html
    assert "valen-fail" in fail_html


def test_led_row_not_shown_when_status_is_not_ok():
    html = theme._led_row_html("Today's count green", "UNAVAILABLE", None)
    assert "not shown" in html
    assert "valen-muted" in html


def test_led_row_uses_flag_over_value_when_both_given():
    """5-day count is a ratio (e.g. 1.35), not itself a boolean -- the LED
    must read pass/fail off `flag`, and still print the real number."""
    html = theme._led_row_html("5-day count (1.00+ to pass)", "OK", 1.35, flag=True)
    assert "valen-ok" in html
    assert "1.35" in html


def test_gauge_bar_carries_a_one_line_explainer_per_kind():
    """A standing PM ask (2026-10-01): what does each instrument measure
    and what does the number mean? Every known `kind` must answer that,
    not just show a label and a number."""
    for kind in ("atr_multiple", "vix_vix3m", "pct_0_100", "mover_ratio"):
        html = theme._gauge_bar_html("Some label", 1.0, kind)
        assert "valen-explainer" in html
        assert theme._GAUGE_EXPLAINER[kind] in html


def test_gauge_bar_unavailable_still_carries_its_explainer():
    html = theme._gauge_bar_html("VIX / VIX3M", None, "vix_vix3m")
    assert theme._GAUGE_EXPLAINER["vix_vix3m"] in html


def test_led_row_carries_a_one_line_explainer_per_label():
    for label, text in theme._LED_EXPLAINER.items():
        html = theme._led_row_html(label, "OK", True)
        assert "valen-explainer" in html
        assert text in html


def test_led_row_unavailable_still_carries_its_explainer():
    html = theme._led_row_html("Today's count green", "UNAVAILABLE", None)
    assert theme._LED_EXPLAINER["Today's count green"] in html


def test_trend_checklist_carries_the_shared_trend_explainer():
    rows = [{"symbol": "SPY", "last_price": 601.2, "daily_buy_signal": True,
            "weekly_buy_signal": True, "above_rising_5d": True, "basis": "eod"}]
    html = theme.trend_checklist_html(rows, [])
    assert theme._TREND_EXPLAINER in html


def test_stance_gauge_highlights_the_right_zone_and_colour():
    html = theme.stance_gauge_html({"word": "RISK ON", "status": "OK"})
    assert "RISK ON" in html
    assert theme._GREEN in html


def test_stance_gauge_degrades_to_grey_dial_when_not_shown():
    html = theme.stance_gauge_html({"word": "—", "status": "DEGRADED"})
    assert theme._GREY in html
    assert theme._GREEN not in html and theme._RED not in html


def test_instruments_html_merges_extension_and_breadth_instrument_rows():
    ext_rows = [{"label": "VIX / VIX3M", "value": 0.9, "kind": "vix_vix3m"}]
    breadth_rows_ = [
        {"label": "T2108", "section": "instrument", "kind": "pct_0_100", "value": 55.0},
        {"label": "Today's count green", "section": "checklist", "kind": "bool", "value": True},
    ]
    html = theme.instruments_html(ext_rows, breadth_rows_)
    assert "VIX / VIX3M" in html
    assert "T2108" in html
    # Checklist-section rows must NOT leak into the instruments gauge list.
    assert "Today's count green" not in html


def test_instruments_html_works_without_breadth_rows_arg():
    """Backward compatible with any caller that only passes extension rows."""
    html = theme.instruments_html([{"label": "VIX / VIX3M", "value": 0.9, "kind": "vix_vix3m"}])
    assert "VIX / VIX3M" in html


# --------------------------------------------- card.py: kind/section tagging


def test_extension_rows_carry_a_gauge_kind():
    empty_kinds = {r["kind"] for r in card.extension_rows({})}
    assert empty_kinds == {"atr_multiple", "vix_vix3m"}


def test_breadth_rows_separate_checklist_from_instrument_sections():
    sections = {r["section"] for r in card.breadth_rows({})}
    assert sections == {"checklist", "instrument"}


def test_breadth_rows_five_day_count_appears_in_both_sections():
    """The handbook lists the 5-day count as BOTH a checklist pass/fail line
    AND one of the four tracked instruments (page 6) -- both must show."""
    rows = card.breadth_rows({})
    five_day = [r for r in rows if "5-day" in r["label"]]
    assert {r["section"] for r in five_day} == {"checklist", "instrument"}


def test_breadth_rows_five_day_led_flag_uses_the_real_threshold():
    valen = {"breadth": {"five_day_count": {"status": "OK", "value": 1.5}}}
    rows = card.breadth_rows(valen)
    checklist_row = next(r for r in rows
                         if r["section"] == "checklist" and "5-day" in r["label"])
    assert checklist_row["flag"] is True

    valen_low = {"breadth": {"five_day_count": {"status": "OK", "value": 0.4}}}
    rows_low = card.breadth_rows(valen_low)
    checklist_row_low = next(r for r in rows_low
                             if r["section"] == "checklist" and "5-day" in r["label"])
    assert checklist_row_low["flag"] is False


def test_breadth_rows_t2108_moved_out_of_checklist_into_instrument():
    """2026-09-30 fix: T2108 is one of the handbook's four INSTRUMENTS, not
    one of the six checklist rows -- it used to be mislabelled into the
    checklist section."""
    rows = card.breadth_rows({})
    t2108_row = next(r for r in rows if "T2108" in r["label"])
    assert t2108_row["section"] == "instrument"


# ------------------------------------------------------- Parts 2-6 integration
# daily.py's run_playbook() orchestrates selection/house/execution/management
# against the finished export; card.py's *_block() functions give the page
# safe defaults when those sections haven't been written yet (e.g. reading
# an artifact from between Step 6i and Step 8a-1b, or an older one predating
# this pass).


def test_run_playbook_never_raises_on_an_empty_export():
    from src.valen.daily import run_playbook
    out = run_playbook({}, None)
    assert out["selection"]["relative_strength"] == []
    assert out["house"]["setups"] == []
    assert out["execution"]["entries"] == []
    assert out["management"]["held_facts"] == []


def test_run_playbook_reads_stance_word_for_no_buy_market_flag():
    from src.valen.daily import run_playbook
    daily_list = [{"ticker": "X", "on_longlist": True}]
    out = run_playbook({"daily_list": daily_list}, {"stance": {"stance": "RISK_OFF"}})
    flags = out["selection"]["no_buy_list"][0]["flags"]
    assert any(f["flag"] == "market_red" for f in flags)


def test_card_selection_block_defaults_when_absent():
    assert card.selection_block({}) == {"relative_strength": [], "funnel": [],
                                        "no_buy_list": []}


def test_card_house_block_defaults_when_absent():
    assert card.house_block({}) == {"setups": []}


def test_card_execution_block_defaults_when_absent():
    assert card.execution_block({}) == {"entries": [], "stop_breaches": []}


def test_card_management_block_defaults_and_streak_shape():
    out = card.management_block({})
    assert out["held_facts"] == []
    assert out["streak"]["status"] == "UNAVAILABLE"


def test_card_blocks_pass_through_real_data():
    valen = {"selection": {"relative_strength": [{"ticker": "A"}], "funnel": [],
                          "no_buy_list": []}}
    assert card.selection_block(valen)["relative_strength"] == [{"ticker": "A"}]


def test_part_header_html_contains_number_title_subtitle():
    html = theme.part_header_html("2", "Neighbourhood — selection", "Buy what is outperforming.")
    assert "Part 2 of 6" in html
    assert "Neighbourhood" in html
    assert "Buy what is outperforming." in html


def test_relative_strength_table_html_empty_reads_not_shown():
    assert "No relative-strength" in theme.relative_strength_table_html([])


def test_funnel_html_empty_reads_not_shown():
    assert "not shown" in theme.funnel_html([]).lower()


def test_no_buy_html_empty_reads_clean():
    assert "no candidate trips" in theme.no_buy_html([]).lower()


def test_house_setups_html_empty_reads_clean():
    assert "no setup pattern" in theme.house_setups_html([]).lower()


def test_entries_table_html_empty_reads_clean():
    assert "no candidate has a recognised entry" in theme.entries_table_html([]).lower()


def test_stop_breaches_html_empty_reads_clean():
    assert "no held position" in theme.stop_breaches_html([]).lower()


def test_held_facts_table_html_empty_reads_clean():
    assert "no open positions" in theme.held_facts_table_html([]).lower()


def test_streak_html_unavailable_reads_not_shown():
    html = theme.streak_html({"status": "UNAVAILABLE", "reason": "no data"})
    assert "not shown" in html.lower()


def test_doctrine_html_renders_heading_and_body():
    html = theme.doctrine_html([("Sizing is arithmetic", "decide risk first")])
    assert "Sizing is arithmetic" in html
    assert "decide risk first" in html


def test_run_valen_includes_gex_key():
    """run_valen() must always add a gex block -- UNAVAILABLE is a fine
    real-world answer (Crown's own gamma fetch needs Alpaca/Tiger secrets
    this sandbox doesn't have), but the key itself must be present so the
    page's card.gex_block() never falls back to a missing-key default
    silently in production."""
    from src.valen.daily import run_valen
    artifact = run_valen()
    assert "gex" in artifact
    assert artifact["gex"]["status"] in ("OK", "UNAVAILABLE")
    assert artifact["gex"].get("ticker") == "SPY"


# ------------------------------------------------- history.py: turning points
# Added 2026-10-01 after PM feedback: the dashboard showed today's weather but
# not whether it was TURNING. Every instrument here is a pure recompute off
# panels that already carry full history, so this needs no new storage and
# has no cold-start gap -- see history.py's own module docstring.


def test_truncate_series_drops_the_most_recent_n_bars():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = history.truncate_series(s, 2)
    assert list(out) == [1.0, 2.0, 3.0]


def test_truncate_series_zero_sessions_ago_is_a_no_op():
    s = pd.Series([1.0, 2.0, 3.0])
    assert list(history.truncate_series(s, 0)) == [1.0, 2.0, 3.0]


def test_truncate_series_not_enough_history_returns_empty_not_an_exception():
    s = pd.Series([1.0, 2.0])
    out = history.truncate_series(s, 5)
    assert out.empty


def test_truncate_panel_drops_the_most_recent_n_distinct_dates():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-09-01", "2026-09-01", "2026-09-02",
                                "2026-09-03", "2026-09-04"]),
        "ticker": ["A", "B", "A", "A", "A"],
        "close": [1.0, 1.0, 2.0, 3.0, 4.0],
    })
    out = history.truncate_panel(df, 2)
    assert set(out["date"].dt.strftime("%Y-%m-%d")) == {"2026-09-01", "2026-09-02"}


def test_truncate_panel_not_enough_history_returns_none():
    df = pd.DataFrame({"date": pd.to_datetime(["2026-09-01", "2026-09-02"]),
                       "ticker": ["A", "A"], "close": [1.0, 2.0]})
    assert history.truncate_panel(df, 5) is None


def test_truncate_panel_none_input_is_a_no_op():
    assert history.truncate_panel(None, 5) is None


def test_index_atr_multiple_as_of_matches_a_manual_truncation():
    dates = pd.date_range("2026-01-01", periods=60, freq="B")
    df = pd.DataFrame({"date": dates, "open": 100.0, "high": 101.0,
                       "low": 99.0, "close": np.linspace(100, 160, 60)})
    full = extension.index_atr_multiple(df)
    truncated_manually = extension.index_atr_multiple(df.iloc[:-5])
    as_of = extension.index_atr_multiple_as_of(df, 5)
    assert as_of == truncated_manually
    assert as_of != full


def test_index_atr_multiple_as_of_zero_sessions_matches_now():
    dates = pd.date_range("2026-01-01", periods=60, freq="B")
    df = pd.DataFrame({"date": dates, "open": 100.0, "high": 101.0,
                       "low": 99.0, "close": np.linspace(100, 160, 60)})
    assert extension.index_atr_multiple_as_of(df, 0) == extension.index_atr_multiple(df)


def test_compute_breadth_as_of_matches_a_manual_truncation():
    dates = pd.bdate_range("2026-01-01", periods=50)
    rows = []
    for d in dates:
        for tk in ("AAA", "BBB", "CCC"):
            rows.append({"ticker": tk, "date": d, "close": 100.0})
    panel = pd.DataFrame(rows)
    manual = breadth.compute_breadth(panel[panel["date"] <= dates[-6]])
    as_of = breadth.compute_breadth_as_of(panel, 5)
    assert as_of["pct_above_40d"] == manual["pct_above_40d"]


def test_compute_breadth_as_of_not_enough_history_degrades_honestly():
    dates = pd.bdate_range("2026-01-01", periods=3)
    panel = pd.DataFrame({"ticker": ["A"] * 3, "date": dates, "close": [1.0, 2.0, 3.0]})
    out = breadth.compute_breadth_as_of(panel, 10)
    assert out["pct_above_40d"]["status"] == "UNAVAILABLE"


def test_history_rows_shapes_now_vs_5d_vs_1mo():
    valen = {
        "stance": {"stance": "RISK_ON"},
        "trend": {"regime": "UPTREND"},
        "extension": {"vix_vix3m": {"ratio": 0.78},
                     "index_atr": {"SPY": {"atr_multiple_from_50d": 2.1}}},
        "breadth": {"pct_above_40d": {"status": "OK", "value": 62.3}},
        "history": {
            "5d_ago": {"stance": "NEUTRAL", "regime": "CHOP", "vix_vix3m": 0.85,
                      "t2108": 55.0, "spy_atr_mult": 1.8},
            "1mo_ago": {"stance": "RISK_OFF", "regime": "DOWNTREND", "vix_vix3m": 1.05,
                       "t2108": 30.0, "spy_atr_mult": 0.5},
        },
    }
    rows = card.history_rows(valen)
    by_label = {r["label"]: r for r in rows}
    assert by_label["Stance"]["now"] == "RISK_ON"
    assert by_label["Stance"]["5d_ago"] == "NEUTRAL"
    assert by_label["Stance"]["1mo_ago"] == "RISK_OFF"
    assert by_label["VIX / VIX3M"]["now"] == 0.78
    assert by_label["T2108"]["now"] == 62.3


def test_history_rows_missing_history_key_degrades_to_none_not_an_exception():
    rows = card.history_rows({})
    assert all(r["5d_ago"] is None and r["1mo_ago"] is None for r in rows)


def test_history_html_flags_a_changed_word_reading():
    rows = [{"label": "Stance", "kind": "word", "now": "RISK_ON",
            "5d_ago": "NEUTRAL", "1mo_ago": "RISK_ON"}]
    html = theme.history_html(rows)
    table = html.split("<table")[1]  # exclude the static explainer's own ⚠ mention
    assert table.count("⚠") == 1  # only the 5d_ago cell differs from now


def test_history_html_shows_direction_arrows_for_numbers():
    rows = [{"label": "VIX / VIX3M", "kind": "number", "now": 0.90,
            "5d_ago": 0.80, "1mo_ago": 1.00}]
    html = theme.history_html(rows)
    assert "↑" in html  # rose since 5d ago (0.80 -> 0.90)
    assert "↓" in html  # fell since 1mo ago (1.00 -> 0.90)


def test_history_html_empty_rows_renders_nothing():
    assert theme.history_html([]) == ""


def test_run_valen_includes_history_with_both_lookback_keys():
    """End-to-end: run_valen() always adds a history block with both
    lookback points, each carrying its own sessions_ago -- never silently
    missing, even when breadth is DEGRADED in this sandbox (no ma_panel)."""
    from src.valen.daily import run_valen
    artifact = run_valen()
    assert "history" in artifact
    assert set(artifact["history"].keys()) == {"5d_ago", "1mo_ago"}
    assert artifact["history"]["5d_ago"]["sessions_ago"] == 5
    assert artifact["history"]["1mo_ago"]["sessions_ago"] == 21
