"""refresh_earnings_dates_full: the nightly's INCREMENTAL, budgeted, loud report-date history refresh (score version v2's earn_score reads it)."""
import json
from datetime import date

import pytest

from src.data import earnings as E
from src.data.fmp_client import FMPError, FMPQuotaError


class Cfg:
    api_key = "k"


class FC:
    config = Cfg()

    def __init__(self, data=None, errors=None):
        self.data, self.errors, self.calls = data or {}, errors or {}, []

    def _get_json(self, url, params):
        t = params["symbol"]
        self.calls.append(t)
        if t in self.errors:
            raise self.errors[t]
        return [{"date": d} for d in self.data.get(t, [])]


@pytest.fixture()
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "EARNINGS_DATES_FULL_PATH", tmp_path / "earnings_dates_full.json")
    from src.data import paths as P
    monkeypatch.setattr(P, "OUTPUT_DIR", tmp_path / "out")
    return tmp_path


D = {"AAA": ["2025-02-01", "2025-05-01"], "BBB": ["2025-03-01"], "CCC": ["2025-04-01"]}
T0 = date(2026, 11, 23)


def test_first_run_pulls_every_missing_name_and_a_second_run_the_same_week_pulls_nothing(paths):
    c = FC(D)
    st = E.refresh_earnings_dates_full(c, ["AAA", "BBB", "CCC"], today=T0)
    assert sorted(c.calls) == ["AAA", "BBB", "CCC"] and st["pulled_this_run"] == 3 and st["missing_after"] == 0 and st["complete"]
    assert E.load_earnings_dates_full()["AAA"] == ["2025-02-01", "2025-05-01"]
    c2 = FC(D)
    st2 = E.refresh_earnings_dates_full(c2, ["AAA", "BBB", "CCC"], today=date(2026, 11, 26))        # 3 days later
    assert c2.calls == [] and st2["to_pull_at_start"] == 0 and st2["complete"]


def test_entries_older_than_seven_days_are_repulled_oldest_first_and_new_names_first_of_all(paths):
    E.refresh_earnings_dates_full(FC(D), ["AAA", "BBB"], today=date(2026, 11, 1))
    E.refresh_earnings_dates_full(FC(D), ["AAA"], today=date(2026, 11, 10))                          # AAA is now newer than BBB
    c = FC(D)
    E.refresh_earnings_dates_full(c, ["AAA", "BBB", "CCC"], today=date(2026, 11, 20))
    assert c.calls == ["CCC", "BBB", "AAA"]                                                         # missing first, then oldest pull first


def test_a_newer_report_than_the_last_pull_triggers_a_refresh_inside_the_week(paths):
    E.refresh_earnings_dates_full(FC(D), ["AAA", "BBB"], today=T0)
    c = FC(D)
    E.refresh_earnings_dates_full(c, ["AAA", "BBB"], recent={"AAA": ["2026-11-24"], "BBB": ["2025-01-01"]}, today=date(2026, 11, 25))
    assert c.calls == ["AAA"]                                                                       # AAA reported after its last pull; BBB did not


def test_the_budget_stops_the_pull_loudly_and_the_rest_wait_for_the_next_run(paths):
    ticks = iter([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    c = FC(D)
    st = E.refresh_earnings_dates_full(c, ["AAA", "BBB", "CCC"], budget_s=1.5, today=T0, clock=lambda: next(ticks))
    assert len(c.calls) == 1 and st["pulled_this_run"] == 1 and "time budget" in st["aborted"] and st["missing_after"] == 2 and not st["complete"]
    assert len(E.load_earnings_dates_full()) == 1


def test_failures_are_named_quota_aborts_loudly_and_existing_entries_are_kept(paths):
    E.refresh_earnings_dates_full(FC(D), ["AAA"], today=date(2026, 11, 1))
    c = FC(D, errors={"BBB": FMPError("FMP HTTP 500 boom")})
    st = E.refresh_earnings_dates_full(c, ["AAA", "BBB", "CCC"], today=T0)
    assert "BBB" in st["failed_this_run"] and st["missing_after"] == 1 and "CCC" in E.load_earnings_dates_full() and "AAA" in E.load_earnings_dates_full()
    c = FC(D, errors={"CCC": FMPQuotaError("denied")})
    st = E.refresh_earnings_dates_full(c, ["CCC", "BBB"], today=date(2026, 11, 30))
    assert "quota" in st["aborted"].lower() and not st["complete"]


def test_status_file_is_written_and_the_cache_format_is_backward_compatible(paths):
    E.refresh_earnings_dates_full(FC(D), ["AAA"], today=T0)
    status = json.loads((paths / "out" / "earnings_dates_status.json").read_text())
    assert status["pulled_this_run"] == 1 and status["tickers_requested"] == 1
    raw = json.loads((paths / "earnings_dates_full.json").read_text())
    assert set(raw) >= {"as_of", "dates", "pulled", "failed", "aborted"} and E.load_earnings_dates_full() == raw["dates"]
    # an entry from the older research pull (no `pulled`) is treated as stale, never trusted forever
    (paths / "earnings_dates_full.json").write_text(json.dumps({"as_of": "2026-11-21", "dates": {"AAA": ["2025-02-01"]}}))
    c = FC(D)
    E.refresh_earnings_dates_full(c, ["AAA"], today=T0)
    assert c.calls == ["AAA"]


def test_fetch_report_dates_one_returns_none_when_unavailable(paths):
    assert E.fetch_report_dates_one("AAA", client=FC(D)) == ["2025-02-01", "2025-05-01"]
    assert E.fetch_report_dates_one("ZZZ", client=FC(D)) is None
    assert E.fetch_report_dates_one("AAA", client=FC(errors={"AAA": FMPError("FMP HTTP 500")})) is None
