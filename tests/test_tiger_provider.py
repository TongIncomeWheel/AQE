"""Tiger option-chain adapter — the parsing, without an account.

The network half needs credentials nobody has in CI. The parsing half is where
the bugs live, so it is pure and tested against rows recorded from a real SPY
chain on 2026-08-10.
"""

from __future__ import annotations

from datetime import date

from src.options.providers import tiger as T

TODAY = date(2026, 8, 10)
EXPIRY_MS = 1787284800000          # 2026-08-21, as Tiger returns it

# Recorded verbatim from Tiger's SPY chain (fields trimmed to what we read).
ROWS = [
    {"identifier": "SPY   260821P00750000", "strike": "750.0", "put_call": "PUT",
     "open_interest": 58308, "volatility": "13.96%", "expiry": EXPIRY_MS,
     "rates_bonds": 0.04012},
    {"identifier": "SPY   260821C00785000", "strike": "785.0", "put_call": "CALL",
     "open_interest": 82245, "volatility": "13.96%", "expiry": EXPIRY_MS,
     "rates_bonds": 0.04012},
    {"identifier": "SPY   260821P00700000", "strike": "700.0", "put_call": "PUT",
     "open_interest": 49990, "volatility": "13.96%", "expiry": EXPIRY_MS,
     "rates_bonds": 0.04012},
]
SPOT = 773.92


def test_it_parses_a_real_recorded_chain():
    out = T.parse_chain_rows(ROWS, "SPY", SPOT, TODAY)
    assert len(out) == 3
    by = {c["strike"]: c for c in out}
    assert by[750.0]["right"] == "PUT" and by[750.0]["open_interest"] == 58308
    assert by[785.0]["right"] == "CALL"
    assert all(c["dte"] == 11 for c in out)
    assert all(c["gamma"] > 0 for c in out)


def test_a_percent_style_iv_is_read_as_a_rate():
    """Tiger sends "13.96%". Feeding 13.96 into Black-Scholes as a rate would
    produce a gamma of essentially zero and a silently empty map."""
    out = T.parse_chain_rows(ROWS, "SPY", SPOT, TODAY)
    atm = max(out, key=lambda c: c["gamma"])
    assert atm["gamma"] > 1e-4, "gamma collapsed — IV was probably read as 1396%"


def test_a_contract_without_open_interest_is_dropped_not_zeroed():
    rows = ROWS + [{"identifier": "X", "strike": "760.0", "put_call": "PUT",
                    "open_interest": 0, "volatility": "13.96%",
                    "expiry": EXPIRY_MS}]
    assert len(T.parse_chain_rows(rows, "SPY", SPOT, TODAY)) == 3


def test_expiries_beyond_the_window_are_excluded():
    assert T.parse_chain_rows(ROWS, "SPY", SPOT, TODAY, dte_max=5) == []


def test_an_expired_contract_is_excluded():
    assert T.parse_chain_rows(ROWS, "SPY", SPOT, date(2026, 9, 1)) == []


def test_epoch_and_iso_expiries_both_parse():
    assert T._expiry_date(EXPIRY_MS) == date(2026, 8, 21)
    assert T._expiry_date("2026-08-21") == date(2026, 8, 21)
    assert T._expiry_date("2026-08-21T00:00:00Z") == date(2026, 8, 21)
    assert T._expiry_date(None) is None
    assert T._expiry_date("not a date") is None


def test_junk_rows_are_skipped_rather_than_raising():
    junk = [{}, {"strike": "abc", "put_call": "PUT", "open_interest": 5},
            {"strike": "750", "put_call": "WAT", "open_interest": 5,
             "volatility": "13%", "expiry": EXPIRY_MS}]
    assert T.parse_chain_rows(junk, "SPY", SPOT, TODAY) == []


def test_it_reports_exactly_what_is_missing_rather_than_just_failing():
    """The point of the fallback is that a PM can switch it on themselves."""
    missing = T.missing_requirements()
    assert missing, "in CI nothing is configured, so something must be reported"
    joined = " ".join(missing)
    for name in (T.TIGER_ID_ENV, T.TIGER_ACCOUNT_ENV, T.TIGER_KEY_ENV):
        assert name in joined or "tigeropen" in joined


def test_an_unconfigured_fetch_degrades_with_the_reason_attached():
    r = T.fetch_chain("SPY", SPOT)
    assert r["contracts"] == [] and r["oi_available"] is False
    assert "not configured" in r["reason"]


def test_the_output_matches_the_shape_the_gamma_engine_consumes():
    """Same keys as the Alpaca path, so the gamma layer cannot tell them apart."""
    from src.macro.crown import gamma as G

    prof = G.gamma_profile(T.parse_chain_rows(ROWS, "SPY", SPOT, TODAY), SPOT)
    assert prof["available"] is True
    assert prof["regime"] in ("POSITIVE", "NEGATIVE")
    assert prof["total_open_interest"] == 58308 + 82245 + 49990
