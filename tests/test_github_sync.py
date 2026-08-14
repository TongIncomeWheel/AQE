"""GitHub as the primary store — the guarantees, not the plumbing.

The network calls are not the risky part. The risky parts are: a write that
fails and reads as a success, a snapshot that quietly comes from the backup, and
a daily binary landing in git history where it would grow the repo forever. Each
of those gets a test.
"""

from __future__ import annotations

import json

import pytest

from src.data import github_sync as gh


# ── configuration is explicit, never guessed ─────────────────────────────

def test_the_output_folder_is_the_one_the_pm_named():
    assert gh.OUTPUT_DIR_IN_REPO == "aegis/output"


def test_the_snapshot_is_a_release_asset_not_a_commit():
    """A daily binary committed to the repo would add its full size to git
    history every day, permanently. The tag is how it stays out."""
    assert gh.SNAPSHOT_TAG
    src = (gh.__file__)
    text = open(src, encoding="utf-8").read()
    assert "uploads.github.com" in text, "release upload path is gone"
    # The snapshot must never be routed through the contents (commit) API.
    assert "put_file(f\"{OUTPUT_DIR_IN_REPO}/aqe_state_snapshot" not in text


def test_every_daily_artifact_is_named_once(monkeypatch):
    assert len(set(gh.DAILY_ARTIFACTS)) == len(gh.DAILY_ARTIFACTS)
    assert "aqe_daily_export.json" in gh.DAILY_ARTIFACTS
    assert "aqe_crown_macro.json" in gh.DAILY_ARTIFACTS


def test_no_dated_filenames_in_the_daily_set():
    """One copy each, overwritten. A folder a reader has to pick the newest
    from is how the wrong-file held book happened once already."""
    import re
    for name in gh.DAILY_ARTIFACTS:
        assert not re.search(r"\d{4}-\d{2}-\d{2}", name), name


# ── it degrades loudly, never silently ───────────────────────────────────

def _no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("AQE_GITHUB_TOKEN", raising=False)


def test_without_a_token_every_call_states_a_reason(monkeypatch):
    _no_token(monkeypatch)
    assert not gh.is_configured()
    for res in (gh.get_file("x"), gh.put_file("x", "y", "m"),
                gh.delete_file("x", "m"), gh.list_output(),
                gh.upload_asset("a.zip", b"x"), gh.download_asset("a.zip"),
                gh.asset_status("a.zip")):
        assert res["ok"] is False
        assert res["reason"], "a failure with no reason is a silent failure"


def test_test_credentials_without_a_token_states_a_reason(monkeypatch):
    _no_token(monkeypatch)
    res = gh.test_credentials()
    assert res["ok"] is False and res["reason"]


def test_test_credentials_rejects_a_bad_pat(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")

    class R:
        status_code = 401

        def raise_for_status(self):
            raise AssertionError("should not be called on 401")

    monkeypatch.setattr(gh.requests, "get", lambda *a, **k: R())
    res = gh.test_credentials()
    assert res["ok"] is False and "rejected" in res["reason"]


def test_test_credentials_flags_a_read_only_pat(monkeypatch):
    """A token that authenticates but lacks Contents: write must fail before
    the first real publish does, not after."""
    monkeypatch.setenv("GITHUB_TOKEN", "x")

    class R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"full_name": "TongIncomeWheel/AQE", "permissions": {"push": False}}

    monkeypatch.setattr(gh.requests, "get", lambda *a, **k: R())
    res = gh.test_credentials()
    assert res["ok"] is False and "push/write" in res["reason"]


def test_test_credentials_confirms_write_access(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")

    class R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"full_name": "TongIncomeWheel/AQE", "permissions": {"push": True}}

    monkeypatch.setattr(gh.requests, "get", lambda *a, **k: R())
    res = gh.test_credentials()
    assert res["ok"] is True
    assert res["repo"] == "TongIncomeWheel/AQE"


def test_publish_outputs_reports_a_reason_when_unconfigured(monkeypatch):
    _no_token(monkeypatch)
    res = gh.publish_outputs({"a.json": "{}"})
    assert res["ok"] is False and res["reason"]


def test_a_missing_file_is_distinguishable_from_an_unreachable_github(monkeypatch):
    """'not there yet' and 'could not reach GitHub' lead to different actions."""
    monkeypatch.setenv("GITHUB_TOKEN", "x")

    class R:
        status_code = 404

        def raise_for_status(self):
            raise AssertionError("should not be called on 404")

    monkeypatch.setattr(gh.requests, "get", lambda *a, **k: R())
    res = gh.get_file("nope.json")
    assert res["ok"] is False and res["missing"] is True


def test_a_partial_publish_is_not_reported_as_a_success(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    calls = {"n": 0}

    def fake_put(path, content, message):
        calls["n"] += 1
        return {"ok": calls["n"] == 1, "reason": None if calls["n"] == 1 else "boom"}

    monkeypatch.setattr(gh, "put_output", fake_put)
    res = gh.publish_outputs({"a.json": "{}", "b.json": "{}"})
    assert res["ok"] is False
    assert res["written"] == 1
    assert res["failed"] and "b.json" in res["failed"]
    assert "1 of 2 failed" in res["reason"]


def test_an_absent_artifact_is_named_rather_than_skipped_quietly(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setattr(gh, "publish_outputs",
                        lambda payload, stamp=None: {"ok": True, "written": len(payload),
                                                     "results": {}, "failed": []})
    import src.data.paths as paths
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    (tmp_path / "aqe_daily_export.json").write_text("{}")

    res = gh.publish_daily_outputs()
    assert res["ok"] is True
    assert "qs_daily.json" in res["absent"], "a run that produced no QS must show it"


def test_identical_content_is_a_success_not_a_failure(monkeypatch):
    """GitHub rejects a commit that changes nothing. That is not a write error,
    and a caller must not read it as one."""
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setattr(gh, "get_file",
                        lambda p: {"ok": True, "text": "same", "sha": "abc"})
    res = gh.put_file("a.json", "same", "m")
    assert res["ok"] is True and res["unchanged"] is True


# ── the snapshot pairing ─────────────────────────────────────────────────

def test_one_zip_feeds_both_stores(monkeypatch):
    """Two stores holding different bytes from the same run is worse than one
    store, because a restore would depend on which answered."""
    from src.data import persist as P
    built = {"ok": True, "blob": b"ZIP", "files": ["data/x"], "bytes": 3,
             "saved_at": "2026-08-12 09:00:00 SGT"}
    seen = []
    monkeypatch.setattr(P, "build_snapshot_bytes", lambda: built)
    monkeypatch.setattr(P, "save_snapshot_github",
                        lambda b=None: seen.append(("gh", b)) or {"ok": True})
    monkeypatch.setattr(P, "save_snapshot",
                        lambda b=None: seen.append(("drive", b)) or {"ok": True})
    res = P.save_snapshot_everywhere()
    assert res["ok"] and res["primary_ok"] and res["backup_ok"]
    assert [s[1] for s in seen] == [built, built], "each store got the same zip"


def test_a_backup_only_save_is_flagged_not_smoothed_over(monkeypatch):
    from src.data import persist as P
    monkeypatch.setattr(P, "build_snapshot_bytes",
                        lambda: {"ok": True, "blob": b"Z", "files": [], "bytes": 1,
                                 "saved_at": "x"})
    monkeypatch.setattr(P, "save_snapshot_github",
                        lambda b=None: {"ok": False, "reason": "403"})
    monkeypatch.setattr(P, "save_snapshot", lambda b=None: {"ok": True})
    res = P.save_snapshot_everywhere()
    assert res["ok"] is True, "one good store still means the state is saved"
    assert res["primary_ok"] is False
    assert "403" in res["reason"], "the broken leg must be visible"


def test_a_restore_says_which_store_answered(monkeypatch):
    from src.data import persist as P
    monkeypatch.setattr(P, "load_snapshot_github",
                        lambda only=None: {"ok": False, "reason": "no asset"})
    monkeypatch.setattr(P, "load_snapshot",
                        lambda only=None: {"ok": True, "files": ["a"]})
    res = P.load_snapshot_best()
    assert res["ok"] and res["store"] == "drive_backup"
    assert res["tried"]["github"] == "no asset", "the primary's reason is kept"


def test_a_total_restore_failure_carries_both_reasons(monkeypatch):
    from src.data import persist as P
    monkeypatch.setattr(P, "load_snapshot_github",
                        lambda only=None: {"ok": False, "reason": "gh down"})
    monkeypatch.setattr(P, "load_snapshot",
                        lambda only=None: {"ok": False, "reason": "drive down"})
    res = P.load_snapshot_best()
    assert res["ok"] is False
    assert "gh down" in res["reason"] and "drive down" in res["reason"]


# ── the cold-start autoload ──────────────────────────────────────────────

def test_a_warm_container_does_not_download_anything(monkeypatch, tmp_path):
    from src.ui import bootstrap as B
    monkeypatch.setattr(B, "_done", False)
    monkeypatch.setattr(B, "state_is_cold", lambda: (False, []))
    called = {"n": 0}
    import src.data.persist as P
    monkeypatch.setattr(P, "load_snapshot_best",
                        lambda only=None: called.__setitem__("n", called["n"] + 1))
    res = B.autoload_state()
    assert res["state"] == "warm"
    assert called["n"] == 0, "a warm container must not pull the snapshot"


def test_a_cold_container_restores_and_names_the_store(monkeypatch):
    from src.ui import bootstrap as B
    import src.data.persist as P
    monkeypatch.setattr(B, "_done", False)
    monkeypatch.setattr(B, "state_is_cold", lambda: (True, ["panel_daily.parquet"]))
    monkeypatch.setattr(P, "load_snapshot_best",
                        lambda only=None: {"ok": True, "count": 12,
                                           "store": "github_release",
                                           "saved_at": "2026-08-12"})
    res = B.autoload_state()
    assert res["state"] == "restored"
    assert res["store"] == "github_release"
    assert res["degraded"] is False


def test_a_fallback_restore_is_marked_degraded(monkeypatch):
    """A working app and a broken primary are two facts, and both must show."""
    from src.ui import bootstrap as B
    import src.data.persist as P
    monkeypatch.setattr(B, "_done", False)
    monkeypatch.setattr(B, "state_is_cold", lambda: (True, ["panel_daily.parquet"]))
    monkeypatch.setattr(P, "load_snapshot_best",
                        lambda only=None: {"ok": True, "count": 3,
                                           "store": "drive_backup",
                                           "tried": {"github": "401"}})
    res = B.autoload_state()
    assert res["degraded"] is True
    assert "401" in res["reason"]


def test_the_app_still_opens_when_every_store_is_down(monkeypatch):
    from src.ui import bootstrap as B
    import src.data.persist as P
    monkeypatch.setattr(B, "_done", False)
    monkeypatch.setattr(B, "state_is_cold", lambda: (True, ["panel_daily.parquet"]))

    def boom(only=None):
        raise RuntimeError("network gone")

    monkeypatch.setattr(P, "load_snapshot_best", boom)
    monkeypatch.setattr(B, "_salvage_read_only_artifacts",
                        lambda: {"ok": False, "reason": "repo unreachable too"})
    res = B.autoload_state()          # must not raise
    assert res["state"] == "failed" and "network gone" in res["reason"]


# ── the deploy guard ─────────────────────────────────────────────────────

def test_a_data_commit_cannot_trigger_an_hf_rebuild():
    """Without this the daily commit would rebuild the Space and destroy the
    container that had just written the file — on a schedule."""
    wf = open(".github/workflows/deploy-hf.yml", encoding="utf-8").read()
    assert "paths-ignore" in wf
    assert "aegis/output/**" in wf


def test_the_actions_backstop_may_write_its_own_output():
    wf = open(".github/workflows/daily-run.yml", encoding="utf-8").read()
    assert "permissions:" in wf and "contents: write" in wf


def test_the_repo_folder_is_the_last_resort_when_the_snapshot_is_gone(monkeypatch, tmp_path):
    """Removing the old committed root copy must not cost the cold path. The
    replacement is better: it fetches the CURRENT export, not a frozen one."""
    from src.ui import bootstrap as B
    import src.data.persist as P
    import src.data.paths as paths

    monkeypatch.setattr(B, "_done", False)
    monkeypatch.setattr(B, "state_is_cold", lambda: (True, ["panel_daily.parquet"]))
    monkeypatch.setattr(P, "load_snapshot_best",
                        lambda only=None: {"ok": False, "reason": "no asset"})
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setattr(gh, "get_file",
                        lambda p: {"ok": True, "text": "{}", "sha": "s"}
                        if p.endswith("aqe_daily_export.json")
                        else {"ok": False, "missing": True, "reason": "no"})

    res = B.autoload_state()
    assert res["state"] == "restored"
    assert res["partial"] is True, "a JSON-only recovery is not a full restore"
    assert res["degraded"] is True
    assert "no asset" in (res["reason"] or ""), "why the snapshot failed must survive"
    assert (tmp_path / "aqe_daily_export.json").exists()


def test_the_salvage_never_tries_to_pull_a_panel_through_the_contents_api():
    from src.ui import bootstrap as B
    assert not any(n.endswith(".parquet") for n in B._SALVAGE)
    assert not any(n.endswith(".db") for n in B._SALVAGE)


# ── ONE destination, and it has to stay that way ─────────────────────────

def test_there_is_exactly_one_daily_file_destination():
    """Two designs for this landed on the same day and both claimed the same
    ruling. The PM picked aegis/output/ on 2026-08-13; this pins it so a second
    location cannot quietly reappear."""
    import subprocess
    tracked = subprocess.run(["git", "ls-files"], capture_output=True,
                             text=True).stdout.split()
    rivals = [p for p in tracked if p.startswith("aegis/data/aqe/")]
    assert not rivals, f"a second AQE data location is back: {rivals}"


def test_no_dated_run_folder_holds_a_daily_aqe_artifact():
    """A dated copy of the export is a second destination wearing a date."""
    import re
    import subprocess
    tracked = subprocess.run(["git", "ls-files"], capture_output=True,
                             text=True).stdout.split()
    dated = [p for p in tracked
             if re.search(r"/\d{4}-\d{2}-\d{2}/", p)
             and any(a.split(".")[0] in p for a in gh.DAILY_ARTIFACTS)]
    assert not dated, f"daily artifacts found under dated folders: {dated}"


def test_the_pma_contract_points_at_the_surviving_destination():
    """S1 is the boundary that moves the day's data into the repo. If it still
    names the retired path, the committee reads a folder nothing writes."""
    s1 = open("aegis/skills/premarket-analysis/stages/S1_ingest.md",
              encoding="utf-8").read()
    assert "aegis/output/" in s1
    assert "data/aqe/<date>/" not in s1 and "data/aqe/<YYYY-MM-DD>/" not in s1


def test_the_fixed_path_freshness_check_is_still_mandated():
    """A dated path fails loudly when a day is missing. A fixed path always
    reads, so staleness is the only guard left and it must not be optional."""
    s1 = open("aegis/skills/premarket-analysis/stages/S1_ingest.md",
              encoding="utf-8").read()
    assert "Freshness" in s1
    assert "not optional" in s1
