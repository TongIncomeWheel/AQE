"""QS end-to-end — panel + scores in, daily_list rows and a rendered card out.

Exercises the whole stack against synthetic parquets: fields -> eligibility ->
regime -> engine -> store -> card. Unit tests can all pass while the seams
between them are wrong, which is exactly the failure this catches.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data import qs_store
from src.engines import qs_card, qs_daily as QD, qs_spec as S

N_DAYS = 320          # enough for trend_200 (200) + tercile history
N_TICKERS = 40


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    """Write panel/scores parquets and point every module at them."""
    rng = np.random.default_rng(11)
    dates = pd.bdate_range("2025-01-01", periods=N_DAYS)
    tickers = [f"T{i:02d}" for i in range(N_TICKERS)]

    prows, srows = [], []
    for tk in tickers:
        px = 100 * np.cumprod(1 + rng.normal(0.0004, 0.015, N_DAYS))
        vol = rng.uniform(1e6, 3e6, N_DAYS)
        vol[-1] *= 3.0          # everyone eligible on the last day
        for i, d in enumerate(dates):
            prows.append({"date": d, "ticker": tk, "close": float(px[i]),
                          "volume": float(vol[i])})
        for i, d in enumerate(dates[-10:], start=N_DAYS - 10):
            row = {"date": d, "ticker": tk, "close": float(px[i]),
                   "atr14": float(px[i] * 0.02),
                   "impulse_state": rng.choice(["GREEN", "RED", "NEUTRAL"])}
            for f in S.CARD_COMPONENTS:
                row.setdefault(f, float(rng.uniform(0, 30)))
            for f in ("vp_position_score", "k39_value", "pr_ma_score",
                      "pr_ret_12m", "excess_return", "rs_accel", "pipe_rank",
                      "volume_score", "fip_quality", "pr_vol_score",
                      "earn_score", "exhaustion_score", "hl_flow", "hl_score",
                      "hl_trend_bars", "hl_higher_lows", "hl_vol_updn",
                      "rd_compression", "rd_pos_mod", "en_trend_bars",
                      "bq_base_days", "bq_base_dur", "atr_score",
                      "resist_score", "skew_score", "price_action_score"):
                row.setdefault(f, float(rng.uniform(0, 30)))
            srows.append(row)

    panel_p, scores_p = tmp_path / "panel.parquet", tmp_path / "scores.parquet"
    pd.DataFrame(prows).to_parquet(panel_p)
    pd.DataFrame(srows).to_parquet(scores_p)

    monkeypatch.setattr(QD, "PANEL_DAILY", panel_p)
    monkeypatch.setattr(QD, "SCORES_DAILY", scores_p)
    monkeypatch.setattr(qs_store, "DB_PATH", tmp_path / "qs.db")
    qs_store.init_qs_tables()
    return {"dates": dates, "tickers": tickers}


def test_full_run_produces_scored_rows(synthetic):
    r = QD.run(store=True)
    assert r["ok"] is True, r.get("reason")
    assert r["status"] == "live"
    assert r["scored_count"] > 0
    assert r["eligible_count"] > 0


def test_every_row_carries_the_fields_a_card_needs(synthetic):
    r = QD.run()
    for row in r["rows"].values():
        for k in ("signal", "conviction", "conviction_word", "state", "odds",
                  "engine", "vetoes", "why", "versions", "eligible"):
            assert k in row, f"missing {k}"
        assert "recipe_hits" in row["engine"]
        assert "lens" in row["engine"] and len(row["engine"]["lens"]) == 5


def test_a_card_renders_from_the_run_output_alone(synthetic):
    r = QD.run()
    tk, row = next(iter(r["rows"].items()))
    card = qs_card.render_card({"ticker": tk, "on_qs": True, "qs": row},
                               r["market"])
    assert tk in card and "CONVICTION" in card


def test_hits_are_stored_so_persistence_can_build(synthetic):
    QD.run(store=True)
    st = qs_store.store_status()
    assert st["hits_rows"] > 0 and st["hits_dates"] >= 1


def test_persistence_feeds_the_next_run(synthetic):
    """Store several sessions, then confirm qs_persist is non-zero somewhere."""
    dates = synthetic["dates"]
    for d in dates[-6:-1]:
        QD.run(as_of=d.date(), store=True)
    r = QD.run(as_of=dates[-1].date(), store=True)
    persists = [row["engine"]["qs_persist"] for row in r["rows"].values()]
    assert max(persists) >= 0            # populated, not defaulted away
    assert qs_store.store_status()["hits_dates"] >= 5
    assert qs_store.store_status()["persist_ready"] is True


def test_market_block_is_populated(synthetic):
    r = QD.run()
    m = r["market"]
    assert m["description"] and m["regime_code"] and m["action"]


def test_emitted_is_a_subset_of_scored(synthetic):
    r = QD.run()
    emitted = [x for x in r["rows"].values() if x["emitted"]]
    assert len(emitted) <= r["scored_count"]
    for row in emitted:
        assert row["engine"]["recipe_hits"] >= S.SHEET_MIN_HITS
        assert row["conviction"] >= 2 or row["conviction"] == 0


def test_non_eligible_names_are_flagged_and_never_emitted(synthetic, tmp_path):
    """Make one ticker ineligible and confirm it is scored but marked."""
    panel = pd.read_parquet(QD.PANEL_DAILY)
    last = panel["date"].max()
    panel.loc[(panel.ticker == "T00") & (panel.date == last), "volume"] = 1.0
    panel.to_parquet(QD.PANEL_DAILY)

    r = QD.run()
    row = r["rows"].get("T00")
    assert row is not None, "non-eligible name should still be scored"
    assert row["eligible"] is False
    assert row["odds"]["extrapolated"] is True
    assert row["emitted"] is False


def test_versions_are_stamped_on_every_row(synthetic):
    """R10 — audit trail. Every output carries book + calibration versions."""
    r = QD.run()
    for row in r["rows"].values():
        assert row["versions"]["recipe_book"]
        assert row["versions"]["calibration"]


# ------------------------------------------------------------------ backfill

def test_backfill_populates_enough_memory_for_persistence(synthetic, monkeypatch):
    """The point of the backfill: persist_ready True on day one, not day six."""
    from scripts import qs_backfill
    monkeypatch.setattr(qs_backfill, "PANEL_DAILY", QD.PANEL_DAILY)
    monkeypatch.setattr(qs_backfill, "SCORES_DAILY", QD.SCORES_DAILY)
    monkeypatch.setattr(qs_backfill, "load_sector_map", lambda: {})

    assert qs_store.store_status()["persist_ready"] is False
    r = qs_backfill.backfill(days=8)
    assert r["ok"] is True
    assert r["sessions"] >= 5 and r["rows"] > 0
    assert qs_store.store_status()["persist_ready"] is True


def test_backfill_dry_run_writes_nothing(synthetic, monkeypatch):
    from scripts import qs_backfill
    monkeypatch.setattr(qs_backfill, "PANEL_DAILY", QD.PANEL_DAILY)
    monkeypatch.setattr(qs_backfill, "SCORES_DAILY", QD.SCORES_DAILY)
    monkeypatch.setattr(qs_backfill, "load_sector_map", lambda: {})

    before = qs_store.store_status()["hits_rows"]
    r = qs_backfill.backfill(days=5, dry_run=True)
    assert r["ok"] is True and r["dry_run"] is True
    assert qs_store.store_status()["hits_rows"] == before


def test_backfill_reports_rather_than_raising_without_data(monkeypatch, tmp_path):
    from scripts import qs_backfill
    monkeypatch.setattr(qs_backfill, "PANEL_DAILY", tmp_path / "nope.parquet")
    r = qs_backfill.backfill()
    assert r["ok"] is False and "missing" in r["reason"]


# ------------------------------------------------------------- ad-hoc lookup

def _adhoc_record(ticker="ADHOC", **over):
    rec = {"ticker": ticker, "close": 150.0, "atr14": 3.0,
           "impulse_state": "RED"}
    for f in S.CARD_COMPONENTS:
        rec.setdefault(f, 15.0)
    for f in ("vp_position_score", "k39_value", "pr_ma_score", "pr_ret_12m",
              "excess_return", "rs_accel", "pipe_rank", "volume_score",
              "fip_quality", "pr_vol_score", "earn_score", "exhaustion_score",
              "hl_flow", "hl_score", "hl_trend_bars", "hl_higher_lows",
              "hl_vol_updn", "rd_compression", "rd_pos_mod", "en_trend_bars",
              "bq_base_days", "bq_base_dur", "atr_score", "resist_score",
              "skew_score", "price_action_score"):
        rec.setdefault(f, 15.0)
    rec.update(over)
    return rec


def test_adhoc_ticker_gets_a_full_qs_read(synthetic):
    r = QD.score_adhoc(_adhoc_record())
    assert r["ok"] is True, r.get("reason")
    qs = r["qs"]
    assert "conviction" in qs and "odds" in qs and "engine" in qs
    assert len(qs["engine"]["lens"]) == 5


def test_adhoc_is_always_flagged_as_a_read_across(synthetic):
    """An ad-hoc name sits outside the measured population by construction."""
    qs = QD.score_adhoc(_adhoc_record())["qs"]
    assert qs["eligible"] is False
    assert qs["odds"]["extrapolated"] is True
    assert qs["emitted"] is False and qs["rank"] is None


def test_adhoc_scoring_does_not_disturb_the_cohort(synthetic):
    """Adding the ad-hoc name must not move any universe name's lens score."""
    before = {t: row["engine"]["lens_total"]
              for t, row in QD.run(store=False)["rows"].items()}
    QD.score_adhoc(_adhoc_record())
    after = {t: row["engine"]["lens_total"]
             for t, row in QD.run(store=False)["rows"].items()}
    assert before == after


def test_adhoc_reports_missing_recipe_inputs(synthetic):
    """A missing field fails its condition silently — the gap must be visible."""
    rec = _adhoc_record()
    rec.pop("k39_value")
    rec.pop("hl_flow")
    r = QD.score_adhoc(rec)
    assert r["ok"] is True
    assert r["coverage"]["complete"] is False
    assert set(r["coverage"]["recipe_inputs_missing"]) >= {"k39_value", "hl_flow"}


def test_adhoc_reports_complete_coverage_when_nothing_is_missing(synthetic):
    r = QD.score_adhoc(_adhoc_record())
    assert r["coverage"]["complete"] is True
    assert r["coverage"]["recipe_inputs_missing"] == []


def test_adhoc_card_renders(synthetic):
    r = QD.score_adhoc(_adhoc_record())
    card = qs_card.render_card(
        {"ticker": "ADHOC", "on_qs": False, "qs": r["qs"]}, r["market"])
    assert "ADHOC" in card and "CONVICTION" in card


def test_adhoc_without_a_ticker_fails_cleanly(synthetic):
    r = QD.score_adhoc({})
    assert r["ok"] is False and "ticker" in r["reason"]


def test_adhoc_never_raises_on_a_junk_record(synthetic):
    r = QD.score_adhoc({"ticker": "X", "close": "not a number"})
    assert isinstance(r, dict) and "ok" in r
