"""Tests for src/scanner/score_runner.py's scoreable_tickers() — the filter
that decides which panel tickers actually get scored.

2026-08-21 incident: GOLD and JPM were held positions, both thematic-basket
constituents outside the scan universe, and both silently scored as fully
null in the daily export — flagged by data_quality but with nothing in the
pipeline explaining why. panel_builder.py explicitly promises held names are
always sourced and scored ("as long as we have the ticker, we can source
this") regardless of universe membership; this filter was the place that
promise quietly broke."""

from __future__ import annotations

from src.scanner.score_runner import scoreable_tickers


def test_basket_only_constituents_are_excluded():
    result = scoreable_tickers(
        panel_tickers=["AAPL", "GOLD"],
        scan_universe=["AAPL"],
        basket_constituents={"GOLD"},
    )
    assert result == ["AAPL"]


def test_a_held_basket_only_constituent_is_still_scored():
    result = scoreable_tickers(
        panel_tickers=["AAPL", "GOLD"],
        scan_universe=["AAPL"],
        basket_constituents={"GOLD"},
        held_tickers={"GOLD"},
    )
    assert result == ["AAPL", "GOLD"]


def test_a_non_held_basket_only_constituent_stays_excluded_even_when_others_are_held():
    """Being held exempts only the held ticker itself, not every basket-only
    name — the exclusion is per-ticker, not all-or-nothing."""
    result = scoreable_tickers(
        panel_tickers=["AAPL", "GOLD", "SLV"],
        scan_universe=["AAPL"],
        basket_constituents={"GOLD", "SLV"},
        held_tickers={"GOLD"},
    )
    assert result == ["AAPL", "GOLD"]
    assert "SLV" not in result


def test_a_ticker_in_the_scan_universe_and_a_basket_is_scored_regardless_of_held_status():
    """A basket constituent that's ALSO independently in the scan universe was
    never excluded in the first place — held_tickers is irrelevant to it."""
    result = scoreable_tickers(
        panel_tickers=["V"],
        scan_universe=["V"],
        basket_constituents={"V"},
        held_tickers=set(),
    )
    assert result == ["V"]


def test_result_is_sorted():
    result = scoreable_tickers(
        panel_tickers=["ZZZ", "AAA", "MMM"],
        scan_universe=["ZZZ", "AAA", "MMM"],
        basket_constituents=set(),
    )
    assert result == ["AAA", "MMM", "ZZZ"]
