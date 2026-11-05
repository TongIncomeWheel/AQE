"""Delete remote branches whose work is MERGED (PM order 2026-11-05, "Delete merged branches"), by rule, with the evidence printed per branch.

A branch is deletable ONLY if
  (a) a PR with head == that branch is MERGED and the branch tip is exactly that PR's head commit (nothing was pushed after the merge), or
  (b) its tip is an ancestor of origin/main (git proves it is contained),
AND it is not main, has no OPEN PR, and is not on the KEEP list (held branches, the old unmerged branches the PM did not name).

  python -m scripts.delete_merged_branches dry-run [names] [confirmed]
  python -m scripts.delete_merged_branches delete <digest-from-the-dry-run> [names] [confirmed]

`names` (comma list, optional) limits the pass to those branches. `confirmed` (comma list, optional) names branches the PM/conductor has CONFIRMED
are fully merged even though git cannot prove it (a rebased branch whose content is in main): they are still never deleted if they have an open PR
or are on the KEEP list.

The dry run prints every branch with its decision and evidence, and a digest of the delete list. `delete` recomputes the list and refuses to run
unless its digest equals the one given, so the real run deletes exactly the list that was reviewed. Env: GITHUB_TOKEN, GITHUB_REPOSITORY.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]
OWNER = REPO.split("/")[0]

# never deleted, whatever the evidence says
KEEP = {
    "main",
    "claude/ma-matcher-v3", "claude/list-churn",                      # held until the PM says go
    # old unmerged work the PM did not name: listed for him, never touched
    "d123-condition-alerts", "raschke-adx-followup-d116", "fix/universe-persistence-keepalive", "archive/pre-phase2",
    "claude/daily-file-management-ktilno", "claude/ibkr-connector-trade-creation-spnjnu", "claude/ibkr-mcp-server-p1miub", "claude/ptj-cleanup-pause",
}


def api(method, path, body=None):
    req = urllib.request.Request(f"https://api.github.com{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, (json.loads(e.read() or b"null") if e.fp else None)


def branches():
    out, page = [], 1
    while True:
        st, js = api("GET", f"/repos/{REPO}/branches?per_page=100&page={page}")
        if st != 200:
            sys.exit(f"cannot list branches: {st} {js}")
        out += js
        if len(js) < 100:
            return out
        page += 1


def prs_for(branch):
    q = urllib.parse.quote(f"{OWNER}:{branch}", safe="")
    st, js = api("GET", f"/repos/{REPO}/pulls?state=all&head={q}&per_page=100")
    if st != 200:
        sys.exit(f"cannot list PRs for {branch}: {st} {js}")
    return [p for p in js if p["head"]["ref"] == branch and p["head"]["repo"] and p["head"]["repo"]["full_name"] == REPO]


def is_ancestor(sha):
    return subprocess.run(["git", "merge-base", "--is-ancestor", sha, "origin/main"], capture_output=True).returncode == 0


def _csv(i):
    return [x.strip() for x in (sys.argv[i] if len(sys.argv) > i else "").split(",") if x.strip()]


def decide(only=(), confirmed=()):
    rows = []
    for b in branches():
        name, tip = b["name"], b["commit"]["sha"]
        if only and name not in only:
            continue
        if name in KEEP:
            rows.append((name, tip, "KEEP", "on the keep list (main / held / unmerged work the PM did not name)"))
            continue
        prs = prs_for(name)
        open_prs = [p for p in prs if p["state"] == "open"]
        if open_prs:
            rows.append((name, tip, "KEEP", f"open PR #{open_prs[0]['number']}"))
            continue
        merged = [p for p in prs if p.get("merged_at")]
        exact = [p for p in merged if p["head"]["sha"] == tip]
        if exact:
            p = exact[0]
            rows.append((name, tip, "DELETE", f"PR #{p['number']} merged {p['merged_at'][:16]}Z, branch tip == the PR's head commit"))
        elif is_ancestor(tip):
            rows.append((name, tip, "DELETE", "tip is an ancestor of main (git merge-base --is-ancestor)"))
        elif name in confirmed:
            rows.append((name, tip, "DELETE", "CONFIRMED merged by the PM/conductor (content is in main; git cannot prove it by ancestry)"))
        elif merged:
            p = merged[0]
            rows.append((name, tip, "KEEP", f"PR #{p['number']} merged but the branch has commits after it (tip {tip[:8]} != PR head {p['head']['sha'][:8]})"))
        else:
            rows.append((name, tip, "KEEP", "no merged PR and not contained in main: unmerged"))
    return rows


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry-run"
    off = 3 if mode == "delete" else 2
    rows = sorted(decide(_csv(off), _csv(off + 1)))
    dele = sorted(n for n, _t, d, _e in rows if d == "DELETE")
    digest = hashlib.sha256("\n".join(dele).encode()).hexdigest()[:16]
    for n, t, d, e in rows:
        print(f"{d:6} {n:55} {t[:8]}  {e}")
    print(f"\nDELETE LIST ({len(dele)}): " + ", ".join(dele))
    print(f"LIST DIGEST: {digest}")
    if mode == "dry-run":
        st, js = api("GET", f"/repos/{REPO}")
        print(f"repo setting delete_branch_on_merge = {(js or {}).get('delete_branch_on_merge')}")
        return
    if mode != "delete" or len(sys.argv) < 3:
        sys.exit("usage: delete <digest>")
    if sys.argv[2] != digest:
        sys.exit(f"REFUSED: the delete list changed since the dry run (digest {digest}, given {sys.argv[2]}). Run the dry run again and review it.")
    failed = []
    for n in dele:
        assert n not in KEEP and n != "main"
        st, js = api("DELETE", f"/repos/{REPO}/git/refs/heads/{urllib.parse.quote(n, safe='/')}")
        print(f"deleted {n}: HTTP {st}" if st in (204, 200) else f"FAILED {n}: HTTP {st} {js}")
        if st not in (204, 200):
            failed.append(n)
    st, js = api("PATCH", f"/repos/{REPO}", {"delete_branch_on_merge": True})
    print(f"set 'Automatically delete head branches': HTTP {st}" + ("" if st == 200 else f" {js and js.get('message')} (needs a repo admin to click it in Settings)"))
    left = sorted(b["name"] for b in branches())
    print("REMAINING BRANCHES:", ", ".join(left))
    if failed:
        sys.exit(f"{len(failed)} deletion(s) failed: {failed}")


if __name__ == "__main__":
    main()
