"""Stage Weather — unit tests on synthetic weekly cycles.

Pins: the cycle order on a textbook base -> advance -> top -> decline path;
the 2-week confirmation (one close across the average is a candidate, not a
stage); the forming week never confirms; NA below MIN_WEEKS; breadth shares
and direction; the artifact build degrading loudly; and explain's output
having a headline and no sizing words.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.stages import classify as C
from src.stages import daily as D
from src.stages import explain as E
from src.stages import spec as S
from src.stages import weather as W


def _cycle(n_base=50, n_up=50, n_top=40, n_down=50, seed=0):
    rng = np.random.default_rng(seed)
    prior = 180 * np.cumprod(np.full(40, 0.985))       # the decline that makes the range a BASE
    base = prior[-1] + rng.normal(0, 0.6, n_base)
    up = base[-1] * np.cumprod(np.full(n_up, 1.02))
    top = up[-1] + rng.normal(0, 0.6, n_top)
    down = top[-1] * np.cumprod(np.full(n_down, 0.98))
    return np.concatenate([prior, base, up, top, down]), (40 + n_base, n_up, n_top, n_down)


def _frame(closes, start="2020-01-03", ticker=None):
    d = pd.date_range(start, periods=len(closes), freq="W-FRI")
    df = pd.DataFrame({"date": d, "close": closes, "high": closes * 1.01,
                       "low": closes * 0.99, "volume": 1e6})
    if ticker:
        df["ticker"] = ticker
    return df


def test_textbook_cycle_runs_1_2_3_4_in_order():
    closes, (b, u, t, dn) = _cycle()
    ser = C.stage_series(pd.Series(closes, index=pd.date_range("2020-01-03", periods=len(closes), freq="W-FRI")))
    st = ser["stage"].dropna().astype(int)
    seq = [s for i, s in enumerate(st) if i == 0 or s != st.iat[i - 1]]
    assert seq[-5:] == [4, 1, 2, 3, 4], seq
    assert int(ser["stage"].iat[b + u - 1]) == 2  # end of the advance
    assert int(st.iat[-1]) == 4                 # end of the decline


def test_one_week_across_the_average_is_a_candidate_not_a_stage():
    closes = 100 * np.cumprod(np.full(80, 1.01))
    closes = np.append(closes, closes[-1] * 0.80)     # one hard weekly close under the MA
    r = C.classify(_frame(closes))
    assert r["status"] == "OK" and r["stage"] == 2
    assert r["candidate"] == 3                         # the warning
    closes2 = np.append(closes, closes[-1] * 0.99)     # a second week under: confirmed
    r2 = C.classify(_frame(closes2))
    assert r2["stage"] == 3 and r2["previous_stage"] == 2
    assert r2["transition"] == "TOPPING" and r2["confirmed_this_week"] is True


def test_forming_week_never_confirms():
    closes = 100 * np.cumprod(np.full(80, 1.01))
    closes = np.append(closes, [closes[-1] * 0.80, closes[-1] * 0.79])
    df = _frame(closes)
    cutoff = df["date"].iloc[-2]                       # last bar is still forming
    r = C.classify(df, forming_after=cutoff)
    assert r["stage"] == 2 and r["candidate"] == 3 and r["candidate_forming"] == 3
    assert r["as_of_week"] == cutoff.date().isoformat()


def test_not_enough_history_is_na_never_a_guess():
    r = C.classify(_frame(np.linspace(100, 120, S.MIN_WEEKS - 1)))
    assert r["status"] == "NA" and "needed" in r["reason"]


def test_mansfield_rs_reads_outperformance():
    n = 120
    bench = pd.Series(100 * np.cumprod(np.full(n, 1.002)), index=pd.date_range("2020-01-03", periods=n, freq="W-FRI"))
    strong = 100 * np.cumprod(np.concatenate([np.full(n - 20, 1.002), np.full(20, 1.02)]))
    r = C.classify(_frame(strong), bench)
    assert r["rs_mansfield"] > 0 and r["rs_rising"] is True


def _panels(tmp_path, tickers: dict):
    wk = pd.concat([_frame(c, ticker=t) for t, c in tickers.items()], ignore_index=True)
    wp = tmp_path / "w.parquet"
    wk.to_parquet(wp)
    dp = tmp_path / "d.parquet"
    pd.DataFrame({"date": [wk["date"].max()], "ticker": ["SPY"], "close": [1.0]}).to_parquet(dp)
    return wp, dp


def test_breadth_shares_and_market_read(tmp_path):
    up = 100 * np.cumprod(np.full(120, 1.01))
    dn = 100 * np.cumprod(np.full(120, 0.99))
    names = {"SPY": up, "QQQ": up, "XLK": up, "XLE": dn,
             "AAA": up, "BBB": up, "CCC": up, "DDD": dn}
    wp, dp = _panels(tmp_path, names)
    out = W.compute(wp, dp, ["XLK", "XLE"], held=["DDD", "ZZZ"], daily_list=["AAA"])
    b = out["breadth"]
    assert b["status"] == "OK" and b["now"]["n"] == 4
    assert b["now"]["stage_2_pct"] == 75.0 and b["now"]["stage_4_pct"] == 25.0
    assert out["market_read"]["stage"] == 2
    assert out["sector_groups"]["stage_2"] == ["XLK"] and out["sector_groups"]["stage_4"] == ["XLE"]
    assert out["held"]["ZZZ"]["status"] == "NA"        # missing held name is LOUD, not dropped
    assert "_series" not in out["market"]["SPY"]


def test_artifact_unavailable_without_panel(tmp_path):
    art = D.run_stage_weather(tmp_path / "nope.parquet", tmp_path / "d.parquet", tmp_path / "e.json")
    assert art["status"] == "UNAVAILABLE" and "not found" in art["reason"]
    assert art["plain_english"]["headline"].startswith("Stage Weather unavailable")


def test_full_run_and_publish(tmp_path, monkeypatch):
    up = 100 * np.cumprod(np.full(120, 1.01))
    wp, dp = _panels(tmp_path, {"SPY": up, "QQQ": up, "AAA": up})
    ex = tmp_path / "e.json"
    ex.write_text(json.dumps({"daily_list": [{"ticker": "AAA"}], "held_positions": [{"ticker": "AAA"}],
                              "held_positions_status": "live"}))
    art = D.run_stage_weather(wp, dp, ex)
    assert art["status"] == "OK" and art["held"]["AAA"]["stage"] == 2
    monkeypatch.setattr(D, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(D, "LOCAL_PATH", tmp_path / "stage_weather.json")
    monkeypatch.setattr(D, "PUBLISHED_PATH", tmp_path / "aqe_stage_weather.json")
    D.write_artifacts(art)
    pub = json.loads((tmp_path / "aqe_stage_weather.json").read_text())
    assert list(pub)[0] == "read_me_first" and "by_ticker" not in pub
    text = json.dumps(pub["read_me_first"]).lower()
    assert "stage 2" in text
    for word in ("shares", "position size", "buy now", "sell now"):
        assert word not in text


def test_explain_is_pure():
    import inspect
    src = inspect.getsource(E)
    assert "import pandas" not in src and "open(" not in src


def test_explain_separates_confirmed_stage_from_this_weeks_close(tmp_path):
    # Confirmed Stage 2, but the last completed week closed under the average:
    # the copy must say "below" and flag the unconfirmed Stage 3 read, never
    # describe price as above a rising average.
    up = 100 * np.cumprod(np.full(100, 1.01))
    spy = np.append(up, up[-1] * 0.80)
    wp, dp = _panels(tmp_path, {"SPY": spy, "QQQ": spy, "AAA": spy})
    art = D.run_stage_weather(wp, dp, tmp_path / "missing.json")
    pe = art["plain_english"]
    assert art["market_read"]["stage"] == 2 and art["market_read"]["change_in_progress"]
    assert "below the 30-week average" in pe["because"][0]
    assert any("unconfirmed" in w for w in pe["watch_for"])
    assert not any("first sign of a top" in w for w in pe["watch_for"])
    assert art["held_status"].startswith("UNAVAILABLE")      # missing export is loud
