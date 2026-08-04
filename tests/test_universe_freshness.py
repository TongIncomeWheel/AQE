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


def _write(tmp_path, built: str | None, tickers=("AAA", "BBB", "CCC")):
    p = tmp_path / "universe.txt"
    head = [f"# AQE Universe — updated {built}"] if built else ["# AQE Universe"]
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
