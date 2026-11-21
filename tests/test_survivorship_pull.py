"""scripts/survivorship_pull.py: candidate union + exclusions are counted, a failed source is named, delisted vs still-trading classification, month-end reduction,
PARTIAL labelling, read-only workflow. Offline, fake client."""
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from scripts import survivorship_pull as SP

ROOT = Path(__file__).resolve().parent.parent


class Cfg:
    api_key = "k"


class FC:
    config = Cfg()

    def __init__(self, bars=None, mcap=None):
        self.bars, self.mcap = bars or {}, mcap or {}

    def _get_json(self, url, params):
        k = url.rsplit("/", 1)[-1]
        src = self.bars if "historical-price-eod" in url else self.mcap
        v = src.get(params.get("symbol"), [])
        if isinstance(v, Exception):
            raise v
        return v


def _srcs(**kw):
    return {n: (lambda c, rows=rows, err=err: (rows, err)) for n, (rows, err) in kw.items()}


def test_candidates_union_filters_and_names_a_failed_source():
    rows_a = [{"symbol": "AAA", "name": "Alpha Inc", "exchange": "NASDAQ", "delisted_date": "2025-01-02", "source": "x"},
              {"symbol": "BBB.TO", "name": "Beta", "exchange": "TSX", "delisted_date": None, "source": "x"},
              {"symbol": "CCCW", "name": "Gamma Warrants", "exchange": "NASDAQ", "delisted_date": None, "source": "x"}]
    rows_b = [{"symbol": "aaa", "name": None, "exchange": "NYSE", "delisted_date": None, "source": "y"},
              {"symbol": "BRK.B", "name": "Berk", "exchange": "NYSE", "delisted_date": None, "source": "y"},
              {"symbol": "", "name": None, "exchange": None, "delisted_date": None, "source": "y"}]
    df, info = SP.build_candidates(None, _srcs(fmp_page0=(rows_a, None), alpaca_inactive=(rows_b, None), aqe_panel_stale=([], "RuntimeError: restore failed")))
    assert sorted(df["symbol"]) == ["AAA", "BRK-B"]
    assert df.set_index("symbol").loc["AAA", "sources"] == "fmp_page0,alpaca_inactive"
    assert info["excluded"] == {"non_us_exchange": 1, "derivative_name_or_symbol": 1, "blank_symbol": 1}
    assert info["sources"]["aqe_panel_stale"]["error"] == "RuntimeError: restore failed"      # a failed source is named, never silent


def _bar(d, c=10.0):
    return {"date": d, "open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 100}


def test_classification_delisted_still_trading_and_no_bars():
    today = date(2026, 11, 21)
    fc = FC(bars={"DEAD": [_bar("2023-03-09"), _bar("2023-03-08")], "LIVE": [_bar("2026-11-20")], "OLD": []},
            mcap={"DEAD": [{"date": "2023-03-09", "marketCap": 6e9}, {"date": "2023-03-08", "marketCap": 15e9}, {"date": "2023-02-28", "marketCap": 17e9}]})
    cls: dict = {}
    got = SP.pull_one(fc, "DEAD", "2021-03-01", today, cls)
    assert cls["DEAD"]["class"] == "delisted_with_bars" and cls["DEAD"]["last_bar"] == "2023-03-09" and cls["DEAD"]["mcap_months"] == 2
    assert len(got) == 1 and list(got[0]["bars"]["date"].dt.strftime("%Y-%m-%d")) == ["2023-03-08", "2023-03-09"]
    assert SP.pull_one(fc, "LIVE", "2021-03-01", today, cls) == [] and cls["LIVE"]["class"] == "still_trading"
    assert SP.pull_one(fc, "OLD", "2021-03-01", today, cls) == [] and cls["OLD"]["class"] == "no_bars_in_window"
    assert cls["OLD"]["reason"] == "fmp_empty_response"


def test_month_end_keeps_the_last_row_of_each_month_per_ticker():
    rows = [{"ticker": "A", "date": "2023-01-30", "market_cap": 1}, {"ticker": "A", "date": "2023-01-31", "market_cap": 2},
            {"ticker": "A", "date": "2023-02-14", "market_cap": 3}, {"ticker": "B", "date": "2023-01-12", "market_cap": 9},
            {"ticker": "B", "date": "2023-01-13", "market_cap": None}]
    m = SP.month_end(rows).set_index(["ticker", "date"])["market_cap"]
    assert m.to_dict() == {("A", pd.Timestamp("2023-01-31")): 2, ("A", pd.Timestamp("2023-02-14")): 3, ("B", pd.Timestamp("2023-01-12")): 9}
    assert SP.month_end([]).empty


def test_partial_label_and_readonly_workflow():
    assert "THIN BEFORE ~2019" in SP.PARTIAL_NOTE and "MISSES SOME MERGERS" in SP.PARTIAL_NOTE and "Premium" in SP.PARTIAL_NOTE
    code = (ROOT / "scripts" / "survivorship_pull.py").read_text()
    assert code.count("_PARTIAL_") >= 4 and "save_snapshot" not in code
    y = (ROOT / ".github" / "workflows" / "survivorship-partial.yml").read_text()
    assert "workflow_dispatch:" in y and "schedule:" not in y and "push:" not in y and "contents: read" in y and "contents: write" not in y
    assert "group: aqe-research" in y and "ALPACA_API_KEY_ID" in y and "fetch-depth: 0" in y


def test_unknown_symbol_404_is_no_bars_not_a_failure_and_5xx_is_retried_and_the_path_is_the_slash_endpoint():
    from src.data.fmp_client import FMPError
    today = date(2026, 11, 21)
    err404 = FMPError("FMP HTTP 404 for https://financialmodelingprep.com/stable/historical-price-eod/full: []")
    fc = FC(bars={"JUNK": err404})
    cls: dict = {}
    assert SP.pull_one(fc, "JUNK", "2021-03-01", today, cls) == [] and cls["JUNK"]["class"] == "no_bars_in_window"

    class Flaky(FC):
        n = 0

        def _get_json(self, url, params):
            assert url.endswith("/historical-price-eod/full"), url
            Flaky.n += 1
            if Flaky.n < 3:
                raise FMPError("FMP HTTP 502 for x: ")
            return [_bar("2023-03-09")]
    got = SP._get_retry(Flaky(), "https://x/historical-price-eod/full", {}, sleep=lambda s: None)
    assert got and Flaky.n == 3
    b = SP.bars_frame(Flaky(), "AAA", "2021-03-01", today)
    assert len(b) == 1


def test_an_empty_mcap_year_window_404_does_not_fail_the_name_and_402_symbols_are_counted_with_a_reason():
    from src.data.fmp_client import FMPError
    today = date(2026, 11, 21)
    err = FMPError("FMP HTTP 404 for https://financialmodelingprep.com/stable/historical-market-cap: []")
    fc = FC(bars={"DEAD": [_bar("2023-03-09")], "ABR-PRC": FMPError("FMP HTTP 402 for x: Premium Query Parameter: 'Special Endpoint'")}, mcap={"DEAD": err})
    cls: dict = {}
    got = SP.pull_one(fc, "DEAD", "2021-03-01", today, cls)
    assert len(got) == 1 and got[0]["mcap"].empty and cls["DEAD"]["mcap_months"] == 0       # bars kept; the name is listed as lacking market cap
    assert SP.pull_one(fc, "ABR-PRC", "2021-03-01", today, cls) == [] and cls["ABR-PRC"]["reason"] == "fmp_402_premium_symbol"
