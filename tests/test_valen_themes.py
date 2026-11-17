"""PM 2026-11-17: the Valen theme layer (DAY-2..5, ALT-5): bullish flag + sessions on, reclaimed/lost, RS/thrust, membership columns, dry-up counts, one card line."""
import numpy as np
import pandas as pd

from src.engines.srm import THEMATIC_BASKETS
from src.valen import themes as TH

N = 260


def make_panel(trend_by_basket, seed=1):
    rng = np.random.default_rng(seed)
    d = pd.bdate_range(end="2026-11-13", periods=N)
    rows = []
    for name, drift in trend_by_basket.items():
        for t in THEMATIC_BASKETS[name]["constituents"]:
            r = rng.normal(drift, 0.004, N)
            px = 50 * np.cumprod(1 + r)
            v = np.full(N, 2_000_000.0)
            rows.append(pd.DataFrame({"date": d, "ticker": t, "open": px, "high": px, "low": px, "close": px, "volume": v}))
    return pd.concat(rows).drop_duplicates(["date", "ticker"])


UP, DOWN, FLAT1, FLAT2 = "Cloud_Computing", "REITs", "Crypto_Digital", "Social_Media"        # explicit; a ticker takes the drift of the FIRST basket that claims it


def names(k):
    return [UP, DOWN, FLAT1, FLAT2][:k]


def test_a_rising_basket_is_bullish_with_sessions_on_and_leading_and_a_falling_one_is_not():
    a, b, c, e = names(4)
    blk = TH.compute_theme_block(make_panel({a: 0.006, b: -0.006, c: 0.0, e: 0.0}))
    assert blk["status"] == "OK"
    assert blk["status"] == "OK" and blk["as_of"] == "2026-11-13"
    by = {x["name"]: x for x in blk["baskets"]}
    assert by[a]["bullish"] is True and by[a]["sessions_on"] > 0 and by[a]["rs_1m"] >= 80 and by[a]["leading"] is True
    assert by[b]["bullish"] is False and by[b]["sessions_on"] < 0 and by[b]["leading"] is False
    assert all(0 <= x["rs_1m"] <= 100 and x["rs_1m"] % 5 == 0 for x in blk["baskets"])               # percentile in steps of 5
    assert by[a]["share_above"]["sma50"] >= 80 and by[b]["share_above"]["sma50"] <= 20
    s = blk["summary"]
    assert s["baskets"] >= 4 and s["bullish"] >= 1 and "ema9" in s["above_pct"] and blk["definitions"]["bullish"]


def test_reclaimed_and_lost_today_are_the_baskets_that_crossed_an_average_at_the_last_close():
    a, b, c = names(3)
    p = make_panel({a: 0.003, b: 0.003, c: 0.003})
    t = p["date"].max()
    m = p["ticker"].isin(THEMATIC_BASKETS[a]["constituents"]) & (p["date"] == t)
    p.loc[m, "close"] = p.loc[m, "close"] * 0.80                  # a sharp last-day drop in basket a
    blk = TH.compute_theme_block(p)
    assert a in blk["lost_today"]["ema9"] and a not in blk["reclaimed_today"]["ema9"]
    assert b not in blk["lost_today"]["ema9"]


def test_membership_columns_say_not_read_when_the_block_is_missing_and_empty_list_when_in_no_basket():
    a, b, c = names(3)
    blk = TH.compute_theme_block(make_panel({a: 0.006, b: -0.006, c: 0.0}))
    mem = TH.membership(blk)
    tk = THEMATIC_BASKETS[a]["constituents"][0]
    f = TH.theme_fields(tk, mem, True)
    assert f["in_leading_theme"] is True and any(x["name"] == a and x["leading"] for x in f["themes"])
    assert TH.theme_fields("ZZZZ", mem, True) == {"themes": [], "in_leading_theme": False}          # read, in no theme
    assert TH.theme_fields(tk, {}, False) == {"themes": None, "in_leading_theme": None}             # NOT read is never an empty list
    assert TH.compute_theme_block(pd.DataFrame({"date": [], "ticker": [], "close": []}))["status"] == "UNAVAILABLE"


def test_theme_line_is_plain_and_silent_only_when_the_layer_was_not_read():
    row = {"themes": [{"name": "AI_Infrastructure", "bullish": True, "sessions_on": 12, "rs_1m": 85, "leading": True}], "in_leading_theme": True}
    line = TH.theme_line(row)
    assert line.startswith("Theme: a leading theme") and "AI Infrastructure" in line and "bullish 12 sessions" in line and "_" not in line
    assert TH.theme_line({"themes": [], "in_leading_theme": False}) == "Theme: in none of AQE's themes"
    assert TH.theme_line({"themes": None}) is None and TH.theme_line({}) is None


def test_dryup_counts_use_the_prior_50_day_average_and_the_last_10_sessions():
    d = pd.bdate_range(end="2026-11-13", periods=80)
    v = np.full(80, 1_000_000.0)
    v[-3:] = 400_000.0            # 60% under: counts for both 45% and 60%
    v[-6:-3] = 500_000.0          # 50% under: counts for 45% only
    p = pd.DataFrame({"date": d, "ticker": "AAA", "volume": v})
    r = TH.dryup_counts(p, {"AAA", "BBB"})
    assert r["AAA"] == {"dryup_45": 6, "dryup_60": 3, "dryup_window": 10}
    short = TH.dryup_counts(pd.DataFrame({"date": d[:20], "ticker": "BBB", "volume": v[:20]}), {"BBB"})
    assert short["BBB"]["dryup_45"] is None                                                         # too little history is not a zero


def test_the_card_carries_the_theme_line_on_every_card_not_only_the_u_and_r_ones():
    import inspect
    from src.alerts import emailer
    src = inspect.getsource(emailer)
    i = src.index("ALT-5 (PM 2026-11-17)")
    assert "theme_line" in src[i:i + 300] and src.index("_card_field_lines(row)", i) > i
