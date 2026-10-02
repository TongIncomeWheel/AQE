"""Tests for src/alerts/live_measures.py (AQE handoff D123/R21, 2026-10-02
§4/§9) — the pure volume-profile/vol_x/hourly/session_vwap/heat_row/
rs_today functions behind the new condition-watching alerts.
"""

from __future__ import annotations

from src.alerts import live_measures as LM

_ET_SUFFIX = ":00"


def _bar(hhmm: str, vol: float, o=100.0, h=101.0, lo=99.0, c=100.5, date="2026-09-01"):
    return {"date": f"{date} {hhmm}{_ET_SUFFIX}", "open": o, "high": h,
           "low": lo, "close": c, "volume": vol}


def _full_session_bars(date: str, per_slot_vol: dict[int, float] | None = None,
                       default_vol: float = 1000.0) -> list[dict]:
    """26 15-min bars for one full session, date's own slot volumes from
    `per_slot_vol` (slot index -> volume) falling back to `default_vol`."""
    per_slot_vol = per_slot_vol or {}
    bars = []
    for slot in range(26):
        mins = 9 * 60 + 30 + slot * 15
        hh, mm = divmod(mins, 60)
        bars.append(_bar(f"{hh:02d}:{mm:02d}", per_slot_vol.get(slot, default_vol),
                         date=date))
    return bars


# --------------------------------------------------------------- volume_profile


def test_volume_profile_averages_full_sessions_only():
    bars = (_full_session_bars("2026-09-01", default_vol=1000.0)
            + _full_session_bars("2026-09-02", default_vol=2000.0))
    profile = LM.volume_profile(bars)
    assert len(profile) == 26
    assert profile[0] == 1500.0  # average of 1000 and 2000


def test_volume_profile_drops_half_days():
    full = _full_session_bars("2026-09-01", default_vol=1000.0)
    half = _full_session_bars("2026-09-02", default_vol=5000.0)[:10]  # only 10 of 26 slots
    profile = LM.volume_profile(full + half)
    assert profile[0] == 1000.0  # the half day never contributed


def test_volume_profile_empty_when_no_full_sessions():
    half = _full_session_bars("2026-09-01")[:10]
    assert LM.volume_profile(half) == {}


def test_volume_profile_skips_unparseable_dates():
    bars = _full_session_bars("2026-09-01") + [{"date": "not-a-date", "volume": 999}]
    profile = LM.volume_profile(bars)
    assert len(profile) == 26  # the bad bar contributed nothing, didn't crash


# -------------------------------------------------------------------- vol_x
# §9: "vol_x on a normal day reads about 1.0 at 10:30, 12:30 and 15:30; the
# linear clock does not." Evidence from the handoff (NTAP, 4 weeks): first
# hour ~21% of the day, each midday hour 8-12%, last hour ~25%.


def _ntap_like_profile() -> dict[int, float]:
    """A profile shaped like the handoff's own NTAP evidence: U-shaped
    across the day, each slot an even share of its hour's total."""
    # Hour shares of the full day: 21%, 10%, 9%, 8%, 12%, 25%6 (six hours,
    # normalised to sum to 100).
    hour_shares = [0.21, 0.10, 0.09, 0.08, 0.12, 0.25]
    day_total = 1_000_000.0
    profile = {}
    for hour_idx, share in enumerate(hour_shares):
        hour_total = day_total * share
        per_slot = hour_total / 4
        for s in range(4):
            profile[hour_idx * 4 + s] = per_slot
    return profile


def _bars_matching_profile(profile: dict[int, float], through_slot: int) -> list[dict]:
    """Today's bars exactly matching the profile through `through_slot`
    inclusive -- "a normal day", by construction."""
    bars = []
    for slot in range(through_slot + 1):
        mins = 9 * 60 + 30 + slot * 15
        hh, mm = divmod(mins, 60)
        bars.append(_bar(f"{hh:02d}:{mm:02d}", profile[slot], date="2026-09-30"))
    return bars


def test_vol_x_reads_near_one_on_a_normal_day_at_1030_1230_1530():
    profile = _ntap_like_profile()
    # Slot s covers [09:30+15s, 09:30+15(s+1)) minutes, so slot 3 is the
    # LAST slot completed exactly at 10:30 (slots 0-3 = the first hour).
    for label, through_slot in (("10:30", 3), ("12:30", 11), ("15:30", 23)):
        bars = _bars_matching_profile(profile, through_slot)
        out = LM.vol_x(bars, profile)
        assert out["so_far"] == 1.0, f"{label}: expected ~1.0, got {out['so_far']}"


def test_vol_x_last_slot_reads_one_when_matching_profile():
    profile = _ntap_like_profile()
    bars = _bars_matching_profile(profile, 3)
    out = LM.vol_x(bars, profile)
    assert out["last_slot"] == 1.0


def test_vol_x_none_without_a_profile():
    bars = _bars_matching_profile(_ntap_like_profile(), 3)
    assert LM.vol_x(bars, {}) == {"so_far": None, "last_slot": None}


def test_vol_x_none_without_any_today_bars():
    assert LM.vol_x([], _ntap_like_profile()) == {"so_far": None, "last_slot": None}


def test_vol_x_detects_a_hot_day():
    profile = _ntap_like_profile()
    bars = _bars_matching_profile(profile, 3)
    for b in bars:
        b["volume"] *= 1.6
    out = LM.vol_x(bars, profile)
    assert out["so_far"] == 1.6


# -------------------------------------------------------------------- hourly


def _hour_bars(hour_start_hhmm: str, vols=(100, 100, 100, 100), date="2026-09-30"):
    hh, mm = int(hour_start_hhmm[:2]), int(hour_start_hhmm[3:])
    start = hh * 60 + mm
    bars = []
    for i, v in enumerate(vols):
        mins = start + i * 15
        bh, bm = divmod(mins, 60)
        bars.append(_bar(f"{bh:02d}:{bm:02d}", v, o=100 + i, h=101 + i,
                         lo=99 + i, c=100.5 + i, date=date))
    return bars


def test_hourly_builds_a_candle_from_four_complete_bars():
    bars = _hour_bars("09:30")
    candles = LM.hourly(bars)
    assert len(candles) == 1
    c = candles[0]
    assert c["open"] == 100.0  # first bar's open
    assert c["close"] == 103.5  # last bar's close


def test_hourly_never_returns_a_partial_hour():
    bars = _hour_bars("09:30")[:3]  # only 3 of 4 bars
    assert LM.hourly(bars) == []


def test_hourly_builds_multiple_candles_across_the_session():
    bars = _hour_bars("09:30") + _hour_bars("10:30")
    candles = LM.hourly(bars)
    assert len(candles) == 2
    assert candles[0]["hour_start_min"] < candles[1]["hour_start_min"]


def test_hourly_ignores_bars_outside_regular_session():
    bars = _hour_bars("09:30") + [_bar("16:15", 100)]  # after close
    candles = LM.hourly(bars)
    assert len(candles) == 1


# -------------------------------------------------------------- session_vwap


def test_session_vwap_is_provisional_before_two_candles():
    candles = LM.hourly(_hour_bars("09:30"))
    out = LM.session_vwap(candles)
    assert out["provisional"] is True
    assert out["n_candles"] == 1


def test_session_vwap_not_provisional_at_two_candles():
    candles = LM.hourly(_hour_bars("09:30") + _hour_bars("10:30"))
    out = LM.session_vwap(candles)
    assert out["n_candles"] == 2
    assert out["provisional"] is False


def test_session_vwap_computes_typical_price_weighted_by_volume():
    candles = [{"hour_start_min": 570, "open": 100, "high": 102, "low": 98,
               "close": 100, "volume": 1000},
              {"hour_start_min": 630, "open": 100, "high": 106, "low": 100,
               "close": 103, "volume": 1000}]
    out = LM.session_vwap(candles)
    typical1 = (102 + 98 + 100) / 3
    typical2 = (106 + 100 + 103) / 3
    expected = round((typical1 * 1000 + typical2 * 1000) / 2000, 4)
    assert out["vwap"] == expected


def test_session_vwap_none_with_no_candles():
    out = LM.session_vwap([])
    assert out["vwap"] is None
    assert out["provisional"] is True


# ----------------------------------------------------------------- heat_row


def test_heat_row_reads_one_on_a_normal_hour():
    profile = _ntap_like_profile()  # exactly 6 hours x 4 slots = 24 slots
    bars = _bars_matching_profile(profile, 23)  # every slot in all 6 hours
    row = LM.heat_row(bars, profile)
    assert len(row) == 6
    assert all(v == 1.0 for v in row)


def test_heat_row_none_for_an_incomplete_hour():
    profile = _ntap_like_profile()
    bars = _bars_matching_profile(profile, 22)  # slot 23 (last of hour 5) missing
    row = LM.heat_row(bars, profile)
    assert row[0] == 1.0
    assert row[5] is None


def test_heat_row_none_without_profile_coverage():
    bars = _hour_bars("09:30")
    row = LM.heat_row(bars, {})
    assert all(v is None for v in row)


# ---------------------------------------------------------------- rs_today


def test_rs_today_positive_when_stock_outperforms():
    quote = {"price": 110.0, "prev_close": 100.0}
    spy = {"price": 101.0, "prev_close": 100.0}
    assert LM.rs_today(quote, spy) == 9.0


def test_rs_today_none_without_prev_close():
    assert LM.rs_today({"price": 110.0}, {"price": 101.0, "prev_close": 100.0}) is None


def test_rs_today_none_when_spy_quote_missing():
    assert LM.rs_today({"price": 110.0, "prev_close": 100.0}, {}) is None
