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
    assert all(v["status"] == "STALE" for v in out.values() if isinstance(v, dict))


def test_fresh_panel_not_stale():
    out = B.compute_breadth(_panel("2026-10-19"), expected_last_session="2026-10-20")
    assert not out["stale"]


def test_history_view_not_stale():
    out = B.compute_breadth_as_of(_panel("2026-10-19"), 1)
    assert not out["stale"]
