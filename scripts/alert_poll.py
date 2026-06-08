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

from src.alerts.engine import run_alert_cycle


def main() -> int:
    if "--test-email" in sys.argv:
        from src.alerts.emailer import send_test
        res = send_test()
        print("[alert_poll] test email:", "OK ->" + str(res.get("to"))
              if res.get("ok") else "FAILED -> " + str(res.get("reason")))
        return 0 if res.get("ok") else 1

    force = "--force" in sys.argv or "-f" in sys.argv
    summary = run_alert_cycle(send_email=True, force=force)
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
