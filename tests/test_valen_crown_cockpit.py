"""Tests for VALEN's macro cockpit (src/valen/crown_cockpit.py, card.py's
crown_cockpit_*/crown_divergence_row/crown_cot_row, theme.py's
macro_cockpit_html). A PM ask (2026-10-02): "how Crown and VALEN can be
combined... more cockpit illustration within VALEN's structure" — answered
"all 5" widgets, "a new sub-section inside Part 1."

Every reading is Crown's own, read-only (crown_cockpit.py computes
nothing Crown doesn't already compute) — the exact pattern GEX's traffic
light already established, now applied to breadth range, CTA crowding,
dispersion, divergence and COT crowding.
"""

from __future__ import annotations

from src.valen import card, crown_cockpit as CC, theme


def _crown_ok(**overrides) -> dict:
    base = {
        "crown_status": "OK",
        "heartbeat": {"range_pct": 0.456, "regime": "neutral",
                     "range_position": "mid", "confidence": 0.45},
        "cta": {"flip_risk": 0.0, "overall_bias": "neutral", "n_markets": 18},
        "volatility": {"status": "OK",
                      "dispersion": {"percentile": 0.686, "state": "NORMAL",
                                    "direction": "FALLING", "basis": "implied"}},
        "divergence": {"count": 2, "types_fired": ["rsi", "vix"]},
        "cot": {"as_of": "2026-09-01", "crowded_long": ["GC", "HG"],
               "crowded_short": ["NG"]},
    }
    base.update(overrides)
    return base


# --------------------------------------------------------- crown_status_ok


def test_crown_status_ok_true_for_ok_and_degraded():
    assert CC.crown_status_ok({"crown_status": "OK"}) == (True, None)
    assert CC.crown_status_ok({"crown_status": "DEGRADED"}) == (True, None)


def test_crown_status_ok_false_for_early_exit_and_unavailable():
    ok, reason = CC.crown_status_ok({"crown_status": "EARLY_EXIT"})
    assert ok is False and "EARLY_EXIT" in reason
    ok, reason = CC.crown_status_ok({"crown_status": "UNAVAILABLE"})
    assert ok is False and "UNAVAILABLE" in reason


def test_crown_status_ok_false_when_crown_is_none():
    ok, reason = CC.crown_status_ok(None)
    assert ok is False
    assert "has not run" in reason


# ------------------------------------------------------- individual readings


def test_breadth_range_reading_ok():
    out = CC.breadth_range_reading(_crown_ok())
    assert out["status"] == "OK"
    assert out["range_pct"] == 45.6
    assert out["regime"] == "neutral"


def test_breadth_range_reading_degrades_when_crown_gated():
    out = CC.breadth_range_reading({"crown_status": "UNAVAILABLE"})
    assert out["status"] == "UNAVAILABLE"
    assert out["reason"]


def test_breadth_range_reading_degrades_when_no_heartbeat():
    out = CC.breadth_range_reading({"crown_status": "OK", "heartbeat": {}})
    assert out["status"] == "UNAVAILABLE"


def test_cta_crowding_reading_ok():
    out = CC.cta_crowding_reading(_crown_ok())
    assert out["status"] == "OK"
    assert out["flip_risk_pct"] == 0.0
    assert out["bias"] == "neutral"
    assert out["n_markets"] == 18


def test_cta_crowding_reading_degrades_without_cta():
    out = CC.cta_crowding_reading({"crown_status": "OK", "cta": {}})
    assert out["status"] == "UNAVAILABLE"


def test_dispersion_reading_ok():
    out = CC.dispersion_reading(_crown_ok())
    assert out["status"] == "OK"
    assert out["percentile_pct"] == 68.6
    assert out["state"] == "NORMAL"


def test_dispersion_reading_degrades_when_vol_unavailable():
    out = CC.dispersion_reading({"crown_status": "OK",
                                 "volatility": {"status": "UNAVAILABLE"}})
    assert out["status"] == "UNAVAILABLE"


def test_dispersion_reading_degrades_without_percentile():
    out = CC.dispersion_reading({"crown_status": "OK",
                                 "volatility": {"status": "OK", "dispersion": {}}})
    assert out["status"] == "UNAVAILABLE"


def test_divergence_reading_ok():
    out = CC.divergence_reading(_crown_ok())
    assert out["status"] == "OK"
    assert out["count"] == 2
    assert out["total"] == 8
    assert out["types_fired"] == ["rsi", "vix"]


def test_divergence_reading_degrades_without_count():
    out = CC.divergence_reading({"crown_status": "OK", "divergence": {}})
    assert out["status"] == "UNAVAILABLE"


def test_cot_reading_ok():
    out = CC.cot_reading(_crown_ok())
    assert out["status"] == "OK"
    assert out["crowded_long"] == ["GC", "HG"]
    assert out["crowded_short"] == ["NG"]


def test_cot_reading_degrades_without_as_of():
    out = CC.cot_reading({"crown_status": "OK", "cot": {}})
    assert out["status"] == "UNAVAILABLE"


def test_all_five_readings_share_one_gate():
    """A crown read that never ran (None) must degrade all five the SAME
    way -- one shared gate, not five separately-reasoned checks."""
    cc = CC.compute_crown_cockpit(None)
    assert all(r["status"] == "UNAVAILABLE" for r in cc.values())
    reasons = {r["reason"] for r in cc.values()}
    assert reasons == {"Crown macro has not run yet this session"}


def test_compute_crown_cockpit_all_ok():
    cc = CC.compute_crown_cockpit(_crown_ok())
    assert all(r["status"] == "OK" for r in cc.values())


def test_no_sizing_or_disposition_leaks_into_the_cockpit():
    """Same charter rule GEX already holds to -- CTA's own size_adjustment
    and anything from `decision` must never surface here."""
    cc = CC.compute_crown_cockpit(_crown_ok())
    blob = str(cc).lower()
    for banned in ("size_adjustment", "size_multiplier", "position_size", "disposition"):
        assert banned not in blob


# --------------------------------------------------------------- card.py


def test_crown_cockpit_block_defaults_when_absent():
    out = card.crown_cockpit_block({})
    assert all(v["status"] == "UNAVAILABLE" for v in out.values())


def test_crown_cockpit_gauge_rows_shapes_three_gauges():
    valen = {"crown_cockpit": CC.compute_crown_cockpit(_crown_ok())}
    rows = card.crown_cockpit_gauge_rows(valen)
    by_kind = {r["kind"]: r for r in rows}
    assert by_kind["breadth_range_pct"]["value"] == 45.6
    assert by_kind["breadth_range_pct"]["tag"] == "Neutral"
    assert by_kind["cta_crowding_pct"]["value"] == 0.0
    assert by_kind["dispersion_pct"]["value"] == 68.6
    assert by_kind["dispersion_pct"]["tag"] == "Normal"


def test_crown_cockpit_gauge_rows_no_tag_when_unavailable():
    valen = {"crown_cockpit": CC.compute_crown_cockpit(None)}
    rows = card.crown_cockpit_gauge_rows(valen)
    assert all(r["value"] is None and r["tag"] is None for r in rows)


def test_crown_divergence_row_passes_through():
    valen = {"crown_cockpit": CC.compute_crown_cockpit(_crown_ok())}
    out = card.crown_divergence_row(valen)
    assert out["count"] == 2 and out["total"] == 8


def test_crown_cot_row_passes_through():
    valen = {"crown_cockpit": CC.compute_crown_cockpit(_crown_ok())}
    out = card.crown_cot_row(valen)
    assert out["crowded_long"] == ["GC", "HG"]


# -------------------------------------------------------------- theme.py


def test_macro_cockpit_html_renders_all_three_gauges():
    valen = {"crown_cockpit": CC.compute_crown_cockpit(_crown_ok())}
    html = theme.macro_cockpit_html(card.crown_cockpit_gauge_rows(valen),
                                    card.crown_divergence_row(valen),
                                    card.crown_cot_row(valen))
    assert "Breadth" in html and "Trend-fund crowding" in html and "Dispersion" in html
    assert "45.60%" in html
    assert "(Neutral)" in html


def test_macro_cockpit_html_shows_divergence_count_and_types():
    valen = {"crown_cockpit": CC.compute_crown_cockpit(_crown_ok())}
    html = theme.macro_cockpit_html(card.crown_cockpit_gauge_rows(valen),
                                    card.crown_divergence_row(valen),
                                    card.crown_cot_row(valen))
    assert "2 of 8" in html
    assert "rsi" in html and "vix" in html


def test_macro_cockpit_html_shows_cot_crowded_tags():
    valen = {"crown_cockpit": CC.compute_crown_cockpit(_crown_ok())}
    html = theme.macro_cockpit_html(card.crown_cockpit_gauge_rows(valen),
                                    card.crown_divergence_row(valen),
                                    card.crown_cot_row(valen))
    assert "GC" in html and "HG" in html and "NG" in html


def test_macro_cockpit_html_shows_one_shared_banner_when_fully_degraded():
    """Crown gated (EARLY_EXIT/UNAVAILABLE/no run) must collapse to ONE
    banner, not five separate gauge/stat 'not shown' placeholders."""
    valen = {"crown_cockpit": CC.compute_crown_cockpit(None)}
    html = theme.macro_cockpit_html(card.crown_cockpit_gauge_rows(valen),
                                    card.crown_divergence_row(valen),
                                    card.crown_cot_row(valen))
    assert "Crown macro not shown" in html
    assert html.count("valen-light-bulb") == 0
    assert "Divergence checks lit" not in html


def test_macro_cockpit_html_never_renders_a_sizing_number():
    """Gauge axis ticks legitimately include 0/20/80/100% -- this checks
    for an actual sizing CONCEPT leaking through, not those bare numbers."""
    valen = {"crown_cockpit": CC.compute_crown_cockpit(_crown_ok())}
    html = theme.macro_cockpit_html(card.crown_cockpit_gauge_rows(valen),
                                    card.crown_divergence_row(valen),
                                    card.crown_cot_row(valen))
    for banned in ("size_adjustment", "size_multiplier", "size_dial", "of normal",
                  "disposition"):
        assert banned not in html.lower()
