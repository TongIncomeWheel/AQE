"""
cli.py — the Phase 1 entrypoint.

  python -m aegis_runtime.cli premarket --date 2026-07-21          (real: needs an API key)
  AEGIS_MOCK=1 python -m aegis_runtime.cli premarket --date 2026-07-21   (offline, free)
  python -m aegis_runtime.cli chief "run premarket for 2026-07-21"  (Layer-2 intent -> action)
"""
import os
import sys
import argparse

from .orchestrator import Orchestrator


def _kernel_root():
    # runtime/aegis_runtime/cli.py -> kernel is two levels up from this package
    here = os.path.dirname(os.path.abspath(__file__))
    return os.environ.get("AEGIS_KERNEL", os.path.dirname(os.path.dirname(here)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aegis-runtime", description="Aegis runtime — Phase 1")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("premarket"); p.add_argument("--date", required=True)
    c = sub.add_parser("chief"); c.add_argument("instruction"); c.add_argument("--date", default=None)
    a = ap.parse_args(argv)

    kernel = _kernel_root()
    orch = Orchestrator(kernel)

    if a.cmd == "premarket":
        s = orch.run_premarket(a.date)
    else:  # chief — demonstrate the Layer-2 interpreter
        s = orch.dispatch(a.instruction, a.date or "2026-07-21")

    print("\n=== RUN SUMMARY ===")
    print(f"date        {s['date']}")
    print(f"voices ran  {s['voices_ran']}/11")
    print(f"nominated   {s['nominated']} names")
    print(f"shortlist   {s['shortlist']}  |  ADVANCE {s['advance']}")
    print(f"artifacts   {s['out_dir']}")
    print(f"\n{s.get('funnel_summary','')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
