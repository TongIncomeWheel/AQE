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

from src.valen import card, explain, extension, spec, stance, trend

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
