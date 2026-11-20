"""scripts/earnings_history_extract.py: per-symbol pull, floor, loud gaps, calendar time fill that stops where the plan stops. Offline, fake client."""
import importlib

import pandas as pd
import pytest

EH = importlib.import_module("scripts.earnings_history_extract")
from src.data.fmp_client import FMPError, FMPQuotaError  # noqa: E402

S = "https://x/stable"


class Cfg:
    api_key = "k"


class FakeClient:
    config = Cfg()

    def __init__(self, per_symbol, calendar=None, quota_at=None, fail=()):
        self.per_symbol, self.calendar, self.quota_at, self.fail, self.n = per_symbol, calendar or {}, quota_at, set(fail), 0

    def _get_json(self, url, params):
        if url.endswith("/earnings"):
            self.n += 1
            t = params["symbol"]
            if self.quota_at is not None and self.n > self.quota_at:
                raise FMPQuotaError("daily quota")
            if t in self.fail:
                raise FMPError("HTTP 500")
            return self.per_symbol.get(t, [])
        w = params["from"]
        if w not in self.calendar:
            raise FMPError("ACCESS DENIED higher plan")
        return self.calendar[w]


def rec(d, eps=1.0, est=0.9, rev=100, revest=90):
    return {"date": d, "epsActual": eps, "epsEstimated": est, "revenueActual": rev, "revenueEstimated": revest, "lastUpdated": "2026-11-20"}


def test_the_floor_is_applied_and_every_requested_field_is_a_column():
    c = FakeClient({"AAA": [rec("2027-02-04", None, 2.9, None, 150), rec("2026-11-02"), rec("2020-10-29"), rec("2020-11-05")]})
    out = EH.pull_symbols(c, ["AAA"], "2020-11-01", S)
    df = pd.DataFrame(out["rows"], columns=EH.COLUMNS)
    assert sorted(df["report_date"]) == ["2020-11-05", "2026-11-02", "2027-02-04"]
    assert set(EH.COLUMNS) <= set(df.columns)
    up = df[df["report_date"] == "2027-02-04"].iloc[0]
    assert not up["reported"] and up["eps_estimate"] == 2.9 and pd.isna(up["eps_actual"])


def test_a_failed_ticker_an_empty_ticker_and_a_quota_stop_are_all_named_never_silent():
    c = FakeClient({"AAA": [rec("2026-11-02")], "CCC": [rec("2019-01-01")]}, fail={"BBB"})
    out = EH.pull_symbols(c, ["AAA", "BBB", "CCC"], "2020-11-01", S)
    assert list(out["failed"]) == ["BBB"] and out["empty"] == ["CCC"] and out["aborted"] is None
    q = EH.pull_symbols(FakeClient({}, quota_at=1), ["AAA", "BBB", "CCC"], "2020-11-01", S)
    assert q["aborted"] and "after 1 of 3" in q["aborted"]


def test_the_time_fill_stamps_bmo_amc_for_served_weeks_and_stops_at_the_first_refused_window():
    from datetime import date, timedelta
    today = date(2026, 11, 20)
    end0 = today + timedelta(days=14)
    w0 = (end0 - timedelta(days=6)).isoformat()
    df = pd.DataFrame([EH.row_from("AAA", rec("2026-11-02")), EH.row_from("BBB", rec("2026-11-25", None, 1, None, 5)), EH.row_from("CCC", rec("2026-06-01"))])
    cal = {w0: [{"symbol": "BBB", "date": "2026-11-25", "time": "amc", "fiscalPeriod": "Q4", "fiscalYear": 2026, "periodEnding": "2026-10-31"}]}
    info = EH.fill_times(FakeClient({}, calendar=cal), df, S, 10, today=today)
    assert info["weeks_served"] == 1 and "refused" in info["stopped"]
    b = df[df["ticker"] == "BBB"].iloc[0]
    assert b["time"] == "amc" and b["time_source"] == "fmp_calendar" and b["fiscal_period"] == "Q4"
    assert (df[df["ticker"] != "BBB"]["time_source"] == "none").all()


def test_meta_names_the_gaps():
    df = pd.DataFrame([EH.row_from("AAA", rec("2022-05-05")), EH.row_from("AAA", rec("2026-11-02"))])
    pulled = {"rows": [], "failed": {"BBB": "x"}, "empty": ["CCC"], "aborted": None}
    m = EH.build_meta(df, ["AAA", "BBB", "CCC"], pulled, {"stopped": "refused"}, "2020-11-01")
    assert m["status"] == "partial" and m["gaps"]["failed_tickers"] == {"BBB": "x"} and m["gaps"]["tickers_with_no_rows_since_floor"] == ["CCC"]
    assert m["gaps"]["first_report_after_2021_06_30"] == ["AAA"] and m["tickers_with_rows"] == 1 and "not_point_in_time" in m
    assert EH.build_meta(pd.DataFrame(columns=EH.COLUMNS), ["A"], {"rows": [], "failed": {}, "empty": ["A"], "aborted": None}, {}, "2020-11-01")["status"] == "failed"
