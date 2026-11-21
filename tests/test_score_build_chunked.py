"""A FULL build_scores streams chunks to disk instead of holding the universe in memory (the shadow v2 columns pushed the single-frame build past the hosted runner's memory,
run 44904664034). The output must be IDENTICAL however it is chunked, the parts must never leak, and a crash must leave the previous file intact."""
import numpy as np
import pandas as pd
import pytest

from src.data.fmp_client import resample_to_weekly
from src.scanner import score_runner as SR

TICKERS = ["AAA", "BBB", "CCC", "DDD", "EEE"]


def _panel(tickers, n=300, seed=3):
    rows = []
    for k, t in enumerate(tickers):
        rng = np.random.default_rng(seed + k)
        close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.013, n))
        rows.append(pd.DataFrame({"date": pd.bdate_range("2021-01-04", periods=n), "ticker": t, "open": close, "high": close * 1.006, "low": close * 0.994,
                                  "close": close, "volume": rng.uniform(5e5, 2e6, n)}))
    return pd.concat(rows, ignore_index=True)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    panel = _panel(TICKERS)
    spy = _panel(["SPY"], seed=99).drop(columns="ticker")
    weekly = pd.concat([resample_to_weekly(g.drop(columns="ticker")).assign(ticker=t) for t, g in panel.groupby("ticker")], ignore_index=True)
    paths = {"PANEL_DAILY": tmp_path / "panel_daily.parquet", "PANEL_WEEKLY": tmp_path / "panel_weekly.parquet", "SPY_DAILY": tmp_path / "spy_daily.parquet",
             "SCORES_DAILY": tmp_path / "scores_daily.parquet"}
    panel.to_parquet(paths["PANEL_DAILY"], index=False)
    weekly.to_parquet(paths["PANEL_WEEKLY"], index=False)
    spy.to_parquet(paths["SPY_DAILY"], index=False)
    for k, v in paths.items():
        monkeypatch.setattr(SR, k, v)
    monkeypatch.setattr(SR, "load_earnings", lambda: {})
    monkeypatch.setattr(SR, "load_earnings_dates_full", lambda: {})
    import src.data.universe as U
    import src.data.ptj as PTJ
    monkeypatch.setattr(U, "load_universe", lambda include_benchmark=False: set(TICKERS) | {"SPY"})
    monkeypatch.setattr(PTJ, "load_held_positions", lambda: [])
    return paths["SCORES_DAILY"]


def test_the_output_is_identical_however_the_build_is_chunked(env, monkeypatch):
    monkeypatch.setattr(SR, "SCORE_CHUNK_TICKERS", 10_000)       # one chunk: the shape of the old single-frame build
    SR.build_scores()
    one = pd.read_parquet(env)
    monkeypatch.setattr(SR, "SCORE_CHUNK_TICKERS", 2)            # 3 chunks (2 + 2 + 1)
    SR.build_scores()
    many = pd.read_parquet(env)
    assert list(many.columns) == SR.SCORE_COLUMNS and len(many) > 500
    pd.testing.assert_frame_equal(one, many, check_dtype=True)
    assert set(many["ticker"]) == set(TICKERS)


def test_peak_frames_in_memory_never_exceed_one_chunk_and_the_parts_do_not_leak(env, monkeypatch):
    seen, orig = [], SR._write_chunk

    def spy(frames, parts_dir, n):
        seen.append(len(frames))
        return orig(frames, parts_dir, n)
    monkeypatch.setattr(SR, "_write_chunk", spy)
    monkeypatch.setattr(SR, "SCORE_CHUNK_TICKERS", 2)
    SR.build_scores()
    assert seen == [2, 2, 1], seen                                # the list held at most one chunk of ticker frames at any time
    assert not env.with_name("scores_daily.parts").exists(), "the part files must be removed after the combine"
    assert not env.with_name("scores_daily.parquet.tmp").exists()


def test_stale_parts_from_a_crashed_build_never_leak_into_the_next_one(env, monkeypatch):
    stale = env.with_name("scores_daily.parts")
    stale.mkdir()
    pd.DataFrame({"date": [pd.Timestamp("2020-01-01")], "ticker": ["ZZZ"], "sc_momentum": [1.0]}).to_parquet(stale / "part_99999.parquet", index=False)
    monkeypatch.setattr(SR, "SCORE_CHUNK_TICKERS", 2)
    SR.build_scores()
    assert "ZZZ" not in set(pd.read_parquet(env)["ticker"]) and not stale.exists()


def test_a_crash_while_combining_leaves_the_previous_scores_file_untouched(env, monkeypatch):
    monkeypatch.setattr(SR, "SCORE_CHUNK_TICKERS", 2)
    SR.build_scores()
    before = env.read_bytes()
    import pyarrow.parquet as pq

    class Boom(Exception):
        pass

    def bad_writer(*a, **k):
        raise Boom("disk full")
    monkeypatch.setattr(pq, "ParquetWriter", bad_writer)
    with pytest.raises(Boom):
        SR.build_scores()
    assert env.read_bytes() == before, "an interrupted combine must not damage the existing scores_daily.parquet"
    assert not env.with_name("scores_daily.parquet.tmp").exists() and not env.with_name("scores_daily.parts").exists()


def test_a_targeted_build_still_upserts_in_memory(env, monkeypatch):
    monkeypatch.setattr(SR, "SCORE_CHUNK_TICKERS", 2)
    SR.build_scores()
    full = pd.read_parquet(env)
    SR.build_scores(only_tickers=["BBB"])
    again = pd.read_parquet(env)
    assert len(again) == len(full) and set(again["ticker"]) == set(TICKERS)
    assert not env.with_name("scores_daily.parts").exists()
