"""Dead-man check for the alert poller, runnable from anywhere that has the Drive
credentials (a scheduled routine, the GitHub workflow_dispatch, a laptop).

    python -m scripts.alert_deadman          # check; email once/day if stale
    python -m scripts.alert_deadman --dry    # check only, never email

Exit 1 when the primary poller is stale inside the US window (so a CI step can
fail loudly), 0 otherwise. Reads `aqe_alert_heartbeat.json`; a missing/unreadable
heartbeat inside the window counts as stale -- never a silent pass.
"""
import sys

from src.alerts.heartbeat import check_and_alarm


def main() -> int:
    st = check_and_alarm(send="--dry" not in sys.argv)
    print("[alert_deadman]", st)
    return 1 if st.get("stale") else 0


if __name__ == "__main__":
    raise SystemExit(main())
