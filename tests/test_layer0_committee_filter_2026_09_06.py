"""The 2026-09-06 "Layer 0" ruling (the committee sees only names on BOTH the Longlist and the Elder
list) was RETIRED by R16 (2026-09-24: every nomination is seated, the room is as large as the seats
make it) and R27 (2026-10-23: the strongest names are voted). `pma_pipeline.py trim` therefore
carries EVERY daily_list row onto the universe and the list memberships ride as FLAGS. Rewritten
2026-11-01 (the four old tests encoded the retired rule and had been red since October).

What still holds, and is tested here end to end through the real CLI:
1. the bug fix the 2026-09-06 pass found -- `on_longlist` is the row's OWN flag, never derived
   from `source` (the plugin copy had regressed this; restored 2026-11-01);
2. no Layer-0 filter: every row survives trim, with its flags intact, so a seat's menu decides what
   it reads and the nominations decide the room;
3. the export's `elder_and_longlist_tickers` view is consistent with the carried flags (a view, not
   a filter).
emit_packets.py (the old PMA-side emitter) is not used by the nightly run (AQE_CODE_AGENT_SPEC §5)
and is no longer tested here."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

ROOT = "/home/user/AQE"
PMA_PIPELINE = f"{ROOT}/aegis/skills/premarket-analysis/tools/pma_pipeline.py"


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def _row(ticker, on_longlist, on_elder, source="longlist"):
    return {"ticker": ticker, "source": source, "on_longlist": on_longlist, "on_elder": on_elder,
            "sc_momentum": 70.0, "flow": 80.0, "energy": 65.0, "structure": 60.0, "mp": 60.0,
            "elder": 8.0, "entry": 50.0, "atr_14d": 1.5, "in_ledger": False,
            "bracket": {"stop": 47.0, "targets": []}}


@pytest.fixture
def export_file(tmp_path):
    daily_list = [
        _row("BOTH1", True, True),
        _row("BOTH2", True, True, source="elder_list"),   # the bug-fix case
        _row("LONGLIST_ONLY", True, False),
        _row("ELDER_ONLY", False, True, source="elder_list"),
        _row("NEITHER", False, False, source="qs"),
    ]
    export = {"date": "2026-11-01", "exported_at": "2026-11-01 08:00:00 SGT", "daily_list": daily_list,
              "held_positions": [], "srm": [], "elder_and_longlist_tickers": ["BOTH1", "BOTH2"]}
    p = tmp_path / "aqe_daily_export.json"
    p.write_text(json.dumps(export), encoding="utf-8")
    return p


def _trim(export_file, tmp_path):
    out = tmp_path / "candidate_set.json"
    r = _run([sys.executable, PMA_PIPELINE, "trim", "--export", str(export_file), "--date", "2026-11-01", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    return json.loads(out.read_text()), r


def test_trim_carries_every_row_the_layer0_filter_is_retired(export_file, tmp_path):
    cs, r = _trim(export_file, tmp_path)
    tickers = {row["ticker"] for row in cs["universe"]}
    assert tickers == {"BOTH1", "BOTH2", "LONGLIST_ONLY", "ELDER_ONLY", "NEITHER"}, (
        "R16/R27: trim filters nothing -- the room is bounded by nominations, not by a list intersection")
    assert "LAYER 0" not in r.stdout


def test_on_longlist_is_the_rows_own_flag_not_derived_from_source(export_file, tmp_path):
    """BOTH2's primary source is elder_list but it independently clears the longlist. The old
    `source == "longlist"` derivation reported on_longlist=False for it -- misclassifying exactly the
    runners the committee most wants, everywhere on_longlist is read downstream."""
    cs, _ = _trim(export_file, tmp_path)
    by = {row["ticker"]: row for row in cs["universe"]}
    assert by["BOTH2"]["on_longlist"] is True and by["BOTH2"]["on_elder"] is True
    assert by["ELDER_ONLY"]["on_longlist"] is False and by["ELDER_ONLY"]["on_elder"] is True
    assert by["LONGLIST_ONLY"]["on_longlist"] is True and by["LONGLIST_ONLY"]["on_elder"] is False
    assert by["NEITHER"]["on_longlist"] is False


def test_trim_falls_back_to_source_only_when_the_flag_is_absent(tmp_path):
    """An old export without the on_longlist field still gets a value, derived from source -- never null."""
    rows = [_row("A", True, True), _row("B", False, True, source="elder_list")]
    for r in rows:
        r.pop("on_longlist")
    p = tmp_path / "old_export.json"
    p.write_text(json.dumps({"date": "2026-11-01", "daily_list": rows, "held_positions": []}), encoding="utf-8")
    cs, _ = _trim(p, tmp_path)
    by = {row["ticker"]: row for row in cs["universe"]}
    assert by["A"]["on_longlist"] is True and by["B"]["on_longlist"] is False


def test_the_both_lists_view_matches_the_carried_flags(export_file, tmp_path):
    cs, _ = _trim(export_file, tmp_path)
    both = {row["ticker"] for row in cs["universe"] if row.get("on_longlist") and row.get("on_elder")}
    export = json.loads(export_file.read_text())
    assert both == set(export["elder_and_longlist_tickers"])
