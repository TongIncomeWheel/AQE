"""Reason-coded macro legs, the feed-timing record, and the committee-gate rule (PM 2026-11-04: 'stale because we are slow' vs
'stale because the publisher is')."""
import importlib.util
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd

from src.macro import legs as L
from src.data import feed_timing as FT

ROOT = Path(__file__).resolve().parents[1]
EXP = "2026-11-03"
TODAY = date(2026, 11, 4)


def _legs(**kw):
    base = dict(breadth={"freshness": {"as_of": EXP, "stale": False, "current": 4314, "total": 4314}},
                vol_series={"vix": EXP, "vixeq": "2026-11-02", "dspx": "2026-11-02", "vix3m": EXP, "vix9d": EXP, "cor1m": EXP},
                cot_as_of="2026-10-27", heartbeat_asof=EXP, cboe_ok=True)
    base.update(kw)
    return {r["leg"]: r for r in L.build_legs(EXP, TODAY, **base)}


def test_the_3_nov_morning_reads_publisher_lag_for_vixeq_and_dspx_and_cadence_for_cot():
    t = _legs()
    assert t["dispersion_vixeq"]["reason"] == L.LAG and t["dspx"]["reason"] == L.LAG
    assert t["vix_level"]["reason"] == L.CURRENT and t["vix3m"]["reason"] == L.CURRENT
    assert t["positioning_cot"]["reason"] == L.CADENCE and "next release 2026-11-06" in t["positioning_cot"]["detail"]
    assert t["breadth_whole_market"]["reason"] == L.CURRENT
    assert L.blocking(list(t.values())) == []                          # a publisher lag never blocks


def test_a_panel_we_did_not_refresh_is_our_budget_and_blocks_and_a_missing_source_is_source_down():
    t = _legs(breadth={"freshness": {"as_of": EXP, "stale": True, "reason": "1600/4314 carry it", "current": 1600, "total": 4314}})
    assert t["breadth_whole_market"]["reason"] == L.BUDGET
    assert [r["leg"] for r in L.blocking(list(t.values()))] == ["breadth_whole_market"]
    t = _legs(breadth={}, vol_series={}, cot_as_of=None, cboe_ok=False)
    assert t["breadth_whole_market"]["reason"] == L.DOWN and t["vix_level"]["reason"] == L.DOWN and t["positioning_cot"]["reason"] == L.DOWN
    t = _legs(cot_as_of="2026-10-06")
    assert t["positioning_cot"]["reason"] == L.DOWN and "missing" in t["positioning_cot"]["detail"]      # a missed weekly release is not 'cadence'


def test_feed_timing_appends_one_entry_per_run_keeps_history_and_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(FT, "REPO_COPY", tmp_path / "no_committed_copy.json")      # hermetic: the nightly commits a real feed_timing.json (5 Nov) that record() falls back to
    class R:
        def __init__(self, text, lm): self.text, self.status_code, self.headers = text, 200, {"Last-Modified": lm}
    def get(u):
        return R("10/30/2026,1\n11/03/2026,2\n", "Wed, 04 Nov 2026 02:11:03 GMT") if "cboe" in u else R('"WHEAT",261027,2026-10-27,001602', "Fri, 30 Oct 2026 19:27:45 GMT")
    d1 = FT.record("2026-11-03", legs=[{"leg": "dspx", "as_of": "2026-11-02", "reason": "PUBLISHER_LAG"}], out_dir=tmp_path, previous_path=tmp_path / "none.json", get=get)
    e = d1["history"][-1]
    assert e["cboe"]["VIXEQ"]["last_modified"].startswith("Wed, 04 Nov 2026 02:11") and e["cboe"]["VIX"]["newest_row_date"] == "11/03/2026"
    assert e["cftc"]["report_date"] == "2026-10-27" and e["legs"][0]["reason"] == "PUBLISHER_LAG"
    d2 = FT.record("2026-11-04", out_dir=tmp_path, previous_path=tmp_path / FT.FILE, get=get)
    assert [h["run_date"] for h in d2["history"]] == ["2026-11-03", "2026-11-04"]
    d3 = FT.record("2026-11-04", out_dir=tmp_path, previous_path=tmp_path / FT.FILE, get=get)       # a rerun replaces, never duplicates
    assert [h["run_date"] for h in d3["history"]] == ["2026-11-03", "2026-11-04"]
    boom = lambda u: (_ for _ in ()).throw(RuntimeError("down"))
    assert "error" in FT.record("2026-11-05", out_dir=tmp_path, previous_path=tmp_path / FT.FILE, get=boom)["history"][-1]["cboe"]["VIX"]


def _check_module():
    p = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "daily-check" / "check.py"
    spec = importlib.util.spec_from_file_location("check_legs", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_the_gate_fails_our_budget_and_two_nights_running_and_only_warns_a_publisher_lag():
    C = _check_module()
    row = lambda leg, rc: {"leg": leg, "as_of": "2026-11-02", "expected": EXP, "reason": rc, "detail": "d"}
    f, n = C.check_macro_legs({"data_freshness": {"legs_table": [row("dspx", "PUBLISHER_LAG"), row("positioning_cot", "PUBLISHER_CADENCE")]}}, None)
    assert f == [] and any("WARN" in x and "PUBLISHER_LAG" in x for x in n) and any("PUBLISHER_CADENCE" in x for x in n)
    f, _ = C.check_macro_legs({"data_freshness": {"legs_table": [row("breadth_whole_market", "OUR_BUDGET")]}}, None)
    assert len(f) == 1 and "OUR_BUDGET" in f[0]
    f, _ = C.check_macro_legs({"data_freshness": {}}, None)
    assert len(f) == 1 and "cannot be audited" in f[0]
    hist = {"history": [{"run_date": "2026-11-02", "legs": [{"leg": "dspx", "reason": "PUBLISHER_LAG"}]},
                        {"run_date": "2026-11-03", "legs": [{"leg": "dspx", "reason": "PUBLISHER_LAG"}, {"leg": "vix_level", "reason": "CURRENT"}]}]}
    f, _ = C.check_macro_legs({"data_freshness": {"legs_table": [row("dspx", "PUBLISHER_LAG")]}}, hist)
    assert len(f) == 1 and "two nights running" in f[0] and "dspx" in f[0]
    f, _ = C.check_macro_legs({"data_freshness": {"legs_table": [row("dspx", "CURRENT")]}}, {"history": [{"legs": [{"leg": "dspx", "reason": "PUBLISHER_LAG"}]}, {"legs": [{"leg": "dspx", "reason": "CURRENT"}]}]})
    assert f == []


def test_weather_refresh_publishes_only_weather_files_and_never_the_committee_ones():
    import importlib
    from src.data import github_sync
    W = importlib.import_module("scripts.weather_refresh")
    published = set(github_sync.DAILY_ARTIFACTS)
    assert set(W.WEATHER_FILES) - {"aqe_weather_refresh.json"} <= published        # every weather file is a normal daily artifact
    forbidden = {"aqe_daily_export.json", "candidate_set.json", "aqe_last_run.json", "held_positions.json", "aqe_sector_map.json"}
    assert not (set(W.WEATHER_FILES) & forbidden)                                  # the export, packets, held book and the nightly marker are not touched


def test_the_nightly_restores_the_qs_memory_before_qs_runs():
    """2026-11-04: on Actions nothing restored aqe.db, so qs_persist read 0 every day. The restore step exists, restores ONLY aqe.db
    (a full restore would roll the panels back), runs before the QS step, and aqe.db is in the Daily Persist file list."""
    src = (ROOT / "src" / "pipeline" / "daily_orchestrator.py").read_text(encoding="utf-8")
    assert "Step 0a3" in src and 'only=["aqe.db"]' in src
    assert src.index("Step 0a3") < src.index("Step 6e: QS engine")
    persist = (ROOT / "src" / "data" / "persist.py").read_text(encoding="utf-8")
    assert '"aqe.db"' in persist


def test_the_gate_reads_the_legs_from_a_fallback_when_the_published_copy_is_stripped():
    """2026-11-05: the published valen copy carried no data_freshness and the committee could not start. The legs are read from the full copy, the
    crown artifact or the run marker; the same reason-code rules apply to them; and it still FAILS when none carries a table."""
    C = _check_module()
    stripped = {"date": "2026-11-05"}                                   # a published copy with no data_freshness
    cur = [{"leg": "vix_level", "as_of": "2026-11-04", "expected": EXP, "reason": "CURRENT", "detail": ""},
           {"leg": "dspx", "as_of": "2026-11-03", "expected": EXP, "reason": "PUBLISHER_LAG", "detail": "next release"}]
    f, n = C.check_macro_legs(stripped, None, [("valen_dashboard.json", cur)])
    assert f == [] and any("read from valen_dashboard.json" in x for x in n) and any("PUBLISHER_LAG" in x for x in n)
    bad = cur + [{"leg": "breadth_whole_market", "as_of": None, "expected": EXP, "reason": "SOURCE_DOWN", "detail": "no panel"}]
    f, _ = C.check_macro_legs(stripped, None, [("valen_dashboard.json", bad)])
    assert len(f) == 1 and "SOURCE_DOWN" in f[0]                         # a fallback leg is judged by the same rules
    f, _ = C.check_macro_legs(stripped, None, [("valen_dashboard.json", None), ("crown", []), ("marker", [])])
    assert len(f) == 1 and "neither valen_dashboard.json" in f[0]        # no source at all = still a FAIL
    f, _ = C.check_macro_legs(stripped, None, [])
    assert len(f) == 1
    f, _ = C.check_macro_legs({"data_freshness": {"legs_table": cur}}, None, [("valen_dashboard.json", bad)])
    assert f == []                                                       # the published table, when present, wins


def test_the_marker_line_is_parsed_into_legs_with_their_reason_codes():
    C = _check_module()
    line = ("Macro legs: expected session 2026-11-04 | breadth_whole_market 2026-11-04 CURRENT | dispersion_vixeq 2026-11-03 PUBLISHER_LAG | "
            "positioning_cot 2026-10-27 PUBLISHER_CADENCE | BEHIND: dspx")
    rows = C._legs_from_marker(line)
    assert [(r["leg"], r["reason"]) for r in rows] == [("breadth_whole_market", "CURRENT"), ("dispersion_vixeq", "PUBLISHER_LAG"), ("positioning_cot", "PUBLISHER_CADENCE")]
    assert rows[0]["expected"] == "2026-11-04" and C._legs_from_marker("nothing") == [] and C._legs_from_marker(None) == []


def test_check_data_passes_the_legs_through_the_fallbacks_end_to_end(tmp_path):
    """The run marker's line alone is enough for the gate to audit the legs (full copy and crown artifact absent)."""
    C = _check_module()
    marker = {"macro_legs": "Macro legs: expected session 2026-11-04 | vix_level 2026-11-04 CURRENT | dspx 2026-11-03 PUBLISHER_LAG"}
    rows = C._legs_from_marker(marker["macro_legs"])
    f, n = C.check_macro_legs({"date": "x"}, None, [("valen_dashboard.json", None), ("aqe_crown_macro.json data_legs", None), ("the run marker's Macro legs line", rows)])
    assert f == [] and any("read from the run marker" in x for x in n)


def test_the_published_valen_copy_now_carries_the_legs_table(tmp_path, monkeypatch):
    from src.valen import daily as VD
    monkeypatch.setattr(VD, "OUTPUT_DIR", tmp_path); monkeypatch.setattr(VD, "LOCAL_PATH", tmp_path / "valen_dashboard.json")
    monkeypatch.setattr(VD, "PUBLISHED_PATH", tmp_path / "aqe_valen_dashboard.json")
    for name in ("stance_banner", "trend_rows", "regime_word", "extension_rows", "breadth_rows", "gex_block", "crown_cockpit_block", "history_rows",
                 "neighbourhood_lines", "theme_leaders_table", "rotation_table", "selection_block", "house_block", "execution_block", "management_block"):
        monkeypatch.setattr(VD.card, name, lambda a: None)
    legs = [{"leg": "vix_level", "as_of": "2026-11-04", "expected": "2026-11-04", "reason": "CURRENT", "detail": ""}]
    art = {"date": "2026-11-05", "exported_at": "x", "basis": "eod", "status": "OK", "plain_english": {},
           "data_freshness": {"expected_session": "2026-11-04", "legs_table": legs, "behind": [], "blocking": [], "legs": {"big": "x"}}}
    VD.write_artifacts(art)
    pub = json.loads((tmp_path / "aqe_valen_dashboard.json").read_text())
    assert pub["data_freshness"]["legs_table"] == legs and pub["data_freshness"]["expected_session"] == "2026-11-04" and "legs" not in pub["data_freshness"]
    C = _check_module()
    f, _ = C.check_macro_legs(pub, None)
    assert f == []


def test_cboe_publisher_timing_two_nights_running_is_a_warn_but_real_staleness_still_fails():
    """Conductor 2026-11-12: Cboe posts VIXEQ/DSPX ~10:11/10:41 SGT, after the 06:26 run, so they are one session behind EVERY night.
    The feed_timing history rows carry leg/as_of/reason and the entry's run_date only (no `expected`), exactly as written by feed_timing.record."""
    C = _check_module()
    L = lambda leg, as_of, rc="PUBLISHER_LAG": {"leg": leg, "as_of": as_of, "reason": rc}
    H = lambda a, b: {"history": [{"run_date": a[0], "legs": [a[1]]}, {"run_date": b[0], "legs": [b[1]]}]}
    cur = {"data_freshness": {"legs_table": [{"leg": "dspx", "as_of": "2026-11-10", "expected": "2026-11-11", "reason": "PUBLISHER_LAG", "detail": "d"}]}}
    # the real 11 and 12 Nov history: leg one session behind both nights
    f, n = C.check_macro_legs(cur, H(("2026-11-11", L("dspx", "2026-11-09")), ("2026-11-12", L("dspx", "2026-11-10"))))
    assert f == [] and any("one session behind again" in x for x in n)
    # Monday run: expected Friday, leg Thursday: one session (a weekend is not a session)
    assert C.check_macro_legs(cur, H(("2026-11-05", L("dspx", "2026-11-03")), ("2026-11-09", L("dspx", "2026-11-05"))))[0] == []
    # two sessions behind, a budget miss, a mix, or no date: still a FAIL
    assert len(C.check_macro_legs(cur, H(("2026-11-11", L("dspx", "2026-11-06")), ("2026-11-12", L("dspx", "2026-11-09"))))[0]) == 1
    assert len(C.check_macro_legs(cur, H(("2026-11-11", L("dspx", "2026-11-09", "OUR_BUDGET")), ("2026-11-12", L("dspx", "2026-11-10"))))[0]) == 1
    assert len(C.check_macro_legs(cur, H(("2026-11-11", {"leg": "dspx", "reason": "PUBLISHER_LAG"}), ("2026-11-12", L("dspx", "2026-11-10"))))[0]) == 1
