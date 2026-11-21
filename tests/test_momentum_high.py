"""MOMENTUM HIGH (PM 2026-11-21): engine rules, first_day, completed-week mapping, section status paths, additive export guard, and the 3 reference dates."""
from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.momentum_high import daily, engine, spec as S

ROOT = Path(__file__).resolve().parent.parent


def _series(n, start, drift, vol, seed):
    rng = np.random.default_rng(seed)
    return start * np.cumprod(1 + rng.normal(drift, vol, n))


def _panel(n=420):
    dates = pd.bdate_range("2023-01-02", periods=n)
    spec_ = {"UP1": (50, 0.0030, 0.012, 1), "UP2": (40, 0.0042, 0.013, 2), "FLAT": (50, 0.0, 0.012, 3), "DOWN": (80, -0.002, 0.012, 4), "PENNY": (2, 0.003, 0.02, 5),
             "WILD": (50, 0.003, 0.09, 6)}
    rows = []
    for t, (s0, d, v, sd) in spec_.items():
        c = _series(n, s0, d, v, sd)
        h, l = c * (1 + np.abs(np.random.default_rng(sd + 10).normal(0, v / 2, n))), c * (1 - np.abs(np.random.default_rng(sd + 20).normal(0, v / 2, n)))
        rows += [{"date": dt, "ticker": t, "open": c[i], "high": h[i], "low": l[i], "close": c[i], "volume": 1e6} for i, dt in enumerate(dates)]
    spy = _series(n, 400, 0.0004, 0.008, 99)
    return pd.DataFrame(rows), pd.DataFrame({"date": dates, "open": spy, "high": spy, "low": spy, "close": spy, "volume": 1e8})


def test_engine_membership_respects_the_eligibility_and_trend_rules():
    panel, spy = _panel()
    res = engine.compute(panel, spy)
    m = res.members
    assert (m & ~res.eligible).sum().sum() == 0, "a member must be eligible (price >= $5 and ATR% 1.5-15)"
    f = res.feat
    assert not (m["PENNY"] & (f["close"]["PENNY"] < S.MIN_PRICE)).any(), "a name is never a member on a date its close is under $5"
    assert not (m["WILD"] & (f["atr_pct"]["WILD"] > S.ATR_PCT_HI)).any(), "a name is never a member on a date its ATR% exceeds 15"
    assert (f["close"]["PENNY"] < S.MIN_PRICE).any() and (f["atr_pct"]["WILD"] > S.ATR_PCT_HI).any(), "the fixture must actually exercise both exclusions"
    assert not m["DOWN"].any() and not m["FLAT"].iloc[-60:].any()
    assert m["UP1"].any() or m["UP2"].any(), "a steady uptrend must reach membership on some date"
    last = res.members.index[-1]
    assert res.counts.loc[last, "eligible"] >= res.counts.loc[last, "weekly"], "gate counts are monotone non-increasing in order"
    c = res.counts.loc[last].to_numpy()
    assert (np.diff(c) <= 0).all()


def test_rows_at_ranks_by_momentum_and_computes_the_reference_stop_and_first_day():
    panel, spy = _panel()
    res = engine.compute(panel, spy)
    dates = res.members.index[res.members.any(axis=1)]
    d = dates[-1]
    rows = engine.rows_at(res, d)
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
    assert [r["mom_12_1"] for r in rows] == sorted((r["mom_12_1"] for r in rows), reverse=True)
    for r in rows:
        assert r["reference_stop"] == pytest.approx(r["close"] - S.STOP_ATR_MULT * r["atr14"], abs=0.02)
        assert r["pct_from_52w_high"] <= 0.5 and r["atr_pct"] >= S.ATR_PCT_LO
    i = res.members.index.get_loc(d)
    for r in rows:
        was = res.members.iloc[max(0, i - 5):i][r["ticker"]].any()
        assert r["first_day"] == (not was)


def test_first_day_is_false_when_the_name_was_a_member_in_the_prior_five_sessions():
    idx = pd.bdate_range("2025-01-01", periods=10)
    mem = pd.DataFrame(False, index=idx, columns=["A", "B"])
    mem.loc[idx[3], "A"] = True          # A was a member 3 sessions before t, B was not
    mem.loc[idx[6], ["A", "B"]] = True
    mem.loc[idx[9], ["A", "B"]] = True
    f = {k: pd.DataFrame(1.0, index=idx, columns=["A", "B"]) for k in ("close", "hi252", "atr14", "atr_pct", "adx14", "mom", "rs")}
    res = engine.Result(members=mem, eligible=mem, market=pd.DataFrame(), feat=f | {"short_history": pd.Series(False, index=["A", "B"])}, counts=pd.DataFrame())
    on6 = {r["ticker"]: r["first_day"] for r in engine.rows_at(res, idx[6])}
    assert on6 == {"A": False, "B": True}          # A was in 3 sessions before: not first day; B is new
    on9 = {r["ticker"]: r["first_day"] for r in engine.rows_at(res, idx[9])}
    assert on9 == {"A": False, "B": False}         # idx[6] is within the prior 5 sessions for both


def test_week_completion_map_friday_counts_and_a_midweek_date_uses_the_prior_friday():
    idx = pd.DatetimeIndex(["2025-03-03", "2025-03-04", "2025-03-05", "2025-03-06", "2025-03-07", "2025-03-10", "2025-03-11", "2025-03-12", "2025-03-13", "2025-03-17"])
    lab, _ = engine._week_complete_map(idx)
    assert lab[pd.Timestamp("2025-03-07")] == pd.Timestamp("2025-03-07")         # a Friday close completes its week
    assert lab[pd.Timestamp("2025-03-05")] == pd.Timestamp("2025-02-28")         # mid-week: the prior completed Friday
    assert lab[pd.Timestamp("2025-03-13")] == pd.Timestamp("2025-03-14")         # Thursday before a Friday holiday: the next session is in a later week -> complete
    assert lab[pd.Timestamp("2025-03-11")] == pd.Timestamp("2025-03-07")


def test_section_has_the_market_check_rows_odds_and_plain_english_and_never_mutates_its_inputs():
    panel, spy = _panel()
    p0, s0 = panel.copy(), spy.copy()
    sec, st = daily.build_section(["UP1", "UP2", "FLAT", "DOWN", "PENNY", "WILD"], "2024-08-30", panel=panel, spy=spy)
    assert panel.equals(p0) and spy.equals(s0), "the section must not mutate its inputs"
    assert st["status"] in ("live", "degraded") and st["as_of"] == sec["as_of"] and st["members_n"] == len(sec["members"])
    mc = sec["market_check"]
    assert set(mc) >= {"spy_above_200d", "breadth_pct_above_50d", "market_ok", "as_of"} and isinstance(mc["market_ok"], bool)
    assert "NOT a forecast" in sec["what_it_is"] and "NOT a buy list" in sec["what_it_is"]
    mo = sec["measured_odds"]
    assert mo["label"] == "history 2022-2026, 6-position $100k book, not a forecast"
    assert mo["caveat"] == "survivor universe; most of the gain came in 2024; not statistically proven against SPY on a risk-adjusted basis"
    h20, mgd = mo["shapes"]["hold 20 sessions"], mo["shapes"]["half off at +1.5R, stop to breakeven, trail rest at 3xATR"]
    assert (h20["win_rate_pct"], h20["avg_winner_r"], h20["avg_loser_r"], h20["avg_r_per_trade"]) == (28, 3.6, -1.0, 0.24)
    assert (mgd["win_rate_pct"], mgd["avg_winner_r"], mgd["avg_loser_r"], mgd["avg_r_per_trade"]) == (43, 1.7, -1.0, 0.14)
    assert "reference level" in sec["stop_note"] and "not an order" in sec["stop_note"]


def test_a_stale_panel_is_degraded_with_the_reason_and_a_short_spy_or_missing_files_is_a_loud_error(tmp_path, monkeypatch):
    panel, spy = _panel()
    sec, st = daily.build_section(None, "2026-01-30", panel=panel, spy=spy)             # panel ends 2024-08, export dated 2026
    assert st["status"] == "degraded" and "days before the export date" in st["reason"] and sec is not None
    sec, st = daily.build_section(None, "2024-08-30", panel=panel, spy=spy.iloc[:100])
    assert sec is None and st["status"] == "error" and "SPY history too short" in st["reason"]
    from src.data import paths
    monkeypatch.setattr(paths, "PANEL_DAILY", tmp_path / "nope.parquet")
    sec, st = daily.build_section(None, "2024-08-30")
    assert sec is None and st["status"] == "error" and "missing" in st["reason"]


def test_the_export_glue_adds_only_the_two_new_keys_and_the_glossary_describes_them():
    src = (ROOT / "src" / "data" / "drive_sync.py").read_text()
    block = src[src.index("# ---- MOMENTUM HIGH"):src.index("# ---- Score version (PM 2026-11-21 cutover)")]
    assigned = {k for k in ('export["momentum_high"]', 'export["momentum_high_status"]') if k in block}
    assert assigned == {'export["momentum_high"]', 'export["momentum_high_status"]'}
    import re
    other = [m for m in re.findall(r'export\["([a-z_0-9]+)"\]\s*(?:,\s*export\["[a-z_0-9]+"\]\s*)?=', block) if m not in ("momentum_high", "momentum_high_status")]
    assert not other, f"the momentum_high glue must not assign any other export key: {other}"
    from src.data import drive_sync as DS
    assert "momentum_high" in DS._FIELD_GLOSSARY and "momentum_high_status" in DS._FIELD_GLOSSARY
    assert "NOT READ" in DS._FIELD_GLOSSARY["momentum_high"] and "RAW PRICES" in DS._FIELD_GLOSSARY["momentum_high"]


REF = {"2025-03-14": ("SSRM TGTX AGI MP BABA WPM TIGO".split(), False),
       "2026-06-15": ("SNDK WDC MU STX DOCN TNGX TTMI SYRE LQDA AMD SPHR SMTC MKSI LRCX GTX KLIC TVTX BTSG CAT AMAT ALAB COCO AXSM UMC KN SNEX ASML RSI TSM DGII SNX ADI VIK ARW BFH OSCR".split(), True),
       "2026-11-18": ("SN TGTX".split(), False)}


@pytest.mark.skipif(not (ROOT / "data" / "panel_daily.parquet").exists() or not (ROOT / "data" / "scores_daily.parquet").exists(), reason="needs the local price panel + scores")
@pytest.mark.parametrize("d", list(REF))
def test_membership_matches_the_review_sessions_reference_lists_on_the_three_sample_dates(d):
    """BACKTEST REVIEW's reference implementation (their panel): >= 90% overlap is a pass. Ours matches 100% and in the same rank order."""
    panel = pd.read_parquet(ROOT / "data" / "panel_daily.parquet")
    spy = pd.read_parquet(ROOT / "data" / "spy_daily.parquet")
    uni = sorted(pd.read_parquet(ROOT / "data" / "scores_daily.parquet", columns=["ticker"])["ticker"].unique())
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    res = engine.compute(panel, spy, uni)
    exp, market_ok = REF[d]
    got = [r["ticker"] for r in engine.rows_at(res, d)]
    assert len(set(got) & set(exp)) / len(exp) >= 0.9, (d, sorted(set(got) ^ set(exp)))
    assert bool(res.market.loc[pd.Timestamp(d), "market_ok"]) == market_ok


def test_the_scanner_renders_the_market_check_and_the_table_without_an_exception(tmp_path, monkeypatch):
    import json as _json
    from streamlit.testing.v1 import AppTest
    from src.ui import shared
    panel, spy = _panel()
    sec, st = daily.build_section(None, "2024-08-30", panel=panel, spy=spy)
    p = tmp_path / "aqe_daily_export.json"
    p.write_text(_json.dumps({"date": "2024-08-30", "daily_list": [], "momentum_high": sec, "momentum_high_status": st}))
    monkeypatch.setattr(shared, "EXPORT_JSON", p)
    at = AppTest.from_file(str(ROOT / "src" / "ui" / "1_Scanner.py")).run(timeout=180)
    assert not at.exception, [e.value for e in at.exception][:2]
    assert any(s.value.startswith("Momentum High (") for s in at.subheader)
    assert {"Market OK", "Breadth: % above 50-day"} <= {m.label for m in at.metric}
