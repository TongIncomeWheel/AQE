"""The three reading sections: what changed, what is coming, where the lines are.

Crown's letter leads with a shift, a short dated calendar, and a levels table.
Copying the shape is easy; the things that make it useful are easy to lose:

  * a levels table that is only prices wastes what this layer computes, since
    the levels that decide the regime here are mostly a breadth ratio, a
    volatility gap and a correlation percentile
  * a "what changed" list padded with unchanged fields buries the one line that
    matters, so silence has to be a real answer
  * a calendar entry without a reason is a date, and the reader already has a
    calendar app
"""

from __future__ import annotations

from datetime import date

from src.macro.crown import calendar as CAL
from src.macro.crown import changes as CH
from src.macro.crown import levels as L

TODAY = date(2026, 8, 10)

CROWN = {
    "generated_at": "2026-08-10T09:00:00+08:00",
    "heartbeat": {"regime": "narrowing", "range_position": "mid", "ratio": 0.3300,
                  "series": {"range_high": 0.3450, "range_low": 0.3280,
                             "ma_20": [0.3310]}},
    "volatility": {
        "vix": 14.9,
        "dispersion": {"state": "ELEVATED_EASING", "spread": 24.74,
                       "series": {"band_elevated": 23.0, "band_calm": 16.9}},
        "corroboration": {"implied_correlation": 7.38,
                          "correlation_percentile": 0.06},
    },
    "cta": {"overall_bias": "risk_on", "flip_risk": 0.11},
    "cta_markets": {
        "ZT": {"signal": -0.38, "label": "UST 2Y note",
               "flips": [{"horizon": 1, "level": 103.65, "spot": 102.96,
                          "distance_pct": 0.67, "direction": "buy_above"},
                         {"horizon": 20, "level": 104.0, "spot": 102.96,
                          "distance_pct": 1.0, "direction": "buy_above"}]},
        "ES": {"signal": 0.57, "label": "S&P 500",
               "flips": [{"horizon": 1, "level": 7014.3, "spot": 7790.0,
                          "distance_pct": -9.96, "direction": "sell_below"}]},
    },
    "gamma": {"status": "OK", "regime": "POSITIVE",
              "underlyings": {"SPY": {"spot": 773.92, "gamma_flip": 776.88,
                                      "flip_distance_pct": 0.38,
                                      "call_wall": {"strike": 785.0},
                                      "put_wall": {"strike": 750.0}}}},
    "cot": {"crowded_long": ["GC", "HG"], "crowded_short": ["ZN"]},
    "decision": {"expression": {"family": "NARROWING_CONCENTRATED"}},
    "freshness": {"cta_markets": {"ZT": {"via": "etf_fallback"},
                                  "ES": {"via": "yahoo_futures"}}},
}


# ─────────────────────────────────────────────── key levels

def test_the_table_is_not_only_prices():
    """The point of the section. A levels table that stops at prices throws
    away the breadth, volatility and correlation levels this layer computes."""
    kinds = set(L.build(CROWN)["by_kind"])
    assert {"breadth", "volatility", "correlation"} <= kinds
    assert "dealer positioning" in kinds and "trend followers" in kinds


def test_the_golden_ratio_gets_its_own_levels():
    rows = [r for r in L.build(CROWN)["levels"] if r["kind"] == "breadth"]
    what = " ".join(r["what"] for r in rows)
    assert "12-month high" in what and "12-month low" in what
    assert "20-day average" in what
    assert all(r["unit"] == "ratio" for r in rows)


def test_volatility_and_correlation_levels_are_quoted_in_their_own_units():
    rows = L.build(CROWN)["levels"]
    vol = [r for r in rows if r["kind"] == "volatility"]
    corr = [r for r in rows if r["kind"] == "correlation"]
    assert vol and all(r["unit"] == "vol points" for r in vol)
    assert corr and corr[0]["unit"] == "percentile"


def test_every_level_says_what_happens_if_it_breaks():
    """A level without a consequence is a number. The consequence is the row."""
    for r in L.build(CROWN)["levels"]:
        assert r["if_it_breaks"] and len(r["if_it_breaks"]) > 30


def test_rows_are_sorted_nearest_first():
    rows = [r for r in L.build(CROWN)["levels"] if r["distance_pct"] is not None]
    d = [abs(r["distance_pct"]) for r in rows]
    assert d == sorted(d), "the line about to be crossed must be at the top"


def test_only_the_one_day_flip_reaches_the_table():
    rows = [r for r in L.build(CROWN)["levels"] if "UST 2Y" in r["what"]]
    assert len(rows) == 1 and rows[0]["level"] == 103.65


def test_an_etf_proxied_level_is_marked_unquotable():
    by = {r["what"]: r for r in L.build(CROWN)["levels"]}
    assert by["UST 2Y note flip"]["quotable_as_contract"] is False
    assert by["S&P 500 flip"]["quotable_as_contract"] is True


def test_a_thin_read_produces_a_table_rather_than_an_exception():
    out = L.build({})
    assert out["count"] == 0 and out["levels"] == []


# ─────────────────────────────────────────────── what changed

def _prev(**over):
    import copy
    p = copy.deepcopy(CROWN)
    for path, val in over.items():
        node, *rest = path.split(".")
        cur = p[node]
        for k in rest[:-1]:
            cur = cur[k]
        cur[rest[-1]] = val
    return p


def test_a_regime_flip_is_reported_as_a_new_starting_point():
    out = CH.diff(CROWN, _prev(**{"heartbeat.regime": "broadening"}))
    assert any("flipped from broadening to narrowing" in c for c in out["changes"])
    assert any("gated on" in c for c in out["changes"])


def test_the_gap_turning_from_widening_to_closing_says_it_reverses_the_trade():
    """The single most consequential change this layer can report."""
    out = CH.diff(CROWN, _prev(**{"volatility.dispersion.state": "ELEVATED_RISING"}))
    joined = " ".join(out["changes"])
    assert "reverses the downside trade" in joined
    assert "leaving rather than building" in joined


def test_the_gap_turning_from_closing_to_widening_says_it_is_actionable():
    today = _prev(**{"volatility.dispersion.state": "ELEVATED_RISING"})
    out = CH.diff(today, CROWN)
    assert any("worth acting on" in c for c in out["changes"])


def test_a_market_crossing_its_own_flip_is_named():
    prev = _prev()
    prev["cta_markets"]["ES"]["signal"] = -0.2      # was short, now long
    out = CH.diff(CROWN, prev)
    assert any("S&P 500 crossed its trend flip" in c and "long" in c
               for c in out["changes"])


def test_new_and_departed_crowding_are_both_reported():
    prev = _prev()
    prev["cot"] = {"crowded_long": ["HG", "DX"], "crowded_short": []}
    out = " ".join(CH.diff(CROWN, prev)["changes"])
    assert "became crowded long GC" in out
    assert "no longer crowded long DX" in out
    assert "became crowded short ZN" in out


def test_an_unchanged_read_says_nothing_rather_than_padding():
    """Silence is a real answer. A list of unchanged fields buries the one line
    that matters."""
    out = CH.diff(CROWN, CROWN)
    assert out["changes"] == []
    assert "continuation" in out["note"]


def test_the_first_ever_run_says_so_instead_of_inventing_a_comparison():
    out = CH.diff(CROWN, None)
    assert out["available"] is False and out["changes"] == []


# ─────────────────────────────────────────────── the calendar

ECON = [
    {"date": "2026-08-12 08:30:00", "country": "US",
     "event": "Consumer Price Index (CPI) YoY", "previous": "2.9%", "estimate": "2.8%"},
    {"date": "2026-08-13 08:30:00", "country": "US",
     "event": "Producer Price Index (PPI) MoM", "previous": "0.2%"},
    {"date": "2026-08-14 08:30:00", "country": "US", "event": "Retail Sales MoM"},
    {"date": "2026-08-12 09:00:00", "country": "DE", "event": "German CPI"},
    {"date": "2026-09-30 08:30:00", "country": "US", "event": "Consumer Price Index"},
    {"date": "2026-08-12 10:00:00", "country": "US", "event": "Cheese Stocks"},
]


def test_only_us_prints_inside_the_window_survive():
    out = CAL.parse_economic_rows(ECON, TODAY, days=10)
    names = [e["event"] for e in out]
    assert not any("German" in n for n in names)
    assert not any(e["date"] > "2026-08-20" for e in out)


def test_an_event_with_nothing_to_say_about_it_is_dropped():
    """A date with no reason attached is something the reader's calendar app
    already gives them."""
    out = CAL.parse_economic_rows(ECON, TODAY, days=10)
    assert not any("Cheese" in e["event"] for e in out)
    assert all(e["what_it_tests"] for e in out)


def test_cpi_and_ppi_carry_the_reason_they_are_on_the_list():
    out = {e["event"]: e for e in CAL.parse_economic_rows(ECON, TODAY, days=10)}
    cpi = next(v for k, v in out.items() if "Consumer Price" in k)
    ppi = next(v for k, v in out.items() if "Producer Price" in k)
    assert "easing case" in cpi["what_it_tests"]
    assert "input costs" in ppi["what_it_tests"]
    assert cpi["day"] == "Wednesday"


def test_earnings_are_filtered_to_names_that_can_move_this_book():
    cal = {"NVDA": "2026-08-12", "AMAT": "2026-08-13", "RANDOM": "2026-08-12"}
    out = CAL.select_earnings(cal, TODAY, held={"NVDA"}, watched={"AMAT"})
    tickers = [e["ticker"] for e in out]
    assert tickers == ["NVDA", "AMAT"], "held first, then watched, then nothing"
    assert "You hold this" in out[0]["what_it_tests"]
    assert "RANDOM" not in tickers


def test_the_calendar_never_forecasts_an_outcome():
    out = CAL.build.__doc__ or ""
    blob = " ".join(e["what_it_tests"] for e in
                    CAL.parse_economic_rows(ECON, TODAY, days=10)).lower()
    for word in ("will rise", "will fall", "we expect", "forecast"):
        assert word not in blob
