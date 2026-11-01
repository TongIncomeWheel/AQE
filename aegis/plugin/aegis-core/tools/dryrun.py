#!/usr/bin/env python3
"""
dryrun.py — pre-pilot readiness check (D-50). ONE command, GREEN/RED per layer.

Runs the DETERMINISTIC checks only (kernel, config, secrets, push auth, state,
notifications) — the parts that don't need a live connector. The connector +
agentic-flow steps (Drive/FMP/broker pulls, a supervised /pm, the gatekeeper
refusal) are in DRYRUN.md and are driven by the session, since MCP tools aren't
reachable from plain Python.

Order-blind, read-only: places/sizes/arms NOTHING. Safe to run any time.

  python3 aegis/tools/dryrun.py          # human report; exit 0 = all green
  python3 aegis/tools/dryrun.py --json
"""

import os, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
DATA = os.path.join(ROOT, "data")


def _try(fn):
    try:
        return fn()
    except Exception as e:
        return e


def checks():
    out = []

    def add(name, ok, detail):
        out.append({"check": name, "pass": bool(ok), "detail": str(detail)})

    # 1 kernel current
    dl = os.path.join(ROOT, "charter", "decisions_log.md")
    txt = open(dl).read() if os.path.exists(dl) else ""
    add("kernel_current", "D-49" in txt, "decisions_log has D-49" if "D-49" in txt else "stale/missing decisions_log")

    # 2 contracts valid
    bad = []
    for f in glob.glob(os.path.join(ROOT, "contracts", "*.json")):
        r = _try(lambda: json.load(open(f)))
        if isinstance(r, Exception):
            bad.append(os.path.basename(f))
    add("contracts_valid", not bad, f"{len(glob.glob(os.path.join(ROOT,'contracts','*.json')))} contracts, bad={bad}")

    # 3 fund config
    def fc():
        import fund_config as F
        cap = F.allocated_capital() if hasattr(F, "allocated_capital") else None
        return cap
    cap = _try(fc)
    add("fund_config", isinstance(cap, (int, float)) and cap, f"allocated_capital={cap}")

    # 4 historical store
    man = _try(lambda: json.load(open(os.path.join(DATA, "historical", "manifest.json"))))
    n = man.get("n_tickers") if isinstance(man, dict) else None
    add("historical_store", isinstance(n, int) and n > 500, f"n_tickers={n}")

    # 5 preflight (GITHUB_PAT)
    def pf():
        import preflight as P
        return P.check()
    p = _try(pf)
    add("secrets_preflight", isinstance(p, dict) and p.get("ready"),
        p.get("missing") if isinstance(p, dict) else p)

    # 6 git push auth
    def gs():
        import git_sync as G
        return G.check()
    g = _try(gs)
    add("git_push_auth", isinstance(g, dict) and g.get("reachable"),
        f"reachable={g.get('reachable')} token={g.get('token_present')}" if isinstance(g, dict) else g)

    # 7 ops_status assembles
    def ops():
        import ops_status as O
        s = O.assemble()
        return s.get("status")
    st = _try(ops)
    add("ops_status_renders", st in ("ALIVE", "PARTIAL", "DEGRADED"), f"status={st}")

    # 8 notify cowork-native
    def nt():
        import notify as N
        r = N.send("pre_run", {"loop": "dryrun", "at": "test"}, dry_run=True)
        return r
    r = _try(nt)
    add("notify_ready", isinstance(r, dict) and r.get("ok"),
        f"channel={r.get('channel')}" if isinstance(r, dict) else r)

    # 9 self-heal doctrine sanity (gate never healed; transient heals)
    def sh():
        import self_heal as S
        return S.classify("tripwire") == "gate" and S.classify("ptj_pull") == "transient"
    add("self_heal_doctrine", _try(sh) is True, "tripwire=gate, ptj_pull=transient")

    return out


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    res = checks()
    allgreen = all(c["pass"] for c in res)
    if "--json" in args:
        print(json.dumps({"ready": allgreen, "checks": res}, indent=2))
    else:
        print("AEGIS DRY-RUN READINESS (deterministic core) — " + ("ALL GREEN ✓" if allgreen else "ATTENTION ✗"))
        for c in res:
            print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['check']:20s} {c['detail']}")
        print("\n  Order-blind / read-only. Connector + /pm flow steps: see DRYRUN.md.")
    sys.exit(0 if allgreen else 1)


if __name__ == "__main__":
    main()
