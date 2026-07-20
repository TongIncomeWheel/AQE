#!/usr/bin/env python3
"""
git_sync.py — autonomous state commit + push (D-48).

The daily loops persist their shelf/state to the repo; a scheduled (unattended)
session must be able to commit and push WITHOUT a human pasting a credential.
There is no GitHub MCP connector, so push authenticates from a token in the
environment (config/.env: GITHUB_PAT), used TRANSIENTLY in the push URL — never
written to .git/config, never logged.

Design / doctrine:
  - Order-blind (constitution law 1): this syncs data/state only. It places,
    sizes, arms nothing.
  - Fail-visible (law 3 / Failure rule): if the token is absent or the push
    fails, it says so and returns a failed status — it never fabricates success,
    and the run's outputs are still safe on disk (and, for the book, in Drive).
  - Idempotent: nothing to commit → clean no-op. Safe to run every loop.
  - Secret-safe: the token is read from env, injected only into the push
    subprocess URL, and scrubbed from any error text before printing.

CLI:
  git_sync.py --message "post-market 2026-07-20" [--paths aegis/data aegis/charter]
  git_sync.py --check      # verify read auth (ls-remote) without committing
  git_sync.py --dry-run    # stage + show what WOULD push, no network
"""

import os
import re
import sys
import json
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("AEGIS_REPO_DIR", ROOT)
# repo web/base without scheme creds — read from endpoints if present, else default
DEFAULT_REMOTE = "github.com/TongIncomeWheel/AQE.git"
COMMIT_NAME = os.environ.get("GIT_AUTHOR_NAME", "Aegis Kernel")
COMMIT_EMAIL = os.environ.get("GIT_AUTHOR_EMAIL", "aegis@local")


def _token():
    # 1) environment (a real env var / secret store), else
    # 2) the ONE file: aegis/config/.env  (line: GITHUB_PAT=...). gitignored.
    t = os.environ.get("GITHUB_PAT") or os.environ.get("GH_TOKEN")
    if t:
        return t
    envfile = os.path.join(ROOT, "config", ".env")
    if os.path.exists(envfile):
        try:
            for line in open(envfile):
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() in ("GITHUB_PAT", "GH_TOKEN"):
                    v = v.split("#", 1)[0].strip().strip('"').strip("'")
                    if v:
                        return v
        except Exception:
            pass
    return None


def _scrub(text, token):
    if not text:
        return text
    if token:
        text = text.replace(token, "***")
    # belt-and-suspenders: redact anything that looks like a PAT
    return re.sub(r"github_pat_[A-Za-z0-9_]+|ghp_[A-Za-z0-9]+", "***", text)


def _remote_base():
    """Host/path of the origin remote, stripped of any embedded credentials."""
    try:
        url = subprocess.run(["git", "-C", REPO, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        url = ""
    if url:
        # strip scheme + any user:pass@
        m = re.sub(r"^https?://([^@/]+@)?", "", url).rstrip("/")
        if m:
            return m
    return DEFAULT_REMOTE


def _run(args, token=None):
    p = subprocess.run(["git", "-C", REPO] + args, capture_output=True, text=True, timeout=120)
    return p.returncode, _scrub(p.stdout, token), _scrub(p.stderr, token)


def check():
    """Read-auth probe (ls-remote). Public repo answers without a token; a token,
    if present, is exercised too. Proves the remote is reachable."""
    token = _token()
    base = _remote_base()
    url = f"https://x-access-token:{token}@{base}" if token else f"https://{base}"
    p = subprocess.run(["git", "-C", REPO, "ls-remote", "--heads", url, "main"],
                       capture_output=True, text=True, timeout=30)
    ok = p.returncode == 0
    return {"ok": ok, "reachable": ok, "token_present": bool(token),
            "remote": base, "detail": _scrub(p.stderr, token) if not ok else "ls-remote ok"}


def sync(message, paths=None, dry_run=False):
    token = _token()
    paths = paths or ["aegis/data", "aegis/charter/decisions_log.md",
                      "aegis/data/persistent"]
    base = _remote_base()

    # identity (idempotent)
    _run(["config", "user.name", COMMIT_NAME])
    _run(["config", "user.email", COMMIT_EMAIL])

    # stage
    existing = [p for p in paths if os.path.exists(os.path.join(REPO, p))]
    if existing:
        _run(["add", "--"] + existing)
    else:
        _run(["add", "-A"])

    # anything to commit?
    rc, out, _ = _run(["status", "--porcelain"])
    if not out.strip():
        return {"ok": True, "pushed": False, "reason": "nothing to commit (clean)"}

    if dry_run:
        return {"ok": True, "pushed": False, "reason": "dry-run",
                "would_commit": out.strip().splitlines()[:20], "remote": base}

    rc, out, err = _run(["commit", "-m", message], token)
    if rc != 0:
        return {"ok": False, "pushed": False, "stage": "commit", "detail": err or out}

    if not token:
        # committed locally but cannot push — fail-visible, do NOT pretend it synced
        return {"ok": False, "pushed": False, "committed": True,
                "reason": "GITHUB_PAT/GH_TOKEN not in env — committed locally, NOT pushed. "
                          "Set the token in config/.env so unattended runs can push (D-48).",
                "remote": base}

    url = f"https://x-access-token:{token}@{base}"
    p = subprocess.run(["git", "-C", REPO, "push", url, "HEAD:main"],
                       capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        return {"ok": False, "pushed": False, "committed": True, "stage": "push",
                "detail": _scrub(p.stderr, token)}
    return {"ok": True, "pushed": True, "remote": base, "message": message}


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Aegis autonomous git state sync (order-blind, D-48)")
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
