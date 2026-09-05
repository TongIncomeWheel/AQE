#!/usr/bin/env python3
"""
preflight.py — session secret/config check (D-49).

The one secret Aegis needs LOCALLY is the GitHub push token (GITHUB_PAT) — the
market-data brokers and Drive are OAuth connectors, no local secret. The token
must NEVER ship in the install pack (a secret in a distributable = a leak); it
lives only in the gitignored aegis/config/.env. So a fresh deployment (or a
workspace that lost its .env) needs a way to notice the token is missing and ask
the PM for it ONCE — rather than silently failing to push at post-market.

This tool is that check. It is read-only and order-blind (constitution law 1):
it verifies presence, it never handles orders. Run it at session/loop start; if
it reports MISSING, ask the PM for the key (the fix one-liner is printed) and
save it to config/.env, then proceed.

CLI:
  preflight.py            # human card; exit 0 = ready, exit 1 = required secret missing
  preflight.py --json     # machine form for a loop's step 0
"""

import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENVFILE = os.path.join(ROOT, "config", ".env")

# name -> (required?, why, fix one-liner the PM can paste in chat)
SECRETS = {
    # v5.3 (2026-09-05): NOT required. The sandbox git proxy returns 403 for this repo regardless of
    # any token ("not in this session's authorized repository set"), and the GitHub connector
    # (push_files) is the working push path and needs no local secret. A missing PAT is therefore a
    # WARNING that names the push path, never a stop. The old "no GitHub connector exists — D-48"
    # premise is false on Cowork. Also: config/.env is gitignored and dies with every fresh container,
    # so treating it as required guaranteed a page to the PM every single morning.
    "GITHUB_PAT": (False,
        "native git push (optional — the connector path needs no secret; the sandbox proxy blocks native push for this repo anyway)",
        "Optional. Push goes via the GitHub connector (push_files)."),
    "FMP_API_KEY": (False,
        "only if FMP is used via raw REST; on Cowork FMP is an OAuth connector (no local secret needed)",
        "Optional — connector-based on Cowork."),
}

CONNECTORS_NOTE = ("Market data + book: FMP, Tiger, Google Drive and GitHub are OAuth CONNECTORS "
                   "(no local secret). config/.env is optional and is wiped with every fresh container.")


def _env_file_values():
    vals = {}
    if os.path.exists(ENVFILE):
        for line in open(ENVFILE):
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            vals[k.strip()] = v.split("#", 1)[0].strip().strip('"').strip("'")
    return vals


def check():
    env_file = _env_file_values()
    present, missing = [], []
    for name, (required, why, fix) in SECRETS.items():
        have = bool(os.environ.get(name) or env_file.get(name))
        if have:
            present.append(name)
        elif required:
            missing.append({"name": name, "why": why, "fix": fix})
    # is config/.env safely gitignored?
    ignored = None
    try:
        import subprocess
        r = subprocess.run(["git", "-C", ROOT, "check-ignore", "config/.env"],
                           capture_output=True, text=True, timeout=8)
        # 0 = ignored (good) · 1 = tracked/not-ignored (real problem) · else (128 = not a git repo) = unknown
        ignored = True if r.returncode == 0 else (False if r.returncode == 1 else None)
    except Exception:
        ignored = None
    push_path = "native git (GITHUB_PAT present)" if "GITHUB_PAT" in present else "GitHub connector (push_files) — no local secret needed"
    return {"ready": not missing, "present": present, "missing": missing,
            "env_file_exists": os.path.exists(ENVFILE), "env_gitignored": ignored,
            "push_path": push_path, "note": CONNECTORS_NOTE}


def _card(s):
    L = ["AEGIS PREFLIGHT — " + ("READY ✓" if s["ready"] else "ACTION NEEDED ✗")]
    L.append(f"  config/.env: {'found' if s['env_file_exists'] else 'MISSING'}"
             + (f"  ·  gitignored: {'yes ✓' if s['env_gitignored'] else 'NO — fix .gitignore!'}"
                if s["env_gitignored"] is not None else ""))
    if s["present"]:
        L.append("  present: " + ", ".join(s["present"]))
    for m in s["missing"]:
        L.append(f"  ✗ MISSING {m['name']} — {m['why']}")
        L.append(f"      → {m['fix']}")
    L.append("  push path: " + s.get("push_path", "?"))
    L.append("  " + s["note"])
    return "\n".join(L)


def _main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    s = check()
    if "--json" in args:
        print(json.dumps(s, indent=2))
    else:
        print(_card(s))
    sys.exit(0 if s["ready"] else 1)


if __name__ == "__main__":
    _main()
