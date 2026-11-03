"""The committee's FMP inputs, fetched by code (PM 2026-11-03: take data fetching out of the model).

Real-shape fixtures: tests/fixtures/fmp_mp/ holds FMP's own /stable responses for MP (2 Nov 2026). The fake
client below serves them; every failure mode is a named status, never a silent empty.
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

from src.data.fmp_client import FMPError, FMPQuotaError
from src.pipeline import committee_data as cd

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "fmp_mp"
SCHEMAS = ROOT / "aegis" / "plugin" / "aegis-core" / "contracts" / "committee_data"
MTF_PY = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / "mtf.py"
RUN_DATE = "2026-11-03"          # the SGT morning that reads the 2 Nov close


def fx(name):
    return json.loads((FIX / f"{name}.json").read_text())


mtf = cd._mtf()


def sessions(n, end="2026-11-02"):
    d, out = date.fromisoformat(end), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return sorted(out)


def bar(day, i):
    c = 100 + i * 0.3 + (i % 5) * 0.1
    return {"date": day, "open": round(c - 0.1, 4), "high": round(c + 0.5, 4), "low": round(c - 0.5, 4),
            "close": round(c, 4), "volume": 1000.0}


def daily_series(n=300):
    return [bar(d, i) for i, d in enumerate(sessions(n))]


def hourly_series(n_sessions=10):
    out, k = [], 0
    for day in sessions(n_sessions):
        for hh in range(7):
            mins = 9 * 60 + 30 + hh * 60
            out.append(dict(bar(f"{day} {mins // 60:02d}:{mins % 60:02d}:00", k), volume=500.0)); k += 1
    return out[::-1]                                   # FMP answers newest first


class FakeClient:
    """Serves recorded payloads by (path, symbol); an Exception value is raised; anything unrouted is an error."""
    def __init__(self, routes=None, default=None):
        self.config = SimpleNamespace(api_key="K")
        self.routes, self.default, self.calls = routes or {}, default, []

    def _get_json(self, url, params):
        path, sym = url.split("/stable/")[1], params.get("symbol")
        self.calls.append((path, sym))
        v = self.routes.get((path, sym), self.routes.get((path, "*"), self.default))
        if v is None:
            raise FMPError(f"unrouted {path} {sym}")
        if isinstance(v, Exception):
            raise v
        return v


def mp_routes(sym="MP", hourly=None, with_15=True):
    r = {("profile", sym): fx("profile"), ("ratios-ttm", sym): fx("ratios_ttm"),
         ("income-statement-growth", sym): fx("income_statement_growth"),
         ("historical-chart/1hour", sym): hourly if hourly is not None else hourly_series()}
    if with_15:
        r[("historical-chart/15min", sym)] = fx("intraday_15min")
    return r


EXPORT = {"daily_list": [{"ticker": "MP", "entry": 38.35}, {"ticker": "AAA", "entry": 100.0}],
          "held_positions": [{"ticker": "V"}]}


def panel_for(tickers):
    return {t: daily_series() for t in tickers}


def run(client, **kw):
    kw.setdefault("panel", panel_for(["MP", "AAA", "V", "SPY"]))
    kw.setdefault("ledger", [])
    # hermetic: five past labels of the same two names, so the run never shells out to git
    kw.setdefault("universe_previous", {"entries": {f"2026-10-{d}": ["MP", "AAA"] for d in (20, 21, 22, 23, 26)}})
    return cd.run(EXPORT, RUN_DATE, client=client, **kw)


def all_routes():
    r = {}
    for t in ("MP", "AAA", "V"):
        r.update(mp_routes(t))
    r[("historical-price-eod/full", "SPY")] = fx("eod_full")
    return r


# ------------------------------------------------------------------ exactness against the real MP responses
def test_fundamentals_entry_is_exactly_the_couriers_fields_from_the_real_payloads():
    f = cd.Fetcher(FakeClient(mp_routes()))
    e = cd.fetch_fundamentals_one(f, "MP", RUN_DATE)
    assert e["status"] == "served" and e["unserved"] is False
    assert e["profile"] == {"sector": "Basic Materials", "industry": "Industrial Materials", "marketCap": 6830195900,
                            "beta": 1.99, "range": "37.11-76.8", "source": "FMP profile", "date": RUN_DATE}
    assert set(e["ratios_ttm"]) == set(cd.RATIO_KEEP) | {"source"}
    assert e["ratios_ttm"]["priceToEarningsRatioTTM"] == -112.20011702750146 if "priceToEarningsRatioTTM" in fx("ratios_ttm")[0] else True
    assert e["ratios_ttm"]["netProfitMarginTTM"] == -0.19850217927348818
    assert e["growth_3y"] == [{"date": "2025-12-31", "growthRevenue": 0.10098354222363935, "growthEPS": 0.12280701754385957},
                              {"date": "2024-12-31", "growthRevenue": -0.19566375347708576, "growthEPS": -5.07142857142857},
                              {"date": "2023-12-31", "growthRevenue": -0.5195446531819302, "growthEPS": -0.9146341463414634}]
    assert len(e["sha256"]) == 64 and f.calls == 3


def test_native_hourly_bars_are_read_exactly_and_the_frame_carries_the_last_bar():
    f = cd.Fetcher(FakeClient({("historical-chart/1hour", "MP"): fx("intraday_1hour")}))
    bars, meta = cd.fetch_hourly_one(f, "MP", RUN_DATE, mtf)
    assert meta["source"] == "1hour" and meta["rows"] == 7 and meta["last_bar"] == "2026-11-02 15:30:00"
    assert [b["date"][11:16] for b in bars] == ["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30"]
    last = bars[-1]
    assert (last["open"], last["high"], last["low"], last["close"]) == (38.62, 38.62, 38.13, 38.34)
    assert last["volume"] == 905248.4913499998


def test_the_15_minute_rollup_matches_fmps_native_hourly_bars_on_real_data():
    """OHLC identical in all 7 buckets; volume identical in 6 of 7. The 09:30 bucket sums to 676,274 from the
    15-minute bars against 583,974 in FMP's hourly bar -- a real difference, recorded, not hidden. The grid reads no
    volume, so no reading changes."""
    native = {b["date"]: b for b in mtf._clean(fx("intraday_1hour"))}
    rolled, dropped = mtf.rollup_hourly(mtf._clean(fx("intraday_15min")))
    assert dropped == 0 and sorted(native) == [b["date"] for b in rolled]
    for b in rolled:
        n = native[b["date"]]
        assert (b["open"], b["high"], b["low"], b["close"]) == (n["open"], n["high"], n["low"], n["close"]), b["date"]
    off = [b["date"][11:16] for b in rolled if abs(b["volume"] - native[b["date"]]["volume"]) > 1e-6]
    assert off == ["09:30"]
    assert round(next(b for b in rolled if b["date"].endswith("09:30:00"))["volume"]) == 676274
    assert native["2026-11-02 09:30:00"]["volume"] == 583974


# -------------------------------------------------------------------------------- the whole run
def test_a_clean_run_produces_the_three_files_and_a_manifest_that_matches_their_bytes():
    r = run(FakeClient(all_routes()))
    m = r["manifest"]
    assert m["status"] == "OK" and m["run_date"] == RUN_DATE and m["scope"]["requested"] == 3
    assert set(r["files"]) == set(cd.FILES) | {cd.UNIVERSE_HISTORY}       # the sidecar rides along, outside the manifest's files
    for name in cd.FILES:
        body = r["files"][name]
        assert m["files"][name]["sha256"] == cd.hashlib.sha256(body).hexdigest()
        assert m["files"][name]["bytes"] == len(body) and m["files"][name]["schema"] == cd.FILES[name]
    assert cd.dumps(json.loads(r["files"]["mtf_grid.json"])) == r["files"]["mtf_grid.json"]      # deterministic bytes
    g = json.loads(r["files"]["mtf_grid.json"])
    assert g["names"]["MP"]["complete"] is True and g["names"]["MP"]["fetch"]["hourly"]["source"] == "1hour"
    assert g["names"]["MP"]["fetch"]["daily"]["source"] == "panel"
    assert g["sha256_of_names"] == cd.sha256_of(g["names"])


def test_every_output_validates_against_its_schema_file():
    r = run(FakeClient(all_routes()))
    for name, schema in (("fundamentals_pack.json", "fundamentals_pack.v1"), ("mtf_grid.json", "mtf_grid.v1"),
                         ("closes_scorecard.json", "closes_scorecard.v1")):
        jsonschema.validate(json.loads(r["files"][name]), json.loads((SCHEMAS / f"{schema}.schema.json").read_text()))
    jsonschema.validate(r["manifest"], json.loads((SCHEMAS / "committee_data_manifest.v1.schema.json").read_text()))
    bad = json.loads(r["files"]["fundamentals_pack.json"]); bad["tickers"]["MP"]["status"] = "fine"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, json.loads((SCHEMAS / "fundamentals_pack.v1.schema.json").read_text()))


def test_closes_have_the_exact_shape_the_scorecard_reads_and_spy_is_in_them():
    r = run(FakeClient(all_routes()), ledger=["V"])
    c = json.loads(r["files"]["closes_scorecard.json"])
    assert c["_missing"] == [] and set(c) == {"MP", "AAA", "V", "SPY", "_missing"}
    assert all(isinstance(v, float) for v in c["SPY"].values()) and max(c["SPY"]) == "2026-11-02"
    sc = _load_tool("pma_scorecard")
    assert sc.calendar({k: v for k, v in c.items() if k != "_missing"}, "SPY")[-1] == "2026-11-02"


def _load_tool(name):
    import importlib.util
    p = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma" / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_a_ledger_name_the_panel_does_not_hold_is_fetched_or_declared_missing_never_dropped():
    routes = all_routes()
    routes[("historical-price-eod/full", "OLD")] = fx("eod_full")
    r = run(FakeClient(routes), ledger=["OLD", "GONE"])
    c = json.loads(r["files"]["closes_scorecard.json"])
    assert "OLD" in c and r["manifest"]["closes_detail"]["OLD"]["source"] == "fmp"
    assert c["_missing"] == ["GONE"] and r["manifest"]["closes_detail"]["GONE"]["source"] == "none"
    assert r["manifest"]["files"]["closes_scorecard.json"]["unserved"] == 1


# ---------------------------------------------------------------------------------- failure is loud
def test_native_hourly_failure_falls_back_to_the_15_minute_rollup_and_says_so():
    routes = all_routes()
    routes[("historical-chart/1hour", "MP")] = FMPError("HTTP 500")
    big = [dict(b, date=d + b["date"][10:]) for d in sessions(10) for b in fx("intraday_15min")]
    routes[("historical-chart/15min", "MP")] = big
    r = run(FakeClient(routes))
    h = json.loads(r["files"]["mtf_grid.json"])["names"]["MP"]["fetch"]["hourly"]
    assert h["source"] == "15min_rollup" and "HTTP 500" in h["fallback_because"] and h["rows"] == 70


def test_no_hourly_bars_at_all_leaves_a_labelled_gap_and_a_partial_run():
    routes = all_routes()
    for t in ("MP", "AAA", "V"):
        routes[("historical-chart/1hour", t)] = FMPError("down")
        routes[("historical-chart/15min", t)] = []
    r = run(FakeClient(routes))
    g = json.loads(r["files"]["mtf_grid.json"])["names"]["MP"]
    assert g["served"] is True and g["complete"] is False and g["gaps"] == ["H1"]
    assert g["fetch"]["hourly"]["source"] == "none" and "down" in g["fetch"]["hourly"]["error"]
    assert r["manifest"]["status"] == "PARTIAL"                # 0 of 3 complete is below 95%, loudly
    assert r["manifest"]["errors_total"] > 0


def test_a_partial_fundamentals_entry_names_the_missing_part_and_why():
    routes = all_routes()
    routes[("ratios-ttm", "MP")] = FMPError("HTTP 404")
    routes[("income-statement-growth", "AAA")] = []
    r = run(FakeClient(routes))
    t = json.loads(r["files"]["fundamentals_pack.json"])["tickers"]
    assert t["MP"]["status"] == "partial" and t["MP"]["missing"] == ["ratios_ttm"] and "404" in t["MP"]["reasons"]["ratios_ttm"]
    assert "ratios_ttm" not in t["MP"] and t["MP"]["unserved"] is False
    assert t["AAA"]["missing"] == ["growth_3y"] and t["AAA"]["reasons"]["growth_3y"] == "empty or unexpected payload"


def test_a_name_fmp_cannot_serve_at_all_is_unserved_with_nothing_invented():
    routes = all_routes()
    for p in ("profile", "ratios-ttm", "income-statement-growth"):
        routes[(p, "V")] = FMPError("no data")
    r = run(FakeClient(routes))
    p = json.loads(r["files"]["fundamentals_pack.json"])
    assert p["tickers"]["V"] == {**p["tickers"]["V"], "unserved": True, "status": "unserved"}
    assert not any(k in p["tickers"]["V"] for k in ("profile", "ratios_ttm", "growth_3y"))
    assert p["coverage"]["unserved_names"] == ["V"]


def test_a_refused_key_is_never_a_clean_run():
    routes = all_routes()
    routes[("profile", "AAA")] = FMPQuotaError("Invalid API KEY")
    c = FakeClient(routes)
    r = run(c)
    assert r["manifest"]["quota_hit"] is True and r["manifest"]["status"] != "OK"
    assert not any(x == ("profile", "V") for x in c.calls)             # stopped asking once refused


def test_an_exhausted_time_budget_declares_the_rest_instead_of_dropping_it():
    ticks = iter(range(0, 10 ** 6, 100))
    r = run(FakeClient(all_routes()), budget_s=250, clock=lambda: next(ticks))
    assert r["manifest"]["time_budget_exhausted"] is True and r["manifest"]["status"] == "PARTIAL"
    assert any("time budget" in e for e in r["manifest"]["errors"])


def test_no_key_is_a_failed_manifest_that_says_why_not_a_missing_file(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    r = cd.run(EXPORT, RUN_DATE, client=None, panel={}, ledger=[], universe_previous={"entries": {}}, git_loader=lambda *a, **k: ({}, "UNAVAILABLE: test"))
    m = r["manifest"]
    assert m["status"] == "FAILED" and "FMP_API_KEY" in m["reason"] and r["files"] == {} and m["files"] == {}
    jsonschema.validate(m, json.loads((SCHEMAS / "committee_data_manifest.v1.schema.json").read_text()))


def test_an_empty_export_is_failed_not_an_empty_success():
    r = cd.run({"daily_list": []}, RUN_DATE, client=FakeClient(), panel={}, ledger=[], universe_previous={"entries": {}}, git_loader=lambda *a, **k: ({}, "UNAVAILABLE: test"))
    assert r["manifest"]["status"] == "FAILED" and "no daily_list" in r["manifest"]["reason"]


# ------------------------------------------------------------------------------ carry-forward
def test_a_young_served_entry_is_carried_with_its_own_date_and_costs_no_calls():
    first = run(FakeClient(all_routes()))
    prev = json.loads(first["files"]["fundamentals_pack.json"])
    prev["tickers"]["MP"]["pulled_on"] = "2026-11-01"                    # 2 days old
    prev["tickers"]["AAA"]["pulled_on"] = "2026-10-20"                   # 14 days old
    prev["tickers"]["V"]["status"], prev["tickers"]["V"]["unserved"] = "partial", False   # always refetched
    c = FakeClient(all_routes())
    r = run(c, previous_pack=prev)
    t = json.loads(r["files"]["fundamentals_pack.json"])["tickers"]
    assert t["MP"]["status"] == "carried" and t["MP"]["pulled_on"] == "2026-11-01" and t["MP"]["age_days"] == 2
    assert t["AAA"]["status"] == "served" and t["AAA"]["pulled_on"] == RUN_DATE
    assert t["V"]["status"] == "served"
    assert not any(x == ("profile", "MP") for x in c.calls) and ("profile", "AAA") in c.calls
    assert json.loads(r["files"]["fundamentals_pack.json"])["coverage"]["carried"] == 1


# ------------------------------------------------------------------------------------- publishing
def test_publish_writes_the_manifest_last_and_names_any_file_that_did_not_land():
    r = run(FakeClient(all_routes()))
    seen = []
    ok = cd.publish(r, put_file=lambda path, content, msg: seen.append(path) or {"ok": True})
    assert ok["ok"] and seen[-1].endswith("/manifest.json") and len(seen) == 5
    assert all(p.startswith("aegis/output/committee_data/") for p in seen)

    def flaky(path, content, msg):
        return {"ok": False, "error": "422"} if path.endswith("mtf_grid.json") else {"ok": True}
    bad = cd.publish(r, put_file=flaky)
    assert not bad["ok"] and bad["failed"] == ["mtf_grid.json: 422"] and bad["manifest_landed"] is True

    def no_manifest(path, content, msg):
        return {"ok": False, "reason": "locked"} if path.endswith("manifest.json") else {"ok": True}
    assert cd.publish(r, put_file=no_manifest)["manifest_landed"] is False


def test_write_local_puts_the_manifest_last(tmp_path):
    r = run(FakeClient(all_routes()))
    d = cd.write_local(r, tmp_path / "cd")
    assert sorted(p.name for p in d.iterdir()) == sorted(list(cd.FILES) + [cd.UNIVERSE_HISTORY, "manifest.json"])
    assert (d / "manifest.json").stat().st_mtime_ns >= (d / "mtf_grid.json").stat().st_mtime_ns


def test_the_summary_line_is_what_the_marker_parser_will_read():
    r = run(FakeClient(all_routes()))
    line = cd.summary_line(r, {"written": 4, "total": 4, "failed": []})
    assert line.startswith("Committee data OK:") and "published 4/4" in line
    assert cd.summary_line({"manifest": cd.failed_manifest(RUN_DATE, "no key")}).startswith("Committee data FAILED: no key")


# ----------------------------------------------------------------------- mtf.py --grid (the reader)
def _mtf_cli(*args):
    r = subprocess.run([sys.executable, str(MTF_PY), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def test_mtf_build_takes_the_rooms_rows_from_the_grid_and_refuses_a_stale_one(tmp_path):
    run_out = run(FakeClient(all_routes()))
    (tmp_path / "grid.json").write_bytes(run_out["files"]["mtf_grid.json"])
    (tmp_path / "p4.json").write_text(json.dumps({"deliberation_set": ["MP", "ZZZ"]}))
    out = tmp_path / "mtf.json"
    rc, log = _mtf_cli("build", "--grid", str(tmp_path / "grid.json"), "--phase4", str(tmp_path / "p4.json"),
                       "--date", RUN_DATE, "--out", str(out))
    assert rc == 0, log
    doc = json.loads(out.read_text())
    assert doc["names"]["MP"]["complete"] is True and doc["names"]["MP"]["W"]["summary"]
    assert doc["names"]["ZZZ"]["served"] is False and "not in the fetched grid" in doc["names"]["ZZZ"]["reason"]
    assert doc["measurement"]["source"] == "mtf_grid.json"
    rc, log = _mtf_cli("build", "--grid", str(tmp_path / "grid.json"), "--phase4", str(tmp_path / "p4.json"),
                       "--date", "2026-11-04", "--out", str(tmp_path / "x.json"))
    assert rc == 2 and "stale" in log and "courier fallback" in log and not (tmp_path / "x.json").exists()
    rc, log = _mtf_cli("build", "--grid", str(tmp_path / "nope.json"), "--phase4", str(tmp_path / "p4.json"),
                       "--date", RUN_DATE, "--out", str(tmp_path / "y.json"))
    assert rc == 2 and "courier fallback" in log


# ------------------------------------------------------------------ the gate (daily-check/check.py data)
CHECK_PY = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "daily-check" / "check.py"


def _check():
    import importlib.util
    spec = importlib.util.spec_from_file_location("daily_check_cd", CHECK_PY)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def _published(tmp_path, **kw):
    r = run(FakeClient(all_routes()), **kw)
    out = tmp_path / "out"
    cd.write_local(r, out / "committee_data")
    return out, r


def test_the_gate_passes_a_clean_set_and_prints_what_it_read(tmp_path):
    out, _ = _published(tmp_path)
    f, n = _check().check_committee_data(str(out), RUN_DATE, EXPORT)
    assert f == [], f
    assert any("committee data OK" in x and "3/3 complete" in x for x in n), n


def test_the_gate_fails_loudly_when_the_set_is_missing_stale_failed_or_tampered(tmp_path):
    C = _check()
    out, r = _published(tmp_path)
    cdir = out / "committee_data"
    # missing manifest
    (cdir / "manifest.json").rename(cdir / "m.bak")
    f, _ = C.check_committee_data(str(out), RUN_DATE, EXPORT)
    assert len(f) == 1 and "MISSING" in f[0] and "courier fallback" in f[0] and "1.5M" in f[0]
    (cdir / "m.bak").rename(cdir / "manifest.json")
    # stale: another day's manifest
    f, _ = C.check_committee_data(str(out), "2026-11-04", EXPORT)
    assert any("STALE" in x and "2026-11-03" in x for x in f), f
    # FAILED manifest says why
    failed = out.parent / "failed"
    cd.write_local({"files": {}, "manifest": cd.failed_manifest(RUN_DATE, "FMPError: FMP_API_KEY not set")}, failed / "committee_data")
    f, _ = C.check_committee_data(str(failed), RUN_DATE, EXPORT)
    assert any("FAILED: FMPError: FMP_API_KEY not set" in x for x in f), f
    # a file edited after the manifest was written
    body = (cdir / "fundamentals_pack.json").read_bytes()
    (cdir / "fundamentals_pack.json").write_bytes(body.replace(b"Basic Materials", b"Tech"))
    f, _ = C.check_committee_data(str(out), RUN_DATE, EXPORT)
    assert any("fundamentals_pack.json: sha256/bytes differ" in x for x in f), f
    (cdir / "fundamentals_pack.json").write_bytes(body)
    # a file missing though the manifest lists it
    (cdir / "closes_scorecard.json").unlink()
    f, _ = C.check_committee_data(str(out), RUN_DATE, EXPORT)
    assert any("closes_scorecard.json: MISSING" in x for x in f), f


def test_the_gate_fails_when_the_set_belongs_to_another_export_or_the_closes_are_stale(tmp_path):
    C = _check()
    out, _ = _published(tmp_path)
    other = {"daily_list": EXPORT["daily_list"] + [{"ticker": "NEW", "entry": 1.0}], "held_positions": EXPORT["held_positions"]}
    f, _ = C.check_committee_data(str(out), RUN_DATE, other)
    assert any("a different export" in x for x in f), f
    # closes that end before the last US close
    panel = {t: daily_series()[:-3] for t in ("MP", "AAA", "V", "SPY")}
    out2, _ = _published(tmp_path / "stale", panel=panel)
    f, _ = C.check_committee_data(str(out2), RUN_DATE, EXPORT)
    assert any("SPY ends" in x and "stale closes" in x for x in f), f


def test_one_coverage_rule_under_95_percent_is_partial_and_check_fails_it_at_or_above_proceeds(tmp_path):
    """ONE rule (conductor + engineering, 2026-11-03): any file under 95% served = manifest PARTIAL = check.py FAIL
    (stop and page: 'couriers' / 'skip'); at or above 95% per-name gaps are a WARN and the run proceeds."""
    def files(served, unserved):
        e = {"served": served, "unserved": unserved}
        return {n: dict(e) for n in cd.FILES}
    assert cd.status_of(files(347, 4)) == "OK"            # the 3 Nov proof run: 347/351 = 98.9%
    assert cd.status_of(files(95, 5)) == "OK"             # exactly 95%
    assert cd.status_of(files(94, 6)) == "PARTIAL"
    assert cd.status_of({}) == "FAILED"
    C = _check()
    routes = all_routes()
    for t in ("MP", "AAA", "V"):
        routes[("historical-chart/1hour", t)] = FMPError("down")
        routes[("historical-chart/15min", t)] = []
    routes[("income-statement-growth", "V")] = []
    r = run(FakeClient(routes))
    assert r["manifest"]["status"] == "PARTIAL"
    cd.write_local(r, tmp_path / "p" / "committee_data")
    f, n = C.check_committee_data(str(tmp_path / "p"), RUN_DATE, EXPORT)
    assert len(f) == 1 and "committee data is PARTIAL" in f[0] and "under 95% served" in f[0], f
    assert "'couriers'" in f[0] and "'skip'" in f[0], f


def test_check_data_includes_the_committee_data_gate(tmp_path):
    """check_data (the READY gate) must call it: an output dir with no committee_data fails the whole gate."""
    C = _check()
    f, _ = C.check_data(str(tmp_path / "empty"))
    assert any("committee_data/manifest.json: MISSING" in x for x in f), f


def test_publishing_without_github_is_a_named_failure_the_summary_line_can_print(monkeypatch):
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "is_configured", lambda: False)
    r = run(FakeClient(all_routes()))
    pub = cd.publish(r)
    assert pub["ok"] is False and pub["manifest_landed"] is False and "not configured" in pub["failed"][0]
    assert "published 0/0 (FAILED: GitHub not configured" in cd.summary_line(r, pub)


# ------------------------------------------------------- the standalone proof run (committee-data.yml)
def test_closes_reuse_the_daily_bars_the_grid_already_fetched_instead_of_paying_twice():
    """The runner is limited to ~80 calls a minute: with no panel, each name's daily series is fetched ONCE."""
    routes = all_routes()
    for t in ("MP", "AAA", "V", "SPY"):
        routes[("historical-price-eod/full", t)] = fx("eod_full")
    c = FakeClient(routes)
    r = cd.run(EXPORT, RUN_DATE, client=c, panel={}, ledger=[], universe_previous={"entries": {}}, git_loader=lambda *a, **k: ({}, "UNAVAILABLE: test"))
    per_name = {}
    for path, sym in c.calls:
        if path == "historical-price-eod/full":
            per_name[sym] = per_name.get(sym, 0) + 1
    assert per_name.get("MP") == 1 and per_name.get("AAA") == 1 and per_name.get("V") == 1, per_name
    assert per_name.get("SPY") == 1                                   # the benchmark is not in the grid: fetched once
    closes = json.loads(r["files"]["closes_scorecard.json"])
    assert closes["MP"]["2026-11-02"] == 38.35 and closes["_missing"] == []
    assert r["manifest"]["closes_detail"]["MP"]["source"] == "fmp"


def test_describe_prints_the_numbers_the_pm_asked_for():
    r = run(FakeClient(all_routes()))
    text = cd.describe(r)
    assert text.startswith(f"COMMITTEE DATA OK  run_date {RUN_DATE}")
    for needle in ("fundamentals_pack.json", "mtf_grid.json", "closes_scorecard.json", "sha256", "FMP calls",
                   "FUNDAMENTALS  served 3", "fundamentals fields filled", "profile.sector 3", "growth_3y (3 yrs, revenue+EPS) 3",
                   "MTF GRID  complete 3/3", "3 native", "hourly bars per name: min 70 / median 70 / max 70", "CLOSES"):
        assert needle in text, (needle, text)
    failed = {"manifest": cd.failed_manifest(RUN_DATE, "FMPError: FMP_API_KEY not set"), "files": {}}
    assert "FAILED: FMPError: FMP_API_KEY not set" in cd.describe(failed)


def _script():
    import importlib
    return importlib.import_module("scripts.committee_data_run")


def _patch_fmp(monkeypatch, routes, default=None):
    import src.data.fmp_client as fc
    monkeypatch.setattr(fc, "FMPClient", lambda: FakeClient(routes, default))


def _export_file(tmp_path, export=EXPORT):
    p = tmp_path / "export.json"
    p.write_text(json.dumps(dict(export, date=RUN_DATE)))
    return p


def test_the_standalone_run_writes_the_set_reads_the_export_date_and_exits_0_when_ok(tmp_path, monkeypatch, capsys):
    S = _script()
    _patch_fmp(monkeypatch, all_routes())
    monkeypatch.setattr(cd, "load_panel_daily", lambda tickers, sessions=cd.DAILY_SESSIONS: panel_for(["MP", "AAA", "V", "SPY"]))
    monkeypatch.setattr(cd, "ledger_tickers", lambda run_date, **k: [])
    monkeypatch.setattr(cd, "git_export_history", lambda *a, **k: ({}, "UNAVAILABLE: test"))
    out = tmp_path / "cd"
    rc = S.main(["--export", str(_export_file(tmp_path)), "--out-dir", str(out), "--no-publish"])
    log = capsys.readouterr().out
    assert rc == 0, log
    assert f"run date {RUN_DATE}" in log and "COMMITTEE DATA OK" in log
    assert sorted(p.name for p in out.iterdir()) == sorted(list(cd.FILES) + [cd.UNIVERSE_HISTORY, "manifest.json"])


def test_a_failed_or_partial_rerun_never_overwrites_an_ok_set_for_the_same_date(tmp_path, monkeypatch, capsys):
    S = _script()
    _patch_fmp(monkeypatch, all_routes())
    monkeypatch.setattr(cd, "load_panel_daily", lambda tickers, sessions=cd.DAILY_SESSIONS: panel_for(["MP", "AAA", "V", "SPY"]))
    monkeypatch.setattr(cd, "ledger_tickers", lambda run_date, **k: [])
    monkeypatch.setattr(cd, "git_export_history", lambda *a, **k: ({}, "UNAVAILABLE: test"))
    out = tmp_path / "cd"
    assert S.main(["--export", str(_export_file(tmp_path)), "--out-dir", str(out), "--no-publish"]) == 0
    good = (out / "manifest.json").read_bytes()
    capsys.readouterr()
    # the key is refused: every call errors
    _patch_fmp(monkeypatch, {}, default=FMPQuotaError("Invalid API KEY"))
    rc = S.main(["--export", str(_export_file(tmp_path)), "--out-dir", str(out), "--no-publish"])
    log = capsys.readouterr().out
    assert rc == 1 and "NOT publishing" in log and "Kept it" in log
    assert (out / "manifest.json").read_bytes() == good


def test_a_missing_export_or_key_is_a_loud_nonzero_exit(tmp_path, monkeypatch, capsys):
    S = _script()
    assert S.main(["--export", str(tmp_path / "nope.json"), "--out-dir", str(tmp_path / "o"), "--no-publish"]) == 1
    assert "nothing to fetch for" in capsys.readouterr().out
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    assert S.main(["--export", str(_export_file(tmp_path)), "--out-dir", str(tmp_path / "o2"), "--no-publish"]) == 1
    assert "FAILED" in capsys.readouterr().out


def test_the_workflow_is_manual_only_cannot_race_the_nightly_and_decides_on_the_committee_check():
    import yaml
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "committee-data.yml").read_text())
    on = wf.get("on") or wf.get(True)
    assert list(on) == ["workflow_dispatch"], "must never fire on a push or a schedule"
    assert wf["concurrency"]["group"] == "aqe-daily" and wf["concurrency"]["cancel-in-progress"] is False
    assert wf["permissions"] == {"contents": "write"}
    steps = wf["jobs"]["fetch"]["steps"]
    text = json.dumps(steps)
    assert "FMP_API_KEY" in text and "secrets.FMP_API_KEY" in text and "scripts.committee_data_run" in text
    assert "check.py data" in text and "check_committee_data" in text
    assert steps[0]["with"]["ref"] == "main"
    daily = (ROOT / ".github" / "workflows" / "daily-run.yml").read_text()
    assert "committee_data_run" not in daily             # the nightly path is unchanged by the proof workflow
    # the script publishes ONLY under aegis/output/committee_data/
    assert cd.REPO_DIR == "aegis/output/committee_data"
    src = (ROOT / "scripts" / "committee_data_run.py").read_text()
    assert "publish_daily_outputs" not in src and "put_file(" not in src


def test_closes_scope_is_today_plus_ledger_plus_every_past_export_plus_spy():
    """Conductor defect 2026-11-03: closes held 353 names, the courier file 530 - the scorecard needs EVERY past run's
    export names (the equal-weight list per run) and every ledger name, not only today's export and the ledger."""
    past = {"2026-10-20": ["OLD1", "OLD2", "MP"], "2026-10-21": ["OLD3", "AAA"], "2026-10-22": ["OLD4"],
            "2026-10-23": ["OLD5"], "2026-10-26": ["OLD6"]}
    routes = all_routes()
    r = run(FakeClient(routes), ledger=["LED1"], universe_previous={"entries": past})
    m = r["manifest"]["closes_scope"]
    want = {"MP", "AAA", "V", "SPY", "LED1", "OLD1", "OLD2", "OLD3", "OLD4", "OLD5", "OLD6"}
    assert m["total"] == len(want) and m["past_export_runs"] == 5 and m["ledger"] == 1 and m["today"] == 3, m
    closes = json.loads(r["files"]["closes_scorecard.json"])
    got = {k for k in closes if k != "_missing"} | set(closes["_missing"])
    assert got == want, got ^ want              # every scoped name is either served or NAMED missing, none silently absent
    hist = json.loads(r["files"][cd.UNIVERSE_HISTORY])
    assert hist["entries"][RUN_DATE] == ["AAA", "MP", "V"] and len(hist["entries"]) == 6      # today recorded for tomorrow's window


def test_past_exports_unavailable_is_loud_not_silent():
    r = run(FakeClient(all_routes()), universe_previous={"entries": {}}, git_loader=lambda *a, **k: ({}, "UNAVAILABLE: not a git checkout"))
    m = r["manifest"]
    assert m["closes_scope"]["past_export_runs"] == 0 and m["closes_scope"]["past_exports_source"].startswith("UNAVAILABLE")
    assert any("closes scope" in e and "understated" in e for e in m["errors"]), m["errors"]


def test_a_bootstrap_from_git_fills_missing_labels_once_and_the_window_prunes_old_ones():
    calls = []
    def loader(run_date, lookback, have):
        calls.append(sorted(have))
        return {"2026-10-15": ["G1", "G2"], "2026-10-16": ["G3"]}, "git history"
    prev = {"entries": {"2026-08-01": ["TOOOLD"], "2026-10-20": ["KEEP"]}}
    uh, note = cd.build_universe_history(RUN_DATE, ["T1"], prev, git_loader=loader)
    assert "TOOOLD" not in {t for v in uh["entries"].values() for t in v}      # outside the 45-day window
    assert {"G1", "G3", "KEEP", "T1"} <= {t for v in uh["entries"].values() for t in v} and note.endswith("git history") and len(calls) == 1
    uh2, _ = cd.build_universe_history(RUN_DATE, ["T1"], {"entries": {f"2026-10-{d}": ["X"] for d in (20, 21, 22, 23, 26)}},
                                       git_loader=lambda *a, **k: (_ for _ in ()).throw(AssertionError("git must not be called for a full record")))
    assert uh2["entries"][RUN_DATE] == ["T1"]


def test_the_ledger_comes_from_the_last_pma_run_dir_never_a_rerun_dir(tmp_path):
    for name, tickers in (("2026-11-01", ["A"]), ("2026-11-02", ["A", "B"]), ("2026-11-02-r2", ["ZZZ"]), ("2026-11-03-r2", ["YYY"])):
        d = tmp_path / "aegis" / "output" / "pma" / "run" / name
        d.mkdir(parents=True)
        (d / "verdict_ledger.json").write_text(json.dumps({"rows": [{"date": "2026-11-02", "ticker": t} for t in tickers]}))
    p = cd.latest_ledger_path(tmp_path)
    assert p.parent.name == "2026-11-02"
    assert cd.ledger_tickers(RUN_DATE, path=p) == ["A", "B"]
