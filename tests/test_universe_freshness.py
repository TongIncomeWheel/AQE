"""Universe freshness tests.

The universe is a DYNAMIC daily screen, so "when was this built" is a
first-class question. A pipeline run against a stale list screens names that
may no longer meet the $2B / 1.5M rule and misses names that now do — and
nothing in the output reveals it. These tests cover the detection that stops
that being silent.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.data import universe as U


def _write(tmp_path, built: str | None, tickers=("AAA", "BBB", "CCC"),
           rule: str | None = "CURRENT"):
    p = tmp_path / "universe.txt"
    head = [f"# AQE Universe — updated {built}"] if built else ["# AQE Universe"]
    if rule is not None:
        head.append(f"# rule: {U.UNIVERSE_RULE_ID if rule == 'CURRENT' else rule}")
    head.append(f"# {len(tickers)} tickers")
    p.write_text("\n".join(head + [""] + list(tickers) + [""]), encoding="utf-8")
    return p


def test_reads_the_build_date_from_the_header(tmp_path):
    p = _write(tmp_path, "2026-05-28")
    assert U.universe_built_date(p) == date(2026, 5, 28)


def test_missing_header_date_reads_as_unknown(tmp_path):
    p = _write(tmp_path, None)
    assert U.universe_built_date(p) is None


def test_unreadable_file_reads_as_unknown_rather_than_raising(tmp_path):
    assert U.universe_built_date(tmp_path / "nope.txt") is None


def test_garbage_date_reads_as_unknown(tmp_path):
    p = tmp_path / "universe.txt"
    p.write_text("# AQE Universe — updated not-a-date\nAAA\n", encoding="utf-8")
    assert U.universe_built_date(p) is None


def test_stale_when_not_built_today(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "DEFAULT_UNIVERSE_FILE",
                        _write(tmp_path, "2026-05-28"))
    assert U.universe_is_stale(date(2026, 8, 4)) is True


def test_fresh_when_built_today(tmp_path, monkeypatch):
    today = date.today()
    monkeypatch.setattr(U, "DEFAULT_UNIVERSE_FILE",
                        _write(tmp_path, today.isoformat()))
    assert U.universe_is_stale() is False


def test_unknown_build_date_counts_as_stale(tmp_path, monkeypatch):
    """Unknown must fail toward rebuilding, not toward trusting it."""
    monkeypatch.setattr(U, "DEFAULT_UNIVERSE_FILE", _write(tmp_path, None))
    assert U.universe_is_stale() is True


def test_status_reports_built_count_and_staleness(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "DEFAULT_UNIVERSE_FILE",
                        _write(tmp_path, "2026-05-28", ("A", "B")))
    st = U.universe_status()
    assert st["built"] == "2026-05-28"
    assert st["count"] == 2
    assert st["stale"] is True


# ------------------------------------------------------------ rule stamping

def test_a_file_built_today_under_an_OLD_rule_is_stale(tmp_path, monkeypatch):
    """The transition case, and the one that would have gone unnoticed.

    On the day a screen rule changes, a universe built that morning by the
    PREVIOUS rule is fresh by date but wrong by definition. Without the rule
    check the new rule would not take effect until the calendar rolled, and
    the run would quietly scan the old membership.
    """
    monkeypatch.setattr(U, "DEFAULT_UNIVERSE_FILE",
                        _write(tmp_path, date.today().isoformat(),
                               rule="v1-with-sma-filters"))
    assert U.universe_is_stale() is True
    assert "v1-with-sma-filters" in U.universe_status()["stale_reason"]


def test_an_unstamped_file_is_stale_even_if_built_today(tmp_path, monkeypatch):
    """Predates rule stamping, so it was built by an older screen."""
    monkeypatch.setattr(U, "DEFAULT_UNIVERSE_FILE",
                        _write(tmp_path, date.today().isoformat(), rule=None))
    assert U.universe_is_stale() is True
    assert "unstamped" in U.universe_status()["stale_reason"]


def test_today_plus_current_rule_is_the_only_fresh_combination(tmp_path,
                                                               monkeypatch):
    monkeypatch.setattr(U, "DEFAULT_UNIVERSE_FILE",
                        _write(tmp_path, date.today().isoformat()))
    st = U.universe_status()
    assert st["stale"] is False and st["stale_reason"] is None
    assert st["rule"] == U.UNIVERSE_RULE_ID


def test_writer_stamps_both_date_and_rule(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "DEFAULT_UNIVERSE_FILE", tmp_path / "universe.txt")
    U._write_universe(["AAA", "BBB"])
    assert U.universe_built_date() == date.today()
    assert U.universe_built_rule() == U.UNIVERSE_RULE_ID
    assert U.universe_is_stale() is False


def test_rule_id_records_that_the_trend_filter_is_gone():
    """The id is documentation the pipeline log prints — keep it meaningful."""
    assert "notrend" in U.UNIVERSE_RULE_ID
    assert "2B" in U.UNIVERSE_RULE_ID


# -------------------------------------------------------------- API budget

def test_verification_bands_bracket_the_liquidity_floor():
    """Only names NEAR the threshold spend a call; the rest are decided free.

    The bands must sit either side of the real floor, or the shortcut would be
    deciding cases where the answer is genuinely in doubt.
    """
    assert U.SCREEN_AVG_VOL_PREFILTER < U.SCREEN_AVG_VOL_10D < U.SCREEN_AVG_VOL_HIGH
    assert U.SCREEN_AVG_VOL_HIGH == U.SCREEN_AVG_VOL_10D * 2
    assert U.SCREEN_AVG_VOL_PREFILTER == U.SCREEN_AVG_VOL_10D // 2


def test_bars_calls_are_hard_capped():
    """A bad screener day must not become a thousand-call run.

    Pass 2 costs one call per name against an 80/min cloud limit, so the cap is
    what bounds the screen's wall-clock time, not just its quota use.
    """
    assert U.SCREEN_MAX_BAR_CALLS <= 500
    per_min_cloud = 80
    assert U.SCREEN_MAX_BAR_CALLS / per_min_cloud <= 6.0, \
        "Pass 2 must stay under ~6 minutes at the cloud rate limit"


def test_screen_call_budget_is_bounded():
    """Whole-screen worst case = screener + batch quotes + capped Pass 2."""
    max_candidates = 5000                      # the screener `limit`
    batch_quote_calls = max_candidates / 50    # chunk=50
    worst = 1 + batch_quote_calls + U.SCREEN_MAX_BAR_CALLS
    assert worst <= 600, f"screen could cost {worst} calls"


def test_missing_avg_volume_is_verified_not_guessed():
    """A missing quote is an FMP gap, not a screening result.

    Guessing either way would silently admit an illiquid name or drop a good
    one on an API hiccup.
    """
    import inspect
    src = inspect.getsource(U.build_universe)
    assert "av is None" in src
    assert "to_verify.append(tk)" in src


def test_the_screen_carries_no_trend_filter():
    """Guard on the rule itself — size + liquidity + listing only.

    A price>SMA condition here would silently delete the pulled-back names QS
    exists to find, before QS ever sees them.
    """
    import inspect
    src = inspect.getsource(U.build_universe)
    for banned in ("sma20", "sma50", "priceAvg50", "ma_50"):
        assert banned not in src, f"trend filter crept back in: {banned}"
    assert U.SCREEN_MCAP == 2_000_000_000
    assert U.SCREEN_AVG_VOL_10D == 1_500_000
