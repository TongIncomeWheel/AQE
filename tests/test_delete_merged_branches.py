"""Branch cleanup rules (PM order 2026-11-05): delete only what is MERGED, by rule, with evidence; never main, held, open-PR or unmerged branches."""
import hashlib
import importlib
import sys

import pytest


@pytest.fixture()
def dm(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "Owner/repo"); monkeypatch.setenv("GITHUB_TOKEN", "t")
    sys.modules.pop("scripts.delete_merged_branches", None)
    return importlib.import_module("scripts.delete_merged_branches")


def _setup(dm, monkeypatch, branches, prs, ancestors=()):
    monkeypatch.setattr(dm, "branches", lambda: [{"name": n, "commit": {"sha": s}} for n, s in branches.items()])
    monkeypatch.setattr(dm, "prs_for", lambda b: prs.get(b, []))
    monkeypatch.setattr(dm, "is_ancestor", lambda sha: sha in ancestors)


def pr(n, state, head, merged=None):
    return {"number": n, "state": state, "merged_at": merged, "head": {"ref": "x", "sha": head, "repo": {"full_name": "Owner/repo"}}}


def test_the_rules_pick_exactly_the_merged_branches(dm, monkeypatch):
    br = {"main": "m1", "claude/done": "d1", "claude/extra-commits": "e2", "claude/open": "o1", "claude/unmerged": "u1", "claude/contained": "c1",
          "claude/ma-matcher-v3": "h1", "claude/list-churn": "h2", "d123-condition-alerts": "old1", "claude/ptj-cleanup-pause": "old2"}
    prs = {"claude/done": [pr(1, "closed", "d1", "2026-11-05T01:00:00Z")], "claude/extra-commits": [pr(2, "closed", "e1", "2026-11-05T01:00:00Z")],
           "claude/open": [pr(3, "open", "o1")], "claude/ma-matcher-v3": [pr(4, "closed", "h1", "2026-11-05T01:00:00Z")],
           "d123-condition-alerts": [pr(5, "closed", "old1", "2026-10-02T00:00:00Z")]}
    _setup(dm, monkeypatch, br, prs, ancestors={"c1"})
    rows = {n: (d, e) for n, _t, d, e in dm.decide()}
    assert rows["claude/done"][0] == "DELETE" and "PR #1 merged" in rows["claude/done"][1]
    assert rows["claude/contained"][0] == "DELETE" and "ancestor" in rows["claude/contained"][1]
    assert rows["claude/extra-commits"][0] == "KEEP" and "commits after it" in rows["claude/extra-commits"][1]
    assert rows["claude/open"][0] == "KEEP" and "open PR #3" in rows["claude/open"][1]
    assert rows["claude/unmerged"][0] == "KEEP"
    for held in ("main", "claude/ma-matcher-v3", "claude/list-churn", "d123-condition-alerts", "claude/ptj-cleanup-pause"):
        assert rows[held][0] == "KEEP", held                      # held / unmerged-by-PM / main: never, even with a merged PR on record


def test_delete_refuses_a_list_that_changed_since_the_dry_run_and_deletes_only_the_reviewed_list(dm, monkeypatch, capsys):
    br = {"main": "m1", "claude/a": "a1", "claude/b": "b1"}
    prs = {"claude/a": [pr(1, "closed", "a1", "2026-11-05T01:00:00Z")], "claude/b": [pr(2, "closed", "b1", "2026-11-05T01:00:00Z")]}
    _setup(dm, monkeypatch, br, prs)
    digest = hashlib.sha256("\n".join(["claude/a", "claude/b"]).encode()).hexdigest()[:16]
    calls = []
    monkeypatch.setattr(dm, "api", lambda m, p, b=None: (calls.append((m, p, b)) or ((204, None) if m == "DELETE" else (403, {"message": "admin"}))))
    monkeypatch.setattr(sys, "argv", ["x", "delete", "0000000000000000"])
    with pytest.raises(SystemExit) as e:
        dm.main()
    assert "REFUSED" in str(e.value) and not [c for c in calls if c[0] == "DELETE"]
    monkeypatch.setattr(sys, "argv", ["x", "delete", digest])
    dm.main()
    assert [c[1] for c in calls if c[0] == "DELETE"] == ["/repos/Owner/repo/git/refs/heads/claude/a", "/repos/Owner/repo/git/refs/heads/claude/b"]
    assert "needs a repo admin" in capsys.readouterr().out                           # the repo setting needing an admin is reported, not hidden


def test_a_named_pass_and_a_conductor_confirmation(dm, monkeypatch):
    br = {"main": "m1", "claude/a": "a1", "claude/rebased": "r1", "claude/other": "o1"}
    prs = {"claude/a": [pr(1, "closed", "a1", "2026-11-05T01:00:00Z")]}
    _setup(dm, monkeypatch, br, prs)
    rows = {n: d for n, _t, d, _e in dm.decide(only=("claude/a", "claude/rebased"), confirmed=())}
    assert rows == {"claude/a": "DELETE", "claude/rebased": "KEEP"}                 # not provable, not confirmed: kept; claude/other not in the pass
    rows = {n: (d, e) for n, _t, d, e in dm.decide(only=("claude/rebased",), confirmed=("claude/rebased",))}
    assert rows["claude/rebased"][0] == "DELETE" and "CONFIRMED" in rows["claude/rebased"][1]
    br["claude/ma-matcher-v3"] = "h1"
    rows = {n: d for n, _t, d, _e in dm.decide(only=("claude/ma-matcher-v3",), confirmed=("claude/ma-matcher-v3",))}
    assert rows["claude/ma-matcher-v3"] == "KEEP"                                    # a confirmation never overrides the keep list
