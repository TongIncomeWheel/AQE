"""scripts/research_extras.py: adaptive intraday windows (a capped response is detected), loud gaps, field shaping. Offline, fake client."""
from datetime import date

import pytest

from scripts import research_extras as RX
from src.data.fmp_client import FMPError, FMPQuotaError


class Cfg:
    api_key = "k"


class FC:
    """Fake client. `bars` is a list of 'YYYY-MM-DD HH:MM:SS' bar stamps; a response is newest-first and capped at `cap` rows."""
    config = Cfg()

    def __init__(self, bars=(), cap=None, **routes):
        self.bars, self.cap, self.routes, self.calls = sorted(bars, reverse=True), cap, routes, []

    def _get_json(self, url, params):
        self.calls.append((url.rsplit("/", 1)[-1], params.get("from"), params.get("to")))
        key = url.rsplit("/", 1)[-1]
        if key in self.routes:
            r = self.routes[key]
            if isinstance(r, Exception):
                raise r
            return r
        lo, hi = params["from"], params["to"]
        rows = [{"date": b, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10} for b in self.bars if lo <= b[:10] <= hi]
        return rows[: self.cap] if self.cap else rows


def _days(start, n):
    from datetime import timedelta
    d = date.fromisoformat(start)
    return [(d + timedelta(days=i)).isoformat() + " 09:30:00" for i in range(n)]


def test_fetch_range_returns_a_full_window_in_one_call():
    c = FC(bars=_days("2021-01-01", 365))
    assert len(RX.fetch_range(c, "A", date(2021, 1, 1), date(2021, 12, 31))) == 365 and len(c.calls) == 1


def test_a_capped_response_is_detected_and_the_older_part_is_re_asked():
    c = FC(bars=_days("2021-01-01", 365), cap=100)
    rows = RX.fetch_range(c, "A", date(2021, 1, 1), date(2021, 12, 31))
    assert len(rows) == 365 and len(c.calls) == 4          # 100 + 100 + 100 + 65, never silently truncated


def test_a_name_that_listed_late_costs_one_extra_empty_call_and_is_not_an_error():
    c = FC(bars=_days("2021-06-01", 30))
    rows = RX.fetch_range(c, "A", date(2021, 1, 1), date(2021, 12, 31))
    assert len(rows) == 30 and len(c.calls) == 2


def test_year_windows_cover_the_span_exactly():
    w = RX.year_windows("2020-11-01", date(2022, 3, 15))
    assert w[0] == (date(2020, 11, 1), date(2020, 12, 31)) and w[1] == (date(2021, 1, 1), date(2021, 12, 31)) and w[-1] == (date(2022, 1, 1), date(2022, 3, 15))


def test_fundamentals_rows_keep_the_point_in_time_keys_and_apply_the_floor():
    inc = [{"date": "2026-09-26", "fiscalYear": "2026", "period": "Q4", "filingDate": "2026-11-03", "acceptedDate": "2026-11-03 08:05:15", "revenue": 5, "netIncome": 2, "eps": 1.1, "epsDiluted": 1.0, "reportedCurrency": "USD"},
           {"date": "2016-12-31", "revenue": 1}]
    rows = RX.fundamentals_rows(FC(**{"income-statement": inc}), "AAPL", "2018-01-01")
    assert len(rows) == 1 and rows[0]["accepted_ts"] == "2026-11-03 08:05:15" and rows[0]["filing_date"] == "2026-11-03" and rows[0]["eps_diluted"] == 1.0


def test_profile_rows_merge_profile_and_float_and_an_empty_symbol_is_empty_not_a_row_of_nones():
    c = FC(profile=[{"companyName": "X", "sector": "Tech", "industry": "Software", "marketCap": 9}], **{"shares-float": [{"floatShares": 5, "outstandingShares": 6, "freeFloat": 80.0, "date": "2026-11-20"}]})
    r = RX.profile_rows(c, "X")[0]
    assert r["industry"] == "Software" and r["float_shares"] == 5 and r["free_float_pct"] == 80.0
    assert RX.profile_rows(FC(profile=[], **{"shares-float": []}), "Y") == []


def test_the_loop_names_failed_empty_and_quota_stops():
    seq = {"A": [{"x": 1}], "B": FMPError("500"), "C": []}
    def one(t):
        v = seq[t]
        if isinstance(v, Exception):
            raise v
        return v
    out = RX._loop(None, ["A", "B", "C"], one, 1e9)
    assert out["rows"] == [{"x": 1}] and list(out["failed"]) == ["B"] and out["empty"] == ["C"] and out["aborted"] is None
    def quota(t):
        if t == "B":
            raise FMPQuotaError("daily quota")
        return [{"x": 1}]
    q = RX._loop(None, ["A", "B", "C"], quota, 1e9)
    assert q["aborted"] and "after 1 of 3" in q["aborted"] and len(q["rows"]) == 1
    ticks = iter(range(0, 1000, 100))
    b = RX._loop(None, ["A", "B", "C"], lambda t: [{"x": 1}], 150, clock=lambda: next(ticks))
    assert b["aborted"] and "time budget" in b["aborted"]


def test_every_workflow_file_parses_and_a_dispatch_workflow_declares_workflow_dispatch():
    """2026-11-20: research-extras.yml merged with an unquoted ': ' in its name, so GitHub saw no workflow_dispatch trigger. Every workflow must be valid YAML."""
    import pathlib
    import yaml
    for p in sorted((pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows").glob("*.yml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert isinstance(d, dict) and (True in d or "on" in d), p.name
    d = yaml.safe_load((pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows" / "research-extras.yml").read_text(encoding="utf-8"))
    assert "workflow_dispatch" in (d.get(True) or d.get("on"))


def test_intraday_frame_is_compact_typed_and_deduplicated():
    import pandas as pd
    c = FC(bars=_days("2021-01-04", 20) + _days("2021-01-04", 3))        # duplicate stamps
    df = RX.intraday_frame(c, "A", "2021-01-01", date(2021, 6, 30))
    assert len(df) == 20 and list(df.columns) == ["ticker", "ts_et", "open", "high", "low", "close", "volume"]
    assert str(df["ticker"].dtype) == "category" and str(df["volume"].dtype) == "int64" and pd.api.types.is_datetime64_any_dtype(df["ts_et"])
    assert RX.intraday_frame(FC(bars=[]), "B", "2021-01-01", date(2021, 6, 30)).empty


def test_shards_cover_every_ticker_exactly_once():
    ts = [f"T{i:03d}" for i in range(101)]
    parts = [RX.shard(ts, i, 3) for i in (1, 2, 3)]
    assert sorted(sum(parts, [])) == sorted(ts) and sum(len(p) for p in parts) == 101 and not (set(parts[0]) & set(parts[1]))
