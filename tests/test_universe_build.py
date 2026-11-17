"""build_universe, PM 2026-11-10: every name meeting mcap >= $2B and 10-day average volume >= 500K on a NASDAQ/NYSE listing is admitted, whatever its
domicile or share type (ADRs are KEPT, PM v5 ruling); only the PM's override exclude list removes names; nothing is capped or decided by prior
membership; a build that lost names fails loudly."""
import pandas as pd
import pytest

from src.data import universe as U

MCAP = 5_000_000_000


def row(sym, av, country="US", mcap=MCAP, **kw):
    r = {"symbol": sym, "marketCap": mcap, "avgVolume": av, "volume": 1, "price": 50.0, "country": country, "exchange": "NASDAQ",
         "exchangeShortName": "NASDAQ", "isEtf": False, "isFund": False}
    r.update(kw)
    return r


class FakeClient:
    """A screener with a known answer; bars carry a 10-day volume of `bars_vol[sym]` (default 2.0M)."""
    bars_vol: dict = {}
    fail: set = set()
    calls: list = []
    adr: set = {"NWG", "TCOM", "RYAAY", "EC", "ARM", "PDD", "SBSW", "LU", "TSM", "BABA"}     # what FMP's profile isAdr says (CI probe 2026-11-10)
    profile_fail: set = set()
    profiled: list = []

    class config:
        rate_limit_per_min = 80

    def __init__(self, rows):
        self.rows = rows
        FakeClient.calls = []

    def get_screener(self, **kw):
        self.kw = kw
        return list(self.rows)

    def get_profile(self, tk):
        FakeClient.profiled.append(tk)
        if tk in FakeClient.profile_fail:
            raise RuntimeError("HTTP 500")
        return {"symbol": tk, "isAdr": tk in FakeClient.adr}

    def get_daily_bars(self, tk, from_date=None, to_date=None):
        FakeClient.calls.append(tk)
        if tk in FakeClient.fail:
            raise RuntimeError("HTTP 429")
        vol = FakeClient.bars_vol.get(tk, 666_667)
        n = 60
        return pd.DataFrame({"volume": [vol] * n, "close": [10.0] * n})


@pytest.fixture()
def build(monkeypatch, tmp_path):
    def run(rows, bars_vol=None, fail=(), dry=True, profile_fail=()):
        FakeClient.bars_vol, FakeClient.fail = bars_vol or {}, set(fail)
        FakeClient.profile_fail, FakeClient.profiled = set(profile_fail), []
        import src.data.fmp_client as F
        monkeypatch.setattr(F, "FMPClient", lambda: FakeClient(rows))
        monkeypatch.setattr(U, "DEFAULT_UNIVERSE_FILE", tmp_path / "universe.txt")
        monkeypatch.setattr(U, "UNIVERSE_MCAP_FILE", tmp_path / "mcap.json")
        monkeypatch.setattr(U, "upload_universe", lambda b: {"drive_ok": False, "drive_reason": "test"})
        return U.build_universe(dry_run=dry)
    return run


def universe_rows():
    rows = [row("ADM", 1_333_333), row("MCHP", 1_666_667), row("TTD", 3_000_000), row("MOS", 1_166_667), row("CLF", 4_000_000),
            row("KTOS", 1_066_667), row("HUT", 1_366_667),
            row("MID1", 666_667), row("MID2", 600_000),                                   # in the verification band
            row("LOW", 200_000),                                                              # rejected cheap
            # foreign-domiciled ORDINARY shares: back in
            row("SHOP", 2_000_000, country="CA"), row("SPOT", 1_166_667, country="SE"), row("CCJ", 2_000_000, country="CA"),
            row("ACN", 1_033_333, country="IE"), row("BIRK", 1_000_000, country="GB"), row("GLBE", 1_000_000, country="IL"),
            row("G", 1_000_000, country="BM"),
            # ADRs and foreign names: all in (PM v5)
            row("ARM", 2_333_333, country="GB"), row("SBSW", 1_000_000, country="ZA"), row("LU", 1_000_000, country="CN"), row("PDD", 3_000_000, country="IE"),
            row("ASML", 833_333, country="NL"),
            row("NWG", 1_000_000, country="GB"), row("TCOM", 1_333_333, country="SG"), row("RYAAY", 1_000_000, country="IE"), row("EC", 1_000_000, country="CO"),
            row("TSM", 3_000_000, country="TW"), row("BABA", 3_000_000, country="CN"),
            row("TD", 2_666_667, country="CA"), row("TTE", 1_000_000, country="FR"), row("BNS", 1_333_333, country="CA"),
            row("JBS", 1_000_000, country="NL"), row("TECK", 1_000_000, country="CA"),
            row("SPYX", 3_000_000, isEtf=True), row("FUNDX", 3_000_000, isFund=True), row("WRNT-W", 3_000_000)]
    return rows


def test_every_qualifying_listed_name_is_admitted_adrs_included(build):
    res = build(universe_rows())
    got = set(res["tickers"])
    assert {"TTD", "MOS", "CLF", "KTOS", "HUT", "ADM", "MCHP"} <= got
    assert {"TD", "TTE", "TSM", "ASML", "ARM", "CCJ", "BABA", "NWG", "TCOM", "SHOP", "SPOT", "ACN", "SBSW", "LU", "PDD"} <= got, "ADRs and foreign names are in"
    assert not ({"SPYX", "FUNDX", "WRNT-W", "LOW"} & got)
    assert {"MID1", "MID2"} <= got, "the verification band is measured, and these qualify"


def test_no_profile_call_is_made_and_no_adr_stage_exists(build):
    res = build(universe_rows())
    assert not hasattr(FakeClient, "profiled") or FakeClient.profiled == []
    assert "excluded_adr" not in res and not any("adr" in k for k in res["stages"])
    assert U.UNIVERSE_RULE_ID.startswith("v6-") and "adrs-in" in U.UNIVERSE_RULE_ID


def test_the_pm_override_exclude_list_still_removes_names_and_is_logged(build, monkeypatch, capsys):
    monkeypatch.setattr(U, "load_universe_overrides", lambda: {"exclude": {"TD"}, "include": set()})
    res = build(universe_rows())
    assert "TD" not in res["tickers"] and "TSM" in res["tickers"] and res["excluded_override"] == ["TD"]
    assert "Excluded by the PM's override list" in capsys.readouterr().out


def test_the_shipped_override_file_is_empty_so_nothing_is_excluded_by_it():
    assert U.load_universe_overrides()["exclude"] == set()


def test_nothing_is_capped_a_thousand_uncertain_names_are_all_verified(build):
    rows = [row(f"U{i:04d}", 666_667) for i in range(1000)]
    res = build(rows)
    assert res["stages"]["to_verify"] == 1000 and len(FakeClient.calls) == 1000 and res["total"] == 1000


def test_prior_membership_neither_admits_nor_excludes(build, tmp_path):
    (tmp_path / "universe.txt").write_text("# AQE Universe — updated 2026-01-01\nOLDNAME\nTTD\n")
    res = build(universe_rows(), dry=True)
    assert "OLDNAME" not in res["tickers"] and "TTD" in res["tickers"]


def test_a_failed_bar_call_fails_the_build_loudly_and_writes_nothing(build, tmp_path):
    rows = [row(f"U{i:03d}", 666_667) for i in range(100)]
    res = build(rows, fail={f"U{i:03d}" for i in range(20)}, dry=False)
    assert res["status"] == "error" and not (tmp_path / "universe.txt").exists()


def test_a_collapsed_screener_fails_the_coverage_guard(build):
    # 100 qualified by the screener's average, but the bars say 90 of them are really below the floor
    rows = [row(f"U{i:03d}", 666_667) for i in range(100)]
    res = build(rows, bars_vol={f"U{i:03d}": 100_000 for i in range(90)})
    assert res["status"] == "error" and "coverage" in res["reason"]


def test_the_written_file_carries_the_stage_counts_and_the_sgt_date(build, tmp_path):
    res = build(universe_rows(), dry=False)
    assert res["status"] == "ok"
    head = (tmp_path / "universe.txt").read_text().splitlines()[:5]
    assert head[0].startswith("# AQE Universe — updated ") and head[1] == f"# rule: {U.UNIVERSE_RULE_ID}"
    assert any(l.startswith("# stages:") and "screener_rows=" in l and "final=" in l and "final=" in l for l in head)
    assert U.universe_built_rule(tmp_path / "universe.txt") == U.UNIVERSE_RULE_ID


def test_staleness_uses_the_singapore_date(tmp_path, monkeypatch):
    from datetime import date
    f = tmp_path / "universe.txt"
    f.write_text(f"# AQE Universe — updated {U._today_sgt()}\n# rule: {U.UNIVERSE_RULE_ID}\nAAA\n")
    monkeypatch.setattr(U, "DEFAULT_UNIVERSE_FILE", f)
    assert U.universe_is_stale() is False
    f.write_text(f"# AQE Universe — updated {date(2026, 1, 1)}\n# rule: {U.UNIVERSE_RULE_ID}\nAAA\n")
    assert U.universe_is_stale() is True


def test_the_screener_call_asks_for_no_volume_or_price_floor(build):
    seen = {}
    import src.data.fmp_client as F

    class C(FakeClient):
        def get_screener(self, **kw):
            seen.update(kw); return super().get_screener(**kw)
    import src.data.universe as UU
    build(universe_rows())  # warm the fixture
    # run again through a client that records the call
    import pytest as _pt
    mp = _pt.MonkeyPatch()
    mp.setattr(F, "FMPClient", lambda: C(universe_rows()))
    try:
        U.build_universe(dry_run=True)
    finally:
        mp.undo()
    assert seen["min_volume"] == 0 and seen["min_price"] == 0 and seen["min_mcap"] == 2_000_000_000


def test_the_batch_quote_never_returns_a_silent_empty_for_a_small_chunk(monkeypatch):
    """The CI probe: a comma-separated /quote returns [] with no error. Small chunks fall back to one call per symbol."""
    import src.data.fmp_client as F
    c = F.FMPClient.__new__(F.FMPClient)
    c.config = type("cfg", (), {"api_key": "x", "rate_limit_per_min": 80})()
    seen = []

    def fake(url, params=None, **kw):
        seen.append(params["symbol"])
        return [] if "," in params["symbol"] else [{"symbol": params["symbol"], "price": 10.0}]
    monkeypatch.setattr(F.FMPClient, "_get_json", lambda self, url, params=None, **kw: fake(url, params))
    out = c.get_quotes_batch(["AAA", "BBB", "CCC"], chunk=50)
    assert set(out) == {"AAA", "BBB", "CCC"}
