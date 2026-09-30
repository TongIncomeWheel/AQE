"""Tests for the GEX Traffic Light (src/valen/gex.py, theme.py's
traffic_light_html). Covers the frozen rule table exactly as specified
(GEX_traffic_light.md), the read from Crown Macro's real gamma computation
degrading honestly to UNAVAILABLE (never a fabricated calm/GREEN read),
the visual renderer, and the "no sizing" charter rule.
"""

from __future__ import annotations

import inspect

from src.valen import card, gex, theme


# ------------------------------------------------------------- gex_light()
# Each test mirrors one row of the spec's own rule table, checked in order.


def test_rule1_red_below_flip():
    out = gex.gex_light(price=99, flip=100, call_wall=120, put_wall=90)
    assert out["light"] == "RED"
    assert "amplified" in out["commentary"]


def test_rule2_red_below_put_wall_when_above_flip():
    # price sits above flip (110) but somehow below put_wall (112, an
    # unusual but spec-anticipated ordering) -- rule 2 is explicit even
    # though in practice the put wall normally sits below the flip.
    out = gex.gex_light(price=111, flip=100, call_wall=120, put_wall=112)
    assert out["light"] == "RED"
    assert "selloff" in out["commentary"]


def test_rule3_amber_just_above_flip():
    out = gex.gex_light(price=100.5, flip=100, call_wall=120, put_wall=90)
    assert out["light"] == "AMBER"
    assert "fragile" in out["commentary"]


def test_rule3_boundary_is_inclusive_at_exactly_one_percent():
    out = gex.gex_light(price=101.0, flip=100, call_wall=120, put_wall=90)
    assert out["light"] == "AMBER"


def test_rule3_one_tick_outside_the_boundary_falls_through():
    out = gex.gex_light(price=101.01, flip=100, call_wall=115, put_wall=90)
    assert out["light"] == "GREEN"
    assert "calm regime" in out["commentary"]


def test_rule4_amber_near_call_wall():
    # 0.5% of 120 = 0.6 -> 119.5 is exactly at the boundary.
    out = gex.gex_light(price=119.5, flip=100, call_wall=120, put_wall=90)
    assert out["light"] == "AMBER"
    assert "stall" in out["commentary"]


def test_rule5_green_call_wall_cleared():
    out = gex.gex_light(price=121, flip=100, call_wall=120, put_wall=90)
    assert out["light"] == "GREEN"
    assert "ceiling gone" in out["commentary"]


def test_rule6_green_calm_regime_default():
    out = gex.gex_light(price=110, flip=100, call_wall=120, put_wall=90)
    assert out["light"] == "GREEN"
    assert "calm regime" in out["commentary"]


def test_rules_checked_in_order_first_match_wins():
    """A price that would satisfy both rule 1 (below flip) and what would
    otherwise look like a call-wall condition must resolve to rule 1 (RED),
    since rule 1 is checked first."""
    out = gex.gex_light(price=50, flip=100, call_wall=50.2, put_wall=10)
    assert out["light"] == "RED"


def test_missing_walls_never_crash_and_skip_their_rule():
    out = gex.gex_light(price=110, flip=100, call_wall=None, put_wall=None)
    assert out["light"] == "GREEN"
    assert "calm regime" in out["commentary"]


def test_reference_pseudocode_matches_exactly():
    """Transcribes the spec's own reference pseudocode and checks every
    branch produces the identical light/commentary pair gex_light() does —
    a direct proof this is a frozen transcription, not a re-derivation."""
    def spec_reference(price, flip, call_wall, put_wall):
        if price < flip:
            return "RED", "Below flip: moves get amplified. Cut size, tighten stops."
        if price < put_wall:
            return "RED", "Put wall broken: selloff feeds itself. Reduce exposure."
        if price <= flip * 1.01:
            return "AMBER", "Just above flip: fragile. A small drop enters the wild zone."
        if abs(price - call_wall) / call_wall <= 0.005:
            return "AMBER", "At call wall: rally likely to stall. Don't chase."
        if price > call_wall:
            return "GREEN", "Call wall cleared: ceiling gone, momentum can run."
        return "GREEN", "Above flip: calm regime. Normal size, normal stops."

    cases = [
        (99, 100, 120, 90), (111, 100, 120, 112), (100.5, 100, 120, 90),
        (119.5, 100, 120, 90), (121, 100, 120, 90), (110, 100, 120, 90),
    ]
    for price, flip, call_wall, put_wall in cases:
        ref_light, ref_note = spec_reference(price, flip, call_wall, put_wall)
        out = gex.gex_light(price, flip, call_wall, put_wall)
        assert (out["light"], out["commentary"]) == (ref_light, ref_note)


# ----------------------------------------------------------- compute_gex_reading


def _crown_gamma_ok(ticker="SPY", spot=575.0, flip=570.0, call_wall=580.0,
                    put_wall=560.0):
    return {
        "status": "OK",
        "underlyings": {ticker: {
            "available": True, "spot": spot, "gamma_flip": flip,
            "call_wall": {"strike": call_wall} if call_wall is not None else None,
            "put_wall": {"strike": put_wall} if put_wall is not None else None,
            "total_gex": 1.5e9, "regime": "POSITIVE", "assumption": "x",
        }},
        "unavailable": {}, "regime": "POSITIVE", "primary": ticker, "reason": None,
    }


def test_compute_gex_reading_ok_shape():
    out = gex.compute_gex_reading(_crown_gamma_ok())
    assert out["status"] == "OK"
    assert out["ticker"] == "SPY"
    assert out["light"] in ("RED", "AMBER", "GREEN")
    assert out["call_wall"] == 580.0
    assert out["put_wall"] == 560.0


def test_compute_gex_reading_none_crown_is_unavailable_not_a_crash():
    out = gex.compute_gex_reading(None)
    assert out["status"] == "UNAVAILABLE"
    assert out["reason"]


def test_compute_gex_reading_crown_status_not_ok():
    out = gex.compute_gex_reading({"status": "UNAVAILABLE", "reason": "no feed"})
    assert out["status"] == "UNAVAILABLE"
    assert out["reason"] == "no feed"


def test_compute_gex_reading_ticker_not_available():
    crown_gamma = {"status": "OK", "underlyings": {}, "unavailable": {
        "SPY": "alpaca keys missing"}, "regime": "UNKNOWN", "primary": None, "reason": None}
    out = gex.compute_gex_reading(crown_gamma, ticker="SPY")
    assert out["status"] == "UNAVAILABLE"
    assert "alpaca" in out["reason"].lower()


def test_compute_gex_reading_never_fabricates_a_flat_or_green_read():
    """The project's own 'UNAVAILABLE, never flat' discipline (CLAUDE.md,
    Crown Macro section) -- a missing feed must never default price/flip
    to 0 or synthesize a calm GREEN reading."""
    out = gex.compute_gex_reading(None)
    assert out.get("light") is None
    assert out["status"] != "OK"


def test_compute_gex_reading_missing_spot_or_flip_degrades_cleanly():
    crown_gamma = {"status": "OK", "unavailable": {},
                   "underlyings": {"SPY": {"available": True, "spot": None,
                                          "gamma_flip": 570.0}}}
    out = gex.compute_gex_reading(crown_gamma)
    assert out["status"] == "UNAVAILABLE"


def test_compute_gex_reading_walls_may_be_none():
    out = gex.compute_gex_reading(_crown_gamma_ok(call_wall=None, put_wall=None))
    assert out["status"] == "OK"
    assert out["call_wall"] is None
    assert out["put_wall"] is None


def test_compute_gex_reading_defaults_to_spy():
    out = gex.compute_gex_reading(_crown_gamma_ok())
    assert out["ticker"] == "SPY"


# --------------------------------------------------------------- no sizing


def test_gex_reading_never_carries_a_sizing_or_disposition_key():
    """Mirrors test_stance_never_carries_a_size_or_disposition_key --
    the same charter rule applies here: AQE computes the light and the
    commentary, never a position size."""
    out = gex.compute_gex_reading(_crown_gamma_ok())
    blob = str(out).lower()
    for banned in ("sizing", "size_pct", "position_size", "max_new_size", "disposition"):
        assert banned not in blob, f"gex reading leaked a sizing concept: {banned!r}"


def test_gex_module_never_imports_pandas_or_touches_files():
    """gex.py should stay a pure rule/read module -- same blindness
    discipline as card.py, no file access of its own (it's handed Crown's
    already-loaded dict by daily.py)."""
    src = inspect.getsource(gex)
    for banned in ("import pandas", "import numpy", "open(", "read_parquet",
                  "requests", "Path("):
        assert banned not in src, f"gex.py found {banned!r}"


# ---------------------------------------------------------------- card.py


def test_card_gex_block_defaults_when_absent():
    out = card.gex_block({})
    assert out["status"] == "UNAVAILABLE"


def test_card_gex_block_passes_through_real_data():
    valen = {"gex": {"status": "OK", "light": "GREEN"}}
    assert card.gex_block(valen) == {"status": "OK", "light": "GREEN"}


# --------------------------------------------------------------- theme.py


def test_traffic_light_html_unavailable_state():
    html = theme.traffic_light_html({"status": "UNAVAILABLE", "reason": "no feed"})
    assert "GEX not shown" in html
    assert "no feed" in html
    assert "lit-" not in html


def test_traffic_light_html_red_state_lights_the_red_bulb():
    gex_reading = {"status": "OK", "ticker": "SPY", "price": 570.0, "flip": 580.0,
                   "call_wall": 590.0, "put_wall": 560.0, "light": "RED",
                   "commentary": "Below flip: moves get amplified. Cut size, tighten stops."}
    html = theme.traffic_light_html(gex_reading)
    assert "lit-red" in html
    assert "lit-amber" not in html and "lit-green" not in html
    assert theme._RED in html


def test_traffic_light_html_amber_state_lights_the_amber_bulb():
    gex_reading = {"status": "OK", "ticker": "SPY", "price": 581.0, "flip": 580.0,
                   "call_wall": 590.0, "put_wall": 560.0, "light": "AMBER",
                   "commentary": "Just above flip."}
    html = theme.traffic_light_html(gex_reading)
    assert "lit-amber" in html
    assert "lit-red" not in html and "lit-green" not in html


def test_traffic_light_html_green_state_lights_the_green_bulb():
    gex_reading = {"status": "OK", "ticker": "SPY", "price": 600.0, "flip": 580.0,
                   "call_wall": 590.0, "put_wall": 560.0, "light": "GREEN",
                   "commentary": "Call wall cleared."}
    html = theme.traffic_light_html(gex_reading)
    assert "lit-green" in html
    assert "lit-red" not in html and "lit-amber" not in html


def test_traffic_light_html_shows_levels_line():
    gex_reading = {"status": "OK", "ticker": "SPY", "price": 600.0, "flip": 580.0,
                   "call_wall": 590.0, "put_wall": 560.0, "light": "GREEN",
                   "commentary": "x"}
    html = theme.traffic_light_html(gex_reading)
    assert "flip 580" in html
    assert "call wall 590" in html
    assert "put wall 560" in html


def test_traffic_light_html_never_renders_a_sizing_number():
    """The one place a viewer could imagine a % showing up -- confirm the
    widget itself never prints a sizing percentage; that's quoted doctrine
    in the page, not this render function's job."""
    gex_reading = {"status": "OK", "ticker": "SPY", "price": 600.0, "flip": 580.0,
                   "call_wall": 590.0, "put_wall": 560.0, "light": "GREEN",
                   "commentary": "x"}
    html = theme.traffic_light_html(gex_reading)
    for banned in ("100%", "75%", "50%", "of normal"):
        assert banned not in html


def test_traffic_light_html_omits_missing_walls_gracefully():
    gex_reading = {"status": "OK", "ticker": "SPY", "price": 600.0, "flip": 580.0,
                   "call_wall": None, "put_wall": None, "light": "GREEN",
                   "commentary": "x"}
    html = theme.traffic_light_html(gex_reading)
    assert "call wall" not in html
    assert "put wall" not in html
