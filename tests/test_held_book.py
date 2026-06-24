"""Tests for the Portfolio Hedge Layer held_book (Charter §4C)."""

from __future__ import annotations

from src.analyzer.held_book import build_held_book


def _pos(tk, qty, cob, beta, sec, entry=None):
    return {"ticker": tk, "qty": qty, "cob_price": cob, "beta_30d": beta,
            "gics_sector": sec, "entry": entry if entry is not None else cob}


def test_held_book_core_math():
    held = [
        _pos("AAA", 100, 50.0, 1.2, "XLK"),    # exp 5000, badj 6000
        _pos("BBB", 200, 25.0, 0.8, "XLF"),    # exp 5000, badj 4000
    ]
    hb = build_held_book(held, as_of="2026-06-24 12:00:00 SGT")
    assert hb["position_count"] == 2
    assert hb["total_exposure_usd"] == 10000.0
    assert hb["beta_adj_exposure_usd"] == 10000.0          # 6000 + 4000
    assert hb["loss_per_1pct_gap_usd"] == 100.0            # 10000 * 0.01
    assert hb["nav_weighted_beta_30d"] == 1.0              # 10000 / 10000
    # Gap scenarios = beta-adj × pct
    assert hb["gap_scenarios"]["gap_5pct"]["est_book_loss_usd"] == 500.0
    assert hb["gap_scenarios"]["gap_10pct"]["est_book_loss_usd"] == 1000.0
    # Sector weights sum to ~100 across the populated sectors
    sw = hb["sector_weights"]
    assert sw["XLK"] == 50.0 and sw["XLF"] == 50.0
    assert round(sum(sw.values()), 1) == 100.0
    # Per-position
    p0 = next(p for p in hb["positions"] if p["ticker"] == "AAA")
    assert p0["exposure_usd"] == 5000.0 and p0["beta_adj_exposure_usd"] == 6000.0
    assert p0["sector_weight_pct"] == 50.0


def test_held_book_price_fallback_and_default_beta():
    # No cob_price → falls back to live_px → entry; missing beta → 1.0 neutral.
    held = [{"ticker": "CCC", "qty": 10, "live_px": 30.0, "gics_sector": "XLV"},
            {"ticker": "DDD", "qty": 10, "entry": 40.0, "gics_sector": "XLE"}]
    hb = build_held_book(held)
    assert hb["total_exposure_usd"] == 700.0               # 300 + 400
    assert hb["beta_adj_exposure_usd"] == 700.0            # beta defaulted to 1.0
    assert hb["positions"][0]["live_price"] == 30.0


def test_held_book_skips_unpriceable_and_empty():
    assert build_held_book([])["position_count"] == 0
    assert build_held_book([])["nav_weighted_beta_30d"] == 0.0
    # A row with no price is skipped, not crashed.
    hb = build_held_book([{"ticker": "EEE", "qty": 5, "gics_sector": "XLK"}])
    assert hb["position_count"] == 0 and hb["total_exposure_usd"] == 0.0


def test_held_book_sector_weights_zero_filled():
    hb = build_held_book([_pos("AAA", 1, 100.0, 1.0, "XLK")])
    # All 11 GICS ETFs present as keys; only XLK non-zero.
    assert len(hb["sector_weights"]) >= 11
    assert hb["sector_weights"]["XLK"] == 100.0
    assert hb["sector_weights"]["XLF"] == 0.0
