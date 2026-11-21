"""Shadow v2: items 12 (NaN instead of default credits), 13 (earn_score as of each bar), 14 (SPY aligned by date), 18 (week-closing days see their own completed week)."""
import numpy as np
import pandas as pd

from src.data import earnings as E
from src.engines import health, k39, mp, readiness, structure
from src.engines import utils as U


def _ohlcv(n, start="2020-01-01", drift=0.0004, seed=1, vol=0.012):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(drift, vol, n))
    return pd.DataFrame({"date": pd.bdate_range(start, periods=n), "open": close, "high": close * 1.005, "low": close * 0.995, "close": close,
                         "volume": rng.uniform(5e5, 2e6, n)})


def _spy(n, start="2020-01-01", seed=7):
    d = _ohlcv(n, start=start, seed=seed, vol=0.008)
    return d


# ------------------------------------------------------------------ item 18
def test_item18_a_friday_row_sees_its_own_completed_week_and_midweek_rows_are_unchanged():
    d = pd.Series(pd.bdate_range("2024-01-01", "2024-02-23"))
    wk = pd.DataFrame({"date": pd.date_range("2024-01-05", "2024-03-01", freq="W-FRI")})
    wk["x"] = np.arange(len(wk), dtype=float)
    strict, v2 = U.asof_weekly_value(d, wk, "x"), U.asof_weekly_value_v2(d, wk, "x")
    dow = pd.to_datetime(d).dt.weekday
    assert (v2[dow == 4].to_numpy() == (np.arange(len(wk))[:int((dow == 4).sum())])).all()          # each Friday = its own week
    assert np.array_equal(strict[dow != 4].fillna(-1).to_numpy(), v2[dow != 4].fillna(-1).to_numpy())  # Mon-Thu unchanged
    assert (v2[dow == 4].to_numpy() > strict[dow == 4].fillna(-1).to_numpy()).all()                    # the strict value was a week stale


def test_item18_a_holiday_shortened_week_closes_on_thursday_and_the_last_row_needs_a_friday():
    # Friday 2024-03-29 is a market holiday: Thursday the 28th is the week's last row.
    dates = pd.Series(pd.to_datetime(["2024-03-26", "2024-03-27", "2024-03-28", "2024-04-01", "2024-04-02"]))
    wk = pd.DataFrame({"date": pd.to_datetime(["2024-03-22", "2024-03-29", "2024-04-05"]), "x": [1.0, 2.0, 3.0]})
    v2 = U.asof_weekly_value_v2(dates, wk, "x")
    assert v2.iloc[2] == 2.0                      # Thursday, week complete (next row is in a later week): its own bar (dated the holiday Friday)
    assert v2.iloc[1] == 1.0 and v2.iloc[0] == 1.0
    assert v2.iloc[4] == 2.0                      # Tuesday, last row but NOT a Friday: the forming week is not used


def test_item18_k39_and_health_use_the_completed_week_only_when_asked():
    n = 400
    d = _ohlcv(n)
    wk = d.set_index("date").resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index()
    g0, v0 = k39.compute_k39_gate(wk, d["date"])
    g1, v1 = k39.compute_k39_gate(wk, d["date"], week_complete=True)
    dow = d["date"].dt.weekday
    assert np.allclose(v0[dow != 4].fillna(-1).to_numpy(), v1[dow != 4].fillna(-1).to_numpy())          # unchanged away from Fridays
    assert not np.allclose(v0[dow == 4].fillna(-1).to_numpy(), v1[dow == 4].fillna(-1).to_numpy())      # changed on Fridays
    h = health.compute(d, spy_daily=_spy(n), weekly=wk)
    assert "hl_trend_v2" in h.columns and "hl_score_v2" in h.columns and "hl_score" in h.columns


# ------------------------------------------------------------------ item 14
def test_item14_positional_spy_alignment_pairs_the_wrong_days_and_the_date_alignment_does_not():
    n = 300
    d = _ohlcv(n, start="2020-03-02")
    spy = _spy(n + 120, start="2020-01-01")                       # SPY starts 40 bars earlier and runs past the ticker: bar i of the ticker is NOT bar i of SPY
    assert U.spy_positional_misaligned_bars(d["date"], spy) == n
    al = U.align_spy_close(spy, d["date"])
    spy_idx = spy.set_index("date")["close"]
    assert np.allclose(al.to_numpy(), spy_idx.loc[d["date"]].to_numpy())
    same = U.spy_positional_misaligned_bars(spy["date"], spy)
    assert same == 0
    r = readiness.compute(d, spy_daily=spy)
    assert {"rd_rs_bonus_v2", "rd_score_v2", "rd_rs_bonus", "rd_score"} <= set(r.columns)
    assert not np.allclose(r["rd_rs_bonus"].to_numpy(), r["rd_rs_bonus_v2"].to_numpy())
    # aligned inputs: both agree
    d2 = _ohlcv(n, start="2020-01-01")
    r2 = readiness.compute(d2, spy_daily=_spy(n, start="2020-01-01"))
    assert np.allclose(r2["rd_rs_bonus"].to_numpy(), r2["rd_rs_bonus_v2"].to_numpy())
    h2 = health.compute(d2, spy_daily=_spy(n, start="2020-01-01"), weekly=None)
    assert np.allclose(h2["hl_rs"].to_numpy(), h2["hl_rs_v2"].to_numpy())


# ------------------------------------------------------------------ item 13
def test_item13_earn_score_v2_is_as_of_each_bar_and_nan_without_dates_and_after_the_last_report():
    dates = pd.Series(pd.to_datetime(["2022-01-03", "2022-01-28", "2022-02-02", "2022-02-03", "2022-04-20", "2022-05-10"]))
    reports = ["2022-02-03", "2022-05-03"]
    s = E.build_earnings_series_v2(dates, reports)
    # 01-03 -> 31 days to 02-03: 10; 01-28 -> 6 days: 4; 02-02 -> 1 day: 0; 02-03 -> 0 days: 0; 04-20 -> 13 days: 7; 05-10 -> no report on/after: NaN
    assert s.iloc[0] == 10 and s.iloc[1] == 4 and s.iloc[2] == 0 and s.iloc[3] == 0 and s.iloc[4] == 7 and np.isnan(s.iloc[5])
    assert E.build_earnings_series_v2(dates, None).isna().all() and E.build_earnings_series_v2(dates, []).isna().all()
    # the live series scores every past bar against TODAY's next date: it cannot see the 2022-02-03 report from 2022-01-28
    live = E.build_earnings_series(dates, "T", {"T": "2030-01-01"})
    assert (live == 10.0).all()


def test_item13_pull_earnings_dates_full_retries_a_429_and_names_failures(tmp_path, monkeypatch):
    from src.data.fmp_client import FMPError

    class Cfg:
        api_key = "k"

    class C:
        config = Cfg()
        n = 0
        def _get_json(self, url, params):
            t = params["symbol"]
            if t == "BAD":
                raise FMPError("HTTP 500")
            if t == "SLOW":
                C.n += 1
                if C.n < 3:
                    raise FMPError("FMP HTTP 429 Limit Reach")
            return [{"date": "2022-02-03"}, {"date": "2017-01-01"}]
    monkeypatch.setattr(E, "EARNINGS_DATES_FULL_PATH", tmp_path / "full.json")
    waits = []
    res = E.pull_earnings_dates_full(C(), ["OK", "SLOW", "BAD"], sleep=waits.append)
    assert res["failed"].keys() == {"BAD"} and len(waits) == 2
    got = E.load_earnings_dates_full()
    assert got == {"OK": ["2022-02-03"], "SLOW": ["2022-02-03"]}


# ------------------------------------------------------------------ item 12
def test_item12_structure_v2_is_nan_where_the_live_score_invents_points():
    n = 260
    d = _ohlcv(n)
    out = structure.compute(d, spy_daily=_spy(n), weekly=pd.DataFrame(), ticker="T", earn_dates_full=None)
    last = out.iloc[-1]
    assert last["wk_score"] == 7.5 and np.isnan(last["wk_score_v2"])          # no weekly history: the live default credits 7.5
    assert last["earn_score"] == 10.0 and np.isnan(last["earn_score_v2"])     # no earnings dates: the live default credits 10
    assert np.isnan(last["structure_100_v2"]) and not np.isnan(last["structure_100"])
    # a missing SPY comparison: RS is NaN in v2, 0 (and 6 + 9 points) in the live series
    out2 = structure.compute(d, spy_daily=_spy(n).iloc[0:0], weekly=pd.DataFrame())
    assert out2["rs_spy_score_v2"].isna().all() and (out2["rs_spy_score"].dropna() >= 3).all()


def test_item12_mp_v2_is_nan_for_an_uncomputable_zscore_and_a_missing_benchmark():
    n = 200
    flat = pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=n), "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1e6})
    o = mp.compute(flat, spy_daily=_spy(n))
    last = o.iloc[-1]
    assert last["roc_zscore"] == 0.0 and last["abs_mom_score"] == 10.0          # the live fill: zero stdev reads as a z-score of 0 and credits 10 points
    assert np.isnan(o["abs_mom_score_v2"].iloc[-1])
    d = _ohlcv(n)
    o2 = mp.compute(d, spy_daily=_spy(n).iloc[0:0])
    assert o2["rel_mom_score_v2"].isna().all() and (o2["rel_mom_score"].dropna() >= 8).all()     # live: excess_return 0 credits 8 points
    assert o2["mp_score_v2"].isna().all() and o2["mp_score"].notna().any()
    o3 = mp.compute(d, spy_daily=_spy(n, start="2020-01-01"))
    ok = o3["mp_score_v2"].notna()
    assert ok.sum() > 50 and o3["mp_score_v2"][ok].between(0, 100).all()


def test_score_columns_carry_the_v2_block_for_items_12_13_14_18():
    from src.scanner.score_runner import SCORE_COLUMNS
    for c in ("mp_score_v2", "rs_spy_score_v2", "rs_accel_score_v2", "wk_score_v2", "earn_score_v2", "rd_score_v2", "rd_rs_bonus_v2", "hl_score_v2", "hl_rs_v2",
              "hl_trend_v2", "k39_gate_v2", "k39_value_v2", "abs_mom_score_v2", "rel_mom_score_v2"):
        assert c in SCORE_COLUMNS, c
