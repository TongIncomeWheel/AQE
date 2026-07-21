#!/usr/bin/env python3
"""
bootstrap.py — reconstruct the Aegis workspace inside a FRESH scheduled session (D-64).

WHY THIS EXISTS (empirically proven by the 2026-07-21 bootstrap diagnostic):
  A scheduled task fires a BRAND-NEW ephemeral container. That container has:
    - the aegis-v4 PLUGIN (skills + agents)          -> PRESENT  (synced env-level)
    - FMP / Tiger / IBKR / Google Drive MCP          -> PRESENT
    - the /home/claude/aegis WORKSPACE + config/.env  -> ABSENT   (empty /home/claude)
    - any usable GitHub credential in the env         -> ABSENT   (GH_TOKEN is a
      'proxy-injected' sentinel, GITHUB_PAT empty)
  So the old scheduled prompts ("read aegis/CONTEXT.md, run tools/...") failed at line 1:
  there was no aegis/ to read and no token to clone it. The session woke, found nothing,
  and died silently -> no commit, no artifact, no page. THAT is why jobs "fired but did
  nothing".

THE CONTRACT (anti-spaghetti — ONE bootstrap, used by every scheduled phase):
  1. The plugin ships this file. It carries NO secret (D-49 — a token never ships in the
     plugin). The token travels INLINE in the trigger prompt (the only channel that
     reaches a fresh container) and is handed to us as env AEGIS_PAT (or GITHUB_PAT).
  2. We clone (or fast-forward) TongIncomeWheel/AQE to CHECKOUT_ROOT, so the real git
     checkout exists and `aegis/...` paths resolve from there.
  3. We write aegis/config/.env with GITHUB_PAT=<token> so the downstream tools
     (git_sync.py self-heal, notify.py, preflight.py) find a credential exactly where
     they already look — no other tool changes needed.
  4. We print the checkout path + a READY/FAIL line the prompt can key on. On failure we
     exit non-zero and say why, so the phase PAGES instead of dying silently.

USAGE (from a scheduled prompt):
    export AEGIS_PAT=github_pat_xxx
    python3 /root/.claude/plugins/synced/aegis-v4/tools/bootstrap.py
    cd /home/claude/AQE      # <- the checkout root it prints; aegis/CONTEXT.md now resolves
"""
import os
import subprocess
import sys

REPO_SLUG = "TongIncomeWheel/AQE"
CHECKOUT_ROOT = os.environ.get("AEGIS_CHECKOUT_ROOT", "/home/claude/AQE")
AEGIS_DIR = os.path.join(CHECKOUT_ROOT, "aegis")
ENV_PATH = os.path.join(AEGIS_DIR, "config", ".env")
COMMIT_NAME = "Claude"
COMMIT_EMAIL = "noreply@anthropic.com"


def _token():
    for k in ("AEGIS_PAT", "GITHUB_PAT", "GH_TOKEN"):
        v = (os.environ.get(k) or "").strip()
        # skip the proxy-injected sentinel a fresh container carries in GH_TOKEN
        if v.startswith("github_pat_") or v.startswith("ghp_") or v.startswith("gho_"):
            return v
    return None


def _run(cmd, cwd=None, token=None):
    env = dict(os.environ)
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    # never echo the token if a git error surfaces the remote URL
    err = r.stderr
    if token:
        err = err.replace(token, "***")
    return r.returncode, r.stdout, err


def _remote(token):
    return f"https://x-access-token:{token}@github.com/{REPO_SLUG}.git"


def main():
    token = _token()
    if not token:
        print("BOOTSTRAP_FAIL: no usable PAT in AEGIS_PAT/GITHUB_PAT (env GH_TOKEN sentinel "
              "does not count). The scheduled prompt must export AEGIS_PAT=<pat>.", file=sys.stderr)
        return 2

    remote = _remote(token)

    if os.path.isdir(os.path.join(CHECKOUT_ROOT, ".git")):
        # already a checkout (idempotent re-run) -> fast-forward
        rc, out, err = _run(["git", "fetch", "--depth", "1", remote, "main"],
                            cwd=CHECKOUT_ROOT, token=token)
        if rc == 0:
            _run(["git", "reset", "--hard", "FETCH_HEAD"], cwd=CHECKOUT_ROOT, token=token)
        else:
            print(f"BOOTSTRAP_WARN: fetch failed, keeping existing checkout: {err.strip()}",
                  file=sys.stderr)
    else:
        # fresh container -> clone
        os.makedirs(os.path.dirname(CHECKOUT_ROOT) or ".", exist_ok=True)
        rc, out, err = _run(["git", "clone", "--depth", "1", remote, CHECKOUT_ROOT], token=token)
        if rc != 0:
            print(f"BOOTSTRAP_FAIL: clone failed: {err.strip()}", file=sys.stderr)
            return 3

    if not os.path.isdir(AEGIS_DIR):
        print(f"BOOTSTRAP_FAIL: repo cloned but {AEGIS_DIR} missing — repo layout changed?",
              file=sys.stderr)
        return 4

    # pin the committer so downstream git_sync pushes are attributable
    _run(["git", "config", "user.name", COMMIT_NAME], cwd=CHECKOUT_ROOT, token=token)
    _run(["git", "config", "user.email", COMMIT_EMAIL], cwd=CHECKOUT_ROOT, token=token)

    # write config/.env where every downstream tool already looks for the PAT
    os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
    with open(ENV_PATH, "w") as f:
        f.write(f"GITHUB_PAT={token}\n")
    os.chmod(ENV_PATH, 0o600)

    print(f"AEGIS_CHECKOUT={CHECKOUT_ROOT}")
    print(f"AEGIS_WORKSPACE={AEGIS_DIR}")
    print("BOOTSTRAP_READY: workspace reconstructed, config/.env written, committer pinned.")
    print(f"NEXT: cd {CHECKOUT_ROOT} && read aegis/CONTEXT.md + charter, then run the phase.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
