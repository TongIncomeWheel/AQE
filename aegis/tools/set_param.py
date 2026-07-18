#!/usr/bin/env python3
"""PM parameter changes — the config layer. The agent runs this when the PM says e.g.
'set the market cap floor to 1.5bn':
    python3 set_param.py universe.screen.market_cap_min_usd 1500000000 --reason "PM: widen small-cap access"
Validates the key EXISTS in parameters.yaml (new keys need a law change, not a tweak),
updates the value, appends a dated entry to charter/decisions_log.md, and git-commits if in a repo.
One source of truth, every tweak logged. Law (rulebook.yaml) is refused by design.
"""
import argparse, subprocess, sys, os
from datetime import date
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = os.path.join(ROOT, "charter", "parameters.yaml")
LOG = os.path.join(ROOT, "charter", "decisions_log.md")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key"); ap.add_argument("value"); ap.add_argument("--reason", required=True)
    a = ap.parse_args()
    doc = yaml.safe_load(open(PARAMS))
    node, parts = doc, a.key.split(".")
    for p in parts[:-1]:
        if not isinstance(node, dict) or p not in node:
            sys.exit(f"REFUSED: '{a.key}' not in parameters.yaml — new keys are a law change, take it to the committee path")
        node = node[p]
    if not isinstance(node, dict):
        sys.exit(f"REFUSED: '{a.key}' path passes through a scalar")
    leaf = parts[-1]
    if leaf not in node: sys.exit(f"REFUSED: '{a.key}' not in parameters.yaml")
    old = node[leaf]
    try: new = yaml.safe_load(a.value)
    except Exception: new = a.value
    def _num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)   # QA-F3: bool is NOT a number
    ok = (type(old) is type(new)) or (_num(old) and _num(new)) or old is None
    if not ok:
        sys.exit(f"REFUSED: type mismatch ({type(old).__name__} -> {type(new).__name__})")
    node[leaf] = new
    yaml.dump(doc, open(PARAMS, "w"), sort_keys=False, allow_unicode=True)
    entry = f"| P-{date.today():%y%m%d} | {date.today()} | Parameter `{a.key}`: `{old}` → `{new}`. Reason: {a.reason} | prior value |\n"
    lines = open(LOG).read().splitlines(keepends=True)
    for i, l in enumerate(lines):
        if l.startswith("| D-") or l.startswith("| P-"):
            lines.insert(i, entry); break
    open(LOG, "w").writelines(lines)
    subprocess.run(["git", "-C", ROOT, "commit", "-am", f"param: {a.key} {old} -> {new} ({a.reason})"], capture_output=True)
    print(f"OK {a.key}: {old} -> {new} (logged + committed if repo)")

if __name__ == "__main__":
    main()
