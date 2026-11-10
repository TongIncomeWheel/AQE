#!/usr/bin/env python3
"""seat_screens.py -- Report B's seven per-seat CODE screens (PM 2026-11-05).

Report B gives each of the seven seats the WHOLE daily screened universe (market cap >= $2B, 10-day volume >= 1.5M, US primary listing,
before any AQE score gate) instead of AQE's lists. A seat cannot read 600 rows, so each seat gets the 25 names its OWN checklist ranks
highest, found by deterministic code written from that seat's card: the same tests the seat would walk, on the fields the universe rows
carry, with no AQE composite, list flag or lens ranking as a door. A screen is a count of the seat's own tests passed; a test whose field
is missing for a row is not passed (never guessed), and the tie-break is plain relative strength so two seats' ties do not depend on AQE's
score. The screen only chooses WHICH 25 rows the seat reads; the seat still walks its full checklist and votes on what it sees.

    seat_screens.py --universe-rows aqe_universe_rows.json [--top 25] --out seat_sets.json
"""
import argparse, json, sys

TOP = 25


def _n(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _g(r, k):
    return r.get(k)


def _ge(r, k, v):
    x = r.get(k)
    return _n(x) and x >= v


def _le(r, k, v):
    x = r.get(k)
    return _n(x) and x <= v


def _cmf(r):
    return ((r.get("subcomponents") or {}).get("flow") or {}).get("cmf")


def _px(r):
    return r.get("bar_close") if _n(r.get("bar_close")) else r.get("last_close")


def _above(r, k):
    p, m = _px(r), r.get(k)
    return _n(p) and _n(m) and p > m


BOS = ("BULLISH_BOS", "ABOVE_STRUCTURE")

# --- one list of (name, test) per seat, written from the seat's own card ---------------------------------------------------------------
SCREENS = {
    # O'Neil: leader, sound base, institutional volume, not extended, in an uptrend (checklist 1-4; C10, C13, C16, C17)
    "oneil": [
        ("leader", lambda r: r.get("rs_leadership") == "LEADER"),
        ("rs rank 80+", lambda r: _ge(r, "rs_rank_pct", 80)),
        ("sound base: structure shift or base score", lambda r: r.get("structure_shift") in BOS or _ge(r, "structure", 60)),
        ("breakout volume 1.4x", lambda r: _ge(r, "day_vol", 1.4)),
        ("within 5% of the pivot", lambda r: _n(r.get("pct_from_continuation_pivot")) and -5 <= r["pct_from_continuation_pivot"] <= 5),
        ("near the 52-week high", lambda r: _ge(r, "pct_from_52w_high", -15)),
        ("above the 50 and 200 day", lambda r: _above(r, "ma_50") and _above(r, "ma_200")),
        ("not 70% above the 200 day", lambda r: _n(_px(r)) and _n(r.get("ma_200")) and _px(r) < 1.7 * r["ma_200"]),
    ],
    # Minervini: the eight-point trend template, all eight or none (C3), plus the base tightening (C4)
    "minervini": [
        ("above the 150 and 200 day", lambda r: _above(r, "ma_150") and _above(r, "ma_200")),
        ("150 day above the 200 day", lambda r: _n(r.get("ma_150")) and _n(r.get("ma_200")) and r["ma_150"] > r["ma_200"]),
        ("50 day above the 150 and 200 day", lambda r: _n(r.get("ma_50")) and _n(r.get("ma_150")) and _n(r.get("ma_200")) and r["ma_50"] > r["ma_150"] > r["ma_200"]),
        ("price above the 50 day", lambda r: _above(r, "ma_50")),
        ("25% above the 52-week low", lambda r: _n(_px(r)) and _n(r.get("low_52w")) and _px(r) >= 1.25 * r["low_52w"]),
        ("within 25% of the 52-week high", lambda r: _ge(r, "pct_from_52w_high", -25)),
        ("rs rank 70+", lambda r: _ge(r, "rs_rank_pct", 70)),
        ("contracting range", lambda r: _le(r, "hv_ratio_6_100", 0.8) or r.get("nr7_flag") is True or r.get("nr4_flag") is True),
    ],
    # Livermore: established uptrend, normal pullback, confirming new high, leading name in a leading group (C5, C12)
    "livermore": [
        ("at or near a new high", lambda r: _ge(r, "pct_from_52w_high", -3)),
        ("trend stack aligned", lambda r: r.get("stack_state") == "ALIGNED"),
        ("momentum alive", lambda r: r.get("mp_state") in ("STRONG", "BUILDING")),
        ("volume on the move", lambda r: _ge(r, "day_vol", 1.4)),
        ("leading name", lambda r: r.get("rs_leadership") == "LEADER"),
        ("leading group", lambda r: r.get("sector_rrg_quadrant") == "LEADING"),
        ("run of the last two weeks", lambda r: _ge(r, "pct_run_10d", 5)),
    ],
    # Elder: permission on (not red), weekly up, pullback in force inside a rising average, inside the channel (R1-R6, R9)
    "elder-lens": [
        ("weekly trend up", lambda r: r.get("weekly_trend_direction") == "UP"),
        ("impulse not red", lambda r: r.get("impulse_colour_last_bar") in ("GREEN", "BLUE")),
        ("short force dips under zero in a rising average", lambda r: _n(r.get("force_index_ema_2")) and r["force_index_ema_2"] < 0 and _n(r.get("price_ema_slope")) and r["price_ema_slope"] > 0),
        ("13-day force above zero", lambda r: _ge(r, "force_index_ema_13", 1e-9)),
        ("inside the channel", lambda r: _n(r.get("channel_upper")) and _n(_px(r)) and _px(r) <= r["channel_upper"]),
        ("20 day above 50 day", lambda r: _n(r.get("ma_20")) and _n(r.get("ma_50")) and r["ma_20"] > r["ma_50"]),
        ("price at or under the 20 day", lambda r: _n(_px(r)) and _n(r.get("ma_20")) and _px(r) <= r["ma_20"] * 1.01),
        ("not a bearish shift", lambda r: r.get("choch_state") != "BEARISH" and r.get("structure_shift") != "BEARISH_CHOCH"),
    ],
    # Seow: position system -- 20 above 40 and rising, a pullback with CCI under -100, close above the 40 day, buyers in the flow, beating the index (R1, R8, R14). PM 2026-11-10: the 'break of structure' test (R13) is dropped from the screen -- it excluded the pullback names this seat buys.
    "seow": [
        ("20 day above 40 day", lambda r: _n(r.get("ma_20")) and _n(r.get("ma_40")) and r["ma_20"] > r["ma_40"]),
        ("20 day rising", lambda r: _ge(r, "ma_20_slope_5d_pct", 1e-9)),
        ("pullback: CCI under -100", lambda r: _le(r, "cci_20", -100)),
        ("close above the 40 day", lambda r: _above(r, "ma_40")),
        ("low reached the 20 day", lambda r: _n(r.get("bar_low")) and _n(r.get("ma_20")) and r["bar_low"] <= r["ma_20"]),
        ("buyers in the flow", lambda r: _n(_cmf(r)) and _cmf(r) > 0),
        ("beating the index over 63 days", lambda r: _n(r.get("ret_63d")) and _n(r.get("index_pct_change_63d")) and r["ret_63d"] > r["index_pct_change_63d"]),
    ],
    # Raschke: the short-term setups (canon C5-C8, C12-C13). PM 2026-11-10: the ADX gate no longer blocks rebound / pullback names. The Holy Grail (C7) is
    # ADX-gated (ADX above 30); the Anti (C6) is NOT -- it reads a washed-out 7/10 stochastic against the longer trend. So the trigger test is EITHER, which is the
    # smallest loosening that keeps both setups as the canon states them; the ADX threshold itself is untouched.
    "raschke": [
        ("Holy Grail or Anti trigger: trend strength 30+, or stochastic washed out", lambda r: _ge(r, "adx_14", 30) or _le(r, "stoch_k_14", 30)),
        ("pullback to the 20 day", lambda r: _n(_px(r)) and _n(r.get("ma_20")) and _n(r.get("atr_14d")) and abs(_px(r) - r["ma_20"]) <= r["atr_14d"]),
        ("narrow range day", lambda r: r.get("nr4_flag") is True or r.get("nr7_flag") is True),
        ("volatility contracted", lambda r: _le(r, "hv_ratio_6_100", 0.5)),
        ("20 day above 50 day", lambda r: _n(r.get("ma_20")) and _n(r.get("ma_50")) and r["ma_20"] > r["ma_50"]),
    ],
    # Wyckoff: break of structure above value, close above the point of control and the VWAPs, a strong bar on volume (R1, R3-R6)
    "wyckoff": [
        ("break of structure or above it", lambda r: r.get("structure_shift") in BOS),
        ("above value", lambda r: r.get("pvp_position") == "ABOVE_VALUE"),
        ("close above the point of control", lambda r: _n(r.get("bar_close")) and _n(r.get("pvp_poc")) and r["bar_close"] > r["pvp_poc"]),
        ("above the 14-day VWAP", lambda r: _n(r.get("bar_close")) and _n(r.get("vwap_14d")) and r["bar_close"] > r["vwap_14d"]),
        ("above the structure anchored VWAP", lambda r: _n(r.get("bar_close")) and _n(r.get("avwap_structure")) and r["bar_close"] > r["avwap_structure"]),
        ("strong bar", lambda r: all(_n(r.get(k)) for k in ("bar_open", "bar_close", "bar_high", "bar_low", "atr_14d")) and r["bar_close"] > r["bar_open"]
            and (r["bar_high"] - r["bar_low"]) >= r["atr_14d"]
            and (r["bar_high"] - r["bar_low"]) > 0 and (r["bar_close"] - r["bar_low"]) / (r["bar_high"] - r["bar_low"]) >= 0.67),
        ("volume 1.2x", lambda r: _ge(r, "rvol_20d", 1.2)),
    ],
}
SEATS = list(SCREENS)


def score(seat, row):
    hits = []
    for name, test in SCREENS[seat]:
        try:
            if test(row):
                hits.append(name)
        except Exception:                      # a malformed field is a test not passed, never a crash and never a guess
            pass
    return len(hits), hits


def screen(seat, rows, top=TOP):
    """The seat's top `top` rows, best first: tests passed, then plain relative strength, then ticker (deterministic)."""
    scored = []
    for r in rows:
        n, hits = score(seat, r)
        rs = r.get("rs_rank_pct")
        scored.append((-n, -(rs if _n(rs) else -1), str(r.get("ticker")), r.get("ticker"), n, hits))
    scored.sort(key=lambda t: t[:3])
    return [{"ticker": t[3], "tests_passed": t[4], "of": len(SCREENS[seat]), "passed": t[5]} for t in scored[:top]]


def all_screens(rows, top=TOP):
    return {s: screen(s, rows, top) for s in SEATS}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--universe-rows", required=True)
    p.add_argument("--top", type=int, default=TOP)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    d = json.load(open(a.universe_rows))
    rows = d["rows"] if isinstance(d, dict) else d
    res = all_screens(rows, a.top)
    json.dump({"rule": "per-seat code screens, top %d of %d universe rows" % (a.top, len(rows)), "universe_rows": len(rows), "seats": res},
              open(a.out, "w"), indent=1)
    for s, v in res.items():
        print(f"{s}: {len(v)} names, best {v[0]['tests_passed']}/{v[0]['of']}" if v else f"{s}: no names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
