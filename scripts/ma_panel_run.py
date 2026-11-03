"""Pre-step: refresh the whole-market ma_panel to the last completed session and persist it (.github/workflows/ma-panel.yml).

Exit 0 only when the panel is current (FRESH or REFRESHED); 1 otherwise, so the workflow shows red and the conductor knows the
nightly's breadth will read STALE.
    python -m scripts.ma_panel_run [--budget-minutes 55]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-minutes", type=float, default=55.0)
    a = ap.parse_args(argv)
    from src.scanner import ma_refresh
    # A fresh runner holds none of the runtime state, and the snapshot is ONE zip: saving it after restoring only the
    # ma_panel would replace the full snapshot with a thin one. Restore the WHOLE snapshot first (GitHub release asset is
    # the primary store, Drive the backup), refresh, then save - so the zip that goes back is complete.
    try:
        from src.data import persist
        got = persist.load_snapshot_github()
        if not (got or {}).get("ok"):
            got = persist.load_snapshot()
        print("restore:", {k: v for k, v in (got or {}).items() if k in ("ok", "reason", "restored")})
        if not (got or {}).get("ok"):
            print("no snapshot restored - refusing to save a thin one over the real snapshot")
            return 1
    except Exception as e:  # noqa: BLE001
        print(f"restore FAILED: {e} - refusing to save a thin snapshot")
        return 1
    r = ma_refresh.refresh_for_breadth(budget_s=a.budget_minutes * 60)
    print(ma_refresh.summary_line(r))
    if r["status"] in ("FRESH", "REFRESHED") or (r.get("after") or r.get("before")):
        try:
            from src.data.persist import save_snapshot_everywhere as save_snapshot
            print("persist:", save_snapshot())
        except Exception as e:  # noqa: BLE001
            print(f"persist FAILED: {e}")
            return 1
    return 0 if r["status"] in ("FRESH", "REFRESHED") else 1


if __name__ == "__main__":
    sys.exit(main())
