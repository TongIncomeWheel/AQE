"""Yahoo bars — the parsing, and the place it sits in the chain.

Yahoo is used for one thing: the futures contracts our data plan gates. It is an
undocumented endpoint with no uptime promise, so the tests that matter are the
ones about WHERE it sits (never in front of the paid source, never the last
resort) and about not fabricating bars when it returns holes.
"""

from __future__ import annotations

import pandas as pd

from src.macro.crown import yahoo as Y

# Shape recorded from a live ZN=F response, trimmed to four sessions.
CHART = {
    "chart": {"result": [{
        "meta": {"symbol": "ZN=F"},
        "timestamp": [1785974400, 1786060800, 1786147200, 1786233600],
        "indicators": {"quote": [{
            "open": [108.5, 108.6, None, 108.7],
            "high": [108.9, 108.8, None, 109.0],
            "low": [108.2, 108.4, None, 108.5],
            "close": [108.75, 108.55, None, 108.671875],
            "volume": [412000, 388000, None, 401000],
        }]},
    }], "error": None}
}


def test_it_parses_a_recorded_chart_into_our_bar_shape():
    df = Y.parse_chart(CHART)
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(df) == 3                       # the null session is dropped
    assert df["close"].iloc[-1] == 108.671875
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_a_null_session_is_dropped_not_carried_forward():
    """A hole in a futures series is a missing session. Filling it forward puts
    a price the market never printed into a trend model."""
    df = Y.parse_chart(CHART)
    assert df["close"].notna().all()
    assert len(df) < len(CHART["chart"]["result"][0]["timestamp"])


def test_a_missing_open_is_filled_from_the_close_rather_than_losing_the_bar():
    c = {"chart": {"result": [{
        "timestamp": [1785974400],
        "indicators": {"quote": [{"open": [None], "high": [None], "low": [None],
                                  "close": [108.75], "volume": [1000]}]}}]}}
    df = Y.parse_chart(c)
    assert len(df) == 1
    assert df["open"].iloc[0] == df["close"].iloc[0] == 108.75


def test_an_error_or_empty_payload_is_an_empty_frame_not_an_exception():
    for bad in ({}, None, {"chart": {"result": None, "error": "Not Found"}},
                {"chart": {"result": [{"timestamp": [], "indicators": {}}]}}):
        assert Y.parse_chart(bad).empty


def test_every_cta_market_has_a_yahoo_symbol():
    from src.macro.crown.cta import MARKETS
    missing = [k for k in MARKETS if k not in Y.SYMBOLS]
    assert not missing, f"no Yahoo symbol for {missing}"


def test_the_dollar_uses_its_index_ticker_not_a_futures_one():
    """There is no DX=F on Yahoo — it 404s. The dollar is the ICE index."""
    assert Y.SYMBOLS["DX"] == "DX-Y.NYB"
    assert not Y.SYMBOLS["DX"].endswith("=F")


def test_an_unmapped_market_returns_empty_rather_than_guessing_a_symbol():
    assert Y.fetch_market("NOT_A_MARKET").empty


def test_yahoo_sits_between_the_paid_source_and_the_etf_proxy():
    """Order is the whole design. FMP first because it is paid and supported;
    Yahoo next because the ETF costs us quotable flip levels; ETF last so that
    if Yahoo disappears the layer degrades to what it does today rather than
    losing the market and silently re-rating flip_risk."""
    import inspect

    from src.macro.crown import data as F
    src = inspect.getsource(F.futures_bars)
    i_fmp = src.index("fetch_bars(sym, client=c)")
    i_yahoo = src.index("_yahoo.fetch_market(key)")
    i_etf = src.index('"etf_fallback"')
    assert i_fmp < i_yahoo < i_etf


def test_the_source_of_every_market_is_recorded():
    """A proxy must never be mistaken for the contract, and a free feed must
    never be mistaken for the paid one."""
    import inspect

    from src.macro.crown import data as F
    src = inspect.getsource(F.futures_bars)
    for label in ('"futures"', '"yahoo_futures"', '"etf_fallback"'):
        assert label in src
    assert '"via": used' in src
