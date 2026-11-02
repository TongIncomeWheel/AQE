"""GitHub Actions backstop for the live alert engine.

Runs one alert cycle independent of the HF Space, so level alerts still fire if
the Space is asleep. Shares the same Drive dedup state as the in-app poller, so
the two never double-email. The cron in .github/workflows/alerts.yml runs this
every 15 min during US market hours.

Pulls the export + dedup state from Drive (no local parquet needed). Requires the
same secrets as the app: OAuth triple (Drive), FMP_API_KEY, AQE_SMTP_*.

    python -m scripts.alert_poll          # respects the market-hours gate
    python -m scripts.alert_poll --force  # ignore the gate (manual test)
"""

from __future__ import annotations

import sys
import time

from src.alerts.engine import run_alert_cycle

# WHY THE STOPWATCH. Two cycles were CANCELLED on the job timeout (2026-08-06,
# 16:58 and 18:24 UTC) and GitHub does not retain logs for cancelled jobs, so
# there was no way to tell WHICH step hung — export fetch, FMP quotes, Drive
# state, ledger, or the email. A cycle that can die without saying where is a
# cycle that cannot be fixed, only guessed at. Every phase now prints its own
# elapsed time as it completes, so the next timeout leaves a trail even when
# the job is killed mid-flight.
_T0 = time.time()


def _tick(label: str) -> None:
    print(f"[alert_poll] +{time.time() - _T0:6.1f}s  {label}", flush=True)


def main() -> int:
    if "--test-email" in sys.argv:
        from src.alerts.emailer import send_test
        res = send_test()
        print("[alert_poll] test email:", "OK ->" + str(res.get("to"))
              if res.get("ok") else "FAILED -> " + str(res.get("reason")))
        return 0 if res.get("ok") else 1

    if "--deadman" in sys.argv:           # dead-man check only (no cycle)
        from src.alerts.heartbeat import check_and_alarm
        st = check_and_alarm()
        print("[alert_poll] deadman:", st)
        return 1 if st.get("stale") else 0

    force = "--force" in sys.argv or "-f" in sys.argv
    try:                                   # the backstop doubles as a dead-man check on the primary
        from src.alerts.heartbeat import check_and_alarm
        st = check_and_alarm()
        print("[alert_poll] primary poller:", st.get("reason"))
    except Exception as exc:  # noqa: BLE001
        print("[alert_poll] deadman pre-check failed:", exc)
    _tick("cycle start")
    summary = run_alert_cycle(send_email=True, force=force)
    _tick("cycle done")
    print("[alert_poll]", summary.get("reason") or "ok",
          "| checked:", summary.get("checked"),
          "| new:", summary.get("new_triggers"),
          "| emailed:", summary.get("emailed"))
    for t in summary.get("triggers") or []:
        print(f"  - {t['ticker']} [{t['source']}] {t['label']} @ {t.get('level_price')}")
    # Always exit 0 — a quiet cycle (no triggers / off-hours) is not a failure.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
