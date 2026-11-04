import pandas as pd
from src.valen import breadth as B


def _panel(last):
    d = pd.bdate_range(end=last, periods=70)
    rows = [{"ticker": t, "date": x, "close": 10 + i * 0.1 + (t == "B")}
            for t in ("A", "B") for i, x in enumerate(d)]
    return pd.DataFrame(rows)


def test_old_panel_all_rows_stale():
    out = B.compute_breadth(_panel("2026-10-09"), expected_last_session="2026-10-19")
    assert out["stale"] and out["as_of"] == "2026-10-09"
    assert all(v["status"] == "STALE" for v in out.values() if isinstance(v, dict) and "status" in v)


def test_fresh_panel_not_stale():
    out = B.compute_breadth(_panel("2026-10-19"), expected_last_session="2026-10-19")
    assert not out["stale"]


def test_history_view_not_stale():
    out = B.compute_breadth_as_of(_panel("2026-10-19"), 1)
    assert not out["stale"]


def test_one_session_behind_is_now_stale_the_3_nov_case():
    """2026-11-03: the panel ended Fri 30 Oct, the last completed session was Mon 2 Nov. Fri->Mon is ONE business day and
    used to pass as fresh; the strict guard calls it STALE on every row, with the reason."""
    out = B.compute_breadth(_panel("2026-10-30"), expected_last_session="2026-11-02")
    assert out["stale"] and out["as_of"] == "2026-10-30"
    assert all(v["status"] == "STALE" and "2026-11-02" in v["reason"] for v in out.values() if isinstance(v, dict) and "status" in v)
    assert out["freshness"]["current"] == 0


def test_a_half_refreshed_panel_is_stale_even_though_its_newest_date_is_right():
    """A panel where only some tickers have the newest bar reads each ticker at its own last bar - mixed dates. Under 95%
    current is STALE, with the counts in the reason."""
    d = pd.bdate_range(end="2026-11-02", periods=70)
    rows = []
    for i in range(100):
        dd = d if i < 60 else d[:-1]                    # 60% carry the 2 Nov bar, 40% stop a session earlier
        rows += [{"ticker": f"T{i}", "date": x, "close": 10 + j * 0.1} for j, x in enumerate(dd)]
    out = B.compute_breadth(pd.DataFrame(rows), expected_last_session="2026-11-02")
    assert out["stale"] and out["freshness"]["current"] == 60 and "60/100" in out["freshness"]["reason"]
    rows2 = []
    for i in range(100):
        dd = d if i < 95 else d[:-1]
        rows2 += [{"ticker": f"T{i}", "date": x, "close": 10 + j * 0.1} for j, x in enumerate(dd)]
    assert not B.compute_breadth(pd.DataFrame(rows2), expected_last_session="2026-11-02")["stale"]      # exactly 95% passes


def test_the_last_completed_session_follows_the_new_york_clock_and_holidays():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.data.sessions import last_completed_session as L
    sgt = lambda s: datetime.fromisoformat(s).replace(tzinfo=ZoneInfo("Asia/Singapore"))
    assert str(L(sgt("2026-11-03T06:54:00"))) == "2026-11-02"          # the morning run reads Monday's close
    assert str(L(sgt("2026-11-02T06:00:00"))) == "2026-10-30"          # Sunday ET: Friday's close
    assert str(L(sgt("2026-11-27T08:00:00"))) == "2026-11-25"          # Thanksgiving ET: Wednesday's close
    assert str(L(datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("America/New_York")))) == "2026-11-02"      # mid-session: yesterday


def test_cboe_is_retried_once_after_a_wait_when_it_is_a_session_behind_and_labelled_if_still_behind():
    from src.macro.crown import data as D

    class FakeCboe:
        def __init__(self, seq): self.seq, self.calls = list(seq), 0
        def refresh(self):
            self.calls += 1
            return self.seq.pop(0)

    waited = []
    c = FakeCboe([{"ok": True, "as_of": "2026-11-02"}])           # the retry brings it current
    st = D._retry_if_behind(c, {"ok": True, "as_of": "2026-10-30"}, sleep=waited.append, expected="2026-11-02", wait_s=300)
    assert waited == [300] and c.calls == 1 and st["as_of"] == "2026-11-02" and st["_retry"]["still_behind"] is False
    waited.clear()
    c = FakeCboe([{"ok": True, "as_of": "2026-10-30"}])           # still behind after the one retry: labelled, no second wait
    st = D._retry_if_behind(c, {"ok": True, "as_of": "2026-10-30"}, sleep=waited.append, expected="2026-11-02", wait_s=300)
    assert waited == [300] and c.calls == 1 and st["_retry"]["still_behind"] is True
    waited.clear()
    c = FakeCboe([])                                                # already current: no wait, no retry
    st = D._retry_if_behind(c, {"ok": True, "as_of": "2026-11-02"}, sleep=waited.append, expected="2026-11-02")
    assert waited == [] and c.calls == 0 and st["_retry"]["retried"] is False


def test_ghost_tickers_neither_fake_a_fresh_panel_nor_make_a_refreshed_one_read_stale():
    """4 Nov: 537 of 4,316 tickers had left the universe and never got a new bar, so a fully refreshed panel read 87% current. Tickers
    more than 10 sessions behind are excluded from the denominator and reported."""
    d = pd.bdate_range(end="2026-11-02", periods=70)
    rows = []
    for i in range(100):
        rows += [{"ticker": f"T{i}", "date": x, "close": 10 + j * 0.1} for j, x in enumerate(d)]        # 100 live names carry the bar
    old = pd.bdate_range(end="2026-09-01", periods=70)
    for i in range(20):
        rows += [{"ticker": f"G{i}", "date": x, "close": 5 + j * 0.1} for j, x in enumerate(old)]       # 20 ghosts, last bar in September
    fr = B.freshness(pd.DataFrame(rows), "2026-11-02")
    assert not fr["stale"] and fr["current"] == 100 and fr["total"] == 100 and fr["excluded_dead"] == 20, fr
    # but a panel that is genuinely behind is still stale (the live names are the ones that matter)
    rows2 = []
    for i in range(100):
        dd = d if i < 60 else d[:-1]
        rows2 += [{"ticker": f"T{i}", "date": x, "close": 10 + j * 0.1} for j, x in enumerate(dd)]
    assert B.freshness(pd.DataFrame(rows2), "2026-11-02")["stale"]
