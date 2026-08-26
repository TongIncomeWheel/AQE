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


def _header_line(text: str) -> str:
    """The real tab-delimited header, skipping any leading '# DICT ...' legend
    lines cmd_packets may prepend (2026-08-26 compression change) -- those are
    comments, not the column row, and must never be mistaken for it."""
    for line in text.split("\n"):
        if not line.startswith("#"):
            return line
    return ""

from src.pipeline import voice_packets as vp

# The full 14-voice roster, per voice_packet_file_instruction v2 (2026-08-25).
# GROUP_A + GROUP_B are the 11 voices that get a real file; GROUP_C's 4 get
# none BY DESIGN — they activate only after the Phase-4 cap, on a bundle
# compiled during that morning's own run, so there is no static file to name.
# Asserting Group C's absence matters as much as Group A's presence: adding
# one of them to the nominator list would quietly serve it the 199-name
# universe it is specifically not supposed to see.
GROUP_A = ["elder-lens", "livermore", "minervini", "oneil", "raschke",
           "seow", "thorp", "weis", "wyckoff"]
GROUP_B = ["crown", "druckenmiller"]
GROUP_C = ["rogers", "steenbarger", "lynch", "detect-lens"]

NOMINATORS = GROUP_A


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
def _isolated_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(vp, "OUTPUT_DIR", tmp_path / "output")
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
        header = _header_line((outdir / f"{voice}.tsv").read_text(encoding="utf-8"))
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
        header = _header_line((outdir / f"{voice}.tsv").read_text(encoding="utf-8"))
        assert header.split("\t") == menus[voice], f"{voice} columns != its menu"


def test_the_packet_set_is_exactly_the_eleven_voices_with_a_file(export_file):
    """v2's tally, asserted mechanically: 9 nominators + 2 macro = 11 files,
    no more and no fewer. A new name appearing here is a voice being served
    data nobody signed off on; one disappearing is a voice left blind."""
    res = vp.build(export_file)
    expected = {f"{v}.tsv" for v in GROUP_A} | {f"{v}.json" for v in GROUP_B}
    assert set(res["files"]) == expected


def test_group_c_voices_never_get_a_packet_file(export_file):
    """rogers/steenbarger/lynch/detect-lens work off the post-cap 20-name
    deliberation bundle, never the 199-name universe. A file here would hand
    them exactly the input the design withholds."""
    vp.build(export_file)
    names = {p.name for p in vp.packets_dir("2026-08-24").iterdir()}
    for voice in GROUP_C:
        assert f"{voice}.tsv" not in names and f"{voice}.json" not in names, \
            f"{voice} must not get a static packet file"


def test_macro_packets_carry_the_macro_blocks_and_never_qs_market(export_file):
    """Group B's R3: the macro pair reads global blocks, but `qs_market` is
    PM-only and must never appear in either packet."""
    vp.build(export_file)
    outdir = vp.packets_dir("2026-08-24")

    for voice in GROUP_B:
        raw = (outdir / f"{voice}.json").read_text(encoding="utf-8")
        assert "qs_market" not in raw, f"R3 breach: qs_market in {voice}.json"
        pk = json.loads(raw)
        for block in ("date", "market", "regime", "intermarket", "srm",
                      "macro_weather", "thematic_baskets"):
            assert block in pk, f"{voice}.json missing the {block} block"


def test_everything_inside_packets_is_seat_safe(export_file):
    """The folder-level invariant: every file in packets/ is one some voice
    may open, so NO file in there may carry the PM-only qs read.
    candidate_set.json deliberately keeps `qs` (CONSUMED, for the S7 card) —
    it therefore lives BESIDE packets/, never inside it."""
    vp.build(export_file)
    outdir = vp.packets_dir()

    for p in sorted(outdir.iterdir()):
        raw = p.read_text(encoding="utf-8")
        assert "qs_market" not in raw, f"R3 breach: qs_market in packets/{p.name}"
        if p.suffix == ".tsv":
            cols = _header_line(raw).split("\t")
            assert "qs" not in cols and "on_qs" not in cols, \
                f"R3 breach: qs column in packets/{p.name}"

    # ...and the QS-carrying trim output is outside that folder.
    cs = outdir.parent / "candidate_set.json"
    assert cs.exists(), "candidate_set.json should be written beside packets/"
    assert cs.parent != outdir, "candidate_set.json must NOT live inside packets/"


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


def _fake_publisher(monkeypatch, seen):
    """Stand in for github_sync, recording what would be pushed and honouring
    the `unchanged` no-op contract put_file actually implements."""
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "is_configured", lambda: True)
    monkeypatch.setattr(github_sync, "test_credentials", lambda: {"ok": True})

    def _put(path, content, message):
        prior = seen.get(path)
        seen[path] = content
        return {"ok": True, "unchanged": prior == content}
    monkeypatch.setattr(github_sync, "put_file", _put)


def test_sync_repairs_packets_a_stale_pipeline_never_wrote(export_file, monkeypatch):
    """THE 2026-08-25 failure: the export is published but the packets were
    never built for it, because the process running the daily did not have
    Step 8a-3. sync() must notice and repair, not report success on absence."""
    seen: dict = {}
    _fake_publisher(monkeypatch, seen)

    assert not vp.packets_dir().exists(), "precondition: no packets yet"
    res = vp.sync(export_file)

    assert res["ok"] is True
    assert res["was_in_sync"] is False          # it found the gap...
    assert res["changed"], "...and actually republished something"
    assert any("packets/wyckoff.tsv" in p for p in seen)


def test_sync_is_a_no_op_when_the_packets_already_match(export_file, monkeypatch):
    """A healthy day must cost nothing and write no commit — otherwise the
    backstop churns the repo daily for no reason."""
    seen: dict = {}
    _fake_publisher(monkeypatch, seen)

    vp.sync(export_file)          # first run publishes
    res = vp.sync(export_file)    # second run: identical content

    assert res["ok"] is True
    assert res["was_in_sync"] is True
    assert res["changed"] == [], "identical content must not be republished"


def test_sync_republishes_only_what_actually_changed(export_file, tmp_path, monkeypatch):
    """When the master moves, only the packets whose columns carry the
    changed field should be rewritten."""
    seen: dict = {}
    _fake_publisher(monkeypatch, seen)
    vp.sync(export_file)

    d = json.loads(export_file.read_text(encoding="utf-8"))
    d["daily_list"][0]["sc_momentum"] = 91.5
    changed_export = tmp_path / "changed.json"
    changed_export.write_text(json.dumps(d), encoding="utf-8")

    res = vp.sync(changed_export)
    assert res["ok"] is True
    menus = json.loads(vp.VOICE_MENUS.read_text(encoding="utf-8"))
    for name in res["changed"]:
        voice = name.replace(".tsv", "").replace(".json", "")
        if voice in GROUP_A:
            assert "sc_momentum" in menus[voice], \
                f"{voice} republished but its menu has no sc_momentum"


def test_bare_invocation_defaults_to_sync():
    """The Scanner button and the .bat both run `python -m
    src.pipeline.voice_packets` with no arguments — if that errored on a
    missing subcommand, neither would work. Guards the CLI contract they
    depend on."""
    import subprocess, sys as _sys
    r = subprocess.run([_sys.executable, "-m", "src.pipeline.voice_packets"],
                       capture_output=True, text=True, cwd=str(vp.PROJECT_ROOT))
    # It may well fail further on (no GITHUB_TOKEN in CI, no export on disk) —
    # what must NOT happen is argparse rejecting the call before any work
    # starts, which is what a required subcommand would do.
    combined = r.stdout + r.stderr
    assert "arguments are required" not in combined, \
        "bare invocation must not be rejected for a missing subcommand"
    assert "invalid choice" not in combined


def test_sync_without_an_export_fails_rather_than_claiming_success(tmp_path):
    res = vp.sync(tmp_path / "nope.json")
    assert res["ok"] is False
    assert "not found" in res["reason"]


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


def test_publish_with_an_unscoped_token_gives_one_clear_reason_not_a_wall_of_403s(
        export_file, monkeypatch):
    """2026-08-26: a token that reads but can't write (e.g. this session's
    proxy-injected git credential, which is not a real Contents-API PAT) used
    to fail all 11 files individually, each with its own raw HTTPError text --
    reads as 'broken' rather than 'wrong token scope'. One auth check up
    front, one sentence, no wasted PUT attempts."""
    vp.build(export_file)
    from src.data import github_sync
    monkeypatch.setattr(github_sync, "is_configured", lambda: True)
    monkeypatch.setattr(github_sync, "test_credentials",
                         lambda: {"ok": False, "reason": "token can read but lacks "
                                                          "push/write access"})
    calls = []
    monkeypatch.setattr(github_sync, "put_file",
                         lambda *a, **k: calls.append(a) or {"ok": True})

    res = vp.publish("2026-08-24")
    assert res["ok"] is False
    assert "lacks push/write access" in res["reason"]
    assert not calls, "must not attempt any file write once the auth check fails"
