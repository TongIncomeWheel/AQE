"""Report B committee-data coverage (conductor defect 2026-11-10): every name the B screens seat has fundamentals, a served MTF row and closes, or the step fails loudly."""
import json

import pytest

from src.pipeline import committee_data as cd
from src.pipeline import committee_topup as ct
from tests.test_committee_data import FakeClient, RUN_DATE, all_routes, daily_series, mp_routes, run as cd_run, fx, panel_for

NEW = ["AMPL", "BRZE"]


def base_docs():
    res = cd_run(FakeClient(all_routes()))
    fund, grid, closes = (json.loads(res["files"][n]) for n in ("fundamentals_pack.json", "mtf_grid.json", "closes_scorecard.json"))
    return fund, grid, closes


def new_routes(names=NEW):
    r = all_routes()
    for t in names:
        r.update(mp_routes(t))
    return r


ROWS = [{"ticker": t, "last_close": 50.0} for t in ["MP", "AAA", "V"] + NEW]


def test_names_outside_the_export_are_missing_everywhere_before_the_topup():
    fund, grid, closes = base_docs()
    m = ct.missing(["MP"] + NEW, fund, grid, closes)
    assert m["fundamentals"] == NEW and m["mtf"] == NEW and m["closes"] == NEW


def test_the_topup_gives_every_screened_name_fundamentals_mtf_and_closes_and_updates_coverage():
    fund, grid, closes = base_docs()
    rep = ct.topup(["MP"] + NEW, RUN_DATE, fund, grid, closes, ROWS, FakeClient(new_routes()), panel=panel_for(NEW + ["SPY"]))
    assert rep["ok"] and rep["unserved_names"] == []
    ct.verify(["MP"] + NEW, fund, grid, closes)                      # the regression gate passes
    assert fund["tickers"]["AMPL"]["status"] == "served" and grid["names"]["BRZE"]["served"] and "AMPL" in closes
    assert fund["coverage"]["requested"] == len(fund["tickers"]) and grid["coverage"]["requested"] == len(grid["names"])
    assert rep["pulled"] == 2 and rep["fmp_calls"] > 0


def test_a_name_that_stays_unserved_is_loud_and_the_gate_raises():
    fund, grid, closes = base_docs()
    routes = new_routes(["AMPL"])                                    # BRZE is unrouted: every FMP call for it errors
    rep = ct.topup(["MP"] + NEW, RUN_DATE, fund, grid, closes, ROWS, FakeClient(routes), panel=panel_for(["AMPL", "SPY"]))
    assert not rep["ok"] and rep["unserved_names"] == ["BRZE"]
    with pytest.raises(RuntimeError, match="BRZE"):
        ct.verify(["MP"] + NEW, fund, grid, closes)


def test_nothing_is_pulled_for_names_already_covered():
    fund, grid, closes = base_docs()
    c = FakeClient(all_routes())
    rep = ct.topup(["MP", "AAA"], RUN_DATE, fund, grid, closes, ROWS, c, panel=panel_for(["SPY"]))
    assert rep["ok"] and rep["pulled"] == 0 and c.calls == []


def test_the_nightly_scope_carries_the_screened_names_outside_the_export():
    c = FakeClient(new_routes())
    export = {"daily_list": [{"ticker": "MP", "entry": 38.35}, {"ticker": "AAA", "entry": 100.0}], "held_positions": [{"ticker": "V"}]}
    extra = [{"ticker": t, "last_close": 50.0} for t in NEW]
    res = cd.run(export, RUN_DATE, client=c, panel=panel_for(["MP", "AAA", "V", "SPY"] + NEW), ledger=[], extra_rows=extra,
                 universe_previous={"entries": {}}, git_loader=lambda *a, **k: ({}, "UNAVAILABLE: test"))
    fund, grid, closes = (json.loads(res["files"][n]) for n in ("fundamentals_pack.json", "mtf_grid.json", "closes_scorecard.json"))
    ct.verify(["MP", "AAA", "V"] + NEW, fund, grid, closes)
    assert res["manifest"]["scope"]["requested"] == 5


def test_screen_picks_and_seat_sets_agree_on_what_a_b_run_needs(tmp_path):
    rows = json.loads((ct.PROJECT_ROOT / "aegis/output/aqe_universe_rows.json").read_text())["rows"]
    picks = ct.screen_picks(rows)
    assert 0 < len(picks) <= 70 and set(picks) <= {r["ticker"] for r in rows}
    ss = tmp_path / "seat_sets.json"
    ss.write_text(json.dumps({"seats": {"oneil": [{"ticker": picks[0]}], "seow": [{"ticker": picks[-1]}]}}))
    assert ct.names_from_seat_sets(ss) == sorted({picks[0], picks[-1]})


def test_a_seat_screened_name_without_data_fails_the_cli(tmp_path, monkeypatch, capsys):
    fund, grid, closes = base_docs()
    for n, d in (("fundamentals_pack.json", fund), ("mtf_grid.json", grid), ("closes_scorecard.json", closes)):
        (tmp_path / n).write_bytes(cd.dumps(d))
    (tmp_path / "manifest.json").write_bytes(cd.dumps({"fmp_calls": 0, "scope": {}}))
    rows = tmp_path / "rows.json"; rows.write_text(json.dumps({"rows": ROWS}))
    monkeypatch.setattr("src.data.fmp_client.FMPClient", lambda: FakeClient(new_routes(["AMPL"])))
    monkeypatch.setattr(cd, "load_panel_daily", lambda tk, sessions=300: panel_for(["AMPL", "SPY"]))
    monkeypatch.setattr(cd, "DATA_DIR", tmp_path)       # panel "exists" check
    (tmp_path / "panel_daily.parquet").write_bytes(b"x")
    rc = ct.main(["--names", "AMPL,BRZE", "--dir", str(tmp_path), "--universe-rows", str(rows), "--date", RUN_DATE])
    assert rc == 2 and "BRZE" in capsys.readouterr().out
    assert json.loads((tmp_path / "topup_report.json").read_text())["unserved_names"] == ["BRZE"]
