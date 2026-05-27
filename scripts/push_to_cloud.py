"""Commit + push the latest AQE export so the Streamlit Cloud app refreshes.

Run after the daily pipeline finishes. Only the small, cloud-facing files are
staged -- the parquet caches and real-money JSON stay local (gitignored).

Usage:
    python -m scripts.push_to_cloud                 # auto-commit + push
    python -m scripts.push_to_cloud --no-push       # commit only
    python -m scripts.push_to_cloud --dry-run       # print plan, no git changes
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SGT = ZoneInfo("Asia/Singapore")

# Files the cloud Scanner needs. Everything else is either gitignored or
# already committed (source code). This is intentionally short — adding new
# entries requires understanding which page consumes them.
CLOUD_FILES = [
    "output/aqe_daily_export.json",
    "output/recipes.json",
    "data/active_recipe.json",
    "data/sector_map.json",
    "data/universe.txt",
    "data/earnings_calendar.json",
]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=PROJECT_ROOT, text=True,
                          capture_output=True, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would happen without staging or pushing")
    ap.add_argument("--no-push", action="store_true",
                    help="commit but don't push")
    ap.add_argument("--message", "-m",
                    help="commit message override; defaults to a timestamped one")
    args = ap.parse_args()

    # Verify git repo
    r = run(["git", "rev-parse", "--is-inside-work-tree"])
    if r.returncode != 0:
        print("ERROR: not a git repo. Run `git init` and add a remote first.")
        return 1

    # Verify remote 'origin' configured
    r = run(["git", "remote", "get-url", "origin"])
    has_remote = r.returncode == 0
    if not has_remote and not args.no_push and not args.dry_run:
        print("ERROR: no 'origin' remote. Add one with:")
        print("    git remote add origin https://github.com/<user>/<repo>.git")
        return 1

    # Stage only the files that exist; warn about the rest
    present = [f for f in CLOUD_FILES if (PROJECT_ROOT / f).exists()]
    missing = [f for f in CLOUD_FILES if not (PROJECT_ROOT / f).exists()]
    if missing:
        print(f"Skipping (not on disk): {', '.join(missing)}")

    if not present:
        print("Nothing to commit -- run the daily pipeline first.")
        return 1

    if args.dry_run:
        print("DRY RUN. Would stage:")
        for f in present:
            print(f"    {f}")
        print("Would commit with message:", _default_message(args.message))
        if has_remote and not args.no_push:
            print("Would push to: origin/main (or current branch)")
        return 0

    # Stage
    r = run(["git", "add", "--"] + present)
    if r.returncode != 0:
        print("git add failed:", r.stderr)
        return r.returncode

    # Anything actually staged?
    r = run(["git", "diff", "--cached", "--name-only"])
    staged = [s for s in r.stdout.splitlines() if s.strip()]
    if not staged:
        print("No changes to commit. Cloud is already up to date.")
        return 0

    print("Staging:", staged)

    # Commit
    msg = _default_message(args.message)
    r = run(["git", "commit", "-m", msg])
    if r.returncode != 0:
        print("git commit failed:", r.stderr)
        return r.returncode
    print("Committed:", msg)

    if args.no_push:
        print("Skipping push (--no-push).")
        return 0

    # Push
    r = run(["git", "push"])
    if r.returncode != 0:
        print("git push failed:", r.stderr)
        return r.returncode
    print("Pushed. Streamlit Cloud should redeploy within ~30 seconds.")
    return 0


def _default_message(override: str | None) -> str:
    if override:
        return override
    ts = datetime.now(tz=SGT).strftime("%Y-%m-%d %H:%M SGT")
    return f"AQE refresh {ts}"


if __name__ == "__main__":
    sys.exit(main())
