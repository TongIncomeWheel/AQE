"""PM 2026-11-05: "anything in the brief is bracketed and watched". pma_pipeline brackets covers the committee's PASS names and the brief lists;
pma_levels emit carries the committee's rejected names as brief_watch WATCH rows with their bracket (labelled by source) and the objections verbatim."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "aegis/plugin/aegis-core/skills/pma/tools"


def _row(tk, rank, entry=100.0, **kw):
    r = {"ticker": tk, "rank": rank, "entry": entry, "atr_14d": 2.0, "on_elder": False, "on_longlist": False,
         "bracket": {"valid": True, "stop": entry - 3, "targets": [{"price": entry + 4}, {"price": entry + 8}]}, "last_pivot_high": {"price": entry + 2}}
    r.update(kw)
    return r


def test_brief_names_and_rejected_names_are_bracketed_and_carried_into_the_levels_file(tmp_path):
    export = {"date": "2026-11-05", "regime": {"level": "GREEN"}, "regime_stop_pct_ceiling": 12.0,
              "daily_list": [_row("ADV", 1), _row("REJ", 2), _row("LST", 3), _row("SWG", 4, swing_pivot=True), _row("FAR", 400),
                             dict(_row("NOS", 5), bracket={"valid": False}, atr_14d=None)],         # no stop definable anywhere
              "lens_ranking": {"ranked": []}, "held_positions": []}
    cons = [{"ticker": "ADV", "verdict": "ADVANCE", "lane": "MOMENTUM", "status": "AGREED", "ordering_score": 5},
            {"ticker": "REJ", "verdict": "PASS", "lane": "PULLBACK", "status": "DROPPED",
             "objections": [{"voice": "oneil", "objection": "Volume did not clear 1.4x.", "would_clear": "A day on 1.4x volume."}]}]
    p4 = {"deliberation_set": ["ADV", "REJ"], "held_seated": []}
    for n, o in (("export.json", export), ("consensus.json", cons), ("phase4.json", p4)):
        (tmp_path / n).write_text(json.dumps(o))
    r = subprocess.run([sys.executable, str(TOOLS / "pma_pipeline.py"), "brackets", "--consensus", str(tmp_path / "consensus.json"), "--phase4",
                        str(tmp_path / "phase4.json"), "--export", str(tmp_path / "export.json"), "--date", "2026-11-05", "--out", str(tmp_path / "brackets.json")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    B = json.loads((tmp_path / "brackets.json").read_text())["brackets"]
    assert set(B) >= {"ADV", "REJ", "LST", "SWG"}                       # committee PASS + every brief-list name
    assert B["REJ"]["source"] == "committee PASS (dropped)" and B["LST"]["source"].startswith("AQE list (") and "Swing pivot" in B["SWG"]["source"]
    assert B["ADV"]["authority"] == "COMMITTEE_ADVANCE" and B["REJ"]["authority"] == "AQE_REFERENCE"
    assert all("risk_atr" in b and "invalid_reason" in b for b in B.values())
    assert B["ADV"]["risk_atr"] is not None and B["ADV"]["invalid_reason"] is None
    assert B["NOS"]["invalid_reason"] and "NO STOP DEFINABLE" in B["NOS"]["invalid_reason"]            # says why, never silently blank

    # emit: the rejected name rides as a brief_watch WATCH row with its bracket (labelled) and the objections verbatim
    cards = {"advance": {"ADV": {"triggers": [{"kind": "close_above", "level": 102.0, "basis": "15m", "priority": "ACTION", "action": "buy"}]}}, "hold": {}, "held": {}}
    for n, o in (("cards.json", cards),):
        (tmp_path / n).write_text(json.dumps(o))
    e = subprocess.run([sys.executable, str(TOOLS / "pma_levels.py"), "emit", "--consensus", str(tmp_path / "consensus.json"), "--brackets", str(tmp_path / "brackets.json"),
                        "--repeat-marks", "none", "--cards", str(tmp_path / "cards.json"), "--broker-stops", "none", "--candidates", "none",
                        "--phase4", str(tmp_path / "phase4.json"), "--date", "2026-11-05", "--out", str(tmp_path / "lv.json")], capture_output=True, text=True)
    assert e.returncode == 0, (e.stdout + e.stderr)[-800:]
    rows = {x["ticker"]: x for x in json.loads((tmp_path / "lv.json").read_text())["rows"]}
    rej = rows["REJ"]
    assert rej["class"] == "WATCH" and rej["brief_watch"] and rej["triggers"] == []
    assert rej["committee_result"] == "dropped by the committee (1 objections)" and rej["committee_objections"][0]["would_clear"] == "A day on 1.4x volume."
    assert rej["levels_source"] == "committee PASS (dropped)" and rej["levels"]["stop"] is not None and rej["levels"]["risk_atr"] is not None
    assert rows["ADV"]["class"] == "ADVANCE"                           # the committee's own row is unchanged
