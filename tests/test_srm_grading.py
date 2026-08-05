"""SRM grading — the acceleration path, the removed cap, and breadth.

Every test here is anchored to a real reading from the 2026-08-05 export,
because the defect was invisible from the code and obvious from the board:
21 of 35 baskets read HOLD, and the fastest theme on the tape (Cybersecurity,
+11.7% in five sessions while LEADING the RRG) sat in the same bucket as one
that had gone nowhere for a month.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engines import srm as S


def _bars(prices: list[float]) -> pd.DataFrame:
    """A daily frame long enough to grade (>= 25 bars), ending on `prices`."""
    pad = [prices[0]] * (30 - len(prices))
    close = pad + prices
    return pd.DataFrame({
        "date": pd.date_range("2026-06-01", periods=len(close), freq="D"),
        "close": close,
    })


def _shaped(roc20: float, roc5: float, above_sma20: bool = True) -> pd.DataFrame:
    """Bars engineered to hit an EXACT roc20 / roc5 with a chosen SMA side.

    Not a realistic price path and not trying to be — grade_sector_etf reads
    exactly three things (roc20, roc5, price vs the 20D SMA), so the fixture
    pins those three and leaves the rest flat. A prettier curve would only
    make the inputs harder to reason about.

    Three bars are load-bearing: close[-1] (today), close[-6] (roc5 anchor) and
    close[-21] (roc20 anchor). The other 18 bars inside the SMA window are free,
    so they are set to whatever level puts the mean on the requested side.
    """
    n, last = 40, 100.0
    close = np.full(n, last)
    close[-21] = last / (1 + roc20 / 100.0)
    close[-6] = last / (1 + roc5 / 100.0)
    # mean(close[-20:]) = (close[-6] + last + 18*level) / 20; solve for the
    # level that puts the SMA either side of today's close, then step off it.
    pivot = (20 * last - close[-6] - last) / 18.0
    level = pivot * (0.97 if above_sma20 else 1.03)
    free = [i for i in range(n - 20, n) if i not in (n - 6, n - 1)]
    close[free] = level
    close[:n - 21] = close[-21]
    return pd.DataFrame({
        "date": pd.date_range("2026-06-01", periods=n, freq="D"),
        "close": close,
    })


# ─────────────────────────────────────────────── the acceleration path

def test_cybersecurity_the_name_that_started_this_no_longer_reads_hold():
    """2026-08-05: roc20 +1.8%, roc5 +11.7%, above SMA20, RRG LEADING.

    The old ladder had one road to DEPLOY (roc20 > 5%), so a theme that turned
    three weeks ago could not pass it however hard it was running — the earlier
    drawdown still sat inside the 20-day window. PM: "cyber security still
    lags, shows hold". It was not lagging; the window was stale.
    """
    g = S.grade_sector_etf(_shaped(roc20=1.8, roc5=11.74))
    assert g["above_sma20"] is True
    assert g["grade"] == "DEPLOY"
    assert g["grade_path"] == "acceleration"


def test_a_good_week_inside_a_slow_month_is_still_hold():
    """Mag7 on the same board: +8.4% in five days but only 4.9 ahead of the
    20-day pace. Real, not an acceleration — the threshold has to bite."""
    g = S.grade_sector_etf(_shaped(roc20=3.47, roc5=8.39))
    assert g["grade"] == "HOLD"


def test_the_trend_road_to_deploy_is_untouched():
    g = S.grade_sector_etf(_shaped(roc20=13.64, roc5=9.08))
    assert g["grade"] == "DEPLOY" and g["grade_path"] == "trend"


def test_a_violent_bounce_off_a_hole_is_not_a_deploy():
    """Solar_Renewables 2026-08-05: -9.2% on the month, +18.6% in a week.

    Without the roc20 >= 0 guard the acceleration path would call this a place
    to put money. It is a bounce; it grades TURNING — 'recovering from
    weakness, watch for entry' — which is the honest reading and still an
    upgrade on the WATCH it used to get.
    """
    g = S.grade_sector_etf(_shaped(roc20=-9.24, roc5=18.63))
    assert g["grade"] == "TURNING"
    assert g["grade_path"] == "recovery"


def test_the_recovery_path_needs_real_thrust_not_merely_a_green_week():
    g = S.grade_sector_etf(_shaped(roc20=-2.45, roc5=0.05))
    assert g["grade"] == "WATCH" and g["grade_path"] == "stalled"


def test_every_grade_says_which_rule_produced_it():
    for roc20, roc5 in ((13.6, 9.1), (1.8, 11.7), (2.2, 1.9), (-3.2, 15.6),
                        (-2.5, 0.1)):
        g = S.grade_sector_etf(_shaped(roc20=roc20, roc5=roc5))
        assert g["grade_path"], (roc20, roc5)


def test_too_few_bars_is_labelled_not_silently_graded_watch():
    g = S.grade_sector_etf(pd.DataFrame({"date": [], "close": []}))
    assert g["grade"] == "WATCH" and g["grade_path"] == "insufficient_bars"


# ─────────────────────────────────────────────────── the removed cap

def _panel(series: dict[str, list[float]]) -> pd.DataFrame:
    rows = []
    for tk, closes in series.items():
        dates = pd.date_range("2026-06-01", periods=len(closes), freq="D")
        rows += [{"date": d, "ticker": tk, "close": c}
                 for d, c in zip(dates, closes)]
    return pd.DataFrame(rows)


def _ramp(pct: float, n: int = 40) -> list[float]:
    return list(np.linspace(100.0, 100.0 * (1 + pct / 100.0), n))


def test_a_strong_theme_is_no_longer_flattened_to_its_parent_sector(monkeypatch):
    """The 2026-08-05 failure in one assertion.

    XLK graded HOLD, so EVERY technology basket was clamped to HOLD —
    Enterprise_Software at +13.6% and RRG LEADING read exactly like Fintech at
    +0.01% and LAGGING. A cap that maps a working theme and a dead one onto the
    same word destroys the only information the basket layer adds.
    """
    monkeypatch.setattr(S, "THEMATIC_BASKETS", {
        "Hot": {"parent_gics_etf": "XLK",
                "constituents": ["AAA", "BBB", "CCC"]},
    })
    panel = _panel({t: _ramp(20.0) for t in ("AAA", "BBB", "CCC")})
    out = S.grade_thematic_baskets(panel, {"XLK": {"grade": "HOLD"}})["Hot"]
    assert out["grade"] == "DEPLOY"                  # its own reading
    assert out["parent_capped_grade"] == "HOLD"      # the old one, still on the row
    assert out["parent_grade"] == "HOLD"             # and the sector's, to judge with


# ────────────────────────────────────────────────────────── breadth

def test_one_name_carrying_the_index_cannot_reach_deploy(monkeypatch):
    """An equal-weight index of 5 names where ONE triples and four go nowhere
    still rises enough to grade DEPLOY. Breadth is the check on that."""
    monkeypatch.setattr(S, "THEMATIC_BASKETS", {
        "Narrow": {"parent_gics_etf": "XLK",
                   "constituents": ["AAA", "BBB", "CCC", "DDD", "EEE"]},
    })
    panel = _panel({"AAA": _ramp(200.0), "BBB": _ramp(-2.0), "CCC": _ramp(-2.0),
                    "DDD": _ramp(-2.0), "EEE": _ramp(-2.0)})
    out = S.grade_thematic_baskets(panel, {"XLK": {"grade": "HOLD"}})["Narrow"]
    assert out["index_grade"] == "DEPLOY"       # the index says go
    assert out["grade"] == "HOLD"               # breadth says one name is going
    assert out["grade_path"] == "narrow"
    assert out["breadth_pct"] < 60.0
    assert "carrying" in out["breadth_note"]


def test_breadth_can_demote_but_never_promote(monkeypatch):
    """A basket where everyone is above their own SMA but the theme is going
    nowhere is not a buy. Breadth confirms strength; it cannot manufacture it."""
    monkeypatch.setattr(S, "THEMATIC_BASKETS", {
        "Broad": {"parent_gics_etf": "XLK", "constituents": ["AAA", "BBB", "CCC"]},
    })
    panel = _panel({t: _ramp(1.0) for t in ("AAA", "BBB", "CCC")})
    out = S.grade_thematic_baskets(panel, {"XLK": {"grade": "DEPLOY"}})["Broad"]
    assert out["breadth_pct"] == 100.0
    assert out["grade"] != "DEPLOY"


def test_unmeasurable_breadth_is_null_not_zero(monkeypatch):
    """A missing measurement must not read as 'no participation' — that would
    silently demote a basket for a data gap."""
    monkeypatch.setattr(S, "THEMATIC_BASKETS", {
        "Thin": {"parent_gics_etf": "XLK", "constituents": ["AAA", "BBB"]},
    })
    panel = _panel({"AAA": _ramp(30.0), "BBB": _ramp(30.0)})
    out = S.grade_thematic_baskets(panel, {"XLK": {"grade": "HOLD"}})["Thin"]
    assert out["breadth_pct"] is not None       # 40 bars each: measurable
    frac, above, meas = S._breadth(pd.DataFrame({"AAA": [1.0, 2.0, 3.0]}))
    assert frac is None and meas == 0           # 3 bars: not measurable, not 0%


def test_a_basket_with_no_data_still_carries_every_key(monkeypatch):
    """Readers index these fields unconditionally; an absent key is a crash,
    and a missing grade must be NO_DATA rather than a default WATCH."""
    monkeypatch.setattr(S, "THEMATIC_BASKETS", {
        "Empty": {"parent_gics_etf": "XLK", "constituents": ["ZZZ"]},
    })
    out = S.grade_thematic_baskets(_panel({"AAA": _ramp(1.0)}),
                                   {"XLK": {"grade": "HOLD"}})["Empty"]
    for k in ("grade", "index_grade", "parent_capped_grade", "grade_path",
              "breadth_pct", "breadth_note", "parent_gics", "parent_grade",
              "roc20", "roc5", "divergence", "above_sma20", "coverage"):
        assert k in out, k
    assert out["grade"] == "NO_DATA"


def test_grades_stay_inside_the_declared_enum(monkeypatch):
    monkeypatch.setattr(S, "THEMATIC_BASKETS", {
        "A": {"parent_gics_etf": "XLK", "constituents": ["AAA", "BBB"]},
    })
    valid = set(S.GRADE_ORDER) | {"NO_DATA"}
    for pct in (-30.0, -5.0, 0.0, 3.0, 25.0):
        panel = _panel({t: _ramp(pct) for t in ("AAA", "BBB")})
        out = S.grade_thematic_baskets(panel, {"XLK": {"grade": "HOLD"}})["A"]
        assert out["grade"] in valid and out["parent_capped_grade"] in valid


def test_sh_still_maps_from_the_grade_for_ptrs():
    """PTRS reads sh, and a new grade path must not orphan it."""
    for roc20, roc5 in ((13.6, 9.1), (1.8, 11.7), (-9.2, 18.6), (-2.5, 0.1)):
        g = S.grade_sector_etf(_shaped(roc20=roc20, roc5=roc5))
        assert g["sh"] == S.GRADE_TO_SH[g["grade"]]
