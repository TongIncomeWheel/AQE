"""Push the current branch to BOTH remotes -- GitHub (origin) + HF Space (hf).

Used by Claude during the iteration loop to publish changes in one shot.
Order: GitHub first (cheap, fast), then HF (which triggers a Docker rebuild).
On HF failure the GitHub push has already landed, so nothing is lost.

Usage:
    python -m scripts.push_both              # commit current branch to both
    python -m scripts.push_both --branch xyz # explicit branch
    python -m scripts.push_both --no-hf      # skip HF (e.g. doc-only changes)
    python -m scripts.push_both --dry-run    # print plan
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REMOTES = {
    "origin": "GitHub (TongIncomeWheel/AQE)",
    "hf":     "HuggingFace Space (AQE-Aegis/aqe)",
}


def run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def current_branch() -> str:
    rc, out, _ = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return out.strip() if rc == 0 else "main"


def remote_exists(name: str) -> bool:
    rc, _, _ = run(["git", "remote", "get-url", name])
    return rc == 0


def push_one(remote: str, branch: str, dry_run: bool) -> int:
    label = REMOTES.get(remote, remote)
    if not remote_exists(remote):
        print(f"  [skip]   {remote} -> {label}: not configured")
        return 0
    if dry_run:
        print(f"  [dry]    would push: git push {remote} {branch}  ({label})")
        return 0
    print(f"  [push]   {remote} {branch}  ({label})")
    rc, out, err = run(["git", "push", remote, branch])
    sys.stdout.write(out)
    sys.stderr.write(err)
    if rc == 0:
        print(f"  [ok]     {remote} done")
    else:
        print(f"  [FAIL]   {remote} returned {rc}")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", help="branch to push (default: current)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show plan, don't push")
    ap.add_argument("--no-hf", action="store_true",
                    help="skip the HF push (doc-only changes)")
    ap.add_argument("--no-origin", action="store_true",
                    help="skip the GitHub push")
    args = ap.parse_args()

    branch = args.branch or current_branch()
    print(f"AQE dual-push -> branch: {branch}")
    print("=" * 60)

    # Verify we're in a git repo
    rc, _, _ = run(["git", "rev-parse", "--is-inside-work-tree"])
    if rc != 0:
        print("ERROR: not a git repo.")
        return 1

    # Any unpushed commits?
    rc, out, _ = run(["git", "log", "--oneline", "@{u}..", branch]) if False else (0, "", "")  # noqa
    rc, out, _ = run(["git", "log", "--oneline", "-5", branch])
    if out.strip():
        print("Recent commits:")
        for line in out.strip().splitlines()[:5]:
            print(f"  {line}")
        print()

    failures: list[str] = []
    if not args.no_origin:
        if push_one("origin", branch, args.dry_run) != 0:
            failures.append("origin")
    else:
        print("  [skip]   origin (--no-origin)")

    if not args.no_hf:
        if push_one("hf", branch, args.dry_run) != 0:
            failures.append("hf")
    else:
        print("  [skip]   hf (--no-hf)")

    print("=" * 60)
    if failures:
        print(f"Done with failures: {', '.join(failures)}")
        return 1
    print("Done. Both remotes in sync." if not args.dry_run else "Dry-run complete.")
    if not args.dry_run and not args.no_hf:
        print("HF should redeploy in ~30s (code-only) or ~3-4 min (Dockerfile change).")
        print("Watch: https://huggingface.co/spaces/AQE-Aegis/aqe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
