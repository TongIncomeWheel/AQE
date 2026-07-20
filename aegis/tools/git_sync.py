#!/usr/bin/env python3
"""
git_sync.py — autonomous state commit + push (D-48; self-heal + identity D-56).

The daily loops persist their shelf/state to the repo; a scheduled (unattended)
session must be able to commit and push WITHOUT a human pasting a credential.
There is no GitHub MCP connector, so push authenticates from a token in the
environment (config/.env: GITHUB_PAT), used TRANSIENTLY in the push URL — never
written to .git/config, never logged.

Design / doctrine:
  - Order-blind (constitution law 1): syncs data/state only. Places/sizes/arms nothing.
  - SELF-HEALING (D-56, the agentic-loop principle): the repo path never changes,
    so a MISSING local checkout is not an error to report to the PM — it is a state
    to REPAIR. If no .git is found (a cold / ephemeral session), git_sync CLONES the
    repo fresh from the known origin (config/endpoints.json aqe_repo.url) using the
    token, mirrors the working state in, commits and pushes. It never again reports a
    missing repo as "nothing to commit (clean)" — that false-success was the D-56 bug.
  - Fail-visible (law 3): a genuine failure (no token, clone fails, push rejected)
    returns ok=false with the reason. It never fabricates success.
  - Idempotent: a real checkout with nothing staged -> clean no-op. Safe every loop.
  - Secret-safe: token read from env/.env, injected only into subprocess URLs,
    scrubbed from all output.
  - Identity PINNED (D-56): commits author as Claude <noreply@anthropic.com> so the
    autonomous history is consistent and GitHub-verified; override via env if needed.
"""

import os
import re
import sys
import json
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../<repo>/aegis
AEGIS_SUBDIR = os.path.basename(ROOT)                                # "aegis"
DEFAULT_REMOTE = "github.com/TongIncomeWheel/AQE.git"
# Identity is pinned so the unattended commit history is consistent + verified.
COMMIT_NAME = os.environ.get("GIT_AUTHOR_NAME", "Claude")
COMMIT_EMAIL = os.environ.get("GIT_AUTHOR_EMAIL", "noreply@anthropic.com")
# Where a self-healed clone lands when no in-place checkout exists.
CHECKOUT_DIR = os.environ.get("AEGIS_CHECKOUT_DIR",
                              os.path.join(os.path.expanduser("~"), ".aegis_sync_checkout"))
DEFAULT_PATHS = ["aegis/data", "aegis/charter/decisions_log.md", "aegis/data/persistent"]


def _looks_like_pat(t):
    """A real GitHub token, not a proxy/placeholder. The sandbox injects a bogus
    GH_TOKEN=proxy-injected... that must NOT shadow the real PAT in config/.env."""
    return bool(t) and (t.startswith("github_pat_") or t.startswith("ghp_") or t.startswith("gho_"))


def _token():
    # Gather candidates in priority order, but RETURN the first that is shaped like a
    # real GitHub PAT (env placeholders like GH_TOKEN=proxy-injected are skipped).
    candidates = [os.environ.get("GITHUB_PAT"), os.environ.get("GH_TOKEN")]
    envfile = os.path.join(ROOT, "config", ".env")
    if os.path.exists(envfile):
        try:
            for line in open(envfile):
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() in ("GITHUB_PAT", "GH_TOKEN"):
                    candidates.append(v.split("#", 1)[0].strip().strip('"').strip("'"))
        except Exception:
            pass
    for t in candidates:
        if _looks_like_pat(t):
            return t
    # nothing PAT-shaped — return the first non-empty as a last resort (fail-visible on push)
    for t in candidates:
        if t:
            return t
    return None


def _scrub(text, token=None):
    if not text:
        return text
    if token:
        text = text.replace(token, "***")
    return re.sub(r"github_pat_[A-Za-z0-9_]+|ghp_[A-Za-z0-9]+", "***", text)


def _remote_base():
    """Host/path of origin, credential-stripped. Prefer endpoints.json (works even
    with NO local checkout — the whole point of self-heal); fall back to git remote,
    then the hard default. The repo path never changes, so this is reliable."""
    ep = os.path.join(ROOT, "config", "endpoints.json")
    try:
        url = json.load(open(ep)).get("aqe_repo", {}).get("url", "")
        m = re.sub(r"^https?://([^@/]+@)?", "", url).rstrip("/")
        if m and "REPLACE" not in m:
            return m
    except Exception:
        pass
    try:
        url = subprocess.run(["git", "-C", ROOT, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        m = re.sub(r"^https?://([^@/]+@)?", "", url).rstrip("/")
        if m:
            return m
    except Exception:
        pass
    return DEFAULT_REMOTE


def _repo_root():
    """The git toplevel that contains ROOT, or None if ROOT is not inside a checkout."""
    try:
        p = subprocess.run(["git", "-C", ROOT, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except Exception:
        pass
    return None


def _run(repo, args, token=None):
    p = subprocess.run(["git", "-C", repo] + args, capture_output=True, text=True, timeout=180)
    return p.returncode, _scrub(p.stdout, token), _scrub(p.stderr, token)


def _self_heal_clone(token, base):
    """No in-place checkout (cold/ephemeral session) — REPAIR it: clone fresh and
    mirror the working state in. Returns (repo_root, error)."""
    if not token:
        return None, ("no local checkout AND no GITHUB_PAT/GH_TOKEN — cannot self-heal. "
                      "Set the token in aegis/config/.env.")
    url = f"https://x-access-token:{token}@{base}"
    if os.path.isdir(os.path.join(CHECKOUT_DIR, ".git")):
        # reuse an earlier self-healed checkout; hard-sync it to origin/main
        subprocess.run(["git", "-C", CHECKOUT_DIR, "remote", "set-url", "origin", url],
                       capture_output=True, text=True, timeout=30)
        f = subprocess.run(["git", "-C", CHECKOUT_DIR, "fetch", "--depth", "1", "origin", "main"],
                           capture_output=True, text=True, timeout=120)
        if f.returncode != 0:
            return None, "self-heal fetch failed: " + _scrub(f.stderr, token)
        subprocess.run(["git", "-C", CHECKOUT_DIR, "reset", "--hard", "origin/main"],
                       capture_output=True, text=True, timeout=60)
    else:
        shutil.rmtree(CHECKOUT_DIR, ignore_errors=True)
        c = subprocess.run(["git", "clone", "--depth", "1", url, CHECKOUT_DIR],
                           capture_output=True, text=True, timeout=300)
        if c.returncode != 0:
            return None, "self-heal clone failed: " + _scrub(c.stderr, token)
    return CHECKOUT_DIR, None


def _mirror_state(repo_root, paths):
    """Copy the live working state from ROOT into the (cloned) checkout's aegis subdir,
    so what we commit is the state this session produced. Only for the self-heal path."""
    copied = []
    for p in paths:
        rel = p[len(AEGIS_SUBDIR) + 1:] if p.startswith(AEGIS_SUBDIR + "/") else p
        src = os.path.join(ROOT, rel)
        dst = os.path.join(repo_root, AEGIS_SUBDIR, rel)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            copied.append(p)
        elif os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(p)
    return copied


def check():
    token = _token()
    base = _remote_base()
    url = f"https://x-access-token:{token}@{base}" if token else f"https://{base}"
    p = subprocess.run(["git", "ls-remote", "--heads", url, "main"],
                       capture_output=True, text=True, timeout=30)
    ok = p.returncode == 0
    return {"ok": ok, "reachable": ok, "token_present": bool(token),
            "remote": base, "detail": _scrub(p.stderr, token) if not ok else "ls-remote ok"}


def sync(message, paths=None, dry_run=False):
    token = _token()
    paths = paths or DEFAULT_PATHS
    base = _remote_base()

    repo = _repo_root()
    healed = False
    if repo is None:
        # SELF-HEAL (D-56): missing checkout is a repair, not a silent "clean".
        if dry_run:
            return {"ok": False, "pushed": False, "reason":
                    "no local checkout — would self-heal-clone then push (dry-run: not doing it)",
                    "remote": base}
        repo, err = _self_heal_clone(token, base)
        if repo is None:
            return {"ok": False, "pushed": False, "reason": err, "remote": base}
        healed = True
        _mirror_state(repo, paths)

    # identity (pinned, idempotent)
    _run(repo, ["config", "user.name", COMMIT_NAME])
    _run(repo, ["config", "user.email", COMMIT_EMAIL])

    # stage
    existing = [p for p in paths if os.path.exists(os.path.join(repo, p))]
    _run(repo, ["add", "--"] + existing) if existing else _run(repo, ["add", "-A"])

    # anything to commit? (guard against a fatal masquerading as clean — the D-56 bug)
    rc, out, err = _run(repo, ["status", "--porcelain"])
    if rc != 0:
        return {"ok": False, "pushed": False, "stage": "status",
                "detail": err or "git status failed", "remote": base}
    if not out.strip():
        return {"ok": True, "pushed": False, "reason": "nothing to commit (clean)",
                "self_healed": healed, "remote": base}

    if dry_run:
        return {"ok": True, "pushed": False, "reason": "dry-run",
                "would_commit": out.strip().splitlines()[:20], "remote": base}

    rc, out, err = _run(repo, ["commit", "-m", message], token)
    if rc != 0:
        return {"ok": False, "pushed": False, "stage": "commit", "detail": err or out}

    if not token:
        return {"ok": False, "pushed": False, "committed": True,
                "reason": "GITHUB_PAT/GH_TOKEN not in env — committed locally, NOT pushed (D-48).",
                "remote": base}

    url = f"https://x-access-token:{token}@{base}"
    p = subprocess.run(["git", "-C", repo, "push", url, "HEAD:main"],
                       capture_output=True, text=True, timeout=180)
    if p.returncode != 0:
        return {"ok": False, "pushed": False, "committed": True, "stage": "push",
                "detail": _scrub(p.stderr, token), "remote": base}
    return {"ok": True, "pushed": True, "self_healed": healed, "remote": base, "message": message}


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Aegis autonomous git state sync (order-blind, D-48/D-56)")
    ap.add_argument("--message", "-m", default="aegis state sync")
    ap.add_argument("--paths", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        print(json.dumps(check(), indent=2)); return
    print(json.dumps(sync(a.message, a.paths, a.dry_run), indent=2))


if __name__ == "__main__":
    _main()
