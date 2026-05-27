"""Smoke test for the AIC web layer.

Verifies (without launching the server) that:
  1. All three brief composers return valid dataclasses (even with no AQE data).
  2. All three Telegram formatters produce non-empty text.
  3. Telegram text obeys the 40-line spec cap.
  4. View modules are importable (catches missing-symbol regressions).

Run:
    python -m src.aic.web.smoke_test
"""

from __future__ import annotations

import sys


def main() -> int:
    failures: list[str] = []

    # 1) Composers
    try:
        from src.aic.web.brief_data import (
            compose_close,
            compose_open,
            compose_premarket,
        )
        pm = compose_premarket()
        mo = compose_open()
        mc = compose_close()
        assert pm.regime in ("GREEN", "YELLOW", "ORANGE", "RED")
        assert mo.regime in ("GREEN", "YELLOW", "ORANGE", "RED")
        assert mc.regime in ("GREEN", "YELLOW", "ORANGE", "RED")
        print(f"[OK] composers: pre-market regime={pm.regime} "
              f"({len(pm.stop_audit)} stops, {len(pm.pipeline_x_aqe)} pipeline rows, "
              f"{len(pm.new_aqe_candidates)} new AQE)")
        print(f"[OK] composers: market-open regime={mo.regime} "
              f"({len(mo.gaps)} gaps, {len(mo.brackets)} brackets)")
        print(f"[OK] composers: market-close regime={mc.regime} "
              f"({len(mc.eod_positions)} eod, {len(mc.trail_events)} trail events)")
    except Exception as e:
        failures.append(f"composers: {e!r}")

    # 2) Telegram formatters
    try:
        from src.aic.delivery.brief_formatters import (
            format_close_telegram,
            format_open_telegram,
            format_premarket_telegram,
        )
        pm_text = format_premarket_telegram(pm)
        mo_text = format_open_telegram(mo)
        mc_text = format_close_telegram(mc)
        for label, text in (("premarket", pm_text),
                            ("open", mo_text),
                            ("close", mc_text)):
            n = len(text.splitlines())
            assert text.strip(), f"{label}: empty text"
            assert n <= 40, f"{label}: {n} lines > 40 cap"
            assert "aegis.local" in text, f"{label}: missing web link footer"
            print(f"[OK] telegram[{label}]: {n} lines, "
                  f"footer present, {len(text)} chars")
    except Exception as e:
        failures.append(f"telegram formatters: {e!r}")

    # 3) View modules import
    try:
        import src.aic.web.views_close                                              # noqa: F401
        import src.aic.web.views_open                                               # noqa: F401
        import src.aic.web.views_premarket                                          # noqa: F401
        print("[OK] view modules importable (premarket/open/close)")
    except Exception as e:
        failures.append(f"view imports: {e!r}")

    # 4) App module imports (smokes route registration & nicegui boot deps)
    try:
        import src.aic.web.app                                                      # noqa: F401
        print("[OK] app module importable -- routes registered")
    except Exception as e:
        failures.append(f"app import: {e!r}")

    if failures:
        print("\n=== FAILED ===")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\n=== ALL CHECKS PASSED ===")
    print("\nPreview each brief at:")
    print("  http://localhost:8765/")
    print("  http://localhost:8765/brief/premarket")
    print("  http://localhost:8765/brief/open")
    print("  http://localhost:8765/brief/close")
    print("  http://localhost:8765/telegram/premarket")
    return 0


if __name__ == "__main__":
    sys.exit(main())
