"""Pause / resume / status for ALL alerts (PM order 2026-11-12). One reversible Drive flag; see src/alerts/pause.py.

    python -m scripts.alerts_pause status
    python -m scripts.alerts_pause pause  [--reason "..."]
    python -m scripts.alerts_pause resume [--reason "..."]

Prints the flag read back from Drive. Exit 1 if a write did not land.
"""
import sys

from src.alerts import pause


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    cmd = a[0] if a else "status"
    reason = a[a.index("--reason") + 1] if "--reason" in a and a.index("--reason") + 1 < len(a) else ""
    try:
        if cmd == "pause":
            st = pause.set_paused(True, reason or "PM order 2026-11-12: pause all alerts until the PM resumes")
        elif cmd == "resume":
            st = pause.set_paused(False, reason or "PM resumed alerts")
        elif cmd == "status":
            st = pause.status()
        else:
            print("usage: alerts_pause [status|pause|resume] [--reason TEXT]")
            return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[alerts_pause] FAILED: {type(exc).__name__}: {exc}")
        return 1
    print(f"[alerts_pause] {cmd}: " + ("PAUSED" if st["paused"] else "RUNNING"), st)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
