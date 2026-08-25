"""Tests for src/pipeline/voice_packets.py — the daily split of the master
export into per-voice packet files, and the drift check that proves the split
still matches its source (committee request 2026-08-25).

These deliberately exercise the REAL pma_pipeline.py slicing rather than
mocking it. The whole point of the module is that the split obeys the
PM-ratified rules in one place (R3 QS exclusion, no-blank-data hold-out,
"null" token for None); a test that mocked that away would pass while the
thing it is meant to protect was broken.
"""

from __future__ import annotations

import json

import pytest

from src.pipeline import voice_packets as vp

NOMINATORS = ["elder-lens", "livermore", "minervini", "oneil", "raschke",
              "seow", "thorp", "weis", "wyckoff"]


def _row(ticker: str, **over):
    """A daily_list row with the core technical fields populated, so it is not
    held out by the no-blank-data rule."""
    r = {
        "ticker": ticker, "source": "longlist", "sc_momentum": 55.0,
        "flow": 40.0, "energy": 60.0, "structure": 50.0, "mp": 30.0,
        "elder": 7.0, "entry": 100.0, "atr_14d": 2.0, "in_ledger": False,
        "bracket": {"stop": 95.0, "targets": []},
        "qs": {"signal": "STRONG"}, "on_qs": True,   # PM-only, must not leak
    }
    r.update(over)
    return r


@pytest.fixture
def export_file(tmp_path):
    p = tmp_path / "aqe_daily_export.json"
    p.write_text(json.dumps({
        "date": "2026-08-24",
        "market": "US equities", "regime": {"vix": 15.0, "level": "GREEN"},
        "intermarket": {}, "srm": [], "macro_weather": {}, "thematic_baskets": {},
        "daily_list": [_row("AAA"), _row("BBB", sc_momentum=70.0), _row("CCC")],
    }), encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _isolated_pma_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(vp, "PMA_DATA_DIR", tmp_path / "pma")
    yield


def test_build_writes_one_file_per_nominator_voice(export_file):
    res = vp.build(export_file)

    assert res["ok"] is True
    assert res["run_date"] == "2026-08-24"
    for voice in NOMINATORS:
        assert f"{voice}.tsv" in res["files"], f"{voice} packet missing"


def test_packets_are_stamped_with_the_exports_date_not_today(export_file):
    """A re-run days later must reproduce the same packets for that export —
    the export's own date is the identity, and it also seeds the shuffle."""
    res = vp.build(export_file)
    assert res["run_date"] == "2026-08-24"
    assert vp.packets_dir("2026-08-24").exists()


def test_no_packet_leaks_the_pm_only_qs_fields(export_file):
    """R3 is absolute: qs/on_qs are PM-only and must never reach a seat. The
    source rows here deliberately carry both."""
    vp.build(export_file)
    outdir = vp.packets_dir("2026-08-24")

    for voice in NOMINATORS:
        header = (outdir / f"{voice}.tsv").read_text(encoding="utf-8").split("\n")[0]
        cols = header.split("\t")
        assert "qs" not in cols and "on_qs" not in cols, f"R3 breach in {voice}"
        assert not any(c.startswith("qs.") for c in cols), f"R3 breach in {voice}"


def test_each_voice_gets_only_its_own_columns(export_file):
    """The selection rule's whole justification: a voice sees its own menu,
    not the union. elder-lens is the narrowest menu, wyckoff the widest."""
    menus = json.loads(vp.VOICE_MENUS.read_text(encoding="utf-8"))
    vp.build(export_file)
    outdir = vp.packets_dir("2026-08-24")

    for voice in NOMINATORS:
        header = (outdir / f"{voice}.tsv").read_text(encoding="utf-8").split("\n")[0]
        assert header.split("\t") == menus[voice], f"{voice} columns != its menu"


def test_verify_is_in_sync_immediately_after_build(export_file):
    vp.build(export_file)
    res = vp.verify(export_file)
    assert res["ok"] is True, res.get("drift")
    assert res["drift"] == []


def test_verify_catches_a_tampered_packet(export_file):
    vp.build(export_file)
    p = vp.packets_dir("2026-08-24") / "wyckoff.tsv"
    lines = p.read_text(encoding="utf-8").split("\n")
    cells = lines[1].split("\t")
    cells[1] = "999.9"
    lines[1] = "\t".join(cells)
    p.write_text("\n".join(lines), encoding="utf-8")

    res = vp.verify(export_file)
    assert res["ok"] is False
    assert any("wyckoff.tsv" in d and "CONTENT DIFFERS" in d for d in res["drift"])


def test_verify_catches_a_missing_packet(export_file):
    vp.build(export_file)
    (vp.packets_dir("2026-08-24") / "seow.tsv").unlink()

    res = vp.verify(export_file)
    assert res["ok"] is False
    assert any("seow.tsv" in d and "MISSING" in d for d in res["drift"])


def test_verify_catches_a_stale_extra_packet(export_file):
    vp.build(export_file)
    (vp.packets_dir("2026-08-24") / "retired-voice.tsv").write_text("junk", encoding="utf-8")

    res = vp.verify(export_file)
    assert res["ok"] is False
    assert any("retired-voice.tsv" in d and "STALE" in d for d in res["drift"])


def test_verify_catches_master_data_changing_under_the_packets(export_file, tmp_path):
    """THE scenario this check exists for: the export is regenerated with
    different numbers and the packets on disk still hold the old ones."""
    vp.build(export_file)

    d = json.loads(export_file.read_text(encoding="utf-8"))
    d["daily_list"][0]["sc_momentum"] = 99.9
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(d), encoding="utf-8")

    res = vp.verify(changed)
    assert res["ok"] is False
    # only voices whose menu actually carries sc_momentum should be flagged
    menus = json.loads(vp.VOICE_MENUS.read_text(encoding="utf-8"))
    flagged = {d.split(":")[0].replace(".tsv", "") for d in res["drift"]}
    for voice in flagged:
        assert "sc_momentum" in menus[voice], f"{voice} flagged but has no sc_momentum"
    assert flagged, "a changed master must flag at least one packet"


def test_verify_reports_never_built_rather_than_claiming_sync(export_file):
    """No packets at all must never read as 'in sync' — that is the silent
    empty CLAUDE.md forbids."""
    res = vp.verify(export_file)
    assert res["ok"] is False
    assert any("does not exist" in d for d in res["drift"])


def test_build_on_a_missing_export_fails_loudly(tmp_path):
    res = vp.build(tmp_path / "nope.json")
    assert res["ok"] is False
    assert "not found" in res["reason"]


def test_publish_without_a_token_says_so_rather_than_silently_skipping(
        export_file, monkeypatch):
    vp.build(export_file)
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "is_configured", lambda: False)

    res = vp.publish("2026-08-24")
    assert res["ok"] is False
    assert "GITHUB_TOKEN" in res["reason"]
