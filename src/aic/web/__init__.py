"""AIC web layer -- NiceGUI app for the Aegis briefs (S02 / S11 / S12).

Mobile-first per spec §14.24. The same Python brief composers used here are also
consumed by `src.aic.delivery.brief_formatters` to produce the Telegram messages,
so web view and push are guaranteed to show the same numbers.

Launch:
    run_aic_web.bat                          (Windows double-click)
    python -m src.aic.web.app                (CLI / IDE)
"""

DEFAULT_PORT = 8765
